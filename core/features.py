"""키 입력 한 번(시도)에서 제외 사유를 찾고, H/UD 특징 19개를 뽑는다.

events 는 브라우저가 보낸 목록이고, 항목 하나는 아래처럼 생겼다.
    {"code": "KeyT", "type": "down", "t": 1234.5}   # t 는 밀리초
"""

# 고정 문구 tie5roan1 + Enter 를 물리 키 이름(event.code)으로 적은 것
EXPECTED_CODES = [
    "KeyT", "KeyI", "KeyE", "Digit5", "KeyR",
    "KeyO", "KeyA", "KeyN", "Digit1", "Enter",
]

# 제외 사유 (CSV 와 화면에 그대로 쓴다)
REASON_CAPSLOCK = "CapsLock 켜짐"
REASON_BACKSPACE = "Backspace 사용"
REASON_WRONG_ORDER = "키 순서 틀림"
REASON_MISSING_KEYUP = "키 뗌 누락"


def key_times(events):
    """키마다 처음 누른 시각과, 그 뒤 처음 뗀 시각을 찾는다."""
    down_times = {}
    up_times = {}
    for event in events:
        code = event["code"]
        if event["type"] == "down" and code not in down_times:
            down_times[code] = event["t"]
        if event["type"] == "up" and code in down_times and code not in up_times:
            up_times[code] = event["t"]
    return down_times, up_times


def find_exclusion_reason(events, caps_lock):
    """시도를 채점하면 안 되는 사유를 돌려준다. 문제가 없으면 None."""
    if caps_lock:
        return REASON_CAPSLOCK

    down_codes = [e["code"] for e in events if e["type"] == "down"]
    if "Backspace" in down_codes:
        return REASON_BACKSPACE
    if down_codes != EXPECTED_CODES:
        return REASON_WRONG_ORDER

    down_times, up_times = key_times(events)
    for code in EXPECTED_CODES:
        if code not in up_times:
            return REASON_MISSING_KEYUP
    return None


def extract_features(events):
    """특징 19개(초 단위)를 돌려준다: 누른 시간 H 10개 + 뗌-누름 간격 UD 9개.

    find_exclusion_reason 이 None 인 시도에만 쓴다.
    """
    down_times, up_times = key_times(events)

    # H: 한 키를 누르고 있던 시간
    holds = []
    for code in EXPECTED_CODES:
        holds.append((up_times[code] - down_times[code]) / 1000)

    # UD: 앞 키를 뗀 순간부터 다음 키를 누른 순간까지 (겹쳐 누르면 음수, 그대로 둔다)
    latencies = []
    for i in range(len(EXPECTED_CODES) - 1):
        previous_code = EXPECTED_CODES[i]
        next_code = EXPECTED_CODES[i + 1]
        latencies.append((down_times[next_code] - up_times[previous_code]) / 1000)

    return holds + latencies
