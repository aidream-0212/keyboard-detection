"""2페이지: Edge Server 관리자. 서버에 도착한 보안 이벤트를 보여준다.

Supabase 가 Edge Server 의 저장소 역할을 대신한다(모의).
"""

import streamlit as st

from core import link, server

RESULT_LABELS = {"SUCCESS": "🟢 재인증 성공", "FAILURE": "🔴 재인증 실패"}


def show():
    """페이지 전체를 그린다."""
    st.title("2 Edge Server 관리자")
    st.caption("(모의) Supabase 가 Edge Server 의 저장소 역할을 대신합니다.")
    if link.is_disconnected():
        st.info(
            "단말과 Edge Server 사이가 통신 단절(모의) 상태입니다. "
            "이 화면은 서버 쪽 기록이라, 단말의 미전송 이벤트는 연결이 돌아온 뒤에 나타납니다."
        )

    database_url = server.load_database_url()
    if database_url is None:
        st.warning(
            "접속 정보가 없습니다. `.streamlit/secrets.toml` 에 `DATABASE_URL` 을 넣어야 합니다. "
            "1페이지의 탐지·재인증·접근 제한은 이것과 무관하게 동작합니다.",
            title="Edge Server(모의)에 연결하지 않았습니다",
        )
        return

    st.button("새로고침", key="admin_refresh", icon=":material/refresh:")  # 누르면 화면을 다시 그린다

    try:
        counts = server.fetch_counts(database_url)
        events = server.fetch_events(database_url)
    except Exception as error:
        st.error(
            f"{server.short_error(error)}\n\n"
            "네트워크와 접속 정보를 확인하세요. "
            "1페이지의 탐지·재인증·접근 제한은 이것과 무관하게 동작합니다.",
            title="Edge Server(모의)에 연결할 수 없습니다",
        )
        return

    show_counts(counts)
    if counts["failure"] > 0:
        st.warning(
            f"재인증 실패가 {counts['failure']}건 있습니다. "
            "해당 단말은 접근 제한 상태가 되었습니다(사용자 변경 의심)."
        )
    show_events(events)


def show_counts(counts):
    """전체, 성공, 실패 건수를 나란히 보여준다."""
    col1, col2, col3 = st.columns(3)
    col1.metric("전체", counts["total"])
    col2.metric("재인증 성공", counts["success"])
    col3.metric("재인증 실패", counts["failure"])


def format_time(value):
    """시각을 이 노트북의 시간대로 바꿔 읽기 쉽게 적는다."""
    return value.astimezone().strftime("%Y-%m-%d %H:%M:%S")


def show_events(events):
    """이벤트를 최근 것부터 표로 보여준다."""
    if not events:
        st.info("아직 도착한 이벤트가 없습니다.")
        return
    rows = []
    for event in events:
        rows.append({
            "발생 시각": format_time(event["occurred_at"]),
            "단말 ID": event["terminal_id"],
            "이벤트 유형": event["event_type"],
            "결과": RESULT_LABELS[event["reauth_result"]],
            "서버 수신 시각": format_time(event["received_at"]),
        })
    st.dataframe(rows, hide_index=True, alt="서버에 도착한 보안 이벤트 목록")
    st.caption(f"최근 {len(rows)}건을 표시합니다.")
