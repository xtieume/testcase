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
        TC3["TC-ids traced to a REQ-, plus tests in the repo's own framework"]
        TC1 --> TC2 --> TC3
    end

    subgraph GR["goalrun — whether it holds"]
        GR1["One ledger row per REQ-"]
        GR2["check runs the test implementing that TC — never a search over text"]
        GR3["break plants the defect the check must catch"]
        GR1 --> GR2 --> GR3
    end

    GATE{"goalrun --lint-ledger --requirements"}
    OUT["Exit 0 = the ledger measures something"]

    SPEC --> DR1
    DR2 -->|"REQ-ids to reqs.txt"| TC1
    DR2 -->|"REQ-ids to reqs.txt"| GR1
    TC3 -->|"the test becomes the row's check"| GR2
    GR3 --> GATE
    GATE -->|"a REQ- no row measures"| FAIL1["Exit 1 — add a row, or waive it with a reason"]
    GATE -->|"a row with no break"| FAIL2["Exit 1 — add a break, or waive it with a reason"]
    GATE -->|"a check that searches text"| FAIL3["Exit 1 — give the claim a test"]
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
deliverable is measured by content: `touch` changes a timestamp and ships nothing.

```mermaid
flowchart TD
    ROW["One ledger row"]
    KIND{"check is MANUAL:owner?"}

    SIG{"Signed in signoff.tsv?"}
    HASH{"Signature matches the current wording?"}
    WAIT["WAIT — awaiting that owner"]

    RUN["Run the check"]
    RAN{"Did it run any test?"}
    CODE{"Exit 0?"}
    DELIV{"Row names a deliverable?"}
    EXISTS{"Path exists?"}
    SHIPPED{"Content differs from baseline.json?"}

    PASS["PASS"]
    FAIL["FAIL"]

    ROW --> KIND
    KIND -->|"yes"| SIG
    SIG -->|"no"| WAIT
    SIG -->|"yes"| HASH
    HASH -->|"no, wording changed"| WAIT
    HASH -->|"yes"| PASS

    KIND -->|"no"| RUN
    RUN --> RAN
    RAN -->|"no — filter matched nothing, or every test skipped"| FAIL
    RAN -->|"yes"| CODE
    CODE -->|"non-zero, or timed out"| FAIL
    CODE -->|"yes"| DELIV
    DELIV -->|"no"| PASS
    DELIV -->|"yes"| EXISTS
    EXISTS -->|"no"| FAIL
    EXISTS -->|"yes"| SHIPPED
    SHIPPED -->|"no"| FAIL
    SHIPPED -->|"yes"| PASS

    style PASS fill:#d6f5dd,stroke:#2f7d4f,color:#12351f
    style FAIL fill:#f8d7da,stroke:#a3303b,color:#3b1015
    style WAIT fill:#fff3cd,stroke:#8a6d1f,color:#3b2f08
```

## 4. Proving the checks themselves

A green row proves nothing until its check has been shown able to go red. `--verify` copies the
tree, plants the row's `break` in the copy, and demands the check fail there — your own files
are read, never written. The sweep then asks whether any other row failed for the same defect,
which would mean neither can tell one defect from another.

```mermaid
flowchart TD
    V["goalrun --verify"]
    LOCK{"Another goalrun running checks in this tree?"}
    STOPL["Exit 2 — a check racing another build goes red for reasons that are not the code"]

    PRE["Pre-pass: run every check on the tree"]
    RED{"Row already red?"}
    AR["ALREADY RED — it proves nothing by going red again, and stays out of the sweep"]

    CLONE["Copy the tree aside"]
    PLANT["Plant the row's break in the copy"]
    MOVED{"Did anything in the copy change?"}
    BF["BREAK FAILED — the break fired nothing, so the check was never tested"]

    CHECK["Run the check inside the copy"]
    RESULT{"What did it do?"}
    HOLLOW["HOLLOW — it passed, so every input it tries is one this defect is invisible in"]
    STUCK["STUCK — it hung, which proves nothing either way"]
    VERIFIED["VERIFIED — it went red, as it must"]
    DROP["Delete the copy"]

    SWEEP["Sweep: run every other row under this same break"]
    SIB{"Which rows went red?"}
    SHARED["shared — siblings shipping the same file, expected"]
    BLAST["BLAST — a row shipping something else, so neither row proves what it claims"]
    BUDGET["SWEEP STOPPED — the budget ran out, those rows are unproven"]

    V --> LOCK
    LOCK -->|"yes"| STOPL
    LOCK -->|"no"| PRE
    PRE --> RED
    RED -->|"yes"| AR
    RED -->|"no"| CLONE
    CLONE --> PLANT
    PLANT --> MOVED
    MOVED -->|"no"| BF
    MOVED -->|"yes"| CHECK
    CHECK --> RESULT
    RESULT -->|"passed"| HOLLOW
    RESULT -->|"hung"| STUCK
    RESULT -->|"failed"| VERIFIED
    VERIFIED --> SWEEP
    SWEEP --> SIB
    SIB -->|"same deliverable"| SHARED
    SIB -->|"different deliverable"| BLAST
    SWEEP -->|"out of sweeping time"| BUDGET
    VERIFIED --> DROP
    HOLLOW --> DROP
    BF --> DROP

    style VERIFIED fill:#d6f5dd,stroke:#2f7d4f,color:#12351f
    style SHARED fill:#d6f5dd,stroke:#2f7d4f,color:#12351f
    style HOLLOW fill:#f8d7da,stroke:#a3303b,color:#3b1015
    style STUCK fill:#f8d7da,stroke:#a3303b,color:#3b1015
    style BLAST fill:#f8d7da,stroke:#a3303b,color:#3b1015
    style BF fill:#f8d7da,stroke:#a3303b,color:#3b1015
    style AR fill:#f8d7da,stroke:#a3303b,color:#3b1015
    style STOPL fill:#f8d7da,stroke:#a3303b,color:#3b1015
    style BUDGET fill:#fff3cd,stroke:#8a6d1f,color:#3b2f08
```

Every box above is a string the script actually prints. `HOLLOW`, `STUCK`, `BLAST`,
`ALREADY RED`, `BREAK FAILED`, `NOTHING VERIFIED` and `SWEEP STOPPED` all exit 1: a run that
proved nothing is not a pass.

`HOLLOW` is the one that is not about the row. It says the check cannot tell the correct
behaviour from the defect — every input it tries is an input this defect is invisible in. The
route back is into `testcase`, whose `Distinguishes from` column names the wrong implementation
each case rules out, never forwards into the ledger by re-pointing the row.
