// make a 480x270 jpeg overview thumb from a screenshot: node tools/thumb.mjs in.png out.jpg
import { chromium } from 'playwright'; import fs from 'node:fs';
const [inp, out] = process.argv.slice(2);
const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: 480, height: 270 } });
const data = 'data:image/png;base64,' + fs.readFileSync(inp).toString('base64');
await p.setContent(`<body style="margin:0"><img src="${data}" style="width:480px;height:270px;display:block"></body>`);
await p.screenshot({ path: out, type: 'jpeg', quality: 80 }); await b.close();
