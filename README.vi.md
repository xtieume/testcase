<p align="center">
  <a href="README.md"><img alt="English" src="https://img.shields.io/badge/EN-English-blue?style=flat-square"></a>
  <a href="README.vi.md"><img alt="Tiếng Việt" src="https://img.shields.io/badge/VI-Tiếng_Việt-cc6699?style=flat-square"></a>
</p>

<h1 align="center">testcase</h1>

<p align="center"><strong>Agent báo xong? Bắt nó chứng minh.</strong></p>

<p align="center">
  <a href=".claude-plugin/plugin.json"><img alt="Version" src="https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fraw.githubusercontent.com%2Fxtieume%2Ftestcase%2Fmain%2F.claude-plugin%2Fplugin.json&query=%24.version&label=version&color=6c63ff&style=flat-square"></a>
  <img alt="Claude Code" src="https://img.shields.io/badge/Claude_Code-ready-d97757?style=flat-square">
  <img alt="ZCode" src="https://img.shields.io/badge/ZCode-ready-informational?style=flat-square">
  <img alt="Cursor" src="https://img.shields.io/badge/Cursor-ready-black?style=flat-square">
  <img alt="Antigravity" src="https://img.shields.io/badge/Antigravity-ready-4285F4?style=flat-square">
  <a href="LICENSE"><img alt="License" src="https://img.shields.io/github/license/xtieume/testcase?color=green&style=flat-square"></a>
  <a href="https://github.com/xtieume/testcase/stargazers"><img alt="Stars" src="https://img.shields.io/github/stars/xtieume/testcase?color=f5a623&style=flat-square"></a>
</p>

<p align="center">
  <a href="#bắt-đầu"><img alt="Bắt đầu" src="https://img.shields.io/badge/Bắt_đầu-2EA043?style=for-the-badge"></a>
  <a href="docs/how-it-works.vi.md"><img alt="Cách hoạt động" src="https://img.shields.io/badge/Cách_hoạt_động-1F6FEB?style=for-the-badge&logo=mermaid&logoColor=white"></a>
  <a href="../../releases"><img alt="Các bản phát hành" src="https://img.shields.io/badge/Bản_phát_hành-6E7681?style=for-the-badge&logo=github&logoColor=white"></a>
</p>

testcase là bộ skill cho agent, đưa một requirement đi trọn đường tới code ship được: chốt spec yêu cầu gì, biến nó thành test thật, rồi build tới khi mọi check đều pass. Bước nào cũng để lại bằng chứng chạy lại được.

## Xong phải là xong thật

Bạn nhờ AI agent build một tính năng. Nó báo xong. Bạn kiểm tra — thiếu một requirement, một test chưa từng được viết, cái edge case nằm ở comment thứ ba của ticket bị bỏ qua. Bạn hỏi lại. Nó tìm ra thêm. Lặp lại.

testcase cắt đứt vòng lặp đó.

**Requirement nào cũng được đếm.** Mỗi cái có id, một câu hỏi có/không, và dòng gốc nó được lấy ra. Không requirement nào lặng lẽ biến mất.

**Có test rồi mới tin.** Requirement thành test case, test case thành test thật bằng framework của chính repo — không phải checklist nằm trong khung chat.

**Xong nghĩa là exit 0.** `goalrun` build từng phase và không báo xong khi script chưa pass trên toàn bộ ledger. Không "xong, còn chờ X". Không "tôi đã kiểm tay rồi".

## Từ ticket tới ship

Chuỗi lõi, mỗi chặng một lần bàn giao. Dùng riêng từng chặng, hoặc ghép lại và giao trọn công việc:

| Bước | Skill | Bạn nhận được |
| ---- | ----- | ------------- |
| 1. Yêu cầu | `docs-review` | Các id `REQ-` nguyên tử, mỗi cái là một câu có/không, kèm trích dẫn dòng gốc |
| 2. Chứng minh | `testcase` | Các id `TC-` truy về một `REQ-`, implement thành test bằng framework của chính repo |
| 3. Build | `goalrun` | Phần implement, từng phase, tới khi ledger các check exit 0 |

Bốn sơ đồ về chuỗi đó, và về cách `goalrun` quyết định một row và chứng minh một check: [Các skill này làm việc thế nào](docs/how-it-works.vi.md).

## Bắt đầu

1. Cài plugin (ví dụ Claude Code; [host khác xem bên dưới](#cài-đặt)):
   ```bash
   claude plugin marketplace add xtieume/testcase
   claude plugin install testcase@testcase-marketplace
   ```
2. Đưa nó một spec: *"viết test case cho spec.md"*.
3. Giao phần build: *"/goalrun build tính năng export, chạy tới khi xong"*.

> [!TIP]
> **Trên Claude Code, mở đầu bằng `/goal`.** `/goal` đặt một điều kiện được kiểm sau mỗi lượt, và Claude cứ làm tiếp tới khi điều kiện đạt — nên phiên chạy không dừng giữa chừng để hỏi có làm tiếp không:
> ```
> /goal /goalrun build tính năng export — xong khi goalrun.py exit 0 trên toàn bộ ledger
> ```

> [!TIP]
> **Nghĩ là đã xong rồi?** Hỏi *"cái này xong thật chưa?"* — `goalrun` kiểm lại công việc theo ledger và chỉ ra chỗ nào còn đỏ.

## Cài đặt

**Claude Code** — cài qua marketplace, lấy toàn bộ skill trong repo:

```bash
claude plugin marketplace add xtieume/testcase
claude plugin install testcase@testcase-marketplace
```

**ZCode** — cùng luồng, đọc `.zcode-plugin/`:

```bash
zcode plugin marketplace add xtieume/testcase
zcode plugin install testcase@testcase-marketplace
```

**Cursor / Antigravity** — cả hai đọc trực tiếp `.agents/skills/`. Clone một lần, rồi symlink vào project hoặc copy ra toàn cục:

```bash
git clone https://github.com/xtieume/testcase.git

# mức project (cả hai editor)
ln -s "$(pwd)/testcase/.agents/skills" .agents/skills

# toàn cục
cp -R testcase/.agents/skills/* ~/.cursor/skills/              # Cursor
cp -R testcase/.agents/skills/* ~/.gemini/antigravity/skills/  # Antigravity
```

**Mọi host, chỉ một skill** — copy đúng folder cần:

```bash
cp -R .agents/skills/<name> ~/.claude/skills/<name>
```

Skill kích hoạt bằng ngôn ngữ tự nhiên, hoặc gọi thẳng `/<name>`.

## Danh sách skill

Mỗi tên link tới `SKILL.md` của nó — đó là tài liệu tham chiếu cho skill đó: điều kiện kích hoạt, workflow, flag, script.

### Build

| Skill | Làm gì | Kích hoạt |
| ----- | ------ | --------- |
| 🎯 [`goalrun`](.agents/skills/goalrun/SKILL.md) | Biến một mục tiêu thành ledger các check, giao từng phase cho subagent độc lập build, và không báo xong khi script chưa exit 0. Cũng kiểm tra lại việc người khác đã báo xong | "làm X, chạy tới khi xong", "cái này xong thật chưa?" |
| ✍️ [`normalize`](.agents/skills/normalize/SKILL.md) | Viết lại một prompt đời thường lan man thành prompt kỹ thuật gọn — giữ nguyên yêu cầu, chuyển sang dạng mệnh lệnh, nói rõ khi nào hỏi lại và thế nào là xong | "chuẩn hóa prompt này cho /goalrun" |

### Kiểm chứng

| Skill | Làm gì | Kích hoạt |
| ----- | ------ | --------- |
| 🧪 [`testcase`](.agents/skills/testcase/SKILL.md) | Sinh test case từ requirement hoặc từ design Figma, tự tấn công output của mình để tìm case bị sót, rồi implement các case automatable thành test chạy được và viết bug report cho cái fail | "viết test case cho…" |
| 📋 [`docs-review`](.agents/skills/docs-review/SKILL.md) | Đối chiếu tài liệu với spec: spec yêu cầu gì vs tài liệu thực sự viết gì, mỗi verdict kèm trích dẫn | "review docs theo spec.md" |

### Thu thập

| Skill | Làm gì | Kích hoạt |
| ----- | ------ | --------- |
| 📥 [`playwright-cdp`](.agents/skills/playwright-cdp/SKILL.md) | Trang Notion và thread Slack → markdown qua browser đang đăng nhập: nội dung, toàn bộ comment, và file đính kèm tải về | "đọc trang Notion này", "lấy thread Slack này" |

## Quy ước chung

Quy ước mà mọi skill ở đây tuân theo, để đoán được một skill mới trước khi mở nó ra:

- **`SKILL.md` giữ nhỏ.** Chi tiết nằm trong `references/`, chỉ load khi task cần.
- **Review trước khi trả kết quả.** Skill nào tạo ra deliverable đều kết thúc bằng một vòng subagent độc lập: tự dựng lại công việc và tấn công nó, lặp đến khi một round không thêm được gì.
- **Script chỉ dùng stdlib.** Python hoặc Node, không cần cài gì trừ khi skill nói rõ; script lint output thay vì tin vào nó.
- **Verdict phải có bằng chứng.** Mọi khẳng định về tài liệu hay requirement đều trích dẫn dòng đã lấy ra.

Bước cài thêm, với skill nào cần:

```bash
cd .agents/skills/playwright-cdp/scripts && npm install   # một lần
```

## Thêm skill mới

Bỏ một folder vào `.agents/skills/<name>/` gồm `SKILL.md` (frontmatter `name` + `description`), kèm `references/` và `scripts/` nếu cần. Không phải sửa manifest: cả hai `plugin.json` trỏ vào thư mục chứ không phải danh sách. Thêm một dòng vào bảng bên trên. Version không sửa tay: merge vào `main` sẽ tự bump cả bốn manifest, tạo tag và publish release — commit `feat:` bump minor, có `!` hoặc `BREAKING CHANGE` bump major, còn lại bump patch.

## Cấu trúc

```
.agents/skills/<name>/     SKILL.md + references/ + scripts/
.claude-plugin/            manifest cho Claude Code
.zcode-plugin/             manifest cho ZCode
```

## License

MIT
