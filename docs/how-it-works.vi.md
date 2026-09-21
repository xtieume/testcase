# Các skill này làm việc thế nào

[English](how-it-works.md)

Bốn bức hình. Mọi thứ ở đây rút ra từ chính `SKILL.md` của các skill.

## 1. Dây chuyền

`docs-review` nói **cần gì**, `testcase` nói **chứng minh thế nào**, `goalrun` nói **đã đạt
chưa**. Mỗi chặng giao cho chặng sau một bộ id, và mỗi ranh giới có một cổng — hụt thì đỏ, chứ
không im lặng cho qua.

```mermaid
flowchart TD
    SPEC["Spec, tài liệu, ticket"]

    subgraph DR["docs-review — cần gì"]
        DR1["Đối chiếu tài liệu với spec"]
        DR2["REQ-id, nguyên tử, mỗi cái một câu yes/no"]
        DR1 --> DR2
    end

    subgraph TC["testcase — chứng minh thế nào"]
        TC1["Sinh case từ yêu cầu"]
        TC2["Pass 2 tấn công chính output của pass 1"]
        TC3["TC-id truy về REQ-, kèm test thật trong framework của repo"]
        TC1 --> TC2 --> TC3
    end

    subgraph GR["goalrun — đã đạt chưa"]
        GR1["Mỗi REQ- một row trong ledger"]
        GR2["check chạy đúng test của TC đó — không bao giờ là lệnh tìm chữ"]
        GR3["break trồng lỗi mà check phải bắt được"]
        GR1 --> GR2 --> GR3
    end

    GATE{"goalrun --lint-ledger --requirements"}
    OUT["Exit 0 = ledger có đo một cái gì đó"]

    SPEC --> DR1
    DR2 -->|"REQ-id ghi vào reqs.txt"| TC1
    DR2 -->|"REQ-id ghi vào reqs.txt"| GR1
    TC3 -->|"test trở thành check của row"| GR2
    GR3 --> GATE
    GATE -->|"một REQ- không row nào đo"| FAIL1["Exit 1 — thêm row, hoặc waive kèm lý do"]
    GATE -->|"một row không có break"| FAIL2["Exit 1 — thêm break, hoặc waive kèm lý do"]
    GATE -->|"check đi tìm chữ"| FAIL3["Exit 1 — viết test cho khẳng định đó"]
    GATE -->|"phần lớn danh sách bị waive"| FAIL4["Exit 1 — waive cả loạt không phải là gap ai đó đã nhìn"]
    GATE -->|"không dính cái nào"| OUT

    style OUT fill:#d6f5dd,stroke:#2f7d4f,color:#12351f
    style FAIL1 fill:#f8d7da,stroke:#a3303b,color:#3b1015
    style FAIL2 fill:#f8d7da,stroke:#a3303b,color:#3b1015
    style FAIL3 fill:#f8d7da,stroke:#a3303b,color:#3b1015
    style FAIL4 fill:#f8d7da,stroke:#a3303b,color:#3b1015
```

## 2. Khác gì

Cột trái là cái giá của "xong" khi không có gì đo nó.

```mermaid
flowchart TD
    subgraph WITHOUT["Không có goalrun"]
        W1["Xong chưa?"]
        W2["Đọc diff, chạy suite"]
        W3["Văn xuôi: gần xong, còn một lưu ý"]
        W4["Không ai biết nửa nào còn thiếu"]
        W1 --> W2 --> W3 --> W4
    end

    subgraph WITH["Có goalrun"]
        G1["Xong chưa?"]
        G2["Ledger: mỗi yêu cầu một row"]
        G3["Chạy script"]
        G4{"Mọi row PASS?"}
        G5["DONE — exit 0"]
        G6["NOT DONE — bảng, gọi tên từng row đỏ và từng row đang chờ"]
        G1 --> G2 --> G3 --> G4
        G4 -->|"có"| G5
        G4 -->|"không"| G6
    end

    style W3 fill:#f8d7da,stroke:#a3303b,color:#3b1015
    style W4 fill:#f8d7da,stroke:#a3303b,color:#3b1015
    style G5 fill:#d6f5dd,stroke:#2f7d4f,color:#12351f
    style G6 fill:#fff3cd,stroke:#8a6d1f,color:#3b2f08
```

## 3. Một row được quyết thế nào

Một row thuộc về **một câu lệnh** hoặc **một con người**, không bao giờ cả hai. Exit code chính
là câu trả lời. Deliverable đo bằng **nội dung**: `touch` chỉ đổi giờ, không ship gì cả.

```mermaid
flowchart TD
    ROW["Một row trong ledger"]
    KIND{"check có dạng MANUAL:owner?"}

    SIG{"Đã ký trong signoff.tsv?"}
    HASH{"Chữ ký khớp với câu chữ hiện tại?"}
    WAIT["WAIT — đang chờ người chủ row đó"]

    RUN["Chạy check"]
    RAN{"Nó có chạy test nào không?"}
    CODE{"Exit 0?"}
    DELIV{"Row có khai deliverable?"}
    EXISTS{"Đường dẫn có tồn tại?"}
    SHIPPED{"Nội dung khác baseline.json?"}

    PASS["PASS"]
    FAIL["FAIL"]

    ROW --> KIND
    KIND -->|"có"| SIG
    SIG -->|"chưa"| WAIT
    SIG -->|"rồi"| HASH
    HASH -->|"không, câu chữ đã đổi"| WAIT
    HASH -->|"khớp"| PASS

    KIND -->|"không"| RUN
    RUN --> RAN
    RAN -->|"không — filter khớp 0 test, hoặc mọi test đều bị skip"| FAIL
    RAN -->|"có"| CODE
    CODE -->|"khác 0, hoặc quá giờ"| FAIL
    CODE -->|"đúng"| DELIV
    DELIV -->|"không"| PASS
    DELIV -->|"có"| EXISTS
    EXISTS -->|"không"| FAIL
    EXISTS -->|"có"| SHIPPED
    SHIPPED -->|"không"| FAIL
    SHIPPED -->|"có"| PASS

    style PASS fill:#d6f5dd,stroke:#2f7d4f,color:#12351f
    style FAIL fill:#f8d7da,stroke:#a3303b,color:#3b1015
    style WAIT fill:#fff3cd,stroke:#8a6d1f,color:#3b2f08
```

## 4. Chứng minh chính những cái check

Một row xanh chưa chứng minh được gì cho tới khi check của nó được cho thấy là **có thể đỏ**.
`--verify` **nhân bản cây**, trồng `break` vào bản sao, và bắt check phải fail ở đó — file của
bạn chỉ bị đọc, không bị ghi. Sau đó sweep hỏi xem có row nào khác cũng đỏ vì đúng lỗi đó
không — nếu có thì cả hai đều không phân biệt nổi lỗi này với lỗi của chính mình.

```mermaid
flowchart TD
    V["goalrun --verify"]
    LOCK{"Có goalrun khác đang chạy check trên cây này?"}
    STOPL["Exit 2 — check tranh build với thứ khác thì đỏ vì lý do không phải của code"]

    PRE["Pre-pass: chạy mọi check trên cây"]
    RED{"Row đã đỏ sẵn?"}
    AR["ALREADY RED — đỏ thêm lần nữa chẳng chứng minh gì, và nó bị loại khỏi sweep"]

    CLONE["Nhân bản cây ra một chỗ khác"]
    PLANT["Trồng break của row vào BẢN SAO"]
    MOVED{"Trong bản sao có gì đổi không?"}
    BF["BREAK FAILED — break không phá được gì, nên check chưa từng bị thử"]

    CHECK["Chạy check TRONG bản sao"]
    RESULT{"Nó làm gì?"}
    HOLLOW["HOLLOW — vẫn xanh, tức mọi input nó thử đều là input mà lỗi này vô hình"]
    STUCK["STUCK — nó treo, không chứng minh được gì"]
    VERIFIED["VERIFIED — nó đỏ, đúng như phải thế"]
    DROP["Xoá bản sao"]

    SWEEP["Sweep: chạy mọi row khác dưới cùng cái break này"]
    SIB{"Row nào đỏ theo?"}
    SHARED["shared — anh em cùng ship một file, bình thường"]
    BLAST["BLAST — row ship thứ khác cũng đỏ, nên cả hai đều không chứng minh được điều mình khai"]
    BUDGET["SWEEP STOPPED — hết ngân sách thời gian, mấy row đó chưa được chứng minh"]

    V --> LOCK
    LOCK -->|"có"| STOPL
    LOCK -->|"không"| PRE
    PRE --> RED
    RED -->|"đỏ sẵn"| AR
    RED -->|"không"| CLONE
    CLONE --> PLANT
    PLANT --> MOVED
    MOVED -->|"không"| BF
    MOVED -->|"có"| CHECK
    CHECK --> RESULT
    RESULT -->|"vẫn xanh"| HOLLOW
    RESULT -->|"treo"| STUCK
    RESULT -->|"đỏ"| VERIFIED
    VERIFIED --> SWEEP
    SWEEP --> SIB
    SIB -->|"cùng deliverable"| SHARED
    SIB -->|"khác deliverable"| BLAST
    SWEEP -->|"hết giờ sweep"| BUDGET
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

Mỗi ô ở trên là một chuỗi mà script **thật sự in ra**. `HOLLOW`, `STUCK`, `BLAST`,
`ALREADY RED`, `BREAK FAILED`, `NOTHING VERIFIED` và `SWEEP STOPPED` đều exit 1: một lần chạy
không chứng minh được gì thì không phải là pass.

`HOLLOW` là cái duy nhất không nói về row. Nó nói check không phân biệt được hành vi đúng với
khiếm khuyết — mọi input nó thử đều là input mà lỗi này vô hình. Đường về là **ngược lên
`testcase`**, nơi cột `Distinguishes from` gọi tên implementation sai mà mỗi case loại trừ —
chứ không phải đi xuôi vào ledger để sửa row.
