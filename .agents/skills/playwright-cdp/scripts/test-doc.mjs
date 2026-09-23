// self-check for the pure renderers: node test-download.mjs
process.env.NOTION_SELFTEST = '1';
const { rich, renderBlocks, commentRef, setPageContext } = await import('./notion.mjs');
import assert from 'assert';

const B = (v) => ({ value: v });
const rm = {
  notion_user: { 'u-1': B({ id: 'u-1', name: 'Tamami Sato' }) },
  discussion: { 'd-1': B({ id: 'd-1', comments: ['c-1', 'c-2'], resolved: false }) },
  comment: {
    'c-1': B({ id: 'c-1', created_by_id: 'u-1', created_time: 1700000000000, text: [['spec chot: dung ty gia cuoi thang']] }),
    'c-2': B({ id: 'c-2', created_by_id: 'u-1', created_time: 1700000100000, text: [['ok']] }),
  },
  block: {
    'p-9': B({ id: 'p-9', type: 'page', properties: { title: [['Linked Page']] } }),
    'h-1': B({ id: 'h-1', type: 'header', properties: { title: [['Requirements']] }, discussions: ['d-1'], content: [] }),
    'i-1': B({ id: 'i-1', type: 'image', properties: { source: [['https://s3.amazonaws.com/x/wire.png']] } }),
  },
};

const book = setPageContext(rm, 'https://notion.so/doc', { 'https://s3.amazonaws.com/x/wire.png': 'assets/doc/wire.png' });

// person + page mentions resolve to names, not @user / [[page]]
assert.strictEqual(rich([['‣', [['u', 'u-1']]]]), '@Tamami Sato');
assert.strictEqual(rich([['‣', [['p', 'p-9']]]]), '[Linked Page](https://www.notion.so/p9)');

const out = renderBlocks(['h-1', 'i-1'], rm, 0, {}, new Set());

// comment thread is numbered, pulled out, and linked from the body
assert.match(out, /💬 2 comment → \[#1–#2\]\(COMMENTS_FILE#c-1\)/);
assert.strictEqual(book.count, 2);
assert.strictEqual(book.docs.length, 1);
assert.match(book.docs[0], /#1 — Tamami Sato/);
assert.match(book.docs[0], /ty gia cuoi thang/);
assert.match(book.docs[0], /\?d=d1\)/);

// relative in-page links are made absolute, or they break outside the app
assert.strictEqual(rich([['see', [['a', '/abc#def']]]]), '[see](https://www.notion.so/abc#def)');

// heading carries a deep link back to the exact block
assert.match(out, /## Requirements \[↗\]\(https:\/\/notion\.so\/doc#h1\)/);

// image points at the downloaded copy, not the expiring signed url
assert.match(out, /!\[\]\(assets\/doc\/wire\.png\)/);

// a second call resets numbering instead of continuing from the last page
setPageContext(rm, 'https://notion.so/doc', {});
assert.match(commentRef({ discussions: ['d-1'] }, 'x'), /#1–#2/);

console.log('ok');

// --- shared output contract (doc.mjs), used by all three sources ---
import os from 'os';
import fsp from 'fs';
import pathp from 'path';
const { commentBook, writeDoc } = await import('./doc.mjs');

const dir = fsp.mkdtempSync(pathp.join(os.tmpdir(), 'doc-test-'));
const bk = commentBook();
const r1 = bk.thread({ on: 'Section A', link: 'https://x/#a', items: [
  { who: 'ann', when: '2026-01-01 10:00', body: 'first' },
  { who: 'bo', when: '2026-01-01 11:00', body: 'second', link: 'https://x/#c2' },
] });
const r2 = bk.thread({ on: 'Section B', items: [{ who: 'ann', body: 'third' }] });

// numbering continues across threads, so a reference names one exact comment
assert.strictEqual(r1, '💬 2 comment → [#1–#2](COMMENTS_FILE#c-1)');
assert.strictEqual(r2, '💬 1 comment → [#3](COMMENTS_FILE#c-3)');
assert.strictEqual(bk.count, 3);

// an empty thread produces no reference and no section
assert.strictEqual(bk.thread({ on: 'C', items: [null, undefined] }), '');
assert.strictEqual(bk.docs.length, 2);

const w = writeDoc({ out: dir, name: 'Doc', title: 'Doc', source: 'https://x', book: bk, body: r1 });
const body = fsp.readFileSync(w.file, 'utf8');
const comments = fsp.readFileSync(w.comments, 'utf8');

// the placeholder is resolved to the real comments file, in both documents
assert.ok(!body.includes('COMMENTS_FILE') && !comments.includes('COMMENTS_FILE'));
assert.match(body, /\(Doc\.comments\.md#c-1\)/);
assert.match(comments, /<a id="c-3"><\/a>#3 — ann/);
assert.match(body, /💬 3 comments in \[Doc\.comments\.md\]/);

// no comments means no stray empty comments file
const w2 = writeDoc({ out: dir, name: 'Bare', title: 'Bare', source: 'https://x', book: commentBook(), body: 'x' });
assert.strictEqual(w2.comments, null);
assert.ok(!fsp.existsSync(pathp.join(dir, 'Bare.comments.md')));

fsp.rmSync(dir, { recursive: true, force: true });
console.log('ok (doc)');
