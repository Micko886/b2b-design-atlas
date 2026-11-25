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
const state={kind:new URLSearchParams(location.search).get('kind')||'site',items:[],records:{},selected:null,csrf:'',user:null,dirty:false,q:'',status:'',busy:false,selectedSlugs:new Set(),taxonomy:{},tagSuggestions:[],mediaTarget:null,categoryRecords:[],categoryEditing:null,tagRecords:[],tagEditing:null,tagSearch:'',role:null,capabilities:[],scheduleItems:[],teamPeople:[],teamSelected:null};
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
const statusText={source:'文件已发布',draft:'草稿',review:'待审核',published:'后台已发布',archived:'已归档',public:'公开内容'};
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
 const status=$('.cms-editor-meta .cms-item-state');
 if(status){status.dataset.status='draft';status.textContent=statusText.draft}
 const submit=$('#cms-edit-form [data-transition="submit"]');
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
function setCmsRole(){
 const title={owner:'最高管理员',editor:'内容编辑',reviewer:'审核员'}[state.role]||'未授权';
 $('#cms-role').textContent=(state.user?.display_name||'Atlas')+' · '+title;
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
function rowImage(x){
 if(x.kind==='site')return '/screenshots/sites/'+x.slug+'.webp';
 if(x.kind==='module')return '/screenshots/modules/'+x.slug+'.webp';
 return '';
}
function drawItems(){
 const items=listFiltered(),root=$('#cms-items');
 root.innerHTML=items.length?items.map(item=>{
   const img=rowImage(item);
   return '<div class="cms-v51-row">'+(mode==='admin'?'<label class="cms-v51-select" aria-label="选择 '+h(item.label)+'"><input type="checkbox" data-bulk-select="'+h(item.slug)+'" '+(state.selectedSlugs.has(item.slug)?'checked':'')+'></label>':'')+'<button type="button" class="cms-item '+(state.selected?.slug===item.slug?'active':'')+'" data-pick="'+h(item.slug)+'" aria-label="查看 '+h(item.label)+'">'
   +'<span class="cms-item-thumb">'+(img?'<img src="'+h(img)+'" loading="lazy" alt="">':icon(kinds[state.kind].icon))+'</span>'
   +'<span class="cms-item-copy"><strong>'+h(item.label)+'</strong><small>'+h(item.sector||item.slug)+'</small></span>'
   +stateClasses(item.status)+'</button></div>';
 }).join(''):'<div class="cms-loading">没有符合条件的内容。可清除筛选或创建新内容。</div>';
 $('#cms-count').textContent=items.length+' ITEMS';
 $('#cms-browser-footer').textContent=items.length+' / '+state.items.length+' 条记录';updateBulkToolbar();
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
 const [name,label,type,required]=spec,value=values[name]??(type==='json'?[]:type==='bool'?false:'');
 const inputName='field-'+name,disabled=editable?'':' disabled';
 const attr='id="'+inputName+'" data-field="'+h(name)+'" data-type="'+h(type)+'"';
 let input='';
 if(name==='category'&&state.kind==='article'){
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
 }else if(type==='long')input='<textarea '+attr+disabled+' rows="4"'+(required?' required':'')+'>'+h(value)+'</textarea>';
 else input='<input '+attr+(name==='category'&&state.kind==='article'?' list="v51-categories"':'')+disabled+' type="'+(type==='url'?'url':type==='number'?'number':'text')+'" value="'+h(value)+'"'+(required?' required':'')+'>';
 return '<div class="cms-field" data-json="'+(type==='json')+'" data-multiline="'+(type==='long')+'"><label for="'+inputName+'">'+h(label)+(required?' *':'')+'</label>'+input+'</div>';
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
 +'<p class="cms-review-helper">退回操作会记录审核原因，已发布内容仍保持公开版本。</p></div>';
}
function renderForm(item){
 const isPreview=mode==='preview',values=item.payload||{},editable=can('edit');
 const specs=fieldSpecs[item.kind];
 const content='<div class="cms-editor-title"><div><div class="section-eyebrow">EDIT / '+kinds[item.kind].label.toUpperCase()+'</div><h2>'+h(values.name||values.title||item.slug)+'</h2><p>URL 标识：'+h(item.slug)+' · '+h(item.source==='cms'?'CMS 内容记录':'原始内容资料')+'</p></div>'
  +'<a target="_blank" rel="noopener" href="'+h(kinds[item.kind].url+item.slug)+'">'+icon('arrow-up-right')+' 查看前台</a></div>';
 const s=item.status;
 const statuses=['draft','review','published'];
 const index=s==='source'||s==='public'?-1:statuses.indexOf(s);
 const steps='<div class="cms-steps">'+['内容准备','保存草稿','提交审核','正式发布'].map((title,i)=>'<span class="cms-step '+(i===index+1?'current':i<index+1?'passed':'')+'"><span>'+String(i+1).padStart(2,'0')+'</span>'+title+'</span>'+(i<3?'<span class="cms-step-line"></span>':'')).join('')+'</div>';
 const meta='<div class="cms-editor-meta">'+stateClasses(s)+'<span>修订版本 <strong>v'+item.revision+'</strong></span><span>内容来源：'+h(item.source==='cms'?'PostgreSQL CMS':'项目内容文件')+'</span>'+(item.published_at?'<span>发布时间：'+h(item.published_at.slice(0,16))+'</span>':'')+'</div>';
 const form='<div class="cms-editor-content">'+(isPreview?'<div class="cms-readonly-banner">当前是公开设计预览。字段来自公开目录，无法在这里保存或发布。正式操作请使用管理员账户。</div>':'')+
 '<form id="cms-edit-form" class="cms-form"><div class="cms-form-group-label"><span>基础资料与内容字段</span><small>自动保存开启 · 发布仍需审核</small></div>'
 +(editable?'<div class="cms-autosave-strip"><span class="cms-autosave-led"></span><span id="cms-autosave-status" role="status" aria-live="polite">已加载 · 修改后 3 秒自动保存草稿</span><button type="button" data-autosave-retry>立即保存</button></div>':'')
 +specs.filter(spec=>!(item.kind==='article'&&['tags','takeaways','sections'].includes(spec[0]))).map(spec=>formField(spec,values,editable)).join('')
 +(item.kind==='article'?articleStudio(values,editable):'')
 +'<details class="cms-json-advanced"><summary>高级 · 查看完整 JSON 结构</summary><div class="cms-field" data-json="true"><label>只读数据结构</label><textarea disabled spellcheck="false">'+h(JSON.stringify(values,null,2))+'</textarea></div></details>'
 +(editable?'<div class="cms-form-actions">'
  +'<button class="primary" type="submit">'+icon('save')+' 保存草稿</button>'
  +'<button type="button" data-transition="submit" '+(s!=='draft'?'disabled':'')+'>'+icon('check')+' 提交审核</button>'
  +'<span class="cms-inline-hint">提交审核后才允许审核员发布</span></div>':'')
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
 root.innerHTML=content+steps+meta+reviewBrief(item)+form+reviewActions+timeline;root.hidden=false;
 syncScheduleEditor(item);
 $('#cms-empty').hidden=true;
 state.dirty=false;autosavePaused=false;
}
async function selectItem(slug){
 if(state.dirty&&!confirm('当前修改还未保存。确定放弃这些更改吗？'))return;
 clearTimeout(autosaveTimer);editGeneration++;
 const item=state.items.find(x=>x.slug===slug);if(!item)return;
 $('#cms-editor-body').hidden=true;$('#cms-empty').hidden=false;$('#cms-empty').innerHTML='<div class="cms-loading">正在读取 '+h(item.label)+'…</div>';
 try{
   const result=mode==='admin'?await api('/api/admin/content/'+state.kind+'/'+slug):
    {kind:state.kind,slug,source:'repository',status:'public',revision:0,payload:state.records[slug],history:[]};
   state.selected=result;
   renderForm(result);drawItems();await offerDraftRecovery(result);
 }catch(e){$('#cms-empty').innerHTML='<div class="cms-error">'+h(e.message)+'</div>';message(e.message,false)}
}
function takeFields(){
 const base=JSON.parse(JSON.stringify(state.selected.payload)),controls=$$('#cms-edit-form [data-field]');
 for(const el of controls){
   const name=el.dataset.field,type=el.dataset.type,value=el.value;
   if(type==='json'){
     try{base[name]=JSON.parse(value)}catch{throw Error('「'+name+'」需要填写有效 JSON。')}
   }else if(type==='bool')base[name]=value==='true';
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
   history.replaceState({},'',listUrl());await loadKind();await selectItem(slug);message('新建草稿成功。请完善内容，再提交审核。');
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
async function changeKind(kind){
 if(!kinds[kind])return;
 if(state.busy){message('草稿正在保存，请完成后切换内容类型。',false);return}
 if(state.dirty&&!confirm('当前修改尚未保存，确定切换？'))return;
 state.kind=kind;state.selected=null;state.dirty=false;state.records={};state.q='';state.status='';state.selectedSlugs.clear();
 $('#cms-search').value='';$('#cms-status').value='';
 $('#cms-empty').hidden=false;$('#cms-editor-body').hidden=true;
 $('#cms-empty').innerHTML='<div class="cms-empty-symbol">✳</div><span class="section-eyebrow">EDITORIAL WORKSPACE</span><h2>选择一个案例，开始研究。</h2><p>选择左侧内容后，可以在这里编辑、审阅和发布。</p>';
 history.pushState({},'',listUrl());
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
 if(mode!=='admin')return;
 $('#cms-media-dialog').showModal();
 await refreshMedia();
}
async function refreshMedia(){
 try{
   const res=await api('/api/admin/media');
   $('#cms-media-grid').innerHTML=res.items.length?res.items.map(item=>'<div class="cms-v51-media-item">'
     +'<img src="'+h(item.url)+'" alt="'+h(item.file_name)+'" loading="lazy">'
     +'<strong title="'+h(item.file_name)+'">'+h(item.file_name)+'</strong>'
     +'<small>'+(item.byte_size/1024).toFixed(0)+' KB · '+h(item.created_at.slice(0,10))+'</small>'
     +'<button type="button" data-v51-copy-media="'+h(item.url)+'">复制图片地址</button>'
     +(state.mediaTarget?'<button type="button" data-v513-use-inline="'+h(item.url)+'">插入当前章节</button>':state.selected?.kind==='article'?'<button type="button" data-v51-use-media="'+h(item.url)+'">设为当前文章封面</button>':'')
     +'<button type="button" data-v51-delete-media="'+h(item.id)+'" class="cms-v51-delete">删除图片</button></div>').join('')
     :'<p class="cms-loading">暂无上传图片。可以上传 JPG、PNG 或 WebP。</p>';
 }catch(e){message(e.message,false)}
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
 if(mode!=='admin')return;
 for(const original of [...files].slice(0,10)){
   try{
     $('#cms-media-status').textContent='正在处理 '+original.name;
     const file=await optimizeMediaFile(original);
     $('#cms-media-status').textContent='正在上传 '+file.name+'（'+Math.round(file.size/1024)+' KB）';
     const base64=await new Promise((resolve,reject)=>{
       const reader=new FileReader();reader.onerror=()=>reject(Error('文件读取失败'));
       reader.onload=()=>resolve(String(reader.result).split(',')[1]);reader.readAsDataURL(file);
     });
     await api('/api/admin/media',{method:'POST',body:JSON.stringify({name:file.name,mime:file.type,content:base64})});
     message((file!==original?'已优化并上传：':'媒体已保存：')+file.name);
   }catch(err){message(err.message,false)}
 }
 $('#cms-media-status').textContent='媒体安全保存在 PostgreSQL';
 await refreshMedia();
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
 $('#cms-v515-category-items [data-v515-pick]').forEach(button=>{
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
 $('#cms-tag-items [data-v513-tag]').forEach(button=>{
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
 $('[data-cal-view]').forEach(btn=>btn.setAttribute('aria-pressed',String(btn.dataset.calView===calendarView)));
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
 $('#cms-new').hidden=mode!=='admin';$('#cms-export').hidden=mode!=='admin';$('#cms-media-open').hidden=mode!=='admin';$('#cms-categories-open').hidden=mode!=='admin';$('#cms-tags-open').hidden=mode!=='admin';$('#cms-review-shortcut').hidden=mode!=='admin';$('#cms-schedules-open').hidden=mode!=='admin';$('#cms-team-open').hidden=mode!=='admin';
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
   const themeButton=e.target.closest('[data-set-theme]');if(themeButton){setTheme(themeButton.dataset.setTheme);return}
   const type=e.target.closest('[data-kind-link]');if(type){e.preventDefault();await changeKind(type.dataset.kindLink);return}
   const choice=e.target.closest('[data-pick]');if(choice){if(state.busy)return;await selectItem(choice.dataset.pick);return}
   const action=e.target.closest('[data-transition]');if(action){await transition(action.dataset.transition);return}
   const restore=e.target.closest('[data-restore]');if(restore){await restoreRevision(Number(restore.dataset.restore));return}
   const bulkCheck=e.target.closest('[data-bulk-select]');if(bulkCheck){const slug=bulkCheck.dataset.bulkSelect;if(bulkCheck.checked)state.selectedSlugs.add(slug);else state.selectedSlugs.delete(slug);updateBulkToolbar();return}
   const tagPick=e.target.closest('[data-v513-tag]');if(tagPick){chooseTag(tagPick.dataset.v513Tag);return}
   if(e.target.closest('[data-v513-close-tags]')){$('#cms-tags-dialog').close();return}
   const picked=e.target.closest('[data-v515-pick]');if(picked){chooseCategory(picked.dataset.v515Pick);return}
   if(e.target.closest('[data-v515-close]')){$('#cms-categories-dialog').close();return}
   if(e.target.closest('[data-autosave-retry]')){if(autosavePaused){message('已暂停覆盖：请备份当前内容并刷新记录。',false);return}await persistDraft(false);return}
   const tag=e.target.closest('[data-v512-tag]');if(tag){const field=$('#v51-tags');if(!field)return;const existing=linesFrom('#v51-tags');if(!existing.includes(tag.dataset.v512Tag)){field.value=[...existing,tag.dataset.v512Tag].join(String.fromCharCode(10));markDraftDirty();refreshArticlePreview()}return}
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
   if(blockPick){state.mediaTarget=blockPick.closest('[data-cms-block]');await openMedia();return}
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
   const deleteMedia=e.target.closest('[data-v51-delete-media]');
   if(deleteMedia){
     if(!confirm('确定删除这张媒体图片？仍被草稿或文章引用的图片会受到保护。'))return;
     try{await api('/api/admin/media/'+deleteMedia.dataset.v51DeleteMedia,{method:'DELETE'});await refreshMedia();message('图片已删除')}
     catch(err){message(err.message,false)}
     return;
   }
   const pickInline=e.target.closest('[data-v513-pick-image]');
   if(pickInline){state.mediaTarget=pickInline.closest('[data-v51-section]');await openMedia();return}
   const clearInline=e.target.closest('[data-v513-clear-image]');
   if(clearInline){clearInline.closest('[data-v51-section]').querySelector('[data-v513-image]').value='';markDraftDirty();refreshArticlePreview();return}
   const useMedia=e.target.closest('[data-v51-use-media]');if(useMedia){const target=$('#field-cover_image');if(target){target.value=useMedia.dataset.v51UseMedia;markDraftDirty();$('#cms-media-dialog').close();message('封面已选择，请保存草稿')}return}
   const copy=e.target.closest('[data-v51-copy-media]');if(copy){try{await navigator.clipboard.writeText(location.origin+copy.dataset.v51CopyMedia);message('图片地址已复制')}catch{message('请从媒体列表中手动复制地址',false)}return}
   if(e.target.closest('[data-media-close]')){state.mediaTarget=null;$('#cms-media-dialog').close();return}
   if(e.target.closest('[data-dialog-close]')){$('#cms-create-dialog').close();return}
 });
 document.addEventListener('input',e=>{if(e.target.closest('#cms-edit-form')){markDraftDirty();refreshArticlePreview()}});
 $('#cms-search').addEventListener('input',e=>{state.q=e.target.value;drawItems()});
 $('#cms-status').addEventListener('change',e=>{state.status=e.target.value;drawItems()});
 $('#cms-refresh').addEventListener('click',async()=>{
  if(state.dirty&&!confirm('当前草稿还有未保存的修改。确认重新读取服务器内容吗？'))return;
  try{await loadKind(true);message('内容列表已刷新')}catch(e){message(e.message,false)}
 });
 $('#cms-export').addEventListener('click',exportCms);
 $('#cms-new').addEventListener('click',async()=>{
   if(mode==='admin'&&state.kind==='article')try{await loadCmsTaxonomy()}catch(err){message(err.message,false)}
   updateCreateFields();$('#cms-create-dialog').showModal()
 });
 $('#cms-create-kind').addEventListener('change',updateCreateFields);
 $('#cms-tags-open').addEventListener('click',openTagManager);
 $('#cms-tag-add').addEventListener('click',()=>chooseTag());
 $('#cms-tag-form').addEventListener('submit',saveTag);
 $('#cms-tag-delete').addEventListener('click',deleteTag);
 $('#cms-tag-search').addEventListener('input',e=>{state.tagSearch=e.target.value;drawTags()});
 $('#cms-review-shortcut').addEventListener('click',()=>{$('#cms-status').value='review';state.status='review';drawItems();$('#cms-items').scrollIntoView({block:'nearest',behavior:'smooth'});message('已筛选当前内容类型的待审核记录')});
 $('#cms-schedules-open').addEventListener('click',openScheduleQueue);
 $('#cms-schedule-refresh').addEventListener('click',refreshSchedules);
 $('#cms-calendar-status').addEventListener('change',()=>{paintCalendar();paintScheduleQueue()});
 $('#cms-calendar-today').addEventListener('click',()=>{calendarCursor=new Date();paintCalendar()});
 $('[data-cal-view]').forEach(button=>button.addEventListener('click',()=>{
   calendarView=button.dataset.calView;paintCalendar()
 }));
 $('[data-cal-shift]').forEach(button=>button.addEventListener('click',()=>shiftCalendar(Number(button.dataset.calShift))));
 installCalendarDrag();
 $('#cms-team-open').addEventListener('click',openTeam);
 $('#cms-team-search').addEventListener('input',paintTeam);
 $('#cms-team-form').addEventListener('submit',grantTeamRole);
 $('#cms-team-revoke').addEventListener('click',revokeTeamRole);
 $('#cms-categories-open').addEventListener('click',openCategoryManager);
 $('#cms-v515-add').addEventListener('click',()=>chooseCategory());
 $('#cms-v515-form').addEventListener('submit',saveCategory);
 $('#cms-v515-delete').addEventListener('click',deleteCategory);
 $('#cms-media-open').addEventListener('click',()=>{state.mediaTarget=null;openMedia()});
 $('#cms-media-file').addEventListener('change',e=>{uploadMedia(e.target.files);e.target.value=''});
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
 window.addEventListener('popstate',()=>{const kind=new URLSearchParams(location.search).get('kind')||'site';changeKind(kind)});
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
     await loadKind();
   }catch(e){setNotice('无法读取后台内容：'+e.message);$('#cms-items').innerHTML='<div class="cms-error">'+h(e.message)+'</div>'}
 })();
}
boot();
})();