// Screenshot every scene/step of a profile with Playwright (node), logging console errors.
// usage: node tools/shot.mjs <profile> <outdir> [scene[/step] ...]   (no scenes = all countable scenes of the profile)
import { chromium } from 'playwright';
import fs from 'node:fs';
const [profile, outdir, ...only] = process.argv.slice(2);
fs.mkdirSync(outdir, { recursive: true });
const base = `http://127.0.0.1:8123/index.html?profile=${profile}`;
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1600, height: 900 }, deviceScaleFactor: 1 });
const errors = [];
page.on('console', m => { if (m.type() === 'error') errors.push(`[${m.type()}] ${m.text()}`); });
page.on('pageerror', e => errors.push(`[pageerror] ${e.message}`));
await page.goto(base, { waitUntil: 'load' });
await page.addStyleTag({ content: '#hint{display:none!important} *{transition:none!important;animation:none!important}' });
const list = only.length ? only.map(x => { const [id, st] = x.split('/'); return { id, st: +st || 1 }; })
  : await page.evaluate(() => SCENES.filter(s => s.act !== 5 && !Skips.has(s.id)).flatMap(s => Array.from({ length: s.steps }, (_, i) => ({ id: s.id, st: i + 1 }))));
let n = 0;
for (const { id, st } of list) {
  await page.evaluate(([id, st]) => { location.hash = '#' + id + (st > 1 ? '/' + st : ''); }, [id, st]);
  await page.waitForTimeout(350);
  await page.evaluate(() => { document.querySelectorAll('[data-step]').forEach(e => e.style.transition = 'none'); });
  await page.waitForTimeout(150);
  const f = `${outdir}/${String(++n).padStart(2, '0')}_${id}${st > 1 ? '-' + st : ''}.png`;
  await page.screenshot({ path: f });
  console.log(f);
}
if (errors.length) { console.log('\nCONSOLE ERRORS:'); errors.forEach(e => console.log(' ', e)); } else console.log('\nno console errors');
await browser.close();
