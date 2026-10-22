# Dalaoweb

基于 Astro 与 Fuwari 的静态个人博客，首发地址为
[quinmeow.github.io](https://quinmeow.github.io/)。

## 内容与架构

- 110 篇历史文章、2 个公开页面，保留 WordPress 分类路径与文章 ID。
- 正文为可直接维护的 Markdown 与经过清理的旧 HTML，不依赖 WordPress。
- 图片、音视频继续使用 `https://cdn.dalaoweb.top`，由既有阿里云 CDN 回源 OSS。
- 不运行 PHP、数据库或常驻 Node 服务；Node 仅在本地和 CI 构建。
- 搜索由 Pagefind 在构建时生成；不接入评论、广告或站点统计脚本。

## 本地开发

使用 Node.js 24 和 `package.json` 中指定的 pnpm 版本。

```sh
pnpm install --frozen-lockfile
pnpm dev
pnpm check
pnpm build
node scripts/verify-build.mjs
pnpm preview
```

生产输出为 `dist/`。本地预览必须使用构建后的 `pnpm preview` 才能验证全文搜索。
新文章放在 `src/content/posts/`，站点资料在 `src/config.ts`。
旧文章的 `slug` 与 `originalPath` 是公开地址，不要随意改动。
旧文章默认不新增授权声明，原作者著作权不因格式迁移而改变。

## GitHub Pages

`main` 分支推送后执行 `.github/workflows/deploy.yml`：
单元测试、内容边界检查、Astro 检查、静态构建、112 条旧路径验收、依赖审计，然后发布 Pages。
仓库 Pages 设置使用 GitHub Actions，不需要部署密钥或云平台 AccessKey。
原始导出只留在本地忽略目录 `.migration-data/`，不可放入公开仓库。

## 将来迁回 ECS

1. 在受支持的新系统安装 Nginx，不需要安装 WordPress、PHP 或 MySQL。
2. 用目标 HTTPS 域名重新构建，例如 `SITE_URL=https://blog.dalaoweb.top pnpm build`。
3. 将 `dist/` 发布至 Nginx 文档根目录，配置 `try_files $uri $uri/ =404;` 和自定义 `404.html`。
4. 分别验收正文、CDN 图片、旧路径、搜索和 RSS 后，再安排 DNS 切换。

图片继续走同一 CDN/OSS，因此站点迁回 ECS 时不必重复搬运整套图片。
本仓库不会自动重装 ECS、修改域名解析或删除旧站。

## 迁移记录

[转换工具说明](tools/migration/README.md) 与
[迁移问题清单](docs/migration-report.json) 记录格式转换边界。
历史失效外链图片保留来源链接；两个旧音乐插件播放器缺少独立媒体地址，不能凭空恢复。
验证过的第三方图片采用逐 URL 允许清单，不放宽整站域名访问。
从旧归档找回的一张 85 KB 图片位于 `public/images/recovered/`，作为小型本地兜底；
其余已确认失效的旧 CDN 对象保留原始链接和明确提示，不伪造恢复结果。

## 上游

页面底座来自 [saicaca/fuwari](https://github.com/saicaca/fuwari)，保留 MIT
[LICENSE](LICENSE) 与页脚署名。构建依赖已在迁移时更新，不等同于上游原始锁文件。
