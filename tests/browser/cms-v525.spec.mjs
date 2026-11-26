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
  else if(method==='GET'&&/^\/api\/admin\/content\/(site|module|pattern|article)\/[^/]+\/diff$/.test(p)){
   const match=p.match(/^\/api\/admin\/content\/(site|module|pattern|article)\/([^/]+)\/diff$/);
   const record=records[match[1]],revision=Number(url.searchParams.get('revision')||0);
   if(!record||record.slug!==match[2]){status=404;result={detail:'Content not found'}}
   else if(revision&&!(record.history||[]).some(x=>x.revision===revision)){
    status=404;result={detail:'No such revision'};
   }else{
    result={current_revision:record.revision,baseline_revision:revision||'published',
     baseline_label:revision?'历史 v'+revision:'当前公开版本',
     revisions:record.history||[],changed_fields:['summary'],summary:{added:1,removed:1},
     chunks:[{tag:'replace',before:['历史内容 v'+revision],after:[record.payload.summary||''],collapsed:0}]};
   }
  }
  else if(method==='POST'&&/^\/api\/admin\/content\/(site|module|pattern|article)\/[^/]+\/restore$/.test(p)){
   const match=p.match(/^\/api\/admin\/content\/(site|module|pattern|article)\/([^/]+)\/restore$/);
   const record=records[match[1]];
   if(!record||record.slug!==match[2]){status=404;result={detail:'Content not found'}}
   else if(body.expected_revision!==record.revision){status=409;result={detail:'Stale revision'}}
   else if(!(record.history||[]).some(x=>x.revision===body.revision)){status=404;result={detail:'History not found'}}
   else{
    record.status='draft';record.source='cms';record.revision++;
    record.history=[{revision:record.revision,action:'restore',created_at:'2026-11-26T12:00:00'},...(record.history||[])];
    result={ok:true,status:'draft',revision:record.revision};
   }
  }
  else if(p==='/api/admin/content'&&method==='POST'){
   const {kind,slug,payload}=body;
   if(records[kind]?.slug===slug){status=409;result={detail:'已存在相同的 URL 标识。'}}
   else if(!records[kind]){status=422;result={detail:'Invalid content type'}}
   else{
    records[kind]={kind,slug,status:'draft',source:'cms',revision:1,payload,history:[{revision:1,action:'create',created_at:'2026-11-26T12:00:00'}]};
    result={ok:true,revision:1,status:'draft'};
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
 await expect(page.locator('[data-editor-save]')).toHaveText('保存草稿');
 await expect(page.locator('[data-editor-submit]')).toBeDisabled();
 await expect(page.locator('[data-editor-submit]')).toHaveAttribute('title','先保存草稿，才能提交审核');
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

test('V53.7 review schedule stays optional and expands on demand',async({page})=>{
 const {records}=await mockCms(page);
 records.site.status='review';
 await page.goto(origin+'/admin/content?kind=site&edit=demo-site');
 await expect(page.locator('[data-editor-tab="review"]')).toHaveAttribute('aria-selected','true');
 const schedule=page.locator('.cms-review-schedule');
 await expect(schedule).toBeVisible();
 await expect(schedule).not.toHaveAttribute('open','');
 await expect(page.locator('#cms-schedule-local')).toBeHidden();
 await schedule.locator('summary').click();
 await expect(schedule).toHaveAttribute('open','');
 await expect(page.locator('#cms-schedule-local')).toBeVisible();
 await expect(page.locator('[data-transition="publish"]')).toBeVisible();
});

test('V53.8 search and status filters offer a single reset action',async({page})=>{
 await mockCms(page);
 await page.goto(origin+'/admin/content?kind=site');
 await expect(page.locator('[data-pick="demo-site"]')).toBeVisible();
 await page.locator('#cms-search').fill('no-such-reference');
 await expect(page.locator('[data-pick]')).toHaveCount(0);
 await expect(page.locator('[data-clear-content-filters]')).toBeVisible();
 await page.locator('[data-clear-content-filters]').click();
 await expect(page.locator('#cms-search')).toHaveValue('');
 await expect(page.locator('[data-pick="demo-site"]')).toBeVisible();
 await page.locator('#cms-status').selectOption('review');
 await expect(page.locator('[data-clear-content-filters]')).toBeVisible();
 await page.locator('[data-clear-content-filters]').click();
 await expect(page.locator('#cms-status')).toHaveValue('');
 await expect(page.locator('[data-pick="demo-site"]')).toBeVisible();
});

test('V54.8 review and history use one tab strip, without duplicate toolbar buttons',async({page})=>{
 const {records}=await mockCms(page);
 records.site.status='review';
 await page.goto(origin+'/admin/content?kind=site&edit=demo-site');
 await expect(page.locator('[data-editor-submit]')).toBeHidden();
 await expect(page.locator('[data-editor-submit]')).toBeDisabled();
 await expect(page.locator('[data-editor-state-link]')).toHaveCount(0);
 await expect(page.locator('.cms-edit-quick-actions [data-editor-save]')).toHaveCount(1);
 await expect(page.locator('[data-editor-tab="review"]')).toHaveText('审核 · 待处理');
 await page.locator('[data-editor-tab="content"]').click();
 await page.locator('[data-editor-tab="review"]').click();
 await expect(page.locator('[data-editor-pane="review"]')).toBeVisible();
 records.site.status='published';
 await page.reload();
 await expect(page.locator('[data-editor-submit]')).toBeHidden();
 await expect(page.locator('[data-editor-state-link]')).toHaveCount(0);
 await page.locator('[data-editor-tab="history"]').click();
 await expect(page.locator('[data-editor-pane="history"]')).toBeVisible();
});

test('V53.8 saving a reviewed item exposes submit action for its new draft',async({page})=>{
 const {records}=await mockCms(page);
 records.site.status='review';
 await page.goto(origin+'/admin/content?kind=site&edit=demo-site');
 await expect(page.locator('[data-editor-state-link]')).toHaveCount(0);
 await expect(page.locator('[data-editor-tab="review"]')).toBeVisible();
 await page.locator('[data-editor-tab="content"]').click();
 await page.locator('#field-name').fill('Updated after review');
 await expect(page.locator('#cms-autosave-status')).toContainText('草稿已保存',{timeout:9000});
 await expect(page.locator('[data-editor-submit]')).toBeVisible();
 await expect(page.locator('[data-editor-submit]')).toBeEnabled();
 await expect(page.locator('[data-editor-state-link]')).toHaveCount(0);
});

test('V53.9 history explains safe restore and compares a previous revision',async({page})=>{
 const {records}=await mockCms(page);
 records.site.source='cms';records.site.status='published';records.site.revision=4;
 records.site.history=[
  {revision:4,action:'publish',created_at:'2026-11-25T11:00:00'},
  {revision:3,action:'submit',created_at:'2026-11-25T10:00:00'},
  {revision:2,action:'save',created_at:'2026-11-25T09:00:00'}
 ];
 await page.goto(origin+'/admin/content?kind=site&edit=demo-site');
 await page.locator('[data-editor-tab="history"]').click();
 await expect(page.locator('.cms-history-heading')).toContainText('不会改变正在公开的内容');
 await expect(page.locator('[data-history-revision="4"] .cms-history-current')).toHaveText('当前版本');
 await expect(page.locator('[data-restore="4"]')).toHaveCount(0);
 await page.locator('[data-review-diff="2"]').click();
 await expect(page.locator('#cms-diff-dialog')).toHaveJSProperty('open',true);
 await expect(page.locator('#cms-diff-left-title')).toHaveText('历史 v2');
 await expect(page.locator('#cms-diff-right-title')).toContainText('当前已发布稿');
 await expect(page.locator('#cms-diff-baseline')).toHaveValue('2');
 await page.locator('#cms-diff-baseline').selectOption('3');
 await expect(page.locator('#cms-diff-left-title')).toHaveText('历史 v3');
 await expect(page.locator('#cms-diff-baseline')).toHaveValue('3');
 await page.locator('[data-v518-close-diff]').first().click();
 expect(records.site.status).toBe('published');
});

test('V53.9 recovering a history snapshot creates draft without publishing',async({page})=>{
 const {records}=await mockCms(page);
 records.site.source='cms';records.site.status='published';records.site.revision=4;
 records.site.history=[
  {revision:4,action:'publish',created_at:'2026-11-25T11:00:00'},
  {revision:2,action:'save',created_at:'2026-11-25T09:00:00'}
 ];
 await page.goto(origin+'/admin/content?kind=site&edit=demo-site');
 await page.locator('[data-editor-tab="history"]').click();
 page.once('dialog',dialog=>{
  expect(dialog.message()).toContain('不会被覆盖');
  dialog.accept();
 });
 await page.locator('[data-restore="2"]').click();
 await expect(page.locator('.cms-easy-header-side .cms-item-state')).toContainText('草稿');
 expect(records.site.status).toBe('draft');
 expect(records.site.revision).toBe(5);
 await expect(page.locator('[data-history-revision="5"] .cms-history-current')).toHaveCount(1);
});

test('V53.9 reviewers can compare history but cannot restore it',async({page})=>{
 const {records}=await mockCms(page,'reviewer');
 records.site.source='cms';records.site.status='review';records.site.revision=4;
 records.site.history=[
  {revision:4,action:'submit',created_at:'2026-11-25T11:00:00'},
  {revision:2,action:'save',created_at:'2026-11-25T09:00:00'}
 ];
 await page.goto(origin+'/admin/content?kind=site&edit=demo-site');
 await page.locator('[data-editor-tab="history"]').click();
 await expect(page.locator('[data-restore]')).toHaveCount(0);
 await expect(page.locator('[data-review-diff="2"]')).toBeVisible();
});

test('V54 editor tabs have linked panels and support arrow, Home and End keys',async({page})=>{
 await mockCms(page);
 await page.goto(origin+'/admin/content?kind=site&edit=demo-site');
 const content=page.locator('[data-editor-tab="content"]');
 const preview=page.locator('[data-editor-tab="preview"]');
 const history=page.locator('[data-editor-tab="history"]');
 await expect(content).toHaveAttribute('aria-controls','cms-editor-pane-content');
 await expect(page.locator('#cms-editor-pane-content')).toHaveAttribute('aria-labelledby','cms-editor-tab-content');
 await expect(page.locator('#cms-editor-pane-content')).toHaveAttribute('role','tabpanel');
 await content.focus();
 await page.keyboard.press('ArrowRight');
 await expect(preview).toBeFocused();
 await expect(preview).toHaveAttribute('aria-selected','true');
 await expect(page.locator('#cms-editor-pane-preview')).toBeVisible();
 await expect(page.locator('#cms-editor-pane-content')).toBeHidden();
 await page.keyboard.press('End');
 await expect(history).toBeFocused();
 await expect(page.locator('#cms-editor-pane-history')).toBeVisible();
 await page.keyboard.press('Home');
 await expect(content).toBeFocused();
 await expect(page.locator('#cms-editor-pane-content')).toBeVisible();
 await page.keyboard.press('ArrowLeft');
 await expect(history).toBeFocused();
});

test('V54 article keyboard tabs and mobile width do not overflow',async({page})=>{
 await mockCms(page);
 await page.setViewportSize({width:320,height:760});
 await page.goto(origin+'/admin/content?kind=article&edit=demo-article');
 const content=page.locator('[data-editor-tab="content"]');
 const seo=page.locator('[data-editor-tab="seo"]');
 await content.focus();
 await page.keyboard.press('ArrowRight');
 await page.keyboard.press('ArrowRight');
 await expect(seo).toBeFocused();
 await expect(page.locator('#cms-editor-pane-seo')).toBeVisible();
 await expect(page.locator('[data-editor-tab="content"]')).toHaveAttribute('tabindex','-1');
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth+1)).toBe(true);
 await page.keyboard.press('End');
 await expect(page.locator('[data-editor-tab="history"]')).toBeFocused();
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth+1)).toBe(true);
});

test('V54 read-only reviewer can navigate panels with keyboard, without edit actions',async({page})=>{
 const {records}=await mockCms(page,'reviewer');
 records.site.status='review';
 await page.goto(origin+'/admin/content?kind=site&edit=demo-site');
 const review=page.locator('[data-editor-tab="review"]');
 await expect(review).toHaveAttribute('aria-selected','true');
 await review.focus();
 await page.keyboard.press('ArrowRight');
 await expect(page.locator('[data-editor-tab="history"]')).toBeFocused();
 await expect(page.locator('#cms-editor-pane-history')).toBeVisible();
 await expect(page.locator('[data-editor-save]')).toHaveCount(0);
 await expect(page.locator('[data-restore]')).toHaveCount(0);
});

test('V54.1 batch actions appear only after eligible CMS records are selected',async({page})=>{
 const {records}=await mockCms(page);
 await page.goto(origin+'/admin/content?kind=site');
 await expect(page.locator('#cms-bulk-toolbar')).toBeHidden();
 await expect(page.locator('[data-bulk-select]')).toHaveCount(0);
 records.site.status='draft';records.site.source='cms';records.site.revision=2;
 await page.reload();
 await expect(page.locator('[data-bulk-select="demo-site"]')).toBeVisible();
 await expect(page.locator('#cms-bulk-toolbar')).toBeVisible();
 await expect(page.locator('#cms-bulk-action')).toBeHidden();
 await expect(page.locator('#cms-bulk-run')).toBeHidden();
 await page.locator('[data-bulk-select="demo-site"]').check();
 await expect(page.locator('#cms-selected-count')).toContainText('1 项已选择');
 await expect(page.locator('#cms-bulk-action')).toBeVisible();
 await expect(page.locator('#cms-bulk-run')).toBeVisible();
 await page.locator('[data-bulk-select="demo-site"]').uncheck();
 await expect(page.locator('#cms-bulk-run')).toBeHidden();
 await expect(page.locator('#cms-selected-count')).toBeHidden();
});

test('V54.1 review queue separates total from categories and stays usable at 320px',async({page})=>{
 const {records}=await mockCms(page);
 records.site.status='review';records.site.revision=3;records.site.source='cms';
 records.module.status='review';records.module.revision=2;records.module.source='cms';
 await page.setViewportSize({width:320,height:740});
 await page.goto(origin+'/admin/content?workspace=review');
 const status=page.locator('#cms-review-queue-status');
 await expect(status.locator('strong')).toHaveText('待审核 2 条');
 await expect(status.locator('span')).toContainText('网站 1 · 模块 1');
 await expect(page.locator('[data-review-open-kind]')).toHaveCount(2);
 await expect(page.locator('.cms-v530-review-row')).toHaveCount(2);
 await expect(page.locator('[data-review-open-kind="site"]')).toHaveAttribute('aria-label',/查看 .* 的审核变更/);
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
});

test('V54.1 all four editors have a single consistent basic-info heading',async({page})=>{
 const {records}=await mockCms(page);
 for(const kind of ['site','module','pattern','article']){
  await page.goto(origin+'/admin/content?kind='+kind+'&edit='+records[kind].slug);
  await expect(page.locator('.cms-easy-intro h3')).toHaveText('基本信息');
  await expect(page.locator('.cms-easy-heading h2')).toBeVisible();
 }
});

test('V54.2 content cards use consistent non-cropping thumbnails and no mobile overflow',async({page})=>{
 await mockCms(page);
 await page.setViewportSize({width:320,height:740});
 await page.goto(origin+'/admin/content?kind=site');
 const thumb=page.locator('.cms-v51-row .cms-item-thumb img').first();
 await expect(thumb).toBeVisible();
 expect(await thumb.evaluate(el=>getComputedStyle(el).objectFit)).toBe('contain');
 const measurements=await page.evaluate(()=>{
  const card=document.querySelector('.cms-v51-row'),thumb=document.querySelector('.cms-item-thumb');
  const outer=card.getBoundingClientRect(),inner=thumb.getBoundingClientRect();
  return {cardWidth:outer.width,thumbWidth:inner.width,docWidth:document.documentElement.scrollWidth,screen:innerWidth};
 });
 expect(measurements.cardWidth).toBeGreaterThan(measurements.thumbWidth);
 expect(measurements.docWidth).toBeLessThanOrEqual(measurements.screen+1);
});

test('V54.2 missing screenshot degrades to a neutral icon instead of broken image',async({page})=>{
 await mockCms(page);
 await page.route('**/screenshots/sites/demo-site.webp',route=>route.fulfill({status:404,contentType:'text/plain',body:'not found'}));
 await page.goto(origin+'/admin/content?kind=site');
 await expect(page.locator('.cms-item-thumb.cms-thumb-missing')).toHaveCount(1);
 await expect(page.locator('.cms-item-thumb.cms-thumb-missing svg')).toBeVisible();
 await expect(page.locator('.cms-item-thumb img')).toHaveCount(0);
});

test('V54.2 image preview stays contained in light and dark mobile themes',async({page})=>{
 await mockCms(page);
 await page.setViewportSize({width:320,height:740});
 await page.goto(origin+'/admin/content?kind=site&edit=demo-site');
 const img=page.locator('#cms-site-image');
 await expect(img).toBeVisible();
 expect(await img.evaluate(el=>getComputedStyle(el).objectFit)).toBe('contain');
 const light=await page.locator('.cms-easy-shot').evaluate(el=>getComputedStyle(el).backgroundColor);
 await page.locator('[data-set-theme="dark"]').click();
 await expect(page.locator('html')).toHaveAttribute('data-theme','dark');
 const dark=await page.locator('.cms-easy-shot').evaluate(el=>getComputedStyle(el).backgroundColor);
 expect(dark).not.toBe(light);
 const layout=await page.evaluate(()=>{
  const parent=document.querySelector('.cms-easy-shot').getBoundingClientRect();
  const child=document.querySelector('#cms-site-image').getBoundingClientRect();
  return {parentLeft:parent.left,parentRight:parent.right,childLeft:child.left,childRight:child.right,documentWidth:document.documentElement.scrollWidth,screen:innerWidth};
 });
 expect(layout.childLeft).toBeGreaterThanOrEqual(layout.parentLeft-1);
 expect(layout.childRight).toBeLessThanOrEqual(layout.parentRight+1);
 expect(layout.documentWidth).toBeLessThanOrEqual(layout.screen+1);
});

test('V54.2 review modal and its action remain inside a narrow dark viewport',async({page})=>{
 const {records}=await mockCms(page);
 records.site.status='review';records.site.source='cms';records.site.revision=2;
 await page.setViewportSize({width:320,height:740});
 await page.goto(origin+'/admin/content?kind=site');
 await page.locator('[data-set-theme="dark"]').click();
 await expect(page.locator('html')).toHaveAttribute('data-theme','dark');
 await page.locator('#cms-menu').click();
 await expect(page.locator('#cms-menu')).toHaveAttribute('aria-expanded','true');
 await expect(page.locator('#cms-review-shortcut')).toBeVisible();
 await page.locator('#cms-review-shortcut').click();
 await expect(page.locator('#cms-review-dialog')).toHaveJSProperty('open',true);
 const result=await page.evaluate(()=>{
  const modal=document.querySelector('#cms-review-dialog').getBoundingClientRect();
  const action=document.querySelector('[data-review-open-kind="site"]').getBoundingClientRect();
  return {left:modal.left,right:modal.right,actionLeft:action.left,actionRight:action.right,viewport:innerWidth,docWidth:document.documentElement.scrollWidth};
 });
 expect(result.left).toBeGreaterThanOrEqual(0);
 expect(result.right).toBeLessThanOrEqual(result.viewport+1);
 expect(result.actionLeft).toBeGreaterThanOrEqual(result.left-1);
 expect(result.actionRight).toBeLessThanOrEqual(result.right+1);
 expect(result.docWidth).toBeLessThanOrEqual(result.viewport+1);
});

test('V54.6 submit and publish show persistent next steps in the editor',async({page})=>{
 const {records}=await mockCms(page);
 records.site.status='draft';records.site.source='cms';records.site.revision=2;
 await page.goto(origin+'/admin/content?kind=site&edit=demo-site');
 await page.locator('[data-editor-submit]').click();
 await expect(page.locator('#cms-transition-feedback')).toContainText('已提交审核');
 await expect(page.locator('#cms-transition-feedback')).toHaveAttribute('data-state','success');
 await expect(page.locator('#cms-transition-feedback')).toHaveAttribute('role','status');
 await page.locator('#cms-transition-feedback [data-editor-tab-link="review"]').click();
 await expect(page.locator('#cms-editor-pane-review')).toBeVisible();
 await page.locator('[data-transition="publish"]').click();
 await expect(page.locator('#cms-transition-feedback')).toContainText('审核通过，已正式发布');
 await expect(page.locator('#cms-transition-feedback a')).toHaveAttribute('href','/websites/demo-site');
 expect(records.site.status).toBe('published');
});

test('V54.6 rejection validation focuses reason, not misleading reload',async({page})=>{
 const {records}=await mockCms(page);
 records.site.status='review';records.site.source='cms';records.site.revision=3;
 await page.goto(origin+'/admin/content?kind=site&edit=demo-site');
 await page.locator('[data-transition="reject"]').click();
 await expect(page.locator('#cms-review-reason')).toBeFocused();
 await expect(page.locator('#cms-review-reason')).toHaveAttribute('aria-invalid','true');
 await expect(page.locator('#cms-transition-feedback')).toHaveAttribute('role','alert');
 await expect(page.locator('[data-review-reload]')).toHaveCount(0);
 await page.locator('#cms-review-reason').fill('请补充目标用户信息');
 await expect(page.locator('#cms-review-reason')).not.toHaveAttribute('aria-invalid','true');
 await expect(page.locator('#cms-transition-feedback')).toBeHidden();
 await page.locator('[data-transition="reject"]').click();
 await expect(page.locator('#cms-transition-feedback')).toContainText('已退回修改');
 expect(records.site.status).toBe('draft');
});

test('V54.6 editor sees the latest review reason, escaped and responsive',async({page})=>{
 const {records}=await mockCms(page,'editor');
 records.site.status='draft';records.site.source='cms';records.site.revision=5;
 records.site.history=[
  {revision:5,action:'save',created_at:'2026-11-25T10:02:00'},
  {revision:4,action:'reject',reason:'请补充证据 <img src=x onerror=alert(1)>',created_at:'2026-11-25T10:01:00'}
 ];
 await page.setViewportSize({width:320,height:720});
 await page.goto(origin+'/admin/content?kind=site&edit=demo-site');
 const note=page.locator('.cms-v546-rejection-note');
 await expect(note).toBeVisible();
 await expect(note).toContainText('请补充证据 <img src=x onerror=alert(1)>');
 await expect(note.locator('img')).toHaveCount(0);
 await note.locator('[data-editor-tab-link="history"]').click();
 await expect(page.locator('#cms-editor-pane-history')).toBeVisible();
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
});

test('V54.7 list next action respects status and current role',async({page})=>{
 const {records}=await mockCms(page,'reviewer');
 records.site.status='review';records.site.source='cms';records.site.revision=3;
 await page.goto(origin+'/admin/content?kind=site');
 await expect(page.locator('.cms-item-open-label')).toHaveText('核对修改 · 审核发布 →');
 await page.locator('#cms-review-shortcut').click();
 await expect(page.locator('[data-review-open-kind="site"]')).toHaveText('查看并审核');
 await page.locator('#cms-review-dialog [data-v530-close="review"]').first().click();
 records.site.status='published';
 await page.reload();
 await expect(page.locator('.cms-item-open-label')).toHaveText('查看发布记录 →');
});

test('V54.7 filters discard hidden bulk selections before any action',async({page})=>{
 const {records}=await mockCms(page);
 records.site.status='draft';records.site.source='cms';records.site.revision=2;
 await page.goto(origin+'/admin/content?kind=site');
 await page.locator('[data-bulk-select="demo-site"]').check();
 await expect(page.locator('#cms-selected-count')).toContainText('1 项已选择');
 await page.locator('#cms-status').selectOption('review');
 await expect(page.locator('#cms-selected-count')).toBeHidden();
 await expect(page.locator('#cms-bulk-run')).toBeHidden();
 await page.locator('#cms-status').selectOption('');
 await expect(page.locator('[data-bulk-select="demo-site"]')).not.toBeChecked();
 await page.locator('[data-bulk-select="demo-site"]').check();
 await page.locator('#cms-search').fill('something else');
 await expect(page.locator('#cms-selected-count')).toBeHidden();
 await page.locator('#cms-search').fill('demo');
 await expect(page.locator('[data-bulk-select="demo-site"]')).not.toBeChecked();
});

test('V54.7 a draft revision conflict offers copy backup, not unsafe retry',async({page})=>{
 const {records}=await mockCms(page);
 records.site.status='draft';records.site.source='cms';records.site.revision=2;
 await page.addInitScript(()=>{
   Object.defineProperty(navigator,'clipboard',{configurable:true,value:{
     writeText:async text=>{window.__savedBackup=String(text)}
   }});
 });
 await page.route('**/api/admin/content/site/demo-site',async route=>{
   if(route.request().method()==='PUT')return route.fulfill({status:409,contentType:'application/json',body:JSON.stringify({detail:'版本已被他人更新'})});
   return route.fallback();
 });
 await page.goto(origin+'/admin/content?kind=site&edit=demo-site');
 await page.locator('#field-name').fill('Unpublished local change');
 await expect(page.locator('#cms-autosave-status')).toContainText('版本冲突',{timeout:10000});
 await expect(page.locator('[data-autosave-copy]')).toBeVisible();
 await expect(page.locator('[data-autosave-retry]')).toBeHidden();
 await page.locator('[data-autosave-copy]').click();
 await expect.poll(()=>page.evaluate(()=>window.__savedBackup||'')).toContain('Unpublished local change');
});

test('V54.8 drafts without published snapshots never show a broken public link',async({page})=>{
 const {records}=await mockCms(page);
 records.site.source='cms';records.site.status='draft';records.site.revision=2;
 records.site.published=null;
 await page.goto(origin+'/admin/content?kind=site&edit=demo-site');
 await expect(page.locator('.cms-easy-public-link')).toHaveCount(0);
 await expect(page.locator('.cms-easy-heading')).toContainText('草稿不会自动公开');
 records.site.status='published';
 await page.reload();
 await expect(page.locator('.cms-easy-public-link')).toHaveAttribute('href','/websites/demo-site');
});

test('V54.8 editor reduces duplicated controls without hiding advanced fields',async({page})=>{
 await mockCms(page);
 await page.goto(origin+'/admin/content?kind=site&edit=demo-site');
 await expect(page.locator('[data-editor-save]')).toHaveCount(1);
 await expect(page.locator('[data-editor-submit]')).toHaveCount(1);
 await expect(page.locator('[data-editor-state-link]')).toHaveCount(0);
 await expect(page.locator('.cms-easy-header h2')).toHaveCount(1);
 await expect(page.locator('[data-editor-tab]')).toHaveCount(4);
 await expect(page.locator('[data-editor-tab="preview"]')).toHaveText('预览');
 await expect(page.locator('[data-editor-tab="history"]')).toHaveText('历史');
 const settings=page.locator('.cms-easy-advanced').filter({has:page.locator('summary', {hasText:'更多设置'})});
 await expect(settings).not.toHaveAttribute('open','');
 await settings.locator('summary').click();
 await expect(settings).toHaveAttribute('open','');
});

test('V54.8 narrow dark-mode editor has no horizontal document overflow',async({page})=>{
 await mockCms(page);
 await page.setViewportSize({width:320,height:740});
 await page.goto(origin+'/admin/content?kind=site&edit=demo-site');
 await page.locator('[data-set-theme="dark"]').click();
 await expect(page.locator('html')).toHaveAttribute('data-theme','dark');
 await expect(page.locator('[data-editor-save]')).toBeVisible();
 await expect(page.locator('.cms-easy-shot')).toBeVisible();
 await page.locator('[data-editor-tab="preview"]').click();
 await expect(page.locator('[data-editor-pane="preview"]')).toBeVisible();
 const result=await page.evaluate(()=>({
   viewport:innerWidth,documentWidth:document.documentElement.scrollWidth,
   scrollableTabs:document.querySelector('.atlas-v521-editor-tabs').scrollWidth,
   tabsWidth:document.querySelector('.atlas-v521-editor-tabs').clientWidth
 }));
 expect(result.documentWidth).toBeLessThanOrEqual(result.viewport+1);
 expect(result.tabsWidth).toBeGreaterThan(0);
});

test('V54.9 browser Back cancellation preserves the dirty editor and URL',async({page})=>{
 const {records}=await mockCms(page);
 await page.goto(origin+'/admin/content?kind=site');
 await page.locator('[data-pick="demo-site"]').click();
 await expect(page).toHaveURL(/edit=demo-site/);
 await page.locator('#field-name').fill('Local unsaved title');
 const rejected=page.waitForEvent('dialog').then(dialog=>dialog.dismiss());
 await page.evaluate(()=>history.back());
 await rejected;
 await expect(page).toHaveURL(/edit=demo-site/);
 await expect(page.locator('#field-name')).toHaveValue('Local unsaved title');
 expect(records.site.payload.name).toBe('Atlas Demo');
 const accepted=page.waitForEvent('dialog').then(dialog=>dialog.accept());
 await page.evaluate(()=>history.back());
 await accepted;
 await expect(page).toHaveURL(/\\?kind=site$/);
 await expect(page.locator('#cms-editor-body')).toBeHidden();
 expect(await page.evaluate(()=>Object.keys(sessionStorage).filter(key=>key.startsWith('atlas-cms-working-v1:')))).toEqual([]);
});

test('V54.9 switching content types discards stale recovery and clears edit URL',async({page})=>{
 await mockCms(page);
 await page.goto(origin+'/admin/content?kind=site&edit=demo-site');
 await page.locator('#field-name').fill('Change to discard before switching');
 const accepted=page.waitForEvent('dialog').then(dialog=>dialog.accept());
 await page.locator('[data-close-editor]').click();
 await accepted;
 await expect(page.locator('#cms-editor-body')).toBeHidden();
 await page.locator('[data-kind-link="module"]').click();
 await expect(page.locator('[data-pick="demo-module"]')).toBeVisible();
 await expect(page).toHaveURL(/\\?kind=module$/);
 expect(await page.evaluate(()=>Object.keys(sessionStorage).filter(key=>key.startsWith('atlas-cms-working-v1:')))).toEqual([]);
});

test('V55.0 editor image picker hides destructive workbench actions and resets stale filters',async({page})=>{
 const {uploads}=await mockCms(page);
 await page.goto(origin+'/admin/content?kind=site&edit=demo-site');
 // Seed the library through the full workbench before opening the focused picker.
 await page.locator('#cms-media-open').click();
 await expect(page.locator('#cms-media-dialog-title')).toHaveText('媒体资源与 SEO');
 await expect(page.locator('#cms-media-usage')).toBeVisible();
 await page.locator('#cms-media-file').setInputFiles({name:'factory.png',mimeType:'image/png',buffer:png});
 await expect(page.locator('[data-media-id]')).toHaveCount(1);
 await page.locator('#cms-media-search').fill('does-not-exist');
 await expect(page.locator('[data-media-id]')).toHaveCount(0);
 await page.locator('[data-media-close]').first().click();
 await page.locator('[data-editor-pick-media="field-screenshot_url"]').click();
 await expect(page.locator('#cms-media-dialog')).toHaveClass(/cms-media-picker-mode/);
 await expect(page.locator('#cms-media-dialog-title')).toHaveText('选择展示图片');
 await expect(page.locator('#cms-media-search')).toHaveValue('');
 await expect(page.locator('#cms-media-usage')).toBeHidden();
 await expect(page.locator('#cms-media-select-unused')).toBeHidden();
 await expect(page.locator('[data-v51-delete-media]')).toBeHidden();
 await expect(page.locator('[data-v51-copy-media]')).toBeHidden();
 await expect(page.locator('[data-v51-use-media]')).toHaveText('使用这张图片');
 await page.locator('[data-v51-use-media]').click();
 await expect(page.locator('#cms-media-dialog')).not.toHaveJSProperty('open',true);
 expect(await page.locator('#field-screenshot_url').inputValue()).toBe(uploads[0].url);
 await page.locator('#cms-media-open').click();
 await expect(page.locator('#cms-media-dialog')).not.toHaveClass(/cms-media-picker-mode/);
 await expect(page.locator('#cms-media-usage')).toBeVisible();
 await expect(page.locator('[data-v51-delete-media]')).toBeVisible();
});

test('V55.0 gallery chooser remains simple and batch-upload works',async({page})=>{
 await mockCms(page);
 await page.goto(origin+'/admin/content?kind=site&edit=demo-site');
 await page.locator('.cms-easy-gallery summary').click();
 await page.locator('[data-gallery-add]').click();
 await expect(page.locator('#cms-media-dialog-title')).toHaveText('添加案例页面截图');
 await expect(page.locator('#cms-media-picker-intro')).toBeVisible();
 await expect(page.locator('#cms-media-bulk-delete')).toBeHidden();
 await page.locator('#cms-media-file').setInputFiles([
  {name:'factory-1.png',mimeType:'image/png',buffer:png},
  {name:'factory-2.png',mimeType:'image/png',buffer:png}
 ]);
 await expect(page.locator('#cms-gallery-count')).toContainText('2 张');
 await expect(page.locator('[data-gallery-index]')).toHaveCount(2);
});

test('V55.1 beginner creates English site without touching URL identifier',async({page})=>{
 const {records}=await mockCms(page);
 await page.goto(origin+'/admin/content?kind=site');
 await page.locator('#cms-new').click();
 await expect(page.locator('#cms-create-dialog')).toHaveJSProperty('open',true);
 await expect(page.locator('#cms-create-advanced')).not.toHaveAttribute('open','');
 await expect(page.locator('#cms-create-slug')).toBeHidden();
 await page.locator('#cms-create-fields [name="name"]').fill('Modern Robotics');
 await page.locator('#cms-create-fields [name="url"]').fill('https://robotics.example');
 await page.locator('#cms-create-fields [name="sector"]').fill('Robotics');
 await page.locator('#cms-create-fields [name="summary"]').fill('Useful visual language');
 const auto=await page.locator('#cms-create-slug').inputValue();
 expect(auto).toMatch(/^modern-robotics-[a-z0-9]{6}$/);
 await page.locator('#cms-create-form button[type="submit"]').click();
 await expect(page.locator('#cms-create-dialog')).not.toHaveJSProperty('open',true);
 await expect(page.locator('#cms-editor-body')).toBeVisible();
 expect(records.site.slug).toBe(auto);
 expect(records.site.payload.name).toBe('Modern Robotics');
 expect(records.site.status).toBe('draft');
});

test('V55.1 Chinese title gets safe URL and advanced override stays stable',async({page})=>{
 const {records}=await mockCms(page);
 await page.goto(origin+'/admin/content?kind=site');
 await page.locator('#cms-new').click();
 await page.locator('#cms-create-fields [name="name"]').fill('智能制造设计');
 await expect(page.locator('#cms-create-slug')).toHaveValue(/^site-\d{8}-[a-z0-9]{6}$/);
 await page.locator('#cms-create-advanced summary').click();
 await page.locator('#cms-create-slug').fill('custom-industrial-guide');
 await page.locator('#cms-create-fields [name="name"]').fill('智能制造案例');
 await expect(page.locator('#cms-create-slug')).toHaveValue('custom-industrial-guide');
 await page.locator('#cms-create-slug-auto').click();
 await expect(page.locator('#cms-create-slug')).toHaveValue(/^site-\d{8}-[a-z0-9]{6}$/);
 await page.locator('#cms-create-slug').fill('custom-industrial-guide');
 await page.locator('#cms-create-fields [name="url"]').fill('https://factory.example');
 await page.locator('#cms-create-fields [name="sector"]').fill('工业制造');
 await page.locator('#cms-create-fields [name="summary"]').fill('案例描述');
 await page.locator('#cms-create-form button[type="submit"]').click();
 await expect(page.locator('#cms-editor-body')).toBeVisible();
 expect(records.site.slug).toBe('custom-industrial-guide');
});

test('V55.1 article author defaults and modules choose an actual site',async({page})=>{
 const {records}=await mockCms(page);
 await page.goto(origin+'/admin/content?kind=article');
 await page.locator('#cms-new').click();
 await expect(page.locator('#cms-create-kind')).toHaveValue('article');
 await page.locator('#cms-create-fields [name="name"]').fill('设计研究');
 await page.locator('#cms-create-fields [name="sector"]').selectOption('research');
 await page.locator('#cms-create-fields [name="summary"]').fill('观察与实践');
 await page.locator('#cms-create-form button[type="submit"]').click();
 await expect(page.locator('#cms-editor-body')).toBeVisible();
 expect(records.article.payload.author).toBe('B2B Atlas 编辑部');
 await page.locator('[data-close-editor]').click();
 await page.locator('[data-kind-link="module"]').click();
 await page.locator('#cms-new').click();
 await expect(page.locator('#cms-create-fields [name="site_id"]')).toHaveJSProperty('tagName','SELECT');
 await expect(page.locator('#cms-create-fields [name="site_id"] option')).toContainText(['请选择已公开的网站','Atlas Demo · demo-site']);
});

test('V55.1 duplicate URL leaves dialog editable and shows clear error',async({page})=>{
 await mockCms(page);
 await page.goto(origin+'/admin/content?kind=site');
 await page.locator('#cms-new').click();
 await page.locator('#cms-create-fields [name="name"]').fill('Existing item');
 await page.locator('#cms-create-fields [name="url"]').fill('https://existing.example');
 await page.locator('#cms-create-fields [name="sector"]').fill('Industrial');
 await page.locator('#cms-create-fields [name="summary"]').fill('A collision example');
 await page.locator('#cms-create-advanced summary').click();
 await page.locator('#cms-create-slug').fill('demo-site');
 await page.locator('#cms-create-form button[type="submit"]').click();
 await expect(page.locator('#cms-create-dialog')).toHaveJSProperty('open',true);
 await expect(page.locator('#cms-create-error')).toContainText('网址标识已被使用');
 await page.locator('#cms-create-slug').fill('brand-new-item');
 await page.locator('#cms-create-form button[type="submit"]').click();
 await expect(page.locator('#cms-create-dialog')).not.toHaveJSProperty('open',true);
});

test('V55.2 article quick insert focuses a new paragraph and preserves content',async({page})=>{
 const {records}=await mockCms(page);
 records.article.payload.sections=[{title:'Buyer research',blocks:[{type:'paragraph',text:'Starting paragraph'}]}];
 await page.goto(origin+'/admin/content?kind=article&edit=demo-article');
 await expect(page.locator('[data-block-quick="paragraph"]')).toBeVisible();
 await expect(page.locator('[data-block-quick="image"]')).toBeVisible();
 await expect(page.locator('.cms-v552-optional-content')).not.toHaveAttribute('open','');
 await page.locator('[data-block-quick="paragraph"]').click();
 await expect(page.locator('[data-cms-block]')).toHaveCount(2);
 const paragraph=page.locator('[data-cms-block]').last().locator('[data-block-text]');
 await expect(paragraph).toBeFocused();
 await paragraph.fill('A buyer-friendly landing page helps conversion.');
 await expect(page.locator('#cms-autosave-status')).toContainText('草稿已保存',{timeout:10000});
 expect(records.article.payload.sections[0].blocks.at(-1).text).toBe('A buyer-friendly landing page helps conversion.');
 await expect(page.locator('[data-article-undo]')).toBeEnabled();
});

test('V55.2 one-click article image opens the focused picker and preserves draft',async({page})=>{
 const {records}=await mockCms(page);
 records.article.payload.sections=[{title:'Screenshots',blocks:[{type:'paragraph',text:'Study'}]}];
 await page.goto(origin+'/admin/content?kind=article&edit=demo-article');
 await page.locator('[data-block-quick="image"]').click();
 await expect(page.locator('[data-cms-block]')).toHaveCount(2);
 await expect(page.locator('#cms-media-dialog')).toHaveJSProperty('open',true);
 await expect(page.locator('#cms-media-dialog-title')).toHaveText('插入文章图片');
 await page.locator('#cms-media-file').setInputFiles({name:'article-study.png',mimeType:'image/png',buffer:png});
 await expect(page.locator('#cms-media-dialog')).not.toHaveJSProperty('open',true);
 const image=page.locator('[data-cms-block]').last();
 await expect(image).toHaveAttribute('data-block-type','image');
 await expect(image.locator('[data-block-image]')).toHaveValue(/^\/api\/media\//);
 await expect(page.locator('#cms-article-health-status')).toContainText('需要处理');
 await image.locator('[data-block-alt]').fill('Product screenshot for industrial buyers');
 await expect(page.locator('#cms-autosave-status')).toContainText('草稿已保存',{timeout:10000});
 expect(records.article.payload.sections[0].blocks.at(-1).alt).toBe('Product screenshot for industrial buyers');
});

test('V55.2 optional article metadata and advanced blocks stay available',async({page})=>{
 const {records}=await mockCms(page);
 records.article.payload.sections=[{title:'Research',blocks:[{type:'paragraph',text:'B2B'}]}];
 await page.goto(origin+'/admin/content?kind=article&edit=demo-article');
 await expect(page.locator('#v51-tags')).toBeHidden();
 await page.locator('.cms-v552-optional-content summary').click();
 await expect(page.locator('#v51-tags')).toBeVisible();
 await page.locator('#v51-tags').fill('design\nindustrial');
 await expect(page.locator('.cms-v552-more-blocks')).not.toHaveAttribute('open','');
 await page.locator('.cms-v552-more-blocks summary').click();
 await page.locator('[data-block-add-type]').selectOption('quote');
 await page.locator('[data-block-add]').click();
 await expect(page.locator('[data-cms-block]').last()).toHaveAttribute('data-block-type','quote');
 await page.locator('[data-cms-block]').last().locator('[data-block-text]').fill('Evidence matters');
 await expect(page.locator('#cms-autosave-status')).toContainText('草稿已保存',{timeout:10000});
 expect(records.article.payload.tags).toEqual(['design','industrial']);
 expect(records.article.payload.sections[0].blocks.at(-1).text).toBe('Evidence matters');
});

test('V55.2 simplified article controls fit narrow mobile and reviewer stays read only',async({page})=>{
 await mockCms(page,'reviewer');
 await page.setViewportSize({width:320,height:760});
 await page.goto(origin+'/admin/content?kind=article&edit=demo-article');
 await expect(page.locator('[data-block-quick]')).toHaveCount(0);
 await expect(page.locator('.cms-v552-studio')).toBeVisible();
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth+1)).toBe(true);
});
