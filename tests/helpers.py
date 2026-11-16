"""시험에서 쓰는 가짜 키 입력을 만든다."""

from core.features import EXPECTED_CODES


def make_events(hold_ms=80, gap_ms=120, codes=None):
    """키를 하나씩 눌렀다 떼는 입력을 만든다.

    hold_ms: 누르고 있는 시간, gap_ms: 떼고 나서 다음 키를 누를 때까지의 시간.
    """
    if codes is None:
        codes = EXPECTED_CODES
    events = []
    t = 1000.0
    for code in codes:
        events.append({"code": code, "type": "down", "t": t})
        events.append({"code": code, "type": "up", "t": t + hold_ms})
        t = t + hold_ms + gap_ms
    return events
