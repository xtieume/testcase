// self-check for the pure renderers: node test-download.mjs
process.env.NOTION_SELFTEST = '1';
const { rich, renderBlocks, commentRef, setPageContext } = await import('./download.mjs');
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

const ctx = setPageContext(rm, 'https://notion.so/doc', { 'https://s3.amazonaws.com/x/wire.png': 'assets/doc/wire.png' });

// person + page mentions resolve to names, not @user / [[page]]
assert.strictEqual(rich([['‣', [['u', 'u-1']]]]), '@Tamami Sato');
assert.strictEqual(rich([['‣', [['p', 'p-9']]]]), '[Linked Page](https://www.notion.so/p9)');

const out = renderBlocks(['h-1', 'i-1'], rm, 0, {}, new Set());

// comment thread is numbered, pulled out, and linked from the body
assert.match(out, /💬 2 comment → \[#1–#2\]\(COMMENTS_FILE#c-1\)/);
assert.strictEqual(ctx.comments.length, 1);
assert.match(ctx.comments[0], /#1 — Tamami Sato/);
assert.match(ctx.comments[0], /ty gia cuoi thang/);
assert.match(ctx.comments[0], /\?d=d1\)/);

// heading carries a deep link back to the exact block
assert.match(out, /## Requirements \[↗\]\(https:\/\/notion\.so\/doc#h1\)/);

// image points at the downloaded copy, not the expiring signed url
assert.match(out, /!\[\]\(assets\/doc\/wire\.png\)/);

// a second call resets numbering instead of continuing from the last page
setPageContext(rm, 'https://notion.so/doc', {});
assert.match(commentRef({ discussions: ['d-1'] }, 'x'), /#1–#2/);

console.log('ok');
