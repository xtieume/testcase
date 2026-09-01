# testcase

Ba skill cho Claude Code. Hai skill QA đều kết thúc bằng một vòng review bắt buộc chạy trong subagent độc lập.

| Skill | Làm gì | Kích hoạt |
| ----- | ------ | --------- |
| 🧪 `testcase` | Sinh test case thủ công từ requirement, rồi tự tấn công output của mình để tìm case bị sót | "viết test case cho…" |
| 📋 `docs-review` | Đối chiếu tài liệu với spec: spec yêu cầu gì vs tài liệu thực sự viết gì | "review docs theo spec.md" |
| 📥 `playwright-notion` | Tải trang Notion về markdown qua browser đang đăng nhập, khi không có API token lẫn nút Export | "tải các trang Notion này về" |

## 🧪 testcase

Lập coverage map trước (positive / negative / boundary / validation / state / permission / error / data / UI / integration / regression, kèm 全角/半角 tiếng Nhật khi liên quan) → sinh case → vòng review độc lập: mỗi round 2 reviewer subagent (lần theo requirement / tấn công feature), lặp đến khi một round không thêm được gì.

Script lint cưỡng chế các rule:

| Check | Fail khi |
| ----- | -------- |
| Tỷ lệ happy-path | >40% case live là `Positive` |
| Độ phủ rủi ro | Một requirement chỉ có case success-path |
| Suppression | `<!-- coverage-ok: R7 — lý do -->` thiếu lý do, hoặc đã cũ |
| `--requirements reqs.txt` | Một requirement **không có** case nào |
| `--diff old.md new.md` | Một ID bị xoá thay vì đánh dấu `[OBSOLETE]` |
| Lint từng dòng | ID trùng, expected result rỗng, priority sai, step mơ hồ |

Thêm: cột `Automatable` Y/N mỗi case, export CSV (UTF-8 BOM, Excel mở tiếng Nhật chuẩn), review mode để audit một danh sách case có sẵn theo requirement.

## 📋 docs-review

Tách spec thành các requirement nguyên tử *trước khi* đọc tài liệu; mỗi requirement được gán `Covered` / `Partial` / `Missing` / `Contradict` / `Conflict` / `Stale` / `Undecided` kèm trích dẫn bắt buộc. Không có spec → chế độ investigation tự suy checklist từ câu hỏi của bạn.

Subagent độc lập tự dựng lại checklist và tấn công report đến khi một round hội tụ (round 5 vẫn còn biến động → báo unconverged). Trên ~15 tài liệu thì chuyển sang workflow index/shard. `--fix` áp các dòng `Missing`/`Partial`/`Stale` vào tài liệu được audit — không bao giờ sửa spec. Có script lint kiểm verdict, trích dẫn, và việc loop đã thực sự chạy.

## 📥 playwright-notion

Gắn vào Brave/Chrome/Edge **đang chạy** qua CDP, gọi thẳng endpoint của Notion từ trong tab đã đăng nhập. Chỉ đọc. Ưu tiên export markdown gốc của Notion (nút Export bị mờ thường chỉ là check phía client), fallback sang tự convert block JSON. An toàn khi chạy batch: xoay vòng tab, retry trang crash, log từng trang. Từ chối hai ngõ cụt: copy profile browser (Chromium 127+ App-Bound Encryption làm rớt session) và scrape DOM (bảng nhân ba, mất properties).

## Cài đặt & sử dụng

```bash
claude plugin marketplace add xtieume/testcase
claude plugin install testcase@testcase-marketplace
```

Hoặc copy tay: `cp -R .agents/skills/<name> ~/.claude/skills/<name>`. Skill kích hoạt bằng ngôn ngữ tự nhiên hoặc `/testcase`, `/docs-review`, `/playwright-notion`.

**Cursor & Antigravity** — skill nằm trong thư mục chuẩn `.agents/skills/` mà cả hai IDE đọc trực tiếp. Clone repo này vào project (hoặc symlink):

```bash
git clone https://github.com/xtieume/testcase.git
ln -s $(pwd)/testcase/.agents/skills .agents/skills   # mức project
# hoặc toàn cục: cp -R testcase/.agents/skills/* ~/.gemini/antigravity/skills/
```

```bash
python3 .agents/skills/testcase/scripts/summarize.py testcases.md [--requirements reqs.txt] [--csv out.csv]
python3 .agents/skills/testcase/scripts/summarize.py --diff previous.md testcases.md
```

`playwright-notion` cần `cd .agents/skills/playwright-notion/scripts && npm install` một lần; lệnh chạy tay xem trong `SKILL.md` của nó.

## Cấu trúc

Mỗi skill: `SKILL.md` (cố ý giữ nhỏ) + `references/` chỉ load khi cần + `scripts/` (Python stdlib / Node). `.claude-plugin/` chứa manifest.

## License

MIT
