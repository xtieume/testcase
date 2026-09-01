import { chromium } from 'playwright';
import fs from 'fs';
import path from 'path';

// usage: node download.mjs <urls-file> <out-dir> [cdp-port]
const URLS_FILE = process.argv[2] || './urls.txt';
const OUT = process.argv[3] || './notion-docs';
const PORT = process.argv[4] || '9222';
const LOG = process.env.NOTION_DL_LOG || '/tmp/notion_dl.log';
const log = (m) => { fs.appendFileSync(LOG, m + '\n'); console.log(m); };

const URLS = fs.readFileSync(URLS_FILE, 'utf8').split('\n').map(s => s.trim()).filter(Boolean);

function dashId(raw) {
  const hex = raw.replace(/-/g, '');
  return `${hex.slice(0,8)}-${hex.slice(8,12)}-${hex.slice(12,16)}-${hex.slice(16,20)}-${hex.slice(20,32)}`;
}
function idFromUrl(u) {
  const m = u.match(/([a-f0-9]{32})/i);
  return m ? dashId(m[1]) : null;
}

// Fetch every block of a page (recursive chunks), run inside the browser
async function fetchRecordMap(page, pageId) {
  return page.evaluate(async (pid) => {
    const merged = { block: {}, collection: {}, collection_view: {} };
    let cursor = { stack: [] };
    for (let i = 0; i < 40; i++) {
      const r = await fetch('/api/v3/loadPageChunk', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pageId: pid, limit: 100, cursor, chunkNumber: i, verticalColumns: false })
      });
      if (r.status !== 200) break;
      const j = await r.json();
      const rm = j.recordMap || {};
      for (const t of ['block', 'collection', 'collection_view']) {
        Object.assign(merged[t], rm[t] || {});
      }
      if (!j.cursor || !j.cursor.stack || j.cursor.stack.length === 0) break;
      cursor = j.cursor;
    }
    return merged;
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

const unwrap = (w) => w?.value?.value || w?.value || null;

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
        if (f[0] === 'p') return '[[page]]';
        if (f[0] === 'u') return '@user';
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
    if (link) t = `[${t}](${link})`;
    return t;
  }).join('');
}

const propText = (v) => Array.isArray(v) ? rich(v) : (v == null ? '' : String(v));

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

    if (t !== 'numbered_list') numCounter = 0;

    switch (t) {
      case 'header':            out.push(`${ind}## ${txt}\n`); break;
      case 'sub_header':        out.push(`${ind}### ${txt}\n`); break;
      case 'sub_sub_header':    out.push(`${ind}#### ${txt}\n`); break;
      case 'text':              out.push(txt ? `${ind}${txt}\n` : ''); break;
      case 'bulleted_list':     out.push(`${ind}- ${txt}`); break;
      case 'numbered_list':     numCounter++; out.push(`${ind}${numCounter}. ${txt}`); break;
      case 'to_do':             out.push(`${ind}- [${b.properties?.checked?.[0]?.[0] === 'Yes' ? 'x' : ' '}] ${txt}`); break;
      case 'toggle':            out.push(`${ind}<details><summary>${txt}</summary>\n`); break;
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
        out.push(`${ind}![${cap}](${src})\n`);
        break;
      }
      case 'file': case 'pdf': case 'video': case 'audio': {
        const src = b.properties?.source?.[0]?.[0] || '';
        out.push(`${ind}[${t}: ${rich(b.properties?.title) || src}](${src})\n`);
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

async function downloadPage(page, url, idx, total) {
  const pid = idFromUrl(url);
  if (!pid) { log(`[${idx}/${total}] SKIP (no id): ${url}`); return; }

  await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 45000 });
  await page.waitForTimeout(2500);

  const rm = await fetchRecordMap(page, pid);
  const root = unwrap(rm.block[pid]);
  if (!root) { log(`[${idx}/${total}] FAIL no root block: ${url}`); return; }

  const title = rich(root.properties?.title) || pid;

  // Resolve any embedded collection views into markdown tables
  const collections = {};
  const spaceId = rm.block[pid]?.spaceId;
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

  const body = renderBlocks(root.content, rm, 0, collections, new Set([pid]));

  const md = [
    `# ${title}`,
    '',
    `> Source: ${url}`,
    '',
    ...(propLines.length ? ['## Properties', '', ...propLines, ''] : []),
    body
  ].join('\n');

  const safe = title.replace(/[/\\?%*:|"<>]/g, '-').replace(/\s+/g, ' ').trim().slice(0, 120) || pid;
  let file = path.join(OUT, `${safe}.md`);
  let n = 2;
  while (fs.existsSync(file)) { file = path.join(OUT, `${safe} (${n++}).md`); }
  fs.writeFileSync(file, md, 'utf8');
  log(`[${idx}/${total}] OK  ${Math.round(md.length/1024)}KB  ${file}`);
}

fs.writeFileSync(LOG, '');
fs.mkdirSync(OUT, { recursive: true });
log(`URLs: ${URLS.length}`);

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
