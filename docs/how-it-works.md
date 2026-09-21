# How these skills work

[Tiếng Việt](how-it-works.vi.md)

Four pictures. Everything here is drawn from the skills' own `SKILL.md` files.

## 1. The pipeline

`docs-review` says what is required, `testcase` says how it is proven, `goalrun` says whether
it holds. Each stage hands the next a set of ids, and each boundary has a gate that fails
rather than passing in silence.

```mermaid
flowchart TD
    SPEC["Spec, docs, ticket"]

    subgraph DR["docs-review — what is required"]
        DR1["Audit docs against the spec"]
        DR2["REQ-ids, atomic, one yes/no each"]
        DR1 --> DR2
    end

    subgraph TC["testcase — how it is proven"]
        TC1["Cases from the requirement"]
        TC2["Second pass attacks its own output"]
        TC3["TC-ids traced to a REQ-, plus runnable tests"]
        TC1 --> TC2 --> TC3
    end

    subgraph GR["goalrun — whether it holds"]
        GR1["One ledger row per REQ-"]
        GR2["check runs those tests"]
        GR3["break plants the defect the check must catch"]
        GR1 --> GR2 --> GR3
    end

    GATE{"goalrun --lint-ledger --requirements"}
    OUT["Exit 0 = the ledger measures something"]

    SPEC --> DR1
    DR2 -->|"REQ-ids to reqs.txt"| TC1
    DR2 -->|"REQ-ids to reqs.txt"| GR1
    TC3 -->|"tests become the row's check"| GR2
    GR3 --> GATE
    GATE -->|"a REQ- no row measures"| FAIL1["Exit 1 — add a row, or waive it with a reason"]
    GATE -->|"a row with no break"| FAIL2["Exit 1 — add a break, or waive it with a reason"]
    GATE -->|"a break on a path git cannot restore"| FAIL3["Exit 1 — point it at a tracked file"]
    GATE -->|"most of the list waived"| FAIL4["Exit 1 — a bulk pass is not a gap someone looked at"]
    GATE -->|"none of those"| OUT

    style OUT fill:#d6f5dd,stroke:#2f7d4f,color:#12351f
    style FAIL1 fill:#f8d7da,stroke:#a3303b,color:#3b1015
    style FAIL2 fill:#f8d7da,stroke:#a3303b,color:#3b1015
    style FAIL3 fill:#f8d7da,stroke:#a3303b,color:#3b1015
    style FAIL4 fill:#f8d7da,stroke:#a3303b,color:#3b1015
```

## 2. What changes

The left column is what "done" costs when nothing measures it.

```mermaid
flowchart TD
    subgraph WITHOUT["Without goalrun"]
        W1["Is it done?"]
        W2["Read the diff, run the suite"]
        W3["Prose: mostly done, one caveat"]
        W4["Nobody can tell which half is missing"]
        W1 --> W2 --> W3 --> W4
    end

    subgraph WITH["With goalrun"]
        G1["Is it done?"]
        G2["Ledger: one row per requirement"]
        G3["Run the script"]
        G4{"Every row PASS?"}
        G5["DONE — exit 0"]
        G6["NOT DONE — the table, naming every red and waiting row"]
        G1 --> G2 --> G3 --> G4
        G4 -->|"yes"| G5
        G4 -->|"no"| G6
    end

    style W3 fill:#f8d7da,stroke:#a3303b,color:#3b1015
    style W4 fill:#f8d7da,stroke:#a3303b,color:#3b1015
    style G5 fill:#d6f5dd,stroke:#2f7d4f,color:#12351f
    style G6 fill:#fff3cd,stroke:#8a6d1f,color:#3b2f08
```

## 3. How one row is decided

A row belongs to a command or to a person, never both. The exit code is the answer. A
deliverable git tracks is measured by git; one it ignores has no history to read, so it is
measured by the weaker standard of mtime — which is why the rule is to track the artifact.

```mermaid
flowchart TD
    ROW["One ledger row"]
    KIND{"check is MANUAL:owner?"}

    SIG{"Signed in signoff.tsv?"}
    HASH{"Signature matches the current wording?"}
    WAIT["WAIT — awaiting that owner"]

    RUN["Run the check"]
    CODE{"Exit 0?"}
    DELIV{"Row names a deliverable?"}
    EXISTS{"Path exists?"}
    TRACKED{"Does git track it?"}
    SHIPPED{"Changed since the baseline commit?"}
    MTIME{"Written since --baseline ran?"}

    PASS["PASS"]
    FAIL["FAIL"]

    ROW --> KIND
    KIND -->|"yes"| SIG
    SIG -->|"no"| WAIT
    SIG -->|"yes"| HASH
    HASH -->|"no, wording changed"| WAIT
    HASH -->|"yes"| PASS

    KIND -->|"no"| RUN
    RUN --> CODE
    CODE -->|"non-zero, or timed out"| FAIL
    CODE -->|"yes"| DELIV
    DELIV -->|"no"| PASS
    DELIV -->|"yes"| EXISTS
    EXISTS -->|"no"| FAIL
    EXISTS -->|"yes"| TRACKED
    TRACKED -->|"yes"| SHIPPED
    TRACKED -->|"no, git ignores it"| MTIME
    SHIPPED -->|"no"| FAIL
    SHIPPED -->|"yes"| PASS
    MTIME -->|"no"| FAIL
    MTIME -->|"yes"| PASS

    style PASS fill:#d6f5dd,stroke:#2f7d4f,color:#12351f
    style FAIL fill:#f8d7da,stroke:#a3303b,color:#3b1015
    style WAIT fill:#fff3cd,stroke:#8a6d1f,color:#3b2f08
```

## 4. Proving the checks themselves

A green row proves nothing until its check has been shown able to go red. `--verify` plants
each row's `break` and demands the check fail; the sweep then asks whether any other row
failed for the same defect, which would mean neither can tell one defect from another.

```mermaid
flowchart TD
    V["goalrun --verify"]
    LOCK{"Another goalrun running checks in this tree?"}
    STOPL["Exit 2 — a check racing another build goes red for reasons that are not the code"]
    CLEAN{"Working tree clean?"}
    STOP2["Exit 2 — commit or stash first"]

    PRE["Pre-pass: run every check on the clean tree"]
    RED{"Row already red?"}
    AR["ALREADY RED — it proves nothing by going red again, and stays out of the sweep"]

    SAFE{"Does the break name a path git cannot restore?"}
    UNRES1["UNRESTORABLE — nothing planted; git restores neither an ignored file's content nor its existence"]
    PLANT["Plant the row's break"]
    BROKE{"Break command itself succeeded?"}
    BF["BREAK FAILED"]

    CHECK["Run the check under the break"]
    RESTORE["Restore: git checkout and clean, then the snapshot for what git cannot reach"]
    MOVED{"Did the break move something git cannot restore?"}
    UNRES2["UNRESTORABLE — put back from the snapshot, and the row is unproven either way"]
    RESULT{"What did the check do?"}
    HOLLOW["HOLLOW — it passed, so it tests nothing"]
    STUCK["STUCK — it hung, which proves nothing either way"]
    VERIFIED["VERIFIED — it went red, as it must"]

    SWEEP["Sweep: run every other row under this same break"]
    SIB{"Which rows went red?"}
    SHARED["shared — siblings shipping the same file, expected"]
    BLAST["BLAST — a row shipping something else, so neither row proves what it claims"]
    BUDGET["SWEEP STOPPED — the budget ran out, those rows are unproven"]

    V --> LOCK
    LOCK -->|"yes"| STOPL
    LOCK -->|"no"| CLEAN
    CLEAN -->|"no"| STOP2
    CLEAN -->|"yes"| PRE
    PRE --> RED
    RED -->|"yes"| AR
    RED -->|"no"| SAFE
    SAFE -->|"yes"| UNRES1
    SAFE -->|"no"| PLANT
    PLANT --> BROKE
    BROKE -->|"no"| BF
    BROKE -->|"yes"| CHECK
    CHECK --> RESTORE
    RESTORE --> MOVED
    MOVED -->|"yes"| UNRES2
    MOVED -->|"no"| RESULT
    RESULT -->|"passed"| HOLLOW
    RESULT -->|"hung"| STUCK
    RESULT -->|"failed"| VERIFIED
    VERIFIED --> SWEEP
    SWEEP --> SIB
    SIB -->|"same deliverable"| SHARED
    SIB -->|"different deliverable"| BLAST
    SWEEP -->|"out of sweeping time"| BUDGET

    style VERIFIED fill:#d6f5dd,stroke:#2f7d4f,color:#12351f
    style SHARED fill:#d6f5dd,stroke:#2f7d4f,color:#12351f
    style HOLLOW fill:#f8d7da,stroke:#a3303b,color:#3b1015
    style STUCK fill:#f8d7da,stroke:#a3303b,color:#3b1015
    style BLAST fill:#f8d7da,stroke:#a3303b,color:#3b1015
    style BF fill:#f8d7da,stroke:#a3303b,color:#3b1015
    style AR fill:#f8d7da,stroke:#a3303b,color:#3b1015
    style STOP2 fill:#f8d7da,stroke:#a3303b,color:#3b1015
    style STOPL fill:#f8d7da,stroke:#a3303b,color:#3b1015
    style UNRES1 fill:#f8d7da,stroke:#a3303b,color:#3b1015
    style UNRES2 fill:#f8d7da,stroke:#a3303b,color:#3b1015
    style BUDGET fill:#fff3cd,stroke:#8a6d1f,color:#3b2f08
```

Every box above is a string the script actually prints. `HOLLOW`, `STUCK`, `BLAST`,
`ALREADY RED`, `UNRESTORABLE`, `NOTHING VERIFIED` and `SWEEP STOPPED` all exit 1: a run that
proved nothing is not a pass.

`UNRESTORABLE` is the one that is not about the check at all. `--verify` restores with `git
checkout` and `git clean`, which reach neither the content nor the existence of a file git
ignores — so a break that deletes an ignored report destroys it, and one that rewrites a check
script under `.testcases/` leaves the row measuring less than the ledger says, past the end of
the run. A break naming such a path is refused before anything is planted; what a break reaches
indirectly is put back from a snapshot taken beforehand, and the row stays unproven until the
break points at a file git can restore.
