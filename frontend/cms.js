/* B2B Atlas CMS V47 — data-backed editor. No third-party dependencies.
   Public preview loads only public source data; all editing requires server auth. */
(()=>{
'use strict';
const $=(q,root=document)=>root.querySelector(q), $$=(q,root=document)=>Array.from(root.querySelectorAll(q));
const icon=n=>'<svg class="icon" aria-hidden="true"><use href="#i-'+n+'"></use></svg>';
const h=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const mode=document.body.dataset.cmsMode==='admin'?'admin':'preview';
const kinds={site:{title:'网站内容',label:'Websites',icon:'globe',public:'/api/source-library',url:'/websites/'},
 module:{title:'页面模块',label:'Sections',icon:'layers',public:'/api/module-library',url:'/sections/'},
 pattern:{title:'设计模式',label:'Patterns',icon:'shapes',public:'/assets/patterns.json',url:'/patterns/'},
 article:{title:'研究文章',label:'Insights',icon:'article',public:'/assets/articles.json',url:'/insights/'}};
const state={kind:new URLSearchParams(location.search).get('kind')||'site',items:[],records:{},selected:null,mediaField:null,csrf:'',user:null,dirty:false,q:'',status:'',busy:false,selectedSlugs:new Set(),page:1,pageSize:24,sort:'recent',taxonomy:{},tagSuggestions:[],mediaTarget:null,categoryRecords:[],categoryEditing:null,tagRecords:[],tagEditing:null,tagSearch:'',role:null,capabilities:[],scheduleItems:[],teamPeople:[],teamSelected:null,siteChoices:[]};
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
let contentListScrollY=0;
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
 const retry=$('[data-autosave-retry]'),backup=$('[data-autosave-copy]');
 if(retry)retry.hidden=kind!=='error'||autosavePaused;
 if(backup)backup.hidden=kind!=='error'||!autosavePaused;
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
 if(state.selected?.kind==='article')refreshArticleHealth();
}
function syncBusyButtonState(button,disabled){
 if(!button)return;
 // An automatic save can legitimately unlock "Submit for review". Updating
 // the desired state while the form is busy prevents btnDisable(false) from
 // restoring the obsolete pre-save disabled state.
 if(state.busy)button.dataset.cmsBeforeBusy=disabled?'1':'0';
 button.disabled=state.busy?true:disabled;
}
function applyDraftResult(target,res,payload){
 target.revision=res.revision;target.status='draft';target.payload=payload;
 const version=$('.cms-editor-meta strong');if(version)version.textContent='v'+res.revision;
 const status=$('.cms-editor-meta .cms-item-state, .cms-easy-header-side .cms-item-state');
 if(status){status.dataset.status='draft';status.textContent=statusText.draft}
 syncBusyButtonState($('#cms-edit-form [data-transition="submit"]'),false);
 syncBusyButtonState($('[data-editor-submit]'),false);
 const submitButton=$('[data-editor-submit]');if(submitButton)submitButton.hidden=false;
 const previousStageLink=$('[data-editor-state-link]');if(previousStageLink)previousStageLink.hidden=true;
 syncBusyButtonState($('#cms-edit-form [data-transition="publish"]'),true);
 syncBusyButtonState($('#cms-edit-form [data-transition="archive"]'),true);
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
     autosaveLabel('版本冲突 · 自动保存已暂停。先复制当前修改，再重新打开最新记录。','error');
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
   const name=button.dataset.editorTab,active=name===selected;
   const tabId='cms-editor-tab-'+name,paneId='cms-editor-pane-'+name;
   button.id=tabId;
   button.setAttribute('aria-controls',paneId);
   button.setAttribute('aria-selected',String(active));
   button.tabIndex=active?0:-1;
   const panel=root.querySelector('[data-editor-pane="'+name+'"]');
   if(panel){
     panel.id=paneId;
     panel.setAttribute('role','tabpanel');
     panel.setAttribute('aria-labelledby',tabId);
     panel.tabIndex=0;
     panel.hidden=!active;
   }
 }
 if(selected==='preview')refreshContentPreview();
}
// Horizontal editor tabs follow the same arrow / Home / End keyboard pattern on all screens.
function onEditorTabKeyDown(event){
 const button=event.target.closest?.('[data-editor-tab]');
 const bar=button?.closest('.atlas-v521-editor-tabs');
 if(!bar||!$('#cms-editor-body')?.contains(bar))return;
 const options=Array.from(bar.querySelectorAll('[data-editor-tab]'));
 const current=options.indexOf(button);if(current<0)return;
 let next;
 if(event.key==='ArrowRight')next=(current+1)%options.length;
 else if(event.key==='ArrowLeft')next=(current-1+options.length)%options.length;
 else if(event.key==='Home')next=0;
 else if(event.key==='End')next=options.length-1;
 else return;
 event.preventDefault();
 const target=options[next];
 setEditorTab(target.dataset.editorTab);
 target.focus({preventScroll:true});
 target.scrollIntoView({block:'nearest',inline:'nearest'});
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
 $('#cms-tools-menu').hidden=!can('view');
 $('#cms-settings-open').hidden=!can('view');
 $('#cms-page-seo-open').hidden=!can('view');
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
function btnDisable(value){
 state.busy=value;
 $$('[data-editor-pane] button,#cms-editor-body .cms-edit-quick-actions button,#cms-new,#cms-refresh,#cms-export').forEach(button=>{
  if(button.dataset.alwaysEnabled)return;
  if(value){
   if(button.dataset.cmsBeforeBusy===undefined)button.dataset.cmsBeforeBusy=button.disabled?'1':'0';
   button.disabled=true;
  }else if(button.dataset.cmsBeforeBusy!==undefined){
   button.disabled=button.dataset.cmsBeforeBusy==='1';
   delete button.dataset.cmsBeforeBusy;
  }
 });
}
function setNotice(text,error=false){const el=$('#cms-notice');el.innerHTML='<div>'+icon(error?'lock':mode==='preview'?'lock':'check')+'<span>'+h(text)+'</span></div><span>'+(error?'REQUIRES ACTION':mode==='preview'?'PUBLIC PREVIEW':'ADMIN ONLY')+'</span>';el.hidden=mode==='admin'&&!error;el.classList.toggle('cms-notice-error',error)}
function listUrl(){return editorUrl(null)}
function showKind(){
 $('#cms-current-kind').textContent=kinds[state.kind].label.toUpperCase();
 $('#cms-browser-title').textContent=kinds[state.kind].title;
 const subtitle=$('#cms-browser-subtitle');if(subtitle)subtitle.textContent='选择一条记录，查看详情或直接编辑。';
 $$('[data-kind-link]').forEach(a=>{a.classList.toggle('active',a.dataset.kindLink===state.kind);a.href='?kind='+a.dataset.kindLink});
 $('#cms-create-kind').value=state.kind;
}
function stateClasses(x){return '<span class="cms-item-state" data-status="'+h(x)+'">'+h(statusText[x]||x)+'</span>'}
function renderListContext(filtered){
 const banner=$('#cms-v559-filter-context'),label=$('#cms-v559-filter-description');
 if(!banner||!label)return;
 const bits=[];
 if(state.status)bits.push('状态：'+(statusText[state.status]||state.status));
 if(state.q.trim())bits.push('搜索：“'+state.q.trim().slice(0,80)+'”');
 banner.hidden=!bits.length;
 label.textContent=bits.length?'当前筛选 · '+bits.join(' · ')+' · 找到 '+filtered.length+' 条':'';
}
function renderListFailure(error,slug=''){
 const root=$('#cms-v559-load-failure');if(!root)return;
 const status=Number(error?.status)||0,login=status===401||/会话已过期|请先登录/.test(String(error?.message||''));
 const detail=login?'登录已失效，重新登录后可继续管理内容。'
  :status===403?'当前账号没有权限读取这项内容，请联系管理员。'
  :'读取失败。请检查网络后重试，刷新不会自动提交或发布内容。';
 root.hidden=false;
 root.innerHTML='<div><strong>'+(slug?'这条内容暂时打不开':'内容列表暂时无法读取')+'</strong>'
  +'<p>'+h(detail)+'</p><small>'+h(error?.message||'未取得服务器响应')+'</small></div>'
  +'<div class="cms-v559-retry-actions">'
  +(login?'<a href="/login?next=%2Fadmin%2Fcontent">重新登录</a>'
   :'<button type="button" data-v559-retry-load="'+h(slug)+'">重新尝试</button>')+'</div>';
}
function clearListFailure(){const root=$('#cms-v559-load-failure');if(root){root.hidden=true;root.innerHTML=''}}

function updateSummary(){
 const counts={source:0,draft:0,review:0,published:0,archived:0,public:0};
 for(const x of state.items)counts[x.status]=(counts[x.status]||0)+1;
 const numbers=[state.items.length,counts.source+counts.public,counts.draft,counts.review,counts.published];
 document.querySelectorAll('.cms-metric strong').forEach((el,i)=>el.textContent=numbers[i].toLocaleString('zh-CN'));
 const button=$('#cms-review-filter');
 if(button){button.hidden=mode!=='admin'||!can('review')||!counts.review;button.textContent='待审核 '+counts.review+' 条 · 直接处理'}
}
function listFiltered(){
 const q=state.q.toLocaleLowerCase().trim();
 const items=state.items.filter(x=>(!state.status||x.status===state.status)&&(!q||(x.label+' '+x.sector+' '+x.slug).toLocaleLowerCase().includes(q)));
 const names=(a,b)=>String(a.label||a.slug).localeCompare(String(b.label||b.slug),'zh-CN',{numeric:true,sensitivity:'base'});
 if(state.sort==='name')return items.sort(names);
 if(state.sort==='status'){
  const rank={review:0,draft:1,published:2,archived:3,source:4,public:5};
  return items.sort((a,b)=>(rank[a.status]??6)-(rank[b.status]??6)||names(a,b));
 }
 return items.sort((a,b)=>(Date.parse(b.updated_at||'')||0)-(Date.parse(a.updated_at||'')||0)||names(a,b));
}
function listPage(filtered=listFiltered()){
 const count=Math.max(1,Math.ceil(filtered.length/state.pageSize));
 state.page=Math.min(count,Math.max(1,state.page));
 const offset=(state.page-1)*state.pageSize;
 return filtered.slice(offset,offset+state.pageSize);
}
function updateListPager(filtered,items){
 const pager=$('#cms-list-pager');if(!pager)return;
 const pages=Math.max(1,Math.ceil(filtered.length/state.pageSize));
 const first=items.length?(state.page-1)*state.pageSize+1:0;
 const last=items.length?first+items.length-1:0;
 pager.hidden=pages<=1;
 $('#cms-page-info').textContent='第 '+state.page+' / '+pages+' 页';
 $('#cms-page-prev').disabled=state.page<=1;
 $('#cms-page-next').disabled=state.page>=pages;
 $('#cms-browser-footer').textContent='显示 '+first+'–'+last+' 条，共 '+filtered.length+' 条'+(filtered.length!==state.items.length?'（总计 '+state.items.length+' 条）':'');
}
function changeListPage(direction){
 const count=Math.max(1,Math.ceil(listFiltered().length/state.pageSize));
 const page=Math.min(count,Math.max(1,state.page+direction));
 if(page===state.page)return;
 state.page=page;state.selectedSlugs.clear();
 drawItems();
 $('#cms-items').scrollTop=0;
 $('#cms-page-info').focus({preventScroll:true});
}
const bulkActionRules={
 submit:{status:'draft',permission:'edit',verb:'提交审核',button:'提交审核',help:'草稿'},
 publish:{status:'review',permission:'review',verb:'发布',button:'批量发布',help:'待审核内容'},
 archive:{status:'published',permission:'review',verb:'归档下线',button:'归档下线',help:'已发布内容'}
};
function bulkEligibility(item,action=$('#cms-bulk-action')?.value||'submit'){
 const rule=bulkActionRules[action];
 if(!rule)return {ok:false,reason:'请先选择批量操作'};
 if(!can(rule.permission))return {ok:false,reason:'当前账号没有此操作权限'};
 if(item.status!==rule.status)return {ok:false,reason:'此操作仅支持'+rule.help};
 if(!(Number(item.revision)>0))return {ok:false,reason:'此内容还没有可操作的版本'};
 return {ok:true,reason:''};
}
function setStudioMode(editing){
 if(editing)closeSeoAudit();
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
 setStudioMode(false);drawItems();clearListFailure();
 if(push)history.pushState({},'',editorUrl(null));
 // Restore the content list position instead of leaving users halfway down the page.
 window.scrollTo({top:contentListScrollY,behavior:'instant'});
 const listHeading=$('#cms-browser-title');if(listHeading){listHeading.setAttribute('tabindex','-1');listHeading.focus({preventScroll:true})}
 return true;
}
function rowImage(x){
 if(x.kind==='site')return '/screenshots/sites/'+x.slug+'.webp';
 if(x.kind==='module')return '/screenshots/modules/'+x.slug+'.webp';
 return '';
}
function listNextAction(item){
 if(mode==='preview')return '查看公开内容 →';
 if(item.status==='source')return can('edit')?'完善内容并保存草稿 →':'查看收录资料 →';
 if(item.status==='draft')return can('edit')?'继续编辑 · 提交审核 →':'查看草稿 →';
 if(item.status==='review')return can('review')?'核对修改 · 审核发布 →':'查看审核进度 →';
 if(item.status==='published')return can('edit')?'查看已发布内容 · 可更新 →':'查看发布记录 →';
 if(item.status==='archived')return can('edit')?'查看归档 · 可重新编辑 →':'查看归档记录 →';
 return '查看内容 →';
}
// V56: On-demand audit of published content. The scan never changes CMS drafts.
let seoAuditGeneration=0,seoAuditData=null,seoAuditShown=12;
function closeSeoAudit(clear=false){
 seoAuditGeneration++;
 const panel=$('#cms-audit-panel'),button=$('#cms-audit-open');
 if(panel)panel.hidden=true;
 if(button)button.setAttribute('aria-expanded','false');
 if(clear)seoAuditData=null;
}
function renderSeoAuditRows(){
 const list=$('#cms-audit-list'),more=$('#cms-audit-more');
 if(!list||!more||!seoAuditData)return;
 const issues=seoAuditData.items||[];
 list.innerHTML=issues.length?issues.slice(0,seoAuditShown).map(item=>
  '<article class="cms-audit-item"><div><strong>'+h(item.title)+'</strong>'
  +'<small>'+item.issue_count+' 项建议 · '+h(item.issues.slice(0,3).map(x=>x.label).join('、'))+'</small></div>'
  +'<button type="button" data-seo-audit-edit="'+h(item.slug)+'">打开编辑</button></article>'
 ).join(''):'<p class="cms-audit-empty">当前栏目未发现这些基础检查项的问题。其他 SEO 要求仍需人工核对。</p>';
 more.hidden=seoAuditShown>=issues.length;
 if(!more.hidden)more.textContent='继续查看（剩余 '+(issues.length-seoAuditShown)+' 条）';
}
async function runPublishedSeoAudit(){
 if(mode!=='admin')return;
 const panel=$('#cms-audit-panel'),trigger=$('#cms-audit-open');
 if(!panel||!trigger)return;
 panel.hidden=false;trigger.setAttribute('aria-expanded','true');
 const kind=state.kind,generation=++seoAuditGeneration;
 seoAuditShown=12;
 $('#cms-audit-summary').textContent='正在检查当前栏目已公开的内容…';
 $('#cms-audit-list').innerHTML='<p class="cms-loading">正在分析标题、描述、来源和关联资料…</p>';
 $('#cms-audit-more').hidden=true;
 try{
  const data=await api('/api/admin/seo/audit?kind='+encodeURIComponent(kind));
  if(generation!==seoAuditGeneration||kind!==state.kind||panel.hidden)return;
  seoAuditData=data;
  $('#cms-audit-summary').textContent='共 '+data.total+' 条公开资料 · '+data.flagged+' 条有优化建议 · '+data.clear+' 条通过基础检查';
  $('#cms-audit-note').textContent=data.note+(data.remaining?' · 列表仅列出前 '+data.items.length+' 条优先处理内容。':'');
  renderSeoAuditRows();
 }catch(error){
  if(generation!==seoAuditGeneration||kind!==state.kind||panel.hidden)return;
  $('#cms-audit-summary').textContent='本次巡检没有完成';
  $('#cms-audit-list').innerHTML='<div class="cms-error">'+h(error.message)+'</div>';
 }
}

function drawItems(){
 const filtered=listFiltered(),items=listPage(filtered),root=$('#cms-items');
 root.innerHTML=items.length?items.map(item=>{
   const img=rowImage(item),actionLabel=can('edit')?'编辑内容':can('review')?'查看并审核':'查看内容';
   const bulkRule=bulkEligibility(item),bulkChecked=state.selectedSlugs.has(item.slug);
   const bulkSelect=mode==='admin'&&item.status!=='source'
    ?'<label class="cms-v51-select" aria-label="选择 '+h(item.label)+'"><input type="checkbox" data-bulk-select="'+h(item.slug)+'" '+(bulkChecked?'checked':'')+(!bulkRule.ok?' disabled title="'+h(bulkRule.reason)+'"':'')+'></label>':'';
   const compare=mode==='admin'&&can('review')&&item.status==='review'
    ?'<button type="button" class="cms-v555-row-compare" data-review-compare="'+h(item.slug)+'" aria-label="对比 '+h(item.label)+' 的待审核修改">对比修改</button>':'';
   return '<div class="cms-v51-row">'+bulkSelect+'<button type="button" class="cms-item '+(state.selected?.slug===item.slug?'active':'')+'" data-pick="'+h(item.slug)+'" aria-label="'+actionLabel+'：'+h(item.label)+'">'
   +'<span class="cms-item-thumb">'+(img?'<img src="'+h(img)+'" loading="lazy" alt="">':icon(kinds[state.kind].icon))+'</span>'
   +'<span class="cms-item-copy"><strong>'+h(item.label)+'</strong><small>'+h(item.sector||item.slug)+'</small><small class="cms-item-open-label">'+h(listNextAction(item))+'</small></span>'
   +stateClasses(item.status)+'</button>'+compare+'</div>';
 }).join(''):'<div class="cms-empty-results" role="status"><strong>'+(state.q||state.status?'没有匹配的内容':'当前还没有内容')+'</strong><p>'+(state.q||state.status?'请使用上方“清除筛选”，或调整关键词和状态。'
   :mode==='preview'?'此栏目暂未收录公开内容，可以先查看其他栏目。'
   :can('edit')?'这里还没有内容，点击下方按钮创建第一条草稿。'
   :'这里还没有内容，请联系具有编辑权限的团队成员添加。')+'</p>'
  +(!(state.q||state.status)&&can('edit')?'<button type="button" data-v559-create-first>新建第一条内容</button>':'')+'</div>';
 $('#cms-count').textContent=filtered.length+' 条';
 renderListContext(filtered);
 updateListPager(filtered,items);
  // Bulk actions are progressive enhancement: never discard a loaded content list if toolbar rendering fails.
  try{updateBulkToolbar()}catch(error){
    console.error('[CMS] bulk toolbar rendering failed; content list remains available',error);
    const toolbar=$('#cms-bulk-toolbar');if(toolbar)toolbar.hidden=true;
  }
}
async function loadKind(keep=false){
 closeSeoAudit(true);
 $('#cms-audit-open').hidden=mode!=='admin';
 showKind();
 $('#cms-items').innerHTML='<div class="cms-loading">正在读取内容…</div>';
 let records=[],items=[];
 try{
  if(mode==='admin'){
   const res=await api('/api/admin/content?kind='+state.kind);
   if(!Array.isArray(res.items))throw Error('内容服务返回的数据格式不正确。');
   items=res.items;
  }else{
   const json=await api(kinds[state.kind].public);
   records=state.kind==='site'?json.sites:state.kind==='module'?json.modules:state.kind==='article'?json.articles:json;
   if(!Array.isArray(records))throw Error('公开栏目返回的数据格式不正确。');
   for(const p of records){const slug=p.id;state.records[slug]=p;
    items.push({kind:state.kind,slug,label:p.name||p.title||slug,status:'public',source:'repository',revision:0,
     url:kinds[state.kind].url+slug,sector:p.sector||p.category||p.family||''});
   }
   items.sort((a,b)=>a.label.localeCompare(b.label,'zh'));
  }
 }catch(error){
  state.items=[];state.selected=null;state.selectedSlugs.clear();
  setStudioMode(false);updateSummary();drawItems();renderListFailure(error);
  throw error;
 }
 clearListFailure();
 if($('#cms-notice')?.classList.contains('cms-notice-error'))
  setNotice('内容已成功重新加载，可以继续安全编辑。');
 state.items=items;state.selectedSlugs.clear();updateSummary();drawItems();
 if(keep&&state.selected){
  const target=items.find(x=>x.slug===state.selected.slug);
  if(target)await selectItem(target.slug);
  else{state.selected=null;setStudioMode(false);drawItems()}
 }
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
 return '<section class="cms-easy-intro"><div><h3>基本信息</h3><p>填写名称、网址、行业和简介，再选一张封面图即可。其他内容均为选填。</p></div></section>'
 +'<div class="cms-easy-layout"><div class="cms-easy-fields">'
 +basic.map(spec=>formField(spec,values,editable)).join('')
 +'<datalist id="cms-site-sector-options"><option value="工业制造"><option value="工业软件"><option value="机器人"><option value="新能源"><option value="医疗科技"><option value="航空航天"></datalist>'
 +'</div><aside class="cms-easy-visual"><strong>案例封面</strong><p>这张图片会用于网站案例展示。</p>'
 +'<div class="cms-easy-shot"><img id="cms-site-image" src="'+(picture?h(raw):'')+'" alt="案例封面预览"'+(picture?'':' hidden')+'>'
 +'<div id="cms-site-image-empty"'+(picture?' hidden':'')+'>还没有设置封面图片</div></div>'
 +'<input id="field-screenshot_url" data-field="screenshot_url" data-type="text" type="hidden" value="'+h(raw)+'">'
 +(editable&&can('media')?'<button type="button" class="cms-easy-upload" data-editor-pick-media="field-screenshot_url">上传或更换图片</button>':'')
 +'<small>支持 JPG、PNG、WebP；已有图片也可从媒体库选用。</small></aside></div>'
 +'<details class="cms-easy-advanced cms-easy-gallery"><summary>添加更多页面截图 <span>选填 · 默认只展示一张案例封面</span></summary><section class="cms-gallery-editor"><div class="cms-gallery-heading"><div><strong>页面截图 <span id="cms-gallery-count">'+(Array.isArray(values.gallery)?values.gallery.length:0)+' 张</span></strong><p>添加产品页、方案页等图片；可调整顺序、重命名或设为主封面。</p></div>'
 +(editable&&can('media')?'<button type="button" data-gallery-add>＋ 添加截图</button>':'')+'</div>'
 +'<input id="field-gallery" type="hidden" data-field="gallery" data-type="json" value="'+h(JSON.stringify(Array.isArray(values.gallery)?values.gallery:[]))+'">'
 +'<div id="cms-gallery-list" class="cms-gallery-list">'+galleryCards(Array.isArray(values.gallery)?values.gallery.filter(x=>x&&validSiteShot(x.url)).slice(0,16):[])+'</div></section></details>'
 +'<details class="cms-easy-advanced"><summary>更多设置 <span>选填 · 业务信息与设计亮点</span></summary>'
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
   title='基本信息';description='填写模块标题、所属网站和设计说明，右侧可更换截图。';
   basic=[['title','模块标题','text',true],['site_id','所属网站','text',true],
     ['category','模块分类','text',true],['lesson','设计方法','long',true],['summary','模块介绍','long']];
   extra=[['url','原始页面链接','url'],['type','模块类型','text']];
   aside=easyImagePreview('screenshot_url',values,editable,'这张截图会展示在页面模块卡片和详情页中。');
 }else if(kind==='pattern'){
   title='基本信息';description='描述设计要解决的问题、核心方法，以及适合什么场景。';
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
   title='基本信息';description='先填写标题、摘要和分类，再在下方逐章编辑文章正文。';
   basic=[['title','文章标题','text',true],['subtitle','文章摘要','long',true],
     ['category','文章分类','text',true],['author','作者','text',true]];
   extra=[['cover_site','关联网站标识','text'],['published_at','发布日期','text'],
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
// V52.7 · Private render-only preview of the current form. Never uses the public API.
function previewSafeHref(uri){
 try{const u=new URL(String(uri||''));return ['https:','http:'].includes(u.protocol)?u.href:''}catch{return ''}
}
function sitePreviewPhotos(data){
 const chosen=[],seen=new Set();
 const add=(url,label)=>{if(validSiteShot(url)&&!seen.has(url)){chosen.push({url,label});seen.add(url)}};
 add(data.screenshot_url,'案例封面');
 for(const shot of (Array.isArray(data.gallery)?data.gallery:[]).slice(0,16)){
  if(shot&&typeof shot==='object')add(shot.url,String(shot.label||'页面截图').slice(0,80));
 }
 return chosen;
}
function contentPreviewMarkup(kind,data){
 const title=h(data.name||data.title||'未填写名称'),summary=h(data.summary||data.subtitle||data.question||'暂无简介');
 if(kind==='article')return '<div class="cms-private-article">'+previewMarkup(data)+'</div>';
 if(kind==='site'){
  const photos=sitePreviewPhotos(data),cover=photos[0],link=previewSafeHref(data.url);
  const specs=[['企业',data.name],['所属行业',data.sector],['业务方向',data.focus],['网站类型',data.model||'企业网站']].filter(x=>x[1]);
  const tags=[data.visual_style,...(Array.isArray(data.design_strengths)?data.design_strengths:[])].filter(Boolean).slice(0,8);
  return '<div class="cms-public-like"><div class="cms-public-sample-label">网站案例 · 前台视觉示意</div>'
   +'<div class="cms-public-card-sample"><div class="cms-public-card-photo">'
   +(cover?'<img src="'+h(cover.url)+'" alt="'+title+' 网站封面" loading="lazy">':'<span>案例封面尚未上传</span>')
   +'</div><div class="cms-public-card-copy"><small>'+h(data.sector||'未分类')+'</small><h3>'+title+'</h3><p>'+summary+'</p></div></div>'
   +'<div class="cms-public-detail-sample"><div class="cms-public-detail-info"><span class="cms-public-sample-label">WEBSITE RESEARCH / 案例研究</span><h2>'+title+'</h2>'
   +'<p>'+summary+'</p><div class="cms-public-meta"><span>'+h(data.sector||'')+'</span>'
   +(data.model?'<span>'+h(data.model)+'</span>':'')
   +(link?'<a href="'+h(link)+'" target="_blank" rel="noopener noreferrer nofollow">访问官方网站 ↗</a>':'')
   +'</div><dl class="cms-public-specs">'+specs.map(([label,value])=>'<div><dt>'+h(label)+'</dt><dd>'+h(value)+'</dd></div>').join('')+'</dl>'
   +(tags.length?'<div class="cms-public-style-tags"><strong>设计风格</strong><div>'+tags.map(tag=>'<span>'+h(tag)+'</span>').join('')+'</div></div>':'')
   +'</div><div class="cms-public-gallery">'
   +(cover?'<img id="cms-preview-hero" src="'+h(cover.url)+'" alt="'+h(cover.label)+'">':'<div class="cms-public-photo-empty">暂无截图</div>')
   +(photos.length>1?'<div class="cms-public-thumbs" role="group" aria-label="切换案例截图">'+photos.map((photo,i)=>
     '<button type="button" data-preview-photo="'+i+'" data-preview-src="'+h(photo.url)+'" data-preview-alt="'+h(photo.label)+'" aria-pressed="'+(i===0?'true':'false')+'">'
      +'<img src="'+h(photo.url)+'" alt=""><span>'+h(photo.label)+'</span></button>').join('')+'</div>':'')
   +'<p class="cms-public-gallery-note">当前预览主封面与新增截图。前台保留的原有研究截图仍可能补充展示。</p></div>'+(data.takeaway?'<section class="cms-public-takeaway"><h3>设计启示</h3><p>'+h(data.takeaway)+'</p></section>':'')
   +(Array.isArray(data.design_strengths)&&data.design_strengths.length?
     '<section class="cms-public-takeaway"><h3>值得借鉴</h3><ul>'+data.design_strengths.slice(0,12).map(x=>'<li>'+h(x)+'</li>').join('')+'</ul></section>':'')
   +'</div></div>';
 }
 if(kind==='module'){
  const image=validSiteShot(data.screenshot_url)?data.screenshot_url:'';
  return '<div class="cms-public-like"><div class="cms-public-sample-label">页面模块 · 前台视觉示意</div>'
   +'<div class="cms-public-card-sample"><div class="cms-public-card-photo">'
   +(image?'<img src="'+h(image)+'" alt="'+title+' 截图" loading="lazy">':'<span>尚未选择模块截图</span>')
   +'</div><div class="cms-public-card-copy"><small>'+h(data.category||'页面模块')+'</small><h3>'+title+'</h3>'
   +'<p>'+h(data.lesson||data.summary||'尚未填写设计方法')+'</p></div></div>'
   +'<section class="cms-public-takeaway"><h3>模块设计方法</h3><p>'+h(data.lesson||'')+'</p>'
   +(data.summary?'<p>'+h(data.summary)+'</p>':'')+'</section></div>';
 }
 const modules=Array.isArray(data.modules)?data.modules:[];
 return '<div class="cms-public-like"><div class="cms-public-sample-label">设计模式 · 前台视觉示意</div>'
  +'<div class="cms-public-pattern"><span>'+h(data.family||'设计模式')+'</span><h2>'+title+'</h2>'
  +'<h3>设计要解决的问题</h3><p>'+h(data.question||'')+'</p><h3>核心原则</h3><p>'+h(data.principle||'')+'</p>'
  +(data.when?'<h3>适用场景</h3><p>'+h(data.when)+'</p>':'')
  +(modules.length?'<small>关联模块 '+modules.length+' 个</small>':'')+'</div></div>';
}
function refreshContentPreview(){
 const pane=$('[data-editor-pane="preview"]');
 if(!pane||pane.hidden||!state.selected)return;
 const target=$('#cms-private-preview'),error=$('#cms-private-preview-error');
 if(!target||!error)return;
 try{
  const data=takeFields();
  target.innerHTML=contentPreviewMarkup(state.selected.kind,data);
  error.hidden=true;
  const stateLabel=$('#cms-private-preview-state');
  if(stateLabel)stateLabel.textContent=state.dirty?'当前未保存修改 · 仅本页可见':'当前草稿内容 · 仅本页可见';
 }catch(e){target.innerHTML='';error.hidden=false;error.textContent='预览无法生成：'+e.message}
}
function compareValue(field,value){
 if(value===undefined||value===null||value==='')return '<span class="cms-review-blank">未填写</span>';
 if(typeof value==='boolean')return value?'是':'否';
 if(Array.isArray(value)){
  if(!value.length)return '<span class="cms-review-blank">无</span>';
  if(field==='gallery')return h(value.length+' 张截图 · '+value.map(x=>x.label||'未命名').slice(0,5).join('、'));
  if(field==='sections')return h(value.length+' 个章节 · '+value.map(x=>x.title||'未命名').slice(0,5).join('、'));
  return h(value.slice(0,8).map(x=>typeof x==='string'?x:JSON.stringify(x)).join('、')).slice(0,300);
 }
 if(typeof value==='object')return h(JSON.stringify(value).slice(0,300));
 const text=String(value);
 if(['screenshot_url','cover_image'].includes(field)&&validSiteShot(text))
  return '<img class="cms-review-photo" src="'+h(text)+'" alt="截图">';
 if(field==='cover_image'&&/^\/api\/media\/[0-9a-f-]{36}$/.test(text))
  return '<img class="cms-review-photo" src="'+h(text)+'" alt="文章封面">';
 return '<span>'+h(text.slice(0,300))+(text.length>300?'…':'')+'</span>';
}
function inlineReviewComparison(item){
 if(item.status!=='review')return '';
 const before=item.published||null,after=item.payload||{};
 const labels={gallery:'页面截图',crop_px:'图片展示区域',modules:'关联页面模块',sections:'文章章节',design_strengths:'设计亮点',...Object.fromEntries((fieldSpecs[item.kind]||[]).map(x=>[x[0],x[1]]))};
 const fields=before?Array.from(new Set([...Object.keys(before),...Object.keys(after)])).filter(k=>
    JSON.stringify(before[k]??null)!==JSON.stringify(after[k]??null)):[];
 if(!before)return '<div class="cms-review-inline"><h4>首次发布</h4><p>这条内容尚未公开，请使用「发布前预览」检查内容、图片和排版。</p></div>';
 if(!fields.length)return '<div class="cms-review-inline"><h4>没有内容差异</h4><p>当前待审核稿与公开版本相同。</p></div>';
 const shown=fields.slice(0,8);
 return '<section class="cms-review-inline"><h4>修改内容对照 <span>共 '+fields.length+' 项</span></h4>'
  +'<div class="cms-review-inline-heading"><strong>当前公开版本</strong><strong>待审核版本</strong></div>'
  +shown.map(field=>'<div class="cms-review-compare-field"><div class="cms-review-compare-label">'+h(labels[field]||field)+'</div>'
   +'<div class="cms-review-compare-cols"><div>'+compareValue(field,before[field])+'</div><div>'+compareValue(field,after[field])+'</div></div></div>').join('')
  +(fields.length>shown.length?'<p>还有 '+(fields.length-shown.length)+' 项修改，请打开下方完整版本对比。</p>':'')
  +'</section>';
}
function nextReviewSlug(currentSlug){
 const pending=state.items.filter(item=>item.status==='review')
  .sort((a,b)=>String(b.updated_at||'').localeCompare(String(a.updated_at||''))||String(a.label||a.slug).localeCompare(String(b.label||b.slug),'zh-CN'));
 if(!pending.length)return null;
 const index=pending.findIndex(item=>item.slug===currentSlug);
 const next=index>=0?pending[(index+1)%pending.length]:pending[0];
 return next?.slug===currentSlug?null:next?.slug||null;
}
function reviewNavigation(item){
 if(mode!=='admin'||!can('review')||item.status!=='review')return '';
 const pending=state.items.filter(x=>x.status==='review').length,next=nextReviewSlug(item.slug);
 return '<nav class="cms-v555-review-nav" aria-label="当前栏目审核导航"><div><strong>审核进度 · '+pending+' 条待处理</strong><span>检查差异，确认后发布或退回</span></div><div>'
  +(next?'<button type="button" data-v555-next-review="'+h(next)+'">下一条待审核</button>':'')
  +'<button type="button" data-v555-review-list>查看待审核列表</button></div></nav>';
}
function reviewBrief(item){
 if(mode!=='admin'||item.status!=='review')return '';
 const original=item.published||null,current=item.payload||{};
 const changed=original?Array.from(new Set([...Object.keys(original),...Object.keys(current)])).filter(k=>
   JSON.stringify(original[k]??null)!==JSON.stringify(current[k]??null)):[];
 const labels={gallery:'页面截图',crop_px:'图片展示区域',modules:'关联页面模块',sections:'文章章节',design_strengths:'设计亮点',...Object.fromEntries((fieldSpecs[item.kind]||[]).map(x=>[x[0],x[1]]))};
 return '<div class="cms-review-brief"><div class="cms-review-brief-head"><div><span class="section-eyebrow">REVIEW GATE · v'+item.revision+'</span><h3>审核此内容版本</h3>'
 +'<p>对照公开快照检查字段更改，确认后再正式发布。</p></div><span class="cms-review-state">等待审核</span></div>'
 +(original?'<div class="cms-review-changes"><strong>对比已发布内容 · '+changed.length+' 项字段变化</strong>'
 +(changed.length?'<div class="cms-review-chips">'+changed.slice(0,20).map(k=>'<span>'+h(labels[k]||k)+'</span>').join('')+'</div>':'<p>草稿与当前公开内容一致。</p>')+'</div>'
 :'<div class="cms-review-changes"><strong>首次发布审查</strong><p>没有可对比的公开快照，请重点核对媒体、链接和正文。</p></div>')
 +inlineReviewComparison(item)
 +'<p class="cms-review-helper">退回操作会记录审核原因，已发布内容仍保持公开版本。</p>'
 +'<button type="button" class="cms-review-preview-link" data-editor-tab-link="preview">预览待审核稿</button>'
 +'<button type="button" class="cms-review-diff-btn" data-review-diff>打开逐段版本对比 ↗</button></div>';
}
let activeDiffRequest=0;
async function openReviewDiff(revision=0){
 if(!can('view')||!state.selected)return;
 const requestId=++activeDiffRequest;
 const item=state.selected,dialog=$('#cms-diff-dialog');
 if(!dialog.open)dialog.showModal();
 $('#cms-diff-results').innerHTML='<p class="cms-loading">正在读取版本快照…</p>';
 $('#cms-diff-summary').textContent='读取中…';
 try{
   const result=await api('/api/admin/content/'+item.kind+'/'+item.slug+'/diff?revision='+Number(revision||0));
   if(requestId!==activeDiffRequest||!dialog.open)return;
   const select=$('#cms-diff-baseline');
   select.innerHTML='<option value="0">当前公开版本</option>'
    +(result.revisions||[]).map(row=>'<option value="'+row.revision+'">历史 v'+row.revision+' · '+h(row.action)+'</option>').join('');
   select.value=String(revision||0);
   $('#cms-diff-left-title').textContent=result.baseline_label;
   const rightTitle=$('#cms-diff-right-title');
   if(rightTitle)rightTitle.textContent=({review:'待审核稿',published:'当前已发布稿',archived:'当前归档稿'}[item.status]||'当前草稿')+' · v'+result.current_revision;
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
 }catch(e){if(requestId===activeDiffRequest&&dialog.open)
   $('#cms-diff-results').innerHTML='<div class="cms-error">'+h(e.message)+'</div>'}
}
// One beginner-friendly SEO panel for all content types; empty values use the published fallback.
function seoSettings(v,kind,editable){
 const locked=editable?'':' disabled',heading=v.name||v.title||'内容标题';
 const suffix={site:' · 网站设计研究',module:' · 页面模块研究',pattern:' · 设计模式',article:''}[kind]||'';
 const summary=(kind==='site'?v.summary||v.focus:kind==='module'?v.lesson||v.summary:kind==='pattern'?v.question||v.principle:v.subtitle)||'内容摘要';
 const url=location.host+(kinds[kind]?.url||'/websites/')+(state.selected?.slug||'');
 return '<details class="cms-easy-advanced cms-seo-settings"><summary>SEO 设置 <span>选填 · 不填自动生成</span></summary>'
  +'<div class="cms-seo-fields">'
  +'<label for="field-seo_title">SEO 标题 <small>不填则使用内容标题</small></label>'
  +'<input id="field-seo_title" data-field="seo_title" data-type="text" maxlength="100" placeholder="'+h(heading+suffix)+'" value="'+h(v.seo_title||'')+'"'+locked+'>'
  +'<label for="field-seo_description">SEO 描述 <small>不填则使用内容简介</small></label>'
  +'<textarea id="field-seo_description" data-field="seo_description" data-type="long" maxlength="300" rows="3" placeholder="'+h(summary)+'"'+locked+'>'+h(v.seo_description||'')+'</textarea>'
  +'<label for="field-seo_keywords">主题关键词 <small>逗号分隔 · 不生成 meta keywords</small></label>'
  +'<input id="field-seo_keywords" data-field="seo_keywords" data-type="text" maxlength="240" placeholder="例如：工业网站设计, 企业品牌视觉" value="'+h(v.seo_keywords||'')+'"'+locked+'>'
  +'<label for="field-seo_image">分享封面 <small>仅用于社交分享，不影响正文封面</small></label>'
  +'<div class="cms-seo-image-field"><input id="field-seo_image" data-field="seo_image" data-type="text" type="text" readonly placeholder="自动使用内容封面" value="'+h(v.seo_image||'')+'"'+locked+'>'
  +(editable&&can('media')?'<button type="button" data-editor-pick-media="field-seo_image">选择图片</button>':'')
  +(editable?'<button type="button" data-seo-image-clear>恢复默认</button>':'')+'</div>'
  +'<div class="cms-seo-inline-preview"><span class="cms-seo-inline-eyebrow">Google 搜索展示预览 · 仅供参考</span>'
  +'<small id="cms-seo-preview-url">'+h(url)+'</small><strong id="cms-seo-preview-title">'+h(heading+suffix)+' · B2B Atlas</strong>'
  +'<p id="cms-seo-preview-desc">'+h(summary)+'</p><img id="cms-seo-preview-image" loading="lazy" alt="分享图片预览" hidden>'
  +'<p id="cms-seo-inline-status" role="status" aria-live="polite"></p></div>'
  +'<p class="cms-seo-inline-note">Canonical 自动维护。所有修改保存为草稿，审核发布后才会更新公开页面；实际搜索展示由搜索引擎决定。</p>'
  +'</div></details>';
}

// V51.19 · Content SEO preflight (editor unsaved preview, reviewer saved snapshot).
function seoStudio(v){
 return '<section id="cms-seo-panel" class="cms-seo-panel"><div class="cms-seo-head"><div>'
   +'<span class="section-eyebrow">EDITORIAL SEO / PRE-PUBLISH</span><h3>SEO 与发布质量检查</h3>'
   +'<p>检查标题、摘要、内容深度、图片替代文字和来源。检查分数不是搜索排名预测。</p></div>'
   +'<div class="cms-seo-panel-actions"><button type="button" data-open-seo-settings>编辑 SEO 设置</button><button type="button" data-seo-check>运行质量检查 ↗</button></div></div>'
   +'<div class="cms-seo-snippet"><span id="cms-seo-url">b2b-design-atlas-preview.onrender.com/insights/'+h(state.selected?.slug||'')+'</span>'
   +'<strong id="cms-seo-title">'+h(v.seo_title||v.title||'文章标题')+'</strong>'
   +'<p id="cms-seo-desc">'+h(v.seo_description||v.subtitle||'请填写文章摘要')+'</p></div>'
   +'<div id="cms-seo-result" class="cms-seo-result"><p>检查当前草稿，了解可以改善的可访问性与搜索展示问题。</p></div></section>';
}
function refreshSeoSnippet(){
 if(!state.selected||!$('#cms-edit-form'))return;
 const kind=state.selected.kind,heading=($('#field-name')||$('#field-title'))?.value.trim()||'内容标题';
 const description=(kind==='site'?$('#field-summary')?.value||$('#field-focus')?.value:
   kind==='module'?$('#field-lesson')?.value||$('#field-summary')?.value:
   kind==='pattern'?$('#field-question')?.value||$('#field-principle')?.value:
   $('#field-subtitle')?.value)||'内容简介';
 const suffix={site:' · 网站设计研究',module:' · 页面模块研究',pattern:' · 设计模式',article:''}[kind]||'';
 const title=$('#field-seo_title')?.value.trim()||heading+suffix;
 const desc=$('#field-seo_description')?.value.trim()||description;
 const fullTitle=title.startsWith('B2B Atlas')?title:title+' · B2B Atlas';
 if($('#cms-seo-preview-title'))$('#cms-seo-preview-title').textContent=fullTitle;
 if($('#cms-seo-preview-desc'))$('#cms-seo-preview-desc').textContent=desc;
 const image=$('#field-seo_image')?.value.trim()||
   (kind==='site'||kind==='module'?$('#field-screenshot_url')?.value:
    kind==='article'?$('#field-cover_image')?.value:'');
 const preview=$('#cms-seo-preview-image');
 if(preview){
  preview.hidden=!validSiteShot(image);
  if(!preview.hidden)preview.src=image;else preview.removeAttribute('src');
 }
 const issues=[];
 if(title.length>70)issues.push('标题较长');
 if(desc.length<35)issues.push('描述可以更具体');
 if(desc.length>170)issues.push('描述较长');
 if(!validSiteShot(image))issues.push('没有可用分享图片');
 if($('#cms-seo-inline-status'))$('#cms-seo-inline-status').textContent=
   '标题 '+title.length+' 字 · 描述 '+desc.length+' 字'+(issues.length?' · '+issues.join('、'):' · 基础检查通过');
 if($('#cms-seo-title'))$('#cms-seo-title').textContent=title;
 if($('#cms-seo-desc'))$('#cms-seo-desc').textContent=desc;
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
 const s=item.status;
 // Editing actions live here; review, preview and history stay in the tab strip.
 // Avoid duplicate stage-navigation buttons above the same tabs, especially on mobile.
 const quickActions=editable?'<div class="cms-edit-quick-actions"><button type="button" data-editor-save>保存草稿</button>'
   +'<button type="button" data-editor-submit '+(s==='draft'?'':s==='source'?'disabled title="先保存草稿，才能提交审核"':'hidden disabled')+'>提交审核</button>'
   +'</div>':'';
 const topbar='<div class="cms-edit-topbar"><button type="button" class="cms-edit-back" data-close-editor>← 返回列表</button><span class="cms-edit-context">'+h(kinds[item.kind].title)+' / '+h(item.slug)+'</span>'+quickActions+'</div>';
 const content='<div class="cms-editor-title"><div><div class="section-eyebrow">EDIT / '+kinds[item.kind].label.toUpperCase()+'</div><h2>'+h(values.name||values.title||item.slug)+'</h2><p>URL 标识：'+h(item.slug)+' · '+h(item.source==='cms'?'CMS 内容记录':'原始内容资料')+'</p></div>'
  +'<a target="_blank" rel="noopener" href="'+h(kinds[item.kind].url+item.slug)+'">'+icon('arrow-up-right')+' 查看前台</a></div>';
 const statusHint={source:'填写内容并保存草稿，审核通过后才会更新前台。',draft:'草稿不会自动公开，确认内容后可以提交审核。',review:'这份内容正在等待审核；修改后保存会生成新草稿。',published:'当前版本已发布；修改内容会生成新的待审草稿。',archived:'内容已归档，需要重新走审核流程才能公开。'}[s]||'查看和管理当前内容。';
 // A new draft may have no public page. Do not offer a misleading broken link.
 const hasPublicPage=s==='source'||s==='public'||s==='published'||(s!=='archived'&&Boolean(item.published));
 const publicLink=hasPublicPage?'<a class="cms-easy-public-link" target="_blank" rel="noopener" href="'+h(kinds[item.kind].url+item.slug)+'">查看前台 ↗</a>':'';
 const siteHeader='<div class="cms-easy-header"><div class="cms-easy-heading"><span class="cms-easy-kicker">'+h(kinds[item.kind].title)+'</span><h2>'+h(values.name||values.title||item.slug)+'</h2><p>'+h(statusHint)+'</p></div>'
  +'<div class="cms-easy-header-side">'+stateClasses(s)+publicLink+'</div></div>';
 const statuses=['draft','review','published'];
 const index=s==='source'||s==='public'?-1:statuses.indexOf(s);
 const steps='<div class="cms-steps">'+['内容准备','保存草稿','提交审核','正式发布'].map((title,i)=>'<span class="cms-step '+(i===index+1?'current':i<index+1?'passed':'')+'"><span>'+String(i+1).padStart(2,'0')+'</span>'+title+'</span>'+(i<3?'<span class="cms-step-line"></span>':'')).join('')+'</div>';
 const meta='<div class="cms-editor-meta">'+stateClasses(s)+'<span>修订版本 <strong>v'+item.revision+'</strong></span><span>内容来源：'+h(item.source==='cms'?'PostgreSQL CMS':'项目内容文件')+'</span>'+(item.published_at?'<span>发布时间：'+h(item.published_at.slice(0,16))+'</span>':'')+'</div>';
 const mediaHint=item.kind==='site'?'':mode==='admin'&&can('media')?'<div class="cms-editor-media-hint"><span>需要上传或更换图片？</span><button type="button" data-editor-open-media>打开媒体库 / 上传图片</button></div>':'';
 const auditHint=seoAuditData?.kind===item.kind?seoAuditData.items?.find(x=>x.slug===item.slug):null;
 const auditNote=auditHint?'<aside class="cms-audit-editor-note"><strong>公开版本的巡检建议</strong><p>这里显示的是上次扫描公开页面时发现的问题；如已有更新草稿，请核对后再修改。</p><ul>'
  +auditHint.issues.map(x=>'<li>'+h(x.label)+'：'+h(x.advice)+'</li>').join('')+'</ul></aside>':'';
 const form='<div class="cms-editor-content"><form id="cms-edit-form" class="cms-form">'
  +(item.kind==='site'?siteEditorForm(values,editable):simpleEditorForm(item.kind,values,editable))
  +seoSettings(values,item.kind,editable)
  +(item.kind==='article'?articleStudio(values,editable):'')
  +(editable?'<div class="cms-easy-save-note"><span class="cms-autosave-led" aria-hidden="true"></span><span id="cms-autosave-status" role="status" aria-live="polite">修改后自动保存草稿</span><button type="button" data-autosave-retry hidden>重试保存</button><button type="button" data-autosave-copy hidden>复制未保存内容</button></div>':'')
  +'</form></div>';
 const schedule=item.schedule||null;
 const isPending=schedule?.status==='pending';
 const reviewActions=can('review')?
   '<section class="cms-v514-review-actions"><div class="cms-v514-review-heading"><div><span class="section-eyebrow">APPROVAL / RELEASE</span><h3>审核与发布控制</h3><p>只有审核员与最高管理员可批准、退回和安排发布。</p></div></div>'
   +(s==='review'?'<div class="cms-v514-review-buttons">'
    +'<button type="button" class="primary" data-transition="publish" '+(isPending?'disabled title="请先取消现有排期"':'')+'>审核并立即发布</button>'
    +'<button type="button" data-schedule-open class="cms-v556-review-calendar">预约发布</button>'
    +'<button type="button" data-transition="reject" class="cms-review-reject">退回修改</button></div>'
    +'<label class="cms-v514-reason">审核意见（退回时必填）<textarea id="cms-review-reason" maxlength="400" rows="3" placeholder="说明需要修改的内容、引用或设计问题"></textarea></label>'
    +'<details class="cms-review-schedule"'+(isPending?' open':'')+'><summary>预约发布时间 <span>可选 · 不立即发布</span></summary><div class="cms-v514-release-box"><label>预约发布时间（当前设备本地时间）<input id="cms-schedule-local" type="datetime-local" aria-label="选择计划发布时间"></label>'
    +'<button type="button" data-schedule-save>保存发布排期</button>'
    +(isPending?'<button type="button" data-schedule-cancel>取消排期</button>':'')
    +'</div>'
    +(isPending?'<p class="cms-v514-schedule-state">已预约 · '+h(formatScheduleTime(schedule.publish_at))+' · v'+schedule.revision+'</p>':'')
    +(isPending?'<button type="button" class="cms-v556-calendar-jump" data-schedule-calendar>在运营日历中查看</button>':'')
    +(schedule?.status==='failed'||schedule?.status==='stale'?'<p class="cms-v514-schedule-error">'+h(schedule.error||'原排期已失效')+'</p>':'')
    +'<small>仅针对已审核的当前版本。免费开发环境采用下一次目录访问触发到期发布。</small></details>'
    :s==='published'?'<div class="cms-v514-review-buttons"><button type="button" class="warn" data-transition="archive">归档下线</button></div>'
    :'<p>当前内容状态为 '+h(statusText[s]||s)+'，无法直接执行发布审核。</p>')
   +'</section>':'';
const history=item.history||[];
 const latestRejection=s==='draft'?history.find(v=>v.action==='reject'&&typeof v.reason==='string'&&v.reason.trim()):null;
 const rejectionNote=latestRejection?
   '<aside class="cms-v546-rejection-note" role="note"><div><strong>审核已退回 · 需要修改</strong><p>'+h(latestRejection.reason)+'</p><small>按意见修改后保存草稿，再重新提交审核。公开版本不会因此改变。</small></div><button type="button" data-editor-tab-link="history">查看审核记录</button></aside>':'';
 const historyActions={create:'创建草稿',save:'保存草稿',submit:'提交审核',publish:'正式发布',archive:'归档下线',restore:'从历史恢复',reject:'审核退回'};
 const timeline=isPreview?'':('<section class="cms-timeline"><div class="cms-history-heading"><div><h3>版本记录</h3><p>查看过去的修改，或把旧版本复制为新草稿。恢复不会改变正在公开的内容。</p></div><span>共 '+history.length+' 条记录</span></div>'
 +(history.length?history.slice(0,15).map(v=>{
   const current=v.revision===item.revision;
   return '<div class="cms-timeline-row'+(current?' is-current':'')+'" data-history-revision="'+h(v.revision)+'">'
    +'<span class="cms-timeline-dot" aria-hidden="true"></span>'
    +'<div class="cms-timeline-content"><b>v'+h(v.revision)+' · '+h(historyActions[v.action]||v.action)+'</b>'
    +'<span>'+h(v.created_at?.replace('T',' ').slice(0,19)||'')+'</span>'
    +(v.reason?'<em class="cms-review-reason">退回意见：'+h(v.reason)+'</em>':'')+'</div>'
    +'<div class="cms-history-row-actions">'
    +(current?'<span class="cms-history-current">当前版本</span>'
      :'<button type="button" data-review-diff="'+h(v.revision)+'">对比当前</button>'
        +(editable?'<button type="button" class="cms-history-restore" data-restore="'+h(v.revision)+'">恢复为新草稿</button>':''))
    +'</div></div>';
 }).join(''):'<p class="cms-history-empty">这条内容还没有历史记录，首次保存后会自动开始记录。</p>')
 +(history.length>15?'<p class="cms-history-footnote">此处仅显示最近 15 条记录。</p>':'')
 +'</section>');
 const root=$('#cms-editor-body');
 const tabs='<div class="atlas-v521-editor-tabs" role="tablist" aria-label="内容工作台">'
  +'<button type="button" data-editor-tab="content" role="tab">编辑</button>'
  +'<button type="button" data-editor-tab="preview" role="tab">预览</button>'
  +(item.kind==='article'?'<button type="button" data-editor-tab="seo" role="tab">SEO · 选填</button>':'')
  +'<button type="button" data-editor-tab="review" role="tab">审核'+(s==='review'?' · 待处理':'')+'</button>'
  +'<button type="button" data-editor-tab="history" role="tab">历史</button></div>';
 const seoPanel=item.kind==='article'?seoStudio(values):'';
 root.classList.toggle('cms-easy-mode',true);
 root.innerHTML=topbar+siteHeader+rejectionNote+tabs
  +'<div id="cms-transition-feedback" class="cms-transition-feedback" role="status" aria-live="polite" hidden></div>'
  +'<div data-editor-pane="content">'+auditNote+form+'</div>'
  +'<div class="cms-private-preview-pane" data-editor-pane="preview" hidden><div class="cms-preview-heading"><div><h3>发布前预览</h3><p>模拟前台视觉效果，显示当前草稿和未保存修改；预览本身不会发布内容。</p></div><span id="cms-private-preview-state">仅当前浏览器可见</span></div><p id="cms-private-preview-error" role="alert" hidden></p><div id="cms-private-preview"></div></div>'
  +(item.kind==='article'?'<div data-editor-pane="seo" hidden>'+seoPanel+'</div>':'')
  +'<div data-editor-pane="review" hidden>'+reviewNavigation(item)+reviewBrief(item)+reviewActions
  +(can('review')?'':s==='review'?'<p class="atlas-v521-readonly-tip">已提交审核，审核员处理后会在这里更新状态。</p>':'')+'</div>'
  +'<div data-editor-pane="history" hidden>'+timeline+'</div>';
 root.hidden=false;
 setStudioMode(true);
 refreshSeoSnippet();
 if(item.kind==='article')refreshArticleHealth();
 setEditorTab(state.editorTab||'content');
 syncScheduleEditor(item);
 $('#cms-empty').hidden=true;
 state.dirty=false;autosavePaused=false;
}
async function selectItem(slug,push=false,afterWrite=false){
 // The form stays locked during a successful review/restore, but its own reload is safe.
 if(state.busy&&!afterWrite){message('草稿正在保存，请完成后打开其他内容。',false);return false}
 const item=state.items.find(x=>x.slug===slug);if(!item)return false;
 if(state.dirty&&!confirm('当前修改还未保存。确定放弃这些更改吗？'))return false;
 if(state.dirty)clearRecovery();
 if(!state.selected)contentListScrollY=window.scrollY;
 clearTimeout(autosaveTimer);editGeneration++;autosavePaused=false;state.dirty=false;
 $('#cms-editor-body').hidden=true;$('#cms-empty').hidden=false;$('#cms-empty').innerHTML='<div class="cms-loading">正在读取 '+h(item.label)+'…</div>';
 try{
   const result=mode==='admin'?await api('/api/admin/content/'+state.kind+'/'+slug):
    {kind:state.kind,slug,source:'repository',status:'public',revision:0,payload:state.records[slug],history:[]};
   state.selected=result;
   clearListFailure();
   resetArticleStructureHistory();
   if(result.kind==='module')await loadSiteChoices();
   state.editorTab=result.status==='review'&&can('review')?'review':'content';
   renderForm(result);drawItems();if(push)history.pushState({},'',editorUrl(slug));
   window.scrollTo({top:0,behavior:'instant'});
   const heading=$('#cms-editor-body .cms-easy-heading h2');if(heading){heading.setAttribute('tabindex','-1');heading.focus({preventScroll:true})}
   await offerDraftRecovery(result);
   return true;
 }catch(e){
  state.selected=null;setStudioMode(false);drawItems();
  renderListFailure(e,slug);
  message('无法打开内容：'+e.message,false);
  return false;
 }
}
// One serializer for save, undo/redo and live image SEO inspection.
function readArticleSections(){
 return Array.from(document.querySelectorAll('[data-v51-section]')).map(section=>{
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
   })
}
function takeFields(){
 const base=JSON.parse(JSON.stringify(state.selected.payload)),controls=$$('#cms-edit-form [data-field]');
 for(const el of controls){
   const name=el.dataset.field,type=el.dataset.type,value=el.value;
   if(type==='json'){
     try{base[name]=JSON.parse(value)}catch{throw Error('「'+name+'」需要填写有效 JSON。')}
   }else if(type==='lines')base[name]=value.split('\n').map(x=>x.trim()).filter(Boolean);
   else if(type==='bool')base[name]=value==='true';
   else if(type==='number')base[name]=value===''?null:Number(value);
   else base[name]=value.trim();
 }
 if(state.selected.kind==='article'){
   base.tags=linesFrom('#v51-tags');
   base.takeaways=linesFrom('#v51-takeaways');
   base.sections=readArticleSections();
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
// V52.8 · Persistent, actionable review feedback. No auto-retry of release writes.
function clearTransitionFeedback(){
 const panel=$('#cms-transition-feedback');if(panel){panel.hidden=true;panel.innerHTML=''}
}
function transitionErrorInfo(error,action,applied=false){
 if(applied)return {title:'操作已提交，但页面刷新失败',detail:'请重新读取服务器状态后再继续，避免重复发布。'};
 if(error.status===409)return {title:'内容版本已经变化',detail:'其他窗口或编辑人员可能修改了这条内容。重新加载最新版本后再决定是否操作。'};
 if(error.status===401)return {title:'登录已失效',detail:'请重新登录。原来的公开版本未因本次请求发生变化。'};
 if(error.status===403)return {title:'没有执行权限',detail:'请使用具备审核权限的账号，或联系最高管理员。'};
 if(error.status===422)return action==='reject'?{title:'退回意见还不够明确',detail:'请在审核页面写明需要修改的地方，至少 4 个字符。'}:{title:action==='publish'?'暂时无法发布':'内容校验未通过',detail:'请根据下方错误检查图片、分类、正文及关联内容，修改后再提交。'};
 return {title:'操作未确认成功',detail:'请检查网络并重新读取内容状态，避免重复执行操作。'};
}
function showTransitionFeedback(error,action,applied=false){
 const panel=$('#cms-transition-feedback');if(!panel)return;
 const info=transitionErrorInfo(error,action,applied);
 const needsReason=error.status===422&&action==='reject'&&!applied;
 panel.dataset.state='error';
 panel.setAttribute('role','alert');
 panel.setAttribute('aria-live','assertive');
 panel.hidden=false;
 panel.innerHTML='<div><strong>'+h(info.title)+'</strong><p>'+h(error.message||'服务器没有返回详细原因')+'</p><small>'+h(info.detail)+'</small></div>'
  +(needsReason?'':'<button type="button" data-review-reload>重新读取服务器状态</button>');
 panel.scrollIntoView({block:'nearest',behavior:'smooth'});
 if(needsReason){
   const input=$('#cms-review-reason');
   if(input){
     input.setAttribute('aria-invalid','true');
     input.setAttribute('aria-describedby','cms-transition-feedback');
     input.focus({preventScroll:true});
     input.scrollIntoView({block:'nearest'});
     input.addEventListener('input',()=>{
       input.removeAttribute('aria-invalid');
       input.removeAttribute('aria-describedby');
       clearTransitionFeedback();
     },{once:true});
   }
 }
}
function showTransitionSuccess(action,item){
 const panel=$('#cms-transition-feedback');if(!panel||!item)return;
 const next=can('review')&&['publish','reject'].includes(action)?nextReviewSlug(item.slug):null;
 const summaries={
   submit:['已提交审核','草稿进入待审核状态。审核员确认后才会更新前台。','review','查看审核状态'],
   reject:['已退回修改','审核意见已记录。编辑员可在基本信息上方查看原因，修改后重新提交。','content','查看修改意见'],
   publish:['审核通过，已正式发布','当前审核版本已进入公开目录。后续修改仍需重新审核。','history','查看发布记录'],
   archive:['内容已归档','内容已从公开目录撤下；历史记录和草稿仍可查看。','history','查看历史记录']
 };
 const info=summaries[action];if(!info)return;
 panel.hidden=false;
 panel.dataset.state='success';
 panel.setAttribute('role','status');
 panel.setAttribute('aria-live','polite');
 panel.innerHTML='<div><strong>'+h(info[0])+'</strong><p>'+h(info[1])+'</p></div>'
  +'<div class="cms-v546-result-actions"><button type="button" data-editor-tab-link="'+h(info[2])+'">'+h(info[3])+'</button>'
  +(action==='publish'?'<a target="_blank" rel="noopener" href="'+h(kinds[item.kind].url+item.slug)+'">查看前台 ↗</a>':'')
  +(next?'<button type="button" data-v555-next-review="'+h(next)+'">继续审核下一条 →</button>':'')
  +(can('review')&&['publish','reject'].includes(action)?'<button type="button" data-v555-review-queue>查看全部待审核</button>':'')+'</div>';
 panel.scrollIntoView({block:'nearest'});
}
async function transition(action){
 if(mode!=='admin'||state.busy||!state.selected)return;
 if(state.dirty||autosavePaused){message('请先等待自动保存成功或解决版本冲突，再继续审核。',false);return}
 const item=state.selected;
 let reason='';
 if(action==='reject'){
   reason=$('#cms-review-reason')?.value?.trim()||'';
   if(reason.trim().length<4){const error=Object.assign(new Error('退回原因至少 4 个字符，请填写具体修改意见。'),{status:422});showTransitionFeedback(error,action);message(error.message,false);return}
   $('#cms-review-reason')?.removeAttribute('aria-invalid');
   $('#cms-review-reason')?.removeAttribute('aria-describedby');
 }
 if(action==='archive'&&!confirm('确定归档「'+(item.payload.name||item.payload.title||item.slug)+'」？该页面将从前台列表移除。'))return;
 clearTransitionFeedback();
 btnDisable(true);
 let applied=false;
 try{
   await api('/api/admin/content/'+item.kind+'/'+item.slug+'/'+action,{
    method:'POST',body:JSON.stringify({expected_revision:item.revision,...(action==='reject'?{reason}:{})})});
   applied=true;
   state.dirty=false;await loadKind(false);
   if(!await selectItem(item.slug,false,true))throw Error('操作已提交，但最新内容尚未成功载入。');
   showTransitionSuccess(action,state.selected);
   message({submit:'已提交审核',publish:'内容已发布到前台',archive:'已归档下线',reject:'已退回草稿并记录审核意见'}[action]||'操作完成');
 }catch(e){showTransitionFeedback(e,action,applied);message(applied?'操作可能已完成，请重新读取服务器状态':e.message,false)}
 finally{btnDisable(false)}
}
async function restoreRevision(revision){
 if(mode!=='admin'||!can('edit')||!state.selected||state.busy)return;
 const targetRevision=Number(revision);
 if(!Number.isSafeInteger(targetRevision)||targetRevision<1||targetRevision>=state.selected.revision
    ||!state.selected.history?.some(v=>v.revision===targetRevision)){
   message('请选择历史记录中的有效旧版本进行恢复。',false);return;
 }
 if(state.dirty||autosavePaused){message('请先保存当前编辑，或解决版本冲突后再恢复历史。',false);return}
 if(!confirm('将历史 v'+targetRevision+' 复制为新的草稿？当前 v'+state.selected.revision+' 的公开内容不会被覆盖，恢复后仍需提交审核。'))return;
 const target=state.selected;btnDisable(true);
 try{
   await api('/api/admin/content/'+target.kind+'/'+target.slug+'/restore',{
    method:'POST',body:JSON.stringify({expected_revision:target.revision,revision:targetRevision})});
   state.dirty=false;await loadKind(false);
   if(!await selectItem(target.slug,false,true))throw Error('恢复已提交，但最新内容尚未成功载入。');
   message('已从历史版本生成新草稿');
 }catch(e){message(e.status===409?'版本已经变化，请刷新记录后再恢复历史。':e.message,false)}
 finally{btnDisable(false)}
}
function createDefault(kind,slug,fields){
 const v={id:slug};
 if(kind==='site')return {...v,name:fields.name,url:fields.url,sector:fields.sector,summary:fields.summary,screenshot_url:'',featured:false,design_strengths:[]};
 if(kind==='module')return {...v,title:fields.name,site_id:fields.site_id,category:fields.sector,lesson:fields.summary,summary:fields.summary,screenshot_url:''};
 if(kind==='pattern')return {...v,title:fields.name,family:fields.sector,question:fields.summary,principle:fields.principle,modules:[]};
 return {...v,title:fields.name,subtitle:fields.summary,category:fields.sector,author:fields.author||'B2B Atlas 编辑部',sections:[{title:'正文',blocks:[{type:'paragraph',text:''}]}],tags:[],takeaways:[],featured:false,reading_minutes:3};
}
// V55.1 · Beginner creation: server still validates stable ASCII slugs, UI generates them.
let createSlugAuto=true,createSlugSuffix='';
function newCreateSuffix(){
 return Math.random().toString(36).slice(2,8).padEnd(6,'0');
}
function suggestedCreateSlug(title,kind){
 const ascii=String(title||'').normalize('NFKD').toLowerCase()
  .replace(/[\u0300-\u036f]/g,'').replace(/[^a-z0-9]+/g,'-')
  .replace(/^-+|-+$/g,'').slice(0,76).replace(/-+$/,'');
 const day=new Date().toISOString().slice(0,10).replace(/-/g,'');
 return (ascii||kind+'-'+day)+'-'+createSlugSuffix;
}
function syncCreateSlug(){
 const input=$('#cms-create-slug');if(!input)return;
 const title=$('#cms-create-fields [name="name"]')?.value||'';
 if(createSlugAuto)input.value=suggestedCreateSlug(title,$('#cms-create-kind').value);
 const preview=$('#cms-create-slug-preview');if(preview)preview.textContent=input.value;
}
function createFormError(text){
 const target=$('#cms-create-error');if(!target)return;
 target.hidden=!text;target.textContent=text||'';
}
function updateCreateFields(){
 const kind=$('#cms-create-kind').value,target=$('#cms-create-fields');
 if(!target)return;
 const fields=[
  ['name',kind==='site'?'网站名称':kind==='module'?'模块标题':kind==='pattern'?'设计模式名称':'文章标题',true],
  ['sector',kind==='site'?'所属行业':kind==='module'?'模块分类':kind==='pattern'?'模式类别':'文章分类',true],
  ['summary',kind==='site'?'案例简介':kind==='module'?'设计方法':kind==='pattern'?'要解决的问题':'文章摘要',true]
 ];
 if(kind==='site')fields.splice(1,0,['url','官方网站 URL',true]);
 if(kind==='module')fields.splice(1,0,['site_id','所属网站',true]);
 if(kind==='pattern')fields.push(['principle','核心设计原则',true]);
 // An optional author uses createDefault's editorial byline.
 if(kind==='article')fields.push(['author','作者',false]);
 target.innerHTML=fields.map(([id,label,required])=>{
  if(id==='site_id'&&state.siteChoices.length){
   return '<label>'+h(label)+'<select name="site_id" required><option value="">请选择已公开的网站</option>'
    +state.siteChoices.map(site=>'<option value="'+h(site.id)+'">'+h(site.name)+' · '+h(site.id)+'</option>').join('')+'</select></label>';
  }
  if(kind==='article'&&id==='sector'){
   const cats=state.categoryRecords.length?state.categoryRecords.map(x=>({id:x.id,name:x.name}))
    :(state.taxonomy.article||[]).map(id=>({id,name:id}));
   return '<label>'+h(label)+'<select name="sector" required><option value="">请选择文章分类</option>'
    +cats.map(cat=>'<option value="'+h(cat.id)+'">'+h(cat.name)+'</option>').join('')+'</select>'
    +(cats.length?'':'<small>请先在系统设置中添加文章分类。</small>')+'</label>';
  }
  if(id==='summary'||id==='principle')
   return '<label>'+h(label)+'<textarea name="'+id+'" rows="3" '+(required?'required ':'')+'maxlength="1800" placeholder="'+h(label)+'"></textarea></label>';
  const hint=id==='url'?'https://example.com':id==='name'?'输入内容标题':id==='site_id'?'网站英文标识':'';
  return '<label>'+h(label)+(required?'':' <small>选填</small>')+'<input name="'+id+'" '+(id==='url'?'type="url"':'type="text"')+(required?' required':'')+' maxlength="1800" placeholder="'+h(hint||label)+'"></label>';
 }).join('');
 createFormError('');
 syncCreateSlug();
}
async function createNew(e){
 e.preventDefault();if(mode!=='admin')return;
 const form=$('#cms-create-form');
 if(form.dataset.submitting==='true'||!form.reportValidity())return;
 const fd=new FormData(form),kind=String(fd.get('kind')||''),slug=String(fd.get('slug')||'').trim();
 if(!/^[a-z0-9][a-z0-9-]{1,110}$/.test(slug)){
  createFormError('网址标识只能包含英文小写、数字和短横线。');
  $('#cms-create-advanced').open=true;$('#cms-create-slug').focus();return
 }
 const fields=Object.fromEntries(fd.entries()),payload=createDefault(kind,slug,fields);
 const button=form.querySelector('button[type="submit"]');
 form.dataset.submitting='true';button.disabled=true;button.textContent='正在创建草稿…';createFormError('');
 try{
  await api('/api/admin/content',{method:'POST',body:JSON.stringify({kind,slug,payload})});
  $('#cms-create-dialog').close();form.reset();state.kind=kind;state.selected=null;state.q='';state.status='';state.page=1;
  $('#cms-search').value='';$('#cms-status').value='';
  history.replaceState({},'',listUrl());await loadKind();
  if(!await selectItem(slug,true))throw Error('草稿已创建，但编辑器尚未成功载入，请刷新内容列表。');
  message('草稿已创建，可以继续编辑图片和正文。');
 }catch(err){
  const detail=err.status===409?'网址标识已被使用。请展开高级选项更换标识，再次创建。':err.message;
  createFormError(detail);message(detail,false);
  if(err.status===409)$('#cms-create-advanced').open=true;
 }finally{
  form.dataset.submitting='false';button.disabled=false;button.textContent='创建草稿并继续编辑';
 }
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
 if(!kinds[kind])return false;
 if(state.busy){message('草稿正在保存，请完成后切换内容类型。',false);return false}
 if(state.dirty&&!confirm('当前修改尚未保存，确定切换？'))return false;
 if(state.dirty)clearRecovery();
 clearTimeout(autosaveTimer);editGeneration++;autosavePaused=false;
 state.kind=kind;state.items=[];state.selected=null;state.dirty=false;state.records={};
 setStudioMode(false);state.q='';state.status='';state.page=1;state.selectedSlugs.clear();
 markWorkspace('content');
 $('#cms-search').value='';$('#cms-status').value='';
 $('#cms-empty').hidden=false;$('#cms-editor-body').hidden=true;
 $('#cms-empty').innerHTML='<div class="cms-empty-symbol">✳</div><span class="section-eyebrow">CONTENT EDITOR</span><h2>选择一条内容，开始编辑。</h2><p>打开一条记录后，可以直接修改并保存草稿。</p>';
 if(push)history.pushState({},'',listUrl());
 closeMobile();
 try{await loadKind();return true}catch(e){message(e.message,false);return false}
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
  +(editable?'<div class="cms-block-add-row cms-v552-add-row" aria-label="插入正文内容">'
      +'<div class="cms-v552-quick-add"><button type="button" data-block-quick="paragraph">＋ 正文</button>'
      +'<button type="button" data-block-quick="image">＋ 图片</button>'
      +'<button type="button" data-block-quick="heading">＋ 小标题</button>'
      +'<button type="button" data-block-quick="list">＋ 列表</button></div>'
      +'<details class="cms-v552-more-blocks"><summary>更多内容类型</summary><div>'
      +'<select data-block-add-type aria-label="添加更多内容块类型">'
      +Object.entries(articleBlockTypes).filter(([key])=>!['paragraph','image','heading','list'].includes(key)).map(([key,label])=>'<option value="'+key+'">'+label+'</option>').join('')+'</select>'
      +'<button type="button" data-block-add>添加内容块</button></div></details>'
      +'<small>系统自动保存草稿。右上角箭头可以调整内容顺序。</small></div>':'')+'</div>';
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
   if(!captureArticleStructure())return;
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
// V53.1 · Undo/redo structural changes without overriding the browser's native text undo.
const articleStructureHistory={key:'',undo:[],redo:[]};
function resetArticleStructureHistory(){
 articleStructureHistory.key=state.selected?.kind+':'+state.selected?.slug;
 articleStructureHistory.undo=[];articleStructureHistory.redo=[];
 syncArticleStructureButtons();
}
function ensureArticleStructureHistory(){
 const key=state.selected?.kind+':'+state.selected?.slug;
 if(articleStructureHistory.key!==key)resetArticleStructureHistory();
}
function syncArticleStructureButtons(){
 const undo=$('[data-article-undo]'),redo=$('[data-article-redo]');
 if(undo)undo.disabled=!can('edit')||!articleStructureHistory.undo.length||state.busy;
 if(redo)redo.disabled=!can('edit')||!articleStructureHistory.redo.length||state.busy;
}
function captureArticleStructure(){
 if(!can('edit')||state.selected?.kind!=='article'||state.busy)return false;
 ensureArticleStructureHistory();
 const snapshot=JSON.stringify(readArticleSections());
 if(articleStructureHistory.undo.at(-1)!==snapshot){
  articleStructureHistory.undo.push(snapshot);
  if(articleStructureHistory.undo.length>20)articleStructureHistory.undo.shift();
 }
 articleStructureHistory.redo.length=0;
 syncArticleStructureButtons();
 return true;
}
function restoreArticleStructure(direction){
 if(!can('edit')||state.selected?.kind!=='article'||state.busy)return;
 ensureArticleStructureHistory();
 const history=articleStructureHistory,source=direction==='undo'?history.undo:history.redo,
  target=direction==='undo'?history.redo:history.undo;
 if(!source.length)return;
 const previous=source.pop(),current=JSON.stringify(readArticleSections());
 target.push(current);if(target.length>20)target.shift();
 const sections=JSON.parse(previous);
 if(!Array.isArray(sections)||!sections.length)return;
 $('#cms-v51-sections').innerHTML=sections.map((section,i)=>articleSection(section,i,true)).join('');
 reindexSections();markDraftDirty();refreshArticlePreview();refreshArticleHealth();
 syncArticleStructureButtons();
 message(direction==='undo'?'已撤销上一次结构修改':'已重做结构修改');
}
// Prepublish photo audit, computed locally from unsaved article blocks.
function refreshArticleHealth(){
 if(state.selected?.kind!=='article')return;
 const status=$('#cms-article-health-status'),details=$('#cms-article-health-list'),stats=$('#cms-article-stat');
 if(!status||!details||!stats)return;
 const sections=readArticleSections(),issues=[];
 let blocks=0,images=0,characters=0;
 sections.forEach((section,chapter)=>{
  characters+=String(section.title||'').length;
  if(Array.isArray(section.blocks)){
   section.blocks.forEach((block,index)=>{
    blocks++;
    characters+=String(block.text||(block.items||[]).join(' ')||'').length;
    if(block.type==='image'){
     images++;
     // Stable editor order: chapter and block index (not a database row number).
     if(!String(block.src||'').trim())issues.push({label:'章节 '+(chapter+1)+'：图片块尚未选择图片',chapter,index,action:'image'});
     else if(!String(block.alt||'').trim())issues.push({label:'章节 '+(chapter+1)+'：图片缺少替代文字 ALT',chapter,index,action:'alt'});
     if(block.src&&!String(block.caption||'').trim())issues.push({label:'章节 '+(chapter+1)+'：建议补充图注或来源',chapter,index,action:'caption',advisory:true});
    }
   });
  }else{
   blocks+=(section.paragraphs||[]).length+(section.bullets?.length?1:0)+(section.callout?1:0);
   characters+=(section.paragraphs||[]).join('').length;
   if(section.image){images++;issues.push({label:'章节 '+(chapter+1)+'：旧版配图没有独立 ALT 字段',chapter,action:'convert'})}
  }
 });
 const cover=$('#field-cover_image')?.value||'';
 if(cover)images++;
 stats.textContent=sections.length+' 个章节 · '+blocks+' 个正文块 · '+characters+' 字符';
 const required=issues.filter(x=>!x.advisory).length;
 status.textContent=images+' 张图片 · '+(required?required+' 项需要处理':'替代文字已检查')+(issues.some(x=>x.advisory)?' · 有图注建议':'');
 status.dataset.health=required?'warning':'ok';
 details.innerHTML=issues.length?issues.map(item=>
  '<button type="button" class="cms-v531-health-row" data-article-health-chapter="'+item.chapter+'"'
  +(item.index!==undefined?' data-article-health-block="'+item.index+'"':'')
  +' data-article-health-action="'+item.action+'"><span>'+h(item.label)+'</span><strong>'
  +(item.action==='convert'?'转换章节':item.action==='image'?'选择图片':'定位编辑')+' ↗</strong></button>').join('')
  :'<p class="cms-v531-health-clear">图片检查通过。这里检查文章配图的缺失项，不会自动发布内容。</p>';
}
function focusArticleHealth(button){
 const chapter=$$('#cms-v51-sections [data-v51-section]')[Number(button.dataset.articleHealthChapter)];
 if(!chapter)return;
 if(button.dataset.articleHealthAction==='convert'){
  if(!captureArticleStructure())return;
  convertLegacyChapter(chapter);
  const field=chapter.querySelector('[data-block-alt]');if(field)field.focus();
  refreshArticleHealth();syncArticleStructureButtons();return;
 }
 const block=$$('[data-cms-block]',chapter)[Number(button.dataset.articleHealthBlock)];
 if(!block)return;
 const action=button.dataset.articleHealthAction;
 if(action==='image'){const pick=block.querySelector('[data-block-pick-image]');if(pick)pick.click();return}
 const input=block.querySelector(action==='alt'?'[data-block-alt]':'[data-block-caption]');
 if(input){input.focus();input.scrollIntoView({block:'center',behavior:'smooth'})}
}

function articleStudio(v,editable){
 const disabled=editable?'':' disabled';
 const categorySuggestions=(state.taxonomy.article||[]).map(x=>'<option value="'+h(x)+'"></option>').join('');
 return '<section class="cms-v51-studio cms-v552-studio"><div class="cms-v51-studio-head"><div><span class="section-eyebrow">文章正文</span><h3>编写文章正文</h3><p>先写章节，再添加正文或图片；标题、图片和段落可随时调整顺序。</p></div></div>'
 +'<div class="cms-v531-editor-bar"><div><strong>文章结构</strong><span id="cms-article-stat">正在计算章节和字数…</span></div>'
 +'<div class="cms-v531-undo-actions">'+(editable?'<button type="button" data-article-undo disabled title="撤销章节或内容块的增删、移动、转换">↶ 撤销操作</button><button type="button" data-article-redo disabled title="重做上一次结构修改">↷ 重做</button>':'')+'</div></div>'
 +'<div class="cms-v51-chapter-head"><strong>正文与章节</strong>'+(editable?'<button type="button" data-v51-add>＋ 新建章节</button>':'')+'</div>'
 +'<div id="cms-v51-sections">'+(v.sections||[]).map((s,i)=>articleSection(s,i,editable)).join('')+'</div>'
 +'<details class="cms-v552-optional-content"><summary>文章标签与核心观点 <small>选填 · 不影响正文编辑</small></summary>'
 +'<div class="cms-v51-taxonomy"><label>文章标签 <small>每行一个关键词</small><textarea id="v51-tags" rows="3"'+disabled+'>'+h((v.tags||[]).join('\n'))+'</textarea></label>'
 +'<label>核心观点 <small>每行一条摘要</small><textarea id="v51-takeaways" rows="3"'+disabled+'>'+h((v.takeaways||[]).join('\n'))+'</textarea></label></div>'
 +'<div class="cms-v512-suggestions"><span>常用标签</span>'+(state.tagSuggestions.length?state.tagSuggestions.slice(0,12).map(tag=>'<button type="button" data-v512-tag="'+h(tag)+'"'+(editable?'':' disabled')+'>'+h(tag)+'</button>').join(''):'<small>暂无常用标签</small>')+'</div>'
 +'<datalist id="v51-categories">'+categorySuggestions+'</datalist></details>'
 +'<div class="cms-v531-media-health"><div class="cms-v531-health-head"><div><strong>发布前图片检查</strong><p>添加图片后，这里会提醒补全图片描述；点击提示即可定位。</p></div><span id="cms-article-health-status" role="status">等待检查…</span></div><div id="cms-article-health-list"></div></div>'
 +'<details class="cms-v552-article-tools"><summary>写作帮助与文章预览 <small>选填</small></summary>'
 +'<p class="cms-v531-undo-note">撤销操作仅记录最近 20 次章节和内容块结构修改；正文文字可用 Ctrl/⌘+Z 撤销。</p>'
 +'<p class="cms-v51-guidance">正文、列表、重点提示和图片可以组合使用。完整的 SEO 检查可在顶部「SEO」页完成。</p>'
 +'<div class="cms-v512-preview-actions"><button type="button" data-v512-preview aria-expanded="false">预览当前文章（无需保存）</button><small>只在当前浏览器展示，不会公开</small></div>'
 +'<section id="cms-v512-preview" class="cms-v512-preview" hidden><div class="cms-v512-preview-heading"><strong>文章排版预览</strong><span>PRIVATE · UNSAVED</span></div>'
 +'<p id="cms-v512-preview-error" hidden role="alert"></p><div id="cms-v512-preview-content"></div></section></details></section>';
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
 const selectable=state.items.filter(x=>x.status!=='source');
 const visibleEligible=listPage(listFiltered()).filter(x=>bulkEligibility(x).ok);
 const action=$('#cms-bulk-action')?.value||'submit',rule=bulkActionRules[action];
 bar.hidden=mode!=='admin'||!(can('edit')||can('review'))||selectable.length===0;
 const chosen=state.selectedSlugs.size;
 bar.dataset.hasSelection=chosen?'true':'false';
 const count=$('#cms-selected-count'),run=$('#cms-bulk-run'),clear=$('#cms-bulk-clear');
 count.textContent=chosen?'已选 '+chosen+' / 20 条':'';
 count.hidden=!chosen;
 clear.hidden=!chosen;
 run.hidden=!chosen;
 run.textContent=(rule?.button||'执行操作')+(chosen?'（'+chosen+'）':'');
 $('#cms-bulk-help').textContent=(rule?'仅支持'+rule.help+'；':'')+'本页 '+visibleEligible.length+' 条符合条件，每批最多 20 条。';
 const cap=Math.min(visibleEligible.length,20);
 const selectedVisible=visibleEligible.filter(x=>state.selectedSlugs.has(x.slug)).length;
 $('#cms-select-all').checked=cap>0&&selectedVisible===cap;
 $('#cms-select-all').disabled=cap===0;
 document.querySelectorAll('[data-bulk-select]').forEach(input=>{
  const item=state.items.find(x=>x.slug===input.dataset.bulkSelect);
  const eligibility=item?bulkEligibility(item):{ok:false,reason:'记录已变化，请刷新列表'};
  const atLimit=chosen>=20&&!input.checked;
  input.disabled=!eligibility.ok||atLimit;
  input.title=!eligibility.ok?eligibility.reason:atLimit?'每批最多选择 20 条':'';
 });
}
async function runBulk(){
 if(mode!=='admin'||state.busy)return;
 if(state.dirty||autosavePaused){message('请先完成草稿保存，再执行批量操作。',false);return}
 const action=$('#cms-bulk-action').value,rule=bulkActionRules[action];
 if(!rule||!can(rule.permission)){message('当前角色没有该批量操作权限。',false);return}
 const items=state.items.filter(x=>state.selectedSlugs.has(x.slug));
 if(!items.length){message('请先选择符合条件的内容。',false);return}
 if(items.some(x=>!bulkEligibility(x,action).ok)){
  message('所选内容状态已变化，请重新选择符合条件的内容。',false);return;
 }
 if(items.length>20){message('每批最多操作 20 条内容，请分批处理。',false);return}
 if(!confirm('确定对 '+items.length+' 条内容执行「'+rule.verb+'」？该操作将写入版本历史。'))return;
 btnDisable(true);$('#cms-bulk-run').disabled=true;
 try{
   const res=await api('/api/admin/content/bulk',{method:'POST',body:JSON.stringify({
     kind:state.kind,action,items:items.map(x=>({slug:x.slug,expected_revision:x.revision}))
   })});
   state.dirty=false;await loadKind(false);
   message('批量操作成功：'+res.results.length+' 条，所有记录已更新。');
 }catch(e){message(e.message,false)}finally{btnDisable(false);updateBulkToolbar()}
}
async function openMedia(){
 if(mode!=='admin'||!can('media')){message('当前账号没有媒体管理权限，请联系管理员。',false);return}
 const dialog=$('#cms-media-dialog'),picking=Boolean(state.mediaField||state.mediaTarget);
 const gallery=state.mediaField==='field-gallery',inline=Boolean(state.mediaTarget);
 dialog.classList.toggle('cms-media-picker-mode',picking);
 dialog.setAttribute('aria-label',picking?'为当前内容选择图片':'媒体资源与 SEO 工作台');
 $('#cms-media-dialog-title').textContent=picking?(gallery?'添加案例页面截图':inline?'插入文章图片':'选择展示图片'):'媒体资源与 SEO';
 $('#cms-media-dialog-description').textContent=picking
  ?(gallery?'选择已有截图，或上传多张图片加入案例。默认只展示封面，其他截图可稍后管理。'
    :inline?'选择图片插入当前章节，也可以直接上传一张新图片。'
    :'选择已有图片，或上传一张新图片自动填入当前内容。')
  :'查找图片、维护可复用的 ALT 与图注、查看引用关系。删除引用中的图片会被服务器阻止。';
 $('#cms-media-picker-intro').hidden=!picking;
 hideBulkAltEditor();
 if(picking){
  // A previously filtered SEO workbench must never look like an empty image picker.
  Object.assign(mediaWorkbench,{query:'',usage:'all',fileType:'all',seo:'all',offset:0});
  mediaWorkbench.selected.clear();
  $('#cms-media-search').value='';
  $('#cms-media-usage').value='all';
  $('#cms-media-type').value='all';
  $('#cms-media-seo').value='all';
 }
 if(!dialog.open)dialog.showModal();
 $('#cms-media-status').textContent='正在加载已有图片…';
 await refreshMedia();
 if(picking)$('#cms-media-search').focus({preventScroll:true});
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
// V53.2 · Server-backed media search and revision-safe management.
const mediaWorkbench={query:'',usage:'all',fileType:'all',seo:'all',offset:0,limit:24,total:0,selected:new Set(),request:0};
function mediaFilters(){
 const p=new URLSearchParams({q:mediaWorkbench.query,usage:mediaWorkbench.usage,
  file_type:mediaWorkbench.fileType,seo:mediaWorkbench.seo,
  offset:String(mediaWorkbench.offset),limit:String(mediaWorkbench.limit)});
 return p.toString();
}
function mediaReferenceLinks(item){
 const refs=Array.isArray(item.used_by)?item.used_by:[];
 if(!refs.length)return '<p>未发现当前 CMS 草稿或已发布内容引用。</p>';
 return '<div class="cms-v532-refs">'+refs.map(ref=>
  '<a href="/admin/content?kind='+encodeURIComponent(ref.kind)+'&edit='+encodeURIComponent(ref.slug)+'" target="_blank" rel="noopener noreferrer">'
   +h(kinds[ref.kind]?.title||ref.kind)+' · '+h(ref.slug)+'</a>').join('')+'</div>';
}
function renderMediaCards(){
 const grid=$('#cms-media-grid'),items=state.mediaRecords||[];
 const visibleIds=new Set(items.filter(x=>!x.usage_count).map(x=>x.id));
 for(const id of mediaWorkbench.selected)if(!visibleIds.has(id))mediaWorkbench.selected.delete(id);
 grid.innerHTML=items.length?items.map(item=>{
  const used=Number(item.usage_count||0),isSelected=mediaWorkbench.selected.has(item.id),alt=String(item.alt_text||''),caption=String(item.caption||'');
  return '<article class="cms-v51-media-item cms-v532-media-item" data-media-id="'+h(item.id)+'">'
   +'<div class="cms-v532-photo"><img src="'+h(item.url)+'" alt="'+h(alt||item.file_name||'媒体缩略图')+'" loading="lazy">'
   +'<label class="cms-v532-select"><input type="checkbox" data-media-check="'+h(item.id)+'"'+(isSelected?' checked':'')+(used?' disabled':'')+' aria-label="选择 '+h(item.file_name)+' 以批量删除"><span>选择</span></label></div>'
   +'<strong title="'+h(item.file_name)+'">'+h(item.file_name)+'</strong>'
   +'<small>'+Math.round(Number(item.byte_size||0)/1024)+' KB · '+h(String(item.mime_type||'').replace('image/','').toUpperCase())+' · '+h(String(item.created_at||'').slice(0,10))+'</small>'
   +(state.mediaTarget?'<button type="button" class="cms-v550-select-photo" data-v513-use-inline="'+h(item.url)+'">插入这张图片</button>'
     :state.mediaField?'<button type="button" class="cms-v550-select-photo" data-v51-use-media="'+h(item.url)+'">'+(state.mediaField==='field-gallery'?'添加这张截图':'使用这张图片')+'</button>':'')
   +'<div class="cms-v532-state"><span data-media-seo-status="'+(alt.trim()?'ready':'missing')+'">'+(alt.trim()?'已填写 ALT':'待补 ALT')+'</span><span>'+(used?'引用 '+used+' 条内容':'未引用')+'</span></div>'
   +(!alt.trim()&&can('media')?'<button type="button" class="cms-v557-alt-edit" data-v557-edit-alt="'+h(item.id)+'">补充图片 ALT</button>':'')
   +(used&&!state.mediaField&&!state.mediaTarget?'<button type="button" class="cms-v558-refs-open" data-v558-open-refs="'+h(item.id)+'">查看引用（'+used+'）</button>':'')
   +'<details class="cms-v532-details"><summary>SEO 信息与引用关系</summary><div class="cms-v532-details-body">'
   +'<label>图片 ALT（复用建议）<input data-media-alt maxlength="240" value="'+h(alt)+'" placeholder="说明图片内容，而不是堆砌关键词"></label>'
   +'<label>图片说明或来源<textarea data-media-caption maxlength="320" rows="2" placeholder="可选：图片背景和来源">'+h(caption)+'</textarea></label>'
   +(can('media')?'<button type="button" data-media-meta-save="'+h(item.id)+'">保存 SEO 资料</button>':'')
   +'<div class="cms-v532-references" tabindex="-1"><strong>当前引用（CMS 草稿与已发布内容）</strong>'+mediaReferenceLinks(item)
   +(used>20?'<p>引用数量较多，当前最多显示 20 条。</p>':'')+'</div></div></details>'
   +(can('media')?'<button type="button" data-media-crop="'+h(item.id)+'">裁剪 / 设置焦点</button>':'')
   +'<button type="button" data-v51-copy-media="'+h(item.url)+'">复制图片地址</button>'
   +(can('media')?'<button type="button" data-v51-delete-media="'+h(item.id)+'" class="cms-v51-delete"'+(used?' disabled title="被内容引用，不能删除"':'')+'>'+(used?'引用中 · 不可删除':'删除图片')+'</button>':'')
   +'</article>';
 }).join(''):'<p class="cms-loading">没有匹配的媒体。可以修改筛选条件，或上传新图片。</p>';
 const total=$('#cms-media-total');if(total)total.textContent='找到 '+mediaWorkbench.total+' 张 · 本页 '+items.length+' 张';
 const missing=items.filter(item=>!String(item.alt_text||'').trim()).length;
 const audit=$('#cms-v557-media-audit'),auditText=$('#cms-v557-alt-count'),auditButton=$('#cms-v557-show-missing');
 if(audit&&auditText&&auditButton){
  audit.hidden=Boolean(state.mediaField||state.mediaTarget);
  const inUse=items.filter(item=>Number(item.usage_count||0)>0).length;
  auditText.textContent='本页 '+missing+' 张待补 ALT · '+inUse+' 张已被引用'
   +(mediaWorkbench.seo==='missing'?' · 仅显示未填写':'');
  auditButton.textContent=mediaWorkbench.seo==='missing'?'查看全部媒体':'只看待补 ALT';
  const batch=$('#cms-v558-bulk-alt-open');
  batch.disabled=!missing||!can('media');
  batch.textContent='批量补 ALT（'+Math.min(20,missing)+'）';
 }
 const page=$('#cms-media-page');if(page)page.textContent='第 '+(Math.floor(mediaWorkbench.offset/mediaWorkbench.limit)+1)+' 页';
 const prev=$('#cms-media-prev'),next=$('#cms-media-next');
 if(prev)prev.disabled=mediaWorkbench.offset===0;
 if(next)next.disabled=mediaWorkbench.offset+mediaWorkbench.limit>=mediaWorkbench.total;
 updateMediaBulkSelection();
}
function updateMediaBulkSelection(){
 const count=mediaWorkbench.selected.size,button=$('#cms-media-bulk-delete');
 if(button){button.disabled=!count||!can('media');button.textContent='删除选中（'+count+'）'}
 const text=$('#cms-media-selected');if(text)text.textContent='已选择 '+count+' 张';
}
function hideBulkAltEditor(){
 const panel=$('#cms-v558-bulk-alt-panel');if(panel)panel.hidden=true;
}
function resetMediaFilters(){
 mediaWorkbench.offset=0;mediaWorkbench.selected.clear();hideBulkAltEditor();
}
function openBulkAltEditor(){
 if(!can('media')||state.mediaField||state.mediaTarget)return;
 const rows=(state.mediaRecords||[]).filter(item=>!String(item.alt_text||'').trim()).slice(0,20);
 if(!rows.length){message('本页图片已经全部填写了 ALT。');return}
 const root=$('#cms-v558-bulk-alt-inputs'),panel=$('#cms-v558-bulk-alt-panel');
 root.innerHTML=rows.map(item=>
  '<label class="cms-v558-alt-row"><span><strong>'+h(item.file_name)+'</strong><small>'
   +(item.usage_count?'已被 '+Number(item.usage_count)+' 条 CMS 内容引用':'尚未被 CMS 内容引用')
   +'</small></span><input type="text" data-v558-bulk-alt-id="'+h(item.id)+'" maxlength="240"'
   +' autocomplete="off" placeholder="例如：工业机器人在生产线上的操作界面" aria-label="为 '+h(item.file_name)+' 填写图片 ALT"></label>'
 ).join('');
 panel.hidden=false;
 $('#cms-v558-alt-note').textContent=rows.length+' 张可编辑；留空的图片不会提交。'
  +((state.mediaRecords||[]).filter(x=>!String(x.alt_text||'').trim()).length>20?'本批最多处理 20 张，请保存后继续。':'');
 updateBulkAltProgress();
 root.querySelector('input')?.focus({preventScroll:true});
}
function updateBulkAltProgress(){
 const inputs=Array.from(document.querySelectorAll('#cms-v558-bulk-alt-inputs [data-v558-bulk-alt-id]'));
 const done=inputs.filter(input=>input.value.trim()).length;
 $('#cms-v558-alt-progress').textContent='已填写 '+done+' / '+inputs.length+' 张';
 $('#cms-v558-alt-save').disabled=!done||!can('media');
}
async function saveBulkAlt(){
 if(!can('media')||state.mediaField||state.mediaTarget)return;
 const inputs=Array.from(document.querySelectorAll('#cms-v558-bulk-alt-inputs [data-v558-bulk-alt-id]'));
 const items=inputs.map(input=>({id:input.dataset.v558BulkAltId,alt_text:input.value.trim()}))
  .filter(item=>item.alt_text);
 if(!items.length){message('请至少填写一张图片的 ALT。',false);return}
 if(items.length>20){message('每批最多提交 20 张图片。',false);return}
 const current=new Map((state.mediaRecords||[]).map(item=>[item.id,item]));
 if(items.some(item=>!current.has(item.id)||String(current.get(item.id).alt_text||'').trim())){
  message('图片列表已经变化，请刷新后再保存。',false);return;
 }
 const save=$('#cms-v558-alt-save');save.disabled=true;
 try{
  const result=await api('/api/admin/media/bulk-alt',{method:'POST',body:JSON.stringify({items})});
  hideBulkAltEditor();
  await refreshMedia();
  message('已保存 '+result.updated+' 张图片 ALT。不会自动修改现有已发布页面。');
 }catch(e){
  $('#cms-v558-alt-note').textContent='保存未完成：'+e.message+'。请刷新图片列表后核对，已有输入仍保留。';
  message(e.message,false);
 }finally{updateBulkAltProgress()}
}
async function refreshMedia(){
 const seq=++mediaWorkbench.request;
 try{
  const res=await api('/api/admin/media?'+mediaFilters());
  if(seq!==mediaWorkbench.request)return false;
  const items=Array.isArray(res.items)?res.items:[];
  state.mediaRecords=items;
  mediaWorkbench.total=Number.isFinite(res.total)?res.total:items.length;
  // If the last image was deleted on a later page, return to the previous one.
  if(!items.length&&mediaWorkbench.total&&mediaWorkbench.offset>=mediaWorkbench.total){
   mediaWorkbench.offset=Math.max(0,mediaWorkbench.offset-mediaWorkbench.limit);
   return refreshMedia();
  }
  $('#cms-media-status').textContent=mediaWorkbench.total?'已加载 '+mediaWorkbench.total+' 张符合条件的图片。':'媒体库暂无图片或没有匹配结果 · 可上传 JPG、PNG 或 WebP。';
  renderMediaCards();return true;
 }catch(e){
  if(seq!==mediaWorkbench.request)return false;
  $('#cms-media-status').textContent='媒体列表加载失败：'+e.message;
  message(e.message,false);return false
 }
}
function applyMediaSeoDefaults(container,url){
 const record=(state.mediaRecords||[]).find(x=>x.url===url);
 if(!record||!container)return;
 const alt=container.querySelector('[data-block-alt]'),caption=container.querySelector('[data-block-caption]');
 if(alt&&!alt.value.trim())alt.value=record.alt_text||'';
 if(caption&&!caption.value.trim())caption.value=record.caption||'';
}
async function saveMediaSeo(button){
 if(!can('media'))return;
 const card=button.closest('[data-media-id]'),id=card?.dataset.mediaId;
 if(!id)return;
 const alt_text=card.querySelector('[data-media-alt]').value.trim(),
  caption=card.querySelector('[data-media-caption]').value.trim();
 button.disabled=true;
 try{
  await api('/api/admin/media/'+id+'/metadata',{method:'PUT',body:JSON.stringify({alt_text,caption})});
  message('图片 SEO 资料已保存。已发布文章中的 ALT 不会被自动修改。');
  await refreshMedia();
 }catch(e){$('#cms-media-status').textContent='SEO 资料保存失败：'+e.message;message(e.message,false)}
 finally{button.disabled=false}
}
async function bulkDeleteMedia(){
 if(!can('media')||!mediaWorkbench.selected.size)return;
 const ids=[...mediaWorkbench.selected];
 if(ids.length>20){message('每次最多删除 20 张图片。',false);return}
 const used=ids.filter(id=>(state.mediaRecords||[]).find(item=>item.id===id)?.usage_count);
 if(used.length){message('当前选择含有引用中的图片，已取消操作。',false);return}
 if(!confirm('确定永久删除选中的 '+ids.length+' 张未引用图片？此操作无法撤销，服务端会再次校验所有引用。'))return;
 const button=$('#cms-media-bulk-delete');button.disabled=true;
 try{
  const result=await api('/api/admin/media/bulk-delete',{method:'POST',body:JSON.stringify({ids})});
  mediaWorkbench.selected.clear();
  await refreshMedia();
  message('已安全删除 '+result.deleted+' 张未引用图片。');
 }catch(e){$('#cms-media-status').textContent='批量删除失败：'+e.message;message(e.message,false)}
 finally{updateMediaBulkSelection()}
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
 picker.disabled=false;dropzone.disabled=false;
 const refreshed=await refreshMedia();
 $('#cms-media-status').textContent='上传完成：成功 '+uploaded+' 张'+(failed?'，失败 '+failed+' 张，请检查文件格式及权限。':'。图片已保存到媒体库。')+(refreshed?'':'（列表刷新失败，请稍后重试）');
 if(uploadedUrls.length&&state.mediaField==='field-gallery'){
   state.mediaField=null;$('#cms-media-dialog').close();addGalleryImages(uploadedUrls);return uploaded;
 }
 if(uploaded===1&&lastUrl&&state.mediaField){
   const target=document.getElementById(state.mediaField);
   if(target){target.value=lastUrl;state.mediaField=null;$('#cms-media-dialog').close();markDraftDirty();syncSiteImage();refreshArticlePreview();refreshSeoSnippet();message('图片已关联到当前字段，请保存草稿')}
 }
 if(uploaded===1&&lastUrl&&state.mediaTarget){
   const target=state.mediaTarget.querySelector('[data-block-image],[data-v513-image]');
   if(target){target.value=lastUrl;applyMediaSeoDefaults(state.mediaTarget,lastUrl);state.mediaTarget=null;$('#cms-media-dialog').close();markDraftDirty();refreshArticlePreview();refreshArticleHealth();message('图片已插入正文，记得保存草稿')}
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
function formatScheduleTime(iso){
 const date=new Date(iso);
 if(!Number.isFinite(date.valueOf()))return '时间未知';
 return date.toLocaleString('zh-CN',{year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false});
}
function syncScheduleEditor(item){
 const input=$('#cms-schedule-local');if(!input)return;
 input.min=datetimeLocal(new Date(Date.now()+61000).toISOString());
 if(item.schedule?.status==='pending')input.value=datetimeLocal(item.schedule.publish_at);
}
function focusReviewSchedule(){
 if(!can('review')||state.selected?.status!=='review')return;
 setEditorTab('review');
 const schedule=$('#cms-editor-body .cms-review-schedule');
 if(!schedule)return;
 schedule.open=true;
 const input=$('#cms-schedule-local');
 if(input){input.scrollIntoView({block:'nearest'});input.focus({preventScroll:true})}
}
async function openItemCalendar(){
 if(!can('view')||!state.selected)return;
 const publishAt=state.selected.schedule?.publish_at;
 if(!publishAt){message('这条内容尚未安排发布日期。',false);return}
 const date=new Date(publishAt);
 if(!Number.isFinite(date.getTime())){message('日期无效，请刷新内容后再查看日历。',false);return}
 calendarCursor=new Date(date.getFullYear(),date.getMonth(),date.getDate());
 $('#cms-calendar-status').value='pending';
 await openScheduleQueue();
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
   message('发布排期已保存 · '+formatScheduleTime(schedule.publish_at)+'（本地时间）');
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
function scheduleIssue(item,now=Date.now()){
 if(['stale','failed'].includes(item.status))return item.status==='stale'
  ?'排期版本失效，请重新确认内容版本后预约。'
  :'自动发布检查失败，请核对内容和图片，再重新预约。';
 if(item.status!=='pending')return '';
 if(Number.isFinite(Number(item.current_revision))&&item.current_revision!=null&&Number(item.current_revision)!==Number(item.revision))
  return '排期版本与当前内容不一致，请重新确认审核版本。';
 const at=Date.parse(item.publish_at);
 if(Number.isFinite(at)&&at<=now)return '计划时间已到，尚未确认发布；请刷新排期核对实际状态。';
 return '';
}
function calendarVisibleRows(){
 const status=$('#cms-calendar-status')?.value||'all';
 return state.scheduleItems.filter(item=>status==='all'||(status==='attention'?Boolean(scheduleIssue(item)):item.status===status));
}
function paintScheduleSummary(){
 const root=$('#cms-v556-schedule-summary');if(!root)return;
 const counts={pending:0,published:0,failed:0,stale:0};
 state.scheduleItems.forEach(item=>{if(Object.hasOwn(counts,item.status))counts[item.status]++});
 const attention=state.scheduleItems.filter(item=>scheduleIssue(item)).length;
 const now=Date.now();
 const nextDay=state.scheduleItems.filter(item=>item.status==='pending'&&!scheduleIssue(item)&&Date.parse(item.publish_at)>now&&Date.parse(item.publish_at)<=now+86400000).length;
 root.innerHTML='<button type="button" data-v556-schedule-filter="pending" aria-pressed="'+String($('#cms-calendar-status').value==='pending')+'"><strong>'+counts.pending+'</strong><span>待发布</span></button>'
  +'<button type="button" data-v556-schedule-filter="published" aria-pressed="'+String($('#cms-calendar-status').value==='published')+'"><strong>'+counts.published+'</strong><span>已发布</span></button>'
  +'<button type="button" data-v556-schedule-filter="attention" aria-pressed="'+String($('#cms-calendar-status').value==='attention')+'"'+(!attention?' disabled':'')+'><strong>'+attention+'</strong><span>需处理</span></button>';
 const hint=$('#cms-v557-schedule-alert');
 if(hint){
  hint.hidden=!attention&&!nextDay;
  hint.textContent=(attention?'有 '+attention+' 条排期需要核对；点击“需处理”集中查看。':'')
   +(attention&&nextDay?' ':'')+(nextDay?'未来 24 小时内有 '+nextDay+' 条计划发布。':'')
   +' 排期到期检查依赖服务器请求，刷新可核对最新状态。';
 }
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
 paintScheduleSummary();
 $('#cms-schedule-count').textContent=rows.length+' 条排期记录';
 const labels={pending:'等待发布',published:'按计划发布',cancelled:'已取消',stale:'版本已失效',failed:'校验失败'};
 box.innerHTML=rows.length?rows.map(item=>{
   const issue=scheduleIssue(item),canResolve=Boolean(issue)&&can('review');
   const label=issue&&item.status==='pending'?'待核对':labels[item.status]||item.status;
   return '<div class="cms-v514-schedule-item'+(issue?' cms-v557-schedule-issue':'')+'" role="listitem"><div class="cms-v514-schedule-item-top">'
    +'<strong>'+h(item.slug)+'</strong><span data-schedule-status="'+h(item.status)+'">'+h(label)+'</span></div>'
    +'<p>'+h(kinds[item.kind]?.title||item.kind)+' · '+h(formatScheduleTime(item.publish_at))+'（本地） · v'+item.revision+'</p>'
    +(item.error?'<small>'+h(item.error)+'</small>':'')
    +(issue?'<p class="cms-v557-schedule-help" role="note">'+h(issue)+'</p>':'')
    +'<button type="button" data-v514-schedule-open="'+h(item.kind)+':'+h(item.slug)+'"'
    +(canResolve?' data-v557-schedule-resolve="true"':'')+'>'+(canResolve?'处理此排期':'打开内容')+'</button></div>';
 }).join('')
    :'<p class="cms-loading">暂无符合条件的排期。可调整筛选或刷新检查发布状态。</p>';
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
// V53.0 — One cross-category review inbox instead of reviewing one hidden filter at a time.
async function refreshReviewQueue(){
 if(!can('view'))return;
 const status=$('#cms-review-queue-status'),root=$('#cms-review-queue');
 status.textContent='正在读取四类内容的待审核稿…';
 root.innerHTML='<p class="cms-loading">读取中…</p>';
 const types=Object.keys(kinds);
 const settled=await Promise.allSettled(types.map(kind=>api('/api/admin/content?kind='+kind)));
 const pending=[],failures=[],counts={};
 settled.forEach((out,i)=>{
  const kind=types[i];
  if(out.status!=='fulfilled'||!Array.isArray(out.value?.items)){failures.push(kinds[kind].title);return}
  const entries=out.value.items.filter(x=>x.status==='review');
  counts[kind]=entries.length;
  entries.forEach(item=>pending.push({...item,kind}));
 });
 pending.sort((a,b)=>String(b.updated_at||b.updatedAt||'').localeCompare(String(a.updated_at||a.updatedAt||''),'zh'));
 const count=$('#cms-review-total');
 if(count){count.textContent=String(pending.length);count.hidden=!pending.length}
 status.dataset.state=failures.length?'warning':'ready';
 if(failures.length){
   status.textContent='部分栏目读取失败：'+failures.join('、')+'。已读取 '+pending.length+' 条待审核内容，请刷新后再核对。';
 }else{
   status.innerHTML='<strong>待审核 '+pending.length+' 条</strong>'
     +'<span>网站 '+(counts.site||0)+' · 模块 '+(counts.module||0)+' · 模式 '+(counts.pattern||0)+' · 文章 '+(counts.article||0)+'</span>';
 }
 root.innerHTML=pending.length?pending.map(item=>
  '<article class="cms-v530-review-row"><div><span>'+h(kinds[item.kind].title)+'</span>'
   +'<strong>'+h(item.label||item.slug)+'</strong><small>待审核 · v'+h(item.revision??0)+' · '+h(item.slug)+'</small></div>'
   +'<button type="button" data-review-open-kind="'+h(item.kind)+'" data-review-open-slug="'+h(item.slug)+'" aria-label="查看 '+h(item.label||item.slug)+' 的审核变更">'+(can('review')?'查看并审核':'查看审核进度')+'</button></article>').join('')
  :'<p class="cms-v530-review-empty">'+(failures.length?'已读取的栏目暂无待审核稿，其他栏目尚未成功读取。':'目前没有待审核内容，可以继续编辑或计划发布。')+'</p>';
}
async function openReviewQueue(){
 if(!can('view')){message('当前账号没有内容查看权限。',false);return}
 markWorkspace('review');
 const dialog=$('#cms-review-dialog');
 if(!dialog.open)dialog.showModal();
 closeMobile();
 try{await refreshReviewQueue()}catch(e){
  $('#cms-review-queue-status').textContent='审核队列读取失败，请点击刷新重试。';
  $('#cms-review-queue').textContent=e.message;
 }
}
// V57 · A compact SEO editor for homepage and four public catalog entry pages.
let siteSeoPages=[],siteSeoDirty=false,siteSeoBusy=false,siteSeoLast='home';
function selectedSiteSeo(){return siteSeoPages.find(x=>x.page===$('#cms-page-seo-page')?.value)}
function previewSiteSeo(){
 const item=selectedSiteSeo();if(!item)return;
 const title=$('#cms-page-seo-title').value.trim()||item.default_title;
 const desc=$('#cms-page-seo-desc').value.trim()||item.default_description;
 const suffix=title.startsWith('B2B Atlas')?'':' · B2B Atlas';
 $('#cms-page-seo-preview-url').textContent=location.host+(item.page==='home'?'/':'/'+item.page);
 $('#cms-page-seo-preview-title').textContent=title+suffix;
 $('#cms-page-seo-preview-desc').textContent=desc;
 const warnings=[];
 if(title.length>70)warnings.push('标题较长');
 if(desc.length<35)warnings.push('描述可以更具体');
 if(desc.length>170)warnings.push('描述较长');
 $('#cms-page-seo-preview-warnings').textContent='标题 '+title.length+' 字 · 描述 '+desc.length+' 字'+(warnings.length?' · '+warnings.join('、'):' · 基础检查通过');
}
function renderSiteSeo(){
 const item=selectedSiteSeo();if(!item)return;
 siteSeoLast=item.page;siteSeoDirty=false;
 const p=item.payload||{};
 for(const [field,value] of [['title',p.seo_title||''],['desc',p.seo_description||''],['image',p.seo_image||'']]){
  $('#cms-page-seo-'+field).value=value;
  $('#cms-page-seo-'+field).disabled=!can('edit');
 }
 $('#cms-page-seo-title').placeholder=item.default_title;
 $('#cms-page-seo-desc').placeholder=item.default_description;
 const labels={default:'使用系统默认 SEO',draft:'草稿（未公开）',review:'待审核（未公开）',published:'已发布（修改需重新审核）'};
 $('#cms-page-seo-state').textContent=labels[item.status]||item.status;
 $('#cms-page-seo-save').hidden=!can('edit');
 $('#cms-page-seo-submit').hidden=!can('edit')||item.status!=='draft';
 $('#cms-page-seo-publish').hidden=!can('review')||item.status!=='review';
 $('#cms-page-seo-reject').hidden=!can('review')||item.status!=='review';
 $('#cms-page-seo-pick-image').hidden=!can('edit')||!can('media');
 $('#cms-page-seo-clear-image').hidden=!can('edit');
 previewSiteSeo();
}
async function refreshSiteSeo(){
 const key=$('#cms-page-seo-page').value;
 const data=await api('/api/admin/seo/pages');
 siteSeoPages=data.pages||[];
 if(siteSeoPages.some(x=>x.page===key))$('#cms-page-seo-page').value=key;
 renderSiteSeo();
}
async function openSiteSeo(){
 if(!can('view'))return;
 if(state.dirty){message('请先保存或放弃当前内容草稿。',false);return}
 if($('#cms-settings-dialog').open)$('#cms-settings-dialog').close();
 const modal=$('#cms-page-seo-dialog');if(!modal.open)modal.showModal();
 markWorkspace('settings');closeMobile();
 $('#cms-page-seo-state').textContent='正在读取设置…';
 try{await refreshSiteSeo()}catch(e){$('#cms-page-seo-state').textContent='加载失败：'+e.message;message(e.message,false)}
}
async function updateSiteSeo(action){
 if(siteSeoBusy)return;
 const item=selectedSiteSeo();if(!item)return;
 if(action!=='save'&&siteSeoDirty){message('请先保存当前修改，再执行审核操作。',false);return}
 siteSeoBusy=true;
 for(const id of ['save','submit','publish','reject','refresh'])$('#cms-page-seo-'+id).disabled=true;
 try{
  const path='/api/admin/seo/pages/'+encodeURIComponent(item.page);
  const payload=action==='save'
   ?{expected_revision:item.revision,payload:{
     seo_title:$('#cms-page-seo-title').value,
     seo_description:$('#cms-page-seo-desc').value,
     seo_image:$('#cms-page-seo-image').value}}
   :{expected_revision:item.revision};
  await api(path+(action==='save'?'':'/'+action),{method:action==='save'?'PUT':'POST',body:JSON.stringify(payload)});
  await refreshSiteSeo();
  message(({save:'SEO 草稿已保存（尚未公开）',submit:'SEO 设置已提交审核',publish:'SEO 设置已正式发布',reject:'SEO 设置已退回草稿'})[action]);
 }catch(e){$('#cms-page-seo-state').textContent='操作失败：'+e.message;message(e.message,false)}
 finally{siteSeoBusy=false;for(const id of ['save','submit','publish','reject','refresh'])$('#cms-page-seo-'+id).disabled=false}
}

async function openSettingsHub(){
 if(!can('view')){message('当前账号没有查看设置的权限。',false);return}
 markWorkspace('settings');
 const dialog=$('#cms-settings-dialog');if(!dialog.open)dialog.showModal();
 closeMobile();
}
async function openReviewRecord(kind,slug){
 if(!can('view')||!kinds[kind]||!slug)return;
 // changeKind/selectItem already prompt for unsaved edits; do not ask twice.
 if(kind!==state.kind){await changeKind(kind,false);if(state.kind!==kind)return}
 const item=state.items.find(x=>x.slug===slug);
 if(!item){message('该条目已从待审核队列中移除，请刷新队列。',false);await refreshReviewQueue();return}
 await selectItem(slug,true);
 if(state.selected?.slug!==slug||state.selected?.kind!==kind)return;
 $('#cms-review-dialog').close();
 setEditorTab('review');
 markWorkspace('review');
}
async function openScheduleQueue(){
 if(!can('view'))return;
 markWorkspace('operations');
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
 // A missing screenshot should show a neutral icon, never a broken-image glyph.
 $('#cms-items').addEventListener('error',event=>{
   const img=event.target;
   if(!img.matches?.('.cms-item-thumb img'))return;
   const thumb=img.closest('.cms-item-thumb');
   if(!thumb||!thumb.contains(img))return;
   thumb.classList.add('cms-thumb-missing');
   thumb.innerHTML=icon(kinds[state.kind].icon);
 },true);
 // Start every privileged action hidden until /api/admin/team/me succeeds.
 $('#cms-audit-open').hidden=mode!=='admin';
 $('#cms-audit-open').addEventListener('click',()=>{
  if($('#cms-audit-panel').hidden)runPublishedSeoAudit();
  else closeSeoAudit();
 });
 $('#cms-audit-refresh').addEventListener('click',runPublishedSeoAudit);
 $('#cms-audit-close').addEventListener('click',()=>closeSeoAudit());
 $('#cms-audit-more').addEventListener('click',()=>{seoAuditShown+=12;renderSeoAuditRows()});
 $('#cms-audit-list').addEventListener('click',async event=>{
  const button=event.target.closest('[data-seo-audit-edit]');
  if(!button)return;
  const slug=button.dataset.seoAuditEdit;
  if(!state.items.some(x=>x.slug===slug)){
   message('该内容不在当前列表，请刷新后重试。',false);return;
  }
  await selectItem(slug,true);
 });
 for(const id of ['cms-new','cms-export','cms-media-open','cms-categories-open',
                  'cms-tags-open','cms-review-shortcut','cms-schedules-open',
                  'cms-settings-open','cms-team-open','cms-logout'])$('#'+id).hidden=true;
 $('#cms-tools-menu').hidden=true;
 $('#cms-login-link').hidden=mode!=='preview';
 $('#cms-role').textContent=mode==='admin'?'管理员 · 内容维护':'公开只读预览';
 setNotice(mode==='admin'?'管理员工作区：编辑先保存草稿，审核通过后才会进入公开目录。':'只读预览：这里展示公开网站资料，不会提供编辑或发布权限。');
 if(mode==='preview')$('#cms-state').innerHTML='<span class="status-led"></span> PUBLIC PREVIEW';
 document.addEventListener('click',async e=>{
   if(e.target.closest('[data-v559-create-first]')){
     if(!can('edit'))return;
     $('#cms-new').click();return;
   }
   const retry=e.target.closest('[data-v559-retry-load]');
   if(retry){
     if(state.busy)return;
     const slug=retry.dataset.v559RetryLoad;
     if(slug&&state.items.some(item=>item.slug===slug)){await selectItem(slug,true);return}
     if(slug){message('该记录当前不在列表中，请先刷新列表。',false)}
     try{await loadKind(false);message('内容列表已恢复')}
     catch(error){message('读取仍然失败：'+error.message,false)}
     return;
   }
   if(e.target.closest('[data-clear-content-filters]')){
     state.q='';state.status='';state.page=1;state.selectedSlugs.clear();$('#cms-search').value='';$('#cms-status').value='';
     markWorkspace('content');drawItems();$('#cms-search').focus();return;
   }
   if(e.target.closest('[data-schedule-open]')){focusReviewSchedule();return}
   if(e.target.closest('[data-schedule-calendar]')){await openItemCalendar();return}
   if(e.target.closest('[data-schedule-save]')){await saveSchedule();return}
   if(e.target.closest('[data-schedule-cancel]')){await cancelSchedule();return}
   const queueEntry=e.target.closest('[data-v514-schedule-open]');
   if(queueEntry){
     const [kind,...slugParts]=queueEntry.dataset.v514ScheduleOpen.split(':');
     const slug=slugParts.join(':'),resolveIssue=queueEntry.hasAttribute('data-v557-schedule-resolve');
     $('#cms-schedules-dialog').close();
     if(kind!==state.kind&&!await changeKind(kind))return;
     if(!await selectItem(slug,true)||state.selected?.kind!==kind||state.selected?.slug!==slug)return;
     if(resolveIssue&&can('review')){
      if(state.selected.status==='review'){
       focusReviewSchedule();
       message('请核对当前审核版本，选择未来的发布时间并重新保存。');
      }else{
       setEditorTab(state.selected.status==='draft'?'content':'history');
       message(state.selected.status==='draft'
        ?'这条内容需要先完成修改并重新提交审核，才能预约发布。'
        :'这条内容目前不能重新预约，请核对状态与版本历史。');
      }
     }
     return;
   }
   const teamEntry=e.target.closest('[data-v514-team-id]');
   if(teamEntry){chooseTeamPerson(teamEntry.dataset.v514TeamId);return}
   const close=e.target.closest('[data-v514-close]');
   if(close){$('#cms-'+close.dataset.v514Close+'-dialog').close();return}
   if(e.target.closest('[data-close-editor]')){closeEditor();return}
   if(e.target.closest('[data-editor-save]')){if(!state.dirty&&state.selected?.status!=='source')message('当前没有待保存的修改。');else if($('#cms-edit-form')?.reportValidity())await saveDraft({preventDefault(){}});return}
   if(e.target.closest('[data-editor-submit]')){await transition('submit');return}
   if(e.target.closest('[data-review-reload]')){if(state.busy||!state.selected)return;const slug=state.selected.slug;try{await loadKind(false);await selectItem(slug);clearTransitionFeedback();message('已重新读取服务器状态')}catch(e){showTransitionFeedback(e,'reload',false)}return}
   if(e.target.closest('[data-gallery-add]')){state.mediaTarget=null;state.mediaField='field-gallery';await openMedia();return}
   const galleryRemove=e.target.closest('[data-gallery-remove]');
   if(galleryRemove){const items=galleryValue();items.splice(Number(galleryRemove.dataset.galleryRemove),1);updateGallery(items);return}
   const galleryMove=e.target.closest('[data-gallery-move]');
   if(galleryMove){const items=galleryValue(),i=Number(galleryMove.dataset.galleryMove),j=i+Number(galleryMove.dataset.galleryDirection);if(j>=0&&j<items.length){[items[i],items[j]]=[items[j],items[i]];updateGallery(items)}return}
   const galleryCover=e.target.closest('[data-gallery-cover]');
   if(galleryCover){const photo=galleryValue()[Number(galleryCover.dataset.galleryCover)],input=$('#field-screenshot_url');if(photo&&input){input.value=photo.url;syncSiteImage();markDraftDirty();message('已设为案例封面。')}return}
   const mediaPicker=e.target.closest('[data-editor-pick-media]');
   if(mediaPicker){state.mediaTarget=null;state.mediaField=mediaPicker.dataset.editorPickMedia;await openMedia();return}
   if(e.target.closest('[data-seo-image-clear]')){const input=$('#field-seo_image');if(input){input.value='';markDraftDirty();refreshSeoSnippet()}return}
   const stageLink=e.target.closest('[data-editor-state-link]');
   if(stageLink){
     const tab=stageLink.dataset.editorStateLink;
     setEditorTab(tab);
     const focusTab=$('#cms-editor-body [data-editor-tab="'+tab+'"]');
     if(focusTab)focusTab.focus({preventScroll:true});
     const pane=$('#cms-editor-body [data-editor-pane="'+tab+'"]');
     if(pane)pane.scrollIntoView({block:'start'});
     return;
   }
   const tab=e.target.closest('[data-editor-tab]');
   if(tab){setEditorTab(tab.dataset.editorTab);return}
   const tabLink=e.target.closest('[data-editor-tab-link]');
   if(tabLink){setEditorTab(tabLink.dataset.editorTabLink);return}
   const photo=e.target.closest('[data-preview-photo]');
   if(photo){const hero=$('#cms-preview-hero'),group=photo.parentElement;
     if(hero){hero.src=photo.dataset.previewSrc;hero.alt=photo.dataset.previewAlt;}
     for(const button of group?.querySelectorAll('[data-preview-photo]')||[])button.setAttribute('aria-pressed',String(button===photo));return}
   const themeButton=e.target.closest('[data-set-theme]');if(themeButton){setTheme(themeButton.dataset.setTheme);return}
   if(e.target.closest('[data-editor-open-media]')){state.mediaTarget=null;state.mediaField=state.selected?.kind==='article'?'field-cover_image':state.selected?.kind==='site'||state.selected?.kind==='module'?'field-screenshot_url':null;await openMedia();return}
   const type=e.target.closest('[data-kind-link]');if(type){e.preventDefault();await changeKind(type.dataset.kindLink);return}
   const quickCompare=e.target.closest('[data-review-compare]');
   if(quickCompare){
     if(!can('review')||state.busy)return;
     const slug=quickCompare.dataset.reviewCompare;
     if(!state.items.some(item=>item.slug===slug&&item.status==='review')){message('该记录已不在待审核列表，请刷新。',false);return}
     if(!await selectItem(slug,true))return;
     if(state.selected?.slug!==slug||state.selected.status!=='review')return;
     setEditorTab('review');markWorkspace('review');
     await openReviewDiff(0);return;
   }
   const reviewNext=e.target.closest('[data-v555-next-review]');
   if(reviewNext){
     if(!can('review')||state.busy)return;
     const slug=reviewNext.dataset.v555NextReview;
     if(!state.items.some(item=>item.slug===slug&&item.status==='review')){message('该内容的状态可能已变化，请刷新列表。',false);return}
     if(!await selectItem(slug,true))return;
     if(state.selected?.slug===slug){setEditorTab('review');markWorkspace('review')}
     return;
   }
   if(e.target.closest('[data-v555-review-list]')){
     if(!closeEditor())return;
     state.status='review';state.q='';state.page=1;state.selectedSlugs.clear();
     $('#cms-status').value='review';$('#cms-search').value='';
     markWorkspace('review');drawItems();return;
   }
   if(e.target.closest('[data-v555-review-queue]')){await openReviewQueue();return}
   const choice=e.target.closest('[data-pick]');if(choice){if(state.busy)return;await selectItem(choice.dataset.pick,true);return}
   const action=e.target.closest('[data-transition]');if(action){await transition(action.dataset.transition);return}
   const restore=e.target.closest('[data-restore]');if(restore){await restoreRevision(Number(restore.dataset.restore));return}
   const bulkCheck=e.target.closest('[data-bulk-select]');if(bulkCheck){
     const slug=bulkCheck.dataset.bulkSelect;
     if(bulkCheck.checked){
       if(state.selectedSlugs.size>=20){bulkCheck.checked=false;message('每批最多选择 20 条内容，请先执行或清空当前选择。',false);return}
       state.selectedSlugs.add(slug);
     }else state.selectedSlugs.delete(slug);
     updateBulkToolbar();return;
   }
   const tagPick=e.target.closest('[data-v513-tag]');if(tagPick){chooseTag(tagPick.dataset.v513Tag);return}
   if(e.target.closest('[data-v513-close-tags]')){$('#cms-tags-dialog').close();return}
   const picked=e.target.closest('[data-v515-pick]');if(picked){chooseCategory(picked.dataset.v515Pick);return}
   if(e.target.closest('[data-v515-close]')){$('#cms-categories-dialog').close();return}
   if(e.target.closest('[data-autosave-retry]')){if(autosavePaused){message('请先备份当前内容，再重新打开最新版本。',false);return}await persistDraft(false);return}
   if(e.target.closest('[data-autosave-copy]')){
     if(!state.selected||!autosavePaused)return;
     let backup='';
     try{
       const payload=takeFields();
       backup=JSON.stringify({kind:state.selected.kind,slug:state.selected.slug,payload},null,2);
     }catch(_){
       backup=Array.from($('#cms-edit-form')?.querySelectorAll('input,textarea,select')||[])
         .filter(el=>el.id&&el.value).map(el=>el.id+': '+el.value).join('\n');
     }
     if(!backup){message('无法生成备份，请手动复制当前表单内容。',false);return}
     try{
       await navigator.clipboard.writeText(backup);
       message('当前编辑内容已复制。请粘贴到本地文档备份，再重新打开最新记录。');
     }catch(_){message('浏览器不允许写入剪贴板，请手动复制表单内容后再刷新。',false)}
     return;
   }
   const tag=e.target.closest('[data-v512-tag]');if(tag){const field=$('#v51-tags');if(!field)return;const existing=linesFrom('#v51-tags');if(!existing.includes(tag.dataset.v512Tag)){field.value=[...existing,tag.dataset.v512Tag].join(String.fromCharCode(10));markDraftDirty();refreshArticlePreview()}return}
   const diffButton=e.target.closest('[data-review-diff]');
   if(diffButton){await openReviewDiff(Number(diffButton.dataset.reviewDiff||0));return}
    if(e.target.closest('[data-v518-close-diff]')){$('#cms-diff-dialog').close();return}
    const convert=e.target.closest('[data-block-convert]');
   if(convert){if(captureArticleStructure())convertLegacyChapter(convert.closest('[data-v51-section]'));return}
   const quickBlock=e.target.closest('[data-block-quick]'),addBlock=e.target.closest('[data-block-add]');
   if(quickBlock||addBlock){
     const mode=(quickBlock||addBlock).closest('[data-blocks-mode]');
     const type=quickBlock?quickBlock.dataset.blockQuick:mode?.querySelector('[data-block-add-type]')?.value;
     if(!mode||!articleBlockTypes[type]||!captureArticleStructure())return;
     const list=mode.querySelector('[data-block-list]');
     list.insertAdjacentHTML('beforeend',articleBlock({type},list.children.length,true));
     reindexBlocks(list);markDraftDirty();refreshArticlePreview();refreshArticleHealth();
     const inserted=list.lastElementChild;
     if(type==='image'){
       const pick=inserted.querySelector('[data-block-pick-image]');if(pick)pick.click();
     }else{
       const input=inserted.querySelector('[data-block-text]');if(input){input.focus();input.scrollIntoView({block:'nearest'});}
     }
     return;
   }
   const removeBlock=e.target.closest('[data-block-remove]');
   if(removeBlock){const el=removeBlock.closest('[data-cms-block]'),list=el.parentElement;
     if(list.children.length<=1){message('每章至少保留一个内容块',false);return}
     if(!captureArticleStructure())return;
     el.remove();reindexBlocks(list);markDraftDirty();refreshArticlePreview();return}
   const moveBlock=e.target.closest('[data-block-move]');
   if(moveBlock){const el=moveBlock.closest('[data-cms-block]'),n=Number(moveBlock.dataset.blockMove);
     const near=n<0?el.previousElementSibling:el.nextElementSibling;
     if(near&&captureArticleStructure()){if(n<0)near.before(el);else near.after(el);
       reindexBlocks(el.parentElement);markDraftDirty();refreshArticlePreview()}
     return}
   const blockFormat=e.target.closest('[data-block-format]');
   if(blockFormat){applyBlockFormat(blockFormat);return}
   const blockPick=e.target.closest('[data-block-pick-image]');
   if(blockPick){state.mediaField=null;state.mediaTarget=blockPick.closest('[data-cms-block]');await openMedia();return}
   if(e.target.closest('[data-open-seo-settings]')){setEditorTab('content');const seo=$('#cms-edit-form .cms-seo-settings');if(seo){seo.open=true;seo.scrollIntoView({block:'start',behavior:'smooth'});seo.querySelector('#field-seo_title')?.focus({preventScroll:true})}return}
    if(e.target.closest('[data-seo-check]')){await runSeoAudit();return}
    const formatter=e.target.closest('[data-v514-format]');if(formatter){applyArticleFormat(formatter);return}
   if(e.target.closest('[data-v512-preview]')){toggleArticlePreview();return}
   if(e.target.closest('[data-article-undo]')){restoreArticleStructure('undo');return}
   if(e.target.closest('[data-article-redo]')){restoreArticleStructure('redo');return}
   const health=e.target.closest('[data-article-health-action]');if(health){focusArticleHealth(health);return}
   if(e.target.closest('[data-v51-add]')){if(!captureArticleStructure())return;const root=$('#cms-v51-sections');root.insertAdjacentHTML('beforeend',articleSection({blocks:[{type:'paragraph',text:''}]},root.children.length,true));reindexSections();markDraftDirty();refreshArticlePreview();return}
   if(e.target.closest('[data-v51-remove]')){const blocks=document.querySelectorAll('#cms-v51-sections [data-v51-section]');if(blocks.length<=1){message('至少保留一个章节',false);return}if(!captureArticleStructure())return;e.target.closest('[data-v51-section]').remove();reindexSections();markDraftDirty();return}
   const move=e.target.closest('[data-v51-move]');if(move){const block=move.closest('[data-v51-section]'),target=Number(move.dataset.v51Move)<0?block.previousElementSibling:block.nextElementSibling;if(target&&captureArticleStructure()){if(Number(move.dataset.v51Move)<0)target.before(block);else target.after(block);reindexSections();markDraftDirty()}return}
   const useInline=e.target.closest('[data-v513-use-inline]');
   if(useInline&&state.mediaTarget){
     const input=state.mediaTarget.querySelector('[data-block-image],[data-v513-image]');
     if(input)input.value=useInline.dataset.v513UseInline;
     applyMediaSeoDefaults(state.mediaTarget,useInline.dataset.v513UseInline);
     state.mediaTarget=null;$('#cms-media-dialog').close();markDraftDirty();refreshArticlePreview();refreshArticleHealth();
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
   const useMedia=e.target.closest('[data-v51-use-media]');if(useMedia){if(state.mediaField==='field-gallery'){state.mediaField=null;$('#cms-media-dialog').close();addGalleryImages([useMedia.dataset.v51UseMedia]);return}const target=state.mediaField?document.getElementById(state.mediaField):null;if(target){target.value=useMedia.dataset.v51UseMedia;state.mediaField=null;markDraftDirty();syncSiteImage();refreshArticlePreview();refreshSeoSnippet();$('#cms-media-dialog').close();message('图片已选择，请保存草稿')}return}
   const copy=e.target.closest('[data-v51-copy-media]');if(copy){try{await navigator.clipboard.writeText(location.origin+copy.dataset.v51CopyMedia);message('图片地址已复制')}catch{message('请从媒体列表中手动复制地址',false)}return}
   if(e.target.closest('[data-media-close]')){state.mediaTarget=null;state.mediaField=null;$('#cms-media-dialog').close();return}
   if(e.target.closest('[data-dialog-close]')){$('#cms-create-dialog').close();return}
 });
 document.addEventListener('input',e=>{if(e.target.closest('[data-gallery-label]')){syncGalleryLabels();return}if(e.target.closest('#cms-edit-form')){markDraftDirty();syncSiteTitle();refreshArticlePreview();refreshSeoSnippet();refreshContentPreview()}});
 $('#cms-review-filter').addEventListener('click',()=>{
  if(mode!=='admin'||!can('review'))return;
  state.status='review';state.q='';state.page=1;state.selectedSlugs.clear();
  $('#cms-status').value='review';$('#cms-search').value='';
  markWorkspace('review');drawItems();
  const heading=$('#cms-browser-title');if(heading){heading.setAttribute('tabindex','-1');heading.focus({preventScroll:true})}
 });
 $('#cms-search').addEventListener('input',e=>{state.q=e.target.value;state.page=1;state.selectedSlugs.clear();drawItems()});
 $('#cms-status').addEventListener('change',e=>{state.status=e.target.value;state.page=1;state.selectedSlugs.clear();markWorkspace(state.status==='review'?'review':'content');drawItems()});
 $('#cms-sort').addEventListener('change',e=>{state.sort=e.target.value;state.page=1;state.selectedSlugs.clear();drawItems()});
 $('#cms-page-prev').addEventListener('click',()=>changeListPage(-1));
 $('#cms-page-next').addEventListener('click',()=>changeListPage(1));
 $('#cms-refresh').addEventListener('click',async()=>{
  if(state.dirty&&!confirm('当前草稿还有未保存的修改。确认重新读取服务器内容吗？'))return;
  try{await loadKind(true);message('内容列表已刷新')}catch(e){message(e.message,false)}
 });
 $('#cms-logout').addEventListener('click',logoutCms);
 $('#cms-export').addEventListener('click',exportCms);
 $('#cms-new').addEventListener('click',async()=>{
   if(state.busy||state.dirty){message('请先保存当前草稿，或返回列表后再新建内容。',false);return}
   if(state.kind==='article')try{await loadCmsTaxonomy()}catch(err){message(err.message,false)}
   if(state.kind==='module')await loadSiteChoices();
   const form=$('#cms-create-form');form.reset();
   $('#cms-create-kind').value=state.kind;$('#cms-create-advanced').open=false;
   createSlugAuto=true;createSlugSuffix=newCreateSuffix();updateCreateFields();
   $('#cms-create-dialog').showModal();
   $('#cms-create-fields [name="name"]')?.focus({preventScroll:true});
 });
 $('#cms-create-kind').addEventListener('change',async()=>{
  const kind=$('#cms-create-kind').value;
  if(kind==='module')await loadSiteChoices();
  if(kind==='article')try{await loadCmsTaxonomy()}catch(err){message(err.message,false)}
  if($('#cms-create-kind').value===kind)updateCreateFields();
 });
 $('#cms-create-fields').addEventListener('input',e=>{
  if(e.target.name==='name')syncCreateSlug();
  createFormError('');
 });
 $('#cms-create-slug').addEventListener('input',()=>{
  createSlugAuto=false;syncCreateSlug();createFormError('');
 });
 $('#cms-create-slug-auto').addEventListener('click',()=>{
  createSlugAuto=true;syncCreateSlug();$('#cms-create-slug').focus();
 });
 $('#cms-diff-baseline').addEventListener('change',e=>openReviewDiff(Number(e.target.value)));
 $('#cms-tags-open').addEventListener('click',openTagManager);
 $('#cms-tag-add').addEventListener('click',()=>chooseTag());
 $('#cms-tag-form').addEventListener('submit',saveTag);
 $('#cms-tag-delete').addEventListener('click',deleteTag);
 $('#cms-tag-search').addEventListener('input',e=>{state.tagSearch=e.target.value;drawTags()});
 $('#cms-review-shortcut').addEventListener('click',openReviewQueue);
 $('#cms-review-refresh').addEventListener('click',refreshReviewQueue);
 $('#cms-settings-open').addEventListener('click',openSettingsHub);
 $('#cms-page-seo-open').addEventListener('click',openSiteSeo);
 $('#cms-page-seo-close').addEventListener('click',()=>{
   if(siteSeoDirty&&!confirm('SEO 设置尚未保存，确定放弃修改吗？'))return;
   siteSeoDirty=false;$('#cms-page-seo-dialog').close();
 });
 $('#cms-page-seo-page').addEventListener('change',()=>{
   if(siteSeoDirty&&!confirm('当前修改未保存，确定切换页面吗？')){
     $('#cms-page-seo-page').value=siteSeoLast;return;
   }
   renderSiteSeo();
 });
 for(const id of ['title','desc'])$('#cms-page-seo-'+id).addEventListener('input',()=>{
   siteSeoDirty=true;previewSiteSeo();
 });
 $('#cms-page-seo-refresh').addEventListener('click',async()=>{
   if(siteSeoDirty&&!confirm('放弃未保存的修改并重新读取吗？'))return;
   try{await refreshSiteSeo()}catch(e){message(e.message,false)}
 });
 $('#cms-page-seo-pick-image').addEventListener('click',async()=>{
   state.mediaField='cms-page-seo-image';state.mediaTarget=null;await openMedia();
 });
 $('#cms-page-seo-clear-image').addEventListener('click',()=>{
   $('#cms-page-seo-image').value='';siteSeoDirty=true;previewSiteSeo();
 });
 for(const action of ['save','submit','publish','reject'])
   $('#cms-page-seo-'+action).addEventListener('click',()=>updateSiteSeo(action));
 for(const area of ['review','settings']){
  const dialog=$('#cms-'+area+'-dialog');
  dialog.addEventListener('close',()=>markWorkspace(state.selected?.status==='review'?'review':'content'));
 }
 $('#cms-settings-dialog').addEventListener('click',event=>{
  if(event.target.closest('.cms-v530-tool'))$('#cms-settings-dialog').close();
 });
 $('#cms-schedules-open').addEventListener('click',openScheduleQueue);
 $('#cms-schedules-dialog').addEventListener('close',()=>markWorkspace(state.status==='review'?'review':'content'));
 $('#cms-schedule-refresh').addEventListener('click',refreshSchedules);
 $('#cms-calendar-status').addEventListener('change',()=>{paintCalendar();paintScheduleQueue()});
 $('#cms-v556-schedule-summary').addEventListener('click',e=>{
  const button=e.target.closest('[data-v556-schedule-filter]');
  if(!button||button.disabled)return;
  const target=button.dataset.v556ScheduleFilter,select=$('#cms-calendar-status');
  select.value=select.value===target?'all':target;
  paintCalendar();paintScheduleQueue();
 });
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
 $('#cms-media-open').addEventListener('click',()=>{state.mediaTarget=null;state.mediaField=null;markWorkspace('media');closeMobile();openMedia()});
 $('#cms-media-dialog').addEventListener('close',()=>{mediaWorkbench.selected.clear();updateMediaBulkSelection();markWorkspace(state.selected?.status==='review'?'review':'content')});
 document.addEventListener('click',async event=>{
  const close=event.target.closest('[data-v530-close]');
  if(close){$('#cms-'+close.dataset.v530Close+'-dialog').close();return}
  const entry=event.target.closest('[data-review-open-kind][data-review-open-slug]');
  if(entry)await openReviewRecord(entry.dataset.reviewOpenKind,entry.dataset.reviewOpenSlug);
 });
 let mediaSearchTimer=0;
 $('#cms-media-search').addEventListener('input',e=>{
  mediaWorkbench.query=e.target.value;resetMediaFilters();clearTimeout(mediaSearchTimer);
  mediaSearchTimer=setTimeout(()=>refreshMedia(),240)
 });
 for(const [id,key] of [['cms-media-usage','usage'],['cms-media-type','fileType'],['cms-media-seo','seo']]){
  $('#'+id).addEventListener('change',e=>{mediaWorkbench[key]=e.target.value;resetMediaFilters();refreshMedia()});
 }
 $('#cms-media-prev').addEventListener('click',()=>{if(mediaWorkbench.offset>0){mediaWorkbench.offset-=mediaWorkbench.limit;mediaWorkbench.selected.clear();hideBulkAltEditor();refreshMedia()}});
 $('#cms-media-next').addEventListener('click',()=>{if(mediaWorkbench.offset+mediaWorkbench.limit<mediaWorkbench.total){mediaWorkbench.offset+=mediaWorkbench.limit;mediaWorkbench.selected.clear();hideBulkAltEditor();refreshMedia()}});
 $('#cms-media-select-unused').addEventListener('click',()=>{
  const available=(state.mediaRecords||[]).filter(item=>!item.usage_count).slice(0,20);
  mediaWorkbench.selected=new Set(available.map(x=>x.id));renderMediaCards();
  if((state.mediaRecords||[]).filter(item=>!item.usage_count).length>20)message('一次最多可以批量选择 20 张图片。')
 });
 $('#cms-media-bulk-delete').addEventListener('click',bulkDeleteMedia);
 $('#cms-media-grid').addEventListener('change',event=>{
  const input=event.target.closest('[data-media-check]');if(!input)return;
  if(input.checked){
   if(mediaWorkbench.selected.size>=20){input.checked=false;message('每次最多选择 20 张图片。',false);return}
   mediaWorkbench.selected.add(input.dataset.mediaCheck)
  }else mediaWorkbench.selected.delete(input.dataset.mediaCheck);
  updateMediaBulkSelection();
 });
 $('#cms-media-grid').addEventListener('click',async event=>{
  const refs=event.target.closest('[data-v558-open-refs]');
  if(refs){
   const card=refs.closest('[data-media-id]'),details=card?.querySelector('.cms-v532-details');
   const target=details?.querySelector('.cms-v532-references');
   if(details&&target){details.open=true;target.focus({preventScroll:true});target.scrollIntoView({block:'nearest'})}
   return;
  }
  const editAlt=event.target.closest('[data-v557-edit-alt]');
  if(editAlt){
   if(!can('media'))return;
   const card=editAlt.closest('[data-media-id]'),details=card?.querySelector('.cms-v532-details');
   if(details){details.open=true;details.querySelector('[data-media-alt]')?.focus()}
   return;
  }
  const save=event.target.closest('[data-media-meta-save]');if(save){await saveMediaSeo(save);return}
 });
 $('#cms-v557-show-missing').addEventListener('click',()=>{
  if(!can('media')||state.mediaField||state.mediaTarget)return;
  mediaWorkbench.seo=mediaWorkbench.seo==='missing'?'all':'missing';
  $('#cms-media-seo').value=mediaWorkbench.seo;
  resetMediaFilters();refreshMedia();
 });
 $('#cms-v558-bulk-alt-open').addEventListener('click',openBulkAltEditor);
 $('#cms-v558-alt-cancel').addEventListener('click',hideBulkAltEditor);
 $('#cms-v558-alt-save').addEventListener('click',saveBulkAlt);
 $('#cms-v558-bulk-alt-inputs').addEventListener('input',updateBulkAltProgress);
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
 $('#cms-bulk-action').addEventListener('change',()=>{
   state.selectedSlugs.clear();drawItems();
   message('已切换批量操作，请重新选择符合条件的内容。');
 });
 $('#cms-bulk-clear').addEventListener('click',()=>{
   state.selectedSlugs.clear();drawItems();message('已清空批量选择。');
 });
 $('#cms-select-all').addEventListener('change',e=>{
   const eligible=listPage(listFiltered()).filter(item=>bulkEligibility(item).ok);
   if(e.target.checked){
     state.selectedSlugs=new Set(eligible.slice(0,20).map(item=>item.slug));
     if(eligible.length>20)message('符合条件的内容有 '+eligible.length+' 条，已选择前 20 条。请分批处理。');
   }else{
     for(const item of eligible)state.selectedSlugs.delete(item.slug);
   }
   drawItems();
 });
 $('#cms-create-form').addEventListener('submit',createNew);
 $('#cms-menu').addEventListener('click',()=>{const open=!document.body.classList.contains('sidebar-open');document.body.classList.toggle('sidebar-open',open);$('#cms-backdrop').hidden=!open;$('#cms-menu').setAttribute('aria-expanded',String(open))});
 $('#cms-backdrop').addEventListener('click',closeMobile);
 document.addEventListener('keydown',e=>{onEditorTabKeyDown(e);if(e.key==='Escape')closeMobile()});
 window.addEventListener('beforeunload',e=>{if(state.dirty&&mode==='admin'){e.preventDefault();e.returnValue=''}});
 // A cancelled browser Back/Forward must not leave URL and editor out of sync.
 window.addEventListener('popstate',async()=>{
   const previous=editorUrl(state.selected?.slug||null);
   const route=new URLSearchParams(location.search),kind=route.get('kind')||'site',slug=route.get('edit');
   if(state.busy){message('草稿正在保存，请完成后再导航。',false);history.pushState({},'',previous);return}
   if(state.dirty){
     if(!confirm('当前修改还未保存。确定放弃这些更改吗？')){history.pushState({},'',previous);return}
     clearRecovery();clearTimeout(autosaveTimer);editGeneration++;state.dirty=false;autosavePaused=false;
   }
   if(kind!==state.kind&&!await changeKind(kind,false)){history.pushState({},'',previous);return}
   if(slug&&state.items.some(x=>x.slug===slug)){
     if(!await selectItem(slug))history.replaceState({},'',editorUrl(state.selected?.slug||null));
     return;
   }
   if(state.selected)closeEditor(false);
   if(slug)history.replaceState({},'',editorUrl(null));
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
     if(routeParams.get('workspace')==='media'&&can('media')){markWorkspace('media');await openMedia()}
     if(routeParams.get('workspace')==='review'&&can('view'))await openReviewQueue();
     if(routeParams.get('workspace')==='settings'&&can('view'))await openSettingsHub();
   }catch(e){
     console.error('[CMS] initial content load failed',e);
     setNotice('无法读取后台内容：'+e.message,true);
     renderListFailure(e);
   }
 })();
}
boot();
})();