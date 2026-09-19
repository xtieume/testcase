[![Version](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fraw.githubusercontent.com%2Fxtieume%2Ftestcase%2Fmain%2F.claude-plugin%2Fplugin.json&query=%24.version&label=version&color=blue)](.claude-plugin/plugin.json)
[![Skills](https://img.shields.io/badge/skills-4-8957e5)](#danh-sách-skill)
[![Stars](https://img.shields.io/github/stars/xtieume/testcase?style=flat&color=f5a623)](https://github.com/xtieume/testcase/stargazers)
[![Last commit](https://img.shields.io/github/last-commit/xtieume/testcase)](https://github.com/xtieume/testcase/commits/main)
[![License](https://img.shields.io/github/license/xtieume/testcase?color=green)](LICENSE)

Skill cho việc QA và tài liệu — viết test case, đối chiếu tài liệu với spec, tải trang về. Cài một lần, dùng được trong Claude Code, ZCode, Cursor hoặc Antigravity.

[English](README.md)

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

### Hoàn thành công việc

| Skill | Làm gì | Kích hoạt |
| ----- | ------ | --------- |
| 🎯 [`goalrun`](.agents/skills/goalrun/SKILL.md) | Biến một mục tiêu thành ledger các check, giao từng phase cho subagent độc lập, và không báo xong khi script chưa exit 0 | "làm X, chạy tới khi xong" |

Ba skill ghép thành một chuỗi: **`docs-review`** nói cần gì, **`testcase`** nói chứng minh thế nào, **`goalrun`** nói đã đạt chưa. Mỗi skill vẫn dùng riêng được.

### QA

| Skill | Làm gì | Kích hoạt |
| ----- | ------ | --------- |
| 🧪 [`testcase`](.agents/skills/testcase/SKILL.md) | Sinh test case từ requirement, tự tấn công output của mình để tìm case bị sót, rồi implement các case automatable thành test chạy được | "viết test case cho…" |
| 📋 [`docs-review`](.agents/skills/docs-review/SKILL.md) | Đối chiếu tài liệu với spec: spec yêu cầu gì vs tài liệu thực sự viết gì, mỗi verdict kèm trích dẫn | "review docs theo spec.md" |

### Thu thập dữ liệu

| Skill | Làm gì | Kích hoạt |
| ----- | ------ | --------- |
| 📥 [`playwright-notion`](.agents/skills/playwright-notion/SKILL.md) | Tải trang Notion về markdown qua browser đang đăng nhập, khi không có API token lẫn nút Export | "tải các trang Notion này về" |

## Quy ước chung

Quy ước mà mọi skill ở đây tuân theo, để đoán được một skill mới trước khi mở nó ra:

- **`SKILL.md` giữ nhỏ.** Chi tiết nằm trong `references/`, chỉ load khi task cần.
- **Review trước khi trả kết quả.** Skill nào tạo ra deliverable đều kết thúc bằng một vòng subagent độc lập: tự dựng lại công việc và tấn công nó, lặp đến khi một round không thêm được gì.
- **Script chỉ dùng stdlib.** Python hoặc Node, không cần cài gì trừ khi skill nói rõ; script lint output thay vì tin vào nó.
- **Verdict phải có bằng chứng.** Mọi khẳng định về tài liệu hay requirement đều trích dẫn dòng đã lấy ra.

Bước cài thêm, với skill nào cần:

```bash
cd .agents/skills/playwright-notion/scripts && npm install   # một lần
```

## Thêm skill mới

Bỏ một folder vào `.agents/skills/<name>/` gồm `SKILL.md` (frontmatter `name` + `description`), kèm `references/` và `scripts/` nếu cần. Không phải sửa manifest: cả hai `plugin.json` trỏ vào thư mục chứ không phải danh sách. Thêm một dòng vào bảng bên trên và cập nhật số skill ở badge. Version không sửa tay: merge vào `main` sẽ tự bump cả bốn manifest, tạo tag và publish release — commit `feat:` bump minor, có `!` hoặc `BREAKING CHANGE` bump major, còn lại bump patch.

## Cấu trúc

```
.agents/skills/<name>/     SKILL.md + references/ + scripts/
.claude-plugin/            manifest cho Claude Code
.zcode-plugin/             manifest cho ZCode
```

## License

MIT
