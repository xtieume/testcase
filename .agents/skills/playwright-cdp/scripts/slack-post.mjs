import fs from 'fs';
import { connectCdp } from './doc.mjs';
import { parseUrl, readToken, slackApi, when } from './slack-api.mjs';

// usage: node slack-post.mjs <url> <text | - | @file> [--send] [cdp-port]
//   url pointing at a message or thread -> replies in that thread
//   url pointing at a channel           -> posts a new message in the channel
// Without --send this only shows what would be posted and where. Posting is
// not undoable for the people who get the notification, so the default is to
// look before sending.
const args = process.argv.slice(2);
const SEND = args.includes('--send');
const rest = args.filter((a) => a !== '--send');
const [URL_ARG, TEXT_ARG, PORT = '9222'] = rest;

if (!URL_ARG || !TEXT_ARG) {
  console.error('usage: node slack-post.mjs <url> <text | - | @file> [--send] [cdp-port]');
  process.exit(1);
}

const text = TEXT_ARG === '-' ? fs.readFileSync(0, 'utf8')
  : TEXT_ARG.startsWith('@') ? fs.readFileSync(TEXT_ARG.slice(1), 'utf8')
  : TEXT_ARG;
if (!text.trim()) { console.error('refusing to post an empty message'); process.exit(1); }

const { channel, ts } = parseUrl(URL_ARG);
const browser = await connectCdp(PORT);
const page = await browser.contexts()[0].newPage();
try {
  await page.goto(URL_ARG, { waitUntil: 'domcontentloaded', timeout: 60000 });
  await page.waitForTimeout(5000);
  const cfg = await readToken(page);
  if (cfg.error) throw new Error(cfg.error + ' — run agent-browser.sh --headed and sign in to Slack');

  const host = `https://${cfg.domain}.slack.com`;
  if (!page.url().startsWith(host)) {
    await page.goto(`${host}/archives/${channel}`, { waitUntil: 'domcontentloaded', timeout: 60000 });
    await page.waitForTimeout(4000);
  }

  // name the destination in full, so a wrong channel is caught before sending
  const info = await slackApi(page, cfg.token, 'conversations.info', { channel }).catch(() => null);
  const c = info?.channel;
  // a DM has no name, and a raw D0... id tells the reader nothing
  let where = c?.name ? `#${c.name}` : channel;
  if (c?.is_im) {
    const u = await slackApi(page, cfg.token, 'users.info', { user: c.user }).catch(() => null);
    const who = u?.user?.profile?.display_name || u?.user?.profile?.real_name || u?.user?.name || c.user;
    where = `DM with @${who}`;
  }
  where += ts ? ` · reply in thread ${when(ts)}` : ' · new message';
  console.log(`to:   ${cfg.name} ${where}`);
  console.log(`text: ${text.trim().split('\n').map((l) => '  ' + l).join('\n').trim()}`);

  if (!SEND) {
    console.log('\nDRY RUN — nothing was posted. Add --send to actually post.');
  } else {
    const res = await slackApi(page, cfg.token, 'chat.postMessage', {
      channel, text, ...(ts ? { thread_ts: ts } : {})
    });
    console.log(`\nPOSTED ${host}/archives/${channel}/p${String(res.ts).replace('.', '')}`);
  }
} catch (e) {
  console.error('FAIL:', e.message);
  process.exitCode = 1;
} finally {
  await page.close().catch(() => {});
  process.exit(process.exitCode || 0);
}
