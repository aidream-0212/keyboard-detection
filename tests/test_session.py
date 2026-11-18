"""등록 -> 보정 -> PIN -> 감시 -> 재인증 흐름과 로컬 기록 시험."""

from core import events, features, session, storage
from core.pin import hash_pin, verify_pin
from tests.helpers import make_events

FAST = dict(hold_ms=80, gap_ms=120)
SLOW = dict(hold_ms=400, gap_ms=900)


def make_monitoring_state():
    """등록 50회, 보정 30회, PIN 설정까지 끝난 상태를 만든다."""
    state = storage.new_state()
    for i in range(50):
        session.process_attempt(state, make_events(hold_ms=78 + i % 5, gap_ms=118 + i % 5), False)
    for i in range(30):
        session.process_attempt(state, make_events(hold_ms=78 + i % 5, gap_ms=118 + i % 5), False)
    state["pin"] = hash_pin("1234")
    return state


def test_steps_advance_in_order():
    state = storage.new_state()
    assert session.current_mode(state) == "enroll"
    for _ in range(50):
        session.process_attempt(state, make_events(**FAST), False)
    assert session.current_mode(state) == "calibrate"
    assert len(state["mean"]) == 19
    for _ in range(30):
        session.process_attempt(state, make_events(**FAST), False)
    assert session.current_mode(state) == "pin"
    assert state["tau"] is not None
    state["pin"] = hash_pin("1234")
    assert session.current_mode(state) == "monitor"


def test_excluded_attempt_is_counted_by_reason_and_not_enrolled():
    state = storage.new_state()
    row = session.process_attempt(state, make_events(**FAST), True)
    assert row["usable"] is False
    assert row["exclusion_reason"] == features.REASON_CAPSLOCK
    assert state["enroll_rows"] == []
    assert state["excluded"]["enroll"] == {features.REASON_CAPSLOCK: 1}


def test_normal_typing_keeps_counter_at_zero():
    state = make_monitoring_state()
    row = session.process_attempt(state, make_events(**FAST), False)
    assert row["anomaly"] is False
    assert state["counter"] == 0
    assert state["status"] == "ALLOWED"


def test_three_slow_attempts_in_a_row_require_reauth():
    state = make_monitoring_state()
    for expected_counter in [1, 2, 3]:
        row = session.process_attempt(state, make_events(**SLOW), False)
        assert row["anomaly"] is True
        assert row["counter_after"] == expected_counter
    assert state["status"] == "REAUTH"


def test_normal_attempt_resets_counter():
    state = make_monitoring_state()
    session.process_attempt(state, make_events(**SLOW), False)
    session.process_attempt(state, make_events(**SLOW), False)
    assert state["counter"] == 2
    session.process_attempt(state, make_events(**FAST), False)
    assert state["counter"] == 0
    assert state["status"] == "ALLOWED"


def test_excluded_attempt_does_not_change_counter():
    state = make_monitoring_state()
    session.process_attempt(state, make_events(**SLOW), False)
    row = session.process_attempt(state, make_events(**SLOW), True)  # CapsLock
    assert row["usable"] is False
    assert row["score"] == ""
    assert state["counter"] == 1


def test_correct_pin_allows_access_again():
    state = make_monitoring_state()
    for _ in range(3):
        session.process_attempt(state, make_events(**SLOW), False)
    assert session.submit_reauth_pin(state, "1234") == "SUCCESS"
    assert state["status"] == "ALLOWED"
    assert state["counter"] == 0


def test_three_wrong_pins_restrict_access_and_unlock_restores():
    state = make_monitoring_state()
    for _ in range(3):
        session.process_attempt(state, make_events(**SLOW), False)
    assert session.submit_reauth_pin(state, "0000") is None
    assert session.submit_reauth_pin(state, "0000") is None
    assert session.submit_reauth_pin(state, "0000") == "FAILURE"
    assert state["status"] == "RESTRICTED"

    assert session.unlock(state, "0000") is False
    assert state["status"] == "RESTRICTED"
    assert session.unlock(state, "1234") is True
    assert state["status"] == "ALLOWED"
    assert state["counter"] == 0


def test_pin_is_stored_only_as_hash():
    stored = hash_pin("1234")
    assert "1234" not in str(stored)
    assert verify_pin("1234", stored) is True
    assert verify_pin("4321", stored) is False


def test_state_survives_save_and_load(tmp_path):
    path = tmp_path / "state.json"
    state = storage.new_state()
    state["status"] = "RESTRICTED"
    storage.save_state(state, path)
    assert storage.load_state(path)["status"] == "RESTRICTED"


def test_attempt_log_has_header_once_and_reads_back(tmp_path):
    path = tmp_path / "attempts.csv"
    state = storage.new_state()
    storage.append_attempt(session.process_attempt(state, make_events(**FAST), False), path)
    storage.append_attempt(session.process_attempt(state, make_events(**FAST), True), path)
    storage.append_attempt(session.add_marker(state), path)

    rows = storage.read_csv_rows(path)
    assert list(rows[0].keys()) == storage.ATTEMPT_COLUMNS
    assert [r["mode"] for r in rows] == ["enroll", "enroll", "marker"]
    assert rows[1]["exclusion_reason"] == features.REASON_CAPSLOCK
    assert rows[2]["marker"] == "1"
    # utf-8-sig 표시(BOM)는 파일 맨 앞에 한 번만 있어야 한다
    assert path.read_bytes().count(b"\xef\xbb\xbf") == 1


def test_security_event_has_only_the_five_allowed_fields(tmp_path):
    path = tmp_path / "security_events.csv"
    outbox_path = tmp_path / "outbox.db"

    def fake_send(payload):  # 시험에서는 진짜 서버로 보내지 않는다
        pass

    events.record_security_event("SUCCESS", path, outbox_path, fake_send)
    events.record_security_event("FAILURE", path, outbox_path, fake_send)

    rows = storage.read_csv_rows(path)
    assert list(rows[0].keys()) == [
        "event_id", "occurred_at", "terminal_id", "event_type", "reauth_result",
    ]
    assert rows[0]["terminal_id"] == "TACTICAL-01"
    assert rows[0]["event_type"] == "USER_CHANGE_SUSPECTED"
    assert [r["reauth_result"] for r in rows] == ["SUCCESS", "FAILURE"]
    assert rows[0]["event_id"] != rows[1]["event_id"]
