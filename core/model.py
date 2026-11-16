"""등록 모델, 이상도 점수(SD-Scaled Manhattan), 임계값, K 카운터.

모두 화면이나 파일을 건드리지 않는 순수 함수다.
"""

import numpy as np

ENROLL_TARGET = 50       # 등록에 필요한 사용 가능 시도 수
CALIBRATION_TARGET = 30  # 보정에 필요한 사용 가능 시도 수
MIN_STD = 0.005          # 표준편차 하한(초). 0 으로 나누는 일을 막는다
K = 3                    # 연속 이상 판정이 K 번이면 재인증


def enroll(feature_rows):
    """등록 시도들의 특징별 평균과 표준편차(ddof=1)를 구한다."""
    rows = np.array(feature_rows, dtype=float)
    mean = rows.mean(axis=0)
    std = rows.std(axis=0, ddof=1)
    return mean.tolist(), std.tolist()


def score(features, mean, std):
    """이상도 점수: 특징마다 |x - 평균| / max(표준편차, 0.005) 를 구해 평균한다."""
    x = np.array(features, dtype=float)
    safe_std = np.maximum(np.array(std, dtype=float), MIN_STD)
    distances = np.abs(x - np.array(mean, dtype=float)) / safe_std
    return float(distances.mean())


def threshold(scores):
    """임계값 tau: 보정 점수들의 95 백분위수(선형 보간)."""
    return float(np.percentile(scores, 95))


def is_anomaly(score_value, tau):
    """점수가 tau 보다 크면 이상."""
    return score_value > tau


def update_counter(counter, anomaly):
    """이상이면 카운터 +1, 정상이면 0 으로 되돌린다."""
    if anomaly:
        return counter + 1
    return 0


def needs_reauth(counter):
    """연속 이상이 K 번에 도달했는지."""
    return counter >= K
