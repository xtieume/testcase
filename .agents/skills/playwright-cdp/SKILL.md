---
name: playwright-cdp
description: Use when pulling a requirement out of Notion or Slack into local markdown — body, every comment, and the attachments — because the decisions live in the comments and the attachments expire. Covers the case where there is no API token (company workspace, no integration allowed), the UI Export button is disabled or missing by permission, and access exists only through a logged-in browser. Also use when a scrape produced wrong markdown (tables repeated, cells duplicated, sidebar text in the body), when only the top level of a Notion page came out, or when a headless browser lands on a login screen.
---

# Playwright CDP

## Overview

Read Notion pages and Slack threads into local markdown, by calling each service's own web API from inside a browser that is already logged in.

Core principle: **do not scrape the DOM, and do not copy a browser profile.** Attach over the Chrome DevTools Protocol (CDP) to a browser this skill owns, then call the same endpoints the web app itself calls.

For GitHub there is nothing to build: `gh pr view <n> --json body,comments,reviews` and `gh api repos/<repo>/pulls/<n>/comments` already return everything, with credentials `gh` holds. Use those directly.

Reading is the main job and touches nothing: those endpoints only fetch data or produce a download. **`slack-post.mjs` is the one exception — it writes.** See *Posting to Slack* below before using it.

## What comes out

The same shape for both sources, per document:

```
<out>/
  <Name>.md            # body
  <Name>.comments.md   # every comment, numbered #1..#n, anchored <a id="c-n">
  assets/<Name>/       # attachments, downloaded
```

The reason for that shape, and the thing to preserve in any new extractor:

- **Comments are half the requirement.** Scope changes, the answer to an open question and the final formula are decided in comments, not in the body. Notion's own export drops them entirely.
- **A commented item in the body carries `> 💬 n comment → [#a–#b](<Name>.comments.md#c-a)`**, so a claim can be walked back to the comment that decided it.
- **Everything deep-links back**: Notion headings and toggles to the exact block, Slack messages and replies to their permalink.
- **Attachments are copied, not linked.** Notion and Slack hand out signed, session-bound URLs that expire — a document that only links them is empty within days. The spec is often in the PDF or the wireframe, not in the text.
- Files skipped for size or media type are named in the header. Report them; do not let them vanish.

## Two hard-won facts

Skipping either one wastes an hour. Both were verified by failure on macOS.

**1. Copying a browser profile can never carry the session.** Chromium 127+ encrypts cookies with App-Bound Encryption: the key is bound to the original profile and the OS, not stored in the copied files. A copied profile shows `os_crypt: {}` in `Local State` and is served the login screen. `Default`, `Profile 1`, `Profile 2` all fail the same way. This is about copying *someone else's* profile — a profile the skill creates and owns is fine, because the same binary writes and reads its own cookies.

**2. Scraping the rendered DOM produces wrong markdown.** Notion nests `.notion-selectable` inside `.notion-selectable`, so a selector walk emits every table once per nesting level (typically 3x) and every cell twice, sweeps the sidebar into the body, and drops all properties. Slack virtual-scrolls, so its DOM holds only a few dozen messages of a long channel. Use the APIs — that is the fix, not a better selector.

## Step 1 — the browser

```bash
scripts/agent-browser.sh          # headless; opens a window only on first run
```

It launches the Chrome for Testing that ships with Playwright against a profile under `~/.cache/playwright-cdp-profile`, so **the everyday browser is never touched**. The first run shows a window: sign in to Notion and Slack there once. Every run after that is headless and the session persists.

| Need | Command |
|---|---|
| Sign in again (session expired) | `scripts/agent-browser.sh --headed` |
| Stop it | `scripts/agent-browser.sh --stop` |
| Throw the profile away (loses the login) | `scripts/agent-browser.sh --reset` |
| Check CDP is up | `curl -s http://127.0.0.1:9222/json/version` |

No automation browser on the machine → `npx playwright install chromium`, or point `CDP_BROWSER_BIN` at a Chromium-family binary.

`scripts/start-browser.sh [brave|chrome|edge]` remains for the one case the owned profile cannot cover: a page reachable only from the personal profile. It **closes the user's browser** (the profile lock blocks the debug port) — say so before running it. If it reports `remote debugging requires a non-default data directory`, that build refuses CDP on its default profile dir; Brave commonly works where Chrome refuses.

## Step 2 — install deps once

```bash
cd scripts && npm install
```

`playwright-core` only (~13MB): the scripts attach to a running browser, so there is no browser to download.

## Step 3 — extract

Every script takes a single URL or a file of URLs, one per line.

### Notion

```bash
node scripts/notion-export.mjs urls.txt ./out 9222   # try first: Notion's own export
node scripts/notion.mjs        urls.txt ./out 9222   # the converter
```

| Script | Endpoint | Gets |
|---|---|---|
| `notion-export.mjs` | `enqueueTask` (`exportBlock`) → zip | Notion's own markdown + images, formatting exactly as the page reads |
| `notion.mjs` | `loadCachedPageChunkV2` + `syncRecordValues` + `queryCollection` + `getSignedFileUrls` | body + **comments** + attachments |

**A disabled Export button does not mean export is blocked.** In many workspaces the button is only hidden client-side by role while the server still accepts the task — that was true in the workspace this skill was built from. Test `notion-export.mjs` on one page before assuming otherwise; fall back when it reports `enqueueTask` `401`/`Unauthorized`, which means export really is disabled server-side.

**But export drops every comment**, so when the page is a requirement, run `notion.mjs` as well and keep both.

`notion.mjs` environment: `NOTION_MAX_MB` (30), `NOTION_MEDIA=1` (also fetch video/audio), `NOTION_NO_ASSETS=1` (link instead of download), `NOTION_RAW=1` (dump `<page>.raw.json` — use it when comments come out `0` but the UI shows some). `NOTION_RECURSIVE=1` on `notion-export.mjs` exports each page's subtree; leave it off, on a database page it pulls the whole table.

### Slack

```bash
node scripts/slack.mjs 'https://<team>.slack.com/archives/C0.../p1712345678901234' ./out 9222
```

| URL form | Gets |
|---|---|
| `.../archives/<C>/p<ts>` | that message and its whole thread |
| `.../archives/<C>` | the last `SLACK_LIMIT` messages (default 200) and each one's thread |
| `app.slack.com/client/<T>/<C>/thread/<C>-<ts>` | same as the first form |

Replies are comments: the body keeps the top-level messages, `comments.md` holds every reply. Environment: `SLACK_LIMIT`, `SLACK_MAX_MB`, `SLACK_MEDIA=1`.

The web client's token lives only on the `app.slack.com` origin — an `/archives/` link is a stub page that redirects to the desktop app, so the script hops origins by itself. `no localConfig_v2` / `no token for team` means that profile is not signed in to Slack: `agent-browser.sh --headed`, sign in, retry.

## Posting to Slack

`slack-post.mjs` posts a message, or a reply in a thread, as the signed-in user.

```bash
node scripts/slack-post.mjs <url> '<text>'            # shows what would be posted
node scripts/slack-post.mjs <url> '<text>' --send     # actually posts
```

A URL pointing at a message or thread replies in that thread; a channel URL posts a new message. Long or multi-line text: `-` reads stdin, `@file.md` reads a file, which also avoids fighting the shell over quoting.

**Without `--send` it is a dry run**: it prints the workspace, the channel name and the thread it would land in, and posts nothing. That default exists because the destination is the easy thing to get wrong — a channel id in a URL says nothing about which channel it is, and a message cannot be unsent from the notifications people already got.

Rules for the agent, not just the script:

- **Never post without the user having seen the exact text and the exact destination.** Run the dry run, show its output, wait for a yes. A previous yes does not cover the next message.
- Never post on your own initiative — only when asked to post something specific.
- It posts **as the user**, under their name. Write what they would write, not a bot announcement.
- Report the permalink the script prints, so they can check or delete it.

## Step 4 — verify

Never report success from an exit code. Each script prints its counts per document:

```
OK  9 comments  27 files  <out>/<Name>.md
```

- `notion.mjs` also logs to `/tmp/notion_dl.log` (`NOTION_DL_LOG` to override); `notion-export.mjs` to `/tmp/notion_export.log`. Count `OK` lines against the URL count and report any `FAIL`/`GAVE UP`.
- A page that reports `0 comments` while the UI clearly shows some is a finding, not a pass. Re-run with `NOTION_RAW=1` and check whether `discussion` in the dump is empty (really none) or populated (a renderer bug).
- A Notion page that comes out with headings but no content under them is the one-level bug — see the mistakes table.

```bash
node scripts/test-doc.mjs        # self-check for the renderers, needs no browser
```

A `slack-post.mjs` run is verified by its own output: a dry run ends in `DRY RUN — nothing was posted`, a real one in `POSTED <permalink>`. Never claim something was posted without that line.

## Common mistakes

| Mistake | What happens | Fix |
|---|---|---|
| Treating an export as the whole requirement | Every comment is missing — that is where the spec gets decided | Also run `notion.mjs` |
| Assuming a greyed-out Export button means export is blocked | Skips the best path for no reason | Test `notion-export.mjs` on one page |
| Trusting one `loadPageChunk` call | It returns one level and then reports an empty cursor: a real page came out as 16 blocks and 1 comment instead of 230 and 9 | Walk down from the root with `syncRecordValues` (`notion.mjs` does) |
| Following every block in the chunk | A chunk also carries unrelated sidebar blocks; following those crawls the workspace and never finishes | Bound the walk to the page |
| Keeping Notion/Slack file URLs instead of the files | Signed URLs expire; the doc is empty days later | The scripts save them under `assets/` |
| Copying a browser profile to a temp dir | Login screen, every time | Use the profile the skill owns |
| Scraping `.notion-selectable` / the Slack DOM | Tables 3x, cells 2x, sidebar in body; Slack yields a few dozen messages | Use the APIs |
| `open -a "Brave Browser" --args --remote-debugging-port=9222` | Flags silently dropped, port never opens | Exec the binary path directly (the scripts do) |
| Leaving a browser running when launching it with CDP | Profile lock blocks the port, with no error at the port | `agent-browser.sh` uses its own profile and sidesteps this |
| `waitUntil: 'networkidle'` | 30s timeout — Notion and Slack sync continuously | `domcontentloaded` + a short fixed wait |
| Attaching while the browser has no tab open | `connectOverCDP` fails with `Browser context management is not supported` | The scripts open a target first; a closed window is not a dead browser |
| Reusing one tab for 30+ Notion pages | Renderer crashes; every later page fails | `notion.mjs` recycles the tab every 5 pages and retries 3x |
| Plain `unzip` on the export zip | `Illegal byte sequence`, Japanese/Vietnamese names destroyed | Decode cp437→utf-8 (`notion-export.mjs` does) |
| Scraping the sidebar for the URL list | Gets database views, not the wanted rows | Ask the user for explicit URLs |
| Piping a long run through `tail` | Output buffered, progress invisible | Log to a file, `grep` it |

## Red flags — stop and re-read this skill

- About to hand over an export as "the requirement" without its comments.
- About to copy `Cookies`, `Local State` or a whole profile folder.
- About to write a `querySelector` walk over Notion blocks or Slack messages.
- About to skip `notion-export.mjs` because the UI hides the Export button.
- About to accept a Notion page whose headings have no content under them.
- About to report "downloaded everything" without reading the counts.

## Adding a source

Keep the output contract: import `commentBook`, `writeDoc` and `saveAsset` from `scripts/doc.mjs`, which own the numbering, the anchors, the reference lines and the attachment handling. `slack.mjs` is the shortest example to copy. Reach for the DOM only when the service has no API worth calling, and say so in the header of what it produces.

## Warn the user before starting

- Posting to Slack is visible to everyone in the channel and cannot be unsent from their notifications.
- These are internal company documents being copied to a local disk. Whether that fits their company policy is their call, not something to assume.
- While a run is active the browser listens on a local debug port, so any local process can drive it. `agent-browser.sh --stop` when done.
- `start-browser.sh` (the fallback path only) closes their everyday browser; unsaved work in it is at risk.
