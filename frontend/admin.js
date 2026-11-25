/* B2B Atlas · V46 Control Room
   Standalone, read-only operations dashboard.
   Every reported number comes from the admin/public catalog API.
   Preview never fetches private user, session or collection records. */
(() => {
  'use strict';
  const $ = (q, root=document) => root.querySelector(q);
  const $$ = (q, root=document) => Array.from(root.querySelectorAll(q));
  const icon = name => '<svg class="icon" aria-hidden="true"><use href="#i-'+name+'"></use></svg>';
  const esc = text => String(text == null ? '' : text).replace(/[&<>"']/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
  const mode = document.body.dataset.adminMode === 'admin' ? 'admin' : 'preview';
  const palette = ['var(--blue)','var(--violet)','var(--orange)','var(--teal)'];
  const typeIcons = ['globe','layers','shapes','article'];
  const typeStyles = ['website','section','pattern','insight'];
  const typeLabels = ['网站案例','页面模块','设计模式','研究文章'];
  const state = {data:null,range:14,query:'',expanded:false,fetching:false,trafficDays:30,traffic:null,trafficFetching:false,growth:null,growthChannel:'all',growthFetching:false,csrf:null};
  let toastTimer = 0;

  async function hydrateAdminIdentity(){
    if(mode!=='admin')return;
    try{
      const response=await fetch('/api/auth/me',{credentials:'same-origin',cache:'no-store'});
      const data=await response.json();
      if(!response.ok||!data.authenticated||!data.csrf_token)return;
      state.csrf=data.csrf_token;
      const button=$('#admin-logout');if(button)button.hidden=false;
    }catch(_){}
  }
  async function logoutAdmin(){
    if(mode!=='admin'||!state.csrf){toast('身份尚未验证，请刷新后重试。');return}
    const button=$('#admin-logout');button.disabled=true;
    try{
      const res=await fetch('/api/auth/logout',{method:'POST',credentials:'same-origin',
        headers:{'X-CSRF-Token':state.csrf,Accept:'application/json'},cache:'no-store'});
      if(!res.ok)throw Error('退出请求失败：HTTP '+res.status);
      location.assign('/login?next=%2Fadmin');
    }catch(err){button.disabled=false;toast(err.message)}
  }
  function savedTheme(){
    try{
      const saved = localStorage.getItem('atlas-admin-theme');
      if(saved === 'light' || saved === 'dark') return saved;
    }catch(_){}
    return 'light';
  }
  function applyTheme(theme,save=true){
    if(theme!=='light' && theme!=='dark')return;
    document.documentElement.dataset.theme = theme;
    document.documentElement.style.colorScheme = theme;
    $$('[data-set-theme]').forEach(btn=>{
      const active = btn.dataset.setTheme === theme;
      btn.setAttribute('aria-pressed',String(active));
      btn.title = active ? (theme==='dark'?'当前：黑夜模式':'当前：白天模式') : (theme==='dark'?'切换白天模式':'切换黑夜模式');
    });
    const meta = $('meta[name="theme-color"]');
    if(meta)meta.content = theme==='dark'?'#0b111c':'#f5f7fb';
    if(save)try{localStorage.setItem('atlas-admin-theme',theme)}catch(_){}
  }
  function toast(message){
    const el=$('#toast');el.textContent=message;el.classList.add('show');
    clearTimeout(toastTimer);toastTimer=setTimeout(()=>el.classList.remove('show'),3200);
  }
  function percent(part,total){return total>0?Math.round(part*100/total):0}
  function number(n){return Number(n||0).toLocaleString('zh-CN')}
  function totalContent(counts){return ['websites','sections','patterns','insights'].reduce((n,k)=>n+(Number(counts[k])||0),0)}
  function setText(selector,text){const el=$(selector);if(el)el.textContent=String(text)}
  function renderNotice(d){
    const box=$('#dashboard-notice');
    if(!box)return;
    if(d.mode==='preview'){
      box.innerHTML='<div>'+icon('lock')+'<span><strong>只读设计预览：</strong>内容规模和研究覆盖来自真实公开目录；用户数、访问数据不在此页面展示。</span></div><span>PUBLIC DATA ONLY</span>';
    }else{
      box.innerHTML='<div>'+icon('shield')+'<span><strong>管理员视图：</strong>目录统计及账户汇总来自当前服务；运营总览为只读统计；内容新增、审核及发布请进入「内容管理」工作台。</span></div><span>ADMIN / READ ONLY</span>';
    }
    setText('#sidebar-user',d.administrator?.name || 'Atlas Workspace');
    setText('#sidebar-user-role',d.mode==='admin'?'已授权管理员':'只读运营预览');
    setText('#sidebar-avatar',(d.administrator?.name || 'Atlas').slice(0,1).toUpperCase());
    const connection=$('#connection-state');connection.innerHTML='<span class="status-led"></span> '+(d.mode==='admin'?'PRIVATE / LIVE':'LIVE CATALOG');
  }
  function renderKpis(d){
    const container=$('#kpi-grid'),sum=totalContent(d.counts);
    const keys=['websites','sections','patterns','insights'];
    container.innerHTML=keys.map((key,i)=>{
      const value=Number(d.counts[key]||0),share=percent(value,sum);
      return '<article class="kpi-card kpi-'+typeStyles[i]+'">'
        +'<div class="kpi-head"><div class="kpi-icon">'+icon(typeIcons[i])+'</div>'
        +'<a class="kpi-open" href="/'+key+'" target="_blank" rel="noopener" aria-label="打开 '+esc(typeLabels[i])+'目录">'+icon('arrow-up-right')+'</a></div>'
        +'<div class="kpi-number">'+number(value)+'</div>'
        +'<div class="kpi-label"><strong>'+typeLabels[i]+'</strong><span>占全部资源 '+share+'%</span></div>'
        +'<div class="kpi-track"><i style="--share:'+share+'%"></i></div></article>';
    }).join('');
  }
  function renderMix(d){
    const items=d.content_mix||[],sum=items.reduce((a,b)=>a+Number(b.value||0),0);
    let cumulative=0;
    const stops=items.map((x,i)=>{
      const start=cumulative,c=Number(x.value||0);
      cumulative+=sum?c*100/sum:0;
      return palette[i%palette.length]+' '+start.toFixed(3)+'% '+cumulative.toFixed(3)+'%';
    });
    const ring=sum?'conic-gradient('+stops.join(',')+')':'var(--bar-track)';
    $('#mix-visual').innerHTML='<div class="donut-wrap"><div class="donut-graph" role="img" aria-label="公开内容总计 '+number(sum)+' 条，按四类资源统计" style="--donut-stops:'+ring+'">'
      +'<div class="donut-hole"><strong>'+number(sum)+'</strong><span>收录参考总数</span><small>CURATED ASSETS</small></div></div></div>'
      +'<div class="mix-legend">'+items.map((item,i)=>{
        const val=Number(item.value)||0;
        return '<div class="mix-legend-item"><span class="mix-legend-dot" style="--color:'+palette[i%palette.length]+'"></span><span>'+esc(item.name)+'</span><strong>'+number(val)+'</strong><small>占全部资源 '+percent(val,sum)+'%</small></div>';
      }).join('')+'</div>';
  }
  function renderSectors(d){
    const sectors=d.sectors||[],max=Math.max(1,...sectors.map(x=>Number(x.count)||0));
    const total=d.counts.websites||0;
    $('#sector-chart').innerHTML=sectors.length?sectors.slice(0,8).map((x)=>{
      const c=Number(x.count||0),share=Math.max(2,Math.round(c*100/max));
      return '<div class="sector-row"><span class="sector-name" title="'+esc(x.name)+'">'+esc(x.name)+'</span>'
        +'<div class="sector-bar" aria-label="'+esc(x.name)+'，'+c+' 个网站"><i style="--pct:'+share+'%"></i></div>'
        +'<span class="sector-count">'+number(c)+'</span></div>';
    }).join(''):'<div class="visual-loading">当前没有行业分类数据</div>';
    setText('#sector-total','共 '+number(total)+' 个网站');
  }
  function renderQuality(d){
    const r=d.review||{},total=Number(d.counts.websites||0);
    const checked=Number(r.reviewed||0),pending=Number(r.pending||0),pct=percent(checked,total);
    $('#quality-content').innerHTML='<div class="quality-main">'
      +'<div class="quality-wheel" style="--complete:'+pct+'%" role="img" aria-label="人工检查档案覆盖率 '+pct+'%"><div class="quality-inner"><strong>'+pct+'%</strong><span>研究覆盖</span></div></div>'
      +'<div class="quality-facts"><p>目前 <strong>'+number(checked)+'</strong> 个网站具有带检查日期的人工研究档案，其余内容继续开放补全。</p>'
      +'<div class="quality-fact-row"><span>已有深度档案</span><b>'+number(checked)+' / '+number(total)+'</b></div>'
      +'<div class="quality-fact-row"><span>待补全研究</span><b>'+number(pending)+'</b></div>'
      +'<div class="quality-fact-row"><span>本地截图就绪</span><b>'+number(r.shots_ready||0)+'</b></div></div></div>'
      +'<a class="quality-link" href="#review-queue">查看尚未补全的案例 '+icon('arrow-right')+'</a>';
  }
  function polyline(values,maxVal){
    const w=560,h=90,padX=6,padY=8;
    if(!values.length)return {line:'',area:''};
    const points=values.map((n,i)=>{
      const x=padX+(values.length===1?0:i/(values.length-1))*(w-2*padX);
      const y=h-padY-(Number(n)||0)/maxVal*(h-2*padY);
      return [x,y];
    });
    const line=points.map((xy,i)=>(i?'L':'M')+xy[0].toFixed(2)+' '+xy[1].toFixed(2)).join(' ');
    return {line,area:line+' L '+points[points.length-1][0].toFixed(2)+' '+h+' L '+points[0][0].toFixed(2)+' '+h+' Z'};
  }
  function renderActivity(d){
    const root=$('#activity-body'),flag=$('#activity-tag');
    if(!d.private){
      flag.textContent='PRIVATE METRICS';
      root.innerHTML='<div class="activity-lock"><div class="activity-lock-icon">'+icon('lock')+'</div><div>'
        +'<strong>私人运营指标受到保护</strong>'
        +'<p>用户数量、收藏趋势和研究板活跃度仅向指定管理员开放。预览不会填充虚构的数据。</p>'
        +'<a href="/login?next=%2Fadmin">管理员登录后查看 →</a></div></div>';
      return;
    }
    flag.textContent='LIVE / 30-DAY DATA';
    const totals=d.private.totals||{},dates=(d.private.activity||[]).slice(-state.range);
    const saves=dates.map(x=>Number(x.saves)||0);
    const max=Math.max(1,...saves),p=polyline(saves,max);
    root.innerHTML='<div class="activity-totals">'
       +[['users','注册用户'],['saves','累计收藏'],['boards','研究板条目']].map(([k,label])=>'<div class="activity-total"><strong>'+number(totals[k]||0)+'</strong><span>'+label+'</span></div>').join('')
       +'</div><div class="activity-plot" role="img" aria-label="过去 '+state.range+' 天，日新增收藏数量的趋势图">'
       +'<svg viewBox="0 0 560 96" preserveAspectRatio="none"><path class="plot-grid" d="M0 28H560 M0 58H560 M0 88H560" fill="none"/>'
       +'<path class="plot-area" d="'+p.area+'"/><path class="plot-line" d="'+p.line+'"/></svg></div>'
       +'<div class="activity-controls"><span class="activity-legend"><i></i>每日新增收藏 · '+state.range+' 天（无访客追踪数据）</span>'
       +'<div class="activity-range" role="group" aria-label="图表时间范围">'
       +[7,14,30].map(n=>'<button type="button" data-days="'+n+'" class="'+(state.range===n?'active':'')+'">'+n+'天</button>').join('')
       +'</div></div>';
  }
  function filteredQueue(){
    const q=state.query.trim().toLowerCase();
    return (state.data?.queue||[]).filter(x=>!q||(x.name+' '+x.sector).toLowerCase().includes(q));
  }
  function renderQueue(){
    const items=filteredQueue(),visible=state.expanded?items:items.slice(0,6);
    const tbody=$('#review-body');
    setText('#queue-total','显示 '+visible.length+' / '+items.length);
    tbody.innerHTML=visible.length?visible.map((x,i)=>{
      const thumb=x.thumbnail?'<img class="queue-thumb" src="'+esc(x.thumbnail)+'" loading="lazy" alt="'+esc(x.name)+' 首页截图">'
        :'<div class="queue-thumb" aria-label="尚无本地截图"></div>';
      const url=/^\/websites\/[a-z0-9-]+$/.test(x.url)?x.url:'/websites';
      return '<tr><td><div class="queue-site">'+thumb+'<div><strong>'+esc(x.name)+'</strong><small>WEB REFERENCE / '+String(i+1).padStart(2,'0')+'</small></div></div></td>'
        +'<td>'+esc(x.sector)+'</td><td><span class="queue-pill '+(!x.thumbnail?'missing':'')+'"><i></i>'+esc(x.status)+'</span></td>'
        +'<td><a class="queue-action" href="'+esc(url)+'" target="_blank" rel="noopener">打开案例 '+icon('arrow-up-right')+'</a></td></tr>';
    }).join(''):'<tr><td colspan="4">没有匹配的待完善案例。</td></tr>';
    const more=$('#queue-more');
    more.hidden=items.length<=6;
    more.innerHTML=state.expanded?'收起列表 '+icon('chevron-right'):'查看剩余 '+(items.length-6)+' 条 '+icon('chevron-right');
  }
  function renderArticles(d){
    const list=d.recent_articles||[];
    $('#recent-articles').innerHTML=list.length?list.map((a,i)=>{
      const url=/^\/insights\/[a-z0-9-]+$/.test(a.url)?a.url:'/insights';
      return '<a class="recent-article" href="'+esc(url)+'" target="_blank" rel="noopener">'
        +'<span class="article-number">'+String(i+1).padStart(2,'0')+'</span>'
        +'<span class="article-content"><strong>'+esc(a.title)+'</strong><span>'+esc(a.category)+' · '+esc(a.date||'未标注日期')+'</span></span>'+icon('arrow-up-right')+'</a>';
    }).join(''):'<div class="visual-loading">暂无研究文章</div>';
  }
  function systemRow(name,description,label,kind,iconName){
    return '<div class="system-row"><div class="system-icon">'+icon(iconName)+'</div>'
      +'<div class="system-info"><strong>'+esc(name)+'</strong><small>'+esc(description)+'</small></div>'
      +'<span class="system-badge '+kind+'">'+esc(label)+'</span></div>';
  }
  function renderSystem(d){
    const real=d.mode==='admin';
    $('#system-content').innerHTML=
      systemRow('内容来源','公开案例库 / 研究档案已接入','已连接','good','database')
      +systemRow('账户运营统计',real?'仅汇总统计，不公开个人数据':'预览不读取用户资料',real?'已授权':'受保护',real?'good':'','users')
      +systemRow('密码找回邮件',real?(d.email_reset_enabled?'SMTP 已配置':'尚未配置 SMTP 发信服务'):'登录管理员后检查 SMTP 状态',real?(d.email_reset_enabled?'已连接':'待配置'):'仅管理员',real?(d.email_reset_enabled?'good':'warn'):'','lock')
      +systemRow('内容发布与审核','支持草稿、审核、正式发布、归档与版本历史；仅授权管理员可操作','已接入','good','quality')
      +systemRow('数据长期备份','请检查数据库有效期及异地备份策略','需核实','warn','shield');
  }
  function render(d){
    state.data=d;renderNotice(d);renderKpis(d);renderMix(d);renderSectors(d);
    renderQuality(d);renderActivity(d);renderQueue();renderArticles(d);renderSystem(d);
    const dt = new Date(d.updated_at);
    setText('#report-date',Number.isNaN(dt.getTime())?'最近同步时间未知':new Intl.DateTimeFormat('zh-CN',{year:'numeric',month:'short',day:'numeric',hour:'2-digit',minute:'2-digit'}).format(dt));
    $('#export-button').disabled=false;
  }
  // V51.7 · Genuine private analytics; preview remains public-data-only.
  function renderTrafficLocked(){
    setText('#atlas-traffic-summary','管理员登录后可查看真实匿名事件与收藏排行。公开预览不会查询这些数据。');
    $('#atlas-traffic-kpis').innerHTML='<div class="atlas-traffic-empty">仅对已授权管理员开放。<a href="/login?next=%2Fadmin%23traffic">登录后台 →</a></div>';
    for(const name of ['chart','pages','searches','saved'])
      $('#atlas-traffic-'+name).innerHTML='<div class="atlas-traffic-empty">PRIVATE ANALYTICS · 登录后查看</div>';
  }
  function trafficChart(daily){
    if(!daily.length)return '<p class="atlas-traffic-empty">暂无统计区间数据。</p>';
    const width=820,height=190,left=35,right=14,top=15,bottom=30;
    const max=Math.max(1,...daily.map(x=>Math.max(Number(x.views)||0,Number(x.searches)||0)));
    const x=i=>left+(daily.length===1?0:i/(daily.length-1))*(width-left-right);
    const y=n=>height-bottom-(Number(n)||0)/max*(height-top-bottom);
    const line=key=>daily.map((v,i)=>(i?'L':'M')+x(i).toFixed(1)+','+y(v[key]).toFixed(1)).join(' ');
    const labels=[0,Math.floor((daily.length-1)/2),daily.length-1].map(i=>
       '<text x="'+x(i).toFixed(1)+'" y="182" text-anchor="middle">'+esc(daily[i].date.slice(5))+'</text>').join('');
    return '<div class="atlas-traffic-chart-key"><span><i class="views"></i>页面浏览</span><span><i class="searches"></i>站内搜索</span></div>'
       +'<svg viewBox="0 0 820 190" role="img" aria-label="真实日访问量与搜索量趋势，最多 '+max+' 次">'
       +'<path class="atlas-traffic-gridline" d="M35 15H806 M35 87H806 M35 160H806"/>'
       +'<text class="atlas-traffic-axis" x="3" y="20">'+max+'</text><text class="atlas-traffic-axis" x="18" y="163">0</text>'
       +'<path class="atlas-traffic-views-line" d="'+line('views')+'"/>'
       +'<path class="atlas-traffic-search-line" d="'+line('searches')+'"/>'
       +'<g class="atlas-traffic-axis">'+labels+'</g></svg>';
  }
  function renderTrafficList(id,rows,type){
    const root=$('#atlas-traffic-'+id);
    if(!rows.length){root.innerHTML='<p class="atlas-traffic-empty">当前没有'+(type==='saved'?'收藏':type==='search'?'搜索':'浏览')+'记录；上线后产生数据时自动显示。</p>';return}
    const countKey=type==='pages'?'views':type==='search'?'searches':'count';
    const max=Math.max(1,...rows.map(x=>Number(x[countKey])||0));
    root.innerHTML=rows.slice(0,10).map((x,i)=>{
      const label=type==='pages'?x.label:type==='saved'?x.label:x.term;
      const url=type==='pages'?x.path:type==='saved'?x.url:null;
      const title=url?'<a target="_blank" rel="noopener" href="'+esc(url)+'">'+esc(label)+'</a>':'<span>'+esc(label)+'</span>';
      const count=Number(x[countKey])||0;
      return '<div class="atlas-traffic-rank"><span class="atlas-traffic-rank-number">'+String(i+1).padStart(2,'0')+'</span>'
        +'<div class="atlas-traffic-rank-body"><div class="atlas-traffic-rank-label">'+title+'<strong>'+number(count)+'</strong></div>'
        +'<div class="atlas-traffic-rank-track"><i style="width:'+Math.max(2,Math.round(100*count/max))+'%"></i></div></div></div>';
    }).join('');
  }
  function renderTraffic(d){
    state.traffic=d;
    setText('#atlas-traffic-summary','已统计 '+d.since+' 至 '+d.through+'（UTC） · '+d.collected_since);
    $$('[data-traffic-days]').forEach(b=>{b.classList.toggle('active',Number(b.dataset.trafficDays)===state.trafficDays);b.setAttribute('aria-pressed',String(Number(b.dataset.trafficDays)===state.trafficDays))});
    const t=d.totals||{};
    const stats=[
      ['page_views','浏览次数',state.trafficDays+' 天真实记录','globe'],
      ['searches','搜索次数',state.trafficDays+' 天真实搜索','magnifier'],
      ['active_saves','当前收藏','全量数据快照','quality'],
      ['registered_users','注册账户','全量账户数','users'],
      ['new_users','新增账户',state.trafficDays+' 天真实注册','calendar']
    ];
    $('#atlas-traffic-kpis').innerHTML=stats.map(([key,label,note,ic])=>
      '<article class="atlas-traffic-kpi"><div class="atlas-traffic-kpi-top">'+icon(ic)+'<span>'+esc(note)+'</span></div>'
      +'<strong>'+number(t[key])+'</strong><span>'+esc(label)+'</span></article>').join('');
    $('#atlas-traffic-chart').innerHTML=trafficChart(d.daily||[]);
    renderTrafficList('pages',d.top_pages||[],'pages');
    renderTrafficList('searches',d.top_searches||[],'search');
    renderTrafficList('saved',d.top_saved||[],'saved');
    $('#atlas-traffic-export').disabled=false;
  }
  async function loadTraffic(){
    if(mode!=='admin'){renderTrafficLocked();return}
    if(state.trafficFetching)return;
    state.trafficFetching=true;
    setText('#atlas-traffic-summary','正在查询真实运营数据…');
    try{
      const response=await fetch('/api/admin/analytics?days='+state.trafficDays,{
        credentials:'same-origin',cache:'no-store',headers:{Accept:'application/json'}});
      if(!response.ok)throw Error(response.status===403?'管理员权限不足':response.status===401?'登录已过期':'HTTP '+response.status);
      renderTraffic(await response.json());
    }catch(err){
      setText('#atlas-traffic-summary','运营统计暂不可用：'+err.message);
      $('#atlas-traffic-kpis').innerHTML='<p class="atlas-traffic-empty">数据获取失败，并非没有访问。请点击刷新重试。</p>';
      state.traffic=null;$('#atlas-traffic-export').disabled=true;
    }finally{state.trafficFetching=false}
  }
  function exportTrafficCsv(){
    const d=state.traffic;if(!d||mode!=='admin')return;
    const safe=x=>{
      const value=String(x??'').replace(/"/g,'""');
      return '"'+(/^[=+\-@\t\r]/.test(value)?"'"+value:value)+'"';
    };
    const rows=[['B2B Atlas · real analytics'],['period',d.since,d.through],
       ['section','date','page views','searches'],...d.daily.map(x=>['daily',x.date,x.views,x.searches]),
       [],['section','page','views'],...d.top_pages.map(x=>['page',x.path,x.views]),
       [],['section','search term','count'],...d.top_searches.map(x=>['search',x.term,x.searches]),
       [],['section','saved resource','count'],...d.top_saved.map(x=>['saved',x.key,x.count])];
    const csv='\ufeff'+rows.map(row=>row.map(safe).join(',')).join('\r\n');
    const url=URL.createObjectURL(new Blob([csv],{type:'text/csv;charset=utf-8'}));
    const link=document.createElement('a');
    link.href=url;link.download='atlas-real-analytics-'+d.period_days+'d-'+d.through+'.csv';
    document.body.appendChild(link);link.click();link.remove();
    setTimeout(()=>URL.revokeObjectURL(url),1500);
    toast('真实运营报表已导出');
  }
  // V51.8–V51.12 · Real acquisition, session and conversion intelligence.
  const growthNames={direct:'直接 / 未识别',organic:'自然搜索',social:'社交媒体',
    referral:'外部引荐',paid:'付费推广',email:'邮件渠道',
    desktop:'桌面设备',tablet:'平板设备',mobile:'移动设备',unknown:'未识别'};
  function growthLabel(value){return growthNames[value]||value||'未分类'}
  function growthNumber(value){return number(Number(value)||0)}
  function growthPercent(n,total){return total?Math.round(1000*n/total)/10:0}
  function growthEmpty(message='该时间范围暂无记录，采集到真实访问后自动显示。'){
    return '<p class="atlas-traffic-empty">'+esc(message)+'</p>';
  }
  function growthBarRows(rows,nameKey='key',countKey='sessions',maxRows=10){
    if(!rows||!rows.length)return growthEmpty();
    const maximum=Math.max(1,...rows.map(r=>Number(r[countKey])||0));
    return rows.slice(0,maxRows).map(x=>{
      const count=Number(x[countKey])||0;
      const title=growthLabel(x[nameKey]);
      return '<div class="atlas-growth-bar-row"><div class="atlas-growth-bar-head"><strong title="'+esc(title)+'">'
       +esc(title)+'</strong><span>'+growthNumber(count)+'</span></div>'
       +'<div class="atlas-growth-bar-track"><i style="width:'+Math.max(2,100*count/maximum).toFixed(1)+'%"></i></div></div>';
    }).join('');
  }
  function renderGrowthLocked(){
    setText('#atlas-growth-note','真实渠道、会话及转化分析仅向管理员开放。');
    $('#atlas-growth-metrics').innerHTML=growthEmpty('管理员登录后查看。');
    for(const key of ['channels','daily','sources','campaigns','funnel','devices','scroll','landings','content'])
      $('#atlas-growth-'+key).innerHTML=growthEmpty('PRIVATE ANALYTICS');
    $('#atlas-growth-export').disabled=true;
  }
  function growthTrend(rows){
    if(!rows.length)return growthEmpty();
    const width=820,height=190,left=35,right=14,top=15,bottom=30;
    const max=Math.max(1,...rows.map(x=>Math.max(Number(x.sessions)||0,Number(x.registrations)||0,Number(x.first_saves)||0)));
    const x=i=>left+(rows.length===1?0:i/(rows.length-1))*(width-left-right);
    const y=n=>height-bottom-(Number(n)||0)/max*(height-top-bottom);
    const series=(key,cls)=>'<path class="'+cls+'" d="'+rows.map((r,i)=>
       (i?'L':'M')+x(i).toFixed(1)+' '+y(r[key]).toFixed(1)).join(' ')+'"/>';
    const ticks=[0,Math.floor((rows.length-1)/2),rows.length-1].map(i=>
       '<text x="'+x(i).toFixed(1)+'" y="182" text-anchor="middle">'+esc(rows[i].date.slice(5))+'</text>').join('');
    return '<div class="atlas-growth-chart-key"><span><i class="sessions"></i>活跃会话</span><span><i class="registrations"></i>注册</span><span><i class="saves"></i>会话首次收藏</span></div>'
       +'<svg viewBox="0 0 820 190" role="img" aria-label="匿名会话及真实转化次数趋势">'
       +'<path class="atlas-traffic-gridline" d="M35 15H806 M35 87H806 M35 160H806"/>'
       +series('sessions','atlas-growth-line-sessions')+series('registrations','atlas-growth-line-signups')
       +series('first_saves','atlas-growth-line-saves')
       +'<g class="atlas-traffic-axis">'+ticks+'</g></svg>';
  }
  function renderGrowth(d){
    state.growth=d;
    const t=d.totals||{};
    setText('#atlas-growth-note','统计区间：'+d.since+' — '+d.through+'（UTC） · '+d.tracking_since);
    const kpis=[
      ['sessions','匿名会话数','按匿名标签页估算','globe'],
      ['engaged_sessions','有互动会话','搜索／多次浏览／深度滚动','magnifier'],
      ['registrations','注册转化','服务端确认的真实注册','users'],
      ['first_saves','收藏转化','当前会话首次新增收藏','quality'],
      ['external_clicks','官网跳转','向外部网站的真实点击','arrow-up-right']
    ];
    $('#atlas-growth-metrics').innerHTML=kpis.map(([key,title,help,ic])=>
      '<article class="atlas-traffic-kpi"><div class="atlas-traffic-kpi-top">'+icon(ic)+'<span>'+esc(help)+'</span></div>'
      +'<strong>'+growthNumber(t[key])+'</strong><span>'+esc(title)+'</span></article>').join('');
    $('#atlas-growth-daily').innerHTML=growthTrend(d.daily||[]);
    const channels=d.channels||[];
    $('#atlas-growth-channels').innerHTML=channels.length?
       '<table class="atlas-growth-table"><thead><tr><th>渠道</th><th>会话</th><th>浏览</th><th>注册</th><th>收藏</th><th>注册率</th></tr></thead><tbody>'
       +channels.map(row=>'<tr><td><span class="atlas-growth-channel-dot"></span>'+esc(growthLabel(row.key))+'</td>'
          +'<td>'+growthNumber(row.sessions)+'</td><td>'+growthNumber(row.views)+'</td>'
          +'<td>'+growthNumber(row.registrations)+'</td><td>'+growthNumber(row.first_saves)+'</td>'
          +'<td>'+growthPercent(row.registrations,row.sessions)+'%</td></tr>').join('')
       +'</tbody></table>':growthEmpty();
    $('#atlas-growth-sources').innerHTML=growthBarRows(d.sources);
    $('#atlas-growth-campaigns').innerHTML=growthBarRows(d.campaigns);
    $('#atlas-growth-landings').innerHTML=growthBarRows(d.landing_pages);
    const funnel=[
      ['到访会话',t.sessions||0,100],
      ['有互动会话',t.engaged_sessions||0,growthPercent(t.engaged_sessions,t.sessions)],
      ['完成注册',t.registrations||0,growthPercent(t.registrations,t.sessions)],
      ['会话内首次收藏',t.first_saves||0,growthPercent(t.first_saves,t.sessions)],
      ['本次注册后收藏',t.signup_to_save||0,growthPercent(t.signup_to_save,t.sessions)]
    ];
    $('#atlas-growth-funnel').innerHTML='<p class="atlas-growth-method">以下是同一统计周期的会话及转化行为，不代表每个访客都依次经过全部步骤。</p>'
       +funnel.map(([label,n,pct])=>'<div class="atlas-growth-step"><span>'+esc(label)+'</span><strong>'+growthNumber(n)
           +'</strong><small>'+pct+'%</small><i style="width:'+Math.max(0,Math.min(100,pct))+'%"></i></div>').join('');
    $('#atlas-growth-devices').innerHTML='<h4>访问设备</h4>'+growthBarRows(d.devices);
    $('#atlas-growth-scroll').innerHTML='<h4>达到的滚动深度</h4>'
      +((d.scroll_depth||[]).map(row=>'<div class="atlas-growth-bar-row"><div class="atlas-growth-bar-head"><strong>'+row.depth+'% 页面</strong><span>'+growthNumber(row.sessions)+' 会话</span></div>'
         +'<div class="atlas-growth-bar-track"><i style="width:'+growthPercent(row.sessions,t.sessions)+'%"></i></div></div>').join(''));
    const contents=d.content||[];
    $('#atlas-growth-content').innerHTML=contents.length?
       '<table class="atlas-growth-table"><thead><tr><th>内容页</th><th>浏览</th><th>预览</th><th>站内点击</th><th>外链</th></tr></thead><tbody>'
       +contents.slice(0,14).map(row=>'<tr><td><a rel="noopener" target="_blank" href="'+esc(row.path)+'">'+esc(row.path)+'</a></td>'
         +'<td>'+growthNumber(row.views)+'</td><td>'+growthNumber(row.previews)+'</td>'
         +'<td>'+growthNumber(row.content_clicks)+'</td><td>'+growthNumber(row.external_clicks)+'</td></tr>').join('')
       +'</tbody></table>':growthEmpty();
    $('#atlas-growth-export').disabled=false;
  }
  async function loadGrowth(){
    if(mode!=='admin'){renderGrowthLocked();return}
    if(state.growthFetching)return;
    state.growthFetching=true;
    setText('#atlas-growth-note','正在查询真实来源、转化与浏览行为…');
    const btn=$('#atlas-growth-export');btn.disabled=true;
    try{
      const url='/api/admin/growth?days='+state.trafficDays+'&channel='+encodeURIComponent(state.growthChannel);
      const response=await fetch(url,{credentials:'same-origin',cache:'no-store',headers:{Accept:'application/json'}});
      if(!response.ok)throw Error(response.status===401?'登录已过期':response.status===403?'当前账户没有管理员权限':'HTTP '+response.status);
      renderGrowth(await response.json());
    }catch(err){
      state.growth=null;
      setText('#atlas-growth-note','真实运营归因统计暂不可用：'+err.message);
      $('#atlas-growth-metrics').innerHTML=growthEmpty('接口暂不可用，不代表流量为零。');
    }finally{state.growthFetching=false}
  }
  function exportGrowthCsv(){
    if(mode!=='admin'||!state.growth)return;
    const d=state.growth,lines=[];
    const protect=value=>{
      const text=String(value??'');
      return '"'+(/^[=+\-@\t\r]/.test(text)?"'"+text:text).replace(/"/g,'""')+'"';
    };
    const push=(...values)=>lines.push(values.map(protect).join(','));
    const section=(name,headers,items,columns)=>{
      push(name);push(...headers);
      for(const row of items||[])push(...columns.map(key=>row[key]));
      lines.push('');
    };
    push('B2B Atlas · 真正运营数据分析','V51.12');
    push('UTC 日期范围',d.since,d.through,'渠道筛选',d.channel_filter);
    push('说明','会话为匿名标签页估算；注册和收藏转化来自服务端成功操作；未采集历史不得回填');
    lines.push('');
    section('每天的真实会话与行为',['日期','会话天数','浏览','搜索','外链','注册','首次收藏'],d.daily,
       ['date','sessions','views','searches','external_clicks','registrations','first_saves']);
    const fields=['key','sessions','views','searches','external_clicks','registrations','first_saves'];
    const headers=['分组','会话','浏览','搜索','外链','注册','首次收藏'];
    for(const key of ['channels','sources','mediums','campaigns','referrers','devices','landing_pages'])
      section(key,headers,d[key],fields);
    section('内容表现（全站、不按渠道筛选）',['URL','浏览','预览','站内点击','外链'],d.content,
      ['path','views','previews','content_clicks','external_clicks']);
    section('滚动深度',['阈值','达到会话数'],d.scroll_depth,['depth','sessions']);
    const bytes='\ufeff'+lines.join('\r\n');
    const url=URL.createObjectURL(new Blob([bytes],{type:'text/csv;charset=utf-8'}));
    const a=document.createElement('a');
    a.href=url;a.download='atlas-growth-'+d.days+'d-'+d.channel_filter+'-'+d.through+'.csv';
    document.body.appendChild(a);a.click();a.remove();
    setTimeout(()=>URL.revokeObjectURL(url),1500);
    toast('渠道与转化报表已导出');
  }
  function showError(message){
    const box=$('#dashboard-notice');
    box.innerHTML='<div>'+icon('alert')+'<span>运营数据读取失败：'+esc(message)+'</span></div><span>RETRY</span>';
    $('#kpi-grid').innerHTML='<div class="dashboard-error" style="grid-column:1/-1"><h2>暂时无法载入内容</h2><p>公开资源或管理员数据可能暂时不可用，现有前台不受影响。</p><button id="retry-button" type="button">重新加载</button></div>';
  }
  async function load(){
    if(state.fetching)return;
    state.fetching=true;
    const btn=$('#refresh-button');btn.disabled=true;
    try{
      const path=mode==='admin'?'/api/admin/overview':'/api/admin/preview';
      const result=await fetch(path,{credentials:'same-origin',cache:'no-store',headers:{Accept:'application/json'}});
      if(!result.ok)throw new Error(result.status===401?'登录已过期':result.status===403?'管理员权限不足':'HTTP '+result.status);
      const data=await result.json();
      if(mode==='preview'&&(data.private||data.administrator))throw new Error('预览接口包含不应公开的数据，已阻止显示');
      render(data);
      await Promise.all([loadTraffic(),loadGrowth()]);
      return true;
    }catch(error){showError(error.message);return false}
    finally{state.fetching=false;btn.disabled=false}
  }
  function exportSummary(){
    if(!state.data)return;
    const d=state.data;
    const out={
      title:'B2B Atlas 内容运营概览',
      mode:d.mode,
      exported_at:new Date().toISOString(),
      counts:d.counts,review:d.review,sectors:d.sectors,
      content_mix:d.content_mix,recent_articles:d.recent_articles,
      // Export is a report summary; never serialize session/token/user records.
      aggregated_operations:d.mode==='admin'&&d.private?d.private:null,
      notes:'运营统计导出。公开预览不包含私有账户指标；内容管理工作台提供独立的草稿、审核与发布工作流。'
    };
    const blob=new Blob([JSON.stringify(out,null,2)],{type:'application/json;charset=utf-8'});
    const href=URL.createObjectURL(blob),a=document.createElement('a');
    a.href=href;a.download='b2b-atlas-operations-'+(d.mode==='preview'?'public-':'')+new Date().toISOString().slice(0,10)+'.json';
    document.body.appendChild(a);a.click();a.remove();
    setTimeout(()=>URL.revokeObjectURL(href),1500);
    toast('概览报表已导出');
  }
  function setNavActive(anchor){
    $$('.side-link[data-nav-section]').forEach(a=>a.classList.toggle('active',a.dataset.navSection===anchor));
  }
  function closeSidebar(){
    document.body.classList.remove('sidebar-open');
    $('#sidebar-backdrop').hidden=true;
    $('#mobile-nav').setAttribute('aria-expanded','false');
  }
  function boot(){
    const studio=$('#open-content-studio');
    if(studio){
      studio.href='/admin/content?kind=site';studio.querySelector('span').textContent='内容管理';
    }

    applyTheme(savedTheme(),false);
    if(location.hash==='#traffic')setNavActive('traffic');
    document.addEventListener('click',event=>{
      const theme=event.target.closest('[data-set-theme]');
      if(theme){applyTheme(theme.dataset.setTheme);return}
      const range=event.target.closest('[data-days]');
      if(range){state.range=Number(range.dataset.days);if(state.data)renderActivity(state.data);return}
      const trafficDays=event.target.closest('[data-traffic-days]');
      if(trafficDays&&mode==='admin'){state.trafficDays=Number(trafficDays.dataset.trafficDays);loadTraffic();loadGrowth();return}
      const nav=event.target.closest('[data-nav-section]');
      if(nav){setNavActive(nav.dataset.navSection);closeSidebar()}
    });
    $('#admin-logout').addEventListener('click',logoutAdmin);
    $('#refresh-button').addEventListener('click',()=>{load().then(success=>{if(success)toast('运营资料已刷新')})});
    $('#export-button').addEventListener('click',exportSummary);
    $('#atlas-traffic-export').addEventListener('click',exportTrafficCsv);
    $('#atlas-growth-filter').addEventListener('change',e=>{
      if(mode!=='admin')return;
      state.growthChannel=e.target.value;loadGrowth();
    });
    $('#atlas-growth-export').addEventListener('click',exportGrowthCsv);
    $('#queue-search').addEventListener('input',event=>{state.query=event.target.value;state.expanded=false;renderQueue()});
    $('#queue-more').addEventListener('click',()=>{state.expanded=!state.expanded;renderQueue()});
    $('#mobile-nav').addEventListener('click',()=>{
      const open=!document.body.classList.contains('sidebar-open');
      document.body.classList.toggle('sidebar-open',open);
      $('#sidebar-backdrop').hidden=!open;
      $('#mobile-nav').setAttribute('aria-expanded',String(open));
    });
    $('#sidebar-backdrop').addEventListener('click',closeSidebar);
    document.addEventListener('keydown',e=>{
      if(e.key==='Escape')closeSidebar();
      if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='k'){
        e.preventDefault();$('#queue-search').focus();$('#review-queue').scrollIntoView({block:'start'});
      }
    });
    hydrateAdminIdentity();
    load();
  }
  boot();
})();
