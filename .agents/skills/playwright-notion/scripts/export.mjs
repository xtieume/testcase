// Notion native markdown export via the browser's own session.
// Calls /api/v3/enqueueTask (exportBlock) — the same task the UI Export button enqueues —
// then downloads and unpacks the resulting zip.
//
// usage: node export.mjs <urls-file> <out-dir> [cdp-port]
//
// Read-only: enqueueTask/getTasks only produce a download; nothing in Notion is modified.
import { chromium } from 'playwright';
import fs from 'fs';
import path from 'path';
import { execFileSync } from 'child_process';

const URLS_FILE = process.argv[2] || './urls.txt';
const OUT = process.argv[3] || './notion-docs';
const PORT = process.argv[4] || '9222';
const LOG = process.env.NOTION_DL_LOG || '/tmp/notion_export.log';
// Export the page's subtree too. Off by default: a database page pulls its whole table.
const RECURSIVE = process.env.NOTION_RECURSIVE === '1';

const log = (m) => { fs.appendFileSync(LOG, m + '\n'); console.log(m); };

const URLS = fs.readFileSync(URLS_FILE, 'utf8').split('\n').map(s => s.trim()).filter(Boolean);

function dashId(hex) {
  return `${hex.slice(0,8)}-${hex.slice(8,12)}-${hex.slice(12,16)}-${hex.slice(16,20)}-${hex.slice(20,32)}`;
}
function idFromUrl(u) {
  const m = u.match(/([a-f0-9]{32})/i);
  return m ? dashId(m[1].toLowerCase()) : null;
}

// Notion writes zip entries as UTF-8 bytes without the UTF-8 flag, so most
// unzip tools mangle Japanese/Vietnamese names. Decode them ourselves.
function unpack(zipPath, destDir) {
  const script = `
import zipfile, pathlib, sys
z = zipfile.ZipFile(sys.argv[1])
out = pathlib.Path(sys.argv[2])
names = []
for info in z.infolist():
    name = info.filename if (info.flag_bits & 0x800) else info.filename.encode('cp437').decode('utf-8', 'replace')
    dest = out / name
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not info.is_dir():
        dest.write_bytes(z.read(info))
        names.append(name)
print(len(names))
`;
  const n = execFileSync('python3', ['-c', script, zipPath, destDir], { encoding: 'utf8' }).trim();
  return parseInt(n, 10) || 0;
}

async function exportOne(page, url, idx, total) {
  const pageId = idFromUrl(url);
  if (!pageId) { log(`[${idx}/${total}] SKIP (no page id): ${url}`); return false; }

  await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 45000 });
  await page.waitForTimeout(2500);

  const res = await page.evaluate(async ({ pid, recursive }) => {
    const post = async (ep, body) => {
      const r = await fetch('/api/v3/' + ep, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body)
      });
      const txt = await r.text();
      if (r.status !== 200) return { httpError: `${ep} ${r.status}: ${txt.slice(0, 200)}` };
      return JSON.parse(txt);
    };

    // spaceId is required by enqueueTask; loadPageChunk carries it and also
    // confirms we can actually read the page with the current session.
    const chunk = await post('loadPageChunk', {
      pageId: pid, limit: 10, cursor: { stack: [] }, chunkNumber: 0, verticalColumns: false
    });
    if (chunk.httpError) return { error: chunk.httpError };
    const wrap = chunk?.recordMap?.block?.[pid];
    const spaceId = wrap?.spaceId;
    const block = wrap?.value?.value || wrap?.value;
    if (!spaceId || !block) return { error: 'page not readable (no session or no access)' };

    const titleArr = block.properties?.title || [];
    const title = titleArr.map(s => s[0]).join('');

    const enq = await post('enqueueTask', {
      task: {
        eventName: 'exportBlock',
        request: {
          block: { id: pid, spaceId },
          recursive,
          exportOptions: {
            exportType: 'markdown',
            timeZone: Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC',
            locale: 'en',
            collectionViewExportType: 'currentView',
            flattenExportFiletree: false
          }
        }
      }
    });
    if (enq.httpError) return { error: enq.httpError, title };
    if (!enq.taskId) return { error: 'no taskId returned', title };

    // Poll. Export is server-side; big subtrees take a while.
    for (let i = 0; i < 90; i++) {
      await new Promise(s => setTimeout(s, 2000));
      const t = await post('getTasks', { taskIds: [enq.taskId] });
      if (t.httpError) return { error: t.httpError, title };
      const task = t?.results?.[0];
      if (task?.state === 'success') {
        return { url: task.status?.exportURL, pages: task.status?.pagesExported, title };
      }
      if (task?.state === 'failure') {
        return { error: 'export task failed: ' + JSON.stringify(task.error || task.status).slice(0, 200), title };
      }
    }
    return { error: 'export task timed out after 3 minutes', title };
  }, { pid: pageId, recursive: RECURSIVE });

  if (res.error) { log(`[${idx}/${total}] FAIL ${res.title || url}: ${res.error}`); return false; }
  if (!res.url) { log(`[${idx}/${total}] FAIL ${url}: no export URL`); return false; }

  // Download through the browser context so the signed URL keeps its session.
  const resp = await page.request.get(res.url);
  if (!resp.ok()) { log(`[${idx}/${total}] FAIL download ${resp.status()} for ${res.title}`); return false; }
  const buf = await resp.body();

  const safe = (res.title || pageId).replace(/[/\\?%*:|"<>]/g, '-').replace(/\s+/g, ' ').trim().slice(0, 120) || pageId;
  const zipPath = path.join(OUT, `${safe}.zip`);
  fs.writeFileSync(zipPath, buf);
  const count = unpack(zipPath, OUT);
  fs.unlinkSync(zipPath);

  log(`[${idx}/${total}] OK  ${res.pages} page(s), ${count} file(s), ${Math.round(buf.length/1024)}KB  ${safe}`);
  return true;
}

fs.writeFileSync(LOG, '');
fs.mkdirSync(OUT, { recursive: true });
log(`URLs: ${URLS.length}  recursive=${RECURSIVE}`);

const browser = await chromium.connectOverCDP(`http://127.0.0.1:${PORT}`);
const ctx = browser.contexts()[0];
let page = await ctx.newPage();

let ok = 0;
for (let i = 0; i < URLS.length; i++) {
  // Recycle the tab: Notion leaks memory and eventually crashes the renderer.
  if (i > 0 && i % 5 === 0) {
    try { await page.close(); } catch {}
    page = await ctx.newPage();
  }
  let done = false;
  for (let attempt = 1; attempt <= 3 && !done; attempt++) {
    try {
      done = await exportOne(page, URLS[i], i + 1, URLS.length);
      if (!done) break; // a reported failure is not a crash — don't retry it
    } catch (e) {
      log(`[${i+1}/${URLS.length}] attempt ${attempt} crashed: ${e.message}`);
      try { await page.close(); } catch {}
      page = await ctx.newPage();
    }
  }
  if (done) ok++;
  else log(`[${i+1}/${URLS.length}] GAVE UP ${URLS[i]}`);
}

try { await page.close(); } catch {}
log(`DONE  ${ok}/${URLS.length} exported`);
process.exit(0);
