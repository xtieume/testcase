---
name: playwright-notion
description: Use when downloading or reading Notion pages without an API token — the workspace is company-owned, there is no integration secret, the UI Export button is disabled or missing by permission, and access exists only through a logged-in browser. Also use when a Notion scrape produced wrong markdown (tables repeated, cells duplicated, sidebar text mixed into content), when a headless browser lands on the Notion login screen, or when a page's comments and attachments are needed alongside its body because that is where the spec was actually decided.
---

# Playwright Notion

## Overview

Read Notion pages through a browser that is already logged in, by calling Notion's own internal web API from inside that browser tab.

Core principle: **do not scrape the DOM, and do not copy the browser profile.** Attach to a running browser over the Chrome DevTools Protocol (CDP), then call the same endpoints the Notion web app itself calls.

Read-only. The endpoints used only fetch data or produce a download; nothing in Notion is created, edited, or deleted.

## When to use

- No Notion API token available (company workspace, no integration allowed).
- UI Export is disabled/greyed out or absent because the account is read-only or guest.
- MCP Notion server is not an option; only browser access exists.
- A previous scrape returned garbage markdown: duplicated tables, doubled cells, sidebar links inside the body, lost properties.
- A Playwright/Puppeteer script keeps landing on Notion's login page even though the user is logged in normally.

**Do NOT use when** an API token or working MCP Notion connection exists — use those, they are simpler and supported.

## Two hard-won facts that dictate the approach

Skipping either one wastes an hour. Both were verified by failure on macOS.

**1. Copying the browser profile can never carry the session.** Chromium 127+ encrypts cookies with App-Bound Encryption: the key is bound to the original profile and the OS, not stored in the copied files. A copied profile shows `os_crypt: {}` in `Local State`, cannot decrypt the original cookies, and Notion serves the login screen. Copying `Cookies` + `Local State` + `Preferences` from `Default`, `Profile 1`, and `Profile 2` all fail the same way. Do not try it — attach to the real running browser instead.

**2. Scraping the rendered DOM produces wrong markdown.** Notion nests `.notion-selectable` inside `.notion-selectable`, so a selector-based walk emits every table once per nesting level (typically 3x) and every cell twice. It also sweeps the sidebar navigation into the page body and drops all page properties. Use the API instead — that is the fix, not a better selector.

## Two scripts: try export first

| Script | Endpoint | Output | Use |
|---|---|---|---|
| `scripts/export.mjs` | `enqueueTask` (`exportBlock`) → zip | Notion's own markdown + images downloaded | **Try this first** |
| `scripts/download.mjs` | `loadCachedPageChunkV2` + `queryCollection` + `getSignedFileUrls` | markdown + `comments.md` + downloaded `assets/` | Fallback if export is blocked, **and whenever comments matter** |

**A disabled Export button does not mean export is blocked.** In many workspaces the button is only hidden client-side by role, while the server still accepts the export task. That was true in the case this skill was built from: the UI offered no Export, yet `enqueueTask` returned `200` and produced a proper zip. So always test `export.mjs` on one page before falling back.

Native export is better where it works: it is Notion's own renderer, so tables, nested content and formatting come out exactly as the page reads.

**But export drops every comment.** In most workspaces the decisions — a scope change, the answer to an open question, the final formula — live in comments, not in the body. When the page is a requirement and the comments matter, run `download.mjs` as well and keep both: export for the body, `download.mjs` for `<page>.comments.md`.

Fall back to `download.mjs` when `export.mjs` reports an `enqueueTask` `401`/`Unauthorized` — that means the workspace really did disable export server-side (an Enterprise setting). `download.mjs` still works there, because it uses nothing more than the read access the browser already has.

## Workflow

**Step 1 — start the browser with CDP enabled.**

```bash
scripts/start-browser.sh brave 9222      # or: chrome | edge
```

The script lists available profiles, closes any running instance (its profile lock blocks the debug port), relaunches detached against the **real** profile dir, and waits for the port. It is idempotent — if CDP already listens it exits immediately.

This closes the user's browser windows. Say so before running it, and re-run it whenever a later step reports a connection refusal.

If it reports `remote debugging requires a non-default data directory`, that browser build refuses CDP on its default profile dir. Try another browser — **Brave commonly works where Chrome refuses**.

**Step 2 — install script deps once.**

```bash
cd scripts && npm install
```

**Step 3 — collect the target URLs.** One per line in a plain text file. Any Notion URL form works; both scripts extract the 32-hex page id themselves, so `?v=...&source=copy_link` query strings can stay.

```
https://app.notion.com/p/883f894a7fd44a1b9bfa0d6af0ff4a28
https://app.notion.com/p/RQ-01-31136f82f94b4a16adb8b434404db850
```

Ask the user for the list. Do not guess links — sidebar `<a href>` scraping returns the navigation menu (a dozen or so database views), not the rows the user means.

**Step 4 — smoke-test one URL.** Run the chosen script against a single-URL file and open the output. A whole batch against a logged-out browser produces a directory of useless files.

```bash
node scripts/export.mjs one-url.txt ./out 9222
```

If it fails with `Unauthorized`, switch to `scripts/download.mjs` and smoke-test that instead.

**Step 5 — run the full list.**

```bash
node scripts/export.mjs   urls.txt ./notion-docs 9222   # preferred
node scripts/download.mjs urls.txt ./notion-docs 9222   # fallback
```

`NOTION_RECURSIVE=1` on `export.mjs` exports each page's subtree as well. Leave it off by default — on a database page it pulls the entire table.

`download.mjs` environment variables:

| Variable | Default | Effect |
|---|---|---|
| `NOTION_MAX_MB` | `30` | skip attachments larger than this |
| `NOTION_MEDIA` | *(off)* | `=1` also downloads video/audio (usually huge) |
| `NOTION_NO_ASSETS` | *(off)* | `=1` keeps the original URLs and downloads nothing |
| `NOTION_RAW` | *(off)* | `=1` also dumps `<page>.raw.json` — use it when comments come out `0` but the UI shows some |

**Step 6 — verify.** Count `OK` lines against the URL count and report any `FAIL`/`GAVE UP` line. Never report success from an exit code alone.

```bash
grep -c OK /tmp/notion_export.log            # export.mjs
grep -E "FAIL|GAVE UP" /tmp/notion_export.log
```

`download.mjs` logs `N comments  M files` per page. If a page shows `0 comments` while the Notion UI clearly has some, say so — do not let it pass silently. Re-run with `NOTION_RAW=1` and check whether `discussion` in the dump is empty (really none) or populated (a renderer bug).

## Quick reference

| Need | Command |
|---|---|
| Start/verify CDP | `scripts/start-browser.sh brave 9222` |
| Check CDP is up | `curl -s http://127.0.0.1:9222/json/version` |
| Install deps | `cd scripts && npm install` |
| Native export (preferred) | `node scripts/export.mjs urls.txt ./out 9222` |
| Converter (fallback) | `node scripts/download.mjs urls.txt ./out 9222` |
| Check results | `grep -c OK /tmp/notion_export.log` |
| Self-check the converter | `node scripts/test-download.mjs` |

Logs default to `/tmp/notion_export.log` and `/tmp/notion_dl.log`; override with `NOTION_DL_LOG`.

## What the output contains

**`export.mjs`** — Notion's own export, unpacked: one `.md` per page under a workspace-named folder, plus a sibling folder of downloaded images per page. Properties appear as a plain key/value block at the top, mentions and relations resolved to names and URLs.

**`download.mjs`** — per page:

```
<out>/
  <Page title>.md            # body
  <Page title>.comments.md   # every comment, numbered #1..#n, anchored <a id="c-n">
  assets/<Page title>/       # attachments downloaded from that page
```

The body holds title, source URL, an extraction header (block/file/comment counts), a `## Properties` section, headings, nested lists, to-do checkboxes, toggles, quotes, callouts as `> [!NOTE]`, code blocks with language tags, equations as `$$`, dividers, and tables with correct columns (inline tables and embedded database views via `queryCollection`).

Traceability — the reason to prefer this over a plain scrape:

- a commented block carries `> 💬 n comment → [#a–#b](<page>.comments.md#c-a)`;
- each heading and toggle carries `[↗](<url>#<blockId>)`, opening that exact block in Notion;
- each comment thread carries `[↗](<url>?d=<discussionId>)`, opening that exact thread;
- person mentions resolve to real names and page mentions to titles plus URLs, from the same recordMap.

Attachments are downloaded rather than linked, because Notion's file URLs are signed and expire — a document that only links them is empty within days. Files skipped for size or media type are named in the header; report them rather than letting them vanish.

## Common mistakes

| Mistake | What happens | Fix |
|---|---|---|
| Assuming a greyed-out Export button means export is blocked | Skips the best path for no reason | Test `export.mjs` on one page first |
| Copying the browser profile to a temp dir | Login screen, every time | Attach to the running browser over CDP |
| Scraping `.notion-selectable` / DOM | Tables 3x, cells 2x, sidebar in body, no properties | Use the API scripts |
| `open -a "Brave Browser" --args --remote-debugging-port=9222` | Flags silently dropped, port never opens | Exec the binary path directly (the script does) |
| Leaving the browser running when launching with CDP | Profile lock blocks the port, with no error at the port | Close it first (the script does) |
| `waitUntil: 'networkidle'` | 30s timeout — Notion syncs continuously | `domcontentloaded` + a short fixed wait |
| Reusing one tab for 30+ pages | Renderer crashes; every later page fails | Both scripts recycle the tab every 5 pages and retry 3x |
| Plain `unzip` on the export zip | `Illegal byte sequence`, Japanese/Vietnamese names destroyed | Decode cp437→utf-8 (`export.mjs` does) |
| Scraping the sidebar for the URL list | Gets database views, not the wanted rows | Ask the user for explicit URLs |
| Treating `export.mjs` output as the whole requirement | Every comment is missing — that is where the spec gets decided | Also run `download.mjs` for `comments.md` |
| Keeping Notion's file URLs instead of the files | Signed URLs expire; the doc is empty a few days later | `download.mjs` saves them under `assets/` |
| Piping a long run through `tail` | Output buffered, progress invisible | Log to a file, `grep` it |

## Red flags — stop and re-read this skill

- About to copy `Cookies`, `Local State`, or a whole profile folder → will not work, see fact 1.
- About to write a `querySelector` walk over Notion blocks → will produce duplicates, see fact 2.
- About to skip `export.mjs` because the UI hides the Export button → test it anyway.
- About to launch a browser with `open -a ... --args` → flags get dropped.
- About to report "downloaded all pages" without grepping the log → verify first.
- About to hand over an export as "the requirement" without its comments → the decisions are in the comments.

## Warn the user before starting

- Their browser will be closed and relaunched; unsaved work in it is at risk.
- While the run is active the browser listens on a local debug port, so any local process can drive it. Restart the browser normally afterwards.
- These are internal company documents being copied to a local disk. Whether that fits their company policy is their call to make, not something to assume.
