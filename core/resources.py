"""4페이지에 쓰는 자원 계산: 시도별 처리 시간 통계, 측정 조건(이 노트북 정보).

전력(W)은 여기서 계산하지 않는다. CPU 사용률을 W 로 바꾸지 않는다.
"""

import platform

import numpy as np
import psutil

MODE_LABELS = {
    "enroll": "등록", "calibrate": "보정", "monitor": "감시",
    "pointer_enroll": "포인터 등록", "pointer_calibrate": "포인터 보정", "pointer_monitor": "포인터 감시",
}


def processing_stats(rows):
    """시도 기록에서 처리 시간(마이크로초) 통계를 단계별로 구한다.

    돌려주는 값: [{"단계", "시도 수", "중앙값(µs)", "95 백분위수(µs)"}, ...] 마지막 줄은 전체.
    교대 표시 줄처럼 처리 시간이 없는 줄은 뺀다.
    """
    times_by_mode = {}
    for row in rows:
        if row.get("mode") not in MODE_LABELS or not row.get("processing_us"):
            continue
        times_by_mode.setdefault(row["mode"], []).append(float(row["processing_us"]))

    table = []
    for mode, label in MODE_LABELS.items():
        if mode in times_by_mode:
            table.append(stats_row(label, times_by_mode[mode]))
    all_times = [t for times in times_by_mode.values() for t in times]
    if all_times:
        table.append(stats_row("전체", all_times))
    return table


CONDITION_ORDER = ["idle", "detection", "reauth", "edge"]
CONDITION_LABELS = {
    "idle": "idle (앱 꺼짐)",
    "detection": "detection (감시, 재인증 없음)",
    "reauth": "reauth (재인증 2번 성공)",
    "edge": "edge (reauth + Supabase 전송)",
}
NOT_MEASURED = "측정 불가"


def number(text):
    """CSV 의 숫자 칸을 float 로. 비어 있으면 None."""
    return None if text in ("", None) else float(text)


def condition_table(summary_rows):
    """측정 도구의 summary.csv 에서 조건마다 가장 최근 줄을 골라 idle 과의 차이를 붙인다.

    전력은 실제 측정 소스에서 읽힌 경우에만 숫자로 두고, 아니면 "측정 불가".
    """
    latest = {}
    for row in summary_rows:
        if row.get("condition") in CONDITION_ORDER:
            latest[row["condition"]] = row  # 뒤에 있는 줄이 더 최근
    idle = latest.get("idle")
    table = []
    for condition in CONDITION_ORDER:
        if condition not in latest:
            continue
        row = latest[condition]
        cpu = number(row["system_cpu_mean"])
        power = number(row["power_w_mean"]) if row.get("power_source") != NOT_MEASURED else None
        idle_cpu = number(idle["system_cpu_mean"]) if idle else None
        idle_power = None
        if idle and idle.get("power_source") != NOT_MEASURED:
            idle_power = number(idle["power_w_mean"])
        table.append({
            "조건": CONDITION_LABELS[condition],
            "측정 시작": row["started_at"][:16].replace("T", " "),
            "초": int(float(row["seconds"])),
            "시스템 CPU(%)": cpu,
            "앱 CPU(%)": number(row["app_cpu_mean"]),
            "앱 메모리(MB)": number(row["app_rss_mb_mean"]),
            # 아래 세 칸은 숫자와 글자("측정 불가", "기준")가 섞이므로 모두 글자로 적는다
            "전력(W)": NOT_MEASURED if power is None else f"{power:.2f}",
            "전력 소스": row.get("power_source") or NOT_MEASURED,
            "CPU 차이(idle 대비, %p)": diff(cpu, idle_cpu, condition),
            "전력 차이(idle 대비, W)": diff(power, idle_power, condition),
            "전원": row.get("power_supply", ""),
        })
    return table


def diff(value, idle_value, condition):
    """idle 과의 차이를 '+1.92' 처럼 적는다. idle 자신은 '기준', 둘 중 하나라도 없으면 '-'."""
    if condition == "idle":
        return "기준"
    if value is None or idle_value is None:
        return "-"
    return f"{value - idle_value:+.2f}"


def stats_row(label, times):
    return {
        "단계": label,
        "시도 수": len(times),
        "중앙값(µs)": round(float(np.median(times))),
        "95 백분위수(µs)": round(float(np.percentile(times, 95))),
    }


def cpu_model():
    """CPU 이름. Windows 는 레지스트리에서 읽는다(platform.processor 는 이름이 대략적이다)."""
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0")
        return winreg.QueryValueEx(key, "ProcessorNameString")[0].strip()
    except Exception:
        return platform.processor() or "알 수 없음"


def power_source_text(battery):
    """psutil.sensors_battery() 결과를 '전원 어댑터' / '배터리 (22%)' 로 바꾼다."""
    if battery is None:
        return "알 수 없음 (배터리 정보 없음)"
    if battery.power_plugged:
        return f"전원 어댑터 (배터리 {battery.percent:.0f}%)"
    return f"배터리 ({battery.percent:.0f}%)"


def system_info():
    """측정 조건으로 보여줄 이 노트북의 정보."""
    return {
        "CPU": cpu_model(),
        "논리 CPU 수": psutil.cpu_count(),
        "메모리(RAM)": f"{psutil.virtual_memory().total / 1024**3:.1f} GB",
        "전원": power_source_text(psutil.sensors_battery()),
        "운영체제": f"{platform.system()} {platform.release()}",
    }
