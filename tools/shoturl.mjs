// screenshot arbitrary URLs: node tools/shoturl.mjs out.png url [wait_ms]
import { chromium } from 'playwright';
const [out, url, wait] = process.argv.slice(2);
const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: 1600, height: 900 } });
const errs = []; p.on('pageerror', e => errs.push(e.message)); p.on('console', m => { if (m.type() === 'error') errs.push(m.text()); });
await p.goto(url, { waitUntil: 'load' }); await p.waitForTimeout(+wait || 1500);
await p.screenshot({ path: out }); console.log(out, errs.length ? 'ERRORS: ' + errs.join(' | ') : 'ok'); await b.close();
