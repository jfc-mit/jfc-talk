// verify the cold-open chain: deck gate -> wall -> plane -> deck title, with the HUD clock carried back
import { chromium } from 'playwright';
const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: 1600, height: 900 } });
const errs = []; p.on('pageerror', e => errs.push(e.message));
await p.goto('http://127.0.0.1:8123/index.html?profile=masterclass', { waitUntil: 'load' });
console.log('landed on', await p.evaluate(() => location.hash));
const t0 = Date.now();
await p.click('.handoff a.go'); await p.waitForLoadState('load'); await p.waitForTimeout(500);
console.log('wall:', p.url().replace(/^.*\/assets/, 'assets'));
for (let i = 0; i < 5; i++) { await p.keyboard.press('PageDown'); await p.waitForTimeout(250); }
await p.waitForLoadState('load'); await p.waitForTimeout(500);
console.log('after wall beats:', p.url().replace(/^.*\/assets/, 'assets').slice(0, 100));
for (let i = 0; i < 5; i++) { await p.keyboard.press('PageDown'); await p.waitForTimeout(250); }
await p.waitForLoadState('load'); await p.waitForTimeout(800);
console.log('after plane beats:', p.url().replace('http://127.0.0.1:8123/', ''));
console.log('scene label:', await p.evaluate(() => document.querySelector('#crumb .lab').textContent));
await p.keyboard.press('h'); await p.waitForTimeout(1200);
console.log('HUD clock:', await p.evaluate(() => document.querySelector('#hud-clock').textContent), '(chain took', Math.round((Date.now() - t0) / 1000), 's)');
await p.goto('http://127.0.0.1:8123/assets/wall/wall.html', { waitUntil: 'load' }); await p.waitForTimeout(600);
await p.keyboard.press('Escape'); await p.waitForLoadState('load'); await p.waitForTimeout(900);
console.log('esc from bare wall ->', p.url().replace('http://127.0.0.1:8123/', ''));
await p.goto('http://127.0.0.1:8123/index.html?profile=masterclass', { waitUntil: 'load' });
console.log(await p.evaluate(() => { const v = SCENES.filter(s => s.act !== 5 && !Skips.has(s.id)); const t = v.reduce((a, s) => a + s.budget, 0);
  return `${v.length} scenes, budget ${Math.floor(t/60)}:${String(t%60).padStart(2,'0')}`; }));
console.log(errs.length ? 'ERRORS ' + errs.join('|') : 'no page errors'); await b.close();
