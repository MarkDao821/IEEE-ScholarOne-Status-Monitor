# GitHub Actions 定时推送

本文说明如何用 GitHub Actions 定时运行本项目，并把 ScholarOne 当前状态推送到微信或邮箱。

适合场景：

- 不想让本地电脑一直开机。
- 希望每天固定时间收到一次 `report` 当前状态报告。
- ScholarOne 账号可以在云端无人工验证地登录。

不太适合场景：

- ScholarOne 经常需要 Cloudflare 或人工验证。
- 你希望稳定复用本地浏览器登录会话。
- 你希望默认只在状态变化时推送。GitHub Actions 运行环境是临时的，`data/status.json` 默认不会保留。

## 1. 添加 workflow 文件

在仓库中创建：

```text
.github/workflows/scheduled-report.yml
```

内容示例：

```yaml
name: Scheduled ScholarOne Report

on:
  schedule:
    # GitHub Actions cron uses UTC. 01:00 UTC is 09:00 in Asia/Shanghai.
    - cron: "0 1 * * *"
  workflow_dispatch:

jobs:
  report:
    runs-on: windows-latest
    timeout-minutes: 30

    steps:
      - name: Check out repository
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: "pip"

      - name: Install dependencies
        run: python -m pip install -e .

      - name: Install Playwright browser
        run: python -m playwright install chromium

      - name: Create .env
        shell: pwsh
        run: |
          @'
          ${{ secrets.ENV_FILE }}
          '@ | Set-Content -Path .env -Encoding utf8

      - name: Create journals.toml
        shell: pwsh
        run: |
          @'
          ${{ secrets.JOURNALS_TOML }}
          '@ | Set-Content -Path journals.toml -Encoding utf8

      - name: Send scheduled report
        run: python -m ieee_scholarone_monitor report
```

这个 workflow 会：

- 定时运行。
- 支持在 GitHub 页面手动运行。
- 安装项目依赖和 Playwright Chromium。
- 从 GitHub Secrets 临时生成 `.env` 和 `journals.toml`。
- 执行 `python -m ieee_scholarone_monitor report`。

运行结束后，GitHub 的临时机器会被销毁，生成的 `.env`、`journals.toml`、`data/status.json` 和 `logs/` 默认不会上传回仓库。

## 2. 设置推送时间

GitHub Actions 的 `cron` 使用 UTC 时间，不是北京时间。

北京时间是 UTC+8，所以：

| 北京时间 | UTC cron |
| --- | --- |
| 每天 08:00 | `0 0 * * *` |
| 每天 09:00 | `0 1 * * *` |
| 每天 12:30 | `30 4 * * *` |
| 每天 20:00 | `0 12 * * *` |

例如每天北京时间 09:00 推送：

```yaml
on:
  schedule:
    - cron: "0 1 * * *"
  workflow_dispatch:
```

如果想每天两次，例如北京时间 09:00 和 20:00：

```yaml
on:
  schedule:
    - cron: "0 1 * * *"
    - cron: "0 12 * * *"
  workflow_dispatch:
```

GitHub Actions 定时任务可能不会精确到秒，繁忙时可能会延迟几分钟。

## 3. 设置 GitHub Secrets

进入 GitHub 仓库页面：

```text
Settings -> Secrets and variables -> Actions -> Repository secrets
```

注意要放在 `Repository secrets`，不要放在 `Environment secrets`。如果放在 `Environment secrets`，除非 workflow 显式配置 `environment`，否则读不到。

需要新增两个 Secret：

| Secret 名称 | 内容 |
| --- | --- |
| `ENV_FILE` | 完整 `.env` 内容 |
| `JOURNALS_TOML` | 完整 `journals.toml` 内容 |

保存后再次打开 Secret，GitHub 不会显示原文，看起来像空白。这是正常的安全设计。只要列表里能看到 Secret 名称和更新时间，就说明已经保存。

## 4. ENV_FILE 示例

如果使用 Server Chan Turbo：

```dotenv
NOTIFY_PROVIDER=wechat
WECHAT_PROVIDER=serverchan
WECHAT_TOKEN=your_server_chan_send_key

RUN_MODE=daily_report
HEADLESS=true
JOURNALS_FILE=journals.toml

TCYB_USERNAME=your_scholarone_username
TCYB_PASSWORD=your_scholarone_password
```

如果使用 PushPlus：

```dotenv
NOTIFY_PROVIDER=wechat
WECHAT_PROVIDER=pushplus
WECHAT_TOKEN=your_pushplus_token

RUN_MODE=daily_report
HEADLESS=true
JOURNALS_FILE=journals.toml

TCYB_USERNAME=your_scholarone_username
TCYB_PASSWORD=your_scholarone_password
```

如果使用邮件：

```dotenv
NOTIFY_PROVIDER=email
EMAIL_SMTP_HOST=smtp.gmail.com
EMAIL_SMTP_PORT=587
EMAIL_USERNAME=your_gmail_address@gmail.com
EMAIL_PASSWORD=your_google_app_password
EMAIL_FROM=your_gmail_address@gmail.com
EMAIL_TO=recipient1@example.com,recipient2@example.com

RUN_MODE=daily_report
HEADLESS=true
JOURNALS_FILE=journals.toml

TCYB_USERNAME=your_scholarone_username
TCYB_PASSWORD=your_scholarone_password
```

如果配置多个期刊，就继续添加对应的账号密码变量：

```dotenv
TCYB_USERNAME=your_tcyb_username
TCYB_PASSWORD=your_tcyb_password

TNNLS_USERNAME=your_tnnls_username
TNNLS_PASSWORD=your_tnnls_password
```

## 5. JOURNALS_TOML 示例

单个期刊：

```toml
[[journals]]
key = "ieee-tcyb"
name = "IEEE TCYB"
platform = "scholarone"
url = "https://mc.manuscriptcentral.com/cyb-ieee"
username_env = "TCYB_USERNAME"
password_env = "TCYB_PASSWORD"
```

多个期刊：

```toml
[[journals]]
key = "ieee-tcyb"
name = "IEEE TCYB"
platform = "scholarone"
url = "https://mc.manuscriptcentral.com/cyb-ieee"
username_env = "TCYB_USERNAME"
password_env = "TCYB_PASSWORD"

[[journals]]
key = "ieee-tnnls"
name = "IEEE TNNLS"
platform = "scholarone"
url = "https://mc.manuscriptcentral.com/tnnls"
username_env = "TNNLS_USERNAME"
password_env = "TNNLS_PASSWORD"
```

`username_env` 和 `password_env` 的值必须和 `ENV_FILE` 里的变量名完全一致。

## 6. 手动运行一次

提交 workflow 后，进入：

```text
Actions -> Scheduled ScholarOne Report -> Run workflow
```

选择 `main` 分支，然后点击绿色的 `Run workflow`。

运行失败时，点击失败的 job，再展开红色步骤查看具体日志。

## 7. 常见问题

### Missing required configuration: WECHAT_PROVIDER

说明 `ENV_FILE` 中没有 `WECHAT_PROVIDER`，或者 workflow 没有读到 `ENV_FILE`。

检查：

- Secret 名称必须是 `ENV_FILE`。
- Secret 应放在 `Repository secrets`。
- `ENV_FILE` 里应包含 `NOTIFY_PROVIDER=wechat` 和 `WECHAT_PROVIDER=serverchan` 或 `WECHAT_PROVIDER=pushplus`。

### Missing required environment variable: TCYB_USERNAME

说明 `JOURNALS_TOML` 里引用了：

```toml
username_env = "TCYB_USERNAME"
```

但 `ENV_FILE` 里没有：

```dotenv
TCYB_USERNAME=...
```

变量名要完全一致。

### Cloudflare human verification is required

说明 ScholarOne 需要人工验证。GitHub Actions 是云端无头环境，通常无法完成这种验证。

这种情况下更建议使用 Windows Task Scheduler 在本地运行，并通过：

```powershell
.\.venv\Scripts\python.exe -m ieee_scholarone_monitor reauth
```

刷新本地浏览器会话。

### 为什么每次都会推送

示例 workflow 使用的是：

```powershell
python -m ieee_scholarone_monitor report
```

`report` 的设计就是每次发送当前状态报告。

如果改成：

```powershell
python -m ieee_scholarone_monitor check
```

理论上可以只在变化时推送，但 GitHub Actions 默认不会保留 `data/status.json`，每次运行都像第一次运行。要实现可靠的变化检测，需要额外配置 cache、artifact、外部存储，或把状态文件提交回私有仓库。状态文件可能包含真实稿件信息，不建议提交到公开仓库。
