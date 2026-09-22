import fs from 'fs';
import path from 'path';

// usage: node download.mjs <urls-file> <out-dir> [cdp-port]
const URLS_FILE = process.argv[2] || './urls.txt';
const OUT = process.argv[3] || './notion-docs';
const PORT = process.argv[4] || '9222';
const LOG = process.env.NOTION_DL_LOG || '/tmp/notion_dl.log';
const MAX_MB = Number(process.env.NOTION_MAX_MB || 30);
const WITH_MEDIA = process.env.NOTION_MEDIA === '1';
const NO_ASSETS = process.env.NOTION_NO_ASSETS === '1';
const WITH_RAW = process.env.NOTION_RAW === '1';
const log = (m) => { fs.appendFileSync(LOG, m + '\n'); console.log(m); };

const ATTACHMENT = /amazonaws|secure\.notion|prod-files|attachment:/;

function dashId(raw) {
  const hex = raw.replace(/-/g, '');
  return `${hex.slice(0,8)}-${hex.slice(8,12)}-${hex.slice(12,16)}-${hex.slice(16,20)}-${hex.slice(20,32)}`;
}
function idFromUrl(u) {
  const m = u.match(/([a-f0-9]{32})/i);
  return m ? dashId(m[1]) : null;
}
const noDash = (id) => String(id).replace(/-/g, '');
const safeName = (s) => (s || 'file').replace(/[/\\?%*:|"<>]/g, '_').replace(/\s+/g, '_').slice(0, 120);

// Fetch every block of a page, run inside the browser.
// loadPageChunk only returns one level deep and then reports an empty cursor,
// so the children it names are pulled in afterwards until nothing is missing.
// discussion/comment/notion_user ride along in the same record map.
async function fetchRecordMap(page, pageId) {
  return page.evaluate(async (pid) => {
    const TABLES = ['block', 'collection', 'collection_view', 'discussion', 'comment', 'notion_user'];
    const merged = Object.fromEntries(TABLES.map(t => [t, {}]));
    const post = (ep, body) => fetch('/api/v3/' + ep, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body)
    });
    const absorb = (rm) => { for (const t of TABLES) Object.assign(merged[t], rm?.[t] || {}); };
    const unwrap = (w) => w?.value?.value || w?.value || null;

    let cursor = { stack: [] };
    let spaceId = null;
    for (let i = 0; i < 40; i++) {
      const body = { pageId: pid, limit: 100, cursor, chunkNumber: i, verticalColumns: false };
      let r = await post('loadCachedPageChunkV2', body);
      if (r.status !== 200) r = await post('loadPageChunk', body);
      if (r.status !== 200) break;
      const j = await r.json();
      absorb(j.recordMap);
      spaceId = spaceId || j.spaceId || null;
      if (!j.cursor || !j.cursor.stack || j.cursor.stack.length === 0) break;
      cursor = j.cursor;
    }
    spaceId = spaceId || unwrap(merged.block[pid])?.space_id || null;

    // loadPageChunk names children without returning them, so walk down from
    // the root and fetch what is missing. Bounded to this page: a chunk also
    // carries unrelated blocks, and following those crawls the workspace.
    const fetchMissing = async (pointers) => {
      for (let k = 0; k < pointers.length; k += 100) {
        const r = await post('syncRecordValues', {
          requests: pointers.slice(k, k + 100).map(p => ({ pointer: { ...p, spaceId }, version: -1 }))
        });
        if (r.status === 200) absorb((await r.json()).recordMap);
      }
    };

    const mine = new Set([pid]);
    let frontier = [pid];
    for (let depth = 0; depth < 30 && frontier.length; depth++) {
      await fetchMissing(frontier.filter(id => !merged.block[id]).map(id => ({ table: 'block', id })));
      const next = [];
      for (const id of frontier) {
        const b = unwrap(merged.block[id]);
        if (!b) continue;
        if (id !== pid && b.type === 'page') continue; // child pages are listed, not inlined
        for (const c of b.content || []) if (!mine.has(c)) { mine.add(c); next.push(c); }
      }
      frontier = next;
    }

    const threads = [];
    for (const id of mine) for (const d of unwrap(merged.block[id])?.discussions || []) threads.push(d);
    await fetchMissing(threads.filter(d => !merged.discussion[d]).map(id => ({ table: 'discussion', id })));

    const msgs = [];
    for (const d of threads) for (const c of unwrap(merged.discussion[d])?.comments || []) msgs.push(c);
    await fetchMissing(msgs.filter(c => !merged.comment[c]).map(id => ({ table: 'comment', id })));

    const people = new Set();
    for (const c of msgs) {
      const by = unwrap(merged.comment[c])?.created_by_id;
      if (by && !merged.notion_user[by]) people.add(by);
    }
    await fetchMissing([...people].map(id => ({ table: 'notion_user', id })));

    return { rm: merged, spaceId };
  }, pageId);
}

// Query a collection (database) to get its rows, inside browser
async function fetchCollectionRows(page, collectionId, viewId, spaceId) {
  return page.evaluate(async ({ cid, vid, sid }) => {
    const body = {
      source: { type: 'collection', id: cid, spaceId: sid },
      collectionView: { id: vid, spaceId: sid },
      loader: { type: 'reducer', reducers: { collection_group_results: { type: 'results', limit: 200 } }, searchQuery: '', userTimeZone: 'Asia/Ho_Chi_Minh' }
    };
    const r = await fetch('/api/v3/queryCollection?src=initial_load', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body)
    });
    if (r.status !== 200) return null;
    return r.json();
  }, { cid: collectionId, vid: viewId, sid: spaceId });
}

// Exchange raw file sources for time-limited signed download URLs
async function fetchSignedUrls(page, refs) {
  return page.evaluate(async (list) => {
    const r = await fetch('/api/v3/getSignedFileUrls', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ urls: list.map(f => ({ url: f.source, permissionRecord: { table: 'block', id: f.id } })) })
    });
    if (r.status !== 200) return [];
    return (await r.json()).signedUrls || [];
  }, refs);
}

const unwrap = (w) => w?.value?.value || w?.value || null;

// per-page state, set in downloadPage
let RM = null;          // record map, so rich() can resolve users and page mentions
let BASE = '';          // page url without hash, for [↗] deep links
let ASSETS = {};        // original file url -> local relative path
let COMMENTS = [];      // markdown chunks for <page>.comments.md
let COMMENT_SEEN = new Set();
let CNUM = 0;

function setPageContext(rm, baseUrl, assets = {}) {
  RM = rm; BASE = baseUrl; ASSETS = assets;
  COMMENTS = []; COMMENT_SEEN = new Set(); CNUM = 0;
  return { comments: COMMENTS };
}

const userName = (id) => {
  const u = unwrap(RM?.notion_user?.[id]);
  if (!u) return 'user';
  return u.name || [u.given_name, u.family_name].filter(Boolean).join(' ') || u.email || 'user';
};
const pageMention = (id) => {
  const p = unwrap(RM?.block?.[id]);
  const t = p ? rich(p.properties?.title) : '';
  return `[${t || 'page'}](https://www.notion.so/${noDash(id)})`;
};
const stamp = (t) => (t ? new Date(t).toISOString().replace('T', ' ').slice(0, 16) : '');

// Notion rich text array -> markdown inline
function rich(arr) {
  if (!Array.isArray(arr)) return '';
  return arr.map(seg => {
    let t = seg[0] ?? '';
    const fmts = seg[1] || [];
    // page/user/date mention placeholder
    if (t === '‣') {
      for (const f of fmts) {
        if (f[0] === 'd' && f[1]?.start_date) return f[1].start_date + (f[1].end_date ? ` → ${f[1].end_date}` : '');
        if (f[0] === 'p') return pageMention(f[1]);
        if (f[0] === 'u') return `@${userName(f[1])}`;
      }
      return '';
    }
    let link = null;
    for (const f of fmts) {
      switch (f[0]) {
        case 'b': t = `**${t}**`; break;
        case 'i': t = `*${t}*`; break;
        case 'c': t = `\`${t}\``; break;
        case 's': t = `~~${t}~~`; break;
        case '_': t = `<u>${t}</u>`; break;
        case 'a': link = f[1]; break;
        case 'e': t = `$${f[1]}$`; break;
      }
    }
    // notion serves in-page links relative; they only resolve from the app
    if (link?.startsWith('/')) link = 'https://www.notion.so' + link;
    if (link) t = `[${t}](${ASSETS[link] || link})`;
    return t;
  }).join('');
}

const propText = (v) => Array.isArray(v) ? rich(v) : (v == null ? '' : String(v));

// Number every comment thread hanging off a block, stash the markdown for
// comments.md, and return the inline reference line for the body document.
function commentRef(b, anchorText) {
  const nums = [];
  for (const did of b.discussions || []) {
    const d = unwrap(RM.discussion?.[did]);
    if (!d || !(d.comments || []).length) continue;
    const items = [];
    for (const cid of d.comments) {
      const c = unwrap(RM.comment?.[cid]);
      if (!c || COMMENT_SEEN.has(cid)) continue;
      COMMENT_SEEN.add(cid);
      const n = ++CNUM;
      nums.push(n);
      const who = userName(c.created_by_id || c.created_by?.id);
      items.push(`### <a id="c-${n}"></a>#${n} — ${who} · ${stamp(c.created_time)}\n\n${rich(c.text) || '_(empty)_'}`);
    }
    if (!items.length) continue;
    COMMENTS.push([
      `## On: ${anchorText || '(page)'}${d.resolved ? ' · _resolved_' : ''} · [↗](${BASE}?d=${noDash(did)})`,
      '', items.join('\n\n'), ''
    ].join('\n'));
  }
  if (!nums.length) return '';
  const label = nums.length === 1 ? `#${nums[0]}` : `#${nums[0]}–#${nums[nums.length - 1]}`;
  return `💬 ${nums.length} comment → [${label}](COMMENTS_FILE#c-${nums[0]})`;
}

function renderBlocks(ids, rm, depth, collections, seen) {
  const out = [];
  const ind = '  '.repeat(depth);
  let numCounter = 0;

  for (const id of ids || []) {
    const b = unwrap(rm.block[id]);
    if (!b) continue;
    if (seen.has(id)) continue;
    seen.add(id);

    const txt = rich(b.properties?.title);
    const kids = b.content || [];
    const t = b.type;
    const deep = ` [↗](${BASE}#${noDash(id)})`;

    if (t !== 'numbered_list') numCounter = 0;

    const ref = commentRef(b, txt || t);
    if (ref) out.push(`${ind}> ${ref}\n`);

    switch (t) {
      case 'header':            out.push(`${ind}## ${txt}${deep}\n`); break;
      case 'sub_header':        out.push(`${ind}### ${txt}${deep}\n`); break;
      case 'sub_sub_header':    out.push(`${ind}#### ${txt}${deep}\n`); break;
      case 'text':              out.push(txt ? `${ind}${txt}\n` : ''); break;
      case 'bulleted_list':     out.push(`${ind}- ${txt}`); break;
      case 'numbered_list':     numCounter++; out.push(`${ind}${numCounter}. ${txt}`); break;
      case 'to_do':             out.push(`${ind}- [${b.properties?.checked?.[0]?.[0] === 'Yes' ? 'x' : ' '}] ${txt}`); break;
      case 'toggle':            out.push(`${ind}<details><summary>${txt}${deep}</summary>\n`); break;
      case 'quote':             out.push(`${ind}> ${txt}\n`); break;
      case 'callout':           out.push(`${ind}> [!NOTE]\n${ind}> ${txt.replace(/\n/g, `\n${ind}> `)}\n`); break;
      case 'code': {
        const lang = (b.properties?.language?.[0]?.[0] || '').toLowerCase();
        out.push(`${ind}\`\`\`${lang}\n${b.properties?.title?.map(s => s[0]).join('') || ''}\n${ind}\`\`\`\n`);
        break;
      }
      case 'equation':          out.push(`${ind}$$\n${txt}\n$$\n`); break;
      case 'divider':           out.push(`${ind}---\n`); break;
      case 'image': {
        const src = b.properties?.source?.[0]?.[0] || '';
        const cap = rich(b.properties?.caption);
        out.push(`${ind}![${cap}](${ASSETS[src] || src})\n`);
        break;
      }
      case 'file': case 'pdf': case 'video': case 'audio': {
        const src = b.properties?.source?.[0]?.[0] || '';
        out.push(`${ind}[${t}: ${rich(b.properties?.title) || src}](${ASSETS[src] || src})\n`);
        break;
      }
      case 'bookmark': {
        const link = b.properties?.link?.[0]?.[0] || '';
        out.push(`${ind}[${rich(b.properties?.title) || link}](${link})\n`);
        break;
      }
      case 'page': {
        out.push(`${ind}- ${txt || '(untitled)'} ↗\n`);
        continue; // don't inline child page content
      }
      case 'table': {
        out.push(renderTable(id, b, rm, ind));
        continue; // rows handled
      }
      case 'column_list': case 'column':
        break; // just descend
      case 'collection_view': case 'collection_view_page': {
        const cvId = (b.view_ids || [])[0];
        const colId = b.collection_id;
        const key = `${colId}|${cvId}`;
        if (collections[key]) out.push(collections[key]);
        else out.push(`${ind}_[database view]_\n`);
        continue;
      }
      case 'transclusion_container': case 'transclusion_reference': case 'alias':
        break;
      default:
        if (txt) out.push(`${ind}${txt}\n`);
    }

    if (kids.length && t !== 'table') {
      const nested = renderBlocks(kids, rm, ['bulleted_list','numbered_list','to_do','toggle'].includes(t) ? depth + 1 : depth, collections, seen);
      if (nested.trim()) out.push(nested);
    }
    if (t === 'toggle') out.push(`${ind}</details>\n`);
  }
  return out.join('\n');
}

// Simple table block -> markdown, one row per table_row, cells by column order
function renderTable(tableId, tableBlock, rm, ind) {
  const colOrder = tableBlock.format?.table_block_column_order || [];
  const rowIds = tableBlock.content || [];
  const lines = [];
  rowIds.forEach((rid, idx) => {
    const row = unwrap(rm.block[rid]);
    if (!row) return;
    const cells = colOrder.map(c => (rich(row.properties?.[c]) || '').replace(/\n/g, ' ').replace(/\|/g, '\\|'));
    lines.push(`${ind}| ${cells.join(' | ')} |`);
    if (idx === 0) lines.push(`${ind}| ${colOrder.map(() => '---').join(' | ')} |`);
  });
  return lines.join('\n') + '\n';
}

// Render a database (collection) as a markdown table of its rows
function renderCollection(colWrap, queryResult, rm) {
  const col = unwrap(colWrap);
  if (!col) return '';
  const schema = col.schema || {};
  // column order: title first, then rest
  const colIds = Object.keys(schema).sort((a, b) => (schema[a].type === 'title' ? -1 : schema[b].type === 'title' ? 1 : 0));
  const headers = colIds.map(id => schema[id].name || id);

  const blockIds = queryResult?.result?.reducerResults?.collection_group_results?.blockIds
                || queryResult?.result?.blockIds || [];
  const rowBlocks = { ...(queryResult?.recordMap?.block || {}), ...rm.block };

  const lines = [];
  lines.push(`| ${headers.map(h => h.replace(/\|/g, '\\|')).join(' | ')} |`);
  lines.push(`| ${headers.map(() => '---').join(' | ')} |`);
  for (const bid of blockIds) {
    const row = unwrap(rowBlocks[bid]);
    if (!row) continue;
    const cells = colIds.map(cid => propText(row.properties?.[cid]).replace(/\n/g, ' ').replace(/\|/g, '\\|'));
    lines.push(`| ${cells.join(' | ')} |`);
  }
  return lines.join('\n') + '\n';
}

// Every file this page points at: file/image blocks plus attachment links
// living inside rich text (database row properties keep their files there).
function collectFileRefs(rm) {
  const refs = [];
  const seen = new Set();
  const add = (id, source) => {
    if (!source || seen.has(source)) return;
    seen.add(source);
    refs.push({ id, source });
  };
  for (const bid in rm.block) {
    const b = unwrap(rm.block[bid]);
    if (!b) continue;
    if (['image', 'file', 'pdf', 'video', 'audio'].includes(b.type)) add(bid, b.properties?.source?.[0]?.[0]);
    for (const key in b.properties || {}) {
      for (const seg of b.properties[key] || []) {
        for (const f of seg[1] || []) if (f[0] === 'a' && ATTACHMENT.test(f[1] || '')) add(bid, f[1]);
      }
    }
  }
  return refs;
}

// Download attachments next to the markdown; signed Notion URLs expire, so a
// document that only links them is empty a few days later.
async function downloadAssets(page, rm, dir) {
  const refs = collectFileRefs(rm);
  if (!refs.length) return { map: {}, saved: 0, skipped: [] };

  let signed = [];
  try { signed = await fetchSignedUrls(page, refs); } catch { /* fall back to raw urls */ }

  const map = {};
  const skipped = [];
  let saved = 0;
  fs.mkdirSync(dir, { recursive: true });

  for (let i = 0; i < refs.length; i++) {
    const { source } = refs[i];
    const url = signed[i] || (/^https?:/.test(source) ? source : null);
    if (!url) continue;
    const rawName = decodeURIComponent((source.split('?')[0].split('/').pop() || 'file').replace(/^.*:/, ''));
    if (!WITH_MEDIA && /\.(mov|mp4|m4v|avi|webm|mkv|mp3|wav|m4a)$/i.test(rawName)) {
      skipped.push(`${rawName} (media, set NOTION_MEDIA=1)`);
      continue;
    }
    try {
      const resp = await page.context().request.get(url, { timeout: 180000 });
      if (!resp.ok()) throw new Error('HTTP ' + resp.status());
      const buf = await resp.body();
      if (buf.length > MAX_MB * 1024 * 1024) {
        skipped.push(`${rawName} (${(buf.length / 1048576).toFixed(1)}MB > NOTION_MAX_MB)`);
        continue;
      }
      let name = safeName(rawName);
      if (!path.extname(name)) name += '.bin';
      let file = path.join(dir, name);
      let n = 2;
      while (fs.existsSync(file) && fs.statSync(file).size !== buf.length) file = path.join(dir, `${n++}_${name}`);
      fs.writeFileSync(file, buf);
      map[source] = path.relative(OUT, file).split(path.sep).join('/');
      saved++;
    } catch (e) {
      skipped.push(`${rawName} (${e.message})`);
    }
  }
  return { map, saved, skipped };
}

async function downloadPage(page, url, idx, total) {
  const pid = idFromUrl(url);
  if (!pid) { log(`[${idx}/${total}] SKIP (no id): ${url}`); return; }

  await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 45000 });
  await page.waitForTimeout(2500);

  const { rm, spaceId: chunkSpaceId } = await fetchRecordMap(page, pid);
  const root = unwrap(rm.block[pid]);
  if (!root) { log(`[${idx}/${total}] FAIL no root block: ${url}`); return; }

  RM = rm;
  BASE = url.split('#')[0];
  ASSETS = {};
  COMMENTS = [];
  COMMENT_SEEN = new Set();
  CNUM = 0;

  const title = rich(root.properties?.title) || pid;
  const safe = title.replace(/[/\\?%*:|"<>]/g, '-').replace(/\s+/g, ' ').trim().slice(0, 120) || pid;

  // Resolve any embedded collection views into markdown tables
  const collections = {};
  const spaceId = chunkSpaceId || root.space_id || rm.block[pid]?.spaceId;
  for (const bid in rm.block) {
    const b = unwrap(rm.block[bid]);
    if (!b || !['collection_view', 'collection_view_page'].includes(b.type)) continue;
    const colId = b.collection_id;
    const cvId = (b.view_ids || [])[0];
    if (!colId || !cvId) continue;
    const key = `${colId}|${cvId}`;
    if (collections[key]) continue;
    try {
      const qr = await fetchCollectionRows(page, colId, cvId, spaceId);
      const colWrap = rm.collection?.[colId];
      if (colWrap && qr) collections[key] = renderCollection(colWrap, qr, rm);
    } catch (e) { /* ignore one view */ }
  }

  let assets = { map: {}, saved: 0, skipped: [] };
  if (!NO_ASSETS) assets = await downloadAssets(page, rm, path.join(OUT, 'assets', safe));
  ASSETS = assets.map;

  // If the page itself IS a database page, its own row properties are useful
  const propLines = [];
  const parentColId = root.parent_table === 'collection' ? root.parent_id : null;
  if (parentColId && rm.collection?.[parentColId]) {
    const schema = unwrap(rm.collection[parentColId])?.schema || {};
    for (const cid in schema) {
      if (schema[cid].type === 'title') continue;
      const v = propText(root.properties?.[cid]);
      if (v) propLines.push(`- **${schema[cid].name}**: ${v}`);
    }
  }

  const pageRef = commentRef(root, title);
  const body = renderBlocks(root.content, rm, 0, collections, new Set([pid]));

  // name is only known now, so comment references are patched in at the end
  const commentsName = `${safe}.comments.md`;
  const fix = (s) => s.split('COMMENTS_FILE').join(encodeURI(commentsName));

  const md = [
    `# ${title}`,
    '',
    `> Source: ${url}`,
    `> Extracted: ${new Date().toISOString().slice(0, 16).replace('T', ' ')} UTC · ${Object.keys(rm.block).length} blocks · ${assets.saved} files`,
    ...(CNUM ? [`> 💬 ${CNUM} comments in [${commentsName}](${encodeURI(commentsName)}) — every commented block below links into it.`] : []),
    ...(assets.skipped.length ? [`> ⚠️ not downloaded: ${assets.skipped.join(', ')}`] : []),
    '',
    ...(pageRef ? [`> ${pageRef}`, ''] : []),
    ...(propLines.length ? ['## Properties', '', ...propLines, ''] : []),
    body
  ].join('\n');

  let file = path.join(OUT, `${safe}.md`);
  let n = 2;
  while (fs.existsSync(file)) { file = path.join(OUT, `${safe} (${n++}).md`); }
  fs.writeFileSync(file, fix(md), 'utf8');

  if (CNUM) {
    const cmd = [
      `# Comments — ${title}`,
      '',
      `> Source: ${url}`,
      `> ${CNUM} comments · body: [${safe}.md](${encodeURI(safe + '.md')})`,
      '',
      ...COMMENTS
    ].join('\n');
    fs.writeFileSync(path.join(OUT, commentsName), fix(cmd), 'utf8');
  }
  if (WITH_RAW) fs.writeFileSync(path.join(OUT, `${safe}.raw.json`), JSON.stringify(rm), 'utf8');

  log(`[${idx}/${total}] OK  ${Math.round(md.length/1024)}KB  ${CNUM} comments  ${assets.saved} files  ${file}`);
}

export { rich, renderBlocks, commentRef, setPageContext };

// skipped when imported by the self-check
if (!process.env.NOTION_SELFTEST) {
  const URLS = fs.readFileSync(URLS_FILE, 'utf8').split('\n').map(s => s.trim()).filter(Boolean);
  fs.writeFileSync(LOG, '');
  fs.mkdirSync(OUT, { recursive: true });
  log(`URLs: ${URLS.length}`);

  const { chromium } = await import('playwright-core');
  const browser = await chromium.connectOverCDP(`http://127.0.0.1:${PORT}`);
  const ctx = browser.contexts()[0];
  const page = await ctx.newPage();

  let cur = page;
  for (let i = 0; i < URLS.length; i++) {
    // recycle the tab periodically: Notion leaks memory and crashes the renderer
    if (i > 0 && i % 5 === 0) {
      try { await cur.close(); } catch {}
      cur = await ctx.newPage();
    }
    let done = false;
    for (let attempt = 1; attempt <= 3 && !done; attempt++) {
      try {
        await downloadPage(cur, URLS[i], i + 1, URLS.length);
        done = true;
      } catch (e) {
        log(`[${i+1}/${URLS.length}] attempt ${attempt} failed: ${e.message}`);
        try { await cur.close(); } catch {}
        cur = await ctx.newPage();
      }
    }
    if (!done) log(`[${i+1}/${URLS.length}] GAVE UP ${URLS[i]}`);
  }
  try { await cur.close(); } catch {}
  log('DONE');
  process.exit(0);
}
