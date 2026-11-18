"""보낼 보안 이벤트를 로컬 SQLite 에 먼저 저장해 두는 곳(outbox).

순서: 로컬에 저장 -> 서버로 전송 -> 성공하면 '보냄' 표시.
전송이 실패해도 이벤트는 로컬에 남아 있어서 나중에 다시 보낼 수 있다.
"""

import sqlite3

from core.storage import DATA_DIR

OUTBOX_PATH = DATA_DIR / "outbox.db"

# 노트북 밖으로 나가도 되는 값은 이 다섯 가지뿐이다
PAYLOAD_FIELDS = ["event_id", "occurred_at", "terminal_id", "event_type", "reauth_result"]


def open_outbox(path):
    """SQLite 파일을 열고, 표가 없으면 만든다."""
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        create table if not exists outbox (
            event_id      text primary key,
            occurred_at   text not null,
            terminal_id   text not null,
            event_type    text not null,
            reauth_result text not null,
            sent          integer not null default 0
        )
        """
    )
    return conn


def build_payload(event):
    """이벤트에서 보내도 되는 다섯 가지 값만 골라낸다."""
    return {field: event[field] for field in PAYLOAD_FIELDS}


def save_event(event, path=OUTBOX_PATH):
    """이벤트를 로컬에 저장한다. 같은 event_id 가 이미 있으면 그대로 둔다."""
    payload = build_payload(event)
    conn = open_outbox(path)
    with conn:
        conn.execute(
            "insert or ignore into outbox "
            "(event_id, occurred_at, terminal_id, event_type, reauth_result) "
            "values (:event_id, :occurred_at, :terminal_id, :event_type, :reauth_result)",
            payload,
        )
    conn.close()


def list_pending(path=OUTBOX_PATH):
    """아직 보내지 못한 이벤트를 오래된 것부터 돌려준다."""
    conn = open_outbox(path)
    rows = conn.execute(
        "select * from outbox where sent = 0 order by occurred_at, event_id"
    ).fetchall()
    conn.close()
    return [build_payload(row) for row in rows]


def mark_sent(event_id, path=OUTBOX_PATH):
    """이벤트에 '보냄' 표시를 한다."""
    conn = open_outbox(path)
    with conn:
        conn.execute("update outbox set sent = 1 where event_id = ?", (event_id,))
    conn.close()


def send_pending(send, path=OUTBOX_PATH):
    """보내지 못한 이벤트를 차례로 보낸다. 보낸 건수를 돌려준다.

    send 는 payload(dict) 하나를 받아 서버로 보내는 함수다. 실패하면 예외를 낸다.
    하나라도 실패하면 거기서 멈춘다. 남은 이벤트는 다음 기회에 다시 보낸다.
    """
    sent_count = 0
    for payload in list_pending(path):
        try:
            send(payload)
        except Exception:
            break
        mark_sent(payload["event_id"], path)
        sent_count += 1
    return sent_count
