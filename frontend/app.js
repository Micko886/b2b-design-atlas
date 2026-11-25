/* B2B Atlas — clean frontend, single entry, no layered legacy JS. */
'use strict';
(function(){
const $=q=>document.querySelector(q), $$=q=>Array.from(document.querySelectorAll(q));
const app=$('#app'), overlay=$('#overlay'), toast=$('#toast');
const state={sites:[],notes:[],modules:[],patterns:[],articles:[],articleCategories:[],articleEditorialNotice:'',profiles:{},palettes:{},q:'',sector:'',category:'',style:'',color:'',sort:'curated',density:'standard',siteType:'',audienceTerm:'',structureTerm:'',styleTag:'',researchOnly:'',saved:[],board:[],notesByKey:{},folders:[],folderItems:{},annotations:{},comparisons:[],legacySaved:read('saved',[]),legacyBoard:read('board',[]),legacyNotes:read('atlas-board-notes',{}),auth:{authenticated:false,user:null,csrf_token:''},authStatus:{available:false,mode:'unconfigured',message:''},pendingFavorite:null,authReady:false,compare:read('atlas-compare',[]),imageIndex:0};
const FILTER_STYLE=['Minimal','Cinematic','Product-led','Technical','Editorial','Photography','3D / Illustration','Motion'];
const FILTER_COLOR=['Black','White','Gray','Red','Orange','Yellow','Green','Blue','Purple','Pink'];
const styleRules={'Minimal':/minimal|restrained|simple|clean/,'Cinematic':/cinematic|immersive|footage|film/,'Product-led':/product|hardware|object|machine/,'Technical':/technical|engineering|specification|data/,'Editorial':/editorial|typography|narrative/,'Photography':/photograph|imagery|real images/,'3D / Illustration':/illustration|render|3d/,'Motion':/motion|animation|video/};
const AUDIENCE_TERMS=[['Engineering · 工程','engineering'],['Procurement · 采购','procurement'],['Manufacturing · 制造','manufacturing'],['Operations · 运营','operations'],['Government · 政府','government'],['Research · 研究','research'],['Commercial · 商业','commercial']];
const STRUCTURE_TERMS=[['Hero / Opening · 首屏', 'hero|opening'],['Product · 产品', 'product'],['Proof · 信任证据', 'proof|trust|customer'],['Use Case · 应用场景', 'use case|application'],['Platform · 平台', 'platform'],['Contact / Inquiry · 转化入口','contact|inquiry|rfq']];
const curated=['vast','figure-robotics','fictiv','skydio','lumafield','helion','saronic','cfs-energy'];
let currentScreens=[], currentScreen=0, toastTimer=0, searchTimer=0, noteTimer=0;
function read(k,v){try{let r=JSON.parse(localStorage.getItem(k));return r===null?v:r}catch{return v}}
function store(k,v){try{localStorage.setItem(k,JSON.stringify(v))}catch{}}
function h(v){return String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
function formatArticleInline(value){
 const escaped=h(value);
 return escaped
  .replace(/\*\*([^*\n]+)\*\*/g,'<strong>$1</strong>')
  .replace(/(^|[^*])\*([^*\n]+)\*/g,'$1<em>$2</em>')
  .replace(/`([^`\n]+)`/g,'<code>$1</code>');
}
function img(v){return h(v||'/screenshots/sites/vast.webp')}
function safeHex(c){return /^#[0-9a-fA-F]{6}$/.test(c||'')?c:'#E0E2E6'}
function site(id){return state.sites.find(x=>x.id===id)}
function moduleBy(id){return state.modules.find(x=>x.id===id)}
function pattern(id){return state.patterns.find(x=>x.id===id)}
function pathSite(s){return '/websites/'+encodeURIComponent(s.id)}
function pathModule(m){return '/sections/'+encodeURIComponent(m.id)}
function pal(x){return state.palettes[x&&x.screenshot_url]||[]}
function entityKind(x){return x.site_id?'module':x.family?'pattern':x.reading_minutes?'article':'site'}
function entityImage(x){
 const kind=entityKind(x);
 if(kind==='article')return articleImage(x);
 if(kind==='pattern')return (x.modules||[]).map(moduleBy).find(Boolean)?.screenshot_url || site('vast')?.screenshot_url;
 return x.screenshot_url;
}
function key(x){return entityKind(x)+':'+x.id}
function byKey(k){const [kind,id]=String(k||'').split(':');return kind==='site'?site(id):kind==='module'?moduleBy(id):kind==='pattern'?pattern(id):kind==='article'?articleBy(id):null}
function cardInfo(x){
 const kind=entityKind(x);
 if(kind==='module')return {name:x.title,sub:(site(x.site_id)?.name||'')+' · '+x.category,url:pathModule(x)};
 if(kind==='pattern')return {name:x.title,sub:'设计模式 · '+x.family,url:'/patterns/'+encodeURIComponent(x.id)};
 if(kind==='article')return {name:x.title,sub:'资讯研究 · '+(articleCat(x.category)?.name||''),url:articleLink(x)};
 return {name:x.name,sub:x.sector,url:pathSite(x)};
}
function saved(k){return state.saved.includes(k)}
function bookmarkIcon(on){return '<svg class="bookmark-svg" viewBox="0 0 24 24" width="17" height="17" aria-hidden="true" fill="'+(on?'currentColor':'none')+'" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"><path d="M6.5 4.5h11v15l-5.5-3.7-5.5 3.7z"/></svg>'}
function inBoard(k){return state.board.includes(k)}
function notify(t){clearTimeout(toastTimer);toast.textContent=t;toast.hidden=false;toastTimer=setTimeout(()=>toast.hidden=true,2300)}
function titleCase(x){return String(x||'').replace(/(^|-)\w/g,s=>s.toUpperCase())}
// Anonymous aggregated operations analytics. No cookies, IP or identity in payload.
let lastAnalyticsPath='',lastAnalyticsAt=0,searchAnalyticsTimer=0;
const sentSearchTerms=new Set();
function analyticsEvent(type,query='',pathOverride=''){
 if(navigator.doNotTrack==='1'||navigator.globalPrivacyControl===true)return;
 fetch('/api/analytics/event',{method:'POST',credentials:'omit',cache:'no-store',
    keepalive:true,headers:{'Content-Type':'application/json'},
    body:JSON.stringify({type,path:pathOverride||location.pathname,query})}).catch(()=>{});
}
// V51.8–V51.12: tab-scoped, short-lived, random first-party session.
const entrySource={
 referrer:(document.referrer||'').slice(0,220),
 utm_source:(new URLSearchParams(location.search).get('utm_source')||'').slice(0,80),
 utm_medium:(new URLSearchParams(location.search).get('utm_medium')||'').slice(0,80),
 utm_campaign:(new URLSearchParams(location.search).get('utm_campaign')||'').slice(0,80)
};
let growthFirst=true,growthFallback=null,scrollPath='',scrollSent=new Set();
function growthAllowed(){return navigator.doNotTrack!=='1'&&navigator.globalPrivacyControl!==true}
function growthSid(){
 if(!growthAllowed()||!globalThis.crypto?.randomUUID)return null;
 const now=Date.now();
 try{
   const existing=JSON.parse(sessionStorage.getItem('atlas-visitor-session')||'null');
   if(existing&&/^[0-9a-f-]{36}$/.test(existing.id)&&now-existing.last<1800000&&now>=existing.last){
     existing.last=now;sessionStorage.setItem('atlas-visitor-session',JSON.stringify(existing));
     return existing.id;
   }
   const fresh={id:crypto.randomUUID(),last:now};
   sessionStorage.setItem('atlas-visitor-session',JSON.stringify(fresh));
   return fresh.id;
 }catch(_){
   if(!growthFallback||now-growthFallback.last>1800000)
     growthFallback={id:crypto.randomUUID(),last:now};
   growthFallback.last=now;return growthFallback.id;
 }
}
function growthSend(event,path=location.pathname,target='',depth=0){
 const session=growthSid();if(!session)return;
 const attribution=growthFirst?entrySource:{};
 growthFirst=false;
 const device=innerWidth<720?'mobile':innerWidth<1100?'tablet':'desktop';
 fetch('/api/analytics/growth',{method:'POST',credentials:'omit',cache:'no-store',
   keepalive:true,headers:{'Content-Type':'application/json'},
   body:JSON.stringify({event,session,path,target,depth,device,...attribution})}).catch(()=>{});
}
function growthScroll(){
 const path=location.pathname;
 if(!/^\/(websites|sections|patterns|insights)(\/[a-z0-9-]+)?$/.test(path))return;
 if(path!==scrollPath){scrollPath=path;scrollSent=new Set()}
 const doc=document.documentElement,scrollable=Math.max(1,doc.scrollHeight-innerHeight);
 const percent=100*scrollY/scrollable;
 for(const depth of [25,50,75,90])if(percent>=depth&&!scrollSent.has(depth)){
   scrollSent.add(depth);growthSend('scroll',path,'',depth)
 }
}
function analyticsPage(){
 const path=location.pathname,now=Date.now();
 if(path===lastAnalyticsPath&&now-lastAnalyticsAt<8000)return;
 lastAnalyticsPath=path;lastAnalyticsAt=now;
 if(path==='/'||/^\/(websites|sections|patterns|insights)(\/[a-z0-9-]+)?$/.test(path))
   {analyticsEvent('page_view');growthSend('page_view',path);scrollPath=path;scrollSent=new Set()}
}
function analyticsSearch(value){
 clearTimeout(searchAnalyticsTimer);
 const query=String(value||'').trim();
 const searchPath=location.pathname.startsWith('/insights')?'/insights':location.pathname.startsWith('/sections')?'/sections':'/websites';
 if(query.length<2||query.length>60)return;
 searchAnalyticsTimer=setTimeout(()=>{
   const cleaned=query.toLowerCase().replace(/\s+/g,' ');
   if(sentSearchTerms.has(searchPath+'|'+cleaned))return;
   sentSearchTerms.add(searchPath+'|'+cleaned);
   analyticsEvent('search',cleaned,searchPath);growthSend('search',searchPath);
 },1200);
}
function go(to){let next=new URL(to,location.origin);if(next.origin!==location.origin){location.href=to;return}history.pushState({},'',next.pathname+next.search+next.hash);render();analyticsPage();window.scrollTo(0,0)}
function setQuery(k,v){const u=new URL(location.href);if(v)u.searchParams.set(k,v);else u.searchParams.delete(k);history.replaceState({},'',u.pathname+u.search)}
function decodeFilters(){let u=new URLSearchParams(location.search);state.q=u.get('q')||'';state.sector=u.get('sector')||'';state.category=u.get('category')||'';state.style=u.get('style')||'';state.color=u.get('color')||'';state.sort=u.get('sort')||'curated';state.density=u.get('density')||'standard';for(const k of ['siteType','audienceTerm','structureTerm','styleTag','researchOnly'])state[k]=u.get(k)||''}
function colorFamily(c){if(!/^#[0-9a-fA-F]{6}$/.test(c||''))return '';let [r,g,b]=[1,3,5].map(i=>parseInt(c.slice(i,i+2),16));let max=Math.max(r,g,b),min=Math.min(r,g,b),d=max-min;if(max<50)return 'Black';if(min>218)return 'White';if(d<29)return 'Gray';let a=(max===r?(g-b)/d:max===g?2+(b-r)/d:4+(r-g)/d)*60;if(a<0)a+=360;return a<15||a>=345?'Red':a<48?'Orange':a<70?'Yellow':a<165?'Green':a<250?'Blue':a<300?'Purple':'Pink'}
function styles(s){return [s.visual_style,...(s.design_strengths||[])].filter(Boolean).join(' ').toLowerCase()}
function choices(type){return Array.from(new Set((type==='websites'?state.sites.map(s=>s.sector):state.modules.map(m=>m.category)).filter(Boolean))).sort()}
function profileOf(x){const s=x?.site_id?site(x.site_id):x;return s?state.profiles[s.id]||null:null}
function researchSiteTypes(){return Array.from(new Set(Object.values(state.profiles).map(p=>p?.type).filter(Boolean))).sort()}
function researchStyleTags(){return Array.from(new Set(Object.values(state.profiles).flatMap(p=>Array.isArray(p?.style)?p.style:[]))).sort()}
function researchStructureText(p){return (p?.structure||[]).flatMap(x=>Array.isArray(x)?x:[]).join(' ').toLowerCase()}
function visibleAdvancedFilters(){return ['siteType','audienceTerm','structureTerm','styleTag','researchOnly'].filter(k=>state[k])}
function activeDiscoveryFilters(type){
 return [['q','搜索',state.q], [type==='websites'?'sector':'category',type==='websites'?'行业':'模块',type==='websites'?state.sector:state.category],['style','风格',state.style],['color','截图色',state.color],['siteType','网站类型',state.siteType],['audienceTerm','客户',AUDIENCE_TERMS.find(x=>x[1]===state.audienceTerm)?.[0]||state.audienceTerm],['structureTerm','页面结构',STRUCTURE_TERMS.find(x=>x[1]===state.structureTerm)?.[0]||state.structureTerm],['styleTag','研究风格',state.styleTag],['researchOnly','研究档案',state.researchOnly==='verified'?'已核实':'']].filter(x=>x[2]);
}
function advancedSelection(entries,selected,all,field){
 return '<label class="filter-select"><span class="sr-only">'+h(all)+'</span><select data-field="'+field+'" aria-label="'+h(all)+'"><option value="">'+h(all)+'</option>'+entries.map(([label,value])=>'<option value="'+h(value)+'" '+(value===selected?'selected':'')+'>'+h(label)+'</option>').join('')+'</select></label>';
}
function discoveryAdvancedControls(type){
 const typeOpts=researchSiteTypes(),tags=researchStyleTags();
 const advancedActive=visibleAdvancedFilters().length;
 return `<details class="discovery-advanced" ${advancedActive?'open':''}><summary><span>高级研究筛选</span><small>从已收录的企业档案和页面结构中匹配 · ${Object.keys(state.profiles).length} 份深度档案</small><b>${advancedActive||'+'}</b></summary><div class="discovery-advanced-inner">
 <div class="discovery-advanced-fields">
 ${selection(typeOpts,state.siteType,'全部网站类型','siteType')}
 ${advancedSelection(AUDIENCE_TERMS,state.audienceTerm,'目标客户关键词','audienceTerm')}
 ${advancedSelection(STRUCTURE_TERMS,state.structureTerm,'页面结构关键词','structureTerm')}
 ${selection(tags,state.styleTag,'已核实视觉风格','styleTag')}
 ${advancedSelection([['有人工检查档案','verified']],state.researchOnly,'研究资料完整度','researchOnly')}
 </div><p class="discovery-advanced-note">目标客户按企业档案中的英文关键词匹配；页面结构来自已记录的模块顺序；“已核实”仅表示有人工检查的研究档案，不代表网站质量排名。未记录的字段不会被推测。</p></div></details>`;
}
function matchList(type){const isSite=type==='websites';let src=isSite?state.sites.slice():state.modules.slice();let q=state.q.trim().toLowerCase(),terms=q.split(/\s+/).filter(Boolean);
src=src.filter(x=>{let s=isSite?x:site(x.site_id);if(!s)return false;
const p=state.profiles[s.id]||null;
if(isSite&&state.sector&&s.sector!==state.sector)return false;
if(!isSite&&state.category&&x.category!==state.category)return false;
if(state.style&&!styleRules[state.style]?.test(styles(s)))return false;
if(state.color&&!pal(x).some(c=>colorFamily(c)===state.color))return false;
if(state.siteType&&p?.type!==state.siteType)return false;
if(state.styleTag&&!(p?.style||[]).includes(state.styleTag))return false;
if(state.audienceTerm&&!(p?.audience||'').toLowerCase().includes(state.audienceTerm.toLowerCase()))return false;
if(state.structureTerm&&(!STRUCTURE_TERMS.some(x=>x[1]===state.structureTerm)||!new RegExp(state.structureTerm,'i').test(researchStructureText(p))))return false;
if(state.researchOnly==='verified'&&!p?.checked)return false;
if(terms.length){const hay=[s.name,s.sector,s.focus,s.summary,s.takeaway,s.visual_style,...(s.design_strengths||[]),x.title,x.lesson,x.category,p?.type,p?.audience,p?.about,p?.country,...(p?.style||[]),...((p?.structure||[]).flatMap(z=>Array.isArray(z)?z:[])),...((p?.breakdown||[]).flatMap(z=>Array.isArray(z)?z:[]))].filter(Boolean).join(' ').toLowerCase();
if(!terms.every(t=>hay.includes(t)))return false}return true});
if(state.sort==='az')src.sort((a,b)=>cardInfo(a).name.localeCompare(cardInfo(b).name));return src}
function paletteCircles(x){return '<span class="palette-dots" aria-label="Representative screenshot colors">'+pal(x).slice(0,3).map(c=>'<button type="button" class="color-dot" style="--swatch:'+safeHex(c)+'" title="Copy '+safeHex(c)+'" data-action="copy" data-value="'+safeHex(c)+'" aria-label="Copy '+safeHex(c)+'"></button>').join('')+'</span>'}
function card(x,index,type){
 const info=cardInfo(x),k=key(x),kind=entityKind(x),isSite=kind==='site',selected=isSite&&state.compare.includes(x.id);
 return `<article class="reference-card ${kind==='module'?'is-section':'is-'+kind}"><div class="reference-media"><a href="${info.url}" data-link="${info.url}" aria-label="研究 ${h(info.name)}"><img src="${img(entityImage(x))}" alt="${h(info.name)} 视觉预览" ${index<5?'loading="eager"':'loading="lazy"'} decoding="async"></a><div class="card-actions"><button title="${saved(k)?'取消收藏':'收藏案例'}" data-action="save" data-key="${h(k)}" aria-label="${saved(k)?'取消收藏':'收藏'} ${h(info.name)}" aria-pressed="${saved(k)}">${bookmarkIcon(saved(k))}</button>${isSite?`<button class="compare-card-action ${selected?'is-selected':''}" data-action="compare-toggle" data-site-id="${h(x.id)}" aria-pressed="${selected}" title="${selected?'从对比中移除':'加入网站对比'}" aria-label="${selected?'从对比中移除':'加入对比'} ${h(info.name)}">⇄</button>`:''}<button title="快速预览" aria-label="预览 ${h(info.name)}" data-action="preview" data-key="${h(k)}">⤢</button></div></div><div class="reference-meta"><a class="reference-name" href="${info.url}" data-link="${info.url}">${h(info.name)}</a>${kind==='site'||kind==='module'?paletteCircles(x):''}<span class="reference-category">${h(info.sub)}</span></div></article>`;
}

function selection(opts,selected,all,field){return '<label class="filter-select"><span class="sr-only">'+h(field)+'</span><select data-field="'+field+'" aria-label="'+h(field)+'"><option value="">'+h(all)+'</option>'+opts.map(x=>'<option value="'+h(x)+'" '+(x===selected?'selected':'')+'>'+h(x)+'</option>').join('')+'</select></label>'}
function topHeading(eyebrow,heading,description){return '<div class="page-heading"><span class="eyebrow">'+eyebrow+'</span><h1>'+heading+'</h1><p>'+description+'</p></div>'}
function countTop(n,label){return '<div class="results-line"><strong>'+n+'</strong><span>'+label+'</span></div>'}
function listView(type){
 const isSite=type==='websites',choice=isSite?state.sector:state.category,cats=choices(type);
 const n=isSite?state.sites.length:state.modules.length;
 const filterChoices=isSite?cats:cats;
 const tabs=isSite?[['全部网站',''],...cats.slice(0,11).map(x=>[x,x])]:[['全部模块',''],...cats.map(x=>[x,x])];
 const tabField=isSite?'sector':'category';
 const spotlight=!isSite&&state.modules.length?state.modules.find(m=>m.category&&/Hero|首屏/i.test(m.category))||state.modules[0]:null;
 return `<div class="shell listing listing-v38 ${isSite?'listing-websites':'listing-sections'}" data-listing="${type}">
  <div class="listing-header"><div><div class="eyebrow">${isSite?'WEBSITE DISCOVERY':'PAGE SECTION LIBRARY'}</div><h1>${isSite?'Websites':'Sections'}</h1><p>${isSite?'视觉优先的 B2B 网站灵感库。浏览真实案例，探索不同行业的设计语言。':'按设计任务发现真实网页中的高质量模块，研究页面细节和信息组织。'}</p></div><strong>${n} / CURATED REFERENCES</strong></div>
  <div class="listing-toolbar"><label class="search-input"><span aria-hidden="true">⌕</span><input id="library-search" type="search" placeholder="${isSite?'搜索网站、行业、设计风格…':'搜索页面模块、应用场景或公司…'}" value="${h(state.q)}" aria-label="搜索资源"><kbd>/</kbd></label>
  ${selection(filterChoices,choice,isSite?'行业':'模块类型',tabField)}${selection(FILTER_STYLE,state.style,'风格','style')}${selection(FILTER_COLOR,state.color,'配色','color')}
  <div class="view-control"><button data-action="density" data-value="standard" class="${state.density==='standard'?'active':''}" title="自然瀑布流" aria-label="标准瀑布流">▦</button><button data-action="density" data-value="compact" class="${state.density==='compact'?'active':''}" title="紧凑瀑布流" aria-label="紧凑模式">▤</button></div></div>
  ${discoveryAdvancedControls(type)}
  <div class="category-nav" role="navigation" aria-label="${isSite?'行业分类':'模块类型'}">${tabs.map(([name,value])=>`<button type="button" data-action="category" data-value="${h(value)}" class="${choice===value?'active':''}">${h(name)}</button>`).join('')}</div>
  ${spotlight?`<div class="section-spotlight"><a href="${pathModule(spotlight)}" data-link="${pathModule(spotlight)}" class="spotlight-image"><img src="${img(spotlight.screenshot_url)}" alt="${h(spotlight.title)} 模块预览"></a><div><span class="eyebrow">FEATURED SECTION</span><h2>${h(spotlight.title)}</h2><p>${h(spotlight.lesson||spotlight.summary||'从真实页面结构中学习如何突出关键信息。')}</p><a href="${pathModule(spotlight)}" data-link="${pathModule(spotlight)}" class="dark-button">研究这个模块 ↗</a></div></div>`:''}
  <div class="listing-summary"><div><h2>${isSite?'精选网页':'页面模块参考'}</h2><p>${isSite?'不同风格、不同业务，从视觉出发自由探索。':'从真实 B2B 网站中拆解可借鉴的设计。'}</p></div></div><div id="library-results"></div><div id="compare-tray-root"></div>
 </div>`;
}
function renderResults(){
 const list=$('[data-listing]');if(!list)return;
 const type=list.dataset.listing,items=matchList(type),div=$('#library-results');
 const filters=activeDiscoveryFilters(type);
 const chips=filters.length?`<div class="discovery-active"><span>当前筛选 · ${filters.length}</span>${filters.map(([k,label,v])=>`<button type="button" data-action="filter-remove" data-field="${h(k)}" title="移除${h(label)}筛选"><span>${h(label)}</span>${h(v)} <b aria-hidden="true">×</b></button>`).join('')}<button type="button" class="discovery-clear" data-action="reset-filters">全部清除</button></div>`:'';
 div.innerHTML=chips+`${countTop(items.length,type==='websites'?'个网站案例':'个页面模块')}${items.length?`<div class="masonry ${state.density==='compact'?'masonry-compact':''}">${items.map((x,i)=>card(x,i,type)).join('')}</div>`:`<div class="empty"><h2>没有找到匹配的资源</h2><p>试试其他关键词，或者清除筛选。</p><button class="primary-button" data-action="reset-filters">清除筛选</button></div>`}`;
 renderCompareTray();
}

function featuredSites(){let x=curated.map(site).filter(Boolean);return x.concat(state.sites.filter(s=>!x.includes(s)).slice(0,Math.max(0,8-x.length)))}
function homeView(){
 const featured=featuredSites(),vast=site('vast')||featured[0],study=state.profiles[vast?.id]||null;
 const industryGroups=[['工业制造','Manufacturing'],['机器人与自动化','Robotics'],['航天科技','Aerospace'],['新能源','Energy'],['企业软件','Software'],['医疗科技','Health']];
 const groups=industryGroups.map(([label,term],i)=>{const chosen=state.sites.find(s=>(s.sector||'').toLowerCase().includes(term.toLowerCase()));return {label,term,sector:chosen?.sector||'',index:i+1}}).filter(x=>x.sector);
 const trio=featured.slice(0,3).map((s,i)=>`<a href="${pathSite(s)}" data-link="${pathSite(s)}" class="hero-preview hero-preview-${i}" aria-label="查看 ${h(s.name)}"><img src="${img(s.screenshot_url)}" alt="${h(s.name)} 网站视觉预览"></a>`).join('');
 return `<div class="home-v38">
  <section class="hero-area"><div class="shell hero-grid"><div class="hero-left">
    <span class="eyebrow">B2B VISUAL RESEARCH LIBRARY</span>
    <h1>发现值得研究的<br><span>B2B 数字设计。</span></h1>
    <p>汇集工业、科技与企业产品的优秀网站、页面模块和设计方法。发现灵感，更深入地理解设计背后的逻辑。</p>
    <form id="home-search" class="hero-search"><span aria-hidden="true">⌕</span><input name="q" aria-label="搜索设计资源" placeholder="搜索网站、公司、页面模块或设计模式…"><button aria-label="搜索">搜索 ↗</button></form>
    <div class="hero-popular"><strong>热门探索</strong>${groups.slice(0,4).map(x=>`<a data-link="/websites?sector=${encodeURIComponent(x.sector)}" href="/websites?sector=${encodeURIComponent(x.sector)}">${h(x.label)}</a>`).join('')}<a data-link="/patterns" href="/patterns">询盘转化</a></div>
   </div><div class="hero-right"><div class="hero-visual" aria-label="精选网站预览">${trio}</div><div class="hero-caption"><span>● CURATED REFERENCES</span><strong>真正值得收藏的设计案例</strong></div></div>
  </div></section>
  <section class="shell home-quick-nav">
    <a href="/websites" data-link="/websites" class="quick-card quick-websites"><span class="quick-icon">◉</span><span><strong>Websites</strong><small>完整网站 · 设计研究档案</small><em>探索 ${state.sites.length} 个真实案例</em></span><b aria-hidden="true">↗</b></a>
    <a href="/sections" data-link="/sections" class="quick-card quick-sections"><span class="quick-icon">▱</span><span><strong>Sections</strong><small>局部页面 · 模块灵感参考</small><em>发现 ${state.modules.length} 个页面模块</em></span><b aria-hidden="true">↗</b></a>
    <a href="/patterns" data-link="/patterns" class="quick-card quick-patterns"><span class="quick-icon">✳</span><span><strong>Patterns</strong><small>设计方法 · 可复用解决方案</small><em>学习 ${state.patterns.length} 个设计模式</em></span><b aria-hidden="true">↗</b></a>
  </section>
  <section class="shell content-section home-featured">
    <div class="eyebrow">01 / DISCOVER</div><div class="section-heading"><div><h2>本周精选网站</h2><p>从真实的 B2B 产品案例中，发现清晰、有力量的视觉表达。</p></div><a href="/websites" data-link="/websites">查看全部 ↗</a></div>
    <div class="home-tabs"><a href="/websites" data-link="/websites" class="selected">编辑精选</a><a href="/websites?sort=az" data-link="/websites?sort=az">按名称浏览</a>${groups.slice(0,3).map(x=>`<a href="/websites?sector=${encodeURIComponent(x.sector)}" data-link="/websites?sector=${encodeURIComponent(x.sector)}">${h(x.label)}</a>`).join('')}</div>
    <div class="home-featured-grid">${featured.slice(0,4).map((s,i)=>card(s,i,'websites')).join('')}</div>
  </section>
  <section class="research-band"><div class="shell">
    <div class="eyebrow">02 / IN-DEPTH RESEARCH</div><div class="section-heading"><div><h2>不只好看，更值得研究</h2><p>从视觉、信息架构和 B2B 转化路径，理解一个优秀网站的设计价值。</p></div><a data-link="${pathSite(vast)}" href="${pathSite(vast)}">查看研究 ↗</a></div>
    <div class="case-highlight"><a href="${pathSite(vast)}" data-link="${pathSite(vast)}" class="case-cover"><img src="${img(vast.screenshot_url)}" loading="lazy" alt="${h(vast.name)} 网站案例"><span>FEATURED RESEARCH</span></a>
      <div class="case-copy"><div class="case-index"><span>DESIGN RESEARCH</span><span>真实案例</span></div><h3>${h(vast.name)}</h3><p class="case-lead">${h(vast.takeaway||vast.focus||'研究一个优秀 B2B 网站如何向客户表达核心价值。')}</p><p>${h(study?.about||vast.summary||'探索真实企业如何将复杂产品、技术实力和商业转化融入网站。')}</p><div class="case-points">${(study?.style||[vast.visual_style||'Industrial']).slice(0,3).map(x=>`<span>${h(x)}</span>`).join('')}</div><a class="dark-button" href="${pathSite(vast)}" data-link="${pathSite(vast)}">阅读完整案例 ↗</a></div>
    </div></div></section>
  <section class="shell content-section home-sections"><div class="eyebrow">03 / BUILDING BLOCKS</div><div class="section-heading"><div><h2>优秀页面，从细节开始</h2><p>拆解真正有效的 Hero、产品展示、技术能力和询盘模块。</p></div><a href="/sections" data-link="/sections">查看全部 ↗</a></div>
   <div class="home-section-grid">${state.modules.slice(0,4).map((m,i)=>card(m,i,'sections')).join('')}</div>
   <div class="purpose-strip"><span>按设计任务发现</span>${choices('sections').slice(0,6).map(x=>`<a href="/sections?category=${encodeURIComponent(x)}" data-link="/sections?category=${encodeURIComponent(x)}">${h(x)}</a>`).join('')}<a href="/sections" data-link="/sections" class="last">全部模块 ↗</a></div>
  </section>
  <section class="pattern-band"><div class="shell"><div class="eyebrow">04 / DESIGN METHODS</div><div class="section-heading"><div><h2>让灵感成为方法</h2><p>从真实案例中总结可复用的思考框架，而不是复制一张截图。</p></div><a href="/patterns" data-link="/patterns">查看全部 ↗</a></div><div class="home-pattern-grid">${state.patterns.slice(0,3).map(patternCard).join('')}</div></div></section>
  <section class="shell content-section home-insights"><div class="eyebrow">05 / INSIGHTS & RESEARCH</div><div class="section-heading"><div><h2>资讯与深度研究</h2><p>关于 B2B 数字体验的案例拆解、视觉观察与可复用的设计方法。</p></div><a href="/insights" data-link="/insights">查看全部文章 ↗</a></div><div class="insights-grid home-insights-grid">${state.articles.slice(0,3).map((a,i)=>articleCard(a,i,true)).join('')}</div></section>
  <section class="shell content-section industries"><div class="eyebrow">06 / INDUSTRIES</div><div class="section-heading"><div><h2>跨行业探索设计</h2><p>从行业与业务背景出发，发现更多值得借鉴的表达方式。</p></div><a href="/websites" data-link="/websites">查看全部 ↗</a></div><div class="industry-tiles">${groups.map(x=>`<a href="/websites?sector=${encodeURIComponent(x.sector)}" data-link="/websites?sector=${encodeURIComponent(x.sector)}"><span>${String(x.index).padStart(2,'0')}</span><strong>${h(x.label)}</strong><small>${h(x.term)}</small><b aria-hidden="true">↗</b></a>`).join('')}</div></section>
  <section class="shell bottom-cta"><div><small>YOUR NEXT REFERENCE IS HERE</small><h2>从一个好设计，<br>开始下一个好项目。</h2><p>探索资源、收藏灵感、建立自己的研究板。</p><a href="/websites" data-link="/websites">开始探索 ↗</a></div><div class="cta-visual">${featured.slice(1,3).map((s,i)=>`<img src="${img(s.screenshot_url)}" loading="lazy" alt="${h(s.name)} 网站">`).join('')}</div></section>
 </div>`;
}
/* Insights editorial module — all content comes from articles.json */
function articleBy(id){return state.articles.find(a=>a.id===id)}
function articleCat(id){return state.articleCategories.find(x=>x.id===id)}
function articleLink(a){return '/insights/'+encodeURIComponent(a.id)}
function articleImage(a){return /^\/api\/media\/[0-9a-f-]{36}$/.test(a.cover_image||'')?a.cover_image:(site(a.cover_site)?.screenshot_url||'/screenshots/sites/vast.webp')}
function articleDate(a){return (a.published_at||'').replace(/-/g,'.')}
function articleCard(a,index,small=false){
 const cat=articleCat(a.category),url=articleLink(a),k=key(a);
 return `<article class="insight-card ${small?'insight-card-small':''}"><a class="insight-card-media" href="${url}" data-link="${url}" aria-label="阅读：${h(a.title)}"><img loading="${index<3?'eager':'lazy'}" src="${img(articleImage(a))}" alt="${h(site(a.cover_site)?.name||'B2B')} 网站截图"></a>
 <div class="insight-card-copy"><div class="insight-card-meta"><a href="/insights?category=${h(a.category)}" data-link="/insights?category=${h(a.category)}" class="insight-category">${h(cat?.name||a.category)}</a><span>${h(articleDate(a))}</span><button type="button" class="article-save" data-action="save" data-key="${h(k)}" aria-label="${saved(k)?'取消收藏':'收藏'} ${h(a.title)}" aria-pressed="${saved(k)}">${bookmarkIcon(saved(k))}</button></div>
 <h3><a href="${url}" data-link="${url}">${h(a.title)}</a></h3><p>${h(a.subtitle)}</p><div class="insight-card-end"><span>阅读约 ${a.reading_minutes} 分钟</span><a href="${url}" data-link="${url}" aria-label="阅读文章 ${h(a.title)}">阅读全文 <span aria-hidden="true">↗</span></a></div></div></article>`;
}
function insightFeature(a){
 if(!a)return '';
 const url=articleLink(a),cat=articleCat(a.category);
 return `<section class="insight-feature" aria-label="精选研究"><a href="${url}" data-link="${url}" class="insight-feature-image"><img src="${img(articleImage(a))}" alt="${h(site(a.cover_site)?.name||'B2B')} 网站截图"><span>EDITOR'S PICK</span></a><div class="insight-feature-text"><div class="insight-feature-kicker"><span>精选文章</span><a href="/insights?category=${h(a.category)}" data-link="/insights?category=${h(a.category)}">${h(cat?.name||'专题研究')}</a></div><h2><a href="${url}" data-link="${url}">${h(a.title)}</a></h2><p>${h(a.subtitle)}</p><div class="insight-feature-divider"></div><div class="insight-feature-meta"><span>✎ B2B Atlas 编辑部</span><span>${h(articleDate(a))}</span><span>约 ${a.reading_minutes} 分钟</span></div><a class="insight-feature-cta" href="${url}" data-link="${url}">阅读完整文章 <span aria-hidden="true">↗</span></a></div></section>`;
}
function insightsIndex(){
 const p=new URLSearchParams(location.search),category=p.get('category')||'',q=p.get('q')||'',sort=p.get('sort')||'latest';
 const feature=state.articles.find(a=>a.featured)||state.articles[0];
 return `<div class="shell insights-index">
 <div class="insights-heading"><div><span class="eyebrow">EDITORIAL / INSIGHTS</span><h1>资讯与研究<span class="insights-heading-dot">.</span></h1><p>关于 B2B 网站、工业产品与数字体验的观察、案例和设计方法。<br>从真实参考中找到值得带进下一个项目的思路。</p></div><div class="insights-heading-aside"><strong>${state.articles.length.toString().padStart(2,'0')}</strong><span>原创研究文章</span><i></i><strong>${state.articleCategories.length.toString().padStart(2,'0')}</strong><span>研究主题</span></div></div>
 ${insightFeature(feature)}
 <section class="insights-library" aria-label="文章列表"><div class="insights-library-head"><div><span class="eyebrow">LATEST RESEARCH</span><h2>探索全部文章</h2><p>案例研究 · 设计方法 · 视觉系统 · 转化与内容策略</p></div></div>
 <div class="insights-controls"><nav class="insights-categories" aria-label="文章分类"><a href="/insights" data-link="/insights" class="${category===''?'active':''}">全部 <small>${state.articles.length}</small></a>${state.articleCategories.map(x=>{const count=state.articles.filter(a=>a.category===x.id).length;return `<a href="/insights?category=${h(x.id)}" data-link="/insights?category=${h(x.id)}" class="${category===x.id?'active':''}">${h(x.name)} <small>${count}</small></a>`}).join('')}</nav>
 <div class="insights-tools"><label class="insights-search"><span aria-hidden="true">⌕</span><input id="insights-search" type="search" placeholder="搜索研究文章…" aria-label="搜索文章" value="${h(q)}"></label><label class="insights-sort-label"><span class="sr-only">排序</span><select id="insights-sort"><option value="latest" ${sort==='latest'?'selected':''}>最新文章</option><option value="az" ${sort==='az'?'selected':''}>按标题排序</option></select></label></div></div>
 <div class="insights-results-label"><strong id="insights-result-label">文章列表</strong><span id="insights-result-count"></span></div>
 <div id="insights-results"></div></section>
 <section class="insights-next"><div><span class="eyebrow">BEYOND READING</span><h2>把研究转化成设计参考。</h2><p>阅读文章之外，还可以从真实网站、局部模块和设计模式中验证这些方法。</p></div><div class="insights-next-links"><a href="/websites" data-link="/websites">Websites <span>↗</span></a><a href="/sections" data-link="/sections">Sections <span>↗</span></a><a href="/patterns" data-link="/patterns">Patterns <span>↗</span></a></div></section>
 <p class="insights-disclaimer">${h(state.articleEditorialNotice)}</p>
 </div>`;
}
function renderInsightResults(){
 const target=$('#insights-results');if(!target)return;
 const params=new URLSearchParams(location.search),category=params.get('category')||'',q=(params.get('q')||'').trim().toLowerCase(),sort=params.get('sort')||'latest';
 const baseline=!category&&!q&&sort==='latest',feature=state.articles.find(a=>a.featured)||state.articles[0];
 const hero=$('.insight-feature');if(hero)hero.hidden=!baseline;
 let rows=state.articles.filter(a=>!category||a.category===category).filter(a=>!q||[a.title,a.subtitle,a.category,...a.tags,...a.takeaways,...a.sections.map(s=>s.title)].join(' ').toLowerCase().includes(q));
 if(sort==='az')rows.sort((a,b)=>a.title.localeCompare(b.title,'zh-Hans'));
 else rows.sort((a,b)=>(b.published_at||'').localeCompare(a.published_at||''));
 if(baseline&&feature)rows=rows.filter(a=>a.id!==feature.id);
 $('#insights-result-label').textContent=baseline?'更多精选文章':category?articleCat(category)?.name||'分类文章':'搜索结果';
 $('#insights-result-count').textContent=(baseline?state.articles.length-1:rows.length)+' 篇';
 target.innerHTML=rows.length?`<div class="insights-grid">${rows.map((a,i)=>articleCard(a,i)).join('')}</div>`:`<div class="insights-empty"><h3>没有找到相关内容</h3><p>换个关键词，或浏览其他分类。</p><a href="/insights" data-link="/insights" class="quiet-button">查看全部文章 ↗</a></div>`;
}
function insightReference(r){
 if(r[0]==='website'){let s=site(r[1]);if(!s)return '';return `<a class="insight-reference" href="${pathSite(s)}" data-link="${pathSite(s)}"><img src="${img(s.screenshot_url)}" loading="lazy" alt="${h(s.name)} 网站"><span><small>WEBSITE STUDY</small><strong>${h(s.name)}</strong><em>${h(s.sector)} · 查看案例 ↗</em></span></a>`}
 if(r[0]==='pattern'){let p=pattern(r[1]);if(!p)return '';return `<a class="insight-reference insight-reference-pattern" href="/patterns/${encodeURIComponent(p.id)}" data-link="/patterns/${encodeURIComponent(p.id)}"><span class="insight-pattern-glyph">▤</span><span><small>DESIGN PATTERN</small><strong>${h(p.title)}</strong><em>${h(p.family)} · 设计方法 ↗</em></span></a>`}
 return '';
}
function insightArticle(a){
 const cat=articleCat(a.category),url=articleLink(a);
 const related=[...state.articles.filter(x=>x.id!==a.id&&x.category===a.category),...state.articles.filter(x=>x.id!==a.id&&x.category!==a.category)].slice(0,3);
 const index=state.articles.findIndex(x=>x.id===a.id),prev=state.articles[index-1],next=state.articles[index+1];
 const sections=a.sections.map((s,i)=>`<section class="insight-prose-section" id="insight-section-${i+1}"><span class="insight-prose-number">${String(i+1).padStart(2,'0')} / ${String(a.sections.length).padStart(2,'0')}</span><h2>${h(s.title)}</h2>${s.paragraphs.map(p=>`<p>${formatArticleInline(p)}</p>`).join('')}${/^\/api\/media\/[0-9a-f-]{36}$/.test(s.image||'')?`<figure class="insight-inline-figure"><img loading="lazy" src="${h(s.image)}" alt="${h(s.image_caption||s.title||'文章配图')}">${s.image_caption?`<figcaption>${h(s.image_caption)}</figcaption>`:''}</figure>`:''}${s.bullets?.length?`<ul>${s.bullets.map(item=>`<li>${h(item)}</li>`).join('')}</ul>`:''}${s.callout?`<div class="insight-prose-callout">${h(s.callout)}</div>`:''}</section>`).join('');
 return `<div class="shell insight-article">
 <nav class="insight-breadcrumb" aria-label="当前位置"><a href="/" data-link="/">首页</a><span>/</span><a href="/insights" data-link="/insights">资讯与研究</a><span>/</span><a href="/insights?category=${h(a.category)}" data-link="/insights?category=${h(a.category)}">${h(cat?.name||a.category)}</a></nav>
 <header class="insight-article-header"><a href="/insights?category=${h(a.category)}" data-link="/insights?category=${h(a.category)}" class="insight-article-category">${h(cat?.name||a.category)}</a><h1>${h(a.title)}</h1><p>${h(a.subtitle)}</p><div class="insight-article-meta"><span class="insight-author-avatar">BA</span><span> B2B Atlas 编辑部</span><i></i><time datetime="${h(a.published_at)}">${h(articleDate(a))}</time><i></i><span>阅读约 ${a.reading_minutes} 分钟</span><button type="button" class="detail-bookmark-button" data-action="save" data-key="${h(key(a))}" aria-pressed="${saved(key(a))}">${bookmarkIcon(saved(key(a)))} ${saved(key(a))?'已收藏':'收藏文章'}</button><button data-action="share-article" type="button"><span aria-hidden="true">↗</span> 复制文章链接</button></div></header>
 <figure class="insight-cover"><img src="${img(articleImage(a))}" alt="${h(site(a.cover_site)?.name||'设计案例')} 网站截图"><figcaption>配图：B2B Atlas 收录的 ${h(site(a.cover_site)?.name||'网站')} 页面截图，供设计观察使用。</figcaption></figure>
 <div class="insight-article-layout"><article class="insight-prose"><div class="insight-intro"><span class="eyebrow">EDITORIAL NOTE</span><p>${h(a.subtitle)}</p></div><div class="insight-takeaways"><h2>本文要点</h2><ul>${a.takeaways.map(t=>`<li>${h(t)}</li>`).join('')}</ul></div>${sections}
 <div class="insight-conclusion"><h2>把观察带回设计项目</h2><p>这些内容是基于收录案例与设计方法整理的编辑性研究，适合用于建立讨论框架。具体到你的项目，仍需结合真实用户、业务内容和产品限制验证。</p><div class="insight-tags">${a.tags.map(t=>`<span># ${h(t)}</span>`).join('')}</div></div></article>
 <aside class="insight-article-aside"><div class="insight-aside-inner"><div class="insight-aside-group"><h3>文章目录</h3><nav aria-label="文章目录">${a.sections.map((s,i)=>`<a href="#insight-section-${i+1}" data-action="anchor" data-target="insight-section-${i+1}"><span>${String(i+1).padStart(2,'0')}</span>${h(s.title)}</a>`).join('')}</nav></div><div class="insight-aside-group"><h3>关联研究资源</h3><div class="insight-references">${a.references.map(insightReference).join('')}</div></div><a class="insight-back" href="/insights" data-link="/insights">← 返回全部文章</a></div></aside></div>
 <nav class="insight-article-pager" aria-label="上一篇和下一篇"><div>${prev?`<a href="${articleLink(prev)}" data-link="${articleLink(prev)}"><span>← 上一篇</span><strong>${h(prev.title)}</strong></a>`:''}</div><div>${next?`<a href="${articleLink(next)}" data-link="${articleLink(next)}"><span>下一篇 →</span><strong>${h(next.title)}</strong></a>`:''}</div></nav>
 <section class="insight-related"><div class="section-heading"><div><span class="eyebrow">KEEP READING</span><h2>继续阅读</h2><p>更多关于 B2B 产品、设计方法和网站研究的文章。</p></div><a href="/insights" data-link="/insights">全部文章 ↗</a></div><div class="insights-grid">${related.map((x,i)=>articleCard(x,i,true)).join('')}</div></section>
 </div>`;
}
function patternCard(p){
 const examples=(p.modules||[]).map(moduleBy).filter(Boolean).slice(0,2),url='/patterns/'+encodeURIComponent(p.id),k=key(p);
 return `<article class="pattern-card"><a class="pattern-card-main" href="${url}" data-link="${url}"><div class="pattern-media">${examples.length?examples.map(m=>`<img src="${img(m.screenshot_url)}" loading="lazy" alt="${h(m.title)}">`).join(''):`<div class="pattern-placeholder">${h(p.family)}</div>`}</div>
 <div class="pattern-meta"><span>${h(p.family)}</span><h2>${h(p.title)}</h2><p>${h(p.question)}</p><b>查看设计方法 ↗</b></div></a>
 <button type="button" class="pattern-save" data-action="save" data-key="${h(k)}" aria-pressed="${saved(k)}" title="${saved(k)?'取消收藏':'收藏设计模式'}" aria-label="${saved(k)?'取消收藏':'收藏'} ${h(p.title)}">${bookmarkIcon(saved(k))}</button></article>`;
}
function patternsView(){
 const families=Array.from(new Set(state.patterns.map(x=>x.family))),select=new URLSearchParams(location.search).get('family')||'';
 const rows=state.patterns.filter(p=>!select||p.family===select);
 const featured=rows[0]||state.patterns[0];
 return `<div class="shell patterns-page patterns-v38"><div class="patterns-hero"><div><div class="eyebrow">PATTERNS / DESIGN METHODS</div><h1>好的设计，<br>背后都有方法。</h1><p>理解设计问题、解决原则与适用场景，再借助真实案例验证你的判断。</p><a href="#pattern-list" data-action="anchor" data-target="pattern-list" class="primary-button">探索设计模式 ↗</a></div><div class="pattern-lead-preview">${featured?patternCard(featured):''}</div></div>
 <div class="pattern-principles"><div><b>01</b><h3>识别问题</h3><p>明确 B2B 用户的决策任务，而不是先选择视觉形式。</p></div><div><b>02</b><h3>研究案例</h3><p>查看实际页面如何组织内容、功能与证据。</p></div><div><b>03</b><h3>提炼方法</h3><p>比较不同案例，把灵感转化为可复用的设计策略。</p></div></div>
 <section id="pattern-list" class="pattern-list"><div class="section-heading"><div><h2>按问题探索设计模式</h2><p>${state.patterns.length} 个与真实页面关联的研究主题</p></div></div>
 <nav class="category-nav" aria-label="设计模式类别"><a class="${!select?'active':''}" href="/patterns" data-link="/patterns">全部模式</a>${families.map(f=>`<a class="${select===f?'active':''}" href="/patterns?family=${encodeURIComponent(f)}" data-link="/patterns?family=${encodeURIComponent(f)}">${h(f)}</a>`).join('')}</nav>
 <div class="pattern-grid">${rows.map(patternCard).join('')}</div></section>
 <section class="pattern-bottom"><div class="section-heading"><div><h2>从一种模式，找到更多真实参考</h2><p>研究模式和网站之间的关联，而不是孤立地复制页面。</p></div></div><div class="home-quick-nav"><a href="/websites" data-link="/websites" class="quick-card quick-websites"><span class="quick-icon">◉</span><span><strong>Websites</strong><small>完整网站研究</small></span><b>↗</b></a><a href="/sections" data-link="/sections" class="quick-card quick-sections"><span class="quick-icon">▱</span><span><strong>Sections</strong><small>真实页面模块</small></span><b>↗</b></a></div></section></div>`;
}
function patternDetail(p){const examples=p.modules.map(moduleBy).filter(Boolean);return '<div class="shell pattern-study"><div class="breadcrumb"><a href="/patterns" data-link="/patterns">← Patterns</a> <span>/</span> '+h(p.family)+'</div><div class="pattern-study-head"><div><span class="eyebrow">'+h(p.family)+'</span><h1>'+h(p.title)+'</h1><p>'+h(p.question)+'</p></div><div class="pattern-detail-actions"><button class="quiet-button detail-bookmark-button" data-action="save" data-key="pattern:'+h(p.id)+'">'+bookmarkIcon(saved(key(p)))+(saved(key(p))?' 已收藏':' 收藏模式')+'</button><a href="/patterns" data-link="/patterns" class="quiet-button">全部模式 ↗</a></div></div><div class="pattern-summary"><div><span>Design principle</span><p>'+h(p.principle)+'</p></div><div><span>When to use</span><p>'+h(p.when)+'</p></div><div><span>What to compare</span><p>'+h(p.compare)+'</p></div></div><div class="section-heading"><h2>Real examples</h2><span>'+examples.length+' reviewed sections</span></div><div class="section-grid">'+examples.map((m,i)=>card(m,i,'sections')).join('')+'</div><div class="pattern-guidance"><h2>Applying this pattern</h2><p>Start with the buyer task and available content. Evaluate the examples above for their visual order, clarity and next action; do not copy the appearance without its context.</p><a href="/sections" data-link="/sections">Explore more sections ↗</a></div></div>'}
function screenshots(s,mod,p){if(mod)return [{label:mod.title,url:mod.screenshot_url,source:mod.url},...state.modules.filter(x=>x.site_id===s.id&&x.id!==mod.id).slice(0,8).map(x=>({label:x.title,url:x.screenshot_url,source:x.url}))];if(p&&p.captures&&p.captures.length)return p.captures.map(([slug,label,url])=>({label,url:'/screenshots/research/'+s.id+'-'+slug+'.jpg',source:s.id==='vast'?'https://www.vastspace.com'+url:new URL(url,s.url).href,mobile:slug==='mobile'}));return [{label:'Homepage',url:s.screenshot_url,source:s.url},...state.notes.filter(x=>x.site_id===s.id).slice(0,8).map(x=>({label:x.title,url:x.screenshot_url,source:x.url}))]}
function attrRow(k,v){return v?'<div><dt>'+h(k)+'</dt><dd>'+h(v)+'</dd></div>':''}
function fullPalette(s,mod,p){let colors=(p&&!mod&&p.colors&&p.colors.length)?p.colors:pal(mod||s).map(x=>[x,'Screenshot color']);return '<div class="palette-grid">'+colors.map(([c,n])=>'<button class="palette-sample" data-action="copy" data-value="'+safeHex(c)+'" title="Copy '+safeHex(c)+'"><span style="background:'+safeHex(c)+'"></span><strong>'+safeHex(c)+'</strong><small>'+h(n)+'</small></button>').join('')+'</div><p class="source-note">'+(p&&!mod?'Observed source-page CSS colors; not an official brand guide.':'Extracted from screenshot imagery; not verified brand tokens.')+'</p>'}
function detailBreakdown(s,m,p){if(m)return [['Section purpose',m.lesson||m.summary||'A real captured section'],['Information hierarchy','Study the ordering of text, visuals and next actions.']];if(p&&p.breakdown?.length)return p.breakdown;return [['Editorial observation',s.takeaway||s.summary||'Review the original source capture.','Compare the visual emphasis with your own user task.'],['Visual direction',s.visual_style||'Not yet audited','An observed editorial description, not a measured specification.'],...(s.design_strengths||[]).slice(0,3).map(t=>['Design attribute',t,'Inspect the screenshot and original source before reusing this idea.'])]}
function detailView(s,m){
 const p=state.profiles[s.id],data=screenshots(s,m,p);currentScreens=data;currentScreen=0;
 const name=m?m.title:s.name,desc=m?`${s.name} · ${m.category}`:s.focus;
 const k=key(m||s),reviewed=!!(p&&!m);
 const related=state.modules.filter(x=>x.site_id===s.id&&x.id!==m?.id).slice(0,8);
 const relatedPatterns=state.patterns.filter(x=>(x.modules||[]).some(id=>state.modules.some(y=>y.site_id===s.id&&y.id===id))).slice(0,4);
 const breakdown=detailBreakdown(s,m,p);
 const target=m?'/sections':'/websites';
 const specs=[['企业',s.name],['所属行业',s.sector],['业务方向',s.focus],['网站类型',m?'页面模块':p?.type||'企业网站'],['所在地区',p?.country],['目标客户',p?.audience]].filter(x=>x[1]);
 const colors=fullPalette(s,m,p);
 const intro=h(m?(m.summary||m.lesson||s.summary):(p?.about||s.summary||s.focus||''));
 const tags=(p&&!m?p.style:[s.visual_style,...(s.design_strengths||[])]).filter(Boolean);
 return `<div class="shell dossier dossier-v38">
  <div class="detail-back-row"><a href="${target}" data-link="${target}">← 返回${m?'Sections':'Websites'}</a><div class="detail-utilities"><button data-action="save" data-key="${h(k)}" aria-label="收藏">${bookmarkIcon(saved(k))}</button><button data-action="board" data-key="${h(k)}" aria-label="添加到工作台">${inBoard(k)?'✓':'+'}</button>${!m?'<button data-action="compare-toggle" data-site-id="'+h(s.id)+'" aria-pressed="'+state.compare.includes(s.id)+'" title="加入网站对比">⇄ 对比</button>':''}<a href="${h(m?.url||s.url)}" target="_blank" rel="noopener noreferrer" aria-label="打开原始网站">↗</a></div></div>
  <div class="detail-top"><div class="detail-visual">
   <button class="detail-hero" id="detail-hero" data-action="image" data-index="0" aria-label="查看大图"><img id="detail-image" src="${img(data[0].url)}" alt="${h(data[0].label)} 网页截图" fetchpriority="high"><span>⤢ 放大查看</span></button>
   <div class="capture-note"><strong id="capture-label">${h(data[0].label)}</strong><a id="capture-source" href="${h(data[0].source)}" target="_blank" rel="noopener noreferrer">原始页面 ↗</a></div>
   <div class="capture-thumbs">${data.map((x,i)=>`<button class="${i===0?'selected':''}" data-action="thumb" data-index="${i}" aria-pressed="${i===0}" title="${h(x.label)}"><img src="${img(x.url)}" alt="" loading="lazy"><span>${h(x.label)}</span></button>`).join('')}</div>
  </div>
  <aside class="detail-overview">
   <div class="eyebrow">${m?'SECTION STUDY':'WEBSITE RESEARCH'}</div><div class="detail-title-line"><h1>${h(name)}</h1>${reviewed?'<span class="reviewed-tag">✓ 已核实</span>':''}</div>
   <p class="detail-intro">${intro}</p><dl class="specs">${specs.map(x=>attrRow(x[0],x[1])).join('')}</dl>
   <div class="detail-small-block"><h2>设计风格</h2><div class="tag-set">${tags.map(x=>`<span>${h(x)}</span>`).join('')||'<span>未审核</span>'}</div></div>
   <div class="detail-small-block"><h2>配色方案</h2>${colors}</div>
   <div class="detail-small-block"><h2>字体信息</h2>${p?.fonts?.length&&!m?`<div class="type-list">${p.fonts.map(([family,role])=>`<div><strong class="type-sample">Aa</strong><div><b>${h(family)}</b><small>${h(role)}</small></div></div>`).join('')}</div>`:'<p class="source-note">暂未取得可核实的字体信息。</p>'}</div>
   <div class="dossier-actions"><button class="quiet-button" data-action="save" data-key="${h(k)}">${bookmarkIcon(saved(k))}${saved(k)?' 已收藏':' 收藏'}</button><button class="quiet-button" data-action="board" data-key="${h(k)}">${inBoard(k)?'✓ 已加入工作台':'+ 研究工作台'}</button>${!m?'<button class="quiet-button" data-action="compare-toggle" data-site-id="'+h(s.id)+'" aria-pressed="'+state.compare.includes(s.id)+'">⇄ '+(state.compare.includes(s.id)?'已加入对比':'加入对比')+'</button>':''}<a class="primary-button" href="${h(m?.url||s.url)}" target="_blank" rel="noopener noreferrer">访问原网站 ↗</a></div>
  </aside></div>
  <nav class="detail-jump" aria-label="研究内容导航"><a href="#design-analysis" data-action="anchor" data-target="design-analysis">设计分析</a><a href="#structure" data-action="anchor" data-target="structure">网站结构</a><a href="#key-sections" data-action="anchor" data-target="key-sections">关联 Sections</a><a href="#related-patterns" data-action="anchor" data-target="related-patterns">关联 Patterns</a></nav>
  <section class="detail-insight" id="design-analysis"><div class="detail-section-heading"><span class="eyebrow">DESIGN REVIEW</span><h2>先理解业务，<br>再研究设计。</h2><p>根据实际页面和企业信息，拆解视觉语言、信息层级和 B2B 转化方式。未核实内容不会被当作事实。</p></div>
  <div class="analysis-grid">${breakdown.map((r,i)=>`<article><span class="analysis-index">${String(i+1).padStart(2,'0')}</span><b>${h(r[0])}</b><p>${h(r[1])}</p>${r[2]?`<small>${h(r[2])}</small>`:''}</article>`).join('')}</div></section>
  <section class="detail-structure" id="structure"><div class="section-heading"><div><span class="eyebrow">INFORMATION ARCHITECTURE</span><h2>网站如何组织复杂内容</h2><p>从品牌价值到技术能力，理解信息的呈现顺序。</p></div></div>
  <div class="structure-list">${p?.structure?.length&&!m?p.structure.map((a,i)=>`<div><span>${String(i+1).padStart(2,'0')}</span><b>${h(a[0])}</b><small>${h(a[1])}</small></div>`).join(''):`<div><span>01</span><b>项目定位</b><small>${h(s.focus||s.sector)}</small></div><div><span>02</span><b>设计参考</b><small>通过截图和关联 Sections 分析网页结构</small></div>`}</div></section>
  <section class="detail-related" id="key-sections"><div class="section-heading"><div><span class="eyebrow">RELATED REFERENCES</span><h2>来自 ${h(s.name)} 的页面参考</h2></div><a href="/sections" data-link="/sections">浏览全部 ↗</a></div>${related.length?`<div class="section-grid">${related.slice(0,6).map((x,i)=>card(x,i,'sections')).join('')}</div>`:'<p class="source-note">当前暂无相关页面截图。</p>'}</section>
  <section class="detail-related" id="related-patterns"><div class="section-heading"><div><span class="eyebrow">REUSABLE THINKING</span><h2>同类设计方法</h2></div><a href="/patterns" data-link="/patterns">更多模式 ↗</a></div>${relatedPatterns.length?`<div class="pattern-preview">${relatedPatterns.map(patternCard).join('')}</div>`:'<p class="source-note">尚未建立已审核的关联模式。</p>'}</section>
  <section class="detail-related"><div class="section-heading"><div><span class="eyebrow">CONTINUE DISCOVERING</span><h2>继续探索相似网站</h2></div><a href="/websites" data-link="/websites">浏览全部 ↗</a></div><div class="section-grid">${state.sites.filter(x=>x.id!==s.id).sort((a,b)=>Number(b.sector===s.sector)-Number(a.sector===s.sector)).slice(0,3).map((x,i)=>card(x,i,'websites')).join('')}</div></section>
  <section class="detail-sources"><strong>资料来源</strong><span>${reviewed?'部分属性来自已检查的官网与样式声明。其他资源仍以截图观察为主。':'当前资料为收录时的编辑性描述，部分设计属性尚未独立核实。'}</span><div class="sources">${(p?.sources?.length&&!m?p.sources:[[s.name,s.url]]).map(([title,url])=>`<a href="${h(url)}" target="_blank" rel="noopener noreferrer">${h(title)} ↗</a>`).join('')}</div></section>
 </div>`;
}

/* Account and identity: all personal data is fetched from the authenticated API.
   Never treat localStorage entries as authenticated saves. */
function loggedIn(){return !!state.auth?.authenticated}
function normalizeNext(v){
 try{if(!v||v.startsWith('//'))return '/account';const u=new URL(v,location.origin);return u.origin===location.origin&&u.pathname.startsWith('/')?u.pathname+u.search:'/account'}catch{return '/account'}
}
function authDestination(){return normalizeNext(new URLSearchParams(location.search).get('next')||'/account')}
async function api(url,options={}){
 const headers={'Content-Type':'application/json',...options.headers};
 if(state.auth?.csrf_token)headers['X-CSRF-Token']=state.auth.csrf_token;
 if(url==='/api/auth/register'||(url==='/api/me/library'&&options.method==='POST')){
   const sid=growthSid();if(sid)headers['X-Atlas-Session']=sid;
 }
 const response=await fetch(url,{...options,credentials:'same-origin',headers,cache:'no-store'});
 let body={};try{body=await response.json()}catch{}
 if(!response.ok){let message=typeof body.detail==='string'?body.detail:response.status===401?'会话已过期，请重新登录。':response.status===503?'账号服务暂时不可用，请稍后重试。':'操作失败，请重试。';const e=new Error(message);e.status=response.status;throw e}
 return body;
}
async function loadLibrary(){
 if(!loggedIn()){state.saved=[];state.board=[];state.notesByKey={};state.folders=[];state.folderItems={};state.annotations={};state.comparisons=[];return}
 const d=await api('/api/me/library');
 state.saved=d.saved||[];state.board=d.board||[];state.notesByKey=d.notes||{};
 state.folders=d.folders||[];state.folderItems=d.folderItems||{};state.annotations=d.annotations||{};state.comparisons=d.comparisons||[];
}
async function syncAuth(){
 try{
  const status=await api('/api/auth/status');
  state.authStatus=status;
  if(!status.available){state.auth={authenticated:false,user:null,csrf_token:''};state.authReady=true;return}
  const me=await api('/api/auth/me');
  state.auth=me.authenticated?me:{authenticated:false,user:null,csrf_token:''};
  if(me.authenticated)await loadLibrary();
 }catch(e){
  console.warn('Account bootstrap unavailable',e.message);
  state.auth={authenticated:false,user:null,csrf_token:''};
  state.authStatus={available:false,mode:'unavailable',message:'账号服务暂时不可用。'};
 }finally{state.authReady=true}
}
function accountPrompt(message='登录后即可收藏与建立研究板。'){
 const path=location.pathname;
 const isBoard=path==='/board';
 const isSaved=path==='/collections'||path==='/discover';
 const heading=isBoard?'让每一个好想法，<br>都有继续生长的地方。':isSaved?'喜欢的设计，<br>不该只看过一次。':'为你的设计灵感，<br>留一个专属空间。';
 const badge=isBoard?'RESEARCH BOARD':isSaved?'SAVED REFERENCES':'PRIVATE RESEARCH SPACE';
 const lead=isBoard?'登录后把网站和页面参考整理为自己的研究板，留下思路、记录笔记，随时继续。':isSaved?'登录后收藏真实 B2B 网站和页面模块。下次打开，继续从自己喜欢的案例出发。':'登录 B2B Atlas，建立自己的设计收藏与研究板。浏览、保存和整理，都由你掌握。';
 const next=encodeURIComponent(path+location.search);
 const login='/login?next='+next,register='/register?next='+next;
 const picks=['vast','fictiv','skydio'].map(x=>site(x)).filter(Boolean);
 const previews=picks.map((s,i)=>`<div class="access-example"><div class="access-example-image"><img src="${img(s.screenshot_url)}" loading="${i===0?'eager':'lazy'}" alt="${h(s.name)} 公开网站参考图"></div><div class="access-example-meta"><strong>${h(s.name)}</strong><small>${h(s.sector)}</small></div><span class="access-example-marker" aria-hidden="true">↗</span></div>`).join('');
 return `<div class="access-landing"><div class="shell">
   <div class="access-breadcrumb"><a href="/" data-link="/">B2B Atlas</a><span aria-hidden="true">/</span><span>${isBoard?'研究工作台':isSaved?'我的收藏':'个人中心'}</span><span class="access-breadcrumb-status"><span></span> 需要登录</span></div>
   <section class="access-stage" aria-labelledby="access-title">
    <div class="access-content"><div class="access-kicker"><span class="access-kicker-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><rect x="5" y="10" width="14" height="11" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3"/></svg></span><span>${badge}</span></div>
      <h1 id="access-title">${heading}</h1><p class="access-lead">${lead}</p>
      <div class="access-actions"><a href="${login}" data-link="${login}" class="access-primary">登录并继续 <span aria-hidden="true">↗</span></a><a href="${register}" data-link="${register}" class="access-secondary">创建免费账户 <span aria-hidden="true">→</span></a></div>
      <p class="access-account-note">已有账户可直接登录；新用户只需要邮箱和密码。</p>
      <div class="access-benefits"><div><span aria-hidden="true">01</span><strong>保存灵感</strong><small>网站与页面参考集中收藏</small></div><div><span aria-hidden="true">02</span><strong>持续研究</strong><small>整理研究板，记录自己的观察</small></div><div><span aria-hidden="true">03</span><strong>个人专属</strong><small>收藏和笔记按账号分开保存</small></div></div>
    </div>
    <div class="access-preview" aria-label="个人资料库展示示意">
      <div class="access-preview-top"><div class="access-preview-brand"><span class="access-preview-brandmark">◈</span><span>My research space<small>PRIVATE LIBRARY</small></span></div><div class="access-preview-avatar" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><circle cx="12" cy="8" r="3.5"/><path d="M5.5 20c.4-4.1 2.9-6.2 6.5-6.2s6.1 2.1 6.5 6.2"/></svg></div></div>
      <div class="access-preview-tabs"><span class="active">Saved websites</span><span>Research board</span></div>
      <div class="access-preview-label"><span>RECENT REFERENCES</span><span>VISUAL RESEARCH ↗</span></div>
      <div class="access-preview-list">${previews}</div>
      <div class="access-preview-bottom"><span aria-hidden="true">◎</span><span>你的个人收藏将在登录后显示</span></div>
      <span class="access-preview-corner" aria-hidden="true"></span>
    </div>
   </section>
   <div class="access-after"><span>只想先逛逛？</span><a href="/websites" data-link="/websites">浏览 Websites ↗</a><a href="/sections" data-link="/sections">探索 Sections ↗</a><a href="/insights" data-link="/insights">阅读 Insights ↗</a></div>
 </div></div>`;
}
function recoveryView(reset=false){
 const ready=!!state.authStatus.password_reset_available,token=new URLSearchParams(location.search).get('token')||'';
 return `<div class="shell auth-page recovery-page"><div class="auth-aside"><span class="eyebrow">ACCOUNT SECURITY</span><h1>重新获得<br>你的设计资料。</h1><p>个人收藏和研究笔记属于你的账号。通过邮箱重置密码，不会丢失原来的资料。</p></div><section class="auth-card"><span class="eyebrow">${reset?'RESET PASSWORD':'RECOVER ACCOUNT'}</span><h2>${reset?'设置新密码':'找回密码'}</h2><p>${reset?'设置至少 10 位的新密码。':'输入注册邮箱，我们会发送一次性密码重置链接。'}</p>
 ${!ready?'<div class="auth-alert">网站暂未配置发信服务。密码找回暂不可用，请联系网站管理员。</div>':reset&&!token?'<div class="auth-alert">缺少重置令牌，请从邮件中的链接打开。</div>':`<form id="${reset?'password-reset-form':'password-request-form'}">${reset?`<input name="token" type="hidden" value="${h(token)}"><label>新密码<input type="password" name="new_password" autocomplete="new-password" minlength="10" maxlength="128" required></label>`:`<label>注册邮箱<input type="email" name="email" autocomplete="email" placeholder="you@example.com" required></label>`}<p id="recovery-error" class="auth-error" role="alert" hidden></p><button class="primary-button auth-submit" type="submit">${reset?'更新密码':'发送重置邮件'} ↗</button></form>`}
 <p class="auth-switch"><a href="/login" data-link="/login">← 返回登录</a></p></section></div>`;
}
async function submitRecovery(form){
 const data=new FormData(form),reset=form.id==='password-reset-form',err=$('#recovery-error'),button=form.querySelector('button[type=submit]');
 if(button)button.disabled=true;if(err)err.hidden=true;
 try{const payload=reset?{token:String(data.get('token')||''),new_password:String(data.get('new_password')||'')}:{email:String(data.get('email')||'')};
 await api('/api/auth/'+(reset?'reset-password':'request-password-reset'),{method:'POST',body:JSON.stringify(payload)});
 notify(reset?'密码已更新，请重新登录':'如果邮箱已注册，重置邮件将在稍后发送');if(reset)go('/login');else form.reset();
 }catch(e){if(err){err.textContent=e.message;err.hidden=false}else notify(e.message)}finally{if(button)button.disabled=false}
}
function authView(register=false){
 const label=register?'注册账户':'登录账户';
 const next=authDestination();
 const status=state.authStatus;
 if(loggedIn())return '<div class="shell auth-page"><div class="account-gate"><h1>你已经登录</h1><p>继续进入用户中心查看个人收藏与资料。</p><a href="/account" data-link="/account" class="primary-button">进入用户中心 ↗</a></div></div>';
 return '<div class="shell auth-page"><div class="auth-aside"><span class="eyebrow">YOUR B2B ATLAS</span><h1>把优秀设计，<br>变成你的灵感资产。</h1><p>创建专属账号，在不同设备间查看个人收藏、研究板和项目笔记。研究不用从头开始。</p><div class="auth-perks"><div><b>01</b><span>保存网站与 Section 参考</span></div><div><b>02</b><span>建立自己的设计研究板</span></div><div><b>03</b><span>跨会话访问个人资料</span></div></div></div><section class="auth-card"><div class="auth-card-title"><span class="eyebrow">ACCOUNT / '+(register?'REGISTER':'SIGN IN')+'</span><h2>'+label+'</h2><p>'+(register?'创建一个账号，开始收藏你喜欢的设计案例。':'欢迎回来，继续整理你的 B2B 设计参考。')+'</p></div>'
 +(status.mode==='demo'?'<p class="auth-alert">演示存储：重新部署后账号数据可能丢失，请勿用于正式资料。</p>':'')
 +(!status.available?'<div class="auth-alert">'+h(status.message||'账号服务暂不可用。')+'</div>':'<form id="auth-form" data-mode="'+(register?'register':'login')+'"><label>邮箱地址<input name="email" type="email" autocomplete="email" placeholder="you@example.com" required maxlength="254"></label>'+(register?'<label>昵称<input name="display_name" autocomplete="nickname" placeholder="你的显示名称" required minlength="2" maxlength="48"></label>':'')+'<label>密码<input name="password" type="password" autocomplete="'+(register?'new-password':'current-password')+'" placeholder="'+(register?'至少 10 位字符':'输入密码')+'" required minlength="'+(register?'10':'1')+'" maxlength="128"></label><p id="auth-form-error" class="auth-error" role="alert" hidden></p><button class="primary-button auth-submit" type="submit">'+(register?'创建账户':'登录')+' ↗</button></form>')
 +'<p class="auth-switch">'+(register?'已有账户？':'还没有账户？')+' <a href="'+(register?'/login':'/register')+'?next='+encodeURIComponent(next)+'" data-link="'+(register?'/login':'/register')+'?next='+encodeURIComponent(next)+'">'+(register?'前往登录':'免费创建账户')+'</a></p><p class="auth-smallprint">使用邮箱和密码登录。'+(!register&&state.authStatus.password_reset_available?'<a href="/forgot-password" data-link="/forgot-password">忘记密码？</a>':'当前邮箱找回尚未启用，请妥善保管密码。')+'</p></section></div>';
}
function accountView(){
 if(!loggedIn())return accountPrompt('用户中心仅对登录用户开放，你的收藏和研究板会按账户隔离。');
 const u=state.auth.user||{},savedCount=state.saved.length,boardCount=state.board.length;
 const tab=new URLSearchParams(location.search).get('tab')||'saved',items=(tab==='board'?state.board:state.saved).map(byKey).filter(Boolean);
 const legacyCount=(state.legacySaved?.length||0)+(state.legacyBoard?.length||0);
 const joined=u.created_at?u.created_at.slice(0,10):'';
 return '<div class="shell account-page"><div class="account-head"><div><span class="eyebrow">MY ACCOUNT / USER CENTER</span><h1>个人中心</h1><p>管理个人资料、收藏和设计研究板。</p></div><div class="account-head-actions"><button class="quiet-button" data-action="export-personal">导出数据 ↓</button><button class="quiet-button" data-action="logout">退出登录 ↗</button></div></div>'
 +'<div class="account-overview"><div class="account-person"><div class="account-avatar">'+h((u.display_name||'A').slice(0,1).toUpperCase())+'</div><div><strong>'+h(u.display_name)+'</strong><span>'+h(u.email)+'</span><small>加入于 '+h(joined)+'</small></div></div><div class="account-metrics"><div><strong>'+savedCount+'</strong><span>已收藏</span></div><div><strong>'+boardCount+'</strong><span>研究板案例</span></div></div></div>'
 +(legacyCount?'<div class="account-import"><div><b>发现此浏览器的旧版本地收藏</b><p>有 '+legacyCount+' 条旧数据。仅在你确认后导入当前账号，避免把共用设备的资料误关联到你。</p></div><button data-action="import-legacy" class="quiet-button">导入到当前账号 ↗</button></div>':'')
 +'<div class="account-layout"><section class="account-library"><div class="account-library-head"><div><span class="eyebrow">YOUR REFERENCE LIBRARY</span><h2>我的资料库</h2></div><a href="/websites" data-link="/websites">发现更多 ↗</a></div><nav class="account-tabs" aria-label="个人资料分类"><a href="/account?tab=saved" data-link="/account?tab=saved" class="'+(tab!=='board'?'active':'')+'">我的收藏 <small>'+savedCount+'</small></a><a href="/account?tab=board" data-link="/account?tab=board" class="'+(tab==='board'?'active':'')+'">研究板 <small>'+boardCount+'</small></a><a href="/collections" data-link="/collections">我的收藏夹 <small>'+state.folders.length+'</small></a></nav>'
 +(items.length?'<div class="account-gallery">'+items.map(x=>savedDetailCard(key(x))).join('')+'</div>':'<div class="account-empty"><span>♡</span><h3>'+(tab==='board'?'研究板还没有内容':'还没有收藏的参考')+'</h3><p>在网站或 Section 上点击收藏，即可把优质案例保存到你的账号。</p><a href="/websites" data-link="/websites" class="primary-button">探索 Websites ↗</a></div>')+'</section>'
 +'<aside class="account-settings"><section><h2>个人资料</h2><p>更新在站内显示的名字。</p><form id="profile-form"><label>昵称<input name="display_name" maxlength="48" minlength="2" required value="'+h(u.display_name)+'"></label><label>账户邮箱<input value="'+h(u.email)+'" disabled></label><button class="quiet-button" type="submit">保存资料</button><p class="account-inline-message" id="profile-message" hidden></p></form></section>'
 +'<section><h2>管理员授权</h2><p>后台使用当前账号登录，但只有站点所有者明确授权的用户才能进行内容管理。下面是当前账号唯一 ID，不是密码。</p><label>当前账户 ID<input readonly value="'+h(u.id||'')+'"></label><button class="quiet-button" type="button" data-action="copy" data-value="'+h(u.id||'')+'">复制账号 ID</button><p><a href="/admin/content" class="quiet-button">打开管理后台 ↗</a></p></section>'
 +'<section><h2>账户安全</h2><p>修改密码后，其他设备的登录会话将失效。</p><form id="password-form"><label>当前密码<input name="current_password" type="password" autocomplete="current-password" required></label><label>新密码<input name="new_password" type="password" autocomplete="new-password" minlength="10" maxlength="128" required placeholder="至少 10 位字符"></label><button class="quiet-button" type="submit">更新密码</button><p class="account-inline-message" id="password-message" hidden></p></form></section><div class="account-security-note">收藏与研究笔记按账号隔离保存，密码不以明文存储。当前仍使用会到期的免费数据库，请定期导出个人数据；正式运营前需迁移到有备份保障的持久存储。</div></aside></div></div>';
}
async function submitAuth(form){
 const data=new FormData(form),register=form.dataset.mode==='register';
 const payload={email:String(data.get('email')||''),password:String(data.get('password')||'')};
 if(register)payload.display_name=String(data.get('display_name')||'');
 const err=$('#auth-form-error'),button=form.querySelector('button[type=submit]');
 if(err)err.hidden=true;if(button)button.disabled=true;
 try{
  const me=await api('/api/auth/'+(register?'register':'login'),{method:'POST',body:JSON.stringify(payload)});
  state.auth=me;await loadLibrary();
  notify(register?'注册成功，已登录':'登录成功');
  const pending=state.pendingFavorite;state.pendingFavorite=null;
  const next=authDestination();
  if(next==='/admin'||next.startsWith('/admin/'))location.assign(next);
  else go(next);
  if(pending&&!next.startsWith('/admin'))await toggleIn(pending.key,pending.collection);
 }catch(e){if(err){err.textContent=e.message;err.hidden=false}else notify(e.message)}
 finally{if(button)button.disabled=false}
}
async function submitProfile(form){
 const value=String(new FormData(form).get('display_name')||'').trim(),el=$('#profile-message');
 try{
  const d=await api('/api/auth/profile',{method:'PATCH',body:JSON.stringify({display_name:value})});
  state.auth.user=d.user;notify('个人资料已更新');render();
 }catch(e){if(el){el.textContent=e.message;el.hidden=false}}
}
async function submitPassword(form){
 const data=new FormData(form),el=$('#password-message');
 try{
  await api('/api/auth/change-password',{method:'POST',body:JSON.stringify({current_password:String(data.get('current_password')||''),new_password:String(data.get('new_password')||'')})});
  form.reset();notify('密码已更新，其他设备已退出');
 }catch(e){if(el){el.textContent=e.message;el.hidden=false}}
}
async function logOut(){
 try{await api('/api/auth/logout',{method:'POST',body:'{}'})}catch(e){notify(e.message);return}
 state.auth={authenticated:false,user:null,csrf_token:''};
 state.saved=[];state.board=[];state.notesByKey={};state.folders=[];state.folderItems={};state.annotations={};state.pendingFavorite=null;
 notify('已安全退出登录');go('/');
}
async function importLegacy(){
 if(!loggedIn())return;
 const saved=Array.from(new Set(state.legacySaved||[])).filter(x=>/^(site|module):[a-z0-9][a-z0-9-]{0,110}$/.test(x)).slice(0,250);
 const board=Array.from(new Set(state.legacyBoard||[])).filter(x=>/^(site|module):[a-z0-9][a-z0-9-]{0,110}$/.test(x)).slice(0,250);
 let count=0;
 try{
  for(const [collection,keys] of [['saved',saved],['board',board]])for(const key of keys){
   await api('/api/me/library',{method:'POST',body:JSON.stringify({collection,key})});count++;
   if(collection==='board'&&state.legacyNotes?.[key])await api('/api/me/library/note',{method:'PATCH',body:JSON.stringify({key,note:String(state.legacyNotes[key]).slice(0,3000)})});
  }
  await loadLibrary();state.legacySaved=[];state.legacyBoard=[];state.legacyNotes={};
  try{localStorage.removeItem('saved');localStorage.removeItem('board');localStorage.removeItem('atlas-board-notes')}catch{}
  notify('成功导入 '+count+' 条旧版资料');render();
 }catch(e){notify('部分资料可能已导入：'+e.message);await loadLibrary();render()}
}

function folderUrl(id='',kind='',tag=''){const p=new URLSearchParams();if(id)p.set('folder',id);if(kind)p.set('kind',kind);if(tag)p.set('tag',tag);return '/collections'+(p.toString()?'?'+p:'')}
function savedDetailCard(k){
 const x=byKey(k);if(!x)return '';
 const info=cardInfo(x),kind=entityKind(x),meta=state.annotations[k]||{},tags=meta.tags||[];
 const attached=state.folders.filter(f=>(state.folderItems[f.id]||[]).includes(k)),available=state.folders.filter(f=>!attached.some(g=>g.id===f.id));
 return `<article class="library-item"><a class="library-item-image" href="${info.url}" data-link="${info.url}"><img loading="lazy" src="${img(entityImage(x))}" alt="${h(info.name)}"></a>
 <div class="library-item-body"><div class="library-item-top"><span>${{site:'WEBSITE',module:'SECTION',pattern:'PATTERN',article:'ARTICLE'}[kind]}</span><button data-action="save" data-key="${h(k)}" aria-label="移除收藏" title="移出收藏">${bookmarkIcon(true)}</button></div>
 <h3><a href="${info.url}" data-link="${info.url}">${h(info.name)}</a></h3><p>${h(info.sub)}</p>
 ${tags.length?`<div class="library-tags">${tags.map(t=>`<span># ${h(t)}</span>`).join('')}</div>`:''}
 ${attached.length?`<div class="library-folders-inline">${attached.map(f=>`<span style="--folder-color:${h(f.color)}">${h(f.name)}<button data-action="folder-remove-item" data-folderid="${h(f.id)}" data-key="${h(k)}" aria-label="从收藏夹移除">×</button></span>`).join('')}</div>`:''}
 <div class="library-item-controls">${available.length?`<label>加入收藏夹 <select data-folder-add="${h(k)}"><option value="">选择收藏夹</option>${available.map(f=>`<option value="${h(f.id)}">${h(f.name)}</option>`).join('')}</select></label>`:'<a href="/collections" data-link="/collections">管理收藏夹 ↗</a>'}
 <details><summary>笔记与标签 ${meta.note?'●':''}</summary><form class="library-annotation-form" data-key="${h(k)}"><label>研究笔记<textarea name="note" maxlength="3000" rows="3" placeholder="有什么值得借鉴的设计？">${h(meta.note||'')}</textarea></label><label>标签（用逗号分隔）<input name="tags" maxlength="250" value="${h(tags.join('，'))}" placeholder="首屏，视觉设计，RFQ"></label><button type="submit">保存笔记 ↗</button></form></details></div></div></article>`;
}
function collectionsView(){
 if(!loggedIn())return accountPrompt('登录后可查看并管理你的个人收藏，收藏内容不会公开。');
 const p=new URLSearchParams(location.search),folder=state.folders.find(f=>f.id===p.get('folder')),kind=['site','module','pattern','article'].includes(p.get('kind'))?p.get('kind'):'',tag=p.get('tag')||'';
 const all=(folder?state.folderItems[folder.id]||[]:state.saved).filter(k=>state.saved.includes(k));
 const items=all.filter(k=>(!kind||k.startsWith(kind+':'))&&(!tag||(state.annotations[k]?.tags||[]).includes(tag))).filter(k=>byKey(k));
 const types=[['全部',''],['Websites','site'],['Sections','module'],['Patterns','pattern'],['Insights','article']];
 const tabs=types.map(([t,v])=>`<a href="${folderUrl(folder?.id||'',v,tag)}" data-link="${folderUrl(folder?.id||'',v,tag)}" class="${kind===v?'active':''}">${t} <small>${all.filter(k=>!v||k.startsWith(v+':')).length}</small></a>`).join('');
 const tags=Array.from(new Set(Object.values(state.annotations).flatMap(x=>x.tags||[]))).slice(0,16);
 return `<div class="shell library-page"><header class="library-page-head"><div><span class="eyebrow">MY REFERENCES / PERSONAL COLLECTIONS</span><h1>我的收藏空间<span>.</span></h1><p>集中收藏、分组管理，并给每条参考添加自己的笔记和标签。</p></div><button class="quiet-button" data-action="export-personal">导出个人数据 ↓</button></header>
 <div class="library-stats"><span><b>${state.saved.length}</b> 所有收藏</span><span><b>${state.folders.length}</b> 收藏夹</span><span><b>${Object.keys(state.annotations).length}</b> 研究笔记与标签</span><a href="/account" data-link="/account">个人中心 ↗</a></div>
 <div class="library-columns"><aside class="library-sidebar"><h2>我的收藏夹</h2><nav aria-label="个人收藏夹"><a href="/collections" data-link="/collections" class="${!folder?'active':''}">▦ 全部收藏 <small>${state.saved.length}</small></a>${state.folders.map(f=>`<a href="${folderUrl(f.id)}" data-link="${folderUrl(f.id)}" class="${folder?.id===f.id?'active':''}"><span style="color:${h(f.color)}">●</span>${h(f.name)} <small>${f.item_count||0}</small></a>`).join('')}</nav>
 <form id="folder-create-form" class="library-create"><strong>新建收藏夹</strong><input name="name" required maxlength="50" placeholder="例如：工业官网改版"><div><input type="color" name="color" value="#315BE8" aria-label="收藏夹颜色"><button type="submit">创建收藏夹 +</button></div></form><p>每个账户最多 40 个收藏夹。</p><a href="/board" data-link="/board" class="library-board-link">进入研究工作台 ↗</a></aside>
 <section class="library-content"><div class="library-content-head"><div><span class="eyebrow">${folder?'PROJECT COLLECTION':'ALL SAVED RESOURCES'}</span><h2>${h(folder?.name||'全部收藏')}</h2><p>${folder?'按项目管理这一组设计参考':'Websites、Sections、Patterns、Insights 统一管理'}</p></div><b>${items.length} REFERENCES</b></div>
 ${folder?`<form id="folder-edit-form" data-folderid="${h(folder.id)}" class="library-edit"><input name="name" required maxlength="50" value="${h(folder.name)}" aria-label="收藏夹名称"><input name="color" type="color" value="${h(folder.color)}" aria-label="收藏夹颜色"><button type="submit">保存名称</button><button type="button" data-action="folder-delete" data-folderid="${h(folder.id)}">删除收藏夹</button></form>`:''}
 <nav class="library-kind-nav" aria-label="收藏类型">${tabs}</nav>
 ${tags.length?`<nav class="library-tag-nav" aria-label="标签筛选"><span>标签</span><a href="${folderUrl(folder?.id||'',kind)}" data-link="${folderUrl(folder?.id||'',kind)}" class="${!tag?'active':''}">全部</a>${tags.map(t=>`<a href="${folderUrl(folder?.id||'',kind,t)}" data-link="${folderUrl(folder?.id||'',kind,t)}" class="${tag===t?'active':''}"># ${h(t)}</a>`).join('')}</nav>`:''}
 ${items.length?`<div class="library-items">${items.map(savedDetailCard).join('')}</div>`:`<div class="account-empty"><h3>这里还没有收藏</h3><p>先去探索 B2B 网站、页面模块、设计模式或资讯文章，点击书签保存后即可整理。</p><a href="/websites" data-link="/websites" class="primary-button">探索资源 ↗</a></div>`}
 </section></div></div>`;
}
async function saveFolder(form,editing=false){
 const fields=new FormData(form),name=String(fields.get('name')||'').trim(),color=String(fields.get('color')||'#315BE8');
 if(!name){notify('请输入收藏夹名称');return}
 try{const obj=await api(editing?'/api/me/folders/'+form.dataset.folderid:'/api/me/folders',{method:editing?'PATCH':'POST',body:JSON.stringify({name,color})});await loadLibrary();notify('收藏夹已保存');if(editing)render();else go(folderUrl(obj.id))}
 catch(e){notify(e.message)}
}
async function folderDelete(id){
 const f=state.folders.find(x=>x.id===id);if(!f||!window.confirm('确定删除「'+f.name+'」？原始收藏仍会保留。'))return;
 try{await api('/api/me/folders/'+id,{method:'DELETE'});await loadLibrary();notify('收藏夹已删除，原收藏不变');go('/collections')}catch(e){notify(e.message)}
}
async function folderAssign(id,k){
 if(!id)return;
 try{await api('/api/me/folders/'+id+'/items',{method:'POST',body:JSON.stringify({key:k})});await loadLibrary();notify('已加入收藏夹');render()}catch(e){notify(e.message)}
}
async function folderRemove(id,k){
 const [kind,slug]=String(k).split(':');
 try{await api('/api/me/folders/'+id+'/items/'+kind+'/'+slug,{method:'DELETE'});await loadLibrary();notify('已移出该收藏夹');render()}catch(e){notify(e.message)}
}
async function annotationSave(form){
 const fields=new FormData(form),key=form.dataset.key,note=String(fields.get('note')||'').trim(),tags=String(fields.get('tags')||'').split(/[,，、]/).map(t=>t.trim()).filter(Boolean).slice(0,10);
 try{await api('/api/me/library/annotation',{method:'PATCH',body:JSON.stringify({key,note,tags})});await loadLibrary();notify('研究笔记已保存')}catch(e){notify(e.message)}
}
async function personalExport(){
 if(!loggedIn())return;
 try{const d=await api('/api/me/export');const url=URL.createObjectURL(new Blob([JSON.stringify(d,null,2)],{type:'application/json'})),a=document.createElement('a');a.href=url;a.download='b2b-atlas-personal-'+new Date().toISOString().slice(0,10)+'.json';document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1500);notify('个人数据已导出')}catch(e){notify(e.message)}
}
function compareSelection(){const p=new URLSearchParams(location.search),savedId=p.get('saved');if(savedId){const item=state.comparisons.find(x=>x.id===savedId);return item?(item.site_ids||[]).filter(id=>site(id)).slice(0,4):[]}const raw=p.get('sites'),ids=raw?raw.split(','):state.compare;return Array.from(new Set((ids||[]).filter(id=>/^[a-z0-9][a-z0-9-]{0,110}$/.test(id)&&site(id)))).slice(0,4)}
function compareHref(ids){return '/compare?sites='+ids.map(encodeURIComponent).join(',')}
function toggleCompare(id){if(!site(id))return;const current=location.pathname==='/compare'?compareSelection():state.compare.filter(x=>site(x));let next=current.slice();if(next.includes(id))next=next.filter(x=>x!==id);else if(next.length>=4){notify('一次最多对比 4 个网站');return}else next.push(id);state.compare=next;store('atlas-compare',next);if(location.pathname==='/compare')go(compareHref(next));else render()}
function clearCompare(){state.compare=[];store('atlas-compare',[]);if(location.pathname==='/compare')go('/websites');else render()}
function renderCompareTray(){const root=$('#compare-tray-root');if(!root)return;const ids=(state.compare||[]).filter(id=>site(id)).slice(0,4);root.innerHTML=ids.length?`<aside class="compare-tray" aria-label="网站对比清单"><div><strong>网站对比</strong><span>${ids.length} / 4 已选择 · ${ids.map(id=>h(site(id).name)).join('、')}</span></div><button data-action="compare-clear" class="compare-tray-clear">清空</button><a class="compare-tray-go" href="${compareHref(ids)}" data-link="${compareHref(ids)}" ${ids.length<2?'aria-disabled="true"':''}>${ids.length<2?'再选 1 个':'开始对比'} ↗</a></aside>`:'';const link=root.querySelector('.compare-tray-go');if(link&&ids.length<2){link.removeAttribute('data-link');link.href='#';link.addEventListener('click',ev=>{ev.preventDefault();notify('至少选择 2 个网站，最多 4 个')})}}
function compareCellText(value){return value?`<p>${h(value)}</p>`:'<span class="compare-unrecorded">尚未记录</span>'}
function compareList(items){return items&&items.length?`<ul class="compare-bullets">${items.map(x=>`<li>${h(x)}</li>`).join('')}</ul>`:'<span class="compare-unrecorded">尚未记录</span>'}
function compareView(){
 const params=new URLSearchParams(location.search),savedId=params.get('saved'),savedItem=state.comparisons.find(x=>x.id===savedId),ids=compareSelection(),items=ids.map(site).filter(Boolean);
 if(savedId&&!savedItem&&!loggedIn())return accountPrompt('登录后可查看你保存的网站对比。');
 if(items.length<2)return `<div class="shell compare-page"><div class="compare-intro"><span class="eyebrow">WEBSITE COMPARISON / RESEARCH</span><h1>把好设计，<br>放在一起研究。</h1><p>从真实网站出发，比较品牌定位、视觉语言、信息架构、信任背书和转化路径。选择 2–4 个网站即可开始。</p><a href="/websites" data-link="/websites" class="primary-button">选择网站开始对比 ↗</a></div><div class="compare-empty-state"><strong>02—04</strong><span>WEBSITES SIDE BY SIDE</span><p>在 Websites 卡片或网站详情中点击 ⇄，把案例加入对比清单。</p><a href="/websites" data-link="/websites">浏览全部网站案例 ↗</a></div></div>`;
 const modulesFor=s=>state.modules.filter(m=>m.site_id===s.id),profile=s=>state.profiles[s.id]||null;
 const breakdown=(s,pattern)=>{const p=profile(s);return (p?.breakdown||[]).find(x=>pattern.test(x[0]||''))};
 const palette=s=>{const p=profile(s),extracted=pal(s).slice(0,5),css=p?.colors||[];return `<div class="compare-palette-block"><span>截图提取色</span><div class="compare-swatches">${extracted.length?extracted.map(c=>`<span title="${safeHex(c)}" style="--swatch:${safeHex(c)}"></span>`).join(''):'<i>未生成</i>'}</div><small>来自当前截图，不代表官方品牌色</small>${css.length?`<span>页面 CSS 色值</span><div class="compare-css-colors">${css.map(([c,n])=>`<div><i style="--swatch:${safeHex(c)}"></i><span><b>${safeHex(c)}</b><small>${h(n)}</small></span></div>`).join('')}</div><small>来自已检查页面样式声明</small>`:''}</div>`};
 const structure=s=>{const p=profile(s),mods=modulesFor(s);if(p?.structure?.length)return `<ol class="compare-structure">${p.structure.map(([a,b])=>`<li><b>${h(a)}</b><span>${h(b)}</span></li>`).join('')}</ol>`;return mods.length?`<ol class="compare-structure">${mods.map(m=>`<li><b>${h(m.category||m.title)}</b><span>${h(m.title)}</span></li>`).join('')}</ol>`:'<span class="compare-unrecorded">暂无已收录页面模块</span>'};
 const evidence=s=>{const p=profile(s);return p?.sources?.length?`<div class="compare-sources">${p.sources.map(([name,url])=>`<a href="${h(url)}" target="_blank" rel="noopener noreferrer">${h(name)} ↗</a>`).join('')}</div><small>研究检查日期：${h(p.checked||'未记录')}</small>`:`<a href="${h(s.url)}" target="_blank" rel="noopener noreferrer">访问官网 ↗</a><small>当前为基础案例资料，尚无完整研究档案</small>`};
 const rows=[
  {n:'01',title:'业务定位',hint:'行业、产品与目标受众',value:s=>{const p=profile(s);return `<dl class="compare-facts"><dt>业务方向</dt><dd>${compareCellText(s.focus)}</dd><dt>产品 / 商业模式</dt><dd>${compareCellText(s.model)}</dd><dt>网站类型</dt><dd>${compareCellText(p?.type)}</dd><dt>目标受众</dt><dd>${compareCellText(p?.audience)}</dd><dt>地区</dt><dd>${compareCellText(p?.country)}</dd></dl>`}},
  {n:'02',title:'视觉语言',hint:'风格、画面与视觉重点',value:s=>{const p=profile(s);return `<strong class="compare-style">${h(s.visual_style||'未记录')}</strong>${p?.style?.length?compareList(p.style):''}${compareList(s.design_strengths||[])}`}},
  {n:'03',title:'色彩系统',hint:'区分截图取色与已观察 CSS 色值',value:palette},
  {n:'04',title:'信息架构',hint:'首页叙事顺序与已收录模块',value:structure},
  {n:'05',title:'信任背书',hint:'案例、数据、客户与技术证据',value:s=>{const b=breakdown(s,/trust|credibility|信任/i);return b?`<b>${h(b[0])}</b><p>${h(b[1])}</p><small>${h(b[2]||'')}</small>`:'<span class="compare-unrecorded">尚无已核实的信任背书分析</span>'}},
  {n:'06',title:'转化路径',hint:'CTA、询盘与自助入口',value:s=>{const b=breakdown(s,/conversion|转化/i);return b?`<b>${h(b[0])}</b><p>${h(b[1])}</p><small>${h(b[2]||'')}</small>`:'<span class="compare-unrecorded">尚无已核实的转化路径分析</span>'}},
  {n:'07',title:'关联设计模式',hint:'从网站案例连接到可复用方法',value:s=>{const p=profile(s),patterns=(p?.patterns||[]).map(pattern).filter(Boolean);return patterns.length?`<div class="compare-related-patterns">${patterns.map(x=>`<a href="/patterns/${h(x.id)}" data-link="/patterns/${h(x.id)}">${h(x.title)} ↗</a>`).join('')}</div>`:'<span class="compare-unrecorded">暂无已关联的深度研究模式</span>'}},
  {n:'08',title:'研究证据',hint:'原始来源与资料完整度',value:evidence}
 ];
 const title=savedItem?.name||items.map(x=>x.name).join(' × ');
 return `<div class="shell compare-page"><header class="compare-page-head"><div><span class="eyebrow">WEBSITE COMPARISON / RESEARCH MATRIX</span><h1>网站横向对比<span>.</span></h1><p>对比的是已收录的证据，不是未经验证的评分。缺少资料的维度会明确标注。</p></div><div class="compare-head-count"><strong>${items.length}</strong><span>个网站 · 2–4 个为一组</span></div></header>
 <div class="compare-toolbar"><a href="/websites" data-link="/websites">← 继续选择网站</a><div><button class="quiet-button" data-action="comparison-export">导出对比报告 ↓</button><button class="quiet-button" data-action="compare-clear">清空本次选择</button></div></div>
 <div class="compare-matrix" style="--compare-count:${items.length}"><div class="compare-site-head"><div class="compare-axis-label"><span>COMPARE</span><b>比较维度</b><small>横向观察，不做主观排名</small></div>${items.map((s,i)=>`<article class="compare-site-heading"><a href="${pathSite(s)}" data-link="${pathSite(s)}" class="compare-site-shot"><img src="${img(s.screenshot_url)}" alt="${h(s.name)} 网站截图"></a><div class="compare-site-title"><span>0${i+1} / ${h(s.sector)}</span><h2><a href="${pathSite(s)}" data-link="${pathSite(s)}">${h(s.name)}</a></h2><p>${h(s.summary||s.focus||'')}</p><div><a href="${h(s.url)}" target="_blank" rel="noopener noreferrer">官网 ↗</a><button data-action="compare-toggle" data-site-id="${h(s.id)}">移出对比 ×</button></div></div></article>`).join('')}</div>
 ${rows.map(row=>`<section class="compare-row"><div class="compare-row-label"><span>${row.n}</span><b>${row.title}</b><small>${row.hint}</small></div><div class="compare-row-cells">${items.map(s=>`<article class="compare-cell"><span class="compare-cell-site-label">${h(s.name)}</span>${row.value(s)}</article>`).join('')}</div></section>`).join('')}</div>
 <section class="compare-save-panel"><div><span class="eyebrow">SAVE TO RESEARCH WORKSPACE</span><h2>${savedItem?'更新已保存的对比':'把这组对比留在研究工作台'}</h2><p>保存网站组合，之后可从研究工作台继续打开、修改和导出。</p></div><div class="compare-save-controls"><label>对比名称<input id="compare-name" maxlength="64" value="${h(title)}" placeholder="例如：工业自动化网站首屏对比"></label><button class="primary-button" data-action="${savedItem?'comparison-update':'comparison-save'}" ${savedItem?`data-id="${h(savedItem.id)}"`:''}>${savedItem?'更新对比':'保存到研究工作台'} ↗</button></div></section>
 </div>`;
}
async function saveComparison(id=''){
 const ids=compareSelection();if(ids.length<2){notify('至少选择 2 个网站才能保存对比');return}
 if(!loggedIn()){go('/login?next='+encodeURIComponent(location.pathname+location.search));return}
 const name=String($('#compare-name')?.value||ids.map(x=>site(x)?.name).filter(Boolean).join(' × ')).trim();
 if(!name){notify('请填写对比名称');return}
 try{const payload={name,site_ids:ids},savedId=id||new URLSearchParams(location.search).get('saved');const data=await api('/api/me/comparisons'+(savedId?'/'+savedId:''),{method:savedId?'PATCH':'POST',body:JSON.stringify(payload)});await loadLibrary();notify('对比组合已保存到研究工作台');go('/compare?saved='+encodeURIComponent(data.id))}
 catch(e){notify(e.message)}
}
async function deleteComparison(id){
 if(!id||!window.confirm('删除这组已保存的网站对比？不会删除原始网站收藏。'))return;
 try{await api('/api/me/comparisons/'+id,{method:'DELETE'});await loadLibrary();notify('对比记录已删除');if(new URLSearchParams(location.search).get('saved')===id)go('/board');else render()}
 catch(e){notify(e.message)}
}
function exportComparison(){
 const ids=compareSelection(),items=ids.map(site).filter(Boolean);if(items.length<2){notify('至少选择 2 个网站');return}
 const lines=['# B2B Atlas · 网站横向对比','',...items.map((s,i)=>{const p=state.profiles[s.id];return `## ${i+1}. ${s.name}\n\n- 官网：${s.url}\n- 行业：${s.sector||'未记录'}\n- 业务方向：${s.focus||'未记录'}\n- 视觉风格：${s.visual_style||'未记录'}\n- 深度研究：${p?.checked||'暂无完整研究档案'}\n\n### 视觉特点\n${(s.design_strengths||[]).map(x=>'- '+x).join('\n')||'- 未记录'}\n\n### 结构与转化\n${(p?.breakdown||[]).map(x=>`- ${x[0]}：${x[1]}`).join('\n')||'- 尚无完整研究资料'}`})];
 const a=document.createElement('a'),u=URL.createObjectURL(new Blob([lines.join('\n\n')],{type:'text/markdown;charset=utf-8'}));a.href=u;a.download='b2b-atlas-website-comparison.md';a.click();setTimeout(()=>URL.revokeObjectURL(u),2000);notify('对比报告已导出');
}
function boardView(){
 if(!loggedIn())return accountPrompt('研究板是账户专属空间。登录后可以整理案例、填写笔记并导出。');
 const items=state.board.map(byKey).filter(Boolean),comparisons=state.comparisons||[];
 const savedComparisons=comparisons.length?`<section class="board-comparisons"><div class="section-heading"><div><span class="eyebrow">SAVED COMPARISONS</span><h2>已保存的网站对比</h2><p>重新打开、调整网站组合，或导出对比报告。</p></div><span>${comparisons.length} 组</span></div><div class="board-comparison-list">${comparisons.map(c=>`<article><a href="/compare?saved=${encodeURIComponent(c.id)}" data-link="/compare?saved=${encodeURIComponent(c.id)}"><strong>${h(c.name)}</strong><span>${(c.site_ids||[]).map(id=>h(site(id)?.name||id)).join(' × ')}</span><small>${(c.site_ids||[]).length} 个网站 · 更新于 ${h((c.updated_at||'').slice(0,10))}</small></a><button data-action="comparison-delete" data-id="${h(c.id)}" aria-label="删除对比记录">×</button></article>`).join('')}</div></section>`:`<section class="board-comparisons board-comparisons-empty"><div><span class="eyebrow">SAVED COMPARISONS</span><h2>网站对比记录</h2><p>在 Websites 选择 2–4 个网站，比较后即可保存到这里。</p><a href="/websites" data-link="/websites">选择网站开始对比 ↗</a></div></section>`;
 return `<div class="shell utility-page">${topHeading('WORKSPACE','我的研究板','将设计参考整理为项目研究资料，笔记会保存到你的账号。')}${savedComparisons}<div class="board-tools"><span>${items.length} 个研究参考</span><button data-action="export-board" class="primary-button" ${!items.length?'disabled':''}>导出 Markdown ↗</button></div>${items.length?`<div class="board-grid">${items.map(x=>`<article class="board-item"><div class="board-image"><a href="${cardInfo(x).url}" data-link="${cardInfo(x).url}"><img loading="lazy" src="${img(entityImage(x))}" alt="${h(cardInfo(x).name)}"></a></div><div class="board-heading"><a href="${cardInfo(x).url}" data-link="${cardInfo(x).url}">${h(cardInfo(x).name)}</a><button data-action="board" data-key="${h(key(x))}" aria-label="从研究板移除">×</button></div><p>${h(cardInfo(x).sub)}</p><label>研究笔记<textarea data-note="${h(key(x))}" placeholder="这条参考对项目有什么价值？">${h(state.notesByKey[key(x)]||'')}</textarea></label></article>`).join('')}</div>`:`<div class="account-empty"><h2>研究板还是空的</h2><p>打开案例详情，选择“研究工作台”即可加入。</p><a href="/websites" data-link="/websites" class="primary-button">探索网站 ↗</a></div>`}</div>`;
}

function notFound(){
 const menu=[['Websites','精选 B2B 网站与产品案例','/websites','01'],['Sections','真实网页的局部设计参考','/sections','02'],['Patterns','设计模式与解决方法','/patterns','03'],['Insights','设计研究和原创文章','/insights','04']];
 return `<div class="missing-landing"><div class="shell">
   <nav class="missing-breadcrumb" aria-label="当前位置"><a href="/" data-link="/">B2B Atlas</a><span aria-hidden="true">/</span><span>404 · Page not found</span></nav>
   <section class="missing-stage" aria-labelledby="missing-title">
    <div class="missing-left"><div class="missing-small"><span class="missing-small-dot"></span> ERROR 404 <span class="missing-small-line"></span> LOST REFERENCE</div>
      <div class="missing-number" aria-hidden="true">404<span class="missing-number-dot">.</span></div>
      <h1 id="missing-title">页面走丢了，<br>灵感还在这里。</h1>
      <p>这个链接可能已经更改、被移除，或者地址输入有误。<br>没关系，你可以回到资源库，继续发现值得研究的好设计。</p>
      <div class="missing-actions"><a href="/" data-link="/" class="access-primary">返回首页 <span aria-hidden="true">↗</span></a><button data-action="global-search" class="access-secondary" type="button"><span aria-hidden="true">⌕</span> 搜索资源</button></div>
    </div>
    <div class="missing-art" aria-hidden="true">
      <div class="missing-art-top"><span>ATLAS / DIRECTORY</span><span>↗</span></div>
      <div class="missing-art-inner"><div class="missing-art-icon"><svg viewBox="0 0 72 72" fill="none"><rect x="11" y="9" width="50" height="54" rx="9" stroke="currentColor" stroke-width="2"/><path d="M23 24h26M23 34h18M23 44h10" stroke="currentColor" stroke-width="2" stroke-linecap="round"/><circle cx="52" cy="49" r="12" fill="#f3f7ff" stroke="#1a4ff3" stroke-width="2"/><path d="m47 44 10 10m0-10L47 54" stroke="#1a4ff3" stroke-width="2" stroke-linecap="round"/></svg></div>
        <div class="missing-art-code">NO MATCH FOUND</div><div class="missing-art-bars"><i></i><i></i><i></i></div><div class="missing-art-pill">REFERENCE NOT AVAILABLE <span>×</span></div>
      </div><div class="missing-art-bottom"><span>INDEX STATUS</span><span>404 / UNKNOWN</span></div>
    </div>
   </section>
   <section class="missing-explore" aria-label="继续探索"><div class="missing-explore-head"><div><span class="eyebrow">BACK TO EXPLORATION</span><h2>换个入口，继续探索。</h2></div><span>04 / LIBRARY ENTRIES</span></div><div class="missing-links">${menu.map(([title,subtitle,url,num])=>`<a href="${url}" data-link="${url}" class="missing-link"><span class="missing-link-index">${num}</span><span class="missing-link-copy"><strong>${title}</strong><small>${subtitle}</small></span><span class="missing-link-arrow" aria-hidden="true">↗</span></a>`).join('')}</div></section>
 </div></div>`;
}
function refreshSeo(section,parts,isMissing){
 const labels={home:['B2B Atlas · 视觉设计研究库','工业、科技和企业产品的高质量 B2B 网站、页面模块和设计研究。'],websites:['Websites · B2B 网站灵感库','真实 B2B 网站案例，探索设计风格、页面结构和转化方式。'],sections:['Sections · 页面模块库','真实的 B2B 网站页面模块，研究首屏、产品、证据和询盘设计。'],patterns:['Patterns · 设计模式库','了解可复用的 B2B 用户体验设计方法。'],insights:['Insights · 资讯与研究','B2B 网站研究、设计方法、视觉系统与转化策略。']};
 let title=labels[section]?.[0]||'B2B Atlas',description=labels[section]?.[1]||'B2B 网站设计研究库。';
 const id=parts[1];
 if(isMissing){title='404 · 页面未找到';description='该页面不存在或已经移动。返回 B2B Atlas 探索设计参考。'}
 else if(section==='websites'&&id&&site(id)){const x=site(id);title=x.name+' · 网站设计研究';description=x.summary||x.focus||description}
 else if(section==='sections'&&id&&moduleBy(id)){const x=moduleBy(id);title=x.title+' · 页面模块';description=x.lesson||x.summary||description}
 else if(section==='patterns'&&id&&pattern(id)){const x=pattern(id);title=x.title+' · 设计模式';description=x.question||description}
 else if(section==='insights'&&id&&articleBy(id)){const x=articleBy(id);title=x.title;description=x.subtitle||description}
 else if(['account','board','collections','discover','login','register','forgot-password','reset-password','compare'].includes(section)){title=({account:'个人中心',board:'研究工作台',collections:'我的收藏',discover:'我的收藏',login:'登录',register:'注册','forgot-password':'找回密码','reset-password':'重置密码',compare:'网站对比'})[section];description='B2B Atlas 个人资料与研究空间。'}
 document.title=title+' · B2B Atlas';
 const desc=document.querySelector('meta[name="description"]');if(desc)desc.content=description;
 const isPrivate=isMissing||['account','board','collections','discover','login','register','forgot-password','reset-password','compare'].includes(section);
 let robots=document.querySelector('meta[name="robots"]');if(!robots){robots=document.createElement('meta');robots.name='robots';document.head.appendChild(robots)}robots.content=isPrivate?'noindex, follow':'index, follow';
 let canonical=document.querySelector('link[rel="canonical"]');if(!canonical){canonical=document.createElement('link');canonical.rel='canonical';document.head.appendChild(canonical)}
 canonical.href=location.origin+location.pathname;
 for(const [property,value] of [['og:title',document.title],['og:description',description],['og:url',canonical.href]]){
  let meta=document.querySelector('meta[property="'+property+'"]');if(!meta){meta=document.createElement('meta');meta.setAttribute('property',property);document.head.appendChild(meta)}meta.content=value;
 }
 let schema=document.getElementById('atlas-seo-schema');if(schema)schema.remove();
 if(!isMissing&&section==='insights'&&id&&articleBy(id)){
  const a=articleBy(id);schema=document.createElement('script');schema.id='atlas-seo-schema';schema.type='application/ld+json';
  schema.textContent=JSON.stringify({'@context':'https://schema.org','@type':'Article',headline:a.title,description:a.subtitle,datePublished:a.published_at,author:{'@type':'Organization',name:'B2B Atlas 编辑部'},mainEntityOfPage:canonical.href}).replace(/</g,'\\u003c');
  document.head.appendChild(schema);
 }
}
function render(){decodeFilters();const parts=location.pathname.split('/').filter(Boolean),section=parts[0]||'home';let html;if(section==='home')html=homeView();else if(section==='websites'&&!parts[1])html=listView('websites');else if(section==='sections'&&!parts[1])html=listView('sections');else if(section==='patterns'&&!parts[1])html=patternsView();else if(section==='insights'&&!parts[1])html=insightsIndex();else if(section==='insights'&&parts.length===2){let a=articleBy(parts[1]);html=a?insightArticle(a):notFound();}else if(section==='websites'&&parts.length===2){let s=site(parts[1]);html=s?detailView(s):notFound()}else if(section==='sections'&&parts.length===2){let m=moduleBy(parts[1]);html=m&&site(m.site_id)?detailView(site(m.site_id),m):notFound()}else if(section==='patterns'&&parts.length===2){let p=pattern(parts[1]);html=p?patternDetail(p):notFound()}else if(section==='compare'&&parts.length===1)html=compareView();else if(section==='forgot-password'&&parts.length===1)html=recoveryView(false);else if(section==='reset-password'&&parts.length===1)html=recoveryView(true);else if(section==='account'&&parts.length===1)html=accountView();else if(section==='login'&&parts.length===1)html=authView(false);else if(section==='register'&&parts.length===1)html=authView(true);else if(section==='board'&&parts.length===1)html=boardView();else if((section==='collections'||section==='discover')&&parts.length===1)html=collectionsView();else html=notFound();const isMissing=html.includes('class="missing-landing"');app.innerHTML=html;document.title=isMissing?'404 · 页面未找到 · B2B Atlas':section==='account'?'个人中心 · B2B Atlas':section==='login'?'登录 · B2B Atlas':section==='register'?'注册 · B2B Atlas':section==='insights'&&parts[1]?(articleBy(parts[1])?.title||'文章')+' · B2B Atlas':(section==='insights'?'资讯与研究':section==='home'?'Discover':titleCase(section))+' · B2B Atlas';let robots=$('meta[name="robots"]');if(!robots){robots=document.createElement('meta');robots.name='robots';document.head.appendChild(robots)}robots.content=isMissing?'noindex, follow':'index, follow';const desc=$('meta[name="description"]');if(desc)desc.content=isMissing?'页面不存在或已被移动。继续探索 B2B Atlas 的 B2B Websites、Sections、Patterns 和 Insights。':section==='insights'&&parts[1]?(articleBy(parts[1])?.subtitle||'B2B Atlas 设计研究'):section==='insights'?'B2B Atlas 资讯与研究：B2B 网站案例、设计方法、视觉系统与转化策略。':'A visual research library of B2B websites, sections and design patterns.';refreshSeo(section,parts,isMissing);$$('.desktop-nav a').forEach(x=>x.classList.toggle('active',x.dataset.nav===section));$('#saved-count').hidden=!loggedIn()||!state.saved.length;$('#saved-count').textContent=state.saved.length;const acc=$('.account-nav');if(acc){acc.classList.toggle('is-logged-in',loggedIn());acc.title=loggedIn()?'个人中心 · '+state.auth.user.display_name:'登录 / 注册';}$('#mobile-menu').hidden=true;if(section==='websites'&&!parts[1]||section==='sections'&&!parts[1])renderResults();if(section==='insights'&&!parts[1])renderInsightResults()}
function updateListing(k,v){if(k==='q'){state.q=v;setQuery('q',v)}else{state[k]=v;setQuery(k,v)}if(k==='category'||k==='sector'){const target=k==='category'?'category':'sector';$$('.category-nav [data-action="category"]').forEach(x=>x.classList.toggle('active',x.dataset.value===v));let sel=$('.listing-controls [data-field="'+target+'"]');if(sel)sel.value=v}if(k==='density')$$('[data-action=density]').forEach(b=>b.classList.toggle('active',b.dataset.value===v));renderResults()}
function showOverlay(markup){overlay.hidden=false;overlay.innerHTML='<div class="overlay-backdrop" data-action="close-overlay"></div><div class="overlay-body" role="dialog" aria-modal="true">'+markup+'<button class="modal-close" data-action="close-overlay" aria-label="Close">×</button></div>';document.body.classList.add('modal-open')}
function closeOverlay(){overlay.hidden=true;overlay.innerHTML='';document.body.classList.remove('modal-open')}
function quickPreview(k){let x=byKey(k);if(!x)return;let info=cardInfo(x);showOverlay('<div class="preview-modal"><img src="'+img(x.screenshot_url)+'" alt="'+h(info.name)+'"><div><span class="eyebrow">QUICK REFERENCE</span><h2>'+h(info.name)+'</h2><p>'+h(info.sub)+'</p><p>'+h(x.summary||x.lesson||x.focus||'')+'</p><a class="primary-button" href="'+info.url+'" data-link="'+info.url+'">Open research profile ↗</a></div></div>')}
function expandImage(){let x=currentScreens[currentScreen];if(!x)return;showOverlay('<div class="image-modal"><img src="'+img(x.url)+'" alt="'+h(x.label)+' screenshot"><div><strong>'+h(x.label)+'</strong><span>'+(currentScreen+1)+' / '+currentScreens.length+'</span><a href="'+h(x.source)+'" target="_blank" rel="noopener noreferrer">Original source ↗</a></div></div>')}
function globalSearch(){showOverlay('<div class="search-modal"><h2>Search the library</h2><input id="global-search" type="search" placeholder="Company, industry, pattern, section…" aria-label="Search all references" autofocus><div id="global-matches"></div></div>');setTimeout(()=>$('#global-search')?.focus(),50)}
function renderGlobalMatches(q){const target=$('#global-matches');if(!target)return;q=(q||'').toLowerCase().trim();if(!q){target.innerHTML='<p>Try “aerospace”, “manufacturing” or “product hero”.</p>';return}let a=state.sites.filter(s=>[s.name,s.sector,s.focus,s.summary].join(' ').toLowerCase().includes(q)).slice(0,5).map(s=>({label:s.name,sub:s.sector,url:pathSite(s)}));let b=state.modules.filter(m=>[m.title,m.category,m.lesson].join(' ').toLowerCase().includes(q)).slice(0,3).map(m=>({label:m.title,sub:'Section',url:pathModule(m)}));let c=state.patterns.filter(p=>[p.title,p.family,p.question].join(' ').toLowerCase().includes(q)).slice(0,3).map(p=>({label:p.title,sub:'Pattern',url:'/patterns/'+p.id}));let d=state.articles.filter(a=>[a.title,a.subtitle,...a.tags].join(' ').toLowerCase().includes(q)).slice(0,3).map(a=>({label:a.title,sub:'资讯文章',url:articleLink(a)}));target.innerHTML=[...a,...b,...c,...d].map(x=>'<a href="'+x.url+'" data-link="'+x.url+'"><strong>'+h(x.label)+'</strong><small>'+h(x.sub)+'</small></a>').join('')||'<p>No matches. Try another keyword.</p>'}
async function toggleIn(k,collection){
 if(!loggedIn()){
  state.pendingFavorite={key:k,collection};
  notify('请登录后使用收藏或研究板');
  go('/login?next='+encodeURIComponent(location.pathname+location.search));return;
 }
 const arr=state[collection],on=arr.includes(k);
 if(!/^(site|module|pattern|article):[a-z0-9][a-z0-9-]{0,110}$/.test(k))return;
 const [kind,slug]=k.split(':');
 try{
  if(on)await api('/api/me/library/'+collection+'/'+kind+'/'+slug,{method:'DELETE'});
  else await api('/api/me/library',{method:'POST',body:JSON.stringify({collection,key:k})});
  await loadLibrary();
  notify(on?'已移除':'已保存到个人账号');render();
 }catch(e){
  if(e.status===401){state.auth={authenticated:false,user:null,csrf_token:''};state.pendingFavorite={key:k,collection};go('/login?next='+encodeURIComponent(location.pathname+location.search))}
  else notify(e.message);
 }
}
function exportBoard(){if(!state.board.length)return;let lines=['# B2B Atlas — Project reference brief','','Generated from your local design board.','','## References',''];state.board.forEach((k,i)=>{let x=byKey(k);if(!x)return;lines.push('### '+(i+1)+'. '+cardInfo(x).name,'','- Source: '+(x.url||cardInfo(x).url),'- Reference: '+cardInfo(x).sub,'- Observation: '+(x.lesson||x.takeaway||site(x.site_id)?.takeaway||''),'- Project note: '+(state.notesByKey[k]||''),'')});let a=document.createElement('a'),u=URL.createObjectURL(new Blob([lines.join('\n')],{type:'text/markdown'}));a.href=u;a.download='b2b-atlas-research.md';a.click();setTimeout(()=>URL.revokeObjectURL(u),2000);notify('Research brief exported')}
document.addEventListener('click',ev=>{
 const external=ev.target.closest('a[href]');
 if(external&&/^\/(websites|sections|patterns|insights)(\/|$)/.test(location.pathname)){
   try{const dest=new URL(external.href,location.origin);
     if(/^https?:$/.test(dest.protocol)&&dest.origin!==location.origin)
       growthSend('external_click',location.pathname);
   }catch(_){}
 }
 let link=ev.target.closest('a[data-link]');if(link){
   const destination=link.dataset.link;
   if(/^\/(websites|sections|patterns|insights)\/[a-z0-9-]+$/.test(destination))
     growthSend('content_click',location.pathname,destination);
   ev.preventDefault();closeOverlay();go(destination);return
 }let target=ev.target.closest('[data-action]');if(!target)return;let a=target.dataset.action,k=target.dataset.key,v=target.dataset.value;if(a==='save')toggleIn(k,'saved');else if(a==='board')toggleIn(k,'board');else if(a==='compare-toggle')toggleCompare(target.dataset.siteId);else if(a==='compare-clear')clearCompare();else if(a==='comparison-save')saveComparison();else if(a==='comparison-update')saveComparison(target.dataset.id);else if(a==='comparison-delete')deleteComparison(target.dataset.id);else if(a==='comparison-export')exportComparison();else if(a==='preview'){growthSend('preview',location.pathname);quickPreview(k)}else if(a==='image')expandImage();else if(a==='global-search')globalSearch();else if(a==='close-overlay')closeOverlay();else if(a==='mobile-menu'){const n=$('#mobile-menu');n.hidden=!n.hidden;target.setAttribute('aria-expanded',String(!n.hidden))}else if(a==='copy'){navigator.clipboard?.writeText(v).then(()=>notify(v+' copied'),()=>notify('Copy unavailable'))}else if(a==='density')updateListing('density',v);else if(a==='category')updateListing(location.pathname.startsWith('/sections')?'category':'sector',v);else if(a==='filter-remove'){updateListing(target.dataset.field,'');$('[data-field="'+target.dataset.field+'"]').forEach(input=>input.value='')}else if(a==='reset-filters'){go(location.pathname)}else if(a==='thumb'){let n=Number(target.dataset.index);currentScreen=n;let x=currentScreens[n];if(!x)return;$('#detail-image').src=x.url;$('#detail-image').alt=x.label;$('#detail-hero').dataset.index=n;$('#capture-label').textContent=x.label;$('#capture-source').href=x.source;$$('.capture-thumbs button').forEach((b,i)=>{b.classList.toggle('selected',i===n);b.setAttribute('aria-pressed',String(i===n))})}else if(a==='anchor'){ev.preventDefault();document.getElementById(target.dataset.target)?.scrollIntoView({behavior:'smooth',block:'start'})}else if(a==='share-article'){const u=location.href;if(navigator.clipboard?.writeText){navigator.clipboard.writeText(u).then(()=>notify('文章链接已复制'),()=>notify('复制失败，请从地址栏复制'))}else notify('请从地址栏复制文章链接')}else if(a==='folder-delete')folderDelete(target.dataset.folderid);else if(a==='folder-remove-item')folderRemove(target.dataset.folderid,k);else if(a==='export-personal')personalExport();else if(a==='logout')logOut();else if(a==='import-legacy')importLegacy();else if(a==='export-board')exportBoard()});
document.addEventListener('change',ev=>{let t=ev.target;if(t.dataset.field)updateListing(t.dataset.field,t.value);if(t.dataset.folderAdd)folderAssign(t.value,t.dataset.folderAdd);if(t.id==='insights-sort'){setQuery('sort',t.value==='latest'?'':t.value);renderInsightResults()}});
document.addEventListener('input',ev=>{let t=ev.target;if(t.id==='library-search'){clearTimeout(searchTimer);searchTimer=setTimeout(()=>updateListing('q',t.value),120);analyticsSearch(t.value)}else if(t.id==='global-search'){renderGlobalMatches(t.value);analyticsSearch(t.value)}else if(t.id==='insights-search'){setQuery('q',t.value);renderInsightResults();analyticsSearch(t.value)}else if(t.dataset.note){state.notesByKey[t.dataset.note]=t.value;clearTimeout(noteTimer);noteTimer=setTimeout(async()=>{if(!loggedIn())return;try{await api('/api/me/library/note',{method:'PATCH',body:JSON.stringify({key:t.dataset.note,note:t.value})})}catch(e){notify('笔记未保存：'+e.message)}},650)}});
document.addEventListener('submit',ev=>{if(ev.target.id==='home-search'){ev.preventDefault();analyticsSearch(ev.target.elements.q.value.trim());go('/websites?q='+encodeURIComponent(ev.target.elements.q.value.trim()))}else if(ev.target.id==='auth-form'){ev.preventDefault();submitAuth(ev.target)}else if(ev.target.id==='password-request-form'||ev.target.id==='password-reset-form'){ev.preventDefault();submitRecovery(ev.target)}else if(ev.target.id==='profile-form'){ev.preventDefault();submitProfile(ev.target)}else if(ev.target.id==='password-form'){ev.preventDefault();submitPassword(ev.target)}else if(ev.target.id==='folder-create-form'){ev.preventDefault();saveFolder(ev.target)}else if(ev.target.id==='folder-edit-form'){ev.preventDefault();saveFolder(ev.target,true)}else if(ev.target.classList.contains('library-annotation-form')){ev.preventDefault();annotationSave(ev.target)}});
document.addEventListener('keydown',ev=>{if(ev.key==='Escape'){closeOverlay();$('#mobile-menu').hidden=true}else if((ev.ctrlKey||ev.metaKey)&&ev.key.toLowerCase()==='k'){ev.preventDefault();globalSearch()}else if(ev.key==='/'&&!/INPUT|TEXTAREA|SELECT/.test(document.activeElement.tagName)&&$('#library-search')){ev.preventDefault();$('#library-search').focus()}});
window.addEventListener('popstate',()=>{render();analyticsPage();window.scrollTo(0,0)});
window.addEventListener('scroll',growthScroll,{passive:true});
async function load(){try{let urls=['/api/source-library','/api/module-library','/assets/research.json','/assets/patterns.json','/assets/screenshot-palettes.json','/assets/articles.json?v=39'];let results=await Promise.all(urls.map(async(u,i)=>{let r=await fetch(u);if(!r.ok&&i<4)throw Error(u+' returned '+r.status);return r.ok?r.json():{}}));state.sites=results[0].sites||[];state.notes=results[0].notes||[];state.modules=results[1].modules||[];state.profiles=results[2]||{};state.patterns=results[3]||[];state.palettes=results[4]||{};state.articles=results[5]?.articles||[];state.articleCategories=results[5]?.categories||[];state.articleEditorialNotice=results[5]?.editorial_notice||'';await syncAuth();render();analyticsPage()}catch(err){console.error('B2B Atlas bootstrap',err);app.innerHTML='<div class="shell empty standalone"><h1>Library unavailable</h1><p>Unable to load the curated data right now. Refresh to retry.</p><button class="primary-button" onclick="location.reload()">Try again</button></div>'}}
load();
})();