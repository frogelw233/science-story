// Portable Playwright QA for local generated HTML; never publishes content.
import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';
import fs from 'node:fs/promises';
import path from 'node:path';
import {createHash} from 'node:crypto';
const require=createRequire(import.meta.url);
if(!process.argv[2]) {console.error('Usage: node scripts/render_browser.mjs <run-directory>'); process.exit(2);}
const {chromium}=require('playwright');
const run=path.resolve(process.argv[2]);
const output=path.join(run,'qa');
await fs.mkdir(output,{recursive:true});
const browser=await chromium.launch({headless:true,...(process.env.SCIENCE_STORY_BROWSER ? {executablePath:process.env.SCIENCE_STORY_BROWSER} : {})});
const records=[];
try {
  // Rasterize original SVGs for portable Markdown readers.
  const story=JSON.parse(await fs.readFile(path.join(run,'story.json'),'utf8'));
  const imagePage=await browser.newPage({deviceScaleFactor:2});
  const rasterManifest={};
  const sha=async file=>createHash('sha256').update(await fs.readFile(file)).digest('hex');
  for(const f of story.figures){
    if(!f.file.endsWith('.svg')) continue;
    await imagePage.goto(pathToFileURL(path.join(run,f.file)).href);
    await imagePage.evaluate(()=>document.fonts.ready);
    const dimensions=await imagePage.locator('svg').evaluate(el=>({width:Number(el.getAttribute('width')),height:Number(el.getAttribute('height'))}));
    await imagePage.setViewportSize(dimensions);
    await imagePage.locator('svg').screenshot({path:path.join(run,f.file.replace(/\.svg$/,'.png'))});
    rasterManifest[f.file]={source_sha256:await sha(path.join(run,f.file)),png_sha256:await sha(path.join(run,f.file.replace(/\.svg$/,'.png')))};
  }
  await fs.writeFile(path.join(run,'assets/raster_manifest.json'),JSON.stringify(rasterManifest,null,2)+'\n');
  await imagePage.close();
  for(const [name,width,height] of [['desktop',1440,1000],['mobile',390,844],['narrow',320,740]]){
    const page=await browser.newPage({viewport:{width,height},deviceScaleFactor:1});
    const errors=[];
    page.on('pageerror',e=>errors.push(String(e)));
    await page.goto(pathToFileURL(path.join(run,'article.html')).href);
    await page.evaluate(async()=>{await document.fonts.ready; for(const im of document.images){im.loading='eager';await im.decode();}});
    const metrics=await page.evaluate(()=>({title:document.title,viewport:innerWidth,scrollWidth:document.documentElement.scrollWidth,images:[...document.images].map(im=>({src:im.getAttribute('src'),loaded:im.complete&&im.naturalWidth>0,width:im.width,alt:im.alt})),bodyFont:getComputedStyle(document.body).fontSize,headings:[...document.querySelectorAll('h1,h2')].map(el=>({text:el.textContent,width:el.getBoundingClientRect().width})),lastText:document.querySelector('main').lastElementChild.textContent}));
    const screenshot=`${name}.png`;
    await page.screenshot({path:path.join(output,screenshot),fullPage:true});
    records.push({name,width,height,passed:metrics.scrollWidth<=width&&metrics.images.every(im=>im.loaded&&im.alt)&&errors.length===0,metrics,errors,screenshot:`qa/${screenshot}`});
    const details = page.locator('details');
    if(await details.count()) {
      const checks=[];
      for(let i=0;i<await details.count();i++) {
        const item=details.nth(i);
        const closedInitially=await item.evaluate(el=>!el.open);
        await item.locator('summary').click();
        const opensOnClick=await item.evaluate(el=>el.open);
        const fitsAfterOpen=await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth);
        await item.screenshot({path:path.join(output,`${name}-details-${i+1}.png`)});
        checks.push({index:i+1,closedInitially,opensOnClick,fitsAfterOpen});
        await item.locator('summary').click();
      }
      records.at(-1).optionalDetails=checks;
      records.at(-1).passed &&= checks.every(c=>c.closedInitially && c.opensOnClick && c.fitsAfterOpen);
    }
    await page.close();
  }
  await fs.writeFile(path.join(output,'browser-checks.json'),JSON.stringify({executed_at:new Date().toISOString(),browser:browser.version(),scope:'Actual local Chromium layout and asset checks; screenshots need separate visual inspection',records},null,2)+'\n');
  console.log(JSON.stringify(records.map(({name,passed,metrics})=>({name,passed,scrollWidth:metrics.scrollWidth,viewport:metrics.viewport,images:metrics.images.length})),null,2));
} finally {await browser.close();}
if(records.some(r=>!r.passed)) process.exitCode=1;
