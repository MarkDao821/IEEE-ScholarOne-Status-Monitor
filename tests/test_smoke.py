"""测试项目包能否被正常导入。

测试什么：
- 确认 ieee_scholarone_monitor 这个包可以 import。
- 确认当前包版本号符合预期。

需要填写什么：
- 不需要填写任何账号、路径或配置。
- 如果项目版本号发生变化，只需要同步更新这里期望的版本号。
"""

def test_imports_package():
    import ieee_scholarone_monitor

    assert ieee_scholarone_monitor.__version__ == "0.1.0"
