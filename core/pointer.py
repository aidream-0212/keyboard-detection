"""포인터(마우스·노트북 터치패드) 동작을 나누고 특징을 뽑는다.

브라우저가 보낸 이벤트 하나는 아래처럼 생겼다 (t 는 밀리초, x·y 는 화면 픽셀).
    {"type": "move", "t": 1234.5, "x": 300, "y": 120}     # 움직임 (약 30ms 마다 하나)
    {"type": "down", ...}  {"type": "up", ...}             # 버튼 누름 / 뗌

동작(action) 하나 = 클릭으로 끝나거나, 0.5초 이상 멈춰서 끝나는 움직임 한 덩어리.
(참고: Antal & Egyed-Zsigmond 2019, Zheng et al. 2016, Shen et al. 2013, Mondal & Bours 2017)
"""

import math

PAUSE_MS = 500        # 이만큼 멈추면 동작 하나가 끝난 것으로 본다
MIN_POINTS = 4        # 위치 기록이 이보다 적으면 특징을 믿기 어렵다
MIN_PATH_PX = 30      # 이보다 짧게 움직였으면 동작으로 치지 않는다

REASON_TOO_SMALL = "움직임 부족"

# 특징 7개. 클릭으로 끝난 동작과 멈춰서 끝난 동작 모두에 있는 값만 쓴다.
FEATURE_NAMES = [
    "duration_s",          # 걸린 시간(초)
    "path_px",             # 지나간 길이(픽셀)
    "straightness",        # 곧은 정도 = 직선 거리 / 지나간 길이 (1 이면 일직선)
    "mean_speed",          # 평균 속도(픽셀/초) = 지나간 길이 / 걸린 시간
    "max_speed",           # 가장 빠른 구간의 속도(픽셀/초)
    "mean_abs_accel",      # 가속도 크기의 평균(픽셀/초²)
    "mean_abs_turn",       # 방향이 꺾인 정도의 평균(라디안, 곡률)
]


def segment_actions(events):
    """이벤트를 동작 단위로 나눈다.

    돌려주는 값: [{"end": "click" 또는 "pause", "events": [...]}, ...]
    - 버튼을 뗀(up) 순간 동작이 끝난다(click).
    - 앞 이벤트와 0.5초 이상 떨어져 있으면 그 앞에서 동작이 끝난다(pause).
      단, 버튼을 누르고 있는 동안(끌기)에는 나누지 않는다.
    - 마지막에 남은 덩어리는 멈춰서 끝난 것(pause)으로 본다. 브라우저는 멈추거나 영역을 벗어날 때 보낸다.
    """
    actions = []
    current = []
    pressed = False
    for event in sorted(events, key=lambda e: e["t"]):
        if current and not pressed and event["t"] - current[-1]["t"] >= PAUSE_MS:
            actions.append({"end": "pause", "events": current})
            current = []
        current.append(event)
        if event["type"] == "down":
            pressed = True
        elif event["type"] == "up":
            pressed = False
            actions.append({"end": "click", "events": current})
            current = []
    if current:
        actions.append({"end": "pause", "events": current})
    return actions


def positions(events):
    """시각(초)과 위치만 뽑는다. 같은 시각의 기록이 겹치면 하나만 남긴다."""
    points = []
    for event in events:
        point = (event["t"] / 1000, float(event["x"]), float(event["y"]))
        if points and point[0] <= points[-1][0]:
            continue
        points.append(point)
    return points


def path_length(points):
    return sum(math.dist(a[1:], b[1:]) for a, b in zip(points, points[1:]))


def find_exclusion_reason(action):
    """채점하면 안 되는 동작의 사유. 문제가 없으면 None."""
    points = positions(action["events"])
    if len(points) < MIN_POINTS or path_length(points) < MIN_PATH_PX:
        return REASON_TOO_SMALL
    return None


def extract_features(action):
    """동작 하나의 특징 7개(FEATURE_NAMES 순서). find_exclusion_reason 이 None 인 동작에만 쓴다."""
    points = positions(action["events"])
    duration = points[-1][0] - points[0][0]
    path = path_length(points)
    straight = math.dist(points[0][1:], points[-1][1:])

    # 구간마다: 걸린 시간, 움직인 거리, 속도, 방향
    steps = []
    for a, b in zip(points, points[1:]):
        dt = b[0] - a[0]
        dx, dy = b[1] - a[1], b[2] - a[2]
        distance = math.hypot(dx, dy)
        steps.append({"dt": dt, "speed": distance / dt, "distance": distance,
                      "angle": math.atan2(dy, dx)})

    # 가속도: 이웃한 두 구간의 속도 차이 / 두 구간 가운데 사이의 시간
    accels = []
    for s1, s2 in zip(steps, steps[1:]):
        accels.append(abs(s2["speed"] - s1["speed"]) / ((s1["dt"] + s2["dt"]) / 2))

    # 꺾인 정도: 움직임이 있었던 이웃 구간들의 방향 차이 (-π ~ π 로 맞춘 뒤 절댓값)
    moving = [s for s in steps if s["distance"] > 0]
    turns = []
    for s1, s2 in zip(moving, moving[1:]):
        diff = s2["angle"] - s1["angle"]
        diff = (diff + math.pi) % (2 * math.pi) - math.pi
        turns.append(abs(diff))

    return [
        duration,
        path,
        straight / path if path > 0 else 0.0,
        path / duration if duration > 0 else 0.0,
        max(s["speed"] for s in steps),
        sum(accels) / len(accels) if accels else 0.0,
        sum(turns) / len(turns) if turns else 0.0,
    ]
