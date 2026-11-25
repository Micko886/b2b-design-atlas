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
const state={kind:new URLSearchParams(location.search).get('kind')||'site',items:[],records:{},selected:null,csrf:'',user:null,dirty:false,q:'',status:'',busy:false,selectedSlugs:new Set(),taxonomy:{},tagSuggestions:[],mediaTarget:null};
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
  ['author','作者','text',true],['cover_site','封面关联网站 ID','text'],['cover_image','媒体封面 URL','text'],['published_at','发布日期（YYYY-MM-DD）','text'],
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
 if(!r.ok)throw Error(typeof v.detail==='string'?v.detail:r.status===403?'管理员权限不足':r.status===401?'请先登录':'内容接口错误 HTTP '+r.status);
 return v;
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
 if(type==='bool')input='<select '+attr+disabled+'><option value="false"'+(!value?' selected':'')+'>否</option><option value="true"'+(value?' selected':'')+'>是</option></select>';
 else if(type==='json'){
   const pretty=typeof value==='string'?value:JSON.stringify(value,null,2);
   input='<textarea '+attr+disabled+' rows="7" spellcheck="false">'+h(pretty)+'</textarea>';
 }else if(type==='long')input='<textarea '+attr+disabled+' rows="4"'+(required?' required':'')+'>'+h(value)+'</textarea>';
 else input='<input '+attr+(name==='category'&&state.kind==='article'?' list="v51-categories"':'')+disabled+' type="'+(type==='url'?'url':type==='number'?'number':'text')+'" value="'+h(value)+'"'+(required?' required':'')+'>';
 return '<div class="cms-field" data-json="'+(type==='json')+'" data-multiline="'+(type==='long')+'"><label for="'+inputName+'">'+h(label)+(required?' *':'')+'</label>'+input+'</div>';
}
function renderForm(item){
 const isPreview=mode==='preview',values=item.payload||{},editable=!isPreview;
 const specs=fieldSpecs[item.kind];
 const content='<div class="cms-editor-title"><div><div class="section-eyebrow">EDIT / '+kinds[item.kind].label.toUpperCase()+'</div><h2>'+h(values.name||values.title||item.slug)+'</h2><p>URL 标识：'+h(item.slug)+' · '+h(item.source==='cms'?'CMS 内容记录':'原始内容资料')+'</p></div>'
  +'<a target="_blank" rel="noopener" href="'+h(kinds[item.kind].url+item.slug)+'">'+icon('arrow-up-right')+' 查看前台</a></div>';
 const s=item.status;
 const statuses=['draft','review','published'];
 const index=s==='source'||s==='public'?-1:statuses.indexOf(s);
 const steps='<div class="cms-steps">'+['内容准备','保存草稿','提交审核','正式发布'].map((title,i)=>'<span class="cms-step '+(i===index+1?'current':i<index+1?'passed':'')+'"><span>'+String(i+1).padStart(2,'0')+'</span>'+title+'</span>'+(i<3?'<span class="cms-step-line"></span>':'')).join('')+'</div>';
 const meta='<div class="cms-editor-meta">'+stateClasses(s)+'<span>修订版本 <strong>v'+item.revision+'</strong></span><span>内容来源：'+h(item.source==='cms'?'PostgreSQL CMS':'项目内容文件')+'</span>'+(item.published_at?'<span>发布时间：'+h(item.published_at.slice(0,16))+'</span>':'')+'</div>';
 const form='<div class="cms-editor-content">'+(isPreview?'<div class="cms-readonly-banner">当前是公开设计预览。字段来自公开目录，无法在这里保存或发布。正式操作请使用管理员账户。</div>':'')+
 '<form id="cms-edit-form" class="cms-form"><div class="cms-form-group-label"><span>基础资料与内容字段</span><small>修改后先保存草稿</small></div>'
 +specs.filter(spec=>!(item.kind==='article'&&['tags','takeaways','sections'].includes(spec[0]))).map(spec=>formField(spec,values,editable)).join('')
 +(item.kind==='article'?articleStudio(values,editable):'')
 +'<details class="cms-json-advanced"><summary>高级 · 查看完整 JSON 结构</summary><div class="cms-field" data-json="true"><label>只读数据结构</label><textarea disabled spellcheck="false">'+h(JSON.stringify(values,null,2))+'</textarea></div></details>'
 +(editable?'<div class="cms-form-actions">'
  +'<button class="primary" type="submit">'+icon('save')+' 保存草稿</button>'
  +'<button type="button" data-transition="submit" '+(s!=='draft'?'disabled':'')+'>'+icon('check')+' 提交审核</button>'
  +'<button class="primary" type="button" data-transition="publish" '+(s!=='review'?'disabled':'')+'>'+icon('arrow-up-right')+' 审核并发布</button>'
  +'<button class="warn" type="button" data-transition="archive" '+(s!=='published'?'disabled':'')+'>归档下线</button>'
  +'<span class="cms-inline-hint">草稿不会覆盖已发布版本</span></div>':'')
 +'</form></div>';
 const history=item.history||[];
 const timeline=isPreview?'':('<div class="cms-timeline"><h3>版本与操作记录</h3>'+
 (history.length?history.slice(0,15).map(v=>'<div class="cms-timeline-row"><span class="cms-timeline-dot"></span><div class="cms-timeline-content"><b>v'+v.revision+' · '+h({create:'创建草稿',save:'保存草稿',submit:'提交审核',publish:'正式发布',archive:'归档下线',restore:'恢复旧稿'}[v.action]||v.action)+'</b><span>'+h(v.created_at?.replace('T',' ').slice(0,19)||'')+'</span></div><button type="button" data-restore="'+v.revision+'">恢复草稿</button></div>').join(''):'<p style="color:var(--muted);font-size:11px">原始内容尚无 CMS 修改记录。首次保存后开始记录版本。</p>')
 +'</div>');
 const root=$('#cms-editor-body');
 root.innerHTML=content+steps+meta+form+timeline;root.hidden=false;
 $('#cms-empty').hidden=true;
 state.dirty=false;
}
async function selectItem(slug){
 if(state.dirty&&!confirm('当前修改还未保存。确定放弃这些更改吗？'))return;
 const item=state.items.find(x=>x.slug===slug);if(!item)return;
 $('#cms-editor-body').hidden=true;$('#cms-empty').hidden=false;$('#cms-empty').innerHTML='<div class="cms-loading">正在读取 '+h(item.label)+'…</div>';
 try{
   const result=mode==='admin'?await api('/api/admin/content/'+state.kind+'/'+slug):
    {kind:state.kind,slug,source:'repository',status:'public',revision:0,payload:state.records[slug],history:[]};
   state.selected=result;
   renderForm(result);drawItems();
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
   base.sections=Array.from(document.querySelectorAll('[data-v51-section]')).map(block=>({
     title:block.querySelector('[data-v51-title]').value.trim(),
     paragraphs:block.querySelector('[data-v51-paragraphs]').value.split(new RegExp(String.fromCharCode(10)+'\\s*'+String.fromCharCode(10))).map(x=>x.trim()).filter(Boolean),
     bullets:block.querySelector('[data-v51-bullets]').value.split(String.fromCharCode(10)).map(x=>x.trim()).filter(Boolean),
     callout:block.querySelector('[data-v51-callout]').value.trim(),
     image:block.querySelector('[data-v513-image]').value.trim(),
     image_caption:block.querySelector('[data-v513-caption]').value.trim()
   }));
   if(!base.sections.length)throw Error('请至少保留一个文章章节。');
 }
 return base;
}
async function saveDraft(event){
 event.preventDefault();if(mode!=='admin'||state.busy)return;
 const target=state.selected;if(!target)return;
 let payload;try{payload=takeFields()}catch(e){message(e.message,false);return}
 btnDisable(true);
 try{
   const res=await api('/api/admin/content/'+target.kind+'/'+target.slug,{method:'PUT',
      body:JSON.stringify({payload,expected_revision:target.revision})});
   message('草稿已保存 · v'+res.revision);
   state.dirty=false;await loadKind(false);await selectItem(target.slug);
 }catch(e){message(e.message,false)}
 finally{btnDisable(false)}
}
async function transition(action){
 if(mode!=='admin'||state.busy||!state.selected)return;
 if(state.dirty){message('请先保存当前修改的草稿，再继续审核。',false);return}
 const item=state.selected;
 if(action==='archive'&&!confirm('确定归档「'+(item.payload.name||item.payload.title||item.slug)+'」？该页面将从前台列表移除。'))return;
 btnDisable(true);
 try{
   const result=await api('/api/admin/content/'+item.kind+'/'+item.slug+'/'+action,{
    method:'POST',body:JSON.stringify({expected_revision:item.revision})});
   message({submit:'已提交审核',publish:'内容已发布到前台',archive:'已归档下线'}[action]||'操作完成');
   state.dirty=false;await loadKind(false);await selectItem(item.slug);
 }catch(e){message(e.message,false)}
 finally{btnDisable(false)}
}
async function restoreRevision(revision){
 if(mode!=='admin'||!state.selected)return;
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
 return {...v,title:fields.name,subtitle:fields.summary,category:fields.sector,author:fields.author||'B2B Atlas 编辑部',sections:[{title:'正文',paragraphs:[],bullets:[],callout:''}],tags:[],takeaways:[],featured:false,reading_minutes:3};
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
 target.innerHTML=f.map(([id,label,required])=>'<label>'+h(label)+'<input name="'+id+'" '+(id==='url'?'type="url"':'type="text"')+' required maxlength="1800" placeholder="'+h(label)+'"></label>').join('');
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
function articleSection(section={},index=0,editable=true){
 const disabled=editable?'':' disabled';
 return '<div class="cms-v51-section" data-v51-section><div class="cms-v51-section-top"><strong>章节 '+(index+1)+'</strong>'
 +(editable?'<div><button type="button" data-v51-move="-1" aria-label="上移章节">↑</button><button type="button" data-v51-move="1" aria-label="下移章节">↓</button><button type="button" data-v51-remove aria-label="删除章节">删除</button></div>':'')+'</div>'
 +'<label>章节标题<input data-v51-title maxlength="180" required'+disabled+' value="'+h(section.title||'')+'" placeholder="为这一节写一个明确的标题"></label>'
 +'<label>正文段落 <small>空行分段 · 选中文字后使用工具栏排版</small></label>'
 +(editable?'<div class="cms-v514-toolbar" role="toolbar" aria-label="正文格式工具"><button type="button" data-v514-format="bold" title="加粗选中文字">B 加粗</button><button type="button" data-v514-format="italic" title="斜体选中文字"><i>I</i> 斜体</button><button type="button" data-v514-format="code" title="代码样式">代码</button></div>':'')
 +'<textarea data-v51-paragraphs rows="7"'+disabled+' placeholder="直接输入正文，空行分隔段落">'+h((section.paragraphs||[]).join('\n\n'))+'</textarea>'
 +'<label>要点列表 <small>每行一个要点</small><textarea data-v51-bullets rows="3"'+disabled+' placeholder="要点 1\n要点 2">'+h((section.bullets||[]).join('\n'))+'</textarea></label>'
 +'<label>重点提示<textarea data-v51-callout rows="2"'+disabled+' placeholder="可选的重点结论">'+h(section.callout||'')+'</textarea></label>'
 +'<div class="cms-v513-image-row"><label>章节配图<input data-v513-image value="'+h(section.image||'')+'" readonly placeholder="尚未选择图片"></label>'
 +(editable?'<button type="button" data-v513-pick-image>选择图片</button><button type="button" data-v513-clear-image>移除配图</button>':'')+'</div>'
 +'<label>配图说明<input data-v513-caption value="'+h(section.image_caption||'')+'" maxlength="240"'+disabled+' placeholder="填写图片来源或说明"></label>'
 +'</div>';
}
function articleStudio(v,editable){
 const disabled=editable?'':' disabled';
 const categorySuggestions=(state.taxonomy.article||[]).map(x=>'<option value="'+h(x)+'"></option>').join('');
 return '<section class="cms-v51-studio"><div class="cms-v51-studio-head"><div><span class="section-eyebrow">VISUAL EDITOR · V51</span><h3>结构化文章编辑器</h3><p>可视化编辑正文、标签和观点，保存后仍进入原有审核流程。</p></div><span class="cms-v51-studio-badge">所见即结构</span></div>'
 +'<div class="cms-v51-taxonomy"><label>文章标签 <small>每行一个关键词</small><textarea id="v51-tags" rows="3"'+disabled+'>'+h((v.tags||[]).join('\n'))+'</textarea></label>'
 +'<label>核心观点 <small>每行一条摘要</small><textarea id="v51-takeaways" rows="3"'+disabled+'>'+h((v.takeaways||[]).join('\n'))+'</textarea></label></div>'
 +'<div class="cms-v512-suggestions"><span>常用标签</span>'+(state.tagSuggestions.length?state.tagSuggestions.slice(0,12).map(tag=>'<button type="button" data-v512-tag="'+h(tag)+'">'+h(tag)+'</button>').join(''):'<small>暂无常用标签</small>')+'</div>'
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
  .replace(/\\*\\*([^*\\n]+)\\*\\*/g,'<strong>$1</strong>')
  .replace(/(^|[^*])\\*([^*\\n]+)\\*/g,'$1<em>$2</em>')
  .replace(/`([^`\\n]+)`/g,'<code>$1</code>');
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
 field.focus();state.dirty=true;refreshArticlePreview();
}
function sectionImageMarkup(s){
 if(!s.image||!/^\/api\/media\/[0-9a-f-]{36}$/.test(s.image))return '';
 return '<figure class="cms-v513-figure"><img src="'+h(s.image)+'" alt="'+h(s.image_caption||s.title||'配图')+'">'
   +(s.image_caption?'<figcaption>'+h(s.image_caption)+'</figcaption>':'')+'</figure>';
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
     +(Array.isArray(s.paragraphs)?s.paragraphs:[]).map(p=>'<p>'+inlineArticleText(p)+'</p>').join('')
     +(Array.isArray(s.bullets)&&s.bullets.length?'<ul>'+s.bullets.map(x=>'<li>'+h(x)+'</li>').join('')+'</ul>':'')
     +sectionImageMarkup(s)
     +(s.callout?'<blockquote>'+h(s.callout)+'</blockquote>':'')+'</section>').join('')
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
 bar.hidden=mode!=='admin';
 $('#cms-selected-count').textContent=state.selectedSlugs.size+' 项已选择';
 const visible=listFiltered().filter(x=>x.status!=='source');
 $('#cms-select-all').checked=visible.length>0&&visible.every(x=>state.selectedSlugs.has(x.slug));
}
async function runBulk(){
 if(mode!=='admin'||state.busy)return;
 const action=$('#cms-bulk-action').value;
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
async function uploadMedia(files){
 if(mode!=='admin')return;
 for(const file of [...files].slice(0,10)){
   if(!['image/jpeg','image/png','image/webp'].includes(file.type)||file.size>1500000){
     message(file.name+'：仅允许 1.5MB 以下的 JPG、PNG 和 WebP 图片',false);continue;
   }
   $('#cms-media-status').textContent='正在上传 '+file.name;
   try{
     const base64=await new Promise((resolve,reject)=>{
       const reader=new FileReader();reader.onerror=()=>reject(Error('文件读取失败'));
       reader.onload=()=>resolve(String(reader.result).split(',')[1]);reader.readAsDataURL(file);
     });
     await api('/api/admin/media',{method:'POST',body:JSON.stringify({name:file.name,mime:file.type,content:base64})});
     message('媒体已保存：'+file.name);
   }catch(e){message(e.message,false)}
 }
 $('#cms-media-status').textContent='媒体资源存储于 PostgreSQL';
 await refreshMedia();
}

function boot(){
 setTheme(theme());
 $('#cms-new').hidden=mode!=='admin';$('#cms-export').hidden=mode!=='admin';$('#cms-media-open').hidden=mode!=='admin';
 $('#cms-login-link').hidden=mode!=='preview';
 $('#cms-role').textContent=mode==='admin'?'管理员 · 内容维护':'公开只读预览';
 setNotice(mode==='admin'?'管理员工作区：编辑先保存草稿，审核通过后才会进入公开目录。':'只读预览：这里展示公开网站资料，不会提供编辑或发布权限。');
 if(mode==='preview')$('#cms-state').innerHTML='<span class="status-led"></span> PUBLIC PREVIEW';
 document.addEventListener('click',async e=>{
   const themeButton=e.target.closest('[data-set-theme]');if(themeButton){setTheme(themeButton.dataset.setTheme);return}
   const type=e.target.closest('[data-kind-link]');if(type){e.preventDefault();await changeKind(type.dataset.kindLink);return}
   const choice=e.target.closest('[data-pick]');if(choice){await selectItem(choice.dataset.pick);return}
   const action=e.target.closest('[data-transition]');if(action){await transition(action.dataset.transition);return}
   const restore=e.target.closest('[data-restore]');if(restore){await restoreRevision(Number(restore.dataset.restore));return}
   const bulkCheck=e.target.closest('[data-bulk-select]');if(bulkCheck){const slug=bulkCheck.dataset.bulkSelect;if(bulkCheck.checked)state.selectedSlugs.add(slug);else state.selectedSlugs.delete(slug);updateBulkToolbar();return}
   const tag=e.target.closest('[data-v512-tag]');if(tag){const field=$('#v51-tags');if(!field)return;const existing=linesFrom('#v51-tags');if(!existing.includes(tag.dataset.v512Tag)){field.value=[...existing,tag.dataset.v512Tag].join(String.fromCharCode(10));state.dirty=true;refreshArticlePreview()}return}
   const formatter=e.target.closest('[data-v514-format]');if(formatter){applyArticleFormat(formatter);return}
   if(e.target.closest('[data-v512-preview]')){toggleArticlePreview();return}
   if(e.target.closest('[data-v51-add]')){const root=$('#cms-v51-sections');root.insertAdjacentHTML('beforeend',articleSection({},root.children.length,true));reindexSections();state.dirty=true;refreshArticlePreview();return}
   if(e.target.closest('[data-v51-remove]')){const blocks=document.querySelectorAll('#cms-v51-sections [data-v51-section]');if(blocks.length<=1){message('至少保留一个章节',false);return}e.target.closest('[data-v51-section]').remove();reindexSections();state.dirty=true;return}
   const move=e.target.closest('[data-v51-move]');if(move){const block=move.closest('[data-v51-section]'),target=Number(move.dataset.v51Move)<0?block.previousElementSibling:block.nextElementSibling;if(target){if(Number(move.dataset.v51Move)<0)target.before(block);else target.after(block);reindexSections();state.dirty=true}return}
   const useInline=e.target.closest('[data-v513-use-inline]');
   if(useInline&&state.mediaTarget){
     state.mediaTarget.querySelector('[data-v513-image]').value=useInline.dataset.v513UseInline;
     state.mediaTarget=null;$('#cms-media-dialog').close();state.dirty=true;refreshArticlePreview();
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
   if(clearInline){clearInline.closest('[data-v51-section]').querySelector('[data-v513-image]').value='';state.dirty=true;refreshArticlePreview();return}
   const useMedia=e.target.closest('[data-v51-use-media]');if(useMedia){const target=$('#field-cover_image');if(target){target.value=useMedia.dataset.v51UseMedia;state.dirty=true;$('#cms-media-dialog').close();message('封面已选择，请保存草稿')}return}
   const copy=e.target.closest('[data-v51-copy-media]');if(copy){try{await navigator.clipboard.writeText(location.origin+copy.dataset.v51CopyMedia);message('图片地址已复制')}catch{message('请从媒体列表中手动复制地址',false)}return}
   if(e.target.closest('[data-media-close]')){state.mediaTarget=null;$('#cms-media-dialog').close();return}
   if(e.target.closest('[data-dialog-close]')){$('#cms-create-dialog').close();return}
 });
 document.addEventListener('input',e=>{if(e.target.closest('#cms-edit-form')){state.dirty=true;refreshArticlePreview()}});
 $('#cms-search').addEventListener('input',e=>{state.q=e.target.value;drawItems()});
 $('#cms-status').addEventListener('change',e=>{state.status=e.target.value;drawItems()});
 $('#cms-refresh').addEventListener('click',async()=>{try{await loadKind(true);message('内容列表已刷新')}catch(e){message(e.message,false)}});
 $('#cms-export').addEventListener('click',exportCms);
 $('#cms-new').addEventListener('click',()=>{updateCreateFields();$('#cms-create-dialog').showModal()});
 $('#cms-create-kind').addEventListener('change',updateCreateFields);
 $('#cms-media-open').addEventListener('click',()=>{state.mediaTarget=null;openMedia()});
 $('#cms-media-file').addEventListener('change',e=>{uploadMedia(e.target.files);e.target.value=''});
 $('#cms-bulk-run').addEventListener('click',runBulk);
 $('#cms-select-all').addEventListener('change',e=>{for(const item of listFiltered()){if(item.status==='source')continue;if(e.target.checked)state.selectedSlugs.add(item.slug);else state.selectedSlugs.delete(item.slug)}drawItems()});

 const dlg=$('#cms-create-dialog');const fields=document.createElement('div');fields.id='cms-create-fields';fields.className='cms-create-fields';
 dlg.querySelector('#cms-create-slug').closest('label').insertAdjacentElement('afterend',fields);
 $('#cms-create-form').addEventListener('submit',createNew);
 $('#cms-menu').addEventListener('click',()=>{const open=!document.body.classList.contains('sidebar-open');document.body.classList.toggle('sidebar-open',open);$('#cms-backdrop').hidden=!open;$('#cms-menu').setAttribute('aria-expanded',String(open))});
 $('#cms-backdrop').addEventListener('click',closeMobile);
 document.addEventListener('keydown',e=>{if(e.key==='Escape')closeMobile()});
 window.addEventListener('popstate',()=>{const kind=new URLSearchParams(location.search).get('kind')||'site';changeKind(kind)});
 document.addEventListener('submit',e=>{if(e.target.id==='cms-edit-form')saveDraft(e)});
 (async()=>{
   try{
     if(mode==='admin'){
       const me=await api('/api/auth/me');
       if(!me.authenticated)throw Error('会话已过期，请登录');
       state.csrf=me.csrf_token;state.user=me.user;try{const result=await api('/api/admin/content/taxonomy');state.taxonomy=result.categories||{};state.tagSuggestions=result.article_tags||[];}catch{}
       $('#cms-role').textContent=(me.user?.display_name||'已授权管理员')+' · 管理员';
     }
     await loadKind();
   }catch(e){setNotice('无法读取后台内容：'+e.message);$('#cms-items').innerHTML='<div class="cms-error">'+h(e.message)+'</div>'}
 })();
}
boot();
})();