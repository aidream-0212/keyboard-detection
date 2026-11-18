"""포인터 동작 나누기, 특징, 그리고 키보드와 같은 모델·정책(OR) 시험."""

import math

import pytest

from core import model, pointer, session, storage
from core.pin import hash_pin
from tests.helpers import make_events


def line_events(start, end, steps, step_ms, t0=0.0, click=False, hold_ms=80):
    """start 에서 end 까지 일정한 속도로 움직이는 이벤트. click=True 면 끝에서 누르고 뗀다."""
    events = []
    for i in range(steps + 1):
        x = start[0] + (end[0] - start[0]) * i / steps
        y = start[1] + (end[1] - start[1]) * i / steps
        events.append({"type": "move", "t": t0 + i * step_ms, "x": x, "y": y})
    if click:
        t_end = events[-1]["t"]
        events.append({"type": "down", "t": t_end + 100, "x": end[0], "y": end[1]})
        events.append({"type": "up", "t": t_end + 100 + hold_ms, "x": end[0], "y": end[1]})
    return events


# ---------- 동작 나누기 ----------

def test_click_ends_an_action():
    events = line_events((0, 0), (300, 0), 10, 30, click=True)
    actions = pointer.segment_actions(events)
    assert len(actions) == 1
    assert actions[0]["end"] == "click"
    assert actions[0]["events"][-1]["type"] == "up"


def test_pause_of_half_a_second_splits_actions():
    first = line_events((0, 0), (200, 0), 8, 30)
    second = line_events((200, 0), (200, 200), 8, 30, t0=first[-1]["t"] + 500)
    actions = pointer.segment_actions(first + second)
    assert [a["end"] for a in actions] == ["pause", "pause"]
    assert len(actions[0]["events"]) == len(first)


def test_shorter_pause_does_not_split():
    first = line_events((0, 0), (200, 0), 8, 30)
    second = line_events((200, 0), (200, 200), 8, 30, t0=first[-1]["t"] + 400)
    assert len(pointer.segment_actions(first + second)) == 1


def test_no_split_while_button_is_held():
    # 끌기: 누른 채 0.5초 넘게 멈춰도 뗄 때까지 한 동작
    events = [{"type": "down", "t": 0, "x": 0, "y": 0}]
    events += line_events((0, 0), (100, 0), 5, 30, t0=900)
    events.append({"type": "up", "t": 1200, "x": 100, "y": 0})
    actions = pointer.segment_actions(events)
    assert len(actions) == 1 and actions[0]["end"] == "click"


def test_click_then_movement_gives_two_actions():
    first = line_events((0, 0), (300, 0), 10, 30, click=True)
    second = line_events((300, 0), (300, 300), 10, 30, t0=first[-1]["t"] + 50)
    actions = pointer.segment_actions(first + second)
    assert [a["end"] for a in actions] == ["click", "pause"]


def test_events_are_sorted_by_time():
    events = line_events((0, 0), (300, 0), 10, 30, click=True)
    actions = pointer.segment_actions(list(reversed(events)))
    assert len(actions) == 1 and actions[0]["end"] == "click"


# ---------- 특징 ----------

def test_straight_constant_speed_features():
    # 300px 를 300ms 에 일직선으로: 속도 1000 px/s, 가속 0, 꺾임 0
    action = {"end": "pause", "events": line_events((0, 0), (300, 0), 10, 30)}
    f = dict(zip(pointer.FEATURE_NAMES, pointer.extract_features(action)))
    assert len(f) == 7
    assert f["duration_s"] == pytest.approx(0.3)
    assert f["path_px"] == pytest.approx(300)
    assert f["straightness"] == pytest.approx(1.0)
    assert f["mean_speed"] == pytest.approx(1000)
    assert f["max_speed"] == pytest.approx(1000)
    assert f["mean_abs_accel"] == pytest.approx(0, abs=1e-6)
    assert f["mean_abs_turn"] == pytest.approx(0, abs=1e-9)


def test_l_shaped_path_features():
    # 오른쪽 100px, 그다음 아래 100px: 곧은 정도 = √2·100 / 200, 꺾임은 한 번 90도
    events = [
        {"type": "move", "t": 0, "x": 0, "y": 0},
        {"type": "move", "t": 100, "x": 100, "y": 0},
        {"type": "move", "t": 200, "x": 100, "y": 100},
        {"type": "move", "t": 300, "x": 100, "y": 200},
    ]
    f = dict(zip(pointer.FEATURE_NAMES, pointer.extract_features({"end": "pause", "events": events})))
    assert f["path_px"] == pytest.approx(300)
    assert f["straightness"] == pytest.approx(math.hypot(100, 200) / 300)
    assert f["mean_abs_turn"] == pytest.approx((math.pi / 2 + 0) / 2)


def test_acceleration_from_speed_change():
    # 구간 속도 1000 → 2000 px/s, 구간 시간 0.1s 씩: 가속 = 1000 / 0.1 = 10000
    events = [
        {"type": "move", "t": 0, "x": 0, "y": 0},
        {"type": "move", "t": 100, "x": 100, "y": 0},
        {"type": "move", "t": 200, "x": 300, "y": 0},
        {"type": "move", "t": 300, "x": 500, "y": 0},
    ]
    f = dict(zip(pointer.FEATURE_NAMES, pointer.extract_features({"end": "pause", "events": events})))
    assert f["max_speed"] == pytest.approx(2000)
    assert f["mean_abs_accel"] == pytest.approx((10000 + 0) / 2)


def test_click_position_counts_toward_the_path():
    events = line_events((0, 0), (300, 0), 10, 30, click=True)
    features = pointer.extract_features({"end": "click", "events": events})
    assert features[0] == pytest.approx(0.3 + 0.1 + 0.08)   # 마지막 움직임 → 누름 → 뗌


def test_tiny_movement_is_excluded():
    small = {"end": "click", "events": line_events((0, 0), (10, 0), 5, 30, click=True)}
    assert pointer.find_exclusion_reason(small) == pointer.REASON_TOO_SMALL
    click_only = {"end": "click", "events": [{"type": "down", "t": 0, "x": 5, "y": 5},
                                            {"type": "up", "t": 80, "x": 5, "y": 5}]}
    assert pointer.find_exclusion_reason(click_only) == pointer.REASON_TOO_SMALL
    normal = {"end": "click", "events": line_events((0, 0), (300, 0), 10, 30, click=True)}
    assert pointer.find_exclusion_reason(normal) is None


def test_duplicate_timestamps_do_not_divide_by_zero():
    events = line_events((0, 0), (300, 0), 10, 30)
    events.insert(3, dict(events[3]))
    features = pointer.extract_features({"end": "pause", "events": events})
    assert all(math.isfinite(v) for v in features)


# ---------- 같은 모델과 정책 ----------

def normal_action(i):
    end = (300 + i % 7 * 10, 100 + i % 5 * 10)
    return {"end": "click", "events": line_events((0, 0), end, 12, 30 + i % 3, click=True)}


def slow_wobbly_action():
    events = []
    for i in range(41):
        events.append({"type": "move", "t": i * 120, "x": i * 8, "y": 60 * math.sin(i)})
    return {"end": "pause", "events": events}


def make_state_with_pointer_monitoring():
    state = storage.new_state()
    for i in range(50):
        session.process_attempt(state, make_events(hold_ms=78 + i % 5, gap_ms=118 + i % 5), False)
    for i in range(30):
        session.process_attempt(state, make_events(hold_ms=78 + i % 5, gap_ms=118 + i % 5), False)
    state["pin"] = hash_pin("1234")
    for i in range(50):
        session.process_pointer_action(state, normal_action(i))
    for i in range(30):
        session.process_pointer_action(state, normal_action(i + 3))
    return state


def test_pointer_path_enrolls_and_calibrates_with_the_shared_model():
    state = storage.new_state()
    for i in range(50):
        session.process_pointer_action(state, normal_action(i))
    path = state["pointer"]
    assert len(path["mean"]) == 7
    assert path["mean"] == pytest.approx(model.enroll(path["enroll_rows"])[0])
    for i in range(30):
        session.process_pointer_action(state, normal_action(i))
    assert path["tau"] == pytest.approx(model.threshold(path["calib_scores"]))
    # PIN 이 아직 없으면 감시 전 대기
    assert session.pointer_mode(state) == "pin"
    # 키보드 경로는 건드리지 않았다
    assert state["enroll_rows"] == [] and state["tau"] is None


def test_pointer_alone_triggers_reauth():
    state = make_state_with_pointer_monitoring()
    assert session.pointer_mode(state) == "monitor"
    for expected in [1, 2, 3]:
        row = session.process_pointer_action(state, slow_wobbly_action())
        assert row["mode"] == "pointer_monitor"
        assert row["anomaly"] is True
        assert row["counter_after"] == expected
    assert state["status"] == "REAUTH"
    assert state["reauth_cause"] == "pointer"
    assert state["counter"] == 0                      # 키보드 카운터는 그대로


def test_normal_pointer_action_resets_pointer_counter():
    state = make_state_with_pointer_monitoring()
    session.process_pointer_action(state, slow_wobbly_action())
    session.process_pointer_action(state, slow_wobbly_action())
    assert state["pointer"]["counter"] == 2
    session.process_pointer_action(state, normal_action(4))
    assert state["pointer"]["counter"] == 0


def test_excluded_pointer_action_does_not_change_counter():
    state = make_state_with_pointer_monitoring()
    session.process_pointer_action(state, slow_wobbly_action())
    tiny = {"end": "click", "events": line_events((0, 0), (5, 0), 3, 30, click=True)}
    row = session.process_pointer_action(state, tiny)
    assert row["usable"] is False and row["exclusion_reason"] == pointer.REASON_TOO_SMALL
    assert state["pointer"]["counter"] == 1
    assert state["pointer"]["excluded"]["monitor"] == {pointer.REASON_TOO_SMALL: 1}


def test_successful_reauth_resets_both_counters():
    state = make_state_with_pointer_monitoring()
    session.process_attempt(state, make_events(hold_ms=400, gap_ms=900), False)   # 키보드 이상 1번
    for _ in range(3):
        session.process_pointer_action(state, slow_wobbly_action())
    assert state["counter"] == 1 and state["pointer"]["counter"] == 3
    assert session.submit_reauth_pin(state, "1234") == "SUCCESS"
    assert state["counter"] == 0 and state["pointer"]["counter"] == 0
    assert state["reauth_cause"] is None


def test_old_state_file_gets_an_empty_pointer_path(tmp_path):
    # P5 이전 파일: 포인터 자리가 없어도 읽을 수 있고, 키보드 기록은 그대로
    path = tmp_path / "state.json"
    old = storage.new_state()
    del old["pointer"], old["reauth_cause"]
    old["tau"] = 1.5
    storage.save_state(old, path)
    loaded = storage.load_state(path)
    assert loaded["tau"] == 1.5
    assert loaded["pointer"]["enroll_rows"] == []
    assert session.pointer_mode(loaded) == "enroll"
