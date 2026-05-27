<div align="center">

# IEEE ScholarOne 投稿状态监控器

本地运行的 IEEE ScholarOne / Manuscript Central 投稿状态监控工具。

从投稿系统读取稿件状态，保存本地快照，并在首次建立基线或状态变化时通过微信或邮件推送通知。

![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB)
![Playwright](https://img.shields.io/badge/Playwright-Chromium-45ba4b)
![Notifications](https://img.shields.io/badge/Notify-ServerChan%20%7C%20PushPlus%20%7C%20Email-orange)
![Platform](https://img.shields.io/badge/Platform-Windows%20friendly-blue)

[English](README.md) | 中文

</div>

## 功能

- 支持配置多个使用 ScholarOne / Manuscript Central 的期刊。
- 自动读取稿件编号、标题、当前状态、创建时间、提交时间等信息。
- 将最新状态保存到本地 `data/status.json`。
- 对比上一次快照，识别首次基线、新增稿件、状态变化和稿件消失。
- 支持 Server Chan Turbo、PushPlus 和 SMTP 邮件通知。
- 失败时保存脱敏 HTML 和截图，方便排查登录或页面解析问题。
- 支持复用浏览器会话，减少重复登录和 Cloudflare 验证。
- 提供 Windows 任务计划程序示例，便于定时运行。

## 效果示例

截图中的稿件编号、标题和链接已做脱敏处理。

| 邮件推送 | Server Chan Turbo | PushPlus / 微信设备通知 |
| --- | --- | --- |
| ![Email notification example](docs/assets/email-notification-example.png) | ![Server Chan notification example](docs/assets/wechat-notification-example-1.png) | ![PushPlus notification example](docs/assets/wechat-notification-example-2.png) |

## 安装

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m playwright install chromium
Copy-Item .env.example .env
Copy-Item journals.example.toml journals.toml
```

如果 Playwright 自带的 Chromium 未安装成功，程序会尝试回退使用系统里的 Microsoft Edge。

## 配置期刊

编辑 `journals.toml`：

```toml
[[journals]]
key = "ieee-tcyb"
name = "IEEE TCYB"
platform = "scholarone"
url = "https://mc.manuscriptcentral.com/cyb-ieee"
username_env = "TCYB_USERNAME"
password_env = "TCYB_PASSWORD"
```

字段说明：

- `key`：本地使用的期刊唯一标识。
- `name`：通知里显示的期刊名称。
- `platform`：目前支持 `scholarone`。
- `url`：期刊 ScholarOne 投稿系统地址。
- `username_env` / `password_env`：从 `.env` 读取账号密码时使用的环境变量名。

如果要添加更多期刊，继续增加 `[[journals]]` 配置块即可。

## 配置通知

编辑 `.env`。你可以选择微信类推送或邮件推送。

### Server Chan Turbo

1. 打开 [Server Chan Turbo](https://sct.ftqq.com/)。
2. 登录后进入 [SendKey 页面](https://sct.ftqq.com/sendkey)。
3. 复制自己的 `SendKey`。
4. 在 `.env` 中填写：

```dotenv
NOTIFY_PROVIDER=wechat
WECHAT_PROVIDER=serverchan
WECHAT_TOKEN=your_server_chan_send_key
```

### PushPlus

1. 打开 [PushPlus](https://www.pushplus.plus/)。
2. 登录后进入「一对一推送」或个人资料页面。
3. 复制自己的 `token`。也可以参考 [PushPlus 官方文档](https://www.pushplus.plus/doc/)。
4. 在 `.env` 中填写：

```dotenv
NOTIFY_PROVIDER=wechat
WECHAT_PROVIDER=pushplus
WECHAT_TOKEN=your_pushplus_token
```

### Gmail 邮件

Gmail 不建议直接使用账号密码发送 SMTP 邮件，应使用应用专用密码。

1. 确认 Google 账号已开启两步验证。
2. 打开 [Google 应用专用密码帮助](https://support.google.com/accounts/answer/185833)。
3. 进入 [应用专用密码页面](https://myaccount.google.com/apppasswords)。
4. 创建一个用于本项目的应用专用密码。
5. 在 `.env` 中填写：

```dotenv
NOTIFY_PROVIDER=email
EMAIL_SMTP_HOST=smtp.gmail.com
EMAIL_SMTP_PORT=587
EMAIL_USERNAME=your_gmail_address@gmail.com
EMAIL_PASSWORD=your_google_app_password
EMAIL_FROM=your_gmail_address@gmail.com
EMAIL_TO=recipient1@example.com,recipient2@example.com
```

`EMAIL_TO` 支持多个收件人，可用英文逗号或分号分隔。

### 投稿系统账号

无论使用哪种通知方式，都需要在 `.env` 中填写期刊账号变量。变量名应与 `journals.toml` 中的 `username_env` / `password_env` 对应：

```dotenv
RUN_MODE=normal
TCYB_USERNAME=your_scholarone_username
TCYB_PASSWORD=your_scholarone_password
```

## 常用命令

测试通知是否可用：

```powershell
.\.venv\Scripts\python.exe -m ieee_scholarone_monitor test
```

执行一次正常检查。只有首次建立基线或检测到状态变化时才会通知：

```powershell
.\.venv\Scripts\python.exe -m ieee_scholarone_monitor check
```

强制发送当前状态报告，即使状态没有变化也会通知：

```powershell
.\.venv\Scripts\python.exe -m ieee_scholarone_monitor report
```

可见浏览器模式，适合登录调试：

```powershell
.\.venv\Scripts\python.exe -m ieee_scholarone_monitor --debug check
```

保存成功页面的诊断信息：

```powershell
.\.venv\Scripts\python.exe run_monitor.py --dump report
```

这会在 `logs/dumps` 下保存截图、脱敏 HTML 和解析出的表格行。

## Cloudflare 验证处理

有些 ScholarOne 站点可能会出现 Cloudflare 真人验证。程序不会自动绕过或模拟点击验证；这是网站的安全机制。

程序会复用浏览器会话目录：

```text
data/browser-profile
```

如果后台运行时遇到 Cloudflare 验证，程序会：

- 不覆盖已有的 `data/status.json`；
- 发送一条 `IEEE ScholarOne Monitor Needs Attention` 通知；
- 提醒你刷新一次浏览器会话。

刷新会话：

```powershell
.\.venv\Scripts\python.exe -m ieee_scholarone_monitor reauth
```

运行后会打开可见浏览器。手动完成验证后，程序会保存新的浏览器会话，后续 `check` / `report` 会继续复用该会话。

如果验证时间不够，可在 `.env` 中调整：

```dotenv
CHALLENGE_TIMEOUT_SECONDS=180
```

## 运行文件

- `.env`：本地密钥、账号和运行配置。不要提交到 Git。
- `journals.toml`：本地期刊列表。如果包含私人配置，建议不要提交。
- `data/status.json`：最新状态快照。不要提交。
- `data/browser-profile`：浏览器会话数据，可能包含 cookie/session。不要提交。
- `logs/app.log`：运行日志。
- `logs/screenshots` 和 `logs/pages`：失败诊断截图和脱敏 HTML。不要提交。

## 定时运行

Windows 用户可以参考：

```text
docs/windows-task-scheduler.md
```

常见方式：

- 每天固定时间运行 `report`，发送当前状态报告。
- 每天多次运行 `check`，只在状态变化时通知。

## 测试

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

如果你的 Windows 临时目录存在权限问题，可以指定一个新的临时目录：

```powershell
$base = Join-Path (Resolve-Path .).Path (".pytest-run-" + [guid]::NewGuid().ToString("N"))
.\.venv\Scripts\python.exe -m pytest -q --basetemp $base -p no:cacheprovider
```

## 安全与开源提醒

开源或提交代码前，请确认没有包含以下内容：

- `.env`
- `journals.toml`
- `data/`
- `logs/`
- 浏览器 profile
- 真实 ScholarOne 账号密码
- 推送 token
- 邮箱应用专用密码
- 真实稿件编号、论文标题或页面诊断文件

建议只提交 `.env.example` 和 `journals.example.toml` 作为配置模板。

## 免责声明

请在遵守 ScholarOne、期刊网站和通知服务条款的前提下使用本工具。本项目不会提供绕过验证码、绕过 Cloudflare 或规避网站安全机制的能力。
