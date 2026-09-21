// PDF fallback of a profile: one page per scene/step, printed from the live deck (Playwright + pdfunite).
// usage: node tools/pdf.mjs <profile> <out.pdf> [theme]
import { chromium } from 'playwright'; import fs from 'node:fs'; import { execFileSync } from 'node:child_process';
const [profile, out, theme = 'dark'] = process.argv.slice(2);
const tmp = fs.mkdtempSync('/tmp/deckpdf-'); const pages = [];
const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: 1600, height: 900 } });
await p.goto(`http://127.0.0.1:8123/index.html?profile=${profile}&theme=${theme}`, { waitUntil: 'load' });
await p.addStyleTag({ content: '#hint,#chrome-br{display:none!important} *{transition:none!important;animation:none!important} html,body{width:1600px;height:900px;overflow:hidden}' });
await p.emulateMedia({ media: 'screen' });
const list = await p.evaluate(() => SCENES.filter(s => s.act !== 5 && !Skips.has(s.id)).flatMap(s => Array.from({ length: s.steps }, (_, i) => ({ id: s.id, st: i + 1 }))));
for (const { id, st } of list) {
  if (id === 'm-cold') continue;   // the wall runs as its own page; its end states are appended below
  await p.evaluate(([id, st]) => { location.hash = '#' + id + (st > 1 ? '/' + st : ''); }, [id, st]);
  await p.waitForTimeout(400);
  await p.evaluate(() => { document.querySelectorAll('[data-step]').forEach(e => e.style.transition = 'none'); if (window.Term && SCENES.find(s => location.hash.slice(1).startsWith(s.id))?.term) {} });
  await p.waitForTimeout(150);
  const f = `${tmp}/${String(pages.length + 1).padStart(3, '0')}.pdf`;
  await p.pdf({ path: f, width: '1600px', height: '900px', printBackground: true, pageRanges: '1' }); pages.push(f);
}
// the wall and the plane, at their last beats
for (const [u, w] of [['assets/wall/wall.html?t=6.9', 1500], ['assets/wall/wall.html?t=12.6', 1500], ['assets/wall/wall.html?t=17.6', 1500], ['assets/wall/wall.html?t=22.6', 1500]]) {
  await p.goto(`http://127.0.0.1:8123/${u}&theme=${theme === 'light' ? 'paper' : 'dark'}`, { waitUntil: 'load' }); await p.waitForTimeout(w);
  await p.addStyleTag({ content: '#hint{display:none!important}' });
  const f = `${tmp}/${String(pages.length + 1).padStart(3, '0')}.pdf`;
  await p.pdf({ path: f, width: '1600px', height: '900px', printBackground: true, pageRanges: '1' }); pages.push(f);
}
await b.close();
fs.mkdirSync('export', { recursive: true });
execFileSync('pdfunite', [...pages, out + '.raw.pdf']);
// Ghostscript halves the size (image re-encoding, font dedup) without rasterising anything
try { execFileSync('gs', ['-q', '-dNOPAUSE', '-dBATCH', '-sDEVICE=pdfwrite', '-dPDFSETTINGS=/printer', '-dCompatibilityLevel=1.6', '-sOutputFile=' + out, out + '.raw.pdf']); fs.unlinkSync(out + '.raw.pdf'); }
catch { fs.renameSync(out + '.raw.pdf', out); }
console.log(out, pages.length, 'pages', (fs.statSync(out).size / 1e6).toFixed(1), 'MB');
