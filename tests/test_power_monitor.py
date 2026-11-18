"""측정 도구(tools/power_monitor.py)의 계산과 대상 프로세스 찾기 시험. 장치나 앱 없이 돈다."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import power_monitor as pm  # noqa: E402


class FakeProcess:
    def __init__(self, name, cmdline, cwd):
        self._name, self._cmdline, self._cwd = name, cmdline, cwd

    def name(self):
        return self._name

    def cmdline(self):
        return self._cmdline

    def cwd(self):
        return self._cwd


def test_average_watts_from_picowatt_hours_and_100ns_ticks():
    # 1초(1e7 틱) 동안 1 Wh/3600 = 277,777,777.8 pWh 면 1 W
    earlier = (0, 0)
    later = (round(1e12 / 3600), 10_000_000)
    assert pm.average_watts(earlier, later) == pytest.approx(1.0, rel=1e-6)


def test_average_watts_rejects_bad_readings():
    assert pm.average_watts((100, 10), (200, 10)) is None     # 시간이 그대로
    assert pm.average_watts((200, 10), (100, 20)) is None     # 에너지가 줄어듦


def test_matches_this_projects_streamlit_app():
    project = str(pm.PROJECT)
    app = FakeProcess("python.exe", ["C:\\x\\python.exe", "-m", "streamlit", "run", "app.py"], project)
    assert pm.is_app_process(app) is True
    absolute = FakeProcess("python.exe", ["python.exe", "streamlit-script.py", "run", str(pm.PROJECT / "app.py")], "C:\\")
    assert pm.is_app_process(absolute) is True


def test_does_not_match_other_processes():
    project = str(pm.PROJECT)
    other_app = FakeProcess("python.exe", ["python.exe", "-m", "streamlit", "run", "app.py"], "C:\\other")
    launcher = FakeProcess("streamlit.exe", ["streamlit.exe", "run", "app.py"], project)
    tool = FakeProcess("python.exe", ["python.exe", "tools/power_monitor.py", "check"], project)
    assert pm.is_app_process(other_app) is False
    assert pm.is_app_process(launcher) is False
    assert pm.is_app_process(tool) is False


def test_summary_without_meter_says_not_measured():
    rows = [{"system_cpu": 10, "app_cpu": "", "app_rss_mb": ""}, {"system_cpu": 20, "app_cpu": "", "app_rss_mb": ""}]
    from datetime import datetime
    summary = pm.summarize("idle", datetime.now().astimezone(), 2, rows, [], pm.NOT_MEASURED, [])
    assert summary["system_cpu_mean"] == 15.0
    assert summary["power_w_mean"] == ""
    assert summary["power_source"] == "측정 불가"
    assert set(summary) == set(pm.SUMMARY_COLUMNS)


def test_summary_with_meter_uses_first_channel():
    rows = [{"system_cpu": 10, "app_cpu": 5, "app_rss_mb": 100, "power_w[PKG]": 4.0, "power_w[PP0]": 2.0},
            {"system_cpu": 20, "app_cpu": 7, "app_rss_mb": 102, "power_w[PKG]": 6.0, "power_w[PP0]": 3.0}]
    from datetime import datetime
    summary = pm.summarize("detection", datetime.now().astimezone(), 2, rows, [object()],
                           "Windows EMI M / PKG", ["PKG", "PP0"])
    assert summary["power_w_mean"] == 5.0
    assert summary["power_channels"] == "PKG=5.0; PP0=2.5"
    assert summary["app_cpu_mean"] == 6.0
