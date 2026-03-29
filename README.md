# X-CrawlFox 🦊

基于 Camoufox 的 X (Twitter) 拟人化爬虫命令行工具。

**特点**：免费、支持高度定制、增量爬取、内置拟人化行为防风控。

---

## 🚀 主要功能特性

- **拟人化交互**：集成 Camoufox 指纹混淆，模拟真人滚动、随机延迟、键入交互，大幅降低风控风险。
- **时间线抓取**：支持爬取“正在关注 (Following)”和“为您推荐 (For you)”的内容，支持指定抓取数量。
- **深度新闻爬取**：自动抓取“今日新闻 (Today's News)”侧边栏，支持点击进入详情页获取 Grok 摘要及相关热门帖子。
- **增量账号监控**：支持多账号监控，自动追踪上次爬取位置，仅抓取新发布的推文。
- **一键全量任务**：通过 JSON 配置文件，一键启动包含时间线、新闻、多账号监控在内的复合爬取任务。
- **自动状态管理**：自动保存登录会话 (Storage State) 和爬取进度 (Crawler State)。

---

## 📦 安装与准备

本项目使用 `uv` 进行包管理。

1. **克隆项目并安装依赖**：
   ```bash
   git clone <repository-url>
   cd x-crawlfox
   uv sync
   ```

2. **安装浏览器驱动（首次启动会自动下载）**：
   ```bash
   uv run playwright install firefox
   ```

---

## 📂 存储与配置 (.x-crawlfox)

为了保护隐私并支持持久化，X-CrawlFox 使用 `.x-crawlfox` 文件夹存储敏感数据（登录 Session 和爬取进度）：

1. **存储位置**：
   - **局部模式**：程序优先检查当前运行目录下是否存在 `.x-crawlfox` 文件夹。如果存在，则所有数据存放在此处（适合多账号隔离）。
   - **全局模式**：如果当前目录没有该文件夹，程序会自动使用用户主目录下的 `~/.x-crawlfox`（Windows 为 `%USERPROFILE%\.x-crawlfox`）。

2. **存储内容**：
   - `storage_state.json`：存储 X 的登录 Cookie 和认证令牌。**请勿泄露此文件**。
   - `crawler_state.json`：存储每个监控账号已爬取的最后一条推文 ID，用于实现增量抓取。

---

## 🛠️ 使用说明

### 1. 账号登录或cookie导出（必备）
在进行任何爬取前，需先完成手动登录以保存会话：
```bash
uv run x-crawlfox x login --no-headless
```
在弹出的窗口中登录 X，完成后回到终端按回车保存状态。

**注意**：如果使用刚注册的账号登录，很容易免被 X 封禁。

如果登陆的过程中被x拦截（识别为可疑的登陆），无法完成登陆，可通过浏览器插件Cookie Editor导出真实使用浏览器的Cookie为json，并保存至storage_state.json文件中。
![Cookie Editor](./docs/images/cookie-editor-export.jpg)
### 2. 爬取个人时间线
```bash
# 爬取“关注”页前 20 条
uv run x-crawlfox x timeline --type Following --max-items 20

# 爬取“推荐”页
uv run x-crawlfox x timeline --type "For you" --max-items 50
```

### 3. 爬取今日新闻
```bash
# 仅爬取侧边栏列表
uv run x-crawlfox x news

# 深度爬取：进入详情页抓取摘要和相关帖子
uv run x-crawlfox x news --detail --max-items 3
```

### 4. 抓取/监控指定用户
```bash
# 抓取指定用户最新的 20 条推文
uv run x-crawlfox x user elonmusk --max-tweets 20

# 增量抓取：仅抓取该用户自上次运行以来发布的新内容
uv run x-crawlfox x user elonmusk --only-new
```

### 5. 一键执行复合任务
编辑 `crawl_config.json`（见下文），然后运行：
```bash
uv run x-crawlfox x all --config crawl_config.json
```

---

## ⚙️ 配置文件示例 (`crawl_config.json`)

```json
{
    "timeline": [
        { "type": "Following", "max_items": 10 },
        { "type": "For you", "max_items": 10 }
    ],
    "news": {
        "enabled": true,
        "detail": true,
        "max_items": 5
    },
    "monitor": [
        { "username": "elonmusk", "only_new": true, "max_tweets": 10 },
        { "username": "OpenAI", "only_new": true, "max_tweets": 5 }
    ]
}
```

---

## 🛡️ 防风控与鲁棒性优化

- **内存释放**：在多账号监控间隙自动跳转 `about:blank`，强制释放 X 平台庞大的 React 内存堆，防止长时间运行崩溃。
- **自动恢复**：检测到 `Target page closed` 或页面报错时，系统会自动尝试重建页面或点击 `Retry` 按钮。
- **异步等待**：全量使用 Playwright 的非阻塞 `wait_for_timeout` 机制，提升自动化执行的稳定性。
- **随机行为**：内置随机滚动距离、随机停顿时间以及拟人化的鼠标移动。

---

## 📁 数据输出
所有抓取结果均以 `.jsonl` 格式保存于 `output/` 目录下，方便进行后续的数据分析或入库。

---

## 🙏 感谢

This project integrates and references these excellent open-source projects:

- [Camoufox](https://github.com/daijro/camoufox): Powerful browser fingerprint obfuscation and human-like interaction.
- [Playwright](https://playwright.dev/): Fast and robust automation and scraping framework.
- [uv](https://github.com/astral-sh/uv): Extremely efficient Python package manager.
- [Loguru](https://github.com/Delgan/loguru) & [Typer](https://typer.tiangolo.com/): For elegant logging and CLI interactions.

---

## ⚠️ 免责声明
本工具仅供学习和研究目的使用。请遵守 X (Twitter) 的服务条款。因使用本工具导致的账号限制或法律纠纷，由使用者自行承担。
