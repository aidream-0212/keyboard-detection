"""시도 한 번, 포인터 동작 한 번, PIN 입력 한 번이 들어왔을 때 상태(state)를 어떻게 바꿀지 정한다.

파일을 읽거나 쓰지 않는다. state(dict)만 고치고 결과를 돌려준다.
저장은 화면 코드가 core.storage 로 한다.

경로(path)가 둘이다. 둘 다 같은 이름의 값(enroll_rows, calib_scores, mean, std, tau, counter,
last_score, excluded)을 가진 dict 이고, 같은 모델 함수(core.model)를 쓴다.
- 키보드 경로: state 자체 (P1 부터 써 온 자리 그대로)
- 포인터 경로: state["pointer"]
재인증 상태(status), PIN, 교대 표시는 두 경로가 함께 쓴다. 어느 쪽이든 K 에 닿으면 재인증(OR).
"""

import time
from datetime import datetime

from core import features as keyboard_features
from core import model, pointer
from core.pin import verify_pin

MAX_PIN_FAILURES = 3
CAUSE_LABELS = {"keyboard": "키보드 입력", "pointer": "포인터 동작"}


# ---------- 단계 ----------

def path_mode(path, pin_is_set):
    """경로 하나가 어느 단계인지: enroll(등록) / calibrate(보정) / pin(PIN 설정 대기) / monitor(감시)."""
    if len(path["enroll_rows"]) < model.ENROLL_TARGET:
        return "enroll"
    if len(path["calib_scores"]) < model.CALIBRATION_TARGET:
        return "calibrate"
    if not pin_is_set:
        return "pin"
    return "monitor"


def current_mode(state):
    """키보드 경로의 단계."""
    return path_mode(state, state["pin"] is not None)


def pointer_mode(state):
    """포인터 경로의 단계."""
    return path_mode(state["pointer"], state["pin"] is not None)


# ---------- 시도 처리 ----------

def new_row(state, path, mode_name):
    """시도 기록에 남길 한 줄의 기본값."""
    return {
        "time": datetime.now().astimezone().isoformat(timespec="milliseconds"),
        "mode": mode_name,
        "usable": False,
        "exclusion_reason": "",
        "score": "",
        "tau": "" if path["tau"] is None else path["tau"],
        "anomaly": "",
        "counter_after": path["counter"],
        "processing_us": 0,
        "marker": state["marker"],
    }


def count_excluded(path, mode, reason):
    counts = path["excluded"].setdefault(mode, {})
    counts[reason] = counts.get(reason, 0) + 1


def use_features(state, path, mode, features, row, cause):
    """사용 가능한 시도의 특징을 단계에 맞게 쓴다. 두 경로가 같이 쓴다."""
    if mode == "enroll":
        add_enroll_attempt(path, features)
    elif mode == "calibrate":
        row["score"] = add_calibration_attempt(path, features)
    elif mode == "monitor":
        add_monitor_attempt(state, path, features, row, cause)


def process_attempt(state, events, caps_lock):
    """키보드 시도 한 번을 처리한다. state 를 고치고, 시도 기록에 남길 한 줄(dict)을 돌려준다."""
    start = time.perf_counter_ns()
    mode = current_mode(state)
    row = new_row(state, state, mode)

    reason = keyboard_features.find_exclusion_reason(events, caps_lock)
    if reason is not None:
        # 제외된 시도: 채점하지 않고 카운터도 그대로 둔다
        row["exclusion_reason"] = reason
        count_excluded(state, mode, reason)
    else:
        row["usable"] = True
        use_features(state, state, mode, keyboard_features.extract_features(events), row, "keyboard")

    row["processing_us"] = (time.perf_counter_ns() - start) // 1000
    return row


def process_pointer_action(state, action):
    """포인터 동작 하나를 처리한다. 시도 기록의 mode 는 'pointer_등록단계' 로 남긴다."""
    start = time.perf_counter_ns()
    path = state["pointer"]
    mode = pointer_mode(state)
    row = new_row(state, path, f"pointer_{mode}")

    reason = pointer.find_exclusion_reason(action)
    if reason is not None:
        row["exclusion_reason"] = reason
        count_excluded(path, mode, reason)
    else:
        row["usable"] = True
        use_features(state, path, mode, pointer.extract_features(action), row, "pointer")

    row["processing_us"] = (time.perf_counter_ns() - start) // 1000
    return row


def add_enroll_attempt(path, features):
    """등록 시도를 모으고, 50개가 차면 모델(평균, 표준편차)을 만든다."""
    path["enroll_rows"].append(features)
    if len(path["enroll_rows"]) == model.ENROLL_TARGET:
        path["mean"], path["std"] = model.enroll(path["enroll_rows"])


def add_calibration_attempt(path, features):
    """보정 시도를 채점해 모으고, 30개가 차면 임계값 tau 를 정한다."""
    score_value = model.score(features, path["mean"], path["std"])
    path["calib_scores"].append(score_value)
    if len(path["calib_scores"]) == model.CALIBRATION_TARGET:
        path["tau"] = model.threshold(path["calib_scores"])
    return score_value


def add_monitor_attempt(state, path, features, row, cause):
    """감시 시도를 판정하고 그 경로의 카운터를 갱신한다. K 번 연속 이상이면 재인증을 요구한다."""
    score_value = model.score(features, path["mean"], path["std"])
    anomaly = model.is_anomaly(score_value, path["tau"])
    path["counter"] = model.update_counter(path["counter"], anomaly)
    path["last_score"] = score_value
    if model.needs_reauth(path["counter"]):
        state["status"] = "REAUTH"
        state["reauth_cause"] = cause
    row["score"] = score_value
    row["anomaly"] = anomaly
    row["counter_after"] = path["counter"]


# ---------- 재인증 ----------

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
    """허용 상태로 되돌린다. 두 경로의 카운터를 모두 0 으로."""
    state["status"] = "ALLOWED"
    state["counter"] = 0
    state["pointer"]["counter"] = 0
    state["pin_failures"] = 0
    state["reauth_cause"] = None


def add_marker(state):
    """교대 표시: 번호를 1 올리고, 시도 기록에 남길 한 줄을 돌려준다."""
    state["marker"] += 1
    return {
        "time": datetime.now().astimezone().isoformat(timespec="milliseconds"),
        "mode": "marker",
        "marker": state["marker"],
    }
