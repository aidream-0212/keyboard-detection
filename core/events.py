"""보안 이벤트 기록. 재인증이 끝날 때마다 한 줄을 남긴다.

화면 코드는 record_security_event 만 부른다.
P2 에서 서버 전송을 붙일 때 이 함수 안만 고치면 된다.
"""

import uuid
from datetime import datetime, timezone

from core.storage import DATA_DIR, append_csv_row

EVENTS_PATH = DATA_DIR / "security_events.csv"
EVENT_COLUMNS = ["event_id", "occurred_at", "terminal_id", "event_type", "reauth_result"]

TERMINAL_ID = "TACTICAL-01"                 # 가상 단말 ID
EVENT_TYPE = "USER_CHANGE_SUSPECTED"        # 사용자 변경 의심


def record_security_event(reauth_result, path=EVENTS_PATH):
    """보안 이벤트 한 건을 로컬 CSV 에 남기고, 남긴 내용을 돌려준다.

    reauth_result 는 "SUCCESS" 또는 "FAILURE".
    키 입력 원문, 특징값, 점수, PIN 은 여기에 넣지 않는다.
    """
    event = {
        "event_id": str(uuid.uuid4()),
        "occurred_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "terminal_id": TERMINAL_ID,
        "event_type": EVENT_TYPE,
        "reauth_result": reauth_result,
    }
    append_csv_row(path, EVENT_COLUMNS, event)
    return event
