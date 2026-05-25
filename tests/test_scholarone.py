from ieee_scholarone_monitor.platforms.scholarone import LOGIN_SUBMIT_SCRIPT


def test_login_script_submits_scholarone_form():
    assert "XIK_PREACT" in LOGIN_SUBMIT_SCRIPT
    assert "NEXT_PAGE" in LOGIN_SUBMIT_SCRIPT
    assert "form.submit()" in LOGIN_SUBMIT_SCRIPT
