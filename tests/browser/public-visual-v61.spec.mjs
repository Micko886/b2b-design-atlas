import {test,expect} from '@playwright/test';
import {mkdirSync} from 'node:fs';
import {join} from 'node:path';

// Chromium runs against an isolated localhost copy, not production data.
const origin=process.env.CMS_E2E_URL||'http://localhost:8765';
if(origin!=='http://localhost:8765')throw Error('V61 visual QA requires isolated localhost:8765');

const out='artifacts/visual-v61';
mkdirSync(out,{recursive:true});
const targets=[
  ['home','/'],
  ['websites','/websites'],
  ['sections','/sections'],
  ['patterns','/patterns'],
  ['insights','/insights'],
  ['manufacturing','/insights/industry-manufacturing-web-experience'],
  ['robotics','/insights/industry-robotics-web-experience'],
  ['automation','/insights/industry-automation-web-experience']
];

async function loaded(page,path){
 const response=await page.goto(origin+path,{waitUntil:'domcontentloaded',timeout:35000});
 expect(response.status(),path+' HTTP response').toBe(200);
 await page.waitForFunction(()=>{
  const app=document.querySelector('#app');
  return app&&app.children.length>0&&!app.querySelector('.loading')
   &&!app.textContent.includes('Library unavailable');
 },null,{timeout:30000});
 await expect(page.locator('#app')).not.toContainText('Library unavailable');
}
async function metrics(page){
 return page.evaluate(()=>{
  const {scrollWidth,clientWidth}=document.documentElement;
  const all=[...document.querySelectorAll('img')];
  const broken=all.filter(x=>x.complete&&!x.naturalWidth);
  const protectedImages=broken.filter(img=>Boolean(img.closest('.visual-load-failed')));
  const overflowing=[...document.querySelectorAll('main *')].filter(el=>{
   const r=el.getBoundingClientRect();
   return r.width>0&&r.right>window.innerWidth+6&&getComputedStyle(el).position!=='fixed';
  }).slice(0,5).map(x=>({
   tag:x.tagName,className:typeof x.className==='string'?x.className.slice(0,60):''
  }));
  return {scrollWidth,clientWidth,images:all.length,broken:broken.length,
          recovered:protectedImages.length,overflowing};
 });
}

test('V61 Chromium desktop/tablet/mobile visual renders and article content',async({browser})=>{
 test.setTimeout(175000);
 const modes=[['desktop',1440,900],['tablet',820,960],['mobile',390,844],['small',320,740]];
 for(const [mode,width,height] of modes){
  const context=await browser.newContext({viewport:{width,height},deviceScaleFactor:1,reducedMotion:'reduce'});
  const page=await context.newPage();
  const errors=[];
  page.on('pageerror',error=>errors.push(error.message));
  try{
   const selected=mode==='desktop'||mode==='mobile'?targets:
     [targets[1],targets[4],targets[5]];
   for(const [name,path] of selected){
    await loaded(page,path);
    const report=await metrics(page);
    expect(report.scrollWidth,mode+' '+name+' horizontal overflow: '+JSON.stringify(report))
      .toBeLessThanOrEqual(report.clientWidth+2);
    expect(errors,mode+' '+name+' uncaught JS errors').toEqual([]);
    if(name==='websites'||name==='sections'){
     await expect(page.locator('#library-results .reference-card').first()).toBeVisible();
     const cols=await page.locator('.masonry').evaluate(el=>getComputedStyle(el).columnCount);
     expect(Number(cols),mode+' '+name+' masonry columns').toBe(
      mode==='desktop'?4:mode==='tablet'?2:1);
    }
    if(['manufacturing','robotics','automation'].includes(name)){
     await expect(page.locator('.insight-prose-section')).toHaveCount(5);
     await expect(page.locator('.insight-block-table-scroll')).toHaveCount(1);
     if(width<=680)await expect(page.locator('.insight-mobile-toc')).toBeVisible();
    }
    await page.screenshot({path:join(out,mode+'-'+name+'.png'),animations:'disabled',timeout:18000});
    console.log('V61_VISUAL_PASS',mode,name,JSON.stringify(report));
   }
  }finally{await context.close();}
 }
});

test('V61 real clicks: mobile menu, topic filter, chapter link and masonry density',async({browser})=>{
 test.setTimeout(85000);
 const context=await browser.newContext({viewport:{width:390,height:844},deviceScaleFactor:1,reducedMotion:'reduce'});
 const page=await context.newPage();
 const errors=[];
 page.on('pageerror',error=>errors.push(error.message));
 try{
  await loaded(page,'/');
  const toggle=page.locator('.mobile-menu-button');
  await expect(toggle).toBeVisible();
  await toggle.click();
  await expect(toggle).toHaveAttribute('aria-expanded','true');
  await page.locator('#mobile-menu a[href="/insights"]').click();
  await expect(page).toHaveURL(origin+'/insights');
  await expect(toggle).toHaveAttribute('aria-expanded','false');
  await page.locator('.insight-topic-card[href*="topic=robotics"]').click();
  await expect(page).toHaveURL(/\/insights\?topic=robotics$/);
  await expect(page.locator('#insights-result-label')).toContainText('机器人');
  await expect(page.locator('#insights-results .insight-card').first()).toBeVisible();
  await page.locator('#insights-results a[href="/insights/industry-robotics-web-experience"]').first().click();
  await expect(page).toHaveURL(/\/insights\/industry-robotics-web-experience$/);
  const toc=page.locator('.insight-mobile-toc');
  await expect(toc).toBeVisible();
  await toc.locator('summary').click();
  await toc.locator('nav [data-action="anchor"]').nth(2).click();
  await expect(page).toHaveURL(/#insight-section-3$/);
  await expect(toc).not.toHaveAttribute('open','');
  await expect(page.locator('#insight-section-3')).toBeFocused();
  await page.screenshot({path:join(out,'mobile-interaction-article-section.png'),animations:'disabled'});
  await loaded(page,'/websites');
  await page.locator('[data-action="density"][data-value="compact"]').click();
  await expect(page.locator('.masonry-compact')).toBeVisible();
  expect(await page.locator('.masonry-compact').evaluate(el=>getComputedStyle(el).columnCount)).toBe('2');
  await page.screenshot({path:join(out,'mobile-interaction-compact-masonry.png'),animations:'disabled'});
  expect(errors,'uncaught JS errors during clicks').toEqual([]);
 }finally{await context.close();}
});
