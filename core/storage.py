"""data/ 폴더에 상태(JSON)와 시도 기록(CSV)을 저장한다. data/ 는 커밋하지 않는다."""

import csv
import json
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
STATE_PATH = DATA_DIR / "state.json"
ATTEMPTS_PATH = DATA_DIR / "attempts.csv"

ATTEMPT_COLUMNS = [
    "time", "mode", "usable", "exclusion_reason", "score", "tau",
    "anomaly", "counter_after", "processing_us", "marker",
]


def new_state():
    """아무것도 하지 않은 처음 상태."""
    return {
        "enroll_rows": [],      # 등록 시도들의 특징(19개씩)
        "calib_scores": [],     # 보정 시도들의 점수
        "mean": None,           # 등록 모델: 특징별 평균
        "std": None,            # 등록 모델: 특징별 표준편차
        "tau": None,            # 임계값
        "pin": None,            # 시험용 PIN 의 해시(salt, hash)
        "status": "ALLOWED",    # ALLOWED / REAUTH / RESTRICTED
        "counter": 0,           # 연속 이상 횟수 (0~3)
        "pin_failures": 0,      # 재인증에서 PIN 을 틀린 횟수
        "marker": 0,            # 교대 표시 번호
        "last_score": None,     # 가장 최근 감시 점수
        "excluded": {"enroll": {}, "calibrate": {}, "monitor": {}},
    }


def load_state(path=STATE_PATH):
    """저장된 상태를 읽는다. 파일이 없으면 처음 상태를 돌려준다."""
    if not path.exists():
        return new_state()
    return json.loads(path.read_text(encoding="utf-8"))


def save_state(state, path=STATE_PATH):
    """상태를 파일에 쓴다. 새로고침해도 유지되게 하기 위해서다."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")


def append_csv_row(path, columns, row):
    """CSV 끝에 한 줄을 붙인다. 파일이 없으면 제목 줄부터 쓴다."""
    path.parent.mkdir(parents=True, exist_ok=True)
    is_new_file = not path.exists()
    with path.open("a", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        if is_new_file:
            writer.writeheader()
        writer.writerow(row)


def append_attempt(row, path=ATTEMPTS_PATH):
    """시도 기록 한 줄을 남긴다."""
    append_csv_row(path, ATTEMPT_COLUMNS, row)


def read_csv_rows(path):
    """CSV 를 dict 목록으로 읽는다. 파일이 없으면 빈 목록."""
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))
