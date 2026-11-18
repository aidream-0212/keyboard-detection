"""3페이지: DDIL 통신 단절 (모의).

통신이 끊겨도 단말은 스스로 판단하고, 이벤트는 로컬에 모였다가 복구 후 전달되는 것을 보여준다.
노트북 한 대에서 하는 모의 시험이다. 현장 네트워크 시험이 아니다.
"""

from datetime import datetime

import streamlit as st

from core import delivery, link, outbox, server
from views.link_status import AUTO_SECONDS

SWITCH_KEY = "ddil_switch"


def show():
    st.title("3 DDIL 통신 단절")
    st.caption(
        "(모의) 노트북 한 대에서 스위치로 통신 단절을 흉내 내는 시험입니다. "
        "실제 현장 네트워크에서 한 시험이 아닙니다."
    )
    st.info(
        "통신이 끊겨도 사용자 변경 의심 판단, 재인증, 접근 제한은 모두 이 단말 안에서 그대로 이루어집니다. "
        "통신 상태가 바꾸는 것은 보안 이벤트가 Edge Server 에 전달되는 시점뿐입니다. "
        "끊긴 동안의 이벤트는 로컬에 저장되었다가, 연결이 돌아오면 한 번씩만 전달됩니다."
    )
    # 스위치는 5초마다 다시 그려지는 부분 밖에 둔다.
    # 그래야 스위치를 바꿀 때 사이드바까지 화면 전체가 바로 다시 그려진다.
    st.session_state[SWITCH_KEY] = link.is_disconnected()   # 다른 곳에서 바뀐 값과 맞춘다
    st.toggle("통신 단절 (모의)", key=SWITCH_KEY, on_change=on_switch_change)
    live_area()


def on_switch_change():
    """스위치를 바꾸면 바로 파일에 저장한다. 끄는 순간에는 곧바로 재전송해 본다."""
    turned_on = st.session_state[SWITCH_KEY]
    link.set_disconnected(turned_on)
    if not turned_on:
        result = delivery.deliver()
        st.session_state["ddil_messages"] = result["messages"]


@st.fragment(run_every=AUTO_SECONDS)
def live_area():
    """5초마다 다시 그려지는 부분: 상태, 미전송 목록, 알림, 전달 시간표."""
    state = link.load_link()
    for text in st.session_state.pop("ddil_messages", []):
        st.success(text)

    pending = outbox.list_pending()
    show_state(state, len(pending))

    if st.button("지금 재전송", key="ddil_resend", icon=":material/send:"):
        resend_now()

    show_messages(state["messages"])
    show_pending(pending)
    show_timeline(link.load_link())


def show_state(state, pending_count):
    col1, col2 = st.columns(2)
    if state["disconnected"]:
        connection = "단절 (모의)"
    elif state["link_ok"]:
        connection = "연결"
    else:
        connection = "연결 안 됨"
    col1.metric("Edge Server 연결", connection)
    col2.metric("미전송", f"{pending_count}건")
    if not state["disconnected"] and pending_count > 0:
        st.caption(f"연결되어 있으면 앱이 열려 있는 동안 {AUTO_SECONDS}초마다 자동으로 다시 보냅니다.")


def resend_now():
    """'지금 재전송' 버튼."""
    if link.is_disconnected():
        st.warning("통신 단절 (모의) 스위치가 켜져 있어 보내지 않았습니다.")
        return
    result = delivery.deliver()
    for text in result["messages"]:
        st.success(text)
    if result["pending"] > 0:
        st.warning(f"Edge Server 에 닿지 않습니다. 미전송 {result['pending']}건은 로컬에 남아 있습니다.")
    elif not result["messages"]:
        st.success("보낼 이벤트가 없습니다.")


def show_messages(messages):
    st.subheader("통신 알림")
    if not messages:
        st.caption("아직 알림이 없습니다.")
        return
    lines = [f"- `{m['time']}` {m['text']}" for m in reversed(messages[-10:])]
    st.markdown("\n".join(lines))


def show_pending(pending):
    st.subheader("미전송 이벤트")
    if not pending:
        st.caption("미전송 이벤트가 없습니다.")
        return
    rows = []
    for event in reversed(pending):
        rows.append({
            "발생 시각": local_time_text(event["occurred_at"]),
            "단말 ID": event["terminal_id"],
            "이벤트 유형": event["event_type"],
            "결과": event["reauth_result"],
        })
    st.dataframe(rows, hide_index=True, alt="로컬에 저장된 미전송 이벤트 목록")


def show_timeline(state):
    """Edge Server 에 도착한 최근 이벤트의 발생 시각과 수신 시각을 나란히 보여준다."""
    st.subheader("전달 시간표 (최근 10건)")
    if state["disconnected"] or not state["link_ok"]:
        st.caption("연결되지 않은 동안에는 Edge Server 를 조회하지 않습니다.")
        return
    database_url = server.load_database_url()
    if database_url is None:
        st.caption("접속 정보가 없어 조회하지 않습니다.")
        return
    try:
        events = server.fetch_events(database_url, limit=10)
    except Exception as error:
        st.caption(f"조회하지 못했습니다: {server.short_error(error)}")
        return
    rows = []
    for event in events:
        delay = (event["received_at"] - event["occurred_at"]).total_seconds()
        rows.append({
            "발생 시각(단말)": event["occurred_at"].astimezone().strftime("%m-%d %H:%M:%S"),
            "수신 시각(서버)": event["received_at"].astimezone().strftime("%m-%d %H:%M:%S"),
            "전달까지": delay_text(delay),
            "결과": event["reauth_result"],
        })
    st.dataframe(rows, hide_index=True, alt="발생 시각과 서버 수신 시각 비교")
    st.caption("두 시각은 서로 다른 컴퓨터의 시계라서 1~2초 정도 어긋날 수 있습니다.")


def delay_text(seconds):
    """지연 시간을 읽기 쉽게 적는다. 몇 초 이내면 '바로'."""
    if seconds < 5:
        return "바로"
    if seconds < 120:
        return f"{seconds:.0f}초 늦게"
    if seconds < 7200:
        return f"{seconds / 60:.0f}분 늦게"
    return f"{seconds / 3600:.1f}시간 늦게"


def local_time_text(iso_text):
    """로컬에 저장된 시각 문자열을 이 노트북 시간대로 바꿔 적는다."""
    return datetime.fromisoformat(iso_text).astimezone().strftime("%m-%d %H:%M:%S")
