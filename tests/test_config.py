"""测试配置文件和环境变量的读取。

测试什么：
- 从 journals.toml 读取期刊账号配置。
- 从环境变量读取微信或邮件通知配置。
- 缺少必要配置或运行模式非法时是否报 ConfigError。

需要填写什么：
- 不需要填写真实账号、密码、token 或邮箱。
- 测试会用 monkeypatch 临时设置假的环境变量，例如 TCYB_USERNAME。
- 新增配置测试时，也请使用 example.test、example.com 和 fake credential。
"""

from pathlib import Path

import pytest

from ieee_scholarone_monitor.config import ConfigError, load_config


def test_load_config_reads_journal_accounts(tmp_path, monkeypatch):
    journals = tmp_path / "journals.toml"
    journals.write_text(
        """
[[journals]]
key = "ieee-tcyb"
name = "IEEE TCYB"
platform = "scholarone"
url = "https://mc.manuscriptcentral.com/cyb-ieee"
username_env = "TCYB_USERNAME"
password_env = "TCYB_PASSWORD"
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setenv("TCYB_USERNAME", "alice")
    monkeypatch.setenv("TCYB_PASSWORD", "secret")
    monkeypatch.setenv("WECHAT_PROVIDER", "serverchan")
    monkeypatch.setenv("WECHAT_TOKEN", "send-key")
    monkeypatch.setenv("RUN_MODE", "daily_report")

    config = load_config(env_file=None, journals_file=journals)

    assert config.journals[0].name == "IEEE TCYB"
    assert config.journals[0].username == "alice"
    assert config.run_mode == "daily_report"


def test_load_config_reads_email_notification_settings(tmp_path, monkeypatch):
    journals = tmp_path / "journals.toml"
    journals.write_text(
        """
[[journals]]
key = "ieee-tcyb"
name = "IEEE TCYB"
platform = "scholarone"
url = "https://mc.manuscriptcentral.com/cyb-ieee"
username_env = "TCYB_USERNAME"
password_env = "TCYB_PASSWORD"
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setenv("TCYB_USERNAME", "alice")
    monkeypatch.setenv("TCYB_PASSWORD", "secret")
    monkeypatch.setenv("NOTIFY_PROVIDER", "email")
    monkeypatch.setenv("EMAIL_SMTP_HOST", "smtp.gmail.com")
    monkeypatch.setenv("EMAIL_SMTP_PORT", "587")
    monkeypatch.setenv("EMAIL_USERNAME", "sender@example.com")
    monkeypatch.setenv("EMAIL_PASSWORD", "fake-email-credential")
    monkeypatch.setenv("EMAIL_FROM", "sender@example.com")
    monkeypatch.setenv("EMAIL_TO", "one@example.com, two@example.com;three@example.com")

    config = load_config(env_file=None, journals_file=journals)

    assert config.notify_provider == "email"
    assert config.email_smtp_host == "smtp.gmail.com"
    assert config.email_smtp_port == 587
    assert config.email_username == "sender@example.com"
    assert config.email_password == "fake-email-credential"
    assert config.email_from == "sender@example.com"
    assert config.email_to == (
        "one@example.com",
        "two@example.com",
        "three@example.com",
    )


def test_load_config_rejects_missing_email_recipient(tmp_path, monkeypatch):
    journals = tmp_path / "journals.toml"
    journals.write_text(
        """
[[journals]]
key = "ieee-tcyb"
name = "IEEE TCYB"
platform = "scholarone"
url = "https://mc.manuscriptcentral.com/cyb-ieee"
username_env = "TCYB_USERNAME"
password_env = "TCYB_PASSWORD"
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setenv("TCYB_USERNAME", "alice")
    monkeypatch.setenv("TCYB_PASSWORD", "secret")
    monkeypatch.setenv("NOTIFY_PROVIDER", "email")
    monkeypatch.setenv("EMAIL_SMTP_HOST", "smtp.gmail.com")
    monkeypatch.setenv("EMAIL_SMTP_PORT", "587")
    monkeypatch.setenv("EMAIL_USERNAME", "sender@example.com")
    monkeypatch.setenv("EMAIL_PASSWORD", "fake-email-credential")
    monkeypatch.setenv("EMAIL_FROM", "sender@example.com")
    monkeypatch.delenv("EMAIL_TO", raising=False)

    with pytest.raises(ConfigError, match="EMAIL_TO"):
        load_config(env_file=None, journals_file=journals)


def test_load_config_rejects_missing_journal_secret(tmp_path, monkeypatch):
    journals = tmp_path / "journals.toml"
    journals.write_text(
        """
[[journals]]
key = "ieee-tcyb"
name = "IEEE TCYB"
platform = "scholarone"
url = "https://mc.manuscriptcentral.com/cyb-ieee"
username_env = "TCYB_USERNAME"
password_env = "TCYB_PASSWORD"
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setenv("TCYB_USERNAME", "alice")
    monkeypatch.delenv("TCYB_PASSWORD", raising=False)
    monkeypatch.setenv("WECHAT_PROVIDER", "serverchan")
    monkeypatch.setenv("WECHAT_TOKEN", "send-key")

    with pytest.raises(ConfigError, match="TCYB_PASSWORD"):
        load_config(env_file=None, journals_file=journals)


def test_load_config_rejects_invalid_mode(tmp_path, monkeypatch):
    journals = Path(tmp_path / "journals.toml")
    journals.write_text("[[journals]]\n", encoding="utf-8")
    monkeypatch.setenv("RUN_MODE", "sometimes")
    monkeypatch.setenv("WECHAT_PROVIDER", "serverchan")
    monkeypatch.setenv("WECHAT_TOKEN", "send-key")

    with pytest.raises(ConfigError, match="RUN_MODE"):
        load_config(env_file=None, journals_file=journals)
