import { test, expect } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

// Completely isolated browser test: real CMS HTML/JS/CSS, mocked API, no production writes.
const root=resolve(import.meta.dirname,'../..');
const origin='http://atlas-ui.test';
const png=Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMBAeKf3UYAAAAASUVORK5CYII=','base64');
const samples={
 site:{id:'demo-site',name:'Atlas Demo',url:'https://example.com',sector:'Industrial',summary:'A design reference',screenshot_url:'/screenshots/sites/fictiv.webp',gallery:[],design_strengths:['Clear navigation']},
 module:{id:'demo-module',title:'Hero module',site_id:'demo-site',category:'Hero',lesson:'Clarify buyer choices',summary:'Strong product framing',screenshot_url:'/screenshots/sites/fictiv.webp',crop_px:[0,0,800,400]},
 pattern:{id:'demo-pattern',title:'Trust-first',family:'Credibility',question:'How to earn trust?',principle:'Use evidence',modules:['demo-module']},
 article:{id:'demo-article',title:'Industry notes',subtitle:'Research summary',category:'research',author:'Atlas',sections:[{title:'Introduction',paragraphs:['First paragraph']}],tags:['design'],takeaways:['Clarity']}
};
function makeState(){
 return Object.fromEntries(Object.entries(samples).map(([kind,payload])=>
 [kind,{kind,slug:payload.id,status:'source',source:'repository',revision:0,payload:structuredClone(payload),history:[]}]));
}
async function mockCms(page){
 const records=makeState(),uploads=[];
 await page.route('**/*',async route=>{
  const request=route.request(),url=new URL(request.url()),p=url.pathname,method=request.method();
  const localFiles={
   '/assets/cms.js':['frontend/cms.js','application/javascript; charset=utf-8'],
   '/assets/cms.css':['frontend/cms.css','text/css; charset=utf-8'],
   '/assets/admin.css':['frontend/admin.css','text/css; charset=utf-8']
  };
  if(p==='/admin/content'){
   const html=readFileSync(resolve(root,'frontend/cms.html'),'utf8').replace('data-cms-mode="__CMS_MODE__"','data-cms-mode="admin"');
   return route.fulfill({status:200,contentType:'text/html',body:html});
  }
  if(localFiles[p]){
   const [file,contentType]=localFiles[p];
   return route.fulfill({status:200,contentType,body:readFileSync(resolve(root,file))});
  }
  if(p.startsWith('/screenshots/')||p.startsWith('/api/media/')){
   return route.fulfill({status:200,contentType:'image/png',body:png});
  }
  let result=null,status=200,body={};
  try{body=JSON.parse(request.postData()||'{}')}catch{}
  if(p==='/api/auth/me')result={authenticated:true,csrf_token:'isolated-qa-token',user:{id:'tester',display_name:'QA Tester'}};
  else if(p==='/api/admin/team/me')result={role:'owner',capabilities:['view','edit','review','media','taxonomy','team','export']};
  else if(p==='/api/admin/content/taxonomy')result={categories:{article:['research']},article_tags:['design']};
  else if(p==='/api/admin/categories')result={items:[{id:'research',name:'Research'}]};
  else if(p==='/api/admin/tags')result={items:[{id:'design',name:'Design'}]};
  else if(p==='/api/source-library')result={sites:[{id:'demo-site',name:'Atlas Demo'}]};
  else if(p==='/api/admin/media'&&method==='GET')result={items:uploads};
  else if(p==='/api/admin/media'&&method==='POST'){
   const id='11111111-1111-4111-8111-'+String(uploads.length+1).padStart(12,'0');
   if(!body.content){status=422;result={detail:'File missing'}}
   else {
    const item={id,url:'/api/media/'+id,file_name:body.name,mime:body.mime,byte_size:png.length,created_at:'2026-11-25T10:00:00',usage_count:0,used_by:[]};
    uploads.push(item);result={id,url:item.url,name:body.name,mime:body.mime};
   }
  }
  else if(p==='/api/admin/content'&&method==='GET'){
   const kind=url.searchParams.get('kind'),x=records[kind];
   result={items:x?[{kind,slug:x.slug,label:x.payload.name||x.payload.title,status:x.status,source:x.source,revision:x.revision,sector:x.payload.sector||x.payload.category||x.payload.family||''}]:[]};
  }else{
   const m=p.match(/^\/api\/admin\/content\/(site|module|pattern|article)\/([^/]+)(?:\/(submit|publish|reject|archive))?$/);
   if(m&&records[m[1]]){
    const x=records[m[1]];
    if(method==='PUT'){x.payload=body.payload;x.status='draft';x.source='cms';x.revision++;result={revision:x.revision,status:x.status}}
    else if(method==='POST'){x.status={submit:'review',publish:'published',reject:'draft',archive:'archived'}[m[3]]||x.status;x.revision++;result={revision:x.revision,status:x.status}}
    else result=x;
   }else{status=404;result={detail:'Mock API endpoint not covered: '+method+' '+p}}
  }
  return route.fulfill({status,contentType:'application/json',body:JSON.stringify(result)});
 });
 return {records,uploads};
}

for(const [kind,payload] of Object.entries(samples)){
 test(`${kind} editor opens without duplicate save bars`,async({page})=>{
  const errors=[];page.on('pageerror',error=>errors.push(error.message));
  await mockCms(page);
  await page.goto(origin+'/admin/content?kind='+kind+'&edit='+payload.id);
  await expect(page.locator('#cms-edit-form')).toBeVisible();
  await expect(page.locator('.cms-easy-layout')).toBeVisible();
  await expect(page.locator('[data-editor-save]')).toHaveCount(1);
  await expect(page.locator('[data-editor-submit]')).toHaveCount(1);
  await expect(page.locator('#cms-autosave-status')).toHaveCount(1);
  if(kind==='module')await expect(page.locator('#field-site_id option')).toContainText(['选择关联的网站案例','Atlas Demo']);
  if(kind==='pattern')await expect(page.locator('#cms-preview-title')).toContainText('Trust-first');
  if(kind==='article')await expect(page.locator('#cms-v51-sections')).toBeVisible();
  expect(errors).toEqual([]);
 });
}

test('site editor autosaves and reviewer transitions work',async({page})=>{
 const {records}=await mockCms(page);
 await page.goto(origin+'/admin/content?kind=site&edit=demo-site');
 await page.locator('#field-name').fill('Atlas Demo revised');
 await expect(page.locator('#cms-autosave-status')).toContainText('草稿已保存',{timeout:9000});
 expect(records.site.payload.name).toBe('Atlas Demo revised');
 await expect(page.locator('[data-editor-submit]')).toBeEnabled();
 await page.locator('[data-editor-submit]').click();
 await expect(page.locator('.cms-easy-header-side .cms-item-state')).toContainText('待审核');
 await page.locator('[data-transition="publish"]').click();
 await expect(page.locator('.cms-easy-header-side .cms-item-state')).toContainText('后台已发布');
 expect(records.site.status).toBe('published');
});

test('media picker loads, uploads and adds a gallery entry',async({page})=>{
 const {uploads}=await mockCms(page);
 await page.goto(origin+'/admin/content?kind=site&edit=demo-site');
 await page.locator('[data-gallery-add]').click();
 await expect(page.locator('#cms-media-dialog')).toHaveJSProperty('open',true);
 await expect(page.locator('#cms-media-status')).toContainText('媒体库暂无图片');
 await page.locator('#cms-media-file').setInputFiles({name:'reference.png',mimeType:'image/png',buffer:png});
 await expect(page.locator('#cms-gallery-count')).toContainText('1 张');
 await expect(page.locator('[data-gallery-index]')).toHaveCount(1);
 expect(uploads).toHaveLength(1);
 await page.locator('[data-gallery-remove]').click();
 await expect(page.locator('#cms-gallery-count')).toContainText('0 张');
});

test('320px mobile editor does not overflow, theme remains usable',async({page})=>{
 await mockCms(page);
 await page.setViewportSize({width:320,height:800});
 await page.goto(origin+'/admin/content?kind=site&edit=demo-site');
 await expect(page.locator('.cms-easy-layout')).toBeVisible();
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth+1)).toBe(true);
 await page.locator('[data-set-theme="dark"]').click();
 await expect(page.locator('html')).toHaveAttribute('data-theme','dark');
 await page.setViewportSize({width:1440,height:900});
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth+1)).toBe(true);
});

test('content index shows records directly without dashboard-only clutter',async({page})=>{
 await mockCms(page);
 await page.goto(origin+'/admin/content?kind=site');
 await expect(page.locator('[data-pick="demo-site"]')).toBeVisible();
 await expect(page.locator('#cms-metrics')).toBeHidden();
 await expect(page.locator('.cms-workflow-guide')).toBeHidden();
 await expect(page.locator('#cms-notice')).toBeHidden();
 await page.locator('[data-pick="demo-site"]').click();
 await expect(page.locator('#field-name')).toBeVisible();
 await page.locator('[data-close-editor]').click();
 await expect(page.locator('[data-pick="demo-site"]')).toBeVisible();
});
