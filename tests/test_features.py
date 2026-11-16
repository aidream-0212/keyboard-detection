"""특징 추출과 제외 사유 시험."""

import pytest

from core import features
from tests.helpers import make_events


def test_extract_features_gives_10_holds_and_9_latencies_in_seconds():
    events = make_events(hold_ms=80, gap_ms=120)
    result = features.extract_features(events)
    assert len(result) == 19
    assert result[:10] == pytest.approx([0.080] * 10)
    assert result[10:] == pytest.approx([0.120] * 9)


def test_negative_latency_is_kept_when_keys_overlap():
    # T 를 떼기 전에 I 를 누른 경우: 첫 UD 가 음수가 된다
    events = make_events(hold_ms=80, gap_ms=120)
    events[1]["t"] = events[2]["t"] + 30  # T 의 뗌을 I 누름보다 30ms 뒤로
    result = features.extract_features(events)
    assert result[10] == pytest.approx(-0.030)


def test_normal_attempt_has_no_exclusion_reason():
    assert features.find_exclusion_reason(make_events(), caps_lock=False) is None


def test_overlapping_keys_are_still_usable():
    events = make_events()
    events[1]["t"] = events[2]["t"] + 30
    events.sort(key=lambda e: e["t"])
    assert features.find_exclusion_reason(events, caps_lock=False) is None


def test_capslock_is_excluded():
    reason = features.find_exclusion_reason(make_events(), caps_lock=True)
    assert reason == features.REASON_CAPSLOCK


def test_backspace_is_excluded():
    codes = ["KeyT", "KeyU", "Backspace"] + features.EXPECTED_CODES[1:]
    reason = features.find_exclusion_reason(make_events(codes=codes), caps_lock=False)
    assert reason == features.REASON_BACKSPACE


def test_wrong_key_order_is_excluded():
    codes = list(features.EXPECTED_CODES)
    codes[0], codes[1] = codes[1], codes[0]
    reason = features.find_exclusion_reason(make_events(codes=codes), caps_lock=False)
    assert reason == features.REASON_WRONG_ORDER


def test_too_few_keys_is_excluded():
    # Enter 만 누른 경우처럼 입력이 부족하면 판정하지 않는다
    reason = features.find_exclusion_reason(make_events(codes=["Enter"]), caps_lock=False)
    assert reason == features.REASON_WRONG_ORDER


def test_missing_keyup_is_excluded():
    events = make_events()
    events = [e for e in events if not (e["code"] == "KeyR" and e["type"] == "up")]
    reason = features.find_exclusion_reason(events, caps_lock=False)
    assert reason == features.REASON_MISSING_KEYUP


def test_keyup_without_keydown_is_ignored():
    # 입력 상자에 들어오기 전에 누르고 있던 키의 뗌은 무시한다
    events = [{"code": "KeyZ", "type": "up", "t": 900.0}] + make_events()
    assert features.find_exclusion_reason(events, caps_lock=False) is None
