# B2B Atlas · Render 预览部署与验收

当前预览服务：https://b2b-design-atlas-preview.onrender.com

## 自动部署为什么不能只看 autoDeploy=yes

Render 的自动部署需要使用**已授权的 Git 提供方连接**。以公开 Git URL 创建的服务虽然能构建并部署，但不能依靠 GitHub push 自动触发。

1. 在 Render [Account Settings](https://dashboard.render.com/account) 中进入 **Git Deployment Credentials**，将 GitHub 连接到 Render。
2. 在 [Render GitHub App 设置](https://github.com/apps/render/installations/new) 检查仓库访问范围，包含 **Micko886/b2b-design-atlas**。
3. 在 [现有预览服务](https://dashboard.render.com/web/srv-dc1tlouc6qcc73brcgd0) 的 Settings 中检查 **Repository / Git Credentials**，确保服务实际使用已授权的 GitHub 连接而非匿名公开仓库 URL。不要新建同名服务或更换数据库。
4. 保持 Branch = `main`，Auto-Deploy = **On Commit**（或 **After CI Checks Pass**）。
5. 提交一个实际更改后，确认 Render 自动生成 trigger = `git_push` 或相应自动触发记录，且构建状态为 live。

## 可重复的上线检查

- 无需登录访问 `/api/atlas-build`，返回 `cms_version` 和当前部署的 `commit`；不会暴露用户、会话、数据库或密钥。
- GitHub Actions 的 **Preview Deployment Verification** 在每次 main 提交后比较线上 `commit` 与当前提交，兼容 Render 免费实例的启动与构建等待；超时失败意味着线上未同步，**不是** GitHub 代码构建失败。
- `/api/health` 用于服务可用性，`/admin/content` 仍要求登录权限。单纯服务显示 live 不等于用户编辑／审核流程已验收。
- 代码上新后，先通过 CMS Browser QA、Docker 后端测试，再检查线上部署指纹，最后使用各角色账号做手动发布验证。

## 手动部署

在 GitHub 尚未授权 Render 前，使用 Render 服务页的 Manual Deploy 或有权限的 Render API 将最新 main 提交部署。不要把 Render API Key、Deploy Hook URL 或数据库凭据提交到 GitHub。
