/* B2B Atlas CMS V47 — data-backed editor. No third-party dependencies.
   Public preview loads only public source data; all editing requires server auth. */
(()=>{
'use strict';
const $=q=>document.querySelector(q), $$=q=>Array.from(document.querySelectorAll(q));
const icon=n=>'<svg class="icon" aria-hidden="true"><use href="#i-'+n+'"></use></svg>';
const h=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const mode=document.body.dataset.cmsMode==='admin'?'admin':'preview';
const kinds={site:{title:'网站内容',label:'Websites',icon:'globe',public:'/api/source-library',url:'/websites/'},
 module:{title:'页面模块',label:'Sections',icon:'layers',public:'/api/module-library',url:'/sections/'},
 pattern:{title:'设计模式',label:'Patterns',icon:'shapes',public:'/assets/patterns.json',url:'/patterns/'},
 article:{title:'研究文章',label:'Insights',icon:'article',public:'/assets/articles.json',url:'/insights/'}};
const state={kind:new URLSearchParams(location.search).get('kind')||'site',items:[],records:{},selected:null,mediaField:null,csrf:'',user:null,dirty:false,q:'',status:'',busy:false,selectedSlugs:new Set(),taxonomy:{},tagSuggestions:[],mediaTarget:null,categoryRecords:[],categoryEditing:null,tagRecords:[],tagEditing:null,tagSearch:'',role:null,capabilities:[],scheduleItems:[],teamPeople:[],teamSelected:null,siteChoices:[]};
if(!kinds[state.kind])state.kind='site';
const fieldSpecs={
 site:[
  ['name','网站名称','text',true],['url','官网 URL','url',true],['sector','所属行业','text',true],['summary','案例描述','long',true],
  ['focus','业务聚焦','text'],['model','业务模式','text'],['takeaway','设计启示','long'],['visual_style','视觉风格','text'],
  ['screenshot_url','站内截图路径','text'],['domain','网站域名','text'],['design_strengths','设计优势（JSON 数组）','json'],
  ['featured','精选案例','bool']
 ],
 module:[
  ['title','模块标题','text',true],['site_id','关联网站 ID','text',true],['category','模块分类','text',true],['lesson','设计方法摘要','long',true],
  ['summary','模块说明','long'],['url','原始页面','url'],['screenshot_url','模块截图路径','text'],
  ['type','模块类型','text'],['crop_px','截图区域（JSON 数组）','json']
 ],
 pattern:[
  ['title','模式名称','text',true],['family','模式类别','text',true],['question','设计问题','long',true],
  ['principle','核心原则','long',true],['compare','比较视角','long'],['when','适用场景','long'],
  ['modules','关联模块 ID（JSON 数组）','json']
 ],
 article:[
  ['title','文章标题','text',true],['subtitle','文章摘要','long',true],['category','文章分类','text',true],
  ['author','作者','text',true],['seo_title','SEO 标题','text'],['seo_description','SEO 描述','long'],['cover_site','封面关联网站 ID','text'],['cover_image','媒体封面 URL','text'],['published_at','发布日期（YYYY-MM-DD）','text'],
  ['reading_minutes','阅读时长（分钟）','number'],['featured','精选文章','bool'],
  ['tags','关键词（JSON 数组）','json'],['takeaways','核心观点（JSON 数组）','json'],
  ['sections','文章章节（JSON 数组）','json'],['references','关联引用（JSON 数组）','json']
 ]
};
const statusText={source:'原始收录 · 可编辑',draft:'草稿',review:'待审核',published:'后台已发布',archived:'已归档',public:'公开内容'};
let toastTimer=0;
function message(text,success=true){const el=$('#cms-toast');el.textContent=text;el.classList.add('show');clearTimeout(toastTimer);toastTimer=setTimeout(()=>el.classList.remove('show'),3200);if(!success)console.warn('CMS',text)}
function theme(saved=false){try{const s=localStorage.getItem('atlas-admin-theme');return s==='dark'?'dark':'light'}catch{return 'light'}}
function setTheme(value){document.documentElement.dataset.theme=value;document.documentElement.style.colorScheme=value;$$('[data-set-theme]').forEach(x=>x.setAttribute('aria-pressed',String(x.dataset.setTheme===value)));const meta=$('meta[name=theme-color]');if(meta)meta.content=value==='dark'?'#0b111c':'#f5f7fb';try{localStorage.setItem('atlas-admin-theme',value)}catch{}}
async function api(path,options={}){
 const headers={Accept:'application/json',...options.headers};
 if(options.body)headers['Content-Type']='application/json';
 if(options.method&&!['GET','HEAD'].includes(options.method.toUpperCase())&&state.csrf)headers['X-CSRF-Token']=state.csrf;
 const r=await fetch(path,{...options,headers,credentials:'same-origin',cache:'no-store'});
 let v={};try{v=await r.json()}catch{}
 if(!r.ok){const e=Error(typeof v.detail==='string'?v.detail:r.status===403?'管理员权限不足':r.status===401?'请先登录':'内容接口错误 HTTP '+r.status);e.status=r.status;throw e}
 return v;
}
// V51.13 · Network-backed autosave, optimistic revision lock and tab recovery.
let autosaveTimer=0,editGeneration=0,autosavePaused=false;
function autosaveLabel(text,kind=''){
 const el=$('#cms-autosave-status');if(el){el.textContent=text;el.dataset.state=kind}
}
function recoveryKey(){
 return 'atlas-cms-working-v1:'+(state.user?.id||'admin')+':'+state.selected?.kind+':'+state.selected?.slug;
}
function clearRecovery(key){try{sessionStorage.removeItem(key||recoveryKey())}catch(_){}}
function keepRecovery(payload){
 if(!state.selected||mode!=='admin')return;
 try{sessionStorage.setItem(recoveryKey(),JSON.stringify({
  revision:state.selected.revision,updatedAt:Date.now(),payload
 }))}catch(_){}
}
function markDraftDirty(){
 if(mode!=='admin'||!state.selected)return;
 state.dirty=true;editGeneration++;
 autosaveLabel('修改未保存 · 3 秒后自动保存','pending');
 clearTimeout(autosaveTimer);
 if(!autosavePaused)autosaveTimer=setTimeout(()=>persistDraft(true),3200);
 try{keepRecovery(takeFields())}catch(_){}
}
function applyDraftResult(target,res,payload){
 target.revision=res.revision;target.status='draft';target.payload=payload;
 const version=$('.cms-editor-meta strong');if(version)version.textContent='v'+res.revision;
 const status=$('.cms-editor-meta .cms-item-state, .cms-easy-header-side .cms-item-state');
 if(status){status.dataset.status='draft';status.textContent=statusText.draft}
 const submit=$('#cms-edit-form [data-transition="submit"]');
 const quickSubmit=$('[data-editor-submit]');if(quickSubmit)quickSubmit.disabled=false;
 const publish=$('#cms-edit-form [data-transition="publish"]');
 const archive=$('#cms-edit-form [data-transition="archive"]');
 if(submit)submit.disabled=false;
 if(publish)publish.disabled=true;
 if(archive)archive.disabled=true;
 const row=state.items.find(x=>x.slug===target.slug);
 if(row){row.revision=res.revision;row.status='draft';drawItems();updateSummary()}
}
async function persistDraft(automatic=false){
 clearTimeout(autosaveTimer);
 if(mode!=='admin'||!state.selected||!state.dirty||autosavePaused)return false;
 if(state.busy){if(automatic)autosaveTimer=setTimeout(()=>persistDraft(true),1600);return false}
 const target=state.selected,generation=editGeneration;
 let payload;
 try{payload=takeFields()}catch(e){
   autosaveLabel('保存检查未通过：'+e.message,'error');
   if(!automatic)message(e.message,false);return false
 }
 const cache=recoveryKey();keepRecovery(payload);
 btnDisable(true);autosaveLabel(automatic?'正在自动保存…':'正在保存草稿…','saving');
 try{
   const res=await api('/api/admin/content/'+target.kind+'/'+target.slug,{
     method:'PUT',body:JSON.stringify({payload,expected_revision:target.revision})});
   applyDraftResult(target,res,payload);
   if(generation===editGeneration&&state.selected===target){
     state.dirty=false;clearRecovery(cache);
     autosaveLabel('草稿已保存 · v'+res.revision,'saved');
   }else{
     state.dirty=true;
     autosaveLabel('上一版已保存，继续同步最新修改…','pending');
   }
   if(!automatic)message('草稿已保存 · v'+res.revision);
   return true;
 }catch(e){
   if(e.status===409){
     autosavePaused=true;
     autosaveLabel('版本冲突 · 自动保存已暂停，请备份本地编辑后刷新。','error');
   }else autosaveLabel('保存失败：'+e.message+' · 可手动重试','error');
   if(!automatic)message(e.message,false);
   return false
 }finally{
   btnDisable(false);
   if(state.dirty&&!autosavePaused&&generation!==editGeneration)
     autosaveTimer=setTimeout(()=>persistDraft(true),1400);
 }
}
async function offerDraftRecovery(item){
 if(mode!=='admin')return;
 try{
   const key=recoveryKey(),cache=JSON.parse(sessionStorage.getItem(key)||'null');
   if(!cache)return;
   if(!cache.payload||cache.revision!==item.revision||Date.now()-cache.updatedAt>86400000){
     clearRecovery(key);return
   }
   if(JSON.stringify(cache.payload)===JSON.stringify(item.payload)){clearRecovery(key);return}
   if(confirm('此标签页存在未提交的内容修改。是否恢复并自动保存为草稿？')){
     state.selected.payload=cache.payload;
     renderForm(state.selected);
     clearRecovery(key);markDraftDirty();
   }else clearRecovery(key)
 }catch(_){}
}
function can(permission){return mode==='admin'&&state.capabilities.includes(permission)}
function markWorkspace(name){
 for(const element of $$('[data-workspace-link]')){
   const active=element.dataset.workspaceLink===name;
   element.classList.toggle('active',active);
   if(active)element.setAttribute('aria-current','page');
   else element.removeAttribute('aria-current');
 }
}
function setEditorTab(tab){
 const root=$('#cms-editor-body');if(!root||root.hidden)return;
 const options=Array.from(root.querySelectorAll('[data-editor-tab]'));
 const selected=options.some(x=>x.dataset.editorTab===tab)?tab:'content';
 state.editorTab=selected;
 for(const button of options){
   const active=button.dataset.editorTab===selected;
   button.setAttribute('aria-selected',String(active));
   button.tabIndex=active?0:-1;
 }
 for(const pane of root.querySelectorAll('[data-editor-pane]'))
   pane.hidden=pane.dataset.editorPane!==selected;
}
async function logoutCms(){
 if(state.busy){message('草稿正在保存，请稍后再退出。',false);return}
 if(state.dirty&&!confirm('有尚未保存的修改。确认退出登录？'))return;
 const btn=$('#cms-logout');btn.disabled=true;
 try{await api('/api/auth/logout',{method:'POST'});
   location.assign('/login?next=%2Fadmin%2Fcontent');
 }catch(err){btn.disabled=false;message('退出失败：'+err.message,false)}
}
function setCmsRole(){
 const title={owner:'最高管理员',editor:'内容编辑',reviewer:'审核员'}[state.role]||'未授权';
 $('#cms-role').textContent=(state.user?.display_name||'Atlas')+' · '+title;
 $('#cms-logout').hidden=mode!=='admin';
 $('#cms-tools-menu').hidden=!(can('media')||can('taxonomy')||can('team')||can('export'));
 $$('[data-owner-only]').forEach(el=>el.hidden=!can('team'));
 $('#cms-new').hidden=!can('edit');
 $('#cms-export').hidden=!can('export');
 $('#cms-media-open').hidden=!can('media');
 $('#cms-categories-open').hidden=!can('taxonomy');
 $('#cms-tags-open').hidden=!can('taxonomy');
 $('#cms-team-open').hidden=!can('team');
 $('#cms-schedules-open').hidden=!can('view');
 $('#cms-review-shortcut').hidden=!can('view');
 $$('.side-nav a[href="/admin"],.side-nav a[href="/admin#traffic"]').forEach(a=>a.hidden=!can('team'));
 const options=[];
 if(can('edit'))options.push(['submit','提交审核']);
 if(can('review'))options.push(['publish','批量发布'],['archive','归档下线']);
 $('#cms-bulk-action').innerHTML=options.map(([key,label])=>'<option value="'+key+'">'+label+'</option>').join('');
}
function btnDisable(value){state.busy=value;$$('#cms-editor-body button,#cms-new,#cms-refresh,#cms-export').forEach(x=>{if(!x.dataset.alwaysEnabled)x.disabled=value})}
function setNotice(text){const el=$('#cms-notice');el.innerHTML='<div>'+icon(mode==='preview'?'lock':'check')+'<span>'+h(text)+'</span></div><span>'+(mode==='preview'?'PUBLIC PREVIEW':'ADMIN ONLY')+'</span>'}
function listUrl(){const u=new URL(location.href);u.searchParams.set('kind',state.kind);return u.pathname+u.search}
function showKind(){
 $('#cms-current-kind').textContent=kinds[state.kind].label.toUpperCase();
 $('#cms-browser-title').textContent=kinds[state.kind].title;
 $$('[data-kind-link]').forEach(a=>{a.classList.toggle('active',a.dataset.kindLink===state.kind);a.href='?kind='+a.dataset.kindLink});
 $('#cms-create-kind').value=state.kind;
}
function stateClasses(x){return '<span class="cms-item-state" data-status="'+h(x)+'">'+h(statusText[x]||x)+'</span>'}
function updateSummary(){
 const counts={source:0,draft:0,review:0,published:0,archived:0,public:0};
 for(const x of state.items)counts[x.status]=(counts[x.status]||0)+1;
 const numbers=[state.items.length,counts.source+counts.public,counts.draft,counts.review,counts.published];
 $$('.cms-metric strong').forEach((el,i)=>el.textContent=numbers[i].toLocaleString('zh-CN'));
}
function listFiltered(){
 const q=state.q.toLowerCase().trim();
 return state.items.filter(x=>(!state.status||x.status===state.status)&&(!q||(x.label+' '+x.sector+' '+x.slug).toLowerCase().includes(q)));
}
function setStudioMode(editing){
 const layout=$('.cms-split');if(layout)layout.classList.toggle('cms-editing',Boolean(editing));
 document.body.classList.toggle('cms-editor-active',Boolean(editing));
 const metrics=$('#cms-metrics');if(metrics)metrics.hidden=Boolean(editing);
 const guide=$('.cms-workflow-guide');if(guide)guide.hidden=Boolean(editing);
}
function editorUrl(slug){
 const url=new URL(location.href);url.searchParams.set('kind',state.kind);
 url.searchParams.delete('edit');url.searchParams.delete('workspace');url.searchParams.delete('status');
 if(slug)url.searchParams.set('edit',slug);
 return url.pathname+url.search;
}
function closeEditor(push=true){
 if(state.busy){message('草稿正在保存，请完成后返回。',false);return false}
 if(state.dirty&&!confirm('修改尚未保存，确定放弃并返回内容列表吗？'))return false;
 clearTimeout(autosaveTimer);editGeneration++;autosavePaused=false;
 if(state.dirty)clearRecovery();state.dirty=false;state.selected=null;
 $('#cms-editor-body').hidden=true;$('#cms-empty').hidden=false;
 setStudioMode(false);drawItems();
 if(push)history.pushState({},'',editorUrl(null));
 return true;
}
function rowImage(x){
 if(x.kind==='site')return '/screenshots/sites/'+x.slug+'.webp';
 if(x.kind==='module')return '/screenshots/modules/'+x.slug+'.webp';
 return '';
}
function drawItems(){
 const items=listFiltered(),root=$('#cms-items');
 root.innerHTML=items.length?items.map(item=>{
   const img=rowImage(item),actionLabel=can('edit')?'编辑内容':can('review')?'查看并审核':'查看内容';
   return '<div class="cms-v51-row">'+(mode==='admin'?'<label class="cms-v51-select" aria-label="选择 '+h(item.label)+'"><input type="checkbox" data-bulk-select="'+h(item.slug)+'" '+(state.selectedSlugs.has(item.slug)?'checked':'')+'></label>':'')+'<button type="button" class="cms-item '+(state.selected?.slug===item.slug?'active':'')+'" data-pick="'+h(item.slug)+'" aria-label="'+actionLabel+'：'+h(item.label)+'">'
   +'<span class="cms-item-thumb">'+(img?'<img src="'+h(img)+'" loading="lazy" alt="">':icon(kinds[state.kind].icon))+'</span>'
   +'<span class="cms-item-copy"><strong>'+h(item.label)+'</strong><small>'+h(item.sector||item.slug)+'</small><small class="cms-item-open-label">'+actionLabel+' →</small></span>'
   +stateClasses(item.status)+'</button></div>';
 }).join(''):'<div class="cms-loading">没有符合条件的内容。可清除筛选或创建新内容。</div>';
 $('#cms-count').textContent=items.length+' ITEMS';
 $('#cms-browser-footer').textContent=items.length+' / '+state.items.length+' 条记录';
  // Bulk actions are progressive enhancement: never discard a loaded content list if toolbar rendering fails.
  try{updateBulkToolbar()}catch(error){
    console.error('[CMS] bulk toolbar rendering failed; content list remains available',error);
    const toolbar=$('#cms-bulk-toolbar');if(toolbar)toolbar.hidden=true;
  }
}
async function loadKind(keep=false){
 showKind();
 $('#cms-items').innerHTML='<div class="cms-loading">正在读取内容…</div>';
 let records=[],items=[];
 if(mode==='admin'){
   const res=await api('/api/admin/content?kind='+state.kind);
   items=res.items;
 }else{
   const json=await api(kinds[state.kind].public);
   records=state.kind==='site'?json.sites:state.kind==='module'?json.modules:state.kind==='article'?json.articles:json;
   for(const p of records){const slug=p.id;state.records[slug]=p;
    items.push({kind:state.kind,slug,label:p.name||p.title||slug,status:'public',source:'repository',revision:0,
     url:kinds[state.kind].url+slug,sector:p.sector||p.category||p.family||''});
   }
   items.sort((a,b)=>a.label.localeCompare(b.label,'zh'));
 }
 state.items=items;state.selectedSlugs.clear();updateSummary();drawItems();
 if(keep&&state.selected){const target=items.find(x=>x.slug===state.selected.slug);if(target)await selectItem(target.slug)}
}
function formField(spec,values,editable){
 const [name,label,type,required]=spec,value=values[name]??((type==='json'||type==='lines')?[]:type==='bool'?false:'');
 const inputName='field-'+name,disabled=editable?'':' disabled';
 const mediaField=(name==='cover_image'||name==='screenshot_url')&&editable&&can('media');
 const attr='id="'+inputName+'" data-field="'+h(name)+'" data-type="'+h(type)+'"';
 let input='';
 if(name==='sector'&&state.kind==='site'&&type==='text'){
   input='<input '+attr+disabled+' list="cms-site-sector-options" type="text" value="'+h(value)+'"'+(required?' required':'')+' placeholder="例如 工业制造">';
 }
 else if(name==='site_id'&&state.kind==='module'&&state.siteChoices.length){
   const options=state.siteChoices;
   input='<select '+attr+disabled+' required><option value="">选择关联的网站案例</option>'
     +(!options.some(x=>x.id===value)&&value?'<option value="'+h(value)+'" selected>'+h(value)+'（现有案例）</option>':'')
     +options.map(x=>'<option value="'+h(x.id)+'"'+(value===x.id?' selected':'')+'>'+h(x.name||x.id)+'</option>').join('')+'</select>';
 }
 else if(name==='category'&&state.kind==='article'){
   const items=state.categoryRecords.length?state.categoryRecords.map(x=>({id:x.id,name:x.name})):
     (state.taxonomy.article||[]).map(id=>({id,name:id}));
   if(value&&!items.some(x=>x.id===value))items.unshift({id:value,name:value+'（待核对）'});
   input='<select '+attr+disabled+' required><option value="">选择文章分类</option>'
     +items.map(x=>'<option value="'+h(x.id)+'"'+(value===x.id?' selected':'')+'>'+h(x.name)+' · '+h(x.id)+'</option>').join('')+'</select>';
 }
 else if(type==='bool')input='<select '+attr+disabled+'><option value="false"'+(!value?' selected':'')+'>否</option><option value="true"'+(value?' selected':'')+'>是</option></select>';
 else if(type==='json'){
   const pretty=typeof value==='string'?value:JSON.stringify(value,null,2);
   input='<textarea '+attr+disabled+' rows="7" spellcheck="false">'+h(pretty)+'</textarea>';
 }else if(type==='lines')input='<textarea '+attr+disabled+' rows="4" placeholder="每行写一条设计亮点">'+h(Array.isArray(value)?value.join('\n'):String(value||''))+'</textarea>';
 else if(type==='long')input='<textarea '+attr+disabled+' rows="4"'+(required?' required':'')+'>'+h(value)+'</textarea>';
 else input='<input '+attr+(name==='category'&&state.kind==='article'?' list="v51-categories"':'')+disabled+' type="'+(type==='url'?'url':type==='number'?'number':'text')+'" value="'+h(value)+'"'+(required?' required':'')+'>';
 return '<div class="cms-field" data-json="'+(type==='json')+'" data-multiline="'+(type==='long')+'"><label for="'+inputName+'">'+h(label)+(required?' *':'')+'</label>'+input+(mediaField?'<button type="button" class="cms-field-media-pick" data-editor-pick-media="'+h(inputName)+'">从媒体库选择或上传图片</button>':'')+'</div>';
}
// V52.1 · A small, beginner-friendly site editor. Keep source fields, not a JSON textarea.
function validSiteShot(url){
 return typeof url==='string'&&((/^\/screenshots\/[a-zA-Z0-9_./-]{1,200}$/.test(url)&&!url.includes('..'))||/^\/api\/media\/[0-9a-f-]{36}$/.test(url));
}
function galleryValue(){
 try{const items=JSON.parse($('#field-gallery')?.value||'[]');
  return Array.isArray(items)?items.filter(x=>x&&validSiteShot(x.url)).slice(0,16):[];
 }catch{return []}
}
function galleryCards(items){
 const editable=can('edit');
 if(!items.length)return '<p class="cms-gallery-empty">还没有其他页面截图。上传产品页、解决方案页、移动端等截图，案例详情页就能切换查看。</p>';
 return items.map((x,i)=>'<article class="cms-gallery-card" data-gallery-index="'+i+'">'
 +'<img class="cms-gallery-thumb" src="'+h(x.url)+'" alt="'+h(x.label||'页面截图')+'" loading="lazy">'
 +'<div class="cms-gallery-info"><label>截图名称<input type="text" data-gallery-label maxlength="80" value="'+h(x.label||'')+'" placeholder="例如 产品详情页"'+(editable?'':' disabled')+'></label>'
 +'<div class="cms-gallery-actions">'+(editable?'<button type="button" data-gallery-cover="'+i+'">设为封面</button>'
 +'<button type="button" data-gallery-move="'+i+'" data-gallery-direction="-1"'+(i===0?' disabled':'')+' aria-label="前移截图">↑</button>'
 +'<button type="button" data-gallery-move="'+i+'" data-gallery-direction="1"'+(i===items.length-1?' disabled':'')+' aria-label="后移截图">↓</button>'
 +'<button type="button" data-gallery-remove="'+i+'" class="cms-gallery-delete">移除</button>':'')+'</div></div></article>').join('');
}
function renderGalleryCards(){
 const list=$('#cms-gallery-list');if(!list)return;
 const gallery=galleryValue();list.innerHTML=galleryCards(gallery);
 const count=$('#cms-gallery-count');if(count)count.textContent=gallery.length+' 张';
}
function updateGallery(gallery){
 const input=$('#field-gallery');if(!input)return;
 input.value=JSON.stringify(gallery);renderGalleryCards();markDraftDirty();
}
function syncGalleryLabels(){
 const gallery=galleryValue(),input=$('#field-gallery');if(!input)return;
 for(const row of document.querySelectorAll('[data-gallery-index]')){
  const idx=Number(row.dataset.galleryIndex);
  if(gallery[idx])gallery[idx].label=row.querySelector('[data-gallery-label]')?.value.trim().slice(0,80)||'';
 }
 input.value=JSON.stringify(gallery);markDraftDirty();
}
function addGalleryImages(urls){
 const gallery=galleryValue();let added=0;
 for(const url of urls){
  if(!validSiteShot(url)||gallery.some(x=>x.url===url))continue;
  if(gallery.length>=16){message('最多可以添加 16 张页面截图。',false);break}
  gallery.push({url,label:'页面截图 '+(gallery.length+1)});added++;
 }
 if(added){updateGallery(gallery);message('已添加 '+added+' 张页面截图，草稿会自动保存。')}
 else message('这些图片已添加，或已达到 16 张上限。',false);
 return added;
}
function siteEditorForm(values,editable){
 const disabled=editable?'':' disabled';
 const basic=[
   ['name','网站名称','text',true],
   ['url','网站网址','url',true],
   ['sector','所属行业','text',true],
   ['summary','案例简介','long',true]
 ];
 const extra=[
   ['focus','业务方向','text'],
   ['model','业务模式','text'],
   ['takeaway','值得借鉴的设计','long'],
   ['visual_style','视觉风格','text'],
   ['domain','网站域名','text'],
   ['design_strengths','设计亮点（每行一条）','lines'],
   ['featured','设为精选案例','bool']
 ];
 const raw=String(values.screenshot_url||'');
 const picture=/^\/screenshots\/[a-zA-Z0-9_./-]{1,200}$/.test(raw)&&!raw.includes('..')||
   /^\/api\/media\/[0-9a-f-]{36}$/.test(raw);
 return '<section class="cms-easy-intro"><div><h3>基本信息</h3><p>左侧修改内容，右侧选择封面图片。更改会自动保存为草稿。</p></div></section>'
 +'<div class="cms-easy-layout"><div class="cms-easy-fields">'
 +basic.map(spec=>formField(spec,values,editable)).join('')
 +'<datalist id="cms-site-sector-options"><option value="工业制造"><option value="工业软件"><option value="机器人"><option value="新能源"><option value="医疗科技"><option value="航空航天"></datalist>'
 +'</div><aside class="cms-easy-visual"><strong>案例封面</strong><p>这张图片会用于网站案例展示。</p>'
 +'<div class="cms-easy-shot"><img id="cms-site-image" src="'+(picture?h(raw):'')+'" alt="案例封面预览"'+(picture?'':' hidden')+'>'
 +'<div id="cms-site-image-empty"'+(picture?' hidden':'')+'>还没有设置封面图片</div></div>'
 +'<input id="field-screenshot_url" data-field="screenshot_url" data-type="text" type="hidden" value="'+h(raw)+'">'
 +(editable&&can('media')?'<button type="button" class="cms-easy-upload" data-editor-pick-media="field-screenshot_url">上传或更换图片</button>':'')
 +'<small>支持 JPG、PNG、WebP；已有图片也可从媒体库选用。</small></aside></div>'
 +'<section class="cms-gallery-editor"><div class="cms-gallery-heading"><div><strong>页面截图 <span id="cms-gallery-count">'+(Array.isArray(values.gallery)?values.gallery.length:0)+' 张</span></strong><p>添加产品页、方案页等图片；可调整顺序、重命名或设为主封面。</p></div>'
 +(editable&&can('media')?'<button type="button" data-gallery-add>＋ 添加截图</button>':'')+'</div>'
 +'<input id="field-gallery" type="hidden" data-field="gallery" data-type="json" value="'+h(JSON.stringify(Array.isArray(values.gallery)?values.gallery:[]))+'">'
 +'<div id="cms-gallery-list" class="cms-gallery-list">'+galleryCards(Array.isArray(values.gallery)?values.gallery.filter(x=>x&&validSiteShot(x.url)).slice(0,16):[])+'</div></section>'
 +'<details class="cms-easy-advanced"><summary>更多设置 <span>选填 · 业务方向、设计亮点</span></summary>'
 +'<div class="cms-easy-extra">'+extra.map(spec=>formField(spec,values,editable)).join('')+'</div></details>';
}
// V52.4: Plain-language editors share the same focused layout without modifying CMS payload schemas.
function easyImagePreview(field,values,editable,explanation){
 const url=String(values[field]||''),valid=validSiteShot(url);
 return '<aside class="cms-easy-visual"><strong>展示图片</strong><p>'+h(explanation)+'</p>'
  +'<div class="cms-easy-shot"><img id="cms-site-image" src="'+(valid?h(url):'')+'" alt="当前图片"'+(valid?'':' hidden')+'>'
  +'<div id="cms-site-image-empty"'+(valid?' hidden':'')+'>暂未添加图片</div></div>'
  +'<input type="hidden" id="field-'+field+'" data-field="'+field+'" data-type="text" value="'+h(url)+'">'
  +(editable&&can('media')?'<button type="button" class="cms-easy-upload" data-editor-pick-media="field-'+field+'">选择或上传图片</button>':'')
  +'<small>从媒体库选择现有图片，或上传 JPG、PNG、WebP。</small></aside>';
}
function simpleEditorForm(kind,values,editable){
 let title='基本信息',description='',basic=[],extra=[],aside='';
 if(kind==='module'){
   title='编辑页面模块';description='填写模块标题、所属网站和设计说明，右侧可更换截图。';
   basic=[['title','模块标题','text',true],['site_id','所属网站','text',true],
     ['category','模块分类','text',true],['lesson','设计方法','long',true],['summary','模块介绍','long']];
   extra=[['url','原始页面链接','url'],['type','模块类型','text']];
   aside=easyImagePreview('screenshot_url',values,editable,'这张截图会展示在页面模块卡片和详情页中。');
 }else if(kind==='pattern'){
   title='编辑设计模式';description='描述设计要解决的问题、核心方法，以及适合什么场景。';
   basic=[['title','模式名称','text',true],['family','所属类别','text',true],
     ['question','解决什么问题','long',true],['principle','核心设计原则','long',true]];
   extra=[['when','适用场景','long'],['compare','可以比较什么','long'],
     ['modules','关联模块标识（每行一个）','lines']];
   aside='<aside class="cms-easy-visual cms-pattern-preview"><strong>即时预览</strong>'
    +'<div class="cms-pattern-preview-card"><small id="cms-preview-category">'+h(values.family||'设计模式')+'</small>'
    +'<h3 id="cms-preview-title">'+h(values.title||'设计模式名称')+'</h3>'
    +'<p id="cms-preview-description">'+h(values.question||'这里会显示设计问题')+'</p>'
    +'<div id="cms-preview-principle">'+h(values.principle||'这里会显示核心设计原则')+'</div></div>'
    +'<small>预览只在当前浏览器显示，未发布的内容不会公开。</small></aside>';
 }else{
   title='文章基本信息';description='先填写标题、摘要和分类，再在下方逐章编辑文章正文。';
   basic=[['title','文章标题','text',true],['subtitle','文章摘要','long',true],
     ['category','文章分类','text',true],['author','作者','text',true]];
   extra=[['seo_title','SEO 标题','text'],['seo_description','SEO 描述','long'],
     ['cover_site','关联网站标识','text'],['published_at','发布日期','text'],
     ['reading_minutes','阅读时长（分钟）','number'],['featured','设为精选文章','bool']];
   aside=easyImagePreview('cover_image',values,editable,'这张封面用于文章列表和详情页展示。');
 }
 return '<section class="cms-easy-intro"><div><h3>'+title+'</h3><p>'+description+'</p></div></section>'
  +'<div class="cms-easy-layout"><div class="cms-easy-fields">'+basic.map(spec=>formField(spec,values,editable)).join('')+'</div>'+aside+'</div>'
  +'<details class="cms-easy-advanced"><summary>更多设置 <span>不常用的内容放在这里</span></summary>'
  +'<div class="cms-easy-extra">'+extra.map(spec=>formField(spec,values,editable)).join('')+'</div></details>';
}
function syncSimplePreview(){
 if(!state.selected)return;
 const kind=state.selected.kind;
 const title=$('.cms-easy-heading h2'),source=$('#field-name')||$('#field-title');
 if(title&&source)title.textContent=source.value.trim()||state.selected.slug;
 if(kind==='pattern'){
  const set=(id,field,fallback)=>{const target=$(id),input=$('#field-'+field);if(target&&input)target.textContent=input.value.trim()||fallback};
  set('#cms-preview-title','title','设计模式名称');
  set('#cms-preview-category','family','设计模式');
  set('#cms-preview-description','question','这里会显示设计问题');
  set('#cms-preview-principle','principle','这里会显示核心设计原则');
 }
}
async function loadSiteChoices(){
 if(state.siteChoices.length)return;
 try{
   const res=await api('/api/source-library');
   state.siteChoices=Array.isArray(res.sites)?res.sites.map(x=>({id:x.id,name:x.name||x.id})): [];
 }catch(e){console.warn('[CMS] site options unavailable',e)}
}
function syncSiteTitle(){
 if(!state.selected)return;
 syncSimplePreview();
}
function syncSiteImage(){
 if(!state.selected||state.selected.kind==='pattern')return;
 const field=$('#field-screenshot_url')||$('#field-cover_image'),img=$('#cms-site-image'),empty=$('#cms-site-image-empty');
 if(!field||!img||!empty)return;
 const value=field.value.trim();
 const safe=(/^\/screenshots\/[a-zA-Z0-9_./-]{1,200}$/.test(value)&&!value.includes('..'))||
   /^\/api\/media\/[0-9a-f-]{36}$/.test(value);
 img.hidden=!safe;empty.hidden=Boolean(safe);
 if(safe&&img.getAttribute('src')!==value)img.src=value;
}
function reviewBrief(item){
 if(mode!=='admin'||item.status!=='review')return '';
 const original=item.published||null,current=item.payload||{};
 const changed=original?Array.from(new Set([...Object.keys(original),...Object.keys(current)])).filter(k=>
   JSON.stringify(original[k]??null)!==JSON.stringify(current[k]??null)):[];
 const labels=Object.fromEntries((fieldSpecs[item.kind]||[]).map(x=>[x[0],x[1]]));
 return '<div class="cms-review-brief"><div class="cms-review-brief-head"><div><span class="section-eyebrow">REVIEW GATE · v'+item.revision+'</span><h3>审核此内容版本</h3>'
 +'<p>对照公开快照检查字段更改，确认后再正式发布。</p></div><span class="cms-review-state">等待审核</span></div>'
 +(original?'<div class="cms-review-changes"><strong>对比已发布内容 · '+changed.length+' 项字段变化</strong>'
 +(changed.length?'<div class="cms-review-chips">'+changed.slice(0,20).map(k=>'<span>'+h(labels[k]||k)+'</span>').join('')+'</div>':'<p>草稿与当前公开内容一致。</p>')+'</div>'
 :'<div class="cms-review-changes"><strong>首次发布审查</strong><p>没有可对比的公开快照，请重点核对媒体、链接和正文。</p></div>')
 +'<p class="cms-review-helper">退回操作会记录审核原因，已发布内容仍保持公开版本。</p>'
 +'<button type="button" class="cms-review-diff-btn" data-review-diff>打开逐段版本对比 ↗</button></div>';
}
async function openReviewDiff(revision=0){
 if(!can('view')||!state.selected)return;
 const item=state.selected,dialog=$('#cms-diff-dialog');
 if(!dialog.open)dialog.showModal();
 $('#cms-diff-results').innerHTML='<p class="cms-loading">正在读取版本快照…</p>';
 $('#cms-diff-summary').textContent='读取中…';
 try{
   const result=await api('/api/admin/content/'+item.kind+'/'+item.slug+'/diff?revision='+Number(revision||0));
   const select=$('#cms-diff-baseline');
   select.innerHTML='<option value="0">当前公开版本</option>'
    +(result.revisions||[]).map(row=>'<option value="'+row.revision+'">历史 v'+row.revision+' · '+h(row.action)+'</option>').join('');
   select.value=String(revision||0);
   $('#cms-diff-left-title').textContent=result.baseline_label;
   const summary=result.summary||{};
   $('#cms-diff-summary').textContent='变化字段 '+result.changed_fields.length+' 项 · 新增 / 修改 '+(summary.added||0)+' 行 · 移除 / 修改 '+(summary.removed||0)+' 行';
   const changes=result.chunks||[];
   $('#cms-diff-results').innerHTML=changes.length?changes.map(chunk=>{
     const total=Math.max(chunk.before?.length||0,chunk.after?.length||0);
     const rows=Array.from({length:Math.max(total,1)},(_,i)=>
       '<div class="cms-diff-row" data-diff-tag="'+h(chunk.tag)+'">'
        +'<pre>'+h(chunk.before?.[i]||'')+'</pre><pre>'+h(chunk.after?.[i]||'')+'</pre></div>').join('');
     return rows+(chunk.collapsed?'<div class="cms-diff-collapsed">… 已折叠 '+chunk.collapsed+' 行未变化正文</div>':'');
   }).join(''):'<p class="cms-loading">暂无正文差异。</p>';
 }catch(e){$('#cms-diff-results').innerHTML='<div class="cms-error">'+h(e.message)+'</div>'}
}
// V51.19 · Content SEO preflight (editor unsaved preview, reviewer saved snapshot).
function seoStudio(v){
 return '<section id="cms-seo-panel" class="cms-seo-panel"><div class="cms-seo-head"><div>'
   +'<span class="section-eyebrow">EDITORIAL SEO / PRE-PUBLISH</span><h3>SEO 与发布质量检查</h3>'
   +'<p>检查标题、摘要、内容深度、图片替代文字和来源。检查分数不是搜索排名预测。</p></div>'
   +'<button type="button" data-seo-check>运行质量检查 ↗</button></div>'
   +'<div class="cms-seo-snippet"><span id="cms-seo-url">b2b-design-atlas-preview.onrender.com/insights/'+h(state.selected?.slug||'')+'</span>'
   +'<strong id="cms-seo-title">'+h(v.seo_title||v.title||'文章标题')+'</strong>'
   +'<p id="cms-seo-desc">'+h(v.seo_description||v.subtitle||'请填写文章摘要')+'</p></div>'
   +'<div id="cms-seo-result" class="cms-seo-result"><p>检查当前草稿，了解可以改善的可访问性与搜索展示问题。</p></div></section>';
}
function refreshSeoSnippet(){
 const title=$('#cms-seo-title');if(!title)return;
 title.textContent=$('#field-seo_title')?.value.trim()||$('#field-title')?.value.trim()||'文章标题';
 $('#cms-seo-desc').textContent=$('#field-seo_description')?.value.trim()||$('#field-subtitle')?.value.trim()||'请填写文章摘要';
}
async function runSeoAudit(){
 if(mode!=='admin'||!state.selected||state.selected.kind!=='article')return;
 const root=$('#cms-seo-result');root.innerHTML='<p>正在计算内容质量…</p>';
 try{
   let data;
   if(can('edit')){
     const payload=takeFields();
     data=await api('/api/admin/seo/check',{method:'POST',
       body:JSON.stringify({slug:state.selected.slug,payload})});
   }else data=await api('/api/admin/seo/article/'+state.selected.slug);
   root.innerHTML='<div class="cms-seo-score"><strong>'+data.score+'<small> / 100</small></strong><span>内容质量提示 · '+data.checks.length+' 项</span></div>'
     +'<div class="cms-seo-checks">'+data.checks.map(item=>
       '<div class="cms-seo-check" data-seo-status="'+h(item.status)+'"><span class="cms-seo-dot"></span>'
       +'<div><strong>'+h(item.label)+'</strong>'+(item.advice?'<p>'+h(item.advice)+'</p>':'')+'</div></div>').join('')+'</div>'
     +'<p class="cms-seo-note">'+h(data.note)+'</p>';
 }catch(err){root.innerHTML='<div class="cms-error">'+h(err.message)+'</div>'}
}
function renderForm(item){
 const isPreview=mode==='preview',values=item.payload||{},editable=can('edit');
 const specs=fieldSpecs[item.kind];
 const topbar='<div class="cms-edit-topbar"><button type="button" class="cms-edit-back" data-close-editor>← 返回列表</button><span class="cms-edit-context">'+h(kinds[item.kind].title)+' / '+h(item.slug)+'</span>'+(editable?'<div class="cms-edit-quick-actions"><button type="button" data-editor-save>保存修改</button><button type="button" data-editor-submit '+(item.status==='draft'?'':'disabled')+'>提交审核</button></div>':'')+'</div>';
 const content='<div class="cms-editor-title"><div><div class="section-eyebrow">EDIT / '+kinds[item.kind].label.toUpperCase()+'</div><h2>'+h(values.name||values.title||item.slug)+'</h2><p>URL 标识：'+h(item.slug)+' · '+h(item.source==='cms'?'CMS 内容记录':'原始内容资料')+'</p></div>'
  +'<a target="_blank" rel="noopener" href="'+h(kinds[item.kind].url+item.slug)+'">'+icon('arrow-up-right')+' 查看前台</a></div>';
 const s=item.status;
 const siteHeader='<div class="cms-easy-header"><div class="cms-easy-heading"><span class="cms-easy-kicker">'+h(kinds[item.kind].title)+' / 编辑</span><h2>'+h(values.name||values.title||item.slug)+'</h2><p>编辑并保存草稿，审核通过后才会更新前台。</p></div>'
  +'<div class="cms-easy-header-side">'+stateClasses(s)
  +'<a class="cms-easy-public-link" target="_blank" rel="noopener" href="'+h(kinds[item.kind].url+item.slug)+'">查看前台 ↗</a></div></div>';
 const statuses=['draft','review','published'];
 const index=s==='source'||s==='public'?-1:statuses.indexOf(s);
 const steps='<div class="cms-steps">'+['内容准备','保存草稿','提交审核','正式发布'].map((title,i)=>'<span class="cms-step '+(i===index+1?'current':i<index+1?'passed':'')+'"><span>'+String(i+1).padStart(2,'0')+'</span>'+title+'</span>'+(i<3?'<span class="cms-step-line"></span>':'')).join('')+'</div>';
 const meta='<div class="cms-editor-meta">'+stateClasses(s)+'<span>修订版本 <strong>v'+item.revision+'</strong></span><span>内容来源：'+h(item.source==='cms'?'PostgreSQL CMS':'项目内容文件')+'</span>'+(item.published_at?'<span>发布时间：'+h(item.published_at.slice(0,16))+'</span>':'')+'</div>';
 const mediaHint=item.kind==='site'?'':mode==='admin'&&can('media')?'<div class="cms-editor-media-hint"><span>需要上传或更换图片？</span><button type="button" data-editor-open-media>打开媒体库 / 上传图片</button></div>':'';
 const form='<div class="cms-editor-content"><form id="cms-edit-form" class="cms-form">'
  +(item.kind==='site'?siteEditorForm(values,editable):simpleEditorForm(item.kind,values,editable))
  +(item.kind==='article'?articleStudio(values,editable):'')
  +(editable?'<div class="cms-easy-save-note"><span class="cms-autosave-led" aria-hidden="true"></span><span id="cms-autosave-status" role="status" aria-live="polite">修改后自动保存草稿</span><button type="button" data-autosave-retry>重试保存</button></div>':'')
  +'</form></div>';
 const schedule=item.schedule||null;
 const isPending=schedule?.status==='pending';
 const reviewActions=can('review')?
   '<section class="cms-v514-review-actions"><div class="cms-v514-review-heading"><div><span class="section-eyebrow">APPROVAL / RELEASE</span><h3>审核与发布控制</h3><p>只有审核员与最高管理员可批准、退回和安排发布。</p></div></div>'
   +(s==='review'?'<div class="cms-v514-review-buttons">'
    +'<button type="button" class="primary" data-transition="publish" '+(isPending?'disabled title="请先取消现有排期"':'')+'>审核并立即发布</button>'
    +'<button type="button" data-transition="reject" class="cms-review-reject">退回修改</button></div>'
    +'<label class="cms-v514-reason">审核意见（退回时必填）<textarea id="cms-review-reason" maxlength="400" rows="3" placeholder="说明需要修改的内容、引用或设计问题"></textarea></label>'
    +'<div class="cms-v514-release-box"><label>预约发布时间（当前设备本地时间）<input id="cms-schedule-local" type="datetime-local" aria-label="选择计划发布时间"></label>'
    +'<button type="button" data-schedule-save>保存发布排期</button>'
    +(isPending?'<button type="button" data-schedule-cancel>取消排期</button>':'')
    +'</div>'
    +(isPending?'<p class="cms-v514-schedule-state">已预约 · '+h(schedule.publish_at)+' UTC · v'+schedule.revision+'</p>':'')
    +(schedule?.status==='failed'||schedule?.status==='stale'?'<p class="cms-v514-schedule-error">'+h(schedule.error||'原排期已失效')+'</p>':'')
    +'<small>仅针对已审核的当前版本。免费开发环境采用下一次目录访问触发到期发布。</small>'
    :s==='published'?'<div class="cms-v514-review-buttons"><button type="button" class="warn" data-transition="archive">归档下线</button></div>'
    :'<p>当前内容状态为 '+h(statusText[s]||s)+'，无法直接执行发布审核。</p>')
   +'</section>':'';
const history=item.history||[];
 const timeline=isPreview?'':('<div class="cms-timeline"><h3>版本与操作记录</h3>'+
 (history.length?history.slice(0,15).map(v=>'<div class="cms-timeline-row"><span class="cms-timeline-dot"></span><div class="cms-timeline-content"><b>v'+v.revision+' · '+h({create:'创建草稿',save:'保存草稿',submit:'提交审核',publish:'正式发布',archive:'归档下线',restore:'恢复旧稿',reject:'审核退回'}[v.action]||v.action)+'</b><span>'+h(v.created_at?.replace('T',' ').slice(0,19)||'')+'</span>'
 +(v.reason?'<em class="cms-review-reason">退回意见：'+h(v.reason)+'</em>':'')+'</div>'+(editable?'<button type="button" data-restore="'+v.revision+'">恢复草稿</button>':'')+'</div>').join(''):'<p style="color:var(--muted);font-size:11px">原始内容尚无 CMS 修改记录。首次保存后开始记录版本。</p>')
 +'</div>');
 const root=$('#cms-editor-body');
 const tabs='<div class="atlas-v521-editor-tabs" role="tablist" aria-label="内容工作台">'
  +'<button type="button" data-editor-tab="content" role="tab">'+(item.kind==='site'?'编辑内容':'正文与资料')+'</button>'
  +(item.kind==='article'?'<button type="button" data-editor-tab="seo" role="tab">SEO 与质量</button>':'')
  +'<button type="button" data-editor-tab="review" role="tab">'+(item.kind==='site'?'审核发布':'审核与发布')+'</button>'
  +'<button type="button" data-editor-tab="history" role="tab">版本记录</button></div>';
 const seoPanel=item.kind==='article'?seoStudio(values):'';
 root.classList.toggle('cms-easy-mode',true);
 root.innerHTML=topbar+siteHeader+tabs
  +'<div data-editor-pane="content">'+form+'</div>'
  +(item.kind==='article'?'<div data-editor-pane="seo" hidden>'+seoPanel+'</div>':'')
  +'<div data-editor-pane="review" hidden>'+reviewBrief(item)+reviewActions
  +(can('review')?'':'<p class="atlas-v521-readonly-tip">本账户没有审核发布权限。如需审核，请联系最高管理员。</p>')+'</div>'
  +'<div data-editor-pane="history" hidden>'+timeline+'</div>';
 root.hidden=false;
 setStudioMode(true);
 setEditorTab(state.editorTab||'content');
 syncScheduleEditor(item);
 $('#cms-empty').hidden=true;
 state.dirty=false;autosavePaused=false;
}
async function selectItem(slug,push=false){
 if(state.dirty&&!confirm('当前修改还未保存。确定放弃这些更改吗？'))return;
 clearTimeout(autosaveTimer);editGeneration++;
 const item=state.items.find(x=>x.slug===slug);if(!item)return;
 $('#cms-editor-body').hidden=true;$('#cms-empty').hidden=false;$('#cms-empty').innerHTML='<div class="cms-loading">正在读取 '+h(item.label)+'…</div>';
 try{
   const result=mode==='admin'?await api('/api/admin/content/'+state.kind+'/'+slug):
    {kind:state.kind,slug,source:'repository',status:'public',revision:0,payload:state.records[slug],history:[]};
   state.selected=result;
   if(result.kind==='module')await loadSiteChoices();
   state.editorTab=result.status==='review'&&can('review')?'review':'content';
   renderForm(result);drawItems();if(push)history.pushState({},'',editorUrl(slug));await offerDraftRecovery(result);
 }catch(e){setStudioMode(false);$('#cms-empty').innerHTML='<div class="cms-error">'+h(e.message)+'</div>';message(e.message,false)}
}
function takeFields(){
 const base=JSON.parse(JSON.stringify(state.selected.payload)),controls=$$('#cms-edit-form [data-field]');
 for(const el of controls){
   const name=el.dataset.field,type=el.dataset.type,value=el.value;
   if(type==='json'){
     try{base[name]=JSON.parse(value)}catch{throw Error('「'+name+'」需要填写有效 JSON。')}
   }else if(type==='lines')base[name]=value.split('\n').map(x=>x.trim()).filter(Boolean);
   else if(type==='bool')base[name]=value==='true';
   else if(type==='number')base[name]=value===''?0:Number(value);
   else base[name]=value.trim();
 }
 if(state.selected.kind==='article'){
   base.tags=linesFrom('#v51-tags');
   base.takeaways=linesFrom('#v51-takeaways');
   base.sections=Array.from(document.querySelectorAll('[data-v51-section]')).map(section=>{
     const title=section.querySelector('[data-v51-title]').value.trim();
     const mode=section.querySelector('[data-blocks-mode]');
     if(mode&&!mode.hidden){
       const blocks=Array.from(section.querySelectorAll('[data-cms-block]')).map(el=>{
         const type=el.dataset.blockType,value=el.querySelector('[data-block-text]')?.value||'';
         if(type==='list')return {type,items:value.split('\n').map(x=>x.trim()).filter(Boolean)};
         if(type==='table')return {type,rows:value.split('\n').map(line=>line.split('\t').map(x=>x.trim())).filter(row=>row.some(Boolean))};
         if(type==='image')return {type,src:el.querySelector('[data-block-image]')?.value||'',
           alt:el.querySelector('[data-block-alt]')?.value.trim()||'',caption:el.querySelector('[data-block-caption]')?.value.trim()||''};
         if(type==='link')return {type,text:value.trim(),url:el.querySelector('[data-block-url]')?.value.trim()||''};
         return {type,text:value.trim()};
       });
       return {title,blocks};
     }
     return {title,
       paragraphs:section.querySelector('[data-v51-paragraphs]').value.split(/\n\s*\n/).map(x=>x.trim()).filter(Boolean),
       bullets:section.querySelector('[data-v51-bullets]').value.split('\n').map(x=>x.trim()).filter(Boolean),
       callout:section.querySelector('[data-v51-callout]').value.trim(),
       image:section.querySelector('[data-v513-image]').value.trim(),
       image_caption:section.querySelector('[data-v513-caption]').value.trim()
     };
   });
   if(!base.sections.length)throw Error('请至少保留一个文章章节。');
 }
 return base;
}
async function saveDraft(event){
 event.preventDefault();
 if(state.selected?.status==='source'&&!state.dirty)state.dirty=true;
 if(autosavePaused){message('版本冲突时不可覆盖远端草稿，请先复制内容并刷新。',false);return}
 await persistDraft(false);
}
async function transition(action){
 if(mode!=='admin'||state.busy||!state.selected)return;
 if(state.dirty||autosavePaused){message('请先等待自动保存成功或解决版本冲突，再继续审核。',false);return}
 const item=state.selected;
 let reason='';
 if(action==='reject'){
   reason=$('#cms-review-reason')?.value?.trim()||'';
   if(reason.trim().length<4){message('退回原因至少 4 个字符。',false);return}
 }
 if(action==='archive'&&!confirm('确定归档「'+(item.payload.name||item.payload.title||item.slug)+'」？该页面将从前台列表移除。'))return;
 btnDisable(true);
 try{
   const result=await api('/api/admin/content/'+item.kind+'/'+item.slug+'/'+action,{
    method:'POST',body:JSON.stringify({expected_revision:item.revision,...(action==='reject'?{reason}:{})})});
   message({submit:'已提交审核',publish:'内容已发布到前台',archive:'已归档下线',reject:'已退回草稿并记录审核意见'}[action]||'操作完成');
   state.dirty=false;await loadKind(false);await selectItem(item.slug);
 }catch(e){message(e.message,false)}
 finally{btnDisable(false)}
}
async function restoreRevision(revision){
 if(mode!=='admin'||!state.selected||state.busy)return;
 if(state.dirty||autosavePaused){message('请先保存当前编辑，或解决版本冲突后再恢复历史。',false);return}
 if(!confirm('将 v'+revision+' 的内容恢复为一份新草稿？当前已发布的前台内容不会改变。'))return;
 const target=state.selected;btnDisable(true);
 try{
   await api('/api/admin/content/'+target.kind+'/'+target.slug+'/restore',{
    method:'POST',body:JSON.stringify({expected_revision:target.revision,revision})});
   state.dirty=false;await loadKind(false);await selectItem(target.slug);message('已从历史版本生成新草稿');
 }catch(e){message(e.message,false)}
 finally{btnDisable(false)}
}
function createDefault(kind,slug,fields){
 const v={id:slug};
 if(kind==='site')return {...v,name:fields.name,url:fields.url,sector:fields.sector,summary:fields.summary,screenshot_url:'',featured:false,design_strengths:[]};
 if(kind==='module')return {...v,title:fields.name,site_id:fields.site_id,category:fields.sector,lesson:fields.summary,summary:fields.summary,screenshot_url:''};
 if(kind==='pattern')return {...v,title:fields.name,family:fields.sector,question:fields.summary,principle:fields.principle,modules:[]};
 return {...v,title:fields.name,subtitle:fields.summary,category:fields.sector,author:fields.author||'B2B Atlas 编辑部',sections:[{title:'正文',blocks:[{type:'paragraph',text:''}]}],tags:[],takeaways:[],featured:false,reading_minutes:3};
}
function updateCreateFields(){
 const kind=$('#cms-create-kind').value;
 const target=$('#cms-create-fields');
 if(!target)return;
 const f=[
  ['name',kind==='site'?'网站名称':kind==='module'?'模块标题':kind==='pattern'?'设计模式名称':'文章标题',true],
  ['sector',kind==='site'?'行业':kind==='module'?'模块分类':kind==='pattern'?'模式类别':'文章分类',true],
  ['summary',kind==='site'?'网站简介':kind==='module'?'模块设计方法':kind==='pattern'?'设计问题':'文章摘要',true]
 ];
 if(kind==='site')f.splice(1,0,['url','官方网站 URL',true]);
 if(kind==='module')f.splice(1,0,['site_id','关联网站 ID',true]);
 if(kind==='pattern')f.push(['principle','核心原则',true]);
 if(kind==='article')f.push(['author','作者',true]);
 target.innerHTML=f.map(([id,label,required])=>{
   if(kind==='article'&&id==='sector')return '<label>'+h(label)+'<select name="sector" required>'
     +'<option value="">选择文章分类</option>'
     +state.categoryRecords.map(cat=>'<option value="'+h(cat.id)+'">'+h(cat.name)+' · '+h(cat.id)+'</option>').join('')
     +'</select></label>';
   return '<label>'+h(label)+'<input name="'+id+'" '+(id==='url'?'type="url"':'type="text"')+' required maxlength="1800" placeholder="'+h(label)+'"></label>';
 }).join('');
}
async function createNew(e){
 e.preventDefault();if(mode!=='admin')return;
 const form=$('#cms-create-form');if(!form.reportValidity())return;
 const fd=new FormData(form),kind=fd.get('kind'),slug=String(fd.get('slug')||'').trim();
 if(!/^[a-z0-9][a-z0-9-]{0,110}$/.test(slug)){message('URL 标识只能使用英文小写、数字及短横线',false);return}
 const fields=Object.fromEntries(fd.entries()),payload=createDefault(kind,slug,fields);
 try{
   await api('/api/admin/content',{method:'POST',body:JSON.stringify({kind,slug,payload})});
   $('#cms-create-dialog').close();form.reset();state.kind=kind;state.selected=null;state.q='';state.status='';$('#cms-search').value='';$('#cms-status').value='';
   history.replaceState({},'',listUrl());await loadKind();await selectItem(slug,true);message('新建草稿成功。请完善内容，再提交审核。');
 }catch(err){message(err.message,false)}
}
async function exportCms(){
 if(mode==='preview'){message('请登录已授权的管理员账号后导出 CMS 内容。',false);return}
 try{
   const d=await api('/api/admin/content/export');
   const u=URL.createObjectURL(new Blob([JSON.stringify(d,null,2)],{type:'application/json;charset=utf-8'}));
   const a=document.createElement('a');a.href=u;a.download='atlas-cms-content-'+new Date().toISOString().slice(0,10)+'.json';document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(u),1200);message('内容与版本记录已导出');
 }catch(e){message(e.message,false)}
}
function closeMobile(){document.body.classList.remove('sidebar-open');$('#cms-backdrop').hidden=true;$('#cms-menu').setAttribute('aria-expanded','false')}
async function changeKind(kind,push=true){
 if(!kinds[kind])return;
 if(state.busy){message('草稿正在保存，请完成后切换内容类型。',false);return}
 if(state.dirty&&!confirm('当前修改尚未保存，确定切换？'))return;
 state.kind=kind;state.selected=null;state.dirty=false;state.records={};
 setStudioMode(false);state.q='';state.status='';state.selectedSlugs.clear();
 markWorkspace('content');
 $('#cms-search').value='';$('#cms-status').value='';
 $('#cms-empty').hidden=false;$('#cms-editor-body').hidden=true;
 $('#cms-empty').innerHTML='<div class="cms-empty-symbol">✳</div><span class="section-eyebrow">EDITORIAL WORKSPACE</span><h2>选择一个案例，开始研究。</h2><p>选择左侧内容后，可以在这里编辑、审阅和发布。</p>';
 if(push)history.pushState({},'',listUrl());
 closeMobile();
 try{await loadKind()}catch(e){message(e.message,false);$('#cms-items').innerHTML='<div class="cms-error">'+h(e.message)+'</div>'}
}
// V51 · Structured editorial studio, taxonomy, media and bulk workflow.
function linesFrom(selector){
 const input=$(selector);return input?input.value.split('\n').map(x=>x.trim()).filter(Boolean):[];
}
// V51.17 · Type-safe editorial blocks; legacy sections remain editable.
const articleBlockTypes={paragraph:'正文段落',heading:'小标题',quote:'引用',callout:'重点提示',
 list:'要点列表',image:'图片',table:'表格',link:'外部链接'};
function articleBlock(block={},index=0,editable=true){
 const type=articleBlockTypes[block.type]?block.type:'paragraph';
 const disabled=editable?'':' disabled';
 const value=type==='list'?(block.items||[]).join('\n'):
   type==='table'?(block.rows||[]).map(row=>row.join('\t')).join('\n'):block.text||'';
 const controls=editable?'<div class="cms-block-tools"><button type="button" data-block-move="-1" aria-label="上移内容块">↑</button>'
   +'<button type="button" data-block-move="1" aria-label="下移内容块">↓</button>'
   +'<button type="button" data-block-remove aria-label="删除内容块">×</button></div>':'';
 const textKind=type==='table'?'表格数据：列用 Tab 分隔，每行一条':
   type==='list'?'每行一个列表要点':type==='quote'?'引用文字':type==='heading'?'小标题文字':
   type==='callout'?'要强调的结论':type==='link'?'链接显示文字':'正文（支持加粗、斜体和行内代码）';
 const text=type==='image'?'':('<label>'+textKind+'<textarea data-block-text rows="'+(type==='paragraph'?5:3)+'"'+disabled+' placeholder="'+h(textKind)+'">'+h(value)+'</textarea></label>');
 const format=editable&&['paragraph','quote','callout'].includes(type)?'<div class="cms-block-inline-tools"><button type="button" data-block-format="bold">加粗</button>'
  +'<button type="button" data-block-format="italic">斜体</button><button type="button" data-block-format="code">行内代码</button></div>':'';
 const media=type==='image'?'<div class="cms-block-image-picker"><label>已选媒体 URL<input data-block-image readonly value="'+h(block.src||'')+'" placeholder="点击选择媒体库图片"></label>'
   +(editable?'<button type="button" data-block-pick-image>选择图片</button>':'')
   +'</div><label>图片替代文字（无障碍及 SEO）<input data-block-alt maxlength="240"'+disabled+' value="'+h(block.alt||'')+'" placeholder="简洁说明图片主体"></label>'
   +'<label>图注与来源<input data-block-caption maxlength="240"'+disabled+' value="'+h(block.caption||'')+'" placeholder="说明图片来源"></label>'
   +(block.src&&/^\/api\/media\/[0-9a-f-]{36}$/.test(block.src)?'<img class="cms-block-preview-image" alt="'+h(block.alt||'媒体缩略图')+'" src="'+h(block.src)+'">':''):'';
 const link=type==='link'?'<label>链接 URL<input data-block-url type="url"'+disabled+' value="'+h(block.url||'')+'" placeholder="https://example.com"></label>':'';
 return '<div class="cms-editor-block" data-cms-block data-block-type="'+type+'" draggable="'+String(editable)+'">'
  +'<div class="cms-editor-block-head"><span class="cms-block-drag" title="拖动排序" aria-hidden="true">⠿</span><strong>'+String(index+1).padStart(2,'0')+' · '+articleBlockTypes[type]+'</strong>'
  +controls+'</div><div class="cms-editor-block-body">'+format+text+media+link+'</div></div>';
}
function articleSection(section={},index=0,editable=true){
 const disabled=editable?'':' disabled',usesBlocks=Array.isArray(section.blocks);
 const head='<div class="cms-v51-section-top"><strong>章节 '+(index+1)+'</strong>'
  +(editable?'<div><button type="button" data-v51-move="-1" aria-label="上移章节">↑</button><button type="button" data-v51-move="1" aria-label="下移章节">↓</button><button type="button" data-v51-remove aria-label="删除章节">删除</button></div>':'')+'</div>'
  +'<label>章节标题<input data-v51-title maxlength="180" required'+disabled+' value="'+h(section.title||'')+'" placeholder="为这一节写一个明确的标题"></label>';
 const legacy='<div data-legacy-article '+(usesBlocks?'hidden':'')+'>'
  +'<label>正文段落 <small>空行分段 · 可转换为块编辑</small></label>'
  +(editable?'<div class="cms-v514-toolbar" role="toolbar" aria-label="正文格式工具"><button type="button" data-v514-format="bold">B 加粗</button><button type="button" data-v514-format="italic">斜体</button><button type="button" data-v514-format="code">代码</button></div>':'')
  +'<textarea data-v51-paragraphs rows="7"'+disabled+' placeholder="直接输入正文，空行分隔段落">'+h((section.paragraphs||[]).join('\n\n'))+'</textarea>'
  +'<label>要点列表<textarea data-v51-bullets rows="3"'+disabled+'>'+h((section.bullets||[]).join('\n'))+'</textarea></label>'
  +'<label>重点提示<textarea data-v51-callout rows="2"'+disabled+'>'+h(section.callout||'')+'</textarea></label>'
  +'<div class="cms-v513-image-row"><label>章节配图<input data-v513-image value="'+h(section.image||'')+'" readonly></label>'
  +(editable?'<button type="button" data-v513-pick-image>选择图片</button><button type="button" data-v513-clear-image>移除配图</button>':'')+'</div>'
  +'<label>配图说明<input data-v513-caption maxlength="240"'+disabled+' value="'+h(section.image_caption||'')+'"></label>'
  +(editable?'<button type="button" class="cms-block-convert" data-block-convert>转换为专业块编辑器 ↗</button>':'')+'</div>';
 const editor='<div data-blocks-mode '+(!usesBlocks?'hidden':'')+'>'
  +'<div class="cms-editor-block-list" data-block-list>'+((section.blocks||[]).map((b,i)=>articleBlock(b,i,editable)).join(''))+'</div>'
  +(editable?'<div class="cms-block-add-row"><select data-block-add-type aria-label="添加内容块的类型">'
      +Object.entries(articleBlockTypes).map(([key,label])=>'<option value="'+key+'">'+label+'</option>').join('')+'</select>'
      +'<button type="button" data-block-add>＋ 添加内容块</button><small>拖动卡片排序，支持上移和下移</small></div>':'')+'</div>';
 return '<div class="cms-v51-section cms-v517-section" data-v51-section>'+head+legacy+editor+'</div>';
}
function reindexBlocks(list){
 if(!list)return;
 Array.from(list.children).filter(x=>x.matches('[data-cms-block]')).forEach((el,i)=>{
   const t=el.querySelector('.cms-editor-block-head strong');
   if(t)t.textContent=String(i+1).padStart(2,'0')+' · '+articleBlockTypes[el.dataset.blockType]
 });
}
function convertLegacyChapter(node){
 const legacy=node.querySelector('[data-legacy-article]'),mode=node.querySelector('[data-blocks-mode]');
 if(!legacy||!mode||!mode.hidden)return;
 const paragraphs=node.querySelector('[data-v51-paragraphs]').value.split(/\n\s*\n/).map(x=>x.trim()).filter(Boolean);
 const bullets=node.querySelector('[data-v51-bullets]').value.split('\n').map(x=>x.trim()).filter(Boolean);
 const note=node.querySelector('[data-v51-callout]').value.trim();
 const image=node.querySelector('[data-v513-image]').value.trim();
 const caption=node.querySelector('[data-v513-caption]').value.trim();
 const blocks=paragraphs.map(text=>({type:'paragraph',text}));
 if(bullets.length)blocks.push({type:'list',items:bullets});
 if(note)blocks.push({type:'callout',text:note});
 if(image)blocks.push({type:'image',src:image,alt:caption,caption});
 if(!blocks.length)blocks.push({type:'paragraph',text:''});
 mode.querySelector('[data-block-list]').innerHTML=blocks.map((b,i)=>articleBlock(b,i,true)).join('');
 legacy.hidden=true;mode.hidden=false;markDraftDirty();refreshArticlePreview();
 message('章节已转换为内容块，保存草稿后生效');
}
function applyBlockFormat(button){
 const field=button.closest('[data-cms-block]')?.querySelector('[data-block-text]');if(!field)return;
 const start=field.selectionStart,end=field.selectionEnd;
 const marker={bold:'**',italic:'*',code:'\x60'}[button.dataset.blockFormat];
 if(!marker)return;
 const text=field.value.slice(start,end)||'文字';
 field.setRangeText(marker+text+marker,start,end,'select');
 field.setSelectionRange(start+marker.length,start+marker.length+text.length);
 field.focus();markDraftDirty();refreshArticlePreview();
}
let draggedCmsBlock=null;
function installBlockDrag(){
 const root=$('#cms-editor-body');
 root.addEventListener('dragstart',e=>{
   const el=e.target.closest('[data-cms-block]');
   if(!el||!can('edit')||e.target.closest('textarea,input'))return;
   draggedCmsBlock=el;el.classList.add('is-dragging');
   if(e.dataTransfer){e.dataTransfer.effectAllowed='move';e.dataTransfer.setData('text/plain','atlas-block')}
 });
 root.addEventListener('dragover',e=>{
   const el=e.target.closest('[data-cms-block]');
   if(el&&draggedCmsBlock&&el!==draggedCmsBlock&&el.parentElement===draggedCmsBlock.parentElement){
     e.preventDefault();if(e.dataTransfer)e.dataTransfer.dropEffect='move'
   }
 });
 root.addEventListener('drop',e=>{
   const el=e.target.closest('[data-cms-block]');
   if(!draggedCmsBlock||!el||el===draggedCmsBlock||el.parentElement!==draggedCmsBlock.parentElement)return;
   e.preventDefault();
   const rect=el.getBoundingClientRect();
   if(e.clientY<rect.top+rect.height/2)el.before(draggedCmsBlock);
   else el.after(draggedCmsBlock);
   reindexBlocks(el.parentElement);markDraftDirty();refreshArticlePreview();
 });
 root.addEventListener('dragend',()=>{
   if(draggedCmsBlock)draggedCmsBlock.classList.remove('is-dragging');
   draggedCmsBlock=null
 });
}
function articleStudio(v,editable){
 const disabled=editable?'':' disabled';
 const categorySuggestions=(state.taxonomy.article||[]).map(x=>'<option value="'+h(x)+'"></option>').join('');
 return '<section class="cms-v51-studio"><div class="cms-v51-studio-head"><div><span class="section-eyebrow">VISUAL EDITOR · V51</span><h3>结构化文章编辑器</h3><p>可视化编辑正文、标签和观点，保存后仍进入原有审核流程。</p></div><span class="cms-v51-studio-badge">所见即结构</span></div>'
 +'<div class="cms-v51-taxonomy"><label>文章标签 <small>每行一个关键词</small><textarea id="v51-tags" rows="3"'+disabled+'>'+h((v.tags||[]).join('\n'))+'</textarea></label>'
 +'<label>核心观点 <small>每行一条摘要</small><textarea id="v51-takeaways" rows="3"'+disabled+'>'+h((v.takeaways||[]).join('\n'))+'</textarea></label></div>'
 +'<div class="cms-v512-suggestions"><span>常用标签</span>'+(state.tagSuggestions.length?state.tagSuggestions.slice(0,12).map(tag=>'<button type="button" data-v512-tag="'+h(tag)+'"'+(editable?'':' disabled')+'>'+h(tag)+'</button>').join(''):'<small>暂无常用标签</small>')+'</div>'
 +'<datalist id="v51-categories">'+categorySuggestions+'</datalist>'
 +'<div class="cms-v51-chapter-head"><strong>文章章节</strong>'+(editable?'<button type="button" data-v51-add>＋ 添加章节</button>':'')+'</div>'
 +'<div id="cms-v51-sections">'+(v.sections||[]).map((s,i)=>articleSection(s,i,editable)).join('')+'</div>'
 +'<p class="cms-v51-guidance">每章可以包含正文、要点与高亮提示。上传媒体后可设为文章封面；图片发布前会检查是否存在。</p>'
 +'<div class="cms-v512-preview-actions"><button type="button" data-v512-preview aria-expanded="false">预览当前文章（无需保存）</button><small>仅在本页渲染，不会公开未保存的内容</small></div>'
 +'<section id="cms-v512-preview" class="cms-v512-preview" hidden><div class="cms-v512-preview-heading"><strong>文章排版预览</strong><span>PRIVATE · UNSAVED</span></div>'
 +'<p id="cms-v512-preview-error" hidden role="alert"></p><div id="cms-v512-preview-content"></div></section></section>';
}
// V51.2: Private, unsaved preview. All user content is HTML-escaped.
// Limited inline emphasis syntax. Always escape text BEFORE applying tags.
function inlineArticleText(value){
 const escaped=h(value);
 return escaped
  .replace(/\*\*([^*\n]+)\*\*/g,'<strong>$1</strong>')
  .replace(/(^|[^*])\*([^*\n]+)\*/g,'$1<em>$2</em>')
  .replace(/`([^`\n]+)`/g,'<code>$1</code>');
}
function applyArticleFormat(button){
 const field=button.closest('[data-v51-section]')?.querySelector('[data-v51-paragraphs]');
 if(!field)return;
 const start=field.selectionStart,end=field.selectionEnd;
 const markers={bold:'**',italic:'*',code:'`'};
 const mark=markers[button.dataset.v514Format];if(!mark)return;
 const selected=field.value.slice(start,end);
 field.setRangeText(mark+(selected||'文字')+mark,start,end,'select');
 field.setSelectionRange(start+mark.length,start+mark.length+(selected||'文字').length);
 field.focus();markDraftDirty();refreshArticlePreview();
}
function sectionImageMarkup(s){
 if(!s.image||!/^\/api\/media\/[0-9a-f-]{36}$/.test(s.image))return '';
 return '<figure class="cms-v513-figure"><img src="'+h(s.image)+'" alt="'+h(s.image_caption||s.title||'配图')+'">'
   +(s.image_caption?'<figcaption>'+h(s.image_caption)+'</figcaption>':'')+'</figure>';
}
function previewArticleBlock(block){
 if(!block||typeof block!=='object')return '';
 const type=block.type,text=inlineArticleText(block.text||'');
 if(type==='paragraph')return '<p>'+text+'</p>';
 if(type==='heading')return '<h3 class="cms-block-subheading">'+text+'</h3>';
 if(type==='quote')return '<blockquote class="cms-block-quote">'+text+'</blockquote>';
 if(type==='callout')return '<aside class="cms-block-callout">'+text+'</aside>';
 if(type==='list')return '<ul>'+((block.items||[]).map(item=>'<li>'+inlineArticleText(item)+'</li>').join(''))+'</ul>';
 if(type==='image'){
   if(!/^\/api\/media\/[0-9a-f-]{36}$/.test(block.src||''))return '';
   return '<figure class="cms-v513-figure"><img src="'+h(block.src)+'" alt="'+h(block.alt||'文章配图')+'">'
       +(block.caption?'<figcaption>'+h(block.caption)+'</figcaption>':'')+'</figure>';
 }
 if(type==='table')return '<div class="cms-block-table-scroll"><table><tbody>'
    +((block.rows||[]).map(row=>'<tr>'+row.map(cell=>'<td>'+h(cell)+'</td>').join('')+'</tr>').join(''))
    +'</tbody></table></div>';
 if(type==='link')return /^https?:\/\/[^<>\s]+$/i.test(block.url||'')
    ?'<p><a target="_blank" rel="nofollow noopener noreferrer" href="'+h(block.url)+'">'+(text||h(block.url))+' ↗</a></p>':'';
 return '';
}
function previewMarkup(article){
 const sections=Array.isArray(article.sections)?article.sections:[];
 const tags=Array.isArray(article.tags)?article.tags:[];
 const cover=new RegExp('^/api/media/[0-9a-f-]{36}$').test(article.cover_image||'')?article.cover_image:'';
 return '<article class="cms-v512-article">'
   +'<div class="cms-v512-kicker">'+h(article.category||'未分类')+' · '+h(article.author||'编辑部')+'</div>'
   +'<h1>'+h(article.title||'未命名文章')+'</h1><p class="cms-v512-deck">'+h(article.subtitle||'请填写文章摘要')+'</p>'
   +(cover?'<img class="cms-v512-cover" src="'+h(cover)+'" alt="文章封面">':'')
   +'<div class="cms-v512-tags">'+tags.map(x=>'<span>'+h(x)+'</span>').join('')+'</div>'
   +sections.map((s,i)=>'<section><h2>'+h(s.title||'章节 '+(i+1))+'</h2>'
     +(Array.isArray(s.blocks)?s.blocks.map(previewArticleBlock).join(''):
       (Array.isArray(s.paragraphs)?s.paragraphs:[]).map(p=>'<p>'+inlineArticleText(p)+'</p>').join('')
       +(Array.isArray(s.bullets)&&s.bullets.length?'<ul>'+s.bullets.map(x=>'<li>'+h(x)+'</li>').join('')+'</ul>':'')
       +sectionImageMarkup(s)
       +(s.callout?'<blockquote>'+h(s.callout)+'</blockquote>':''))+'</section>').join('')
   +'</article>';
}
function refreshArticlePreview(){
 const target=$('#cms-v512-preview');if(!target||target.hidden||!state.selected||state.selected.kind!=='article')return;
 try{
   const draft=takeFields();
   $('#cms-v512-preview-content').innerHTML=previewMarkup(draft);
   $('#cms-v512-preview-error').hidden=true;
 }catch(err){
   $('#cms-v512-preview-error').textContent=err.message;
   $('#cms-v512-preview-error').hidden=false;
 }
}
function toggleArticlePreview(){
 const target=$('#cms-v512-preview');if(!target)return;
 target.hidden=!target.hidden;
 const button=$('[data-v512-preview]');
 if(button)button.setAttribute('aria-expanded',String(!target.hidden));
 if(!target.hidden)refreshArticlePreview();
}
function reindexSections(){
 document.querySelectorAll('#cms-v51-sections [data-v51-section]').forEach((el,i)=>el.querySelector('.cms-v51-section-top strong').textContent='章节 '+(i+1));
}
function updateBulkToolbar(){
 const bar=$('#cms-bulk-toolbar');if(!bar)return;
 bar.hidden=mode!=='admin'||!(can('edit')||can('review'));
 $('#cms-selected-count').textContent=state.selectedSlugs.size+' 项已选择';
 const visible=listFiltered().filter(x=>x.status!=='source');
 $('#cms-select-all').checked=visible.length>0&&visible.every(x=>state.selectedSlugs.has(x.slug));
}
async function runBulk(){
 if(mode!=='admin'||state.busy)return;
 if(state.dirty||autosavePaused){message('请先完成草稿保存，再执行批量审核。',false);return}
 const action=$('#cms-bulk-action').value;
 if(!(action==='submit'?can('edit'):can('review'))){message('当前角色没有该批量操作权限。',false);return}
 const items=state.items.filter(x=>state.selectedSlugs.has(x.slug));
 if(!items.length){message('请先勾选需要操作的 CMS 内容',false);return}
 const allowed={submit:'draft',publish:'review',archive:'published'};
 if(items.some(x=>x.status!==allowed[action]||x.revision<1)){
   message('当前操作只能选择'+({submit:'草稿',publish:'待审核',archive:'已发布'}[action])+'内容；文件收录需先保存为草稿。',false);return;
 }
 if(items.length>20){message('每次最多批量操作 20 条内容',false);return}
 if(!confirm('确定对 '+items.length+' 条内容执行「'+({submit:'提交审核',publish:'发布到公开网站',archive:'归档下线'}[action])+'」？该操作将写入版本历史。'))return;
 btnDisable(true);
 try{
   const res=await api('/api/admin/content/bulk',{method:'POST',body:JSON.stringify({
     kind:state.kind,action,items:items.map(x=>({slug:x.slug,expected_revision:x.revision}))
   })});
   state.dirty=false;await loadKind(false);
   message('批量操作成功：'+res.results.length+' 条，所有记录已提交。');
 }catch(e){message(e.message,false)}finally{btnDisable(false)}
}
async function openMedia(){
 if(mode!=='admin'||!can('media')){message('当前账号没有媒体管理权限，请联系管理员。',false);return}
 const dialog=$('#cms-media-dialog');if(!dialog.open)dialog.showModal();
 $('#cms-media-status').textContent='正在加载已有图片…';
 await refreshMedia();
}
let cropBitmap=null,cropFilename='';
async function openCrop(mediaId){
 if(!can('media'))return;
 const media=(state.mediaRecords||[]).find(x=>x.id===mediaId);
 if(!media)return;
 try{
   const response=await fetch(media.url,{credentials:'same-origin',cache:'no-store'});
   if(!response.ok)throw Error('媒体无法读取，状态 '+response.status);
   if(typeof createImageBitmap!=='function')throw Error('浏览器不支持图片裁剪。');
   const bitmap=await createImageBitmap(await response.blob());
   if(cropBitmap&&cropBitmap.close)cropBitmap.close();
   cropBitmap=bitmap;cropFilename=media.file_name.replace(/\.[^.]+$/,'')||'atlas-image';
   $('#cms-crop-ratio').value='16:9';$('#cms-crop-x').value='50';$('#cms-crop-y').value='50';
   $('#cms-crop-dialog').showModal();paintCrop();
 }catch(err){message(err.message,false)}
}
function drawCrop(canvas,width){
 if(!cropBitmap)return;
 const [x,y]=$('#cms-crop-ratio').value.split(':').map(Number),aspect=x/y;
 const iw=cropBitmap.width,ih=cropBitmap.height;
 let sw=iw,sh=ih;
 if(iw/ih>aspect)sw=ih*aspect;else sh=iw/aspect;
 const sx=(iw-sw)*Number($('#cms-crop-x').value)/100;
 const sy=(ih-sh)*Number($('#cms-crop-y').value)/100;
 canvas.width=Math.max(1,Math.round(width));
 canvas.height=Math.max(1,Math.round(width/aspect));
 const ctx=canvas.getContext('2d');if(!ctx)throw Error('无法初始化裁剪画布。');
 ctx.imageSmoothingEnabled=true;ctx.imageSmoothingQuality='high';
 ctx.clearRect(0,0,canvas.width,canvas.height);
 ctx.drawImage(cropBitmap,sx,sy,sw,sh,0,0,canvas.width,canvas.height);
}
function paintCrop(){
 if(!cropBitmap)return;
 drawCrop($('#cms-crop-canvas'),640);
 for(const axis of ['x','y'])$('#cms-crop-'+axis+'-label').textContent=$('#cms-crop-'+axis).value+'%';
 $('#cms-crop-notice').textContent='正在预览裁剪比例；生成的新图片不会覆盖原文件。';
}
function closeCrop(){
 if($('#cms-crop-dialog').open)$('#cms-crop-dialog').close();
 if(cropBitmap&&cropBitmap.close)cropBitmap.close();
 cropBitmap=null;
}
async function saveCrop(){
 if(!cropBitmap||!can('media'))return;
 const button=$('#cms-crop-save');button.disabled=true;button.textContent='正在处理图片…';
 try{
   const canvas=document.createElement('canvas');
   let output=null;
   for(const width of [1600,1200,960]){
     drawCrop(canvas,Math.min(width,cropBitmap.width));
     const blob=await new Promise(resolve=>canvas.toBlob(resolve,'image/webp',0.82));
     if(blob&&blob.type==='image/webp'&&blob.size<=1500000){output=blob;break}
   }
   if(!output)throw Error('裁剪图片仍超过 1.5MB，请选择其他比例或使用更小的图片。');
   const file=new File([output],cropFilename+'-crop.webp',{type:'image/webp'});
   const uploaded=await uploadMedia([file]);
   if(!uploaded)throw Error('裁剪版本上传失败，请重试。');
   closeCrop();message('裁剪副本已保存，原始资源不变。');
 }catch(err){message(err.message,false)}
 finally{button.disabled=false;button.textContent='生成并保存裁剪图片'}
}
async function refreshMedia(){
 try{
   const res=await api('/api/admin/media');
   state.mediaRecords=res.items||[];
   $('#cms-media-grid').innerHTML=res.items.length?res.items.map(item=>'<div class="cms-v51-media-item">'
     +'<img src="'+h(item.url)+'" alt="'+h(item.file_name)+'" loading="lazy">'
     +'<strong title="'+h(item.file_name)+'">'+h(item.file_name)+'</strong>'
     +'<small>'+(item.byte_size/1024).toFixed(0)+' KB · '+h(item.created_at.slice(0,10))+'</small>'
     +'<small class="cms-v519-usage">'+(item.usage_count?'<strong>引用 '+item.usage_count+' 篇</strong> · '+h((item.used_by||[]).map(x=>x.slug).join('、')):'未被 CMS 内容引用')+'</small>'
     +(can('media')?'<button type="button" data-media-crop="'+h(item.id)+'">裁剪 / 设置焦点</button>':'')
     +'<button type="button" data-v51-copy-media="'+h(item.url)+'">复制图片地址</button>'
     +(state.mediaTarget?'<button type="button" data-v513-use-inline="'+h(item.url)+'">插入当前章节</button>':state.mediaField?'<button type="button" data-v51-use-media="'+h(item.url)+'">使用此图片</button>':'')
     +'<button type="button" data-v51-delete-media="'+h(item.id)+'" class="cms-v51-delete">删除图片</button></div>').join('')
     :'<p class="cms-loading">暂无上传图片。可以上传 JPG、PNG 或 WebP。</p>';
 }catch(e){$('#cms-media-status').textContent='媒体列表加载失败：'+e.message;message(e.message,false)}
}
// V51.6 · Optimize oversized images locally; never upload unsupported content.
async function optimizeMediaFile(original){
 if(!['image/jpeg','image/png','image/webp'].includes(original.type))
   throw Error(original.name+'：仅支持 JPG、PNG 或 WebP。');
 if(original.size<=1500000)return original;
 if(original.size>12000000)throw Error(original.name+'：原始图片不能超过 12MB。');
 if(typeof createImageBitmap!=='function')throw Error('当前浏览器不支持自动压缩，请先将图片压缩到 1.5MB 以下。');
 const bitmap=await createImageBitmap(original);
 try{
   const canvas=document.createElement('canvas');
   const context=canvas.getContext('2d',{alpha:true});
   if(!context)throw Error('浏览器无法创建图片压缩画布。');
   for(const limit of [2400,1800,1400,1100]){
     const factor=Math.min(1,limit/Math.max(bitmap.width,bitmap.height));
     canvas.width=Math.max(1,Math.round(bitmap.width*factor));
     canvas.height=Math.max(1,Math.round(bitmap.height*factor));
     context.clearRect(0,0,canvas.width,canvas.height);
     context.drawImage(bitmap,0,0,canvas.width,canvas.height);
     for(const quality of [0.86,0.74,0.62]){
       const blob=await new Promise(resolve=>canvas.toBlob(resolve,'image/webp',quality));
       if(blob&&blob.type==='image/webp'&&blob.size>0&&blob.size<=1500000)
         return new File([blob],(original.name.slice(0,original.name.lastIndexOf('.'))||'atlas-image')+'.webp',{type:'image/webp'});
     }
   }
   throw Error(original.name+'：图片优化后仍超过 1.5MB，请使用更小的图片。');
 }finally{if(typeof bitmap.close==='function')bitmap.close()}
}
async function uploadMedia(files){
 if(mode!=='admin'||!can('media')){message('没有上传图片权限',false);return 0}
 const batch=Array.from(files||[]).slice(0,10);
 if(!batch.length)return 0;
 const picker=$('#cms-media-select'),dropzone=$('#cms-media-drop');
 picker.disabled=true;dropzone.disabled=true;
 let uploaded=0,failed=0,lastUrl='',uploadedUrls=[];
 for(const original of batch){
   try{
     $('#cms-media-status').textContent='正在处理 '+original.name;
     const file=await optimizeMediaFile(original);
     $('#cms-media-status').textContent='正在上传 '+file.name+'（'+Math.round(file.size/1024)+' KB）';
     const base64=await new Promise((resolve,reject)=>{
       const reader=new FileReader();reader.onerror=()=>reject(Error('文件读取失败'));
       reader.onload=()=>resolve(String(reader.result).split(',')[1]);reader.readAsDataURL(file);
     });
     const saved=await api('/api/admin/media',{method:'POST',body:JSON.stringify({name:file.name,mime:file.type,content:base64})});
     lastUrl=saved.url||'';
     if(lastUrl)uploadedUrls.push(lastUrl);
     uploaded++;
     message((file!==original?'已优化并上传：':'媒体已保存：')+file.name);
   }catch(err){failed++;console.error('[CMS] media upload failed',err);message(original.name+' 上传失败：'+err.message,false)}
 }
 $('#cms-media-status').textContent='上传完成：成功 '+uploaded+' 张'+(failed?'，失败 '+failed+' 张，请检查文件格式及权限。':'。图片已保存到媒体库。');
 picker.disabled=false;dropzone.disabled=false;
 await refreshMedia();
 if(uploadedUrls.length&&state.mediaField==='field-gallery'){
   state.mediaField=null;$('#cms-media-dialog').close();addGalleryImages(uploadedUrls);return uploaded;
 }
 if(uploaded===1&&lastUrl&&state.mediaField){
   const target=document.getElementById(state.mediaField);
   if(target){target.value=lastUrl;state.mediaField=null;$('#cms-media-dialog').close();markDraftDirty();syncSiteImage();refreshArticlePreview();message('图片已关联到当前字段，请保存草稿')}
 }
 if(uploaded===1&&lastUrl&&state.mediaTarget){
   const target=state.mediaTarget.querySelector('[data-block-image],[data-v513-image]');
   if(target){target.value=lastUrl;state.mediaTarget=null;$('#cms-media-dialog').close();markDraftDirty();refreshArticlePreview();message('图片已插入正文，记得保存草稿')}
 }
 return uploaded;
}

// V51.5 · Manage article categories separately from individual articles.
async function loadCmsTaxonomy(){
 if(mode!=='admin')return;
 const [taxonomy,categories,tags]=await Promise.all([
   api('/api/admin/content/taxonomy'),api('/api/admin/categories'),api('/api/admin/tags')
 ]);
 state.taxonomy=taxonomy.categories||{};
 state.tagSuggestions=taxonomy.article_tags||[];
 state.categoryRecords=categories.items||[];
 state.tagRecords=tags.items||[];
}
function refreshEditorCategoryChoices(){
 const select=$('#field-category');
 if(state.kind!=='article'||!select||select.tagName!=='SELECT')return;
 const selected=select.value;
 select.innerHTML='<option value="">选择文章分类</option>'
  +(selected&&!state.categoryRecords.some(x=>x.id===selected)?'<option value="'+h(selected)+'" selected>'+h(selected)+'（待核对）</option>':'')
  +state.categoryRecords.map(x=>'<option value="'+h(x.id)+'"'+(selected===x.id?' selected':'')+'>'+h(x.name)+' · '+h(x.id)+'</option>').join('');
}
function drawCategories(){
 const root=$('#cms-v515-category-items');
 if(!root)return;
 root.innerHTML=state.categoryRecords.length?state.categoryRecords.map(cat=>
   '<button type="button" data-v515-pick="'+h(cat.id)+'" class="cms-v515-category">'
   +'<span><strong>'+h(cat.name)+'</strong><small>'+h(cat.id)+' · '+h(cat.description||'暂无分类说明')+'</small></span>'
   +'<span class="cms-v515-usage">'+cat.usage+' 篇</span></button>').join('')
   :'<p class="cms-loading">暂无分类，请新建。</p>';
}
function chooseCategory(id=null){
 const item=state.categoryRecords.find(x=>x.id===id);
 state.categoryEditing=item?item.id:null;
 $('#cms-v515-id').value=item?.id||'';
 $('#cms-v515-name').value=item?.name||'';
 $('#cms-v515-description').value=item?.description||'';
 $('#cms-v515-id').readOnly=Boolean(item);
 $('#cms-v515-form-title').textContent=item?'EDIT CATEGORY':'NEW CATEGORY';
 $('#cms-v515-save').textContent=item?'保存修改':'创建分类';
 $('#cms-v515-delete').hidden=!item;
 $('#cms-v515-info').textContent=item
   ?'被 '+item.usage+' 篇文章使用 · '+(item.source==='repository'?'原始分类':'CMS 分类')
   :'分类 ID 创建后不可更改；新分类会同步到前台资讯筛选。';
 $$('#cms-v515-category-items [data-v515-pick]').forEach(button=>{
   button.classList.toggle('active',button.dataset.v515Pick===id);
   button.setAttribute('aria-pressed',String(button.dataset.v515Pick===id));
 });
}
async function openCategoryManager(){
 if(mode!=='admin')return;
 $('#cms-categories-dialog').showModal();
 try{await loadCmsTaxonomy();drawCategories();chooseCategory(state.categoryEditing)}
 catch(err){message(err.message,false);$('#cms-v515-category-items').textContent='读取分类失败：'+err.message}
}
async function syncCategoryUpdates(){
 await loadCmsTaxonomy();drawCategories();refreshEditorCategoryChoices();
}
async function saveCategory(event){
 event.preventDefault();if(mode!=='admin'||state.busy)return;
 const id=$('#cms-v515-id').value.trim(),name=$('#cms-v515-name').value.trim();
 const description=$('#cms-v515-description').value.trim();
 if(!/^[a-z0-9][a-z0-9-]{1,47}$/.test(id)||!name){message('请填写有效的分类 ID 和显示名称',false);return}
 const editing=state.categoryEditing;
 $('#cms-v515-save').disabled=true;
 try{
   await api(editing?'/api/admin/categories/'+encodeURIComponent(editing):'/api/admin/categories',{
     method:editing?'PUT':'POST',body:JSON.stringify({id,name,description})
   });
   await syncCategoryUpdates();chooseCategory(id);
   message(editing?'分类修改已同步到前台':'分类创建成功');
 }catch(err){message(err.message,false)}
 finally{$('#cms-v515-save').disabled=false}
}
async function deleteCategory(){
 const id=state.categoryEditing;if(mode!=='admin'||!id)return;
 const cat=state.categoryRecords.find(x=>x.id===id);
 if(!confirm('确认删除分类「'+(cat?.name||id)+'」？仍被文章引用时无法删除。'))return;
 $('#cms-v515-delete').disabled=true;
 try{
   await api('/api/admin/categories/'+encodeURIComponent(id),{method:'DELETE'});
   state.categoryEditing=null;await syncCategoryUpdates();chooseCategory();
   message('分类已删除');
 }catch(err){message(err.message,false)}
 finally{$('#cms-v515-delete').disabled=false}
}

function paintSuggestedTags(){
 const box=$('.cms-v512-suggestions');
 if(!box)return;
 box.innerHTML='<span>常用标签</span>'
  +(state.tagSuggestions.length?state.tagSuggestions.slice(0,18).map(name=>
    '<button type="button" data-v512-tag="'+h(name)+'">'+h(name)+'</button>').join('')
  :'<small>暂无标签，点击顶部「标签管理」创建</small>');
}
function drawTags(){
 const box=$('#cms-tag-items');if(!box)return;
 const q=state.tagSearch.toLowerCase().trim();
 const items=state.tagRecords.filter(x=>!q||(x.name+' '+x.description).toLowerCase().includes(q));
 box.innerHTML=items.length?items.map(x=>
   '<button type="button" class="cms-v515-category cms-v513-tag-item" data-v513-tag="'+h(x.name)+'">'
   +'<span><strong>'+h(x.name)+'</strong><small>'+h(x.description||'尚无运营说明')+'</small></span>'
   +'<span class="cms-v515-usage">'+x.usage+' 篇</span></button>').join('')
   :'<p class="cms-loading">尚无标签，或搜索无结果。</p>';
 $$('#cms-tag-items [data-v513-tag]').forEach(button=>{
   const selected=button.dataset.v513Tag===state.tagEditing;
   button.classList.toggle('active',selected);
   button.setAttribute('aria-pressed',String(selected));
 });
}
function chooseTag(name=null){
 const selected=state.tagRecords.find(x=>x.name===name);
 state.tagEditing=selected?.name||null;
 $('#cms-tag-name').value=selected?.name||'';
 $('#cms-tag-description').value=selected?.description||'';
 $('#cms-tag-name').readOnly=Boolean(selected);
 $('#cms-tag-form-title').textContent=selected?'EDIT TAG':'NEW TAG';
 $('#cms-tag-save').textContent=selected?'保存标签说明':'创建标签';
 $('#cms-tag-delete').hidden=!selected;
 $('#cms-tag-info').textContent=selected
  ?'目前有 '+selected.usage+' 篇内容引用 · '+(selected.source==='content'?'收录内容标签':'后台管理标签')
  :'创建标签后可在文章编辑区快速添加；名称不可直接重命名。';
 drawTags();
}
async function openTagManager(){
 if(mode!=='admin')return;
 $('#cms-tags-dialog').showModal();
 try{await loadCmsTaxonomy();drawTags();chooseTag(state.tagEditing)}
 catch(e){message(e.message,false);$('#cms-tag-items').textContent='标签读取失败：'+e.message}
}
async function refreshTagsAfterEdit(){
 await loadCmsTaxonomy();drawTags();paintSuggestedTags();
}
async function saveTag(e){
 e.preventDefault();if(mode!=='admin'||state.busy)return;
 const name=$('#cms-tag-name').value.trim(),description=$('#cms-tag-description').value.trim();
 if(!name||name.length>32||/[<>]/.test(name)){message('标签名称不合法',false);return}
 $('#cms-tag-save').disabled=true;
 try{
   const editing=state.tagEditing;
   await api(editing?'/api/admin/tags/'+encodeURIComponent(editing):'/api/admin/tags',{
     method:editing?'PUT':'POST',body:JSON.stringify({name,description})
   });
   await refreshTagsAfterEdit();chooseTag(name);
   message(editing?'标签说明已更新':'标签创建成功');
 }catch(err){message(err.message,false)}
 finally{$('#cms-tag-save').disabled=false}
}
async function deleteTag(){
 const name=state.tagEditing;if(!name||mode!=='admin')return;
 const tag=state.tagRecords.find(t=>t.name===name);
 if(!confirm('删除标签「'+name+'」？仍被 '+(tag?.usage||0)+' 篇文章引用的标签不可删除。'))return;
 $('#cms-tag-delete').disabled=true;
 try{
   await api('/api/admin/tags/'+encodeURIComponent(name),{method:'DELETE'});
   state.tagEditing=null;await refreshTagsAfterEdit();chooseTag();
   message('标签已删除');
 }catch(err){message(err.message,false)}
 finally{$('#cms-tag-delete').disabled=false}
}
// V51.14 · Schedule queue and owner-controlled editorial permissions.
function datetimeLocal(iso){
 const d=new Date(iso);if(!Number.isFinite(d.valueOf()))return '';
 const pad=x=>String(x).padStart(2,'0');
 return d.getFullYear()+'-'+pad(d.getMonth()+1)+'-'+pad(d.getDate())+'T'+pad(d.getHours())+':'+pad(d.getMinutes());
}
function syncScheduleEditor(item){
 const input=$('#cms-schedule-local');if(!input)return;
 input.min=datetimeLocal(new Date(Date.now()+61000).toISOString());
 if(item.schedule?.status==='pending')input.value=datetimeLocal(item.schedule.publish_at);
}
async function saveSchedule(){
 if(!can('review')||state.busy||!state.selected)return;
 const item=state.selected;
 if(state.dirty||autosavePaused){message('需要先完成草稿保存才能设置发布排期。',false);return}
 if(item.status!=='review'){message('只有待审核内容可安排发布。',false);return}
 const input=$('#cms-schedule-local');
 if(!input?.value){message('请先选择发布的本地日期和时间。',false);return}
 const date=new Date(input.value);
 if(!Number.isFinite(date.getTime())){message('发布时间无效。',false);return}
 btnDisable(true);
 try{
   const schedule=await api('/api/admin/content/'+item.kind+'/'+item.slug+'/schedule',{
     method:'POST',body:JSON.stringify({expected_revision:item.revision,publish_at:date.toISOString()})});
   item.schedule={...schedule,revision:item.revision};
   renderForm(item);syncScheduleEditor(item);
   message('发布排期已保存 · '+datetimeLocal(schedule.publish_at));
 }catch(e){message(e.message,false)}
 finally{btnDisable(false)}
}
async function cancelSchedule(){
 if(!can('review')||state.busy||!state.selected)return;
 const item=state.selected;
 if(!confirm('确定取消当前待发布排期？已审核的草稿仍保留。'))return;
 btnDisable(true);
 try{
   await api('/api/admin/content/'+item.kind+'/'+item.slug+'/schedule',{method:'DELETE'});
   item.schedule={...item.schedule,status:'cancelled'};
   renderForm(item);
   message('已取消发布排期');
 }catch(e){message(e.message,false)}
 finally{btnDisable(false)}
}
// V51.18 · Month/week editorial calendar with accessible move controls.
let calendarCursor=new Date(),calendarView='month';
function calendarDateKey(d){
 const pad=n=>String(n).padStart(2,'0');
 return d.getFullYear()+'-'+pad(d.getMonth()+1)+'-'+pad(d.getDate());
}
function calendarVisibleRows(){
 const status=$('#cms-calendar-status')?.value||'all';
 return state.scheduleItems.filter(item=>status==='all'||item.status===status);
}
function calendarStart(){
 const d=calendarView==='month'
   ?new Date(calendarCursor.getFullYear(),calendarCursor.getMonth(),1)
   :new Date(calendarCursor.getFullYear(),calendarCursor.getMonth(),calendarCursor.getDate());
 d.setDate(d.getDate()-(d.getDay()+6)%7);
 return d;
}
function paintCalendar(){
 const root=$('#cms-calendar-grid');if(!root)return;
 const start=calendarStart(),days=calendarView==='month'?42:7;
 const today=calendarDateKey(new Date()),dateRows=new Map();
 for(const item of calendarVisibleRows()){
   const date=new Date(item.publish_at);if(!Number.isFinite(date.getTime()))continue;
   const key=calendarDateKey(date);
   if(!dateRows.has(key))dateRows.set(key,[]);
   dateRows.get(key).push(item)
 }
 $('#cms-calendar-label').textContent=calendarView==='month'
   ?calendarCursor.getFullYear()+'年 '+(calendarCursor.getMonth()+1)+'月'
   :calendarDateKey(start)+' – '+calendarDateKey(new Date(start.getFullYear(),start.getMonth(),start.getDate()+6));
 $$('[data-cal-view]').forEach(btn=>btn.setAttribute('aria-pressed',String(btn.dataset.calView===calendarView)));
 root.dataset.calendarView=calendarView;
 const statusLabels={pending:'待发布',published:'已发布',failed:'发布失败',stale:'版本失效',cancelled:'已取消'};
 root.innerHTML=Array.from({length:days},(_,i)=>{
   const date=new Date(start.getFullYear(),start.getMonth(),start.getDate()+i);
   const key=calendarDateKey(date),items=dateRows.get(key)||[];
   const outside=calendarView==='month'&&date.getMonth()!==calendarCursor.getMonth();
   const entries=items.slice(0,4).map(item=>{
     const draggable=can('review')&&item.status==='pending'&&item.current_revision===item.revision;
     return '<button type="button" class="cms-calendar-event" data-calendar-status="'+h(item.status)+'"'
       +' data-v514-schedule-open="'+h(item.kind)+':'+h(item.slug)+'"'
       +(draggable?' draggable="true" data-cal-drag="'+h(item.kind)+':'+h(item.slug)+'"':'')
       +' title="'+h(item.slug)+' · '+h(statusLabels[item.status]||item.status)+'">'
       +'<span>'+h(item.slug)+'</span><small>'+h(new Date(item.publish_at).toLocaleTimeString('zh-CN',{hour:'2-digit',minute:'2-digit'}))+'</small></button>'
   }).join('');
   return '<div role="gridcell" class="cms-calendar-day'+(outside?' outside':'')+(key===today?' today':'')+'" data-cal-date="'+key+'">'
     +'<div class="cms-calendar-day-head"><time datetime="'+key+'">'+date.getDate()+'</time>'
     +(items.length?'<span>'+items.length+' 项</span>':'')+'</div><div class="cms-calendar-events">'
     +entries+(items.length>4?'<small>另有 '+(items.length-4)+' 项，查看明细</small>':'')
     +'</div></div>';
 }).join('');
}
function shiftCalendar(delta){
 if(calendarView==='month')calendarCursor=new Date(calendarCursor.getFullYear(),calendarCursor.getMonth()+delta,1);
 else calendarCursor=new Date(calendarCursor.getFullYear(),calendarCursor.getMonth(),calendarCursor.getDate()+delta*7);
 paintCalendar();
}
function installCalendarDrag(){
 const root=$('#cms-calendar-grid');let current=null;
 root.addEventListener('dragstart',e=>{
   const source=e.target.closest('[data-cal-drag]');
   if(!source||!can('review'))return;
   current=source.dataset.calDrag;
   if(e.dataTransfer){e.dataTransfer.effectAllowed='move';e.dataTransfer.setData('text/plain',current)}
 });
 root.addEventListener('dragover',e=>{
   const day=e.target.closest('[data-cal-date]');
   if(!day||!current||!can('review'))return;
   e.preventDefault();if(e.dataTransfer)e.dataTransfer.dropEffect='move';
 });
 root.addEventListener('drop',async e=>{
   const day=e.target.closest('[data-cal-date]'),name=current;current=null;
   if(!day||!name||!can('review'))return;
   e.preventDefault();
   const [kind,slug]=name.split(':');
   const item=state.scheduleItems.find(x=>x.kind===kind&&x.slug===slug);
   if(!item||item.status!=='pending'||item.current_revision!==item.revision){
      message('排期版本已更新，请刷新后再调整。',false);return
   }
   const old=new Date(item.publish_at);
   const local=calendarDateKey(old),newDay=day.dataset.calDate;
   if(local===newDay)return;
   const hour=String(old.getHours()).padStart(2,'0'),minute=String(old.getMinutes()).padStart(2,'0');
   const adjusted=new Date(newDay+'T'+hour+':'+minute+':00');
   if(!Number.isFinite(adjusted.getTime())||adjusted.getTime()<Date.now()+65000){
     message('请选择至少 1 分钟后的日期。',false);return
   }
   if(!confirm('将「'+slug+'」的发布日期调整为 '+newDay+' '+hour+':'+minute+'？'))return;
   try{
     await api('/api/admin/content/'+kind+'/'+slug+'/schedule',{
       method:'POST',body:JSON.stringify({expected_revision:item.revision,publish_at:adjusted.toISOString()})});
     await refreshSchedules();message('发布日期已调整');
   }catch(err){message(err.message,false)}
 });
 root.addEventListener('dragend',()=>{current=null});
}
function paintScheduleQueue(){
 const box=$('#cms-schedule-items');
 const rows=calendarVisibleRows();
 $('#cms-schedule-count').textContent=rows.length+' 条排期记录';
 const labels={pending:'等待发布',published:'按计划发布',cancelled:'已取消',stale:'版本已失效',failed:'校验失败'};
 box.innerHTML=rows.length?rows.map(item=>
   '<div class="cms-v514-schedule-item" role="listitem"><div class="cms-v514-schedule-item-top">'
    +'<strong>'+h(item.slug)+'</strong><span data-schedule-status="'+h(item.status)+'">'+h(labels[item.status]||item.status)+'</span></div>'
    +'<p>'+h(kinds[item.kind]?.label||item.kind)+' · '+h(item.publish_at)+' UTC · v'+item.revision+'</p>'
    +(item.error?'<small>'+h(item.error)+'</small>':'')
    +'<button type="button" data-v514-schedule-open="'+h(item.kind)+':'+h(item.slug)+'">打开内容</button></div>').join('')
    :'<p class="cms-loading">暂无发布排期。可先提交内容审核，再预约发布时间。</p>';
}
async function refreshSchedules(){
 if(mode!=='admin'||!can('view'))return;
 try{
   const res=await api('/api/admin/schedules');
   state.scheduleItems=res.items||[];
   paintScheduleQueue();
   paintCalendar();
   $('#cms-schedule-note').textContent=res.execution_note||'到期检查随公开目录访问执行。';
 }catch(e){$('#cms-schedule-items').innerHTML='<div class="cms-error">'+h(e.message)+'</div>'}
}
async function openScheduleQueue(){
 if(!can('view'))return;
 markWorkspace('schedule');
 $('#cms-schedules-dialog').showModal();
 await refreshSchedules();
}
function paintTeam(){
 const root=$('#cms-team-people');
 const term=String($('#cms-team-search')?.value||'').trim().toLowerCase();
 const rows=state.teamPeople.filter(person=>!term||(
   person.id+' '+person.email+' '+person.display_name
 ).toLowerCase().includes(term));
 const label={owner:'最高管理员',editor:'内容编辑',reviewer:'审核员'};
 root.innerHTML=rows.length?rows.map(p=>
   '<button type="button" class="cms-v514-person '+(p.id===state.teamSelected?'active':'')+'" data-v514-team-id="'+h(p.id)+'">'
    +'<span><strong>'+h(p.display_name||p.email)+'</strong><small>'+h(p.email)+' · '+h(p.id)+'</small></span>'
    +'<b>'+h(label[p.role]||'普通用户')+'</b></button>').join('')
    :'<p class="cms-loading">没有匹配的已注册账号。</p>';
}
function chooseTeamPerson(id=null){
 const person=state.teamPeople.find(p=>p.id===id);
 state.teamSelected=person?.id||null;
 $('#cms-team-person-name').textContent=person?.display_name||'选择一个用户';
 $('#cms-team-person-id').textContent=person?person.email+' · ID '+person.id:'从左侧选择已注册账号';
 $('#cms-team-role').value=person?.role==='reviewer'?'reviewer':'editor';
 const locked=!person||person.role==='owner';
 $('#cms-team-role').disabled=locked;
 $('#cms-team-grant').disabled=locked;
 $('#cms-team-revoke').disabled=locked||!person?.role;
 $('#cms-team-info').textContent=person?.role==='owner'
   ?'最高管理员由部署环境固定授权，无法在此撤销。'
   :person?'按用户 ID 保存权限，授权立即影响下一次服务器操作。':'编辑可修改草稿；审核员仅能审核、发布、退回与排期。';
 paintTeam();
}
async function refreshTeam(){
 const res=await api('/api/admin/team');
 state.teamPeople=res.people||[];
 chooseTeamPerson(state.teamSelected);
}
async function openTeam(){
 if(!can('team'))return;
 $('#cms-team-dialog').showModal();
 try{await refreshTeam()}catch(e){message(e.message,false)}
}
async function grantTeamRole(e){
 e.preventDefault();if(!can('team')||!state.teamSelected)return;
 const id=state.teamSelected,role=$('#cms-team-role').value;
 $('#cms-team-grant').disabled=true;
 try{
   await api('/api/admin/team/role',{method:'PUT',
     body:JSON.stringify({user_id:id,role})});
   await refreshTeam();message('角色已更新：'+role);
 }catch(e){message(e.message,false)}
 finally{$('#cms-team-grant').disabled=false}
}
async function revokeTeamRole(){
 if(!can('team')||!state.teamSelected)return;
 if(!confirm('确定撤销此用户的内容后台权限？'))return;
 const id=state.teamSelected;
 try{
   await api('/api/admin/team/role/'+encodeURIComponent(id),{method:'DELETE'});
   await refreshTeam();message('后台角色已撤销');
 }catch(e){message(e.message,false)}
}
function boot(){
 setTheme(theme());
 // Start every privileged action hidden until /api/admin/team/me succeeds.
 for(const id of ['cms-new','cms-export','cms-media-open','cms-categories-open',
                  'cms-tags-open','cms-review-shortcut','cms-schedules-open',
                  'cms-team-open','cms-logout'])$('#'+id).hidden=true;
 $('#cms-tools-menu').hidden=true;
 $('#cms-login-link').hidden=mode!=='preview';
 $('#cms-role').textContent=mode==='admin'?'管理员 · 内容维护':'公开只读预览';
 setNotice(mode==='admin'?'管理员工作区：编辑先保存草稿，审核通过后才会进入公开目录。':'只读预览：这里展示公开网站资料，不会提供编辑或发布权限。');
 if(mode==='preview')$('#cms-state').innerHTML='<span class="status-led"></span> PUBLIC PREVIEW';
 document.addEventListener('click',async e=>{
   if(e.target.closest('[data-schedule-save]')){await saveSchedule();return}
   if(e.target.closest('[data-schedule-cancel]')){await cancelSchedule();return}
   const queueEntry=e.target.closest('[data-v514-schedule-open]');
   if(queueEntry){
     const [kind,...slugParts]=queueEntry.dataset.v514ScheduleOpen.split(':');
     const slug=slugParts.join(':');
     $('#cms-schedules-dialog').close();
     if(kind!==state.kind)await changeKind(kind);
     await selectItem(slug);return
   }
   const teamEntry=e.target.closest('[data-v514-team-id]');
   if(teamEntry){chooseTeamPerson(teamEntry.dataset.v514TeamId);return}
   const close=e.target.closest('[data-v514-close]');
   if(close){$('#cms-'+close.dataset.v514Close+'-dialog').close();return}
   if(e.target.closest('[data-close-editor]')){closeEditor();return}
   if(e.target.closest('[data-editor-save]')){if(!state.dirty&&state.selected?.status!=='source')message('当前没有待保存的修改。');else if($('#cms-edit-form')?.reportValidity())await saveDraft({preventDefault(){}});return}
   if(e.target.closest('[data-editor-submit]')){await transition('submit');return}
   if(e.target.closest('[data-gallery-add]')){state.mediaTarget=null;state.mediaField='field-gallery';await openMedia();return}
   const galleryRemove=e.target.closest('[data-gallery-remove]');
   if(galleryRemove){const items=galleryValue();items.splice(Number(galleryRemove.dataset.galleryRemove),1);updateGallery(items);return}
   const galleryMove=e.target.closest('[data-gallery-move]');
   if(galleryMove){const items=galleryValue(),i=Number(galleryMove.dataset.galleryMove),j=i+Number(galleryMove.dataset.galleryDirection);if(j>=0&&j<items.length){[items[i],items[j]]=[items[j],items[i]];updateGallery(items)}return}
   const galleryCover=e.target.closest('[data-gallery-cover]');
   if(galleryCover){const photo=galleryValue()[Number(galleryCover.dataset.galleryCover)],input=$('#field-screenshot_url');if(photo&&input){input.value=photo.url;syncSiteImage();markDraftDirty();message('已设为案例封面。')}return}
   const mediaPicker=e.target.closest('[data-editor-pick-media]');
   if(mediaPicker){state.mediaTarget=null;state.mediaField=mediaPicker.dataset.editorPickMedia;await openMedia();return}
   const tab=e.target.closest('[data-editor-tab]');
   if(tab){setEditorTab(tab.dataset.editorTab);return}
   const themeButton=e.target.closest('[data-set-theme]');if(themeButton){setTheme(themeButton.dataset.setTheme);return}
   if(e.target.closest('[data-editor-open-media]')){state.mediaTarget=null;state.mediaField=state.selected?.kind==='article'?'field-cover_image':state.selected?.kind==='site'||state.selected?.kind==='module'?'field-screenshot_url':null;await openMedia();return}
   const type=e.target.closest('[data-kind-link]');if(type){e.preventDefault();await changeKind(type.dataset.kindLink);return}
   const choice=e.target.closest('[data-pick]');if(choice){if(state.busy)return;await selectItem(choice.dataset.pick,true);return}
   const action=e.target.closest('[data-transition]');if(action){await transition(action.dataset.transition);return}
   const restore=e.target.closest('[data-restore]');if(restore){await restoreRevision(Number(restore.dataset.restore));return}
   const bulkCheck=e.target.closest('[data-bulk-select]');if(bulkCheck){const slug=bulkCheck.dataset.bulkSelect;if(bulkCheck.checked)state.selectedSlugs.add(slug);else state.selectedSlugs.delete(slug);updateBulkToolbar();return}
   const tagPick=e.target.closest('[data-v513-tag]');if(tagPick){chooseTag(tagPick.dataset.v513Tag);return}
   if(e.target.closest('[data-v513-close-tags]')){$('#cms-tags-dialog').close();return}
   const picked=e.target.closest('[data-v515-pick]');if(picked){chooseCategory(picked.dataset.v515Pick);return}
   if(e.target.closest('[data-v515-close]')){$('#cms-categories-dialog').close();return}
   if(e.target.closest('[data-autosave-retry]')){if(autosavePaused){message('已暂停覆盖：请备份当前内容并刷新记录。',false);return}await persistDraft(false);return}
   const tag=e.target.closest('[data-v512-tag]');if(tag){const field=$('#v51-tags');if(!field)return;const existing=linesFrom('#v51-tags');if(!existing.includes(tag.dataset.v512Tag)){field.value=[...existing,tag.dataset.v512Tag].join(String.fromCharCode(10));markDraftDirty();refreshArticlePreview()}return}
   if(e.target.closest('[data-review-diff]')){await openReviewDiff();return}
    if(e.target.closest('[data-v518-close-diff]')){$('#cms-diff-dialog').close();return}
    const convert=e.target.closest('[data-block-convert]');
   if(convert){convertLegacyChapter(convert.closest('[data-v51-section]'));return}
   const addBlock=e.target.closest('[data-block-add]');
   if(addBlock){const mode=addBlock.closest('[data-blocks-mode]'),list=mode.querySelector('[data-block-list]');
     const type=mode.querySelector('[data-block-add-type]').value;
     list.insertAdjacentHTML('beforeend',articleBlock({type},list.children.length,true));
     reindexBlocks(list);markDraftDirty();refreshArticlePreview();return}
   const removeBlock=e.target.closest('[data-block-remove]');
   if(removeBlock){const el=removeBlock.closest('[data-cms-block]'),list=el.parentElement;
     if(list.children.length<=1){message('每章至少保留一个内容块',false);return}
     el.remove();reindexBlocks(list);markDraftDirty();refreshArticlePreview();return}
   const moveBlock=e.target.closest('[data-block-move]');
   if(moveBlock){const el=moveBlock.closest('[data-cms-block]'),n=Number(moveBlock.dataset.blockMove);
     const near=n<0?el.previousElementSibling:el.nextElementSibling;
     if(near){if(n<0)near.before(el);else near.after(el);
       reindexBlocks(el.parentElement);markDraftDirty();refreshArticlePreview()}
     return}
   const blockFormat=e.target.closest('[data-block-format]');
   if(blockFormat){applyBlockFormat(blockFormat);return}
   const blockPick=e.target.closest('[data-block-pick-image]');
   if(blockPick){state.mediaField=null;state.mediaTarget=blockPick.closest('[data-cms-block]');await openMedia();return}
   if(e.target.closest('[data-seo-check]')){await runSeoAudit();return}
    const formatter=e.target.closest('[data-v514-format]');if(formatter){applyArticleFormat(formatter);return}
   if(e.target.closest('[data-v512-preview]')){toggleArticlePreview();return}
   if(e.target.closest('[data-v51-add]')){const root=$('#cms-v51-sections');root.insertAdjacentHTML('beforeend',articleSection({blocks:[{type:'paragraph',text:''}]},root.children.length,true));reindexSections();markDraftDirty();refreshArticlePreview();return}
   if(e.target.closest('[data-v51-remove]')){const blocks=document.querySelectorAll('#cms-v51-sections [data-v51-section]');if(blocks.length<=1){message('至少保留一个章节',false);return}e.target.closest('[data-v51-section]').remove();reindexSections();markDraftDirty();return}
   const move=e.target.closest('[data-v51-move]');if(move){const block=move.closest('[data-v51-section]'),target=Number(move.dataset.v51Move)<0?block.previousElementSibling:block.nextElementSibling;if(target){if(Number(move.dataset.v51Move)<0)target.before(block);else target.after(block);reindexSections();markDraftDirty()}return}
   const useInline=e.target.closest('[data-v513-use-inline]');
   if(useInline&&state.mediaTarget){
     const input=state.mediaTarget.querySelector('[data-block-image],[data-v513-image]');
     if(input)input.value=useInline.dataset.v513UseInline;
     state.mediaTarget=null;$('#cms-media-dialog').close();markDraftDirty();refreshArticlePreview();
     message('图片已加入章节，保存草稿后生效');return;
   }
   const crop=e.target.closest('[data-media-crop]');
    if(crop){await openCrop(crop.dataset.mediaCrop);return}
    if(e.target.closest('[data-crop-close]')){closeCrop();return}
    const deleteMedia=e.target.closest('[data-v51-delete-media]');
   if(deleteMedia){
     if(!confirm('确定删除这张媒体图片？仍被草稿或文章引用的图片会受到保护。'))return;
     try{await api('/api/admin/media/'+deleteMedia.dataset.v51DeleteMedia,{method:'DELETE'});await refreshMedia();message('图片已删除')}
     catch(err){message(err.message,false)}
     return;
   }
   const pickInline=e.target.closest('[data-v513-pick-image]');
   if(pickInline){state.mediaField=null;state.mediaTarget=pickInline.closest('[data-v51-section]');await openMedia();return}
   const clearInline=e.target.closest('[data-v513-clear-image]');
   if(clearInline){clearInline.closest('[data-v51-section]').querySelector('[data-v513-image]').value='';markDraftDirty();refreshArticlePreview();return}
   const useMedia=e.target.closest('[data-v51-use-media]');if(useMedia){if(state.mediaField==='field-gallery'){state.mediaField=null;$('#cms-media-dialog').close();addGalleryImages([useMedia.dataset.v51UseMedia]);return}const target=state.mediaField?document.getElementById(state.mediaField):null;if(target){target.value=useMedia.dataset.v51UseMedia;state.mediaField=null;markDraftDirty();syncSiteImage();refreshArticlePreview();$('#cms-media-dialog').close();message('图片已选择，请保存草稿')}return}
   const copy=e.target.closest('[data-v51-copy-media]');if(copy){try{await navigator.clipboard.writeText(location.origin+copy.dataset.v51CopyMedia);message('图片地址已复制')}catch{message('请从媒体列表中手动复制地址',false)}return}
   if(e.target.closest('[data-media-close]')){state.mediaTarget=null;state.mediaField=null;$('#cms-media-dialog').close();return}
   if(e.target.closest('[data-dialog-close]')){$('#cms-create-dialog').close();return}
 });
 document.addEventListener('input',e=>{if(e.target.closest('[data-gallery-label]')){syncGalleryLabels();return}if(e.target.closest('#cms-edit-form')){markDraftDirty();syncSiteTitle();refreshArticlePreview();refreshSeoSnippet()}});
 $('#cms-search').addEventListener('input',e=>{state.q=e.target.value;drawItems()});
 $('#cms-status').addEventListener('change',e=>{state.status=e.target.value;markWorkspace(state.status==='review'?'review':'content');drawItems()});
 $('#cms-refresh').addEventListener('click',async()=>{
  if(state.dirty&&!confirm('当前草稿还有未保存的修改。确认重新读取服务器内容吗？'))return;
  try{await loadKind(true);message('内容列表已刷新')}catch(e){message(e.message,false)}
 });
 $('#cms-logout').addEventListener('click',logoutCms);
 $('#cms-export').addEventListener('click',exportCms);
 $('#cms-new').addEventListener('click',async()=>{
   if(mode==='admin'&&state.kind==='article')try{await loadCmsTaxonomy()}catch(err){message(err.message,false)}
   updateCreateFields();$('#cms-create-dialog').showModal()
 });
 $('#cms-create-kind').addEventListener('change',updateCreateFields);
 $('#cms-diff-baseline').addEventListener('change',e=>openReviewDiff(Number(e.target.value)));
 $('#cms-tags-open').addEventListener('click',openTagManager);
 $('#cms-tag-add').addEventListener('click',()=>chooseTag());
 $('#cms-tag-form').addEventListener('submit',saveTag);
 $('#cms-tag-delete').addEventListener('click',deleteTag);
 $('#cms-tag-search').addEventListener('input',e=>{state.tagSearch=e.target.value;drawTags()});
 $('#cms-review-shortcut').addEventListener('click',async()=>{
   if(!can('view'))return;
   if(state.dirty&&!confirm('当前草稿尚未保存，确定切换到审核队列吗？'))return;
   $('#cms-status').value='review';state.status='review';markWorkspace('review');drawItems();
   closeMobile();$('#cms-items').scrollIntoView({block:'nearest',behavior:'smooth'});
   const first=listFiltered()[0];
   if(first){await selectItem(first.slug);setEditorTab('review')}
   else message('当前类型没有待审核内容');
 });
 $('#cms-schedules-open').addEventListener('click',openScheduleQueue);
 $('#cms-schedules-dialog').addEventListener('close',()=>markWorkspace(state.status==='review'?'review':'content'));
 $('#cms-schedule-refresh').addEventListener('click',refreshSchedules);
 $('#cms-calendar-status').addEventListener('change',()=>{paintCalendar();paintScheduleQueue()});
 $('#cms-calendar-today').addEventListener('click',()=>{calendarCursor=new Date();paintCalendar()});
 $$('[data-cal-view]').forEach(button=>button.addEventListener('click',()=>{
   calendarView=button.dataset.calView;paintCalendar()
 }));
 $$('[data-cal-shift]').forEach(button=>button.addEventListener('click',()=>shiftCalendar(Number(button.dataset.calShift))));
 installCalendarDrag();
 $('#cms-team-open').addEventListener('click',openTeam);
 $('#cms-team-search').addEventListener('input',paintTeam);
 $('#cms-team-form').addEventListener('submit',grantTeamRole);
 $('#cms-team-revoke').addEventListener('click',revokeTeamRole);
 $('#cms-categories-open').addEventListener('click',openCategoryManager);
 $('#cms-v515-add').addEventListener('click',()=>chooseCategory());
 $('#cms-v515-form').addEventListener('submit',saveCategory);
 $('#cms-v515-delete').addEventListener('click',deleteCategory);
 $('#cms-crop-ratio').addEventListener('change',paintCrop);
 $('#cms-crop-x').addEventListener('input',paintCrop);
 $('#cms-crop-y').addEventListener('input',paintCrop);
 $('#cms-crop-save').addEventListener('click',saveCrop);
 $('#cms-media-open').addEventListener('click',()=>{state.mediaTarget=null;state.mediaField=null;openMedia()});
 $('#cms-media-select').addEventListener('click',()=>$('#cms-media-file').click());
 $('#cms-media-file').addEventListener('change',async e=>{const files=Array.from(e.target.files||[]);e.target.value='';await uploadMedia(files)});
 const drop=$('#cms-media-drop');
 drop.addEventListener('click',()=>$('#cms-media-file').click());
 for(const eventName of ['dragenter','dragover']){
   drop.addEventListener(eventName,e=>{
     e.preventDefault();if(mode!=='admin')return;
     if(e.dataTransfer)e.dataTransfer.dropEffect='copy';
     drop.classList.add('dragging');
   });
 }
 for(const eventName of ['dragleave','dragend'])drop.addEventListener(eventName,()=>drop.classList.remove('dragging'));
 drop.addEventListener('drop',e=>{
   e.preventDefault();drop.classList.remove('dragging');
   if(mode!=='admin'||!e.dataTransfer?.files?.length)return;
   uploadMedia(e.dataTransfer.files);
 });
 installBlockDrag();
 $('#cms-bulk-run').addEventListener('click',runBulk);
 $('#cms-select-all').addEventListener('change',e=>{for(const item of listFiltered()){if(item.status==='source')continue;if(e.target.checked)state.selectedSlugs.add(item.slug);else state.selectedSlugs.delete(item.slug)}drawItems()});

 const dlg=$('#cms-create-dialog');const fields=document.createElement('div');fields.id='cms-create-fields';fields.className='cms-create-fields';
 dlg.querySelector('#cms-create-slug').closest('label').insertAdjacentElement('afterend',fields);
 $('#cms-create-form').addEventListener('submit',createNew);
 $('#cms-menu').addEventListener('click',()=>{const open=!document.body.classList.contains('sidebar-open');document.body.classList.toggle('sidebar-open',open);$('#cms-backdrop').hidden=!open;$('#cms-menu').setAttribute('aria-expanded',String(open))});
 $('#cms-backdrop').addEventListener('click',closeMobile);
 document.addEventListener('keydown',e=>{if(e.key==='Escape')closeMobile()});
 window.addEventListener('beforeunload',e=>{if(state.dirty&&mode==='admin'){e.preventDefault();e.returnValue=''}});
 window.addEventListener('popstate',async()=>{
   const route=new URLSearchParams(location.search),kind=route.get('kind')||'site',slug=route.get('edit');
   if(kind!==state.kind)await changeKind(kind,false);
   if(slug&&state.items.some(x=>x.slug===slug)){await selectItem(slug);return}
   if(state.selected)closeEditor(false);
 });
 document.addEventListener('submit',e=>{if(e.target.id==='cms-edit-form')saveDraft(e)});
 (async()=>{
   try{
     if(mode==='admin'){
       const me=await api('/api/auth/me');
       if(!me.authenticated)throw Error('会话已过期，请登录');
       state.csrf=me.csrf_token;state.user=me.user;
       const role=await api('/api/admin/team/me');
       state.role=role.role;state.capabilities=role.capabilities||[];
       setCmsRole();
       try{await loadCmsTaxonomy()}catch(err){console.warn('分类列表读取失败',err.message)}
     }
     const routeParams=new URLSearchParams(location.search);
     if(routeParams.get('status')==='review'){
       state.status='review';$('#cms-status').value='review';markWorkspace('review');
     }
     await loadKind();
     if(routeParams.get('edit')&&state.items.some(x=>x.slug===routeParams.get('edit')))await selectItem(routeParams.get('edit'));
     if(routeParams.get('workspace')==='schedule'&&can('view'))await openScheduleQueue();
   }catch(e){console.error('[CMS] initial content load failed',e);setNotice('无法读取后台内容：'+e.message);$('#cms-items').innerHTML='<div class="cms-error">'+h(e.message)+'</div>'}
 })();
}
boot();
})();