"""Run-aware CLI, evidence and compare-and-restore recovery for goalrun.

The engine's path bindings and SESSION exist only in one CLI process. Durable
state lives in Store, independently of the installed script or agent host.
"""
import argparse
import base64
from contextlib import contextmanager, redirect_stderr, redirect_stdout
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import time
import uuid

from run_store import RunError, Store

ACTIONS = ('init', 'list', 'inspect', 'resume', 'checkpoint', 'release', 'migrate')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def atomic_json(store, path, data):
    store._safe(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    store._atomic(path, data)


@contextmanager
def workspace_lock(engine):
    store = Store()
    store._safe(os.path.join(store.root, '.testcases', 'goalrun.lock'))
    lock = engine.hold_lock()
    try:
        yield lock
    finally:
        engine.drop_lock(lock)


def fingerprint(store, view, engine):
    # Same exclusions as the original baseline. Include ignored run inputs explicitly.
    files = {'runtime': sys.version + '|' + sys.executable + '|' + os.environ.get('PATH', '')}
    for label, path in (('engine', engine.__file__), ('cli', __file__),
                        ('store', sys.modules[Store.__module__].__file__)):
        files[label] = engine._mark(path)
    for base, dirs, names in os.walk(store.root):
        dirs[:] = [d for d in dirs if d not in engine.BASELINE_SKIP]
        for name in names + [d for d in dirs if os.path.islink(os.path.join(base, d))]:
            full = os.path.join(base, name)
            files[os.path.relpath(full, store.root)] = engine._mark(full)
    # Fingerprint authoritative inputs, not derived session logs/CSV/review exports.
    # Source/tests/tracked case tables are covered by the workspace walk above.
    for name in ('reqs.txt', 'ledger.tsv', 'baseline.json', 'signoff.tsv'):
        full = store._safe(os.path.join(view['paths']['goalrun_dir'], name))
        files['run-input:' + name] = engine._mark(full) if os.path.exists(full) else 'absent'
    # Local spec paths outside the workspace are read-only inputs too.
    spec = view['manifest']['spec']
    if spec:
        full = spec if os.path.isabs(spec) else os.path.join(store.root, spec)
        files['spec:' + spec] = engine._mark(os.path.realpath(full)) if os.path.isfile(full) else 'unavailable'
    return digest(json.dumps(files, sort_keys=True).encode())


def evidence_view(store, view, engine):
    evidence = view['checkpoint'].get('last_evidence')
    view['last_evidence'] = evidence
    view['evidence_stale'] = (evidence is None or
                              evidence.get('ownership_epoch') != view['checkpoint']['ownership_epoch'] or
                              evidence.get('fingerprint') != fingerprint(store, view, engine))
    # Inspection/listing cannot confer writer privileges.
    view['checkpoint'] = dict(view['checkpoint'])
    view['checkpoint'].pop('token', None)
    return view


def journal_path(store, run_id, row_id):
    # Row IDs aren't filenames: existing ledger IDs can contain punctuation/slashes.
    return store._safe(os.path.join(store._paths(run_id)['goalrun_dir'], 'undo',
                                    digest(row_id.encode()) + '.json'))


def prepare_undo(store, run_id, row_id, path, original, planted):
    full = store._safe(os.path.join(store.root, path))
    if os.path.islink(full) or os.path.realpath(full) != os.path.abspath(full):
        raise RunError('verify cannot journal a symlinked source path')
    record = {'version': 1, 'run_id': run_id, 'row_id': row_id,
              'path': os.path.relpath(full, store.root),
              'original': base64.b64encode(original).decode(),
              'planted_hash': None if planted is None else digest(planted)}
    atomic_json(store, journal_path(store, run_id, row_id), record)


def recover(store, engine):
    """Called under the workspace lock, across ALL runs before source is trusted."""
    for summary in store.list():
        run_id = summary['run_id']
        directory = store._safe(os.path.join(store._paths(run_id)['goalrun_dir'], 'undo'))
        for path in sorted(Path(directory).glob('*.json')):
            record = store._read(str(path))
            if record.get('version') != 1 or record.get('run_id') != run_id:
                raise RunError(f'unsupported recovery journal: {path}')
            rel = record.get('path')
            if not isinstance(rel, str) or os.path.isabs(rel):
                raise RunError(f'invalid recovery path: {path}')
            full = store._safe(os.path.join(store.root, rel))
            if os.path.islink(full) or os.path.realpath(full) != os.path.abspath(full):
                raise RunError(f'recovery target is symlinked: {rel}')
            try:
                original = base64.b64decode(record['original'], validate=True)
            except (KeyError, ValueError, TypeError) as exc:
                raise RunError(f'invalid recovery bytes: {path}') from exc
            current = Path(full).read_bytes() if os.path.exists(full) else None
            if current == original:
                pass  # crash before planting or after restoration
            elif (current is None and record['planted_hash'] is None) or \
                    (current is not None and digest(current) == record['planted_hash']):
                engine.restore((full, original))
                print(f'recovered {run_id}/{record["row_id"]}: {rel}', file=sys.stderr)
            else:
                raise RunError(f'recovery conflict at {rel} in {run_id}: source changed after verify; '
                               'reconcile it with the journal before continuing')
            path.unlink()
    # Legacy undo bytes have no planted fingerprint. Never blindly overwrite edits.
    legacy = Path(store.root) / '.testcases/goalrun/undo'
    if legacy.is_dir() and any(legacy.iterdir()):
        raise RunError('legacy pending undo has no guarded fingerprint; reconcile before named runs')


class Tee:
    def __init__(self, terminal, log):
        self.terminal, self.log = terminal, log

    def write(self, value):
        self.terminal.write(value)
        self.log.write(value)
        self.log.flush()
        return len(value)

    def flush(self):
        self.terminal.flush()
        self.log.flush()


class Session:
    def __init__(self, store, run_id, token, engine, args, workspace_fd):
        self.store, self.run_id, self.token, self.engine, self.args = store, run_id, token, engine, args
        self.workspace_fd = workspace_fd
        self.active_row = None
        self.view = store.require(run_id, token)
        self.evidence_dir = store._safe(os.path.join(self.view['paths']['run_dir'], 'evidence'))
        os.makedirs(self.evidence_dir, exist_ok=True)
        self.evidence_id = str(uuid.uuid4())
        self.rows = {}
        self.checks = []
        self.before = fingerprint(store, self.view, engine)

    def record_row(self, row, status, note):
        self.rows[row.id] = {'status': status, 'note': note}

    def record_check(self, command, exit_code, output, timed_out):
        entry = {'command': command, 'exit_code': exit_code, 'timed_out': timed_out, 'output': output}
        self.checks.append(entry)
        # Each command survives interruption even if no final result was written.
        path = os.path.join(self.evidence_dir, self.evidence_id + f'-check-{len(self.checks)}.json')
        atomic_json(self.store, path, entry)

    def prepare(self, row_id, path, original, planted):
        self.active_row = row_id
        prepare_undo(self.store, self.run_id, row_id, path, original, planted)

    def guard_restore(self, full, original):
        path = journal_path(self.store, self.run_id, self.active_row)
        record = self.store._read(path)
        self.store._safe(full)
        if os.path.islink(full) or os.path.realpath(full) != os.path.abspath(full):
            raise RunError('restore target became symlinked; reconcile pending journal')
        current = Path(full).read_bytes() if os.path.exists(full) else None
        if current == original:
            return
        if (current is None and record['planted_hash'] is None) or \
                (current is not None and digest(current) == record['planted_hash']):
            return
        raise RunError(f'recovery conflict at {full}: source changed during verify; journal retained')

    def restored(self, row_id):
        # Compare-and-restore guard runs before engine restoration too.
        path = journal_path(self.store, self.run_id, row_id)
        if os.path.exists(path):
            os.unlink(path)

    def finish(self, code, log_path):
        view = self.store.require(self.run_id, self.token)
        cp = view['checkpoint']
        for row_id, outcome in self.rows.items():
            if outcome['status'] not in ('PASS', 'VERIFIED', 'WAIT'):
                cp['failures'][row_id] = cp['failures'].get(row_id, 0) + 1
        after = fingerprint(self.store, view, self.engine)
        result = {'id': self.evidence_id, 'at': time.time(), 'exit_code': code,
                  'argv': [a for a in sys.argv[1:] if a != self.token],
                  'fingerprint': after, 'input_fingerprint': self.before,
                  'inputs_changed': self.before != after, 'rows': self.rows,
                  'ownership_epoch': cp['ownership_epoch'],
                  'log': log_path, 'checks': len(self.checks),
                  'whole_ledger_verified': code == 0 and self.args.verify == '' and self.before == after}
        atomic_json(self.store, os.path.join(self.evidence_dir, self.evidence_id + '.json'), result)
        cp['last_evidence'] = result
        cp['generation'] += 1
        self.store._save(view, cp)


@contextmanager
def bind(engine, view, session):
    paths = view['paths']
    names = ('GOAL_DIR', 'LEDGER', 'SIGNOFF', 'BASELINE', 'UNDO_DIR', 'SESSION')
    old = {name: getattr(engine, name) for name in names}
    engine.GOAL_DIR = paths['goalrun_dir']
    engine.LEDGER = os.path.join(engine.GOAL_DIR, 'ledger.tsv')
    engine.SIGNOFF = os.path.join(engine.GOAL_DIR, 'signoff.tsv')
    engine.BASELINE = os.path.join(engine.GOAL_DIR, 'baseline.json')
    engine.UNDO_DIR = os.path.join(engine.GOAL_DIR, 'undo')
    engine.SESSION = session
    try:
        yield
    finally:
        for name, value in old.items():
            setattr(engine, name, value)


def require_baseline(view, engine):
    path = os.path.join(view['paths']['goalrun_dir'], 'baseline.json')
    baseline = engine.read_baseline(path=path)
    if not isinstance(baseline, dict) or not isinstance(baseline.get('files'), dict):
        raise RunError('run baseline missing or invalid; restore the original baseline, never retake it')


def named_engine(engine, args):
    store = Store()
    if not args.run:
        if store.list():
            raise RunError('named runs exist; select --run explicitly (list/inspect to find unfinished work)')
        if args.token:
            raise RunError('--token requires --run')
        return engine.run(args)
    if args.ledger is not None or args.requirements is not None:
        raise RunError('named runs bind ledger and requirements together; do not override their paths')
    if args.baseline is not None or args.reset:
        raise RunError('named baseline is taken once by init; resume never retakes or resets it')
    with store.lock(args.run), workspace_lock(engine) as lock:
        view = store.require(args.run, args.token)
        recover(store, engine)
        require_baseline(view, engine)
        session = Session(store, args.run, args.token, engine, args, lock.fileno())
        log_path = os.path.join(session.evidence_dir, session.evidence_id + '.log')
        with bind(engine, view, session), open(log_path, 'w', encoding='utf-8') as log:
            args.ledger = engine.LEDGER
            if args.lint_ledger:
                args.requirements = os.path.join(engine.GOAL_DIR, 'reqs.txt')
            code = 2
            with redirect_stdout(Tee(sys.stdout, log)), redirect_stderr(Tee(sys.stderr, log)):
                try:
                    if args.verify == '':
                        rows = engine.load(engine.LEDGER)
                        reqs = engine.read_requirements(os.path.join(engine.GOAL_DIR, 'reqs.txt'))
                        problems = engine.lint(rows, engine.load_signatures(),
                                               has_baseline=True, waived=engine.waivers(engine.LEDGER),
                                               requirements=reqs)
                        if problems:
                            for problem in problems:
                                print(problem)
                            print('NOT DONE — ledger coverage or design failed lint')
                            code = 1
                            return code
                    code = engine.run(args, locked=True)
                    if args.verify == '' and code == 0 and session.before != fingerprint(store, view, engine):
                        print('NOT DONE — inputs changed during verification; rerun on stable inputs')
                        code = 1
                    return code
                except KeyboardInterrupt:
                    code = 130
                    raise
                finally:
                    session.finish(code, log_path)


def initialize_run(store, engine, args):
    """Stage the complete payload before making the run visible to other controllers."""
    destination = store._paths(args.run_id)['testcases']
    cases = Path(store.root) / 'testcases.md'
    migrating_cases = args.action == 'migrate' and cases.exists()
    if migrating_cases and os.path.lexists(destination):
        raise RunError('migration testcase destination already exists; reconcile its permanent IDs first')
    linked_table = None

    def populate(paths):
        nonlocal linked_table
        if args.action == 'init':
            engine.take_baseline(path=os.path.join(paths['goalrun_dir'], 'baseline.json'))
            return
        legacy = Path(store.root) / '.testcases/goalrun'
        for name in ('ledger.tsv', 'reqs.txt', 'baseline.json', 'signoff.tsv'):
            if (legacy / name).exists():
                shutil.copy2(legacy / name, Path(paths['goalrun_dir']) / name)
        for name, dest in (('docs-review', 'docs_review_dir'), ('testcase', 'testcase_dir')):
            source = Path(store.root) / '.testcases' / name
            if source.exists():
                shutil.copytree(source, paths[dest], dirs_exist_ok=True)
        if migrating_cases:
            staged_table = Path(paths['run_dir']) / 'migrated-testcases.md'
            shutil.copy2(cases, staged_table)
            store._safe(destination)
            os.makedirs(os.path.dirname(destination), exist_ok=True)
            # Linking a finished payload is exclusive: even a late collision cannot overwrite.
            os.link(staged_table, destination)
            linked_table = os.stat(destination)
            staged_table.unlink()

    try:
        store.create(args.run_id, args.goal, args.spec, populate=populate)
    except BaseException:
        # Do not leave a tracked table behind after a failed publication. Never remove a
        # replacement from another editor, or a table belonging to a successfully published run.
        if linked_table is not None and not os.path.exists(store._paths(args.run_id)['run_dir']):
            try:
                current = os.stat(destination, follow_symlinks=False)
                if (current.st_dev, current.st_ino) == (linked_table.st_dev, linked_table.st_ino):
                    os.unlink(destination)
            except FileNotFoundError:
                pass
        raise


def lifecycle(engine, argv):
    parser = argparse.ArgumentParser(description='Persistent goalrun lifecycle (JSON output)')
    parser.add_argument('action', choices=ACTIONS)
    parser.add_argument('run_id', nargs='?')
    parser.add_argument('--goal')
    parser.add_argument('--spec', default='')
    parser.add_argument('--owner')
    parser.add_argument('--token')
    parser.add_argument('--expected-generation', type=int)
    parser.add_argument('--phase')
    parser.add_argument('--next', dest='next_action')
    parser.add_argument('--note', default='')
    parser.add_argument('--failure')
    a = parser.parse_args(argv)
    store = Store()
    if a.action == 'list':
        if a.run_id:
            raise RunError('list does not take a run id')
        print(json.dumps(store.list(), indent=2))
        return 0
    if not a.run_id:
        raise RunError('select a run id explicitly')
    if a.action == 'inspect':
        print(json.dumps(evidence_view(store, store.inspect(a.run_id), engine), indent=2))
        return 0
    with store.lock(a.run_id), workspace_lock(engine):
        recover(store, engine)
        if a.action in ('init', 'migrate'):
            if a.action == 'migrate':
                legacy = Path(store.root) / '.testcases/goalrun'
                if not (legacy / 'baseline.json').is_file():
                    raise RunError('migration needs the existing legacy baseline; never take a new one mid-work')
            initialize_run(store, engine, a)
            result = store.inspect(a.run_id)
        elif a.action == 'resume':
            existing = store.inspect(a.run_id)
            require_baseline(existing, engine)
            evidence_view(store, existing, engine)  # validate all inputs before revoking an owner
            result = store.resume(a.run_id, a.owner, a.expected_generation)
        elif a.action == 'release':
            result = store.release(a.run_id, a.token, a.note)
        else:
            result = store.checkpoint(a.run_id, a.token, a.phase, a.next_action, a.note, a.failure)
        result = evidence_view(store, result, engine)
        if a.action == 'resume':
            result['token'] = store.inspect(a.run_id)['checkpoint']['token']
        print(json.dumps(result, indent=2))
    return 0
