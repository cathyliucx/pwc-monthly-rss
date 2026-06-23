# PWC Monthly RSS

自动抓取 Papers with Code 指定任务页面中的论文，筛选当前自然月内容，去重后生成 Atom Feed，并通过 GitHub Actions 定时更新、GitHub Pages 对外发布。

## 订阅 Feed

普通使用者不需要克隆仓库、不需要安装 Python，也不需要自行部署。

直接将下面的 Feed 地址添加到 NetNewsWire、Reeder 或其他支持 Atom/RSS 的阅读器：

```text
https://cathyliucx.github.io/pwc-monthly-rss/feed.xml
```

当前监控以下方向：

* Agents
* Reasoning
* Language Modeling
* Reinforcement Learning

项目会每天自动更新两次。

---

## 工作流程

```text
Papers with Code
        ↓
Playwright 渲染任务页面
        ↓
BeautifulSoup 解析论文卡片
        ↓
按任务和关键词过滤
        ↓
仅保留当前自然月论文
        ↓
按论文 URL 去重
        ↓
生成 docs/feed.xml
        ↓
GitHub Actions 定时运行
        ↓
GitHub Pages 发布
```

---

## 项目结构

```text
pwc-monthly-rss/
├── .github/
│   └── workflows/
│       └── update.yml
├── docs/
│   └── feed.xml
├── .gitignore
├── .python-version
├── config.yaml
├── generate_feed.py
├── inspect_html.py
├── pyproject.toml
├── uv.lock
└── README.md
```

| 文件                             | 作用                              |
| ------------------------------ | ------------------------------- |
| `config.yaml`                  | 配置任务页面、筛选关键词、时区和输出路径            |
| `generate_feed.py`             | 抓取、过滤、去重并生成 Atom Feed           |
| `inspect_html.py`              | 保存 Playwright 实际渲染的 HTML 和截图    |
| `docs/feed.xml`                | 最终发布的 Atom Feed                 |
| `.github/workflows/update.yml` | GitHub Actions 自动抓取与 Pages 部署配置 |
| `pyproject.toml`               | Python 项目配置和依赖                  |
| `uv.lock`                      | uv 依赖锁文件                        |
| `.python-version`              | 固定 Python 版本                    |

---

# 开发与自托管

以下内容只适用于：

* 修改筛选规则
* 调试抓取页面
* 参与项目开发
* fork 后发布自己的 Feed

普通订阅者不需要执行这些步骤。

## 环境要求

* macOS 或 Linux
* Git
* Python 3.12
* uv
* Playwright
* Playwright Chromium 浏览器

### 安装 uv

macOS：

```bash
brew install uv
```

检查版本：

```bash
uv --version
```

### 安装 Python 3.12

```bash
uv python install 3.12
uv python pin 3.12
```

检查：

```bash
uv run python --version
```

### 安装项目依赖

```bash
uv sync --locked
```

### 安装 Playwright Chromium

Playwright Python 包和 Chromium 浏览器是两部分。安装依赖后，还需要单独下载 Chromium：

```bash
uv run playwright install chromium
```

检查 Playwright：

```bash
uv run playwright --version
```

Chromium 通常会安装到：

```text
~/Library/Caches/ms-playwright/
```

---

## 本地检查

### 检查 Python 语法

```bash
uv run python -m py_compile \
  inspect_html.py \
  generate_feed.py
```

没有输出通常表示语法检查通过。

### 检查实际页面 HTML

```bash
uv run python inspect_html.py --task Agents
```

生成：

```text
debug/agents.html
debug/agents.png
```

打开截图：

```bash
open debug/agents.png
```

打开 HTML：

```bash
open debug/agents.html
```

检查论文卡片数量：

```bash
grep -o '<article class="paper-card"' debug/agents.html | wc -l
```

检查论文标题数量：

```bash
grep -o 'class="paper-title"' debug/agents.html | wc -l
```

两个结果大于 `0`，通常表示页面抓取正常。

---

## 本地生成 Feed

```bash
uv run python generate_feed.py
```

成功输出示例：

```text
Fetching: Agents
HTTP status: 200
Extracted candidates: 77

Fetching: Reasoning
HTTP status: 200
Extracted candidates: 78

Fetching: Language Modeling
HTTP status: 200
Extracted candidates: 76

Fetching: Reinforcement Learning
HTTP status: 200
Extracted candidates: 77

Current-month unique papers: 23

Wrote 23 entries to docs/feed.xml
```

检查条目数量：

```bash
grep -c '<entry>' docs/feed.xml
```

验证 XML：

```bash
uv run python -c "import xml.etree.ElementTree as ET; ET.parse('docs/feed.xml'); print('feed.xml is valid XML')"
```

打开本地 Feed：

```bash
open docs/feed.xml
```

---

## 当前月份筛选逻辑

项目保留当前自然月论文，而不是最近 30 天。

例如：

```text
2026 年 6 月运行：只保留 2026 年 6 月论文
2026 年 7 月运行：只保留 2026 年 7 月论文
```

核心条件：

```python
paper.published.year == current_year
and
paper.published.month == current_month
```

同一篇论文出现在多个任务页面时，按论文 URL 去重，并合并任务标签。

---

## 任务过滤策略

### Agents

保留该任务页面中的全部论文。

### Reasoning

保留该任务页面中的全部论文。

### Language Modeling

根据 `config.yaml` 中的关键词进一步过滤，例如：

* Large Language Model
* LLM
* Agent
* Reasoning
* Tool Use
* Memory
* Alignment
* Post-training
* Long Context
* Inference Scaling
* Mixture of Experts

### Reinforcement Learning

根据 `config.yaml` 中的关键词进一步过滤，例如：

* LLM
* Agent
* Multi-agent
* RLHF
* RLAIF
* GRPO
* PPO
* Reward Model
* Process Reward
* Verifier
* Preference Optimization

---

## GitHub Actions 自动更新

工作流文件：

```text
.github/workflows/update.yml
```

触发方式：

* 推送到 `main`
* 手动运行
* 每日定时运行两次

定时配置：

```yaml
schedule:
  - cron: "0 0,12 * * *"
```

对应日本时间：

```text
09:00
21:00
```

---

## GitHub Pages 部署

本项目当前已经部署，普通使用者无需重复部署。

只有 fork 项目并希望发布自己 Feed 的用户，才需要配置 GitHub Pages。

仓库需满足：

* 仓库为 Public，或使用支持私有 Pages 的付费方案
* Pages 发布方式为 GitHub Actions
* Workflow 具有 Pages 部署权限

关键权限：

```yaml
permissions:
  contents: read
  pages: write
  id-token: write
```

关键步骤：

```yaml
- name: Configure GitHub Pages
  uses: actions/configure-pages@v5

- name: Upload GitHub Pages artifact
  uses: actions/upload-pages-artifact@v5
  with:
    path: docs
```

部署任务：

```yaml
deploy:
  environment:
    name: github-pages
    url: ${{ steps.deployment.outputs.page_url }}

  runs-on: ubuntu-latest
  needs: build

  steps:
    - name: Deploy GitHub Pages
      id: deployment
      uses: actions/deploy-pages@v4
```

---

## 手动运行工作流

进入：

```text
Repository
→ Actions
→ Update monthly Papers with Code feed
```

点击：

```text
Run workflow
```

选择：

```text
Branch: main
```

再次点击：

```text
Run workflow
```

成功时应看到：

```text
build   ✓
deploy  ✓
```

---

## 验证线上 Feed

检查 HTTP 状态：

```bash
curl -I https://cathyliucx.github.io/pwc-monthly-rss/feed.xml
```

成功时应返回：

```text
HTTP/2 200
```

查看前几行：

```bash
curl -s https://cathyliucx.github.io/pwc-monthly-rss/feed.xml | head -20
```

浏览器打开：

```bash
open https://cathyliucx.github.io/pwc-monthly-rss/feed.xml
```

---

## 在 NetNewsWire 中订阅

打开 NetNewsWire：

```text
File
→ New Feed
```

输入：

```text
https://cathyliucx.github.io/pwc-monthly-rss/feed.xml
```

推荐名称：

```text
PWC — This Month
```

---

## 常见问题

### Feed 生成结果为 0

检查实际 HTML：

```bash
uv run python inspect_html.py --task Agents
```

打开截图：

```bash
open debug/agents.png
```

检查论文卡片：

```bash
grep -o '<article class="paper-card"' debug/agents.html | wc -l
```

### grep 搜索到 403

不要搜索裸的 `403`，因为页面 SVG 数值中也可能包含这三个数字。

使用：

```bash
grep -Eino 'just a moment|checking your browser|verify you are human|attention required|access denied|ray id|cf-chl|challenge-platform' debug/agents.html
```

没有输出通常表示没有遇到 Cloudflare 挑战页面。

### Node.js deprecated warning

GitHub Actions 中可能出现：

```text
Node.js 20 is deprecated
```

这通常只是警告，不一定会导致工作流失败。

判断标准：

```text
黄色圆点：正在运行
绿色勾：成功
红色叉：失败
```

只有步骤显示红色叉时，才需要查看具体错误日志。

### Pages 部署返回 404

确认：

* 仓库为 Public
* Pages 使用 GitHub Actions
* Workflow 包含 `pages: write`
* Workflow 包含 `id-token: write`
* Workflow 包含 `actions/configure-pages@v5`
* build 成功上传 Pages artifact
* deploy 使用 `actions/deploy-pages@v4`

---

## 常用开发命令

重新生成 Feed：

```bash
uv run python generate_feed.py
```

检查 Agents 页面：

```bash
uv run python inspect_html.py --task Agents
```

检查 Reasoning 页面：

```bash
uv run python inspect_html.py --task Reasoning
```

同步依赖：

```bash
uv sync --locked
```

检查锁文件：

```bash
uv lock --check
```

查看依赖：

```bash
uv tree
```

查看 Feed 条目数：

```bash
grep -c '<entry>' docs/feed.xml
```

重建本地环境：

```bash
rm -rf .venv
uv sync --locked
uv run playwright install chromium
```

---

## License

This project is licensed under the MIT License.

Paper titles, abstracts, authorship information, and other metadata retrieved from third-party sources remain subject to the rights and terms of their respective owners and providers.

