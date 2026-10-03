<p align="center">
  <a href="README.md"><img alt="English" src="https://img.shields.io/badge/EN-English-blue?style=flat-square"></a>
  <a href="README.vi.md"><img alt="Tiếng Việt" src="https://img.shields.io/badge/VI-Tiếng_Việt-cc6699?style=flat-square"></a>
</p>

<h1 align="center">testcase</h1>

<p align="center"><strong>Agent báo xong? Bắt nó chứng minh.</strong></p>

<p align="center">
  <a href=".claude-plugin/plugin.json"><img alt="Version" src="https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fraw.githubusercontent.com%2Fxtieume%2Ftestcase%2Fmain%2F.claude-plugin%2Fplugin.json&query=%24.version&label=version&color=6c63ff&style=flat-square"></a>
  <img alt="Claude Code" src="https://img.shields.io/badge/Claude_Code-ready-d97757?style=flat-square">
  <img alt="Codex" src="https://img.shields.io/badge/Codex-ready-412991?style=flat-square">
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

<p align="center">
  <a href="docs/how-it-works.vi.md#1-dây-chuyền"><img alt="Dây chuyền" src="https://img.shields.io/badge/1-Dây_chuyền-8957e5?style=flat-square"></a>
  <a href="docs/how-it-works.vi.md#2-khác-gì"><img alt="Khác gì" src="https://img.shields.io/badge/2-Khác_gì-1f6feb?style=flat-square"></a>
  <a href="docs/how-it-works.vi.md#3-một-row-được-quyết-thế-nào"><img alt="Một row được quyết thế nào" src="https://img.shields.io/badge/3-Một_row_được_quyết_thế_nào-2ea043?style=flat-square"></a>
  <a href="docs/how-it-works.vi.md#4-chứng-minh-chính-những-cái-check"><img alt="Chứng minh các check" src="https://img.shields.io/badge/4-Chứng_minh_các_check-d97757?style=flat-square"></a>
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

Năm sơ đồ về chuỗi đó, và về cách `goalrun` quyết định một row và chứng minh một check: [Các skill này làm việc thế nào](docs/how-it-works.vi.md).

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

## Tiếp tục công việc qua nhiều agent

Run có tên gắn với công việc, giữ baseline, đường dẫn artifact, số lần thất bại và ghi chú
bàn giao khi đổi agent hoặc host trong cùng workspace. Khởi tạo trước khi sửa file:

```bash
GOALRUN=.agents/skills/goalrun/scripts/goalrun.py
python3 "$GOALRUN" init export-v1 --goal "Ship CSV export" --spec spec.md
python3 "$GOALRUN" resume export-v1 --owner agent-a   # lưu token từ JSON vào TOKEN
python3 "$GOALRUN" checkpoint export-v1 --token "$TOKEN" --phase build \
  --next "Implement TC-EXP-004" --note "Tests red; continue from spec.md"
python3 "$GOALRUN" release export-v1 --token "$TOKEN" --note "Continue TC-EXP-004"
python3 "$GOALRUN" inspect export-v1
python3 "$GOALRUN" resume export-v1 --owner agent-b   # nhận token mới
```

Dùng đường dẫn do `inspect` trả về: test case được lưu trong repo tại
`docs/testcases/<id>/testcases.md`, trạng thái làm việc ở `.testcases/runs/<id>/`.
`docs-review` và `testcase` cũng dùng run này khi chạy riêng. Quyền sở hữu không tự hết hạn;
chỉ tiếp quản bằng `--expected-generation` vừa đọc sau khi agent và check trước đã dừng.
Input thay đổi làm bằng chứng cũ hết hiệu lực; báo xong cần `--verify` mới trên toàn ledger.
Xem [run context](.agents/skills/goalrun/references/run-context.md) để biết cách bàn giao,
kiểm tra bằng chứng, giao việc cho subagent, chuyển workspace và migrate trạng thái cũ.

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

**Codex app / CLI** — thêm marketplace của repo rồi cài plugin:

```bash
codex plugin marketplace add xtieume/testcase
codex plugin add testcase@testcase-marketplace
```

Với bản clone local, dùng `codex plugin marketplace add ./testcase`.
Trong app, chọn marketplace `testcase` ở Plugins. Mở phiên mới sau khi cài.
Xem [hướng dẫn Codex](.codex/INSTALL.md) cho CLI cũ, Windows và cập nhật.
Đây là marketplace của repo, tách biệt với thư mục plugin công khai của OpenAI.

**Các host plugin khác** — dùng chung toàn bộ bộ skill:

| Host | Cài đặt | Đóng gói |
| ---- | ------- | -------- |
| Cursor | Thêm URL GitHub vào Settings → Plugins nếu phiên bản hỗ trợ, hoặc dùng native skills bên dưới | `.cursor-plugin/plugin.json` |
| Devin CLI | `devin plugins install xtieume/testcase` | `.devin-plugin/plugin.json` + `skills/` ở root |
| Kimi Code | `/plugins install https://github.com/xtieume/testcase` | `.kimi-plugin/plugin.json` |
| Hermes Agent | `hermes plugins install xtieume/testcase --enable` | `.hermes-plugin/` đăng ký từng skill |
| Muse | Clone repo, rồi `muse plugins install ./testcase` | `.muse-plugin/` liệt kê từng skill |
| Gemini CLI | `gemini extensions install https://github.com/xtieume/testcase` | `gemini-extension.json` + `skills/` ở root |
| Pi | `pi install git:github.com/xtieume/testcase` | `package.json` → `pi.skills` |
| Factory Droid | `droid plugin marketplace add https://github.com/xtieume/testcase`, rồi `droid plugin install testcase@testcase-marketplace` | Marketplace tương thích Claude |
| GitHub Copilot CLI | `copilot plugin marketplace add xtieume/testcase`, rồi `copilot plugin install testcase@testcase-marketplace` | Marketplace tương thích Claude |
| Qwen Code | `qwen extensions install xtieume/testcase` | Marketplace tương thích Claude |

Trước khi các file này được publish, cài từ bản clone local nếu host hỗ trợ.
Mở phiên mới sau khi cài. Workflow yêu cầu subagent độc lập cần host có công cụ
ủy nhiệm; skill thu thập qua browser cần bước setup bên dưới. Cấu trúc đóng gói
tham khảo [các adapter của Superpowers](https://github.com/obra/superpowers).

**Cursor / Antigravity / OpenCode — native skills** — clone vào nơi cố định,
rồi liên kết từng skill vào project cần dùng:

```bash
git clone https://github.com/xtieume/testcase.git /absolute/path/to/testcase
mkdir -p .agents/skills
for skill in /absolute/path/to/testcase/.agents/skills/*; do
  ln -s "$skill" .agents/skills/
done
```

`ln -s` giữ entry đã có và báo lỗi nếu trùng tên. Để cài toàn cục, tạo thư mục của
host bên dưới rồi liên kết hoặc copy từng skill vào đó:

| Host | Thư mục skill toàn cục |
| ---- | --------------------- |
| Codex | `~/.agents/skills/` |
| Cursor | `~/.cursor/skills/` |
| Antigravity | `~/.gemini/antigravity/skills/` |
| OpenCode | `~/.config/opencode/skills/` |
| Claude Code | `~/.claude/skills/` |

Xem [hướng dẫn OpenCode](.opencode/INSTALL.md) để có lệnh đầy đủ. Trên Windows,
copy folder thay cho symlink. Mỗi host chọn một cách cài, tránh nạp trùng bộ skill
qua cả plugin lẫn native skills.

**Chỉ một skill** — copy `.agents/skills/<name>/` vào thư mục tương ứng.
Khi dùng `docs-review/` hoặc `testcase/`, copy thêm `goalrun/` để giữ trạng thái run.
Skill kích hoạt bằng ngôn ngữ tự nhiên. Cách gọi trực tiếp tùy host:
`$testcase` trên Codex, `/<name>` nếu hỗ trợ, hoặc công cụ `skill` trên OpenCode.

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

Bỏ một folder vào `.agents/skills/<name>/` gồm `SKILL.md` (frontmatter `name` + `description`), kèm `references/` và `scripts/` nếu cần. Host đọc thư mục sẽ tự nhận skill. Muse cần danh sách tường minh: chạy `python3 scripts/sync_plugins.py` sau khi thêm hoặc xóa skill; CI kiểm tra sai lệch. Thêm một dòng vào bảng bên trên. Version không sửa tay: merge vào `main` sẽ tự đồng bộ version cho mọi manifest plugin, marketplace, Gemini, Pi và Hermes, tạo tag và publish release — commit `feat:` bump minor, có `!` hoặc `BREAKING CHANGE` bump major, còn lại bump patch.

## Cấu trúc

```
.agents/skills/<name>/     SKILL.md + references/ + scripts/
.claude-plugin/            manifest cho Claude Code
.zcode-plugin/             manifest cho ZCode
.codex-plugin/             metadata plugin Codex
.agents/plugins/           marketplace repo cho Codex
.cursor-plugin/            metadata plugin Cursor
.devin-plugin/             metadata plugin Devin
.kimi-plugin/              metadata plugin Kimi
.hermes-plugin/            manifest Hermes + đăng ký native skills
.muse-plugin/              manifest Muse + marketplace
.codex/INSTALL.md          hướng dẫn cài Codex
.opencode/INSTALL.md       hướng dẫn native skills OpenCode
skills -> .agents/skills   bộ skill chung cho host đọc skills ở root
gemini-extension.json      metadata extension Gemini CLI
package.json               metadata package Pi
scripts/sync_plugins.py    version release + danh sách skill Muse
```

## License

MIT
