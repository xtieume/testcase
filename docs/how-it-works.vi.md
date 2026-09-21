# Các skill này làm việc thế nào

[English](how-it-works.md)

Bốn hình. Mọi thứ ở đây lấy từ chính `SKILL.md` của các skill.

## 1. Chuỗi ba skill

`docs-review` nói **cần gì**, `testcase` nói **chứng minh thế nào**, `goalrun` nói **đã đạt
chưa**. Mỗi chặng bàn giao cho chặng sau một tập id, và mỗi biên có một cổng chặn — nó fail
chứ không im lặng cho qua.

```mermaid
flowchart TD
    SPEC["Spec, tài liệu, ticket"]

    subgraph DR["docs-review — cần gì"]
        DR1["Đối chiếu tài liệu với spec"]
        DR2["REQ-ids, nguyên tử, mỗi cái một câu hỏi có/không"]
        DR1 --> DR2
    end

    subgraph TC["testcase — chứng minh thế nào"]
        TC1["Sinh case từ requirement"]
        TC2["Lượt hai tấn công chính output của nó"]
        TC3["TC-ids truy vết về REQ-, kèm test chạy được"]
        TC1 --> TC2 --> TC3
    end

    subgraph GR["goalrun — đã đạt chưa"]
        GR1["Mỗi REQ- một row trong ledger"]
        GR2["check chạy đúng những test đó"]
        GR3["break trồng đúng lỗi mà check phải bắt"]
        GR1 --> GR2 --> GR3
    end

    GATE{"goalrun --lint-ledger --requirements"}
    OUT["Exit 0 = ledger có đo một cái gì đó"]

    SPEC --> DR1
    DR2 -->|"REQ-ids ghi vào reqs.txt"| TC1
    DR2 -->|"REQ-ids ghi vào reqs.txt"| GR1
    TC3 -->|"test trở thành check của row"| GR2
    GR3 --> GATE
    GATE -->|"một REQ- không row nào đo"| FAIL1["Exit 1 — thêm row, hoặc waive kèm lý do"]
    GATE -->|"một row không có break"| FAIL2["Exit 1 — thêm break, hoặc waive kèm lý do"]
    GATE -->|"break nhắm vào path git không khôi phục được"| FAIL3["Exit 1 — trỏ nó vào file git track"]
    GATE -->|"phần lớn danh sách bị waive"| FAIL4["Exit 1 — waive cả loạt không phải là gap ai đó đã nhìn"]
    GATE -->|"không dính cái nào"| OUT

    style OUT fill:#d6f5dd,stroke:#2f7d4f,color:#12351f
    style FAIL1 fill:#f8d7da,stroke:#a3303b,color:#3b1015
    style FAIL2 fill:#f8d7da,stroke:#a3303b,color:#3b1015
    style FAIL3 fill:#f8d7da,stroke:#a3303b,color:#3b1015
    style FAIL4 fill:#f8d7da,stroke:#a3303b,color:#3b1015
```

## 2. Khác biệt nằm ở đâu

Cột trái là cái giá của chữ "xong" khi không có gì đo nó.

```mermaid
flowchart TD
    subgraph WITHOUT["Không có goalrun"]
        W1["Xong chưa?"]
        W2["Đọc diff, chạy test suite"]
        W3["Văn xuôi: gần xong rồi, có một caveat"]
        W4["Không ai biết nửa nào còn thiếu"]
        W1 --> W2 --> W3 --> W4
    end

    subgraph WITH["Có goalrun"]
        G1["Xong chưa?"]
        G2["Ledger: mỗi requirement một row"]
        G3["Chạy script"]
        G4{"Mọi row đều PASS?"}
        G5["DONE — exit 0"]
        G6["NOT DONE — bảng, gọi tên từng row đỏ và từng row đang chờ"]
        G1 --> G2 --> G3 --> G4
        G4 -->|"đúng"| G5
        G4 -->|"không"| G6
    end

    style W3 fill:#f8d7da,stroke:#a3303b,color:#3b1015
    style W4 fill:#f8d7da,stroke:#a3303b,color:#3b1015
    style G5 fill:#d6f5dd,stroke:#2f7d4f,color:#12351f
    style G6 fill:#fff3cd,stroke:#8a6d1f,color:#3b2f08
```

## 3. Một row được quyết thế nào

Một row thuộc về **một câu lệnh** hoặc **một con người**, không bao giờ cả hai. Exit code
chính là câu trả lời. Deliverable được git track thì git đo; cái git ignore không có lịch sử
để đọc nên phải đo bằng chuẩn yếu hơn là mtime — đó là lý do luật là hãy track cái artifact.

```mermaid
flowchart TD
    ROW["Một row trong ledger"]
    KIND{"check có dạng MANUAL:owner?"}

    SIG{"Đã ký trong signoff.tsv?"}
    HASH{"Chữ ký khớp với câu chữ hiện tại?"}
    WAIT["WAIT — đang chờ người chủ row đó"]

    RUN["Chạy check"]
    CODE{"Exit 0?"}
    DELIV{"Row có khai deliverable?"}
    EXISTS{"Đường dẫn có tồn tại?"}
    TRACKED{"Git có track nó không?"}
    SHIPPED{"Đã đổi kể từ commit baseline?"}
    MTIME{"Được ghi sau lúc chạy --baseline?"}

    PASS["PASS"]
    FAIL["FAIL"]

    ROW --> KIND
    KIND -->|"có"| SIG
    SIG -->|"chưa"| WAIT
    SIG -->|"rồi"| HASH
    HASH -->|"không, câu chữ đã đổi"| WAIT
    HASH -->|"khớp"| PASS

    KIND -->|"không"| RUN
    RUN --> CODE
    CODE -->|"khác 0, hoặc quá giờ"| FAIL
    CODE -->|"đúng"| DELIV
    DELIV -->|"không"| PASS
    DELIV -->|"có"| EXISTS
    EXISTS -->|"không"| FAIL
    EXISTS -->|"có"| TRACKED
    TRACKED -->|"có"| SHIPPED
    TRACKED -->|"không, git ignore nó"| MTIME
    SHIPPED -->|"không"| FAIL
    SHIPPED -->|"có"| PASS
    MTIME -->|"không"| FAIL
    MTIME -->|"có"| PASS

    style PASS fill:#d6f5dd,stroke:#2f7d4f,color:#12351f
    style FAIL fill:#f8d7da,stroke:#a3303b,color:#3b1015
    style WAIT fill:#fff3cd,stroke:#8a6d1f,color:#3b2f08
```

## 4. Chứng minh chính những cái check

Một row xanh chưa chứng minh được gì cho tới khi check của nó được cho thấy là **có thể đỏ**.
`--verify` trồng `break` của từng row và bắt check phải fail; sau đó sweep hỏi xem có row nào
khác cũng đỏ vì đúng lỗi đó không — nếu có thì cả hai đều không phân biệt nổi lỗi này với lỗi
của chính mình.

```mermaid
flowchart TD
    V["goalrun --verify"]
    LOCK{"Có goalrun khác đang chạy check trên cây này?"}
    STOPL["Exit 2 — check tranh build với thứ khác thì đỏ vì lý do không phải của code"]
    CLEAN{"Working tree sạch?"}
    STOP2["Exit 2 — commit hoặc stash trước đã"]

    PRE["Pre-pass: chạy mọi check trên cây sạch"]
    RED{"Row đã đỏ sẵn?"}
    AR["ALREADY RED — đỏ thêm lần nữa chẳng chứng minh gì, và nó bị loại khỏi sweep"]

    SAFE{"Break có nhắm vào path git không khôi phục được?"}
    UNRES1["UNRESTORABLE — không trồng gì cả; git không giữ nội dung lẫn sự tồn tại của file bị ignore"]
    PLANT["Trồng break của row"]
    BROKE{"Bản thân lệnh break có chạy được không?"}
    BF["BREAK FAILED"]

    CHECK["Chạy check dưới cái break đó"]
    RESTORE["Khôi phục: git checkout và clean, rồi tới snapshot cho phần git với không tới"]
    MOVED{"Break có đụng vào thứ git không khôi phục được?"}
    UNRES2["UNRESTORABLE — đã đặt lại từ snapshot, nhưng row vẫn là chưa chứng minh"]
    RESULT{"Nó làm gì?"}
    HOLLOW["HOLLOW — vẫn xanh, tức là nó chẳng test cái gì"]
    STUCK["STUCK — nó treo, không nói lên điều gì cả"]
    VERIFIED["VERIFIED — nó đỏ, đúng như phải thế"]

    SWEEP["Sweep: chạy mọi row khác dưới cùng cái break này"]
    SIB{"Những row nào đỏ theo?"}
    SHARED["shared — row anh em cùng ship một file, chuyện bình thường"]
    BLAST["BLAST — row ship thứ khác, nên cả hai đều không chứng minh được điều nó khai"]
    BUDGET["SWEEP STOPPED — hết budget, những row đó chưa được chứng minh"]

    V --> LOCK
    LOCK -->|"có"| STOPL
    LOCK -->|"không"| CLEAN
    CLEAN -->|"không"| STOP2
    CLEAN -->|"sạch"| PRE
    PRE --> RED
    RED -->|"đỏ sẵn"| AR
    RED -->|"không"| SAFE
    SAFE -->|"có"| UNRES1
    SAFE -->|"không"| PLANT
    PLANT --> BROKE
    BROKE -->|"không"| BF
    BROKE -->|"được"| CHECK
    CHECK --> RESTORE
    RESTORE --> MOVED
    MOVED -->|"có"| UNRES2
    MOVED -->|"không"| RESULT
    RESULT -->|"vẫn xanh"| HOLLOW
    RESULT -->|"treo"| STUCK
    RESULT -->|"đỏ"| VERIFIED
    VERIFIED --> SWEEP
    SWEEP --> SIB
    SIB -->|"cùng deliverable"| SHARED
    SIB -->|"khác deliverable"| BLAST
    SWEEP -->|"hết thời gian sweep"| BUDGET

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

Mỗi ô ở trên là một chuỗi mà script **thật sự in ra**. `HOLLOW`, `STUCK`, `BLAST`,
`ALREADY RED`, `UNRESTORABLE`, `NOTHING VERIFIED` và `SWEEP STOPPED` đều exit 1: một lần chạy
không chứng minh được gì thì không phải là pass.

`UNRESTORABLE` là cái duy nhất không nói về check. `--verify` khôi phục bằng `git checkout` và
`git clean`, mà hai lệnh đó không với tới nội dung lẫn sự tồn tại của file git ignore — nên một
break xoá report bị ignore là mất hẳn, còn break sửa một check script dưới `.testcases/` thì để
row đo ít hơn những gì ledger nói, kéo dài qua hết cả lần chạy. Break nào **gọi tên** một path
như vậy bị từ chối trước khi trồng bất cứ thứ gì; thứ break với tới gián tiếp thì được đặt lại
từ snapshot chụp trước đó, và row vẫn là chưa chứng minh cho tới khi break trỏ vào file git
khôi phục được.
