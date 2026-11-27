"""V66: public editorial methodology and source-transparency explainer.

No invented staff credentials, affiliations, performance claims or source dates.
"""
RECORD={
    "title":"研究方法与引用说明",
    "description":"了解 B2B Atlas 如何展示第三方网站截图、文章来源、编辑观察及资料的验证边界。",
    "path":"/methodology","indexed":True,"kind":"methodology"
}
STYLE="""<style id="atlas-methodology-style">
.atlas-methodology{max-width:900px;padding:54px 0 80px}
.atlas-methodology h1{font-size:clamp(30px,4vw,47px);line-height:1.15;letter-spacing:-.04em;margin:8px 0 22px}
.atlas-methodology h2{font-size:22px;margin:0 0 11px}
.atlas-methodology p{font-size:15px;line-height:1.9;color:#55647a;margin:0 0 17px}
.atlas-methodology section{border-bottom:1px solid #e1e8f2;padding:24px 0}
.atlas-methodology a{color:#2456c6}
.atlas-methodology .eyebrow{font-size:11px;letter-spacing:.16em;color:#2456c6;font-weight:750}
.atlas-methodology .methodology-lead{font-size:18px;line-height:1.8}
.atlas-methodology .methodology-links{display:flex;flex-wrap:wrap;gap:16px;margin-top:30px}
@media(max-width:720px){.atlas-methodology{padding:24px 0 50px}}
</style>"""


def prerender():
    return """<article class="shell atlas-methodology">
<p class="eyebrow">RESEARCH METHODOLOGY / B2B ATLAS</p>
<h1>研究方法与引用说明</h1>
<p class="methodology-lead">B2B Atlas 整理公开 B2B 网站、页面模块和设计模式，帮助读者观察信息层级、视觉选择与产品叙事。我们区分“可以从页面直接观察的内容”和“需要独立核验的事实”。</p>
<section><h2>资料是什么</h2>
<p>网站案例记录的是第三方公开页面的视觉与内容表现。案例页面中可提供原始网站链接，文章也会在相关位置列出公开参考来源。网站、商标、产品及其内容归各自权利人所有。</p></section>
<section><h2>编辑观察与事实边界</h2>
<p>页面布局、模块顺序、截图色彩和文案呈现可以用于设计研究；这不构成对第三方产品性能、交付质量、安全性、转化率或商业结果的验证。研究观点不是第三方品牌的官方背书。</p></section>
<section><h2>如何核对文章引用</h2>
<p>研究文章中的来源区域列出已关联的公开案例和文章正文提供的外部资料链接。读者可以沿原始链接核对信息；如果没有明确依据，不应把编辑推断当作已核实的产品事实。</p></section>
<section><h2>发布日期与更新记录</h2>
<p>文章公开展示的日期来自内容记录。只有存在有效日期时，站点才会在结构化数据和站点地图中呈现日期；不会仅为了搜索排名虚构更新时间。</p></section>
<section><h2>公开范围</h2>
<p>仅正式发布的内容进入公开检索页面与资源索引。个人收藏、账户资料、待审核草稿和内部审核记录不属于公开研究内容。</p></section>
<nav class="methodology-links" aria-label="继续研究"><a href="/insights">查看研究文章</a><a href="/directory">查看全部公开资源目录</a></nav>
</article>"""
