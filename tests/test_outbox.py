"""outbox(로컬 저장 후 전송) 시험. 네트워크 없이 가짜 전송 함수로 돈다."""

from core import events, outbox, server
from core.pin import hash_pin
from core import session, storage
from tests.helpers import make_events

ALLOWED_FIELDS = {"event_id", "occurred_at", "terminal_id", "event_type", "reauth_result"}


def make_event(event_id="e1", result="SUCCESS"):
    return {
        "event_id": event_id,
        "occurred_at": "2026-11-17T00:00:00+00:00",
        "terminal_id": "TACTICAL-01",
        "event_type": "USER_CHANGE_SUSPECTED",
        "reauth_result": result,
    }


class FakeServer:
    """서버 흉내. 받은 payload 를 모아 두고, event_id 가 같으면 한 번만 남긴다."""

    def __init__(self):
        self.online = True
        self.payloads = []   # 받은 그대로
        self.rows = {}       # 서버에 남은 것 (event_id 로 중복 제거)

    def send(self, payload):
        if not self.online:
            raise ConnectionError("서버에 연결할 수 없음")
        self.payloads.append(payload)
        self.rows.setdefault(payload["event_id"], payload)


def test_saved_event_is_pending_until_sent(tmp_path):
    path = tmp_path / "outbox.db"
    outbox.save_event(make_event("e1"), path)
    assert [p["event_id"] for p in outbox.list_pending(path)] == ["e1"]

    outbox.mark_sent("e1", path)
    assert outbox.list_pending(path) == []


def test_saving_same_event_twice_keeps_one(tmp_path):
    path = tmp_path / "outbox.db"
    outbox.save_event(make_event("e1"), path)
    outbox.save_event(make_event("e1"), path)
    assert len(outbox.list_pending(path)) == 1


def test_send_pending_sends_and_marks_sent(tmp_path):
    path = tmp_path / "outbox.db"
    fake = FakeServer()
    outbox.save_event(make_event("e1"), path)
    outbox.save_event(make_event("e2", "FAILURE"), path)

    assert outbox.send_pending(fake.send, path) == 2
    assert set(fake.rows) == {"e1", "e2"}
    assert outbox.list_pending(path) == []
    # 다시 불러도 보낼 것이 없다
    assert outbox.send_pending(fake.send, path) == 0
    assert len(fake.payloads) == 2


def test_failed_send_keeps_event_and_resend_works(tmp_path):
    path = tmp_path / "outbox.db"
    fake = FakeServer()
    fake.online = False
    outbox.save_event(make_event("e1"), path)

    assert outbox.send_pending(fake.send, path) == 0
    assert len(outbox.list_pending(path)) == 1   # 로컬에 남아 있다

    fake.online = True
    assert outbox.send_pending(fake.send, path) == 1
    assert outbox.list_pending(path) == []


def test_resending_never_creates_a_duplicate(tmp_path):
    # 서버에는 도착했는데 '보냄' 표시를 못 한 상황: 같은 이벤트가 한 번 더 간다
    path = tmp_path / "outbox.db"
    fake = FakeServer()
    outbox.save_event(make_event("e1"), path)
    fake.send(outbox.list_pending(path)[0])      # 도착했지만 표시는 안 됨

    assert outbox.send_pending(fake.send, path) == 1
    assert len(fake.payloads) == 2               # 두 번 갔지만
    assert len(fake.rows) == 1                   # 서버에는 한 건만 남는다


def test_server_insert_ignores_existing_event_id():
    # 실제 서버로 보내는 SQL 이 중복을 무시하는 형태인지 확인한다
    assert "on conflict (event_id) do nothing" in server.INSERT_SQL


def test_payload_has_only_the_five_allowed_fields(tmp_path):
    # 이벤트에 다른 값이 섞여 들어와도 밖으로 나가면 안 된다
    path = tmp_path / "outbox.db"
    fake = FakeServer()
    event = make_event("e1")
    event.update({"score": 40.2, "pin": "1234", "features": [0.1, 0.2], "keys": "tie5roan1"})

    assert set(outbox.build_payload(event)) == ALLOWED_FIELDS
    outbox.save_event(event, path)
    outbox.send_pending(fake.send, path)
    assert set(fake.payloads[0]) == ALLOWED_FIELDS


def test_recorded_event_goes_through_outbox_with_only_allowed_fields(tmp_path):
    fake = FakeServer()
    event = events.record_security_event(
        "SUCCESS", tmp_path / "events.csv", tmp_path / "outbox.db", fake.send, tmp_path / "link.json"
    )
    assert len(fake.payloads) == 1
    assert set(fake.payloads[0]) == ALLOWED_FIELDS
    assert fake.payloads[0]["event_id"] == event["event_id"]
    assert set(server.INSERT_SQL.split("(")[1].split(")")[0].replace(" ", "").split(",")) == ALLOWED_FIELDS


def test_recording_works_when_sending_fails(tmp_path):
    # 서버가 죽어 있어도 기록은 남고 예외가 나지 않는다
    fake = FakeServer()
    fake.online = False
    outbox_path = tmp_path / "outbox.db"

    event = events.record_security_event(
        "FAILURE", tmp_path / "events.csv", outbox_path, fake.send, tmp_path / "link.json"
    )

    assert event["reauth_result"] == "FAILURE"
    assert len(storage.read_csv_rows(tmp_path / "events.csv")) == 1
    assert [p["event_id"] for p in outbox.list_pending(outbox_path)] == [event["event_id"]]


def test_reauth_result_is_the_same_whether_sending_succeeds_or_fails(tmp_path):
    # 1페이지의 판정·PIN·접근 제한은 전송 성공 여부와 무관해야 한다
    final_states = []
    for online in [True, False]:
        fake = FakeServer()
        fake.online = online
        state = storage.new_state()
        for _ in range(50):
            session.process_attempt(state, make_events(hold_ms=80, gap_ms=120), False)
        for _ in range(30):
            session.process_attempt(state, make_events(hold_ms=80, gap_ms=120), False)
        state["pin"] = hash_pin("1234")
        for _ in range(3):
            session.process_attempt(state, make_events(hold_ms=400, gap_ms=900), False)
        for _ in range(3):
            result = session.submit_reauth_pin(state, "0000")
        folder = tmp_path / str(online)
        events.record_security_event(
            result, folder / "events.csv", folder / "outbox.db", fake.send, folder / "link.json"
        )
        final_states.append((result, state["status"], state["counter"], state["pin_failures"]))

    assert final_states[0] == final_states[1]
    assert final_states[0][:2] == ("FAILURE", "RESTRICTED")


def test_missing_secrets_means_no_sender(tmp_path):
    assert server.load_database_url(tmp_path / "no_such_file.toml") is None
    placeholder = tmp_path / "secrets.toml"
    placeholder.write_text('DATABASE_URL = "postgresql://u:[YOUR-PASSWORD]@host:5432/postgres"', encoding="utf-8")
    assert server.load_database_url(placeholder) is None
    assert server.make_sender(placeholder) is None
