"""4페이지: 자원·전력. 탐지가 이 노트북에서 얼마나 드는지 보여준다.

전력(W)은 실제 측정 소스에서 읽힌 값만 쓰고, 소스 이름을 옆에 적는다. 없으면 "측정 불가".
CPU 사용률을 W 로 바꾸지 않는다.
"""

import os

import psutil
import streamlit as st

from core import resources, storage

LIVE_SECONDS = 2


def show():
    st.title("4 자원·전력")
    show_conditions()
    live_usage()
    show_processing_times()
    show_condition_summary()


def show_conditions():
    st.subheader("측정 조건")
    info = resources.system_info()
    st.table({"항목": list(info), "값": [str(v) for v in info.values()]})
    st.info(
        "키보드 입력 자체(브라우저가 키를 받아 화면을 다시 그리는 일)도 CPU 를 씁니다. "
        "그래서 '앱을 켜지 않은 상태'와 '감시 중' 사이의 차이에는 탐지 계산 말고도 입력 처리 부담이 함께 들어 있습니다. "
        "탐지 계산만의 비용은 아래 '시도별 처리 시간'으로 따로 봅니다."
    )


@st.cache_resource
def app_process():
    """이 Streamlit 앱의 파이썬 프로세스. CPU 사용률은 직전 호출과의 차이로 계산된다."""
    process = psutil.Process(os.getpid())
    process.cpu_percent(None)  # 첫 호출은 기준점만 잡는다
    return process


@st.fragment(run_every=LIVE_SECONDS)
def live_usage():
    """앱 프로세스의 CPU 와 메모리를 2초마다 다시 읽는다."""
    st.subheader("앱 프로세스 실시간 사용량")
    process = app_process()
    cpu = process.cpu_percent(None)
    rss_mb = process.memory_info().rss / 1024**2
    col1, col2 = st.columns(2)
    col1.metric("CPU (코어 1개 = 100%)", f"{cpu:.1f}%")
    col2.metric("메모리 (RSS)", f"{rss_mb:.0f} MB")
    st.caption(
        f"PID {process.pid}, {LIVE_SECONDS}초마다 갱신. "
        "전력은 이 화면에서 따로 읽지 않고, 아래 조건별 측정 결과에서 실제 측정 소스로 읽힌 값만 보여줍니다."
    )


def show_processing_times():
    st.subheader("시도별 처리 시간 (탐지 계산만)")
    rows = storage.read_csv_rows(storage.ATTEMPTS_PATH)
    table = resources.processing_stats(rows)
    if not table:
        st.caption("아직 시도 기록이 없습니다.")
        return
    st.dataframe(table, hide_index=True, alt="단계별 시도 처리 시간 통계")
    st.caption(
        "Enter 를 뗀 시도 한 번을 파이썬이 받아 제외 여부 확인, 특징 추출, 점수 계산, 판정까지 한 시간입니다. "
        "1,000µs = 1ms. 화면을 다시 그리는 시간은 들어 있지 않습니다."
    )


SUMMARY_PATH = storage.DATA_DIR.parent / "power_experiment" / "summary.csv"


def show_condition_summary():
    st.subheader("조건별 측정 결과")
    table = resources.condition_table(storage.read_csv_rows(SUMMARY_PATH))
    if not table:
        st.caption(
            "아직 측정 결과가 없습니다. 프로젝트 폴더에서 "
            "`python tools/power_monitor.py run idle --seconds 60` 처럼 조건마다 한 번씩 재면 여기에 나옵니다."
        )
        return
    st.dataframe(table, hide_index=True, alt="조건별 CPU, 메모리, 전력 측정 결과와 idle 대비 차이")
    notes = [
        "조건마다 가장 최근 측정 한 번입니다. 시스템 CPU 는 노트북 전체 사용률, 앱 CPU 는 이 앱 프로세스(코어 1개 = 100%)입니다.",
        "전력은 측정 도구가 실제 측정 소스에서 읽은 경우에만 숫자로 나오고, 소스 이름이 옆에 있습니다.",
    ]
    if any("RAPL" in str(row["전력 소스"]) for row in table):
        notes.append("RAPL_Package0_PKG 는 CPU 패키지 전력이며 노트북 전체 전력이 아닙니다.")
    notes.append("측정 한 번씩의 평균이라, 차이가 작으면 우연한 변동일 수 있습니다.")
    st.caption(" ".join(notes))
