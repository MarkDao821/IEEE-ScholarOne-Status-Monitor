"""测试 ScholarOne 登录表单提交脚本。

测试什么：
- 确认登录脚本里包含 ScholarOne 登录表单需要的关键字段。
- 确认脚本最终会调用 form.submit() 提交表单。

需要填写什么：
- 不需要填写真实 ScholarOne 用户名、密码或网址。
- 这里检查的是脚本文本本身，不会真的访问 ScholarOne。
"""

from ieee_scholarone_monitor.platforms.scholarone import LOGIN_SUBMIT_SCRIPT


def test_login_script_submits_scholarone_form():
    assert "XIK_PREACT" in LOGIN_SUBMIT_SCRIPT
    assert "NEXT_PAGE" in LOGIN_SUBMIT_SCRIPT
    assert "form.submit()" in LOGIN_SUBMIT_SCRIPT
