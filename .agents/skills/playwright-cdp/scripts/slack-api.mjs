// Slack access shared by the read and write scripts: which conversation a link
// points at, and the web client's own token, which every call needs alongside
// the session cookie.
// channel id and, when the link points at one message, its timestamp
export function parseUrl(u) {
  const url = new URL(u);
  let channel = null, ts = null;
  const arch = url.pathname.match(/\/archives\/([A-Z0-9]+)(?:\/p(\d{10})(\d{6}))?/i);
  if (arch) { channel = arch[1]; if (arch[2]) ts = `${arch[2]}.${arch[3]}`; }
  const thread = url.pathname.match(/\/client\/[A-Z0-9]+\/([A-Z0-9]+)(?:\/thread\/[A-Z0-9]+-(\d+\.\d+))?/i);
  if (thread) { channel = channel || thread[1]; ts = ts || thread[2] || null; }
  ts = url.searchParams.get('thread_ts') || ts;
  channel = url.searchParams.get('cid') || channel;
  if (!channel) throw new Error('no channel id in URL: ' + u);
  return { channel, ts };
}

export const when = (ts) => new Date(Number(String(ts).split('.')[0]) * 1000).toISOString().replace('T', ' ').slice(0, 16);

// The web client's own token, which the in-page API calls need alongside the
// session cookie. It only exists on the app.slack.com origin - a /archives/
// link is a stub page that redirects to the desktop app.
export async function readToken(page) {
  const read = () => page.evaluate(() => {
    const raw = localStorage.getItem('localConfig_v2');
    if (!raw) return { error: 'no localConfig_v2 (not signed in to Slack in this profile?)' };
    const cfg = JSON.parse(raw);
    const teams = cfg.teams || {};
    const fromUrl = (location.pathname.match(/\/client\/(T[A-Z0-9]+)/i) || [])[1];
    const id = (fromUrl && teams[fromUrl] && fromUrl) || cfg.lastActiveTeamId || Object.keys(teams)[0];
    const team = teams[id];
    if (!team?.token) return { error: 'no token for team ' + id };
    return { token: team.token, domain: team.domain, name: team.name };
  });
  let cfg = await read();
  if (cfg.error && !page.url().startsWith('https://app.slack.com/')) {
    await page.goto('https://app.slack.com/client', { waitUntil: 'domcontentloaded', timeout: 90000 });
    await page.waitForTimeout(10000);
    cfg = await read();
  }
  return cfg;
}

// One authenticated call, made from inside the page so the session cookie rides
// along. Slack's web API takes the token as a form field, not a header.
export async function slackApi(page, token, method, params) {
  return page.evaluate(async ({ token, method, params }) => {
    const fd = new FormData();
    fd.append('token', token);
    for (const [k, v] of Object.entries(params)) fd.append(k, String(v));
    const r = await fetch('/api/' + method, { method: 'POST', body: fd, credentials: 'include' });
    const j = await r.json();
    if (!j.ok) throw new Error(method + ' -> ' + (j.error || 'unknown'));
    return j;
  }, { token, method, params });
}
