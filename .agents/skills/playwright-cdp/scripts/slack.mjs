import path from 'path';
import { commentBook, writeDoc, saveAsset, docName, readUrls, connectCdp } from './doc.mjs';
import { parseUrl, readToken, when } from './slack-api.mjs';

// usage: node slack.mjs <url|urls-file> <out-dir> [cdp-port]
// Accepts a channel link, a message permalink, or a thread link.
const URLS = readUrls(process.argv[2]);
const OUT = process.argv[3] || './slack-docs';
const PORT = process.argv[4] || '9222';
const LIMIT = Number(process.env.SLACK_LIMIT || 200);
const MAX_MB = Number(process.env.SLACK_MAX_MB || 30);
const WITH_MEDIA = process.env.SLACK_MEDIA === '1';

// Slack virtual-scrolls, so the DOM only ever holds a few dozen messages.
// These calls run in the page: same origin, session cookie attached.
async function fetchConversation(page, { token, channel, ts, limit }) {
  return page.evaluate(async ({ token, channel, ts, limit }) => {
    const api = async (method, params) => {
      const fd = new FormData();
      fd.append('token', token);
      for (const [k, v] of Object.entries(params)) fd.append(k, String(v));
      const r = await fetch('/api/' + method, { method: 'POST', body: fd, credentials: 'include' });
      const j = await r.json();
      if (!j.ok) throw new Error(method + ' -> ' + (j.error || 'unknown'));
      return j;
    };

    const info = await api('conversations.info', { channel }).catch((e) => ({ error: String(e.message) }));
    let messages = [];
    const threads = {};

    if (ts) {
      const r = await api('conversations.replies', { channel, ts, limit: 1000 });
      messages = r.messages.slice(0, 1);
      threads[ts] = r.messages.slice(1);
    } else {
      const h = await api('conversations.history', { channel, limit });
      messages = (h.messages || []).slice().reverse(); // oldest first
      let pulled = 0;
      for (const m of messages) {
        if (!m.reply_count || pulled >= 60) continue;
        pulled++;
        try {
          const r = await api('conversations.replies', { channel, ts: m.ts, limit: 1000 });
          threads[m.ts] = r.messages.slice(1);
        } catch (e) {
          threads[m.ts] = [{ text: `_(thread unavailable: ${e.message})_`, user: '' }];
        }
      }
    }

    const ids = new Set();
    const scan = (m) => {
      if (m.user) ids.add(m.user);
      (m.text || '').replace(/<@([UW][A-Z0-9]+)>/g, (_, u) => ids.add(u));
    };
    messages.forEach(scan);
    Object.values(threads).flat().forEach(scan);

    const users = {};
    for (const id of ids) {
      try {
        const u = await api('users.info', { user: id });
        users[id] = u.user.profile.display_name || u.user.profile.real_name || u.user.name;
      } catch { users[id] = id; }
    }
    return { info: info.channel || null, infoError: info.error || null, messages, threads, users };
  }, { token, channel, ts, limit });
}

async function extract(page, url, out) {
  const { channel, ts } = parseUrl(url);
  await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 60000 });
  await page.waitForTimeout(6000);

  const cfg = await readToken(page);
  if (cfg.error) throw new Error(cfg.error + ' — run agent-browser.sh --headed and sign in to Slack');

  const host = `https://${cfg.domain}.slack.com`;
  if (!page.url().startsWith(host)) {
    await page.goto(`${host}/archives/${channel}`, { waitUntil: 'domcontentloaded', timeout: 60000 });
    await page.waitForTimeout(5000);
  }

  const data = await fetchConversation(page, { token: cfg.token, channel, ts, limit: LIMIT });
  const name = docName(`slack ${data.info?.name || channel}${ts ? ' ' + ts : ''}`, channel);
  const title = `#${data.info?.name || channel}${ts ? ` — thread ${when(ts)}` : ` — last ${LIMIT} messages`}`;

  // files live behind the session; the token goes in as a bearer header
  const files = {};
  const skipped = [];
  for (const m of [...data.messages, ...Object.values(data.threads).flat()]) {
    for (const f of m.files || []) {
      const src = f.url_private_download || f.url_private;
      if (!src || files[f.id]) continue;
      const r = await saveAsset(page.context().request, src, path.join(out, 'assets', name), {
        name: f.name || f.id, maxMb: MAX_MB, media: WITH_MEDIA,
        headers: { Authorization: 'Bearer ' + cfg.token }
      });
      if (r.skipped) { skipped.push(r.skipped); continue; }
      files[f.id] = { name: r.name, local: path.relative(out, r.file).split(path.sep).join('/') };
    }
  }

  const who = (id) => data.users[id] || id || 'unknown';
  const mrkdwn = (t) => (t || '')
    .replace(/<@([UW][A-Z0-9]+)>/g, (_, u) => '@' + who(u))
    .replace(/<#([CG][A-Z0-9]+)\|([^>]*)>/g, (_, c, n) => '#' + (n || c))
    .replace(/<!(here|channel|everyone)>/g, '@$1')
    .replace(/<(https?:\/\/[^|>]+)\|([^>]+)>/g, '[$2]($1)')
    .replace(/<(https?:\/\/[^>]+)>/g, '$1')
    .replace(/&gt;/g, '>').replace(/&lt;/g, '<').replace(/&amp;/g, '&')
    .replace(/\*([^*\n]+)\*/g, '**$1**');

  const attached = (m) => (m.files || []).map((f) => {
    const hit = files[f.id];
    if (!hit) return `📎 ${f.name || f.id} _(not downloaded)_`;
    return /\.(png|jpe?g|gif|webp)$/i.test(hit.name) ? `![${hit.name}](${hit.local})` : `📎 [${hit.name}](${hit.local})`;
  }).join('\n');

  const permalink = (mts, parent) =>
    `${host}/archives/${channel}/p${String(mts).replace('.', '')}` +
    (parent && parent !== mts ? `?thread_ts=${parent}&cid=${channel}` : '');

  const book = commentBook();
  const refs = {};
  for (const [parent, replies] of Object.entries(data.threads)) {
    const root = data.messages.find((m) => m.ts === parent);
    refs[parent] = book.thread({
      on: root ? `${who(root.user)} · ${when(parent)} — ${mrkdwn(root.text).split('\n')[0].slice(0, 120)}` : when(parent),
      link: permalink(parent),
      items: replies.map((r) => ({
        who: who(r.user), when: when(r.ts), link: permalink(r.ts, parent),
        body: [mrkdwn(r.text), attached(r)].filter(Boolean).join('\n\n')
      }))
    });
  }

  const body = data.messages.map((m) => [
    `### ${who(m.user)} · ${when(m.ts)} [↗](${permalink(m.ts)})`, '',
    mrkdwn(m.text),
    ...(attached(m) ? ['', attached(m)] : []),
    ...((m.reactions || []).length ? ['', m.reactions.map((r) => `:${r.name}: ${r.count}`).join('  ')] : []),
    ...(refs[m.ts] ? ['', `> ${refs[m.ts]}`] : [])
  ].join('\n')).join('\n\n---\n\n');

  const { file } = writeDoc({
    out, name, title, source: url, book,
    meta: [
      `Extracted: ${new Date().toISOString().slice(0, 16).replace('T', ' ')} UTC · ${data.messages.length} messages · ${Object.keys(files).length} files`,
      ...(data.infoError ? [`⚠️ channel info unavailable: ${data.infoError}`] : []),
      ...(skipped.length ? [`⚠️ not downloaded: ${skipped.join(', ')}`] : [])
    ],
    body
  });
  console.log(`OK  ${data.messages.length} messages  ${book.count} replies  ${Object.keys(files).length} files  ${file}`);
}

if (!URLS.length) { console.error('usage: node slack.mjs <url|urls-file> <out-dir> [cdp-port]'); process.exit(1); }
const browser = await connectCdp(PORT);
const ctx = browser.contexts()[0];
for (const url of URLS) {
  const page = await ctx.newPage();
  try { await extract(page, url, OUT); }
  catch (e) { console.error(`FAIL ${url}: ${e.message}`); }
  finally { await page.close().catch(() => {}); }
}
process.exit(0);
