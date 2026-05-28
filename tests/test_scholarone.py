"""测试 ScholarOne 登录表单提交脚本。

测试什么：
- 确认登录脚本里包含 ScholarOne 登录表单需要的关键字段。
- 确认脚本最终会调用 form.submit() 提交表单。

需要填写什么：
- 不需要填写真实 ScholarOne 用户名、密码或网址。
- 这里检查的是脚本文本本身，不会真的访问 ScholarOne。
"""

from playwright.sync_api import Error as PlaywrightError

from ieee_scholarone_monitor.platforms.scholarone import LOGIN_SUBMIT_SCRIPT, _save_failure_artifacts


def test_login_script_submits_scholarone_form():
    assert "XIK_PREACT" in LOGIN_SUBMIT_SCRIPT
    assert "NEXT_PAGE" in LOGIN_SUBMIT_SCRIPT
    assert "form.submit()" in LOGIN_SUBMIT_SCRIPT


class _NavigatingLocator:
    def evaluate_all(self, script):
        raise PlaywrightError("Execution context was destroyed")


class _ArtifactPage:
    def locator(self, selector):
        return _NavigatingLocator()

    def screenshot(self, path, full_page):
        with open(path, "wb") as handle:
            handle.write(b"png")

    def content(self):
        return "<input value='secret'>"


def test_failure_artifacts_tolerate_navigation_during_redaction(tmp_path):
    _save_failure_artifacts(_ArtifactPage(), tmp_path, ("secret",))

    html_files = list((tmp_path / "pages").glob("failure-*.html"))
    assert len(html_files) == 1
    assert "secret" not in html_files[0].read_text(encoding="utf-8")
