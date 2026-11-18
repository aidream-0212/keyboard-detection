"""1페이지: 키보드 행동 탐지 (등록 -> 보정 -> 시험용 PIN 설정 -> 감시).

계산은 core/ 에 있고, 여기서는 화면을 그리고 결과를 저장만 한다.
이 단계(P1)에서는 서버로 아무것도 보내지 않는다.
"""

import streamlit as st

from components.key_input import key_input
from core import model, session, storage
from core.events import record_security_event
from core.pin import hash_pin, is_valid_pin
from views.link_status import status_line

STEP_LABELS = {
    "enroll": "1. 등록",
    "calibrate": "2. 보정",
    "pin": "3. 시험용 PIN 설정",
    "monitor": "4. 감시",
}
STATUS_LABELS = {"ALLOWED": "허용", "REAUTH": "재인증 요구", "RESTRICTED": "접근 제한"}


def show():
    """페이지 전체를 그린다."""
    st.title("1 키보드 행동 탐지")
    st.session_state.setdefault("last_attempt_id", 0)
    status_line()  # 전송 상태 한 줄. 아래의 탐지·재인증·접근 제한은 이것과 무관하다
    show_flash()

    state = storage.load_state()
    if state["status"] == "RESTRICTED":
        show_restricted(state)
        return

    mode = session.current_mode(state)
    show_steps(mode)
    if mode == "enroll":
        show_enroll(state)
    elif mode == "calibrate":
        show_calibrate(state)
    elif mode == "pin":
        show_pin_setup(state)
    else:
        show_monitor(state)


# ---------- 공통 조각 ----------

def set_flash(kind, text):
    """다음 화면 맨 위에 한 번만 보여줄 알림을 맡겨 둔다."""
    st.session_state["flash"] = (kind, text)


def show_flash():
    """맡겨 둔 알림이 있으면 보여주고 지운다."""
    kind, text = st.session_state.pop("flash", (None, None))
    if kind == "success":
        st.success(text)
    elif kind == "error":
        st.error(text)


def show_steps(mode):
    """네 단계 중 어디까지 왔는지 한 줄로 보여준다."""
    modes = list(STEP_LABELS)
    current = modes.index(mode)
    parts = []
    for i, step in enumerate(modes):
        label = STEP_LABELS[step]
        if i < current:
            parts.append(f":green[:material/check_circle: {label}]")
        elif i == current:
            parts.append(f":blue[:material/play_circle: **{label}**]")
        else:
            parts.append(f":gray[:material/radio_button_unchecked: {label}]")
    st.markdown(" → ".join(parts))


def typing_box(state):
    """입력 상자를 놓고, 새 시도가 들어오면 한 번만 처리한다."""
    attempt = key_input(last_id=st.session_state["last_attempt_id"])
    if attempt is None:
        return
    # Streamlit 은 화면을 그릴 때마다 이 코드를 다시 실행한다.
    # 이미 처리한 번호의 시도는 다시 세지 않는다.
    if attempt["id"] <= st.session_state["last_attempt_id"]:
        return
    st.session_state["last_attempt_id"] = attempt["id"]

    row = session.process_attempt(state, list(attempt["events"]), attempt["caps_lock"])
    storage.save_state(state)
    storage.append_attempt(row)
    st.session_state["last_row"] = row
    st.rerun()  # 바뀐 상태로 화면을 처음부터 다시 그린다


def show_last_attempt():
    """방금 시도가 어떻게 처리됐는지 보여준다."""
    row = st.session_state.get("last_row")
    if row is None:
        return
    if not row["usable"]:
        st.warning(f"방금 시도는 제외되었습니다: {row['exclusion_reason']}")
    elif row["anomaly"] is True:
        st.warning("방금 시도: 평소와 다름 (이상)")
    elif row["anomaly"] is False:
        st.success("방금 시도: 정상")
    else:
        st.success("방금 시도: 사용 가능")


def show_excluded(state, mode):
    """제외된 시도를 사유별로 센 결과를 보여준다."""
    counts = state["excluded"][mode]
    if not counts:
        st.caption("제외된 시도: 없음")
        return
    parts = [f"{reason} {count}회" for reason, count in counts.items()]
    st.caption("제외된 시도: " + ", ".join(parts))


# ---------- 1. 등록 ----------

def show_enroll(state):
    st.subheader("1. 등록")
    st.write("문구 `tie5roan1` 을 평소처럼 입력하고 Enter 를 누르세요. 사용 가능한 시도 50회가 필요합니다.")
    done = len(state["enroll_rows"])
    st.progress(done / model.ENROLL_TARGET, text=f"사용 가능 {done} / {model.ENROLL_TARGET}")
    show_excluded(state, "enroll")
    typing_box(state)
    show_last_attempt()


# ---------- 2. 보정 ----------

def show_calibrate(state):
    st.subheader("2. 보정")
    st.info(
        "보정은 등록과 다른 시간대에 하세요(예: 쉬었다가, 또는 다음 날). "
        "잘 치려고 하지 말고 평소처럼 입력하세요."
    )
    done = len(state["calib_scores"])
    st.progress(done / model.CALIBRATION_TARGET, text=f"사용 가능 {done} / {model.CALIBRATION_TARGET}")
    show_excluded(state, "calibrate")
    typing_box(state)
    show_last_attempt()


# ---------- 3. 시험용 PIN 설정 ----------

def show_pin_setup(state):
    st.subheader("3. 시험용 PIN 설정")
    st.metric("임계값 tau", f"{state['tau']:.3f}")
    st.info("이것은 실습을 위한 시험용 PIN 입니다. 실제로 쓰는 비밀번호나 PIN 을 넣지 마세요.")
    with st.form("pin_setup", clear_on_submit=True):
        pin = st.text_input("시험용 PIN (숫자 4~8자리)", type="password", key="new_pin")
        pin_again = st.text_input("한 번 더 입력", type="password", key="new_pin_again")
        submitted = st.form_submit_button("PIN 저장")
    if not submitted:
        return
    if not is_valid_pin(pin):
        st.error("숫자 4~8자리로 입력하세요.")
    elif pin != pin_again:
        st.error("두 입력이 서로 다릅니다.")
    else:
        state["pin"] = hash_pin(pin)  # 해시만 저장한다
        storage.save_state(state)
        st.session_state.pop("last_row", None)
        set_flash("success", "시험용 PIN 을 저장했습니다. 감시를 시작합니다.")
        st.rerun()


# ---------- 4. 감시 ----------

def show_monitor(state):
    st.subheader("4. 감시")
    show_monitor_numbers(state)

    if state["status"] == "REAUTH":
        show_reauth(state)
        return

    st.write("문구 `tie5roan1` 을 입력하고 Enter 를 누르세요. 입력할 때마다 판정합니다.")
    show_excluded(state, "monitor")
    typing_box(state)
    show_last_attempt()

    st.divider()
    st.caption(f"교대 표시 번호: {state['marker']} (다른 사람이 이어받는 순간에 누릅니다. A/B 실험용)")
    if st.button("교대 표시", key="marker_button"):
        storage.append_attempt(session.add_marker(state))
        storage.save_state(state)
        st.rerun()


def show_monitor_numbers(state):
    """현재 점수, 임계값, 카운터, 상태를 나란히 보여준다."""
    score_text = "-" if state["last_score"] is None else f"{state['last_score']:.3f}"
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("현재 점수", score_text)
    col2.metric("임계값 tau", f"{state['tau']:.3f}")
    col3.metric("연속 이상 카운터", f"{state['counter']} / {model.K}")
    col4.metric("상태", STATUS_LABELS[state["status"]])


def show_reauth(state):
    """재인증 배너: 시험용 PIN 을 묻는다."""
    left = session.MAX_PIN_FAILURES - state["pin_failures"]
    st.error(
        f"평소와 다른 입력이 {model.K}번 이어졌습니다(사용자 변경 의심). "
        f"시험용 PIN 을 입력하세요. 남은 기회 {left}번.",
        title="재인증 요구",
    )
    with st.form("reauth", clear_on_submit=True):
        pin = st.text_input("시험용 PIN", type="password", key="reauth_pin")
        submitted = st.form_submit_button("확인")
    if not submitted:
        return

    result = session.submit_reauth_pin(state, pin)
    storage.save_state(state)
    st.session_state.pop("last_row", None)
    if result is None:
        set_flash("error", "PIN 이 맞지 않습니다.")
    else:
        record_security_event(result)  # 재인증이 끝났을 때만 한 줄 남긴다
        if result == "SUCCESS":
            set_flash("success", "재인증에 성공했습니다. 상태를 허용으로 되돌렸습니다.")
    st.rerun()


# ---------- 접근 제한 ----------

def show_restricted(state):
    """접근 제한: 작업 화면을 숨기고 안내와 잠금 해제만 보여준다."""
    st.error(
        "재인증에 3번 실패해 이 단말의 작업 화면을 숨겼습니다. "
        "새로고침해도 풀리지 않습니다.",
        title="접근 제한",
    )
    st.subheader("잠금 해제")
    with st.form("unlock", clear_on_submit=True):
        pin = st.text_input("시험용 PIN", type="password", key="unlock_pin")
        submitted = st.form_submit_button("잠금 해제")
    if not submitted:
        return
    if session.unlock(state, pin):
        storage.save_state(state)
        set_flash("success", "잠금을 해제했습니다. 상태를 허용으로 되돌렸습니다.")
    else:
        set_flash("error", "PIN 이 맞지 않습니다.")
    st.rerun()
