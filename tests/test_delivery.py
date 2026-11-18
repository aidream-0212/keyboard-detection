"""통신 단절(모의)과 복구 시험. 네트워크 없이 가짜 서버로 돈다."""

import pytest

from core import delivery, events, link, outbox
from tests.test_outbox import FakeServer


@pytest.fixture
def paths(tmp_path):
    """시험마다 따로 쓰는 파일 경로 (진짜 data/ 를 건드리지 않는다)."""
    return {
        "csv": tmp_path / "events.csv",
        "outbox": tmp_path / "outbox.db",
        "link": tmp_path / "link.json",
    }


def record(result, fake, paths):
    return events.record_security_event(result, paths["csv"], paths["outbox"], fake.send, paths["link"])


def deliver(fake, paths, ping=None):
    return delivery.deliver(send=fake.send, ping=ping, outbox_path=paths["outbox"], link_path=paths["link"])


def messages(paths):
    return [m["text"] for m in link.load_link(paths["link"])["messages"]]


def test_switch_state_is_saved_to_disk(paths):
    assert link.is_disconnected(paths["link"]) is False
    link.set_disconnected(True, paths["link"])
    assert link.is_disconnected(paths["link"]) is True     # 다른 페이지가 읽어도 같은 값
    link.set_disconnected(False, paths["link"])
    assert link.is_disconnected(paths["link"]) is False


def test_events_are_kept_while_switch_is_on(paths):
    fake = FakeServer()
    link.set_disconnected(True, paths["link"])

    record("SUCCESS", fake, paths)
    record("FAILURE", fake, paths)

    assert fake.payloads == []                              # 서버에 연락하지 않았다
    assert len(outbox.list_pending(paths["outbox"])) == 2
    assert messages(paths) == [
        "[연결 안 됨] 이벤트를 로컬에 저장했습니다. 미전송 1건",
        "[연결 안 됨] 이벤트를 로컬에 저장했습니다. 미전송 2건",
    ]


def test_events_are_sent_once_after_recovery(paths):
    fake = FakeServer()
    link.set_disconnected(True, paths["link"])
    first = record("SUCCESS", fake, paths)
    second = record("FAILURE", fake, paths)

    link.set_disconnected(False, paths["link"])
    result = deliver(fake, paths)

    assert result == {
        "connected": True, "sent": 2, "pending": 0,
        "messages": ["[연결 복구] Edge Server 연결 확인", "[전송 완료] 미전송 이벤트 2건 전송"],
    }
    assert set(fake.rows) == {first["event_id"], second["event_id"]}

    # 5초마다 다시 불려도 더 보내지 않고, 알림도 더 남기지 않는다
    again = deliver(fake, paths)
    assert again["sent"] == 0 and again["messages"] == []
    assert len(fake.payloads) == 2


def test_sending_twice_does_not_duplicate(paths):
    # 서버에는 도착했지만 노트북이 '보냄' 표시를 못 한 경우: 한 번 더 가지만 서버에는 한 건
    fake = FakeServer()
    link.set_disconnected(True, paths["link"])
    event = record("SUCCESS", fake, paths)
    fake.send(outbox.list_pending(paths["outbox"])[0])

    link.set_disconnected(False, paths["link"])
    deliver(fake, paths)

    assert len(fake.payloads) == 2
    assert list(fake.rows) == [event["event_id"]]


def test_real_send_failure_is_handled_like_the_switch(paths):
    fake = FakeServer()
    fake.online = False                                     # 스위치는 꺼져 있지만 서버에 닿지 않는다

    record("SUCCESS", fake, paths)
    record("FAILURE", fake, paths)

    assert len(outbox.list_pending(paths["outbox"])) == 2
    assert link.load_link(paths["link"])["link_ok"] is False
    assert messages(paths)[-1] == "[연결 안 됨] 이벤트를 로컬에 저장했습니다. 미전송 2건"

    fake.online = True                                      # 네트워크가 돌아왔다
    result = deliver(fake, paths)
    assert result["sent"] == 2 and result["pending"] == 0
    assert len(fake.rows) == 2


def test_repeated_failures_do_not_repeat_the_message(paths):
    fake = FakeServer()
    fake.online = False
    record("SUCCESS", fake, paths)
    for _ in range(5):                                      # 자동 재시도가 계속 실패해도
        deliver(fake, paths)
    assert len(messages(paths)) == 1                        # 알림은 처음 한 번뿐


def test_recovery_with_nothing_pending_checks_the_server(paths):
    fake = FakeServer()
    calls = []
    link.set_disconnected(True, paths["link"])
    deliver(fake, paths)
    link.set_disconnected(False, paths["link"])

    result = deliver(fake, paths, ping=lambda: calls.append("ping"))

    assert calls == ["ping"]                                # 실제로 연결을 확인했을 때만
    assert result["messages"] == ["[연결 복구] Edge Server 연결 확인"]


def test_recovery_is_not_claimed_when_the_check_fails(paths):
    fake = FakeServer()
    link.set_disconnected(True, paths["link"])
    deliver(fake, paths)
    link.set_disconnected(False, paths["link"])

    def broken_ping():
        raise ConnectionError("연결 안 됨")

    result = deliver(fake, paths, ping=broken_ping)
    assert result["connected"] is False
    assert result["messages"] == []
