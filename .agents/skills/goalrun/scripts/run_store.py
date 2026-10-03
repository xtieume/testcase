"""Persistent, fenced goal runs using only the Python standard library.

Mutations do not acquire locks internally. Hold ``store.lock(run_id)`` around
ownership checks, state mutations, and any engine work authorized by a token.
Checkpoint and handoff share one atomic JSON record so a crash cannot split them.
Ownership never expires; takeover requires the observed generation explicitly.
"""
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
import uuid


class RunError(Exception):
    """Invalid run, unsafe storage, stale ownership or an unavailable lock."""


class Store:
    VERSION = 1

    def __init__(self, root='.'):
        self.root = os.path.realpath(os.fspath(root))
        self.runs = os.path.join(self.root, '.testcases', 'runs')

    def _id(self, run_id):
        if not isinstance(run_id, str) or not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_-]{0,79}', run_id):
            raise RunError('run id must be 1–80 letters, digits, underscores or hyphens, starting with a letter or digit')
        return run_id

    def _safe(self, path):
        """Check existing symlink ancestors as well as the final path."""
        full = os.path.abspath(os.fspath(path))
        try:
            if os.path.commonpath((self.root, full)) != self.root or \
                    os.path.commonpath((self.root, os.path.realpath(full))) != self.root:
                raise RunError(f'run path leaves workspace: {full}')
        except ValueError as exc:
            raise RunError(f'run path leaves workspace: {full}') from exc
        if os.path.realpath(full) != full:
            raise RunError(f'run storage path is symlinked: {full}')
        return full

    def _paths(self, run_id):
        run = os.path.join(self.runs, self._id(run_id))
        paths = {
            'run_dir': run,
            'manifest': os.path.join(run, 'manifest.json'),
            'checkpoint': os.path.join(run, 'checkpoint.json'),
            'handoff': os.path.join(run, 'checkpoint.json'),
            'goalrun_dir': os.path.join(run, 'goalrun'),
            'docs_review_dir': os.path.join(run, 'docs-review'),
            'testcase_dir': os.path.join(run, 'testcase'),
            'testcases': os.path.join(self.root, 'docs', 'testcases', run_id, 'testcases.md'),
        }
        for path in paths.values():
            self._safe(path)
        return paths

    @contextmanager
    def lock(self, run_id):
        self._id(run_id)
        self._safe(self.runs)
        try:
            os.makedirs(self.runs, exist_ok=True)
            path = self._safe(os.path.join(self.runs, run_id + '.lock'))
            flags = os.O_CREAT | os.O_RDWR | getattr(os, 'O_NOFOLLOW', 0)
            fd = os.open(path, flags, 0o600)
        except OSError as exc:
            raise RunError(f'cannot open run lock: {exc}') from exc
        try:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                raise RunError(f'run {run_id!r} is locked by another process') from exc
            yield
        finally:
            os.close(fd)

    def _read(self, path):
        self._safe(path)
        try:
            with open(path, encoding='utf-8') as stream:
                data = json.load(stream)
            if not isinstance(data, dict):
                raise ValueError('expected an object')
            return data
        except (OSError, ValueError) as exc:
            raise RunError(f'cannot read run state at {path}: {exc}') from exc

    def _atomic(self, path, value):
        self._safe(path)
        temporary = None
        try:
            fd, temporary = tempfile.mkstemp(suffix='.tmp', dir=os.path.dirname(path))
            with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                json.dump(value, stream, indent=2, sort_keys=True)
                stream.write('\n')
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
            temporary = None
            self._sync_dir(os.path.dirname(path))
        except (OSError, TypeError, ValueError) as exc:
            raise RunError(f'cannot persist run state: {exc}') from exc
        finally:
            if temporary is not None:
                os.unlink(temporary)

    @staticmethod
    def _sync_dir(directory):
        fd = os.open(directory, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)

    def create(self, run_id, goal, spec=''):
        paths = self._paths(run_id)
        if not isinstance(goal, str) or not goal.strip():
            raise RunError('a run needs a nonempty goal')
        if not isinstance(spec, str):
            raise RunError('spec must be a path or description string')
        self._safe(self.runs)
        os.makedirs(self.runs, exist_ok=True)
        if os.path.lexists(paths['run_dir']):
            raise RunError(f'run {run_id!r} already exists')
        manifest = {'version': self.VERSION, 'run_id': run_id, 'workspace': self.root,
                    'goal': goal, 'spec': spec, 'paths': paths}
        checkpoint = {'version': self.VERSION, 'phase': 'plan',
                      'next_action': 'Define requirements and executable ledger',
                      'failures': {}, 'generation': 0, 'ownership_epoch': 0, 'owner': None, 'token': None,
                      'handoff': ''}
        staging = tempfile.mkdtemp(prefix='.' + run_id + '-', dir=self.runs)
        try:
            for name in ('goalrun', 'docs-review', 'testcase'):
                os.mkdir(os.path.join(staging, name))
            self._atomic(os.path.join(staging, 'manifest.json'), manifest)
            self._atomic(os.path.join(staging, 'checkpoint.json'), checkpoint)
            # Cooperating creators hold the same lock; refuse rather than replace
            # any existing target, including an incomplete or symlinked run.
            if os.path.lexists(paths['run_dir']):
                raise RunError(f'run {run_id!r} already exists')
            os.rename(staging, paths['run_dir'])
            staging = None
            self._sync_dir(self.runs)
        except OSError as exc:
            raise RunError(f'cannot create run {run_id!r}: {exc}') from exc
        finally:
            if staging is not None:
                shutil.rmtree(staging)
        return manifest

    def inspect(self, run_id):
        paths = self._paths(run_id)
        manifest = self._read(paths['manifest'])
        checkpoint = self._read(paths['checkpoint'])
        if type(manifest.get('version')) is not int or manifest['version'] != self.VERSION or \
                type(checkpoint.get('version')) is not int or checkpoint['version'] != self.VERSION:
            raise RunError('unsupported run schema version; migrate explicitly')
        if manifest.get('workspace') != self.root:
            raise RunError('run belongs to a different workspace')
        if manifest.get('run_id') != run_id or manifest.get('paths') != paths:
            raise RunError('run manifest has inconsistent paths or identity')
        if not isinstance(manifest.get('goal'), str) or not manifest['goal'].strip() or not isinstance(manifest.get('spec'), str):
            raise RunError('invalid run goal or spec')
        evidence = checkpoint.get('last_evidence')
        if evidence is not None and (not isinstance(evidence, dict) or
                                    not isinstance(evidence.get('fingerprint'), str) or
                                    type(evidence.get('whole_ledger_verified')) is not bool or
                                    not isinstance(evidence.get('rows'), dict)):
            raise RunError('invalid run evidence')
        epoch = checkpoint.get('ownership_epoch')
        if type(epoch) is not int or epoch < 0:
            raise RunError('invalid ownership epoch')
        generation = checkpoint.get('generation')
        failures = checkpoint.get('failures')
        owner, token = checkpoint.get('owner'), checkpoint.get('token')
        if type(generation) is not int or generation < 0 or not isinstance(failures, dict) or \
                any(not isinstance(k, str) or type(v) is not int or v < 0 for k, v in failures.items()) or \
                any(not isinstance(checkpoint.get(key), str) for key in ('phase', 'next_action', 'handoff')) or \
                ((owner is None) != (token is None)) or \
                (owner is not None and (not isinstance(owner, str) or not owner.strip() or
                                       not isinstance(token, str) or not token)):
            raise RunError('invalid run checkpoint')
        return {'manifest': manifest, 'checkpoint': checkpoint,
                'handoff': checkpoint['handoff'], 'paths': paths}

    def list(self):
        self._safe(self.runs)
        if not os.path.exists(self.runs):
            return []
        summaries = []
        for run_id in sorted(os.listdir(self.runs)):
            if re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_-]{0,79}', run_id) and \
                    os.path.isdir(os.path.join(self.runs, run_id)):
                view = self.inspect(run_id)
                checkpoint = view['checkpoint']
                summaries.append({'run_id': run_id, 'goal': view['manifest']['goal'],
                                  'phase': checkpoint['phase'], 'next_action': checkpoint['next_action'],
                                  'owner': checkpoint['owner'], 'generation': checkpoint['generation']})
        return summaries

    def _save(self, view, checkpoint):
        self._atomic(view['paths']['checkpoint'], checkpoint)
        return self.inspect(view['manifest']['run_id'])

    def resume(self, run_id, owner, expected_generation=None):
        if not isinstance(owner, str) or not owner.strip():
            raise RunError('resume needs a nonempty owner')
        view = self.inspect(run_id)
        checkpoint = view['checkpoint']
        if expected_generation is not None and (type(expected_generation) is not int or
                                                expected_generation != checkpoint['generation']):
            raise RunError('stale generation; inspect the run before taking ownership')
        if checkpoint['owner'] is not None and expected_generation is None:
            raise RunError(f'run is owned by {checkpoint["owner"]!r}; explicit generation required for takeover')
        checkpoint.update(owner=owner.strip(), token=str(uuid.uuid4()),
                          ownership_epoch=checkpoint['ownership_epoch'] + 1,
                          generation=checkpoint['generation'] + 1)
        return self._save(view, checkpoint)

    def require(self, run_id, token):
        view = self.inspect(run_id)
        if not isinstance(token, str) or not token or view['checkpoint']['token'] != token:
            raise RunError('ownership token is missing or stale; resume the run')
        return view

    def release(self, run_id, token, note=''):
        if not isinstance(note, str):
            raise RunError('handoff note must be a string')
        view = self.require(run_id, token)
        checkpoint = view['checkpoint']
        checkpoint.update(owner=None, token=None, handoff=note,
                          generation=checkpoint['generation'] + 1)
        return self._save(view, checkpoint)

    def checkpoint(self, run_id, token, phase, next_action, note='', failure=None):
        if not isinstance(phase, str) or not phase.strip() or \
                not isinstance(next_action, str) or not next_action.strip() or not isinstance(note, str):
            raise RunError('checkpoint needs a phase, next action and string handoff note')
        if failure is not None and (not isinstance(failure, str) or not failure.strip()):
            raise RunError('failure must be a nonempty identifier')
        view = self.require(run_id, token)
        checkpoint = view['checkpoint']
        checkpoint.update(phase=phase, next_action=next_action, handoff=note,
                          generation=checkpoint['generation'] + 1)
        if failure is not None:
            checkpoint['failures'][failure] = checkpoint['failures'].get(failure, 0) + 1
        return self._save(view, checkpoint)
