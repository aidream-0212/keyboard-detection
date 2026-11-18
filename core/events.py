"""보안 이벤트 기록. 재인증이 끝날 때마다 한 건을 남기고 서버로 보낸다.

화면 코드는 record_security_event 만 부른다.
순서: 로컬 CSV 에 기록 -> 로컬 outbox 에 저장 -> 서버로 전송 시도(core.delivery).
전송이 실패하거나 통신 단절(모의) 중이어도 예외를 내지 않는다.
탐지·재인증·접근 제한은 서버와 무관하게 동작해야 한다.
"""

import uuid
from datetime import datetime, timezone

from core import delivery, link, outbox
from core.storage import DATA_DIR, append_csv_row

EVENTS_PATH = DATA_DIR / "security_events.csv"
EVENT_COLUMNS = ["event_id", "occurred_at", "terminal_id", "event_type", "reauth_result"]

TERMINAL_ID = "TACTICAL-01"                 # 가상 단말 ID
EVENT_TYPE = "USER_CHANGE_SUSPECTED"        # 사용자 변경 의심


def record_security_event(reauth_result, path=EVENTS_PATH, outbox_path=outbox.OUTBOX_PATH,
                          send=None, link_path=link.LINK_PATH):
    """보안 이벤트 한 건을 남기고, 남긴 내용을 돌려준다.

    reauth_result 는 "SUCCESS" 또는 "FAILURE".
    키 입력 원문, 특징값, 점수, PIN 은 여기에 넣지 않는다.
    send 를 주지 않으면 secrets.toml 의 접속 정보로 보낸다(시험에서는 가짜 send 를 준다).
    """
    event = {
        "event_id": str(uuid.uuid4()),
        "occurred_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "terminal_id": TERMINAL_ID,
        "event_type": EVENT_TYPE,
        "reauth_result": reauth_result,
    }
    append_csv_row(path, EVENT_COLUMNS, event)
    outbox.save_event(event, outbox_path)   # 먼저 로컬에 저장하고
    try:                                    # 그다음 보낸다
        delivery.deliver(new_event=True, send=send, outbox_path=outbox_path, link_path=link_path)
    except Exception:
        pass  # 전송 쪽 문제로 재인증 흐름이 멈추면 안 된다
    return event
