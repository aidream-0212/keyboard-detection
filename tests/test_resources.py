"""4페이지 자원 계산 시험."""

from collections import namedtuple

import pytest

from core import resources

Battery = namedtuple("Battery", "percent secsleft power_plugged")


def test_processing_stats_by_mode_and_overall():
    rows = [
        {"mode": "enroll", "processing_us": "100"},
        {"mode": "enroll", "processing_us": "300"},
        {"mode": "monitor", "processing_us": "200"},
        {"mode": "marker", "processing_us": ""},       # 교대 표시는 빼야 한다
    ]
    table = resources.processing_stats(rows)
    assert [r["단계"] for r in table] == ["등록", "감시", "전체"]
    assert table[0]["시도 수"] == 2
    assert table[0]["중앙값(µs)"] == 200
    assert table[0]["95 백분위수(µs)"] == 290              # 100 + 0.95*(300-100)
    assert table[-1]["시도 수"] == 3
    assert table[-1]["중앙값(µs)"] == 200


def test_processing_stats_empty_log():
    assert resources.processing_stats([]) == []


def test_power_source_text():
    assert resources.power_source_text(Battery(80, 0, True)) == "전원 어댑터 (배터리 80%)"
    assert resources.power_source_text(Battery(22, 3000, False)) == "배터리 (22%)"
    assert resources.power_source_text(None).startswith("알 수 없음")


def test_system_info_has_the_conditions():
    info = resources.system_info()
    assert set(info) == {"CPU", "논리 CPU 수", "메모리(RAM)", "전원", "운영체제"}
    assert info["논리 CPU 수"] >= 1


def summary_row(condition, cpu, power, source, started="2026-11-18T10:00:00+09:00"):
    return {"condition": condition, "started_at": started, "seconds": "60",
            "system_cpu_mean": str(cpu), "app_cpu_mean": "", "app_rss_mb_mean": "",
            "power_w_mean": "" if power is None else str(power), "power_source": source,
            "power_supply": "전원 어댑터 (80%)"}


def test_condition_table_orders_conditions_and_diffs_from_idle():
    rows = [
        summary_row("detection", 12.0, 6.5, "Windows EMI X / PKG"),
        summary_row("idle", 4.0, 3.0, "Windows EMI X / PKG"),
        summary_row("idle", 5.0, 3.5, "Windows EMI X / PKG", started="2026-11-18T11:00:00+09:00"),  # 더 최근
    ]
    table = resources.condition_table(rows)
    assert [r["조건"].split()[0] for r in table] == ["idle", "detection"]
    assert table[0]["시스템 CPU(%)"] == 5.0              # idle 은 가장 최근 줄
    assert table[0]["CPU 차이(idle 대비, %p)"] == "기준"
    assert table[1]["CPU 차이(idle 대비, %p)"] == "+7.00"
    assert table[1]["전력(W)"] == "6.50"
    assert table[1]["전력 차이(idle 대비, W)"] == "+3.00"
    assert table[1]["전력 소스"] == "Windows EMI X / PKG"


def test_power_is_not_shown_without_a_real_source():
    rows = [summary_row("idle", 4.0, None, "측정 불가"), summary_row("reauth", 9.0, None, "측정 불가")]
    table = resources.condition_table(rows)
    assert table[1]["전력(W)"] == "측정 불가"
    assert table[1]["전력 차이(idle 대비, W)"] == "-"
    assert table[1]["CPU 차이(idle 대비, %p)"] == "+5.00"


@pytest.mark.parametrize("name", ["power_w", "watts", "estimated_power"])
def test_no_watt_conversion_in_resources(name):
    # CPU 사용률을 W 로 바꾸는 함수를 두지 않는다
    assert not hasattr(resources, name)
