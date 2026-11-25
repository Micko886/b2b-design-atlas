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
async function mockCms(page,role='owner',forcedErrors={}){
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
  if(p==='/api/auth/me')result={authenticated:role!=='guest',csrf_token:'isolated-qa-token',user:{id:'tester',display_name:'QA Tester'}};
  else if(p==='/api/admin/team/me')result={role,capabilities:role==='reviewer'?['view','review']:role==='editor'?['view','edit','media']:['view','edit','review','media','taxonomy','team','export']};
  else if(p==='/api/admin/content/taxonomy')result={categories:{article:['research']},article_tags:['design']};
  else if(p==='/api/admin/categories')result={items:[{id:'research',name:'Research'}]};
  else if(p==='/api/admin/tags')result={items:[{id:'design',name:'Design'}]};
  else if(p==='/api/source-library')result={sites:[{id:'demo-site',name:'Atlas Demo'}]};
  else if(p==='/api/admin/media'&&method==='GET'){
   const q=(url.searchParams.get('q')||'').toLowerCase(),
    usage=url.searchParams.get('usage')||'all',
    type=url.searchParams.get('file_type')||'all',
    seo=url.searchParams.get('seo')||'all',
    offset=Number(url.searchParams.get('offset')||0),
    limit=Number(url.searchParams.get('limit')||24);
   const filtered=uploads.filter(item=>
    (!q||[item.file_name,item.alt_text,item.caption,...(item.used_by||[]).map(x=>x.slug)].join(' ').toLowerCase().includes(q))&&
    (usage==='all'||(usage==='used'?item.usage_count>0:!item.usage_count))&&
    (type==='all'||item.mime==='image/'+type||item.mime_type==='image/'+type)&&
    (seo==='all'||(seo==='ready'?Boolean(item.alt_text):!item.alt_text)));
   result={items:filtered.slice(offset,offset+limit),total:filtered.length,offset,limit,has_more:offset+limit<filtered.length};
  }
  else if(p==='/api/admin/media'&&method==='POST'){
   const id='11111111-1111-4111-8111-'+String(uploads.length+1).padStart(12,'0');
   if(!body.content){status=422;result={detail:'File missing'}}
   else {
    const item={id,url:'/api/media/'+id,file_name:body.name,mime:body.mime,mime_type:body.mime,byte_size:png.length,created_at:'2026-11-25T10:00:00',usage_count:0,used_by:[],alt_text:'',caption:''};
    uploads.push(item);result={id,url:item.url,name:body.name,mime:body.mime};
   }
  }
  else if(method==='PUT'&&/^\/api\/admin\/media\/[0-9a-f-]{36}\/metadata$/.test(p)){
   const id=p.split('/')[4],item=uploads.find(x=>x.id===id);
   if(!item){status=404;result={detail:'Media missing'}}
   else if(String(body.alt_text||'').length>240){status=422;result={detail:'ALT is too long'}}
   else{item.alt_text=String(body.alt_text||'').trim();item.caption=String(body.caption||'').trim();result={ok:true,id,alt_text:item.alt_text,caption:item.caption}}
  }
  else if(p==='/api/admin/media/bulk-delete'&&method==='POST'){
   const target=uploads.filter(item=>(body.ids||[]).includes(item.id));
   if(target.some(item=>item.usage_count)){status=409;result={detail:'有图片仍被草稿或公开内容引用'}}
   else if(target.length!==(body.ids||[]).length){status=404;result={detail:'Media missing'}}
   else{for(const item of target)uploads.splice(uploads.indexOf(item),1);result={ok:true,deleted:target.length}}
  }
  else if(method==='DELETE'&&/^\/api\/admin\/media\/[0-9a-f-]{36}$/.test(p)){
   const id=p.split('/')[4],item=uploads.find(x=>x.id===id);
   if(!item){status=404;result={detail:'Media missing'}}
   else if(item.usage_count){status=409;result={detail:'Image is used'}}
   else{uploads.splice(uploads.indexOf(item),1);result={ok:true}}
  }
  else if(p==='/api/admin/content'&&method==='GET'){
   const kind=url.searchParams.get('kind'),x=records[kind];
   result={items:x?[{kind,slug:x.slug,label:x.payload.name||x.payload.title,status:x.status,source:x.source,revision:x.revision,sector:x.payload.sector||x.payload.category||x.payload.family||''}]:[]};
  }else{
   const m=p.match(/^\/api\/admin\/content\/(site|module|pattern|article)\/([^/]+)(?:\/(submit|publish|reject|archive))?$/);
   if(m&&records[m[1]]){
    const x=records[m[1]];
    if(method==='PUT'){x.payload=body.payload;x.status='draft';x.source='cms';x.revision++;result={revision:x.revision,status:x.status}}
    else if(method==='POST'){if(forcedErrors[m[3]]){status=forcedErrors[m[3]].status;result={detail:forcedErrors[m[3]].detail}}else{x.status={submit:'review',publish:'published',reject:'draft',archive:'archived'}[m[3]]||x.status;x.revision++;result={revision:x.revision,status:x.status}}}
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
 await page.locator('.cms-easy-gallery summary').click();
 await expect(page.locator('.cms-easy-gallery')).toHaveAttribute('open','');
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
 await expect(page.locator('.cms-workflow-guide')).toBeVisible();
 await expect(page.locator('.cms-workflow-guide')).not.toHaveAttribute('open','');
 await expect(page.locator('#cms-notice')).toBeHidden();
 await page.locator('[data-pick="demo-site"]').click();
 await expect(page.locator('#field-name')).toBeVisible();
 await page.locator('[data-close-editor]').click();
 await expect(page.locator('[data-pick="demo-site"]')).toBeVisible();
});

test('reviewer sees records but cannot edit or upload',async({page})=>{
 await mockCms(page,'reviewer');
 await page.goto(origin+'/admin/content?kind=site&edit=demo-site');
 await expect(page.locator('#field-name')).toBeDisabled();
 await expect(page.locator('[data-editor-save]')).toHaveCount(0);
 await expect(page.locator('[data-gallery-add]')).toHaveCount(0);
});

test('expired session shows a clear error instead of an editable list',async({page})=>{
 await mockCms(page,'guest');
 await page.goto(origin+'/admin/content?kind=site');
 await expect(page.locator('#cms-notice')).toBeVisible();
 await expect(page.locator('#cms-notice')).toContainText('无法读取后台内容');
 await expect(page.locator('[data-editor-save]')).toHaveCount(0);
});

test('V52.7 site preview uses unsaved form data without publishing',async({page})=>{
 const {records}=await mockCms(page);
 const media='/api/media/11111111-1111-4111-8111-111111111111';
 records.site.payload.gallery=[{url:media,label:'产品页面'}];
 await page.goto(origin+'/admin/content?kind=site&edit=demo-site');
 await page.locator('[data-editor-tab="preview"]').click();
 await expect(page.locator('.cms-public-card-sample')).toBeVisible();
 await expect(page.locator('.cms-public-detail-sample')).toContainText('Atlas Demo');
 await expect(page.locator('[data-preview-photo]')).toHaveCount(2);
 await page.locator('[data-preview-photo="1"]').click();
 await expect(page.locator('#cms-preview-hero')).toHaveAttribute('src',media);
 await expect(page.locator('[data-preview-photo="1"]')).toHaveAttribute('aria-pressed','true');
 await page.locator('[data-editor-tab="content"]').click();
 await page.locator('#field-summary').fill('<img src=x onerror=alert(1)> Unsaved summary');
 await page.locator('[data-editor-tab="preview"]').click();
 await expect(page.locator('.cms-public-detail-sample')).toContainText('Unsaved summary');
 await expect(page.locator('#cms-private-preview-state')).toContainText('未保存');
 await expect(page.locator('#cms-private-preview img[src="x"]')).toHaveCount(0);
 expect(records.site.payload.summary).toBe('A design reference');
});

test('V52.7 reviewer sees readable original-versus-proposed changes',async({page})=>{
 const {records}=await mockCms(page);
 records.site.status='review';
 records.site.source='cms';
 records.site.revision=2;
 records.site.published=structuredClone(records.site.payload);
 records.site.payload={...records.site.payload,summary:'New review description',
  name:'Atlas Demo Updated',gallery:[{url:'/api/media/11111111-1111-4111-8111-111111111111',label:'Product page'}]};
 await page.goto(origin+'/admin/content?kind=site&edit=demo-site');
 await expect(page.locator('.cms-review-inline')).toBeVisible();
 const inline=page.locator('.cms-review-inline');
 await expect(inline).toContainText('A design reference');
 await expect(inline).toContainText('New review description');
 await expect(inline).toContainText('页面截图');
 await page.locator('[data-editor-tab-link="preview"]').click();
 await expect(page.locator('.cms-public-detail-sample h2')).toContainText('Atlas Demo Updated');
 expect(records.site.status).toBe('review');
});

test('V52.7 preview remains within mobile viewport',async({page})=>{
 await mockCms(page);
 await page.setViewportSize({width:320,height:800});
 await page.goto(origin+'/admin/content?kind=site&edit=demo-site');
 await page.locator('[data-editor-tab="preview"]').click();
 await expect(page.locator('.cms-public-card-sample')).toBeVisible();
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
});

test('V52.8 preview mirrors public research layout and website metadata',async({page})=>{
 const {records}=await mockCms(page);
 records.site.payload.focus='Industrial sourcing';
 records.site.payload.model='B2B platform';
 records.site.payload.visual_style='Clean editorial';
 await page.setViewportSize({width:1160,height:900});
 await page.goto(origin+'/admin/content?kind=site&edit=demo-site');
 await page.locator('[data-editor-tab="preview"]').click();
 await expect(page.locator('.cms-public-specs')).toContainText('业务方向');
 await expect(page.locator('.cms-public-specs')).toContainText('Industrial sourcing');
 await expect(page.locator('.cms-public-style-tags')).toContainText('Clean editorial');
 await expect(page.locator('.cms-public-gallery-note')).toContainText('原有研究截图');
 const layout=await page.evaluate(()=>{
  const image=document.querySelector('.cms-public-gallery').getBoundingClientRect();
  const info=document.querySelector('.cms-public-detail-info').getBoundingClientRect();
  return {imageLeft:image.left,infoLeft:info.left};
 });
 expect(layout.imageLeft).toBeLessThan(layout.infoLeft);
 await page.setViewportSize({width:390,height:800});
 const mobile=await page.evaluate(()=>{
  const image=document.querySelector('.cms-public-gallery').getBoundingClientRect();
  const info=document.querySelector('.cms-public-detail-info').getBoundingClientRect();
  return {imageTop:image.top,infoTop:info.top,scrollWidth:document.documentElement.scrollWidth,width:innerWidth};
 });
 expect(mobile.imageTop).toBeLessThan(mobile.infoTop);
 expect(mobile.scrollWidth).toBeLessThanOrEqual(mobile.width+1);
});

test('V52.8 publish 422 error persists and supports safe server refresh',async({page})=>{
 const {records}=await mockCms(page,'owner',{publish:{status:422,detail:'关联的网站不存在或尚未发布。'}});
 records.site.status='review';records.site.revision=3;records.site.source='cms';
 await page.goto(origin+'/admin/content?kind=site&edit=demo-site');
 await expect(page.locator('[data-editor-submit]')).toBeDisabled();
 await page.locator('[data-transition="publish"]').click();
 await expect(page.locator('#cms-transition-feedback')).toBeVisible();
 await expect(page.locator('#cms-transition-feedback')).toContainText('关联的网站不存在或尚未发布');
 await expect(page.locator('[data-editor-submit]')).toBeDisabled();
 expect(records.site.status).toBe('review');
 await page.locator('[data-review-reload]').click();
 await expect(page.locator('#cms-transition-feedback')).toBeHidden();
 await expect(page.locator('.cms-easy-header-side .cms-item-state')).toContainText('待审核');
});

test('V52.8 stale review revision 409 fails closed without a second publish',async({page})=>{
 const {records}=await mockCms(page,'owner',{publish:{status:409,detail:'版本已更新，请重新打开内容。'}});
 records.site.status='review';records.site.revision=3;records.site.source='cms';
 await page.goto(origin+'/admin/content?kind=site&edit=demo-site');
 await page.locator('[data-transition="publish"]').click();
 await expect(page.locator('#cms-transition-feedback')).toContainText('内容版本已经变化');
 await expect(page.locator('#cms-transition-feedback')).toContainText('版本已更新');
 expect(records.site.revision).toBe(3);
 expect(records.site.status).toBe('review');
});

test('V52.8 rejection requires a reason and retains the draft for correction',async({page})=>{
 const {records}=await mockCms(page);
 records.site.status='review';records.site.revision=4;records.site.source='cms';
 await page.goto(origin+'/admin/content?kind=site&edit=demo-site');
 await page.locator('[data-transition="reject"]').click();
 await expect(page.locator('#cms-transition-feedback')).toContainText('退回原因至少 4 个字符');
 expect(records.site.status).toBe('review');
 await page.locator('#cms-review-reason').fill('请核对行业资料与官网地址');
 await page.locator('[data-transition="reject"]').click();
 await expect(page.locator('.cms-easy-header-side .cms-item-state')).toContainText('草稿');
 expect(records.site.status).toBe('draft');
});

test('V53.0 unified review inbox opens all four types',async({page})=>{
 const {records}=await mockCms(page);
 for(const record of Object.values(records)){record.status='review';record.revision=2;record.source='cms'}
 await page.goto(origin+'/admin/content?workspace=review');
 await expect(page.locator('#cms-review-dialog')).toHaveJSProperty('open',true);
 await expect(page.locator('#cms-review-queue-status')).toContainText('待审核 4 条');
 await expect(page.locator('[data-review-open-kind]')).toHaveCount(4);
 await page.locator('[data-review-open-kind="module"]').click();
 await expect(page.locator('#cms-review-dialog')).toHaveJSProperty('open',false);
 await expect(page.locator('.cms-easy-heading h2')).toContainText('Hero module');
 await expect(page.locator('[data-editor-tab="review"]')).toHaveAttribute('aria-selected','true');
 await expect(page).toHaveURL(/kind=module.*edit=demo-module/);
});

test('V53.0 media and settings are separate role-gated entries',async({page})=>{
 await mockCms(page);
 await page.goto(origin+'/admin/content?workspace=media');
 await expect(page.locator('#cms-media-dialog')).toHaveJSProperty('open',true);
 await expect(page.locator('#cms-media-status')).toContainText('媒体库暂无图片');
 await page.locator('[data-media-close]').first().click();
 await page.locator('#cms-settings-open').click();
 await expect(page.locator('#cms-settings-dialog')).toHaveJSProperty('open',true);
 await expect(page.locator('.cms-v530-tool:not([hidden])')).toHaveCount(4);
 await expect(page.locator('#cms-tools-menu')).toBeVisible();
 await page.locator('[data-v530-close="settings"]').first().click();
 await expect(page.locator('#cms-settings-dialog')).toHaveJSProperty('open',false);
});

test('V53.0 low-privilege roles cannot open settings',async({page})=>{
 const {records}=await mockCms(page,'reviewer');
 for(const record of Object.values(records))record.status='review';
 await page.goto(origin+'/admin/content?workspace=settings');
 await expect(page.locator('#cms-settings-open')).toBeHidden();
 await expect(page.locator('#cms-media-open')).toBeHidden();
 await expect(page.locator('#cms-tools-menu')).toBeHidden();
 await expect(page.locator('#cms-review-shortcut')).toBeVisible();
 await expect(page.locator('#cms-settings-dialog')).toHaveJSProperty('open',false);
 await page.locator('#cms-review-shortcut').click();
 await expect(page.locator('#cms-review-dialog')).toHaveJSProperty('open',true);
 await expect(page.locator('[data-review-open-kind]')).toHaveCount(4);
});

test('V53.0 admin and CMS navigation share six labels',async({page})=>{
 await mockCms(page);
 await page.goto(origin+'/admin/content?kind=site');
 await expect(page.locator('#cms-role')).toContainText('最高管理员');
 await expect(page.locator('#cms-settings-open')).toBeVisible();
 const cms=await page.locator('.atlas-v530-nav').innerText();
 const admin=readFileSync(resolve(root,'frontend/admin.html'),'utf8');
 const adminNav=admin.split('atlas-v530-nav',2)[1].split('</nav>',1)[0];
 for(const label of ['工作台','内容管理','媒体资源','审核发布','运营中心','系统设置']){
  expect(cms).toContain(label);
  expect(adminNav).toContain('<span>'+label+'</span>');
 }
 await page.setViewportSize({width:320,height:760});
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
});

test('V53.1 article structural undo redo restores chapters and blocks safely',async({page})=>{
 const {records}=await mockCms(page);
 records.article.payload.sections=[{title:'Research overview',blocks:[
  {type:'paragraph',text:'Introduction text'},
  {type:'quote',text:'Important evidence'},
  {type:'image',src:'/api/media/11111111-1111-4111-8111-111111111111',alt:'Product dashboard',caption:'Research image'}
 ]}];
 await page.goto(origin+'/admin/content?kind=article&edit=demo-article');
 await expect(page.locator('[data-cms-block]')).toHaveCount(3);
 await expect(page.locator('[data-article-undo]')).toBeDisabled();
 await page.locator('[data-cms-block]').nth(1).locator('[data-block-remove]').click();
 await expect(page.locator('[data-cms-block]')).toHaveCount(2);
 await expect(page.locator('[data-article-undo]')).toBeEnabled();
 await page.locator('[data-article-undo]').click();
 await expect(page.locator('[data-cms-block]')).toHaveCount(3);
 await expect(page.locator('[data-cms-block]').nth(1).locator('[data-block-text]')).toHaveValue('Important evidence');
 await page.locator('[data-article-redo]').click();
 await expect(page.locator('[data-cms-block]')).toHaveCount(2);
 await page.locator('[data-article-undo]').click();
 await page.locator('[data-cms-block]').first().locator('[data-block-move="1"]').click();
 await expect(page.locator('[data-cms-block]').first().locator('[data-block-text]')).toHaveValue('Important evidence');
 await page.locator('[data-article-undo]').click();
 await expect(page.locator('[data-cms-block]').first().locator('[data-block-text]')).toHaveValue('Introduction text');
});

test('V53.1 article image SEO inspector detects missing ALT and offers focused correction',async({page})=>{
 const {records}=await mockCms(page);
 records.article.payload.sections=[{title:'Intro',blocks:[
  {type:'paragraph',text:'B2B visual references'},
  {type:'image',src:'/api/media/11111111-1111-4111-8111-111111111111',alt:'',caption:''}
 ]}];
 await page.goto(origin+'/admin/content?kind=article&edit=demo-article');
 await expect(page.locator('#cms-article-stat')).toContainText('1 个章节');
 await expect(page.locator('#cms-article-health-status')).toContainText('1 项需要处理');
 await expect(page.locator('[data-article-health-action="alt"]')).toHaveCount(1);
 await page.locator('[data-article-health-action="alt"]').click();
 await expect(page.locator('[data-block-alt]')).toBeFocused();
 await page.locator('[data-block-alt]').fill('Industrial product overview screenshot');
 await expect(page.locator('[data-article-health-action="alt"]')).toHaveCount(0);
 await expect(page.locator('#cms-article-health-status')).toContainText('替代文字已检查');
 await expect(page.locator('[data-article-health-action="caption"]')).toHaveCount(1);
 await page.locator('[data-article-health-action="caption"]').click();
 await expect(page.locator('[data-block-caption]')).toBeFocused();
 await page.locator('[data-block-caption]').fill('Product study · Image owner');
 await expect(page.locator('.cms-v531-health-clear')).toBeVisible();
});

test('V53.1 legacy article conversion can be undone and redone without losing text',async({page})=>{
 const {records}=await mockCms(page);
 records.article.payload.sections=[{title:'Legacy section',paragraphs:['Original research'],bullets:['Evidence'],callout:'Remember buyers',
 image:'/api/media/11111111-1111-4111-8111-111111111111',image_caption:'Original image caption'}];
 await page.goto(origin+'/admin/content?kind=article&edit=demo-article');
 await expect(page.locator('[data-article-health-action="convert"]')).toBeVisible();
 await page.locator('[data-article-health-action="convert"]').click();
 await expect(page.locator('[data-blocks-mode]')).toBeVisible();
 await expect(page.locator('[data-cms-block]')).toHaveCount(4);
 await page.locator('[data-article-undo]').click();
 await expect(page.locator('[data-legacy-article]')).toBeVisible();
 await expect(page.locator('[data-v51-paragraphs]')).toHaveValue('Original research');
 await page.locator('[data-article-redo]').click();
 await expect(page.locator('[data-blocks-mode]')).toBeVisible();
 await expect(page.locator('[data-cms-block]')).toHaveCount(4);
});

test('V53.1 article toolbar and image audit fit mobile viewport without overflowing',async({page})=>{
 await mockCms(page);
 await page.setViewportSize({width:320,height:800});
 await page.goto(origin+'/admin/content?kind=article&edit=demo-article');
 await expect(page.locator('.cms-v531-editor-bar')).toBeVisible();
 await expect(page.locator('.cms-v531-media-health')).toBeVisible();
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth+1)).toBe(true);
});

test('V53.2 media search, filters, linked references and pagination operate via API',async({page})=>{
 const {uploads}=await mockCms(page);
 for(let i=0;i<30;i++){
  const id='22222222-2222-4222-8222-'+String(i+1).padStart(12,'0');
  uploads.push({id,url:'/api/media/'+id,file_name:'asset-'+i+'.png',mime_type:'image/png',
   byte_size:125000,created_at:'2026-11-26T10:00:00',usage_count:i===3?1:0,
   used_by:i===3?[{kind:'site',slug:'demo-site'}]:[],alt_text:i%2?'Factory product screenshot':'',caption:''});
 }
 await page.goto(origin+'/admin/content?workspace=media');
 await expect(page.locator('[data-media-id]')).toHaveCount(24);
 await expect(page.locator('#cms-media-total')).toContainText('30 张');
 await page.locator('#cms-media-next').click();
 await expect(page.locator('[data-media-id]')).toHaveCount(6);
 await page.locator('#cms-media-prev').click();
 await expect(page.locator('[data-media-id]')).toHaveCount(24);
 await page.locator('#cms-media-usage').selectOption('used');
 await expect(page.locator('[data-media-id]')).toHaveCount(1);
 await expect(page.locator('[data-media-check]')).toBeDisabled();
 await page.locator('.cms-v532-details summary').click();
 await expect(page.locator('.cms-v532-refs a')).toHaveAttribute('href','/admin/content?kind=site&edit=demo-site');
 await page.locator('#cms-media-usage').selectOption('all');
 await page.locator('#cms-media-seo').selectOption('missing');
 await expect(page.locator('#cms-media-total')).toContainText('15 张');
 await page.locator('#cms-media-seo').selectOption('all');
 await page.locator('#cms-media-search').fill('asset-29');
 await expect(page.locator('[data-media-id]')).toHaveCount(1);
 await expect(page.locator('[data-media-id]')).toContainText('asset-29.png');
});

test('V53.2 media ALT and caption edits persist without modifying published content',async({page})=>{
 const {records,uploads}=await mockCms(page);
 const id='33333333-3333-4333-8333-333333333333';
 uploads.push({id,url:'/api/media/'+id,file_name:'product.png',mime_type:'image/png',byte_size:25000,
  created_at:'2026-11-26T10:00:00',usage_count:0,used_by:[],alt_text:'',caption:''});
 await page.goto(origin+'/admin/content?workspace=media');
 await expect(page.locator('[data-media-seo-status="missing"]')).toHaveCount(1);
 await page.locator('.cms-v532-details summary').click();
 await page.locator('[data-media-alt]').fill('Industrial machinery close-up');
 await page.locator('[data-media-caption]').fill('Product engineering team');
 await page.locator('[data-media-meta-save]').click();
 await expect(page.locator('[data-media-seo-status="ready"]')).toHaveCount(1);
 expect(uploads[0].alt_text).toBe('Industrial machinery close-up');
 expect(uploads[0].caption).toBe('Product engineering team');
 expect(records.article.payload.sections[0].paragraphs[0]).toBe('First paragraph');
 await page.locator('#cms-media-seo').selectOption('missing');
 await expect(page.locator('[data-media-id]')).toHaveCount(0);
});

test('V53.2 bulk delete selects only unused assets and rejects stale used references',async({page})=>{
 const {uploads}=await mockCms(page);
 for(let i=0;i<3;i++){
  const id='44444444-4444-4444-8444-'+String(i+1).padStart(12,'0');
  uploads.push({id,url:'/api/media/'+id,file_name:'sample-'+i+'.png',mime_type:'image/png',
   byte_size:10000,created_at:'2026-11-26T10:00:00',usage_count:i===2?1:0,
   used_by:i===2?[{kind:'article',slug:'demo-article'}]:[],alt_text:'',caption:''});
 }
 page.on('dialog',async dialog=>dialog.accept());
 await page.goto(origin+'/admin/content?workspace=media');
 await page.locator('#cms-media-select-unused').click();
 await expect(page.locator('#cms-media-selected')).toContainText('2 张');
 expect(await page.locator('[data-media-check]:checked').count()).toBe(2);
 await page.locator('#cms-media-bulk-delete').click();
 await expect(page.locator('[data-media-id]')).toHaveCount(1);
 expect(uploads).toHaveLength(1);
 await expect(page.locator('[data-media-check]')).toBeDisabled();
});

test('V53.2 server rejects a media batch if one selected asset gained a reference',async({page})=>{
 const {uploads}=await mockCms(page);
 for(let i=0;i<2;i++){
  const id='55555555-5555-4555-8555-'+String(i+1).padStart(12,'0');
  uploads.push({id,url:'/api/media/'+id,file_name:'photo-'+i+'.png',mime_type:'image/png',
   byte_size:10000,created_at:'2026-11-26T10:00:00',usage_count:0,used_by:[],alt_text:'',caption:''});
 }
 page.on('dialog',async dialog=>dialog.accept());
 await page.goto(origin+'/admin/content?workspace=media');
 await page.locator('#cms-media-select-unused').click();
 uploads[1].usage_count=1;
 await page.locator('#cms-media-bulk-delete').click();
 await expect(page.locator('#cms-media-status')).toContainText('批量删除失败');
 expect(uploads).toHaveLength(2);
});

test('V53.2 media workspace controls fit 320px mobile viewport',async({page})=>{
 await mockCms(page);
 await page.setViewportSize({width:320,height:800});
 await page.goto(origin+'/admin/content?workspace=media');
 await expect(page.locator('.cms-v532-toolbar')).toBeVisible();
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
});
