"""여러 페이지가 같이 쓰는 통신 상태 표시와 자동 재전송.

run_every=5 인 fragment 는 앱이 열려 있는 동안 5초마다 그 부분만 다시 실행된다.
"""

import streamlit as st

from core import delivery, link

AUTO_SECONDS = 5


@st.fragment(run_every=AUTO_SECONDS)
def sidebar_status():
    """사이드바: 5초마다 미전송 이벤트를 보내 보고, 통신 상태를 한 줄로 보여준다."""
    result = delivery.deliver()
    for text in result["messages"]:
        st.toast(text)
    st.caption(status_text(result["pending"]))


@st.fragment(run_every=AUTO_SECONDS)
def status_line():
    """1페이지용 한 줄 상태. 보내지는 않고 읽기만 한다(보내는 일은 사이드바가 한다)."""
    st.caption(status_text(delivery.pending_count()))


def status_text(pending):
    """'Edge Server(모의) 연결 · 전송 완료' 같은 한 줄 문장."""
    state = link.load_link()
    if state["disconnected"]:
        connection = ":orange[단절 (모의)]"
    elif state["link_ok"]:
        connection = "연결"
    else:
        connection = ":orange[연결 안 됨]"
    if pending == 0:
        sending = "전송 완료"
    else:
        sending = f":orange[미전송 {pending}건]"
    return f"Edge Server(모의): {connection} · {sending}"
