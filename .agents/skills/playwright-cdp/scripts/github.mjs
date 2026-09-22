import { execFileSync } from 'child_process';
import fs from 'fs';
import path from 'path';
import { commentBook, writeDoc, docName, readUrls, stamp, safeName } from './doc.mjs';

// usage: node github.mjs <url|urls-file> <out-dir>
// No browser: gh already holds the credentials, so this runs anywhere.
const URLS = readUrls(process.argv[2]);
const OUT = process.argv[3] || './github-docs';
const MAX_MB = Number(process.env.GH_MAX_MB || 30);

const gh = (args) => JSON.parse(execFileSync('gh', args, { encoding: 'utf8', maxBuffer: 64 * 1024 * 1024 }));

function parseUrl(u) {
  const m = u.match(/github\.com\/([^/]+)\/([^/]+)\/(pull|issues)\/(\d+)/);
  if (!m) throw new Error('not a PR or issue URL: ' + u);
  return { repo: `${m[1]}/${m[2]}`, kind: m[3] === 'pull' ? 'pr' : 'issue', number: m[4] };
}

// Attachments are links in the markdown; private ones need the gh token.
function saveAttachments(md, dir, source) {
  const urls = [...md.matchAll(/!?\[[^\]]*\]\((https:\/\/[^)\s]*(?:user-images\.githubusercontent\.com|github\.com\/user-attachments\/assets)[^)\s]*)\)/g)]
    .map((m) => m[1]);
  const map = {};
  const skipped = [];
  for (const url of new Set(urls)) {
    const name = safeName(decodeURIComponent(url.split('?')[0].split('/').pop() || 'file'));
    const file = path.join(dir, name);
    try {
      fs.mkdirSync(dir, { recursive: true });
      execFileSync('gh', ['api', '--method', 'GET', url.replace('https://github.com/', ''), '--cache', '0'],
        { stdio: 'ignore' });
    } catch { /* gh api cannot serve these; fall back to curl with the token */ }
    try {
      const token = execFileSync('gh', ['auth', 'token'], { encoding: 'utf8' }).trim();
      execFileSync('curl', ['-sL', '--max-filesize', String(MAX_MB * 1024 * 1024),
        '-H', `Authorization: Bearer ${token}`, '-o', file, url], { stdio: 'ignore' });
      if (fs.existsSync(file) && fs.statSync(file).size > 0) {
        map[url] = path.relative(OUT, file).split(path.sep).join('/');
      } else {
        fs.rmSync(file, { force: true });
        skipped.push(name);
      }
    } catch { skipped.push(name); }
  }
  let out = md;
  for (const [url, local] of Object.entries(map)) out = out.split(url).join(local);
  return { md: out, saved: Object.keys(map).length, skipped, source };
}

function extract(url) {
  const { repo, kind, number } = parseUrl(url);
  const fields = kind === 'pr'
    ? 'title,body,author,createdAt,state,comments,reviews,files,baseRefName,headRefName'
    : 'title,body,author,createdAt,state,comments,labels';
  const d = gh([kind, 'view', number, '--repo', repo, '--json', fields]);

  // Comments left on a line of the diff are a separate API and are usually
  // where the code-level decisions get made.
  const lineComments = kind === 'pr'
    ? gh(['api', `repos/${repo}/pulls/${number}/comments`, '--paginate']).map((c) => ({
        at: c.created_at, who: c.user?.login || 'unknown', link: c.html_url, body: c.body,
        on: `${c.path}${c.line ? ':' + c.line : ''}`
      }))
    : [];

  const name = docName(`${repo.split('/')[1]} ${kind} ${number} ${d.title}`, `${kind}-${number}`);
  const assetDir = path.join(OUT, 'assets', name);
  const book = commentBook();

  // A review carries a verdict plus its own line comments; both decide scope,
  // so they sit in the same numbered stream as plain comments, in time order.
  const entries = [
    ...(d.comments || []).map((c) => ({
      at: c.createdAt, who: c.author?.login || 'unknown', link: c.url, body: c.body, on: 'Conversation'
    })),
    ...(d.reviews || []).map((r) => ({
      at: r.submittedAt, who: r.author?.login || 'unknown', link: r.url,
      body: [r.state && `**${r.state}**`, r.body].filter(Boolean).join('\n\n'), on: 'Review'
    }))
    , ...lineComments
  ].filter((e) => e.body || e.on === 'Review').sort((a, b) => String(a.at).localeCompare(String(b.at)));

  // grouped by where they were left, each group kept in time order
  const refs = {};
  for (const group of [...new Set(entries.map((e) => e.on))]) {
    const items = entries.filter((e) => e.on === group);
    refs[group] = book.thread({
      on: group, items: items.map((e) => ({ who: e.who, when: stamp(e.at), link: e.link, body: e.body }))
    });
  }

  const changed = (d.files || []).map((f) => `- \`${f.path}\` (+${f.additions} −${f.deletions})`);
  const body = [
    ...(kind === 'pr' ? [`**${d.state}** · \`${d.headRefName}\` → \`${d.baseRefName}\` · by ${d.author?.login}`, ''] : []),
    ...(kind === 'issue' ? [`**${d.state}** · by ${d.author?.login} · ${(d.labels || []).map((l) => l.name).join(', ')}`, ''] : []),
    d.body || '_(no description)_',
    ...(Object.values(refs).length ? ['', ...Object.values(refs).map((r) => `> ${r}`)] : []),
    ...(changed.length ? ['', '## Changed files', '', ...changed] : [])
  ].join('\n');

  const withAssets = saveAttachments(body, assetDir, url);
  const commentsWithAssets = book.docs.map((doc) => saveAttachments(doc, assetDir, url));
  book.docs.length = 0;
  book.docs.push(...commentsWithAssets.map((c) => c.md));
  const saved = withAssets.saved + commentsWithAssets.reduce((n, c) => n + c.saved, 0);
  const skipped = [...withAssets.skipped, ...commentsWithAssets.flatMap((c) => c.skipped)];

  const { file } = writeDoc({
    out: OUT, name, title: `${d.title} (${repo}#${number})`, source: url, book,
    meta: [
      `Extracted: ${new Date().toISOString().slice(0, 16).replace('T', ' ')} UTC · ${saved} files`,
      ...(skipped.length ? [`⚠️ not downloaded: ${skipped.join(', ')}`] : [])
    ],
    body: withAssets.md
  });
  console.log(`OK  ${book.count} comments  ${saved} files  ${file}`);
}

if (!URLS.length) { console.error('usage: node github.mjs <url|urls-file> <out-dir>'); process.exit(1); }
try { execFileSync('gh', ['auth', 'status'], { stdio: 'ignore' }); }
catch { console.error('gh is not authenticated: run `gh auth login`'); process.exit(1); }
for (const url of URLS) {
  try { extract(url); } catch (e) { console.error(`FAIL ${url}: ${e.message}`); }
}
