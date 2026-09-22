// Output contract shared by every source: a body document, a numbered
// comments document beside it, and downloaded attachments. The point is
// traceability - each claim in the body can be walked back to the comment or
// the file it came from, and from there to the original page.
import fs from 'fs';
import path from 'path';

export const safeName = (s) =>
  (s || 'file').replace(/[/\\?%*:|"<>]/g, '_').replace(/\s+/g, '_').slice(0, 120);

export const docName = (s, fallback) =>
  (s || '').replace(/[/\\?%*:|"<>]/g, '-').replace(/\s+/g, ' ').trim().slice(0, 120) || fallback;

export const stamp = (t) =>
  t ? new Date(t).toISOString().replace('T', ' ').slice(0, 16) : '';

// The body is written before its comments file has a name, so references are
// laid down as this placeholder and patched in at write time.
const PLACEHOLDER = 'COMMENTS_FILE';

// Collects comment threads in document order, numbering them #1..#n so the
// body can point at an exact comment and the reader can find it.
export function commentBook() {
  const docs = [];
  let n = 0;
  return {
    get count() { return n; },
    get docs() { return docs; },
    // items: [{ who, when, body, link }] -> the reference line for the body
    thread({ on, link, items, note }) {
      const real = items.filter(Boolean);
      if (!real.length) return '';
      const nums = [];
      const rendered = real.map((it) => {
        const k = ++n;
        nums.push(k);
        const head = `#${k} — ${it.who}${it.when ? ` · ${it.when}` : ''}${it.link ? ` · [↗](${it.link})` : ''}`;
        return `### <a id="c-${k}"></a>${head}\n\n${it.body || '_(empty)_'}`;
      });
      docs.push([
        `## On: ${on || '(top)'}${note ? ` · _${note}_` : ''}${link ? ` · [↗](${link})` : ''}`,
        '', rendered.join('\n\n'), ''
      ].join('\n'));
      const label = nums.length === 1 ? `#${nums[0]}` : `#${nums[0]}–#${nums[nums.length - 1]}`;
      return `💬 ${nums.length} comment → [${label}](${PLACEHOLDER}#c-${nums[0]})`;
    }
  };
}

// Writes <name>.md and, when there are any, <name>.comments.md next to it.
export function writeDoc({ out, name, title, source, meta = [], body, book, suffix = [] }) {
  fs.mkdirSync(out, { recursive: true });
  const commentsName = `${name}.comments.md`;
  const patch = (s) => s.split(PLACEHOLDER).join(encodeURI(commentsName));
  const count = book ? book.count : 0;

  const md = [
    `# ${title}`,
    '',
    `> Source: ${source}`,
    ...meta.map((m) => `> ${m}`),
    ...(count ? [`> 💬 ${count} comments in [${commentsName}](${encodeURI(commentsName)}) — every commented item below links into it.`] : []),
    '',
    body,
    ...suffix
  ].join('\n');

  let file = path.join(out, `${name}.md`);
  let n = 2;
  while (fs.existsSync(file)) file = path.join(out, `${name} (${n++}).md`);
  fs.writeFileSync(file, patch(md), 'utf8');

  if (count) {
    fs.writeFileSync(path.join(out, commentsName), patch([
      `# Comments — ${title}`,
      '',
      `> Source: ${source}`,
      `> ${count} comments · body: [${name}.md](${encodeURI(name + '.md')})`,
      '',
      ...book.docs
    ].join('\n')), 'utf8');
  }
  return { file, comments: count ? path.join(out, commentsName) : null };
}

const MEDIA = /\.(mov|mp4|m4v|avi|webm|mkv|mp3|wav|m4a)$/i;

// Attachments are copied rather than linked: the URLs these services hand out
// are signed or session-bound, so a document that only links them goes empty.
export async function saveAsset(request, url, dir, opts = {}) {
  const { name, maxMb = 30, media = false, headers } = opts;
  const raw = name || decodeURIComponent((url.split('?')[0].split('/').pop() || 'file').replace(/^.*:/, ''));
  if (!media && MEDIA.test(raw)) return { skipped: `${raw} (media, set *_MEDIA=1)` };
  try {
    const resp = await request.get(url, { timeout: 180000, ...(headers ? { headers } : {}) });
    if (!resp.ok()) throw new Error('HTTP ' + resp.status());
    const buf = await resp.body();
    if (buf.length > maxMb * 1024 * 1024) {
      return { skipped: `${raw} (${(buf.length / 1048576).toFixed(1)}MB > limit)` };
    }
    fs.mkdirSync(dir, { recursive: true });
    let file = path.join(dir, safeName(raw));
    if (!path.extname(file)) file += '.bin';
    let n = 2;
    while (fs.existsSync(file) && fs.statSync(file).size !== buf.length) {
      file = path.join(dir, `${n++}_${safeName(raw)}`);
    }
    fs.writeFileSync(file, buf);
    return { file, name: raw };
  } catch (e) {
    return { skipped: `${raw} (${e.message})` };
  }
}

// Sources take either a file of URLs or a single URL, so a one-off link does
// not need a file made for it.
export function readUrls(arg) {
  if (arg && fs.existsSync(arg) && fs.statSync(arg).isFile()) {
    return fs.readFileSync(arg, 'utf8').split('\n').map((s) => s.trim()).filter(Boolean);
  }
  return arg ? [arg] : [];
}
