# Insights · 资讯与研究内容维护

本栏目使用 **`frontend/articles.json`** 作为独立的结构化文章库，并由 `frontend/app.js` 渲染。新增或修改文章不需要修改 HTML 模板或 CSS，也不需要另外添加旧版的覆盖脚本。

## 页面

- `/insights`：首页精选、五个分类、全文关键词搜索和排序
- `/insights?category=cases`：分类筛选（类目使用 `categories[].id`）
- `/insights/<article-id>`：文章独立详情、目录、相关案例和延伸阅读
- 首页及全局搜索会推荐 Insights 的文章

## 文章数据

每篇文章包含：`id`（稳定 URL slug）、`title`、`subtitle`、`category`、`cover_site`（已有 Websites 的 site ID）、`tags`、`published_at`（ISO 日期）、`author`、`featured`、`reading_minutes`、`takeaways`、`sections` 和 `references`。

`sections` 每节支持 `title`、`paragraphs`（数组）、`bullets`（数组，可空）、`callout`（可空）。`references` 是形如 `["website","vast"]` 或 `["pattern","object-first-hero"]` 的二元数组，必须指向已收录资源。

`featured: true` 用于指定栏目首页的头条；优先保持至多一篇。

## 内容与事实标准

- 首批 10 篇是 B2B Atlas 编辑性设计研究，并非实时行业新闻。勿将旧内容伪装成当天发生的新事件。
- 任何案例、年份、客户、技术指标或性能数字必须有可靠来源，未经核实的信息不应写成事实。
- 文章用真实的已收录网站截图作配图；截图可说明观察内容，但不等于官方设计系统规范。
- 发布前核对标题、分类、阅读时间、实际引用的案例、移动端布局和每条正文深链。
- 大规模内容更新如需 CMS，可在当前 JSON 数据结构之上继续构建，不应另起一套独立风格的页面。

## 发布验证

1. 在文章库中新增一个唯一的 slug，确保 category 与 cover_site 存在。
2. 验证 `/insights`、`/insights?category=...`、`/insights/<id>` 均能访问。
3. 检查分类数量、关键词搜索、目录锚点、复制链接、相关案例和首页最新文章卡片。
4. 检查 390 / 768 / 1440 像素宽度、图片加载、浏览器历史与页脚。

