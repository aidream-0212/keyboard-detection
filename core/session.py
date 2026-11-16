"""시도 한 번, PIN 입력 한 번이 들어왔을 때 상태(state)를 어떻게 바꿀지 정한다.

파일을 읽거나 쓰지 않는다. state(dict)만 고치고 결과를 돌려준다.
저장은 화면 코드가 core.storage 로 한다.
"""

import time
from datetime import datetime

from core import model
from core.features import extract_features, find_exclusion_reason
from core.pin import verify_pin

MAX_PIN_FAILURES = 3


def current_mode(state):
    """지금 어느 단계인지: enroll(등록) / calibrate(보정) / pin(PIN 설정) / monitor(감시)."""
    if len(state["enroll_rows"]) < model.ENROLL_TARGET:
        return "enroll"
    if len(state["calib_scores"]) < model.CALIBRATION_TARGET:
        return "calibrate"
    if state["pin"] is None:
        return "pin"
    return "monitor"


def process_attempt(state, events, caps_lock):
    """시도 한 번을 처리한다. state 를 고치고, 시도 기록에 남길 한 줄(dict)을 돌려준다."""
    start = time.perf_counter_ns()
    mode = current_mode(state)
    row = {
        "time": datetime.now().astimezone().isoformat(timespec="milliseconds"),
        "mode": mode,
        "usable": False,
        "exclusion_reason": "",
        "score": "",
        "tau": "" if state["tau"] is None else state["tau"],
        "anomaly": "",
        "counter_after": state["counter"],
        "processing_us": 0,
        "marker": state["marker"],
    }

    reason = find_exclusion_reason(events, caps_lock)
    if reason is not None:
        # 제외된 시도: 채점하지 않고 카운터도 그대로 둔다
        row["exclusion_reason"] = reason
        counts = state["excluded"][mode]
        counts[reason] = counts.get(reason, 0) + 1
    else:
        row["usable"] = True
        features = extract_features(events)
        if mode == "enroll":
            add_enroll_attempt(state, features)
        elif mode == "calibrate":
            row["score"] = add_calibration_attempt(state, features)
        elif mode == "monitor":
            add_monitor_attempt(state, features, row)

    row["processing_us"] = (time.perf_counter_ns() - start) // 1000
    return row


def add_enroll_attempt(state, features):
    """등록 시도를 모으고, 50개가 차면 모델(평균, 표준편차)을 만든다."""
    state["enroll_rows"].append(features)
    if len(state["enroll_rows"]) == model.ENROLL_TARGET:
        state["mean"], state["std"] = model.enroll(state["enroll_rows"])


def add_calibration_attempt(state, features):
    """보정 시도를 채점해 모으고, 30개가 차면 임계값 tau 를 정한다."""
    score_value = model.score(features, state["mean"], state["std"])
    state["calib_scores"].append(score_value)
    if len(state["calib_scores"]) == model.CALIBRATION_TARGET:
        state["tau"] = model.threshold(state["calib_scores"])
    return score_value


def add_monitor_attempt(state, features, row):
    """감시 시도를 판정하고 카운터를 갱신한다. K 번 연속 이상이면 재인증을 요구한다."""
    score_value = model.score(features, state["mean"], state["std"])
    anomaly = model.is_anomaly(score_value, state["tau"])
    state["counter"] = model.update_counter(state["counter"], anomaly)
    state["last_score"] = score_value
    if model.needs_reauth(state["counter"]):
        state["status"] = "REAUTH"
    row["score"] = score_value
    row["anomaly"] = anomaly
    row["counter_after"] = state["counter"]


def submit_reauth_pin(state, pin):
    """재인증 PIN 한 번을 처리한다.

    재인증이 끝났으면 "SUCCESS" 또는 "FAILURE", 아직 기회가 남았으면 None 을 돌려준다.
    """
    if verify_pin(pin, state["pin"]):
        allow_access(state)
        return "SUCCESS"
    state["pin_failures"] += 1
    if state["pin_failures"] >= MAX_PIN_FAILURES:
        state["status"] = "RESTRICTED"
        return "FAILURE"
    return None


def unlock(state, pin):
    """접근 제한을 푼다. PIN 이 맞으면 True."""
    if not verify_pin(pin, state["pin"]):
        return False
    allow_access(state)
    return True


def allow_access(state):
    """허용 상태로 되돌린다."""
    state["status"] = "ALLOWED"
    state["counter"] = 0
    state["pin_failures"] = 0


def add_marker(state):
    """교대 표시: 번호를 1 올리고, 시도 기록에 남길 한 줄을 돌려준다."""
    state["marker"] += 1
    return {
        "time": datetime.now().astimezone().isoformat(timespec="milliseconds"),
        "mode": "marker",
        "marker": state["marker"],
    }
