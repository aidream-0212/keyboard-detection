# keyboard-detection

키보드 행동(H/UD) 기반 사용자 변경 탐지 실습 프로젝트입니다. (AIoT 수업 실습 자료)

현재 단계는 **P1** 입니다. 1페이지(키보드 행동 탐지)가 이 노트북 안에서 끝까지 동작합니다.
서버 전송은 아직 없고, 2~4페이지는 "준비 중" 입니다.

## 준비물

- Windows, 파이썬 3.10 이상 (`python --version` 으로 확인)

## 1. 가상환경 만들기

프로젝트 폴더(`keyboard-detection`) 안에서 실행합니다.

```
python -m venv .venv
```

## 2. 가상환경 켜기

PowerShell:

```
.venv\Scripts\Activate.ps1
```

cmd:

```
.venv\Scripts\activate.bat
```

켜지면 줄 맨 앞에 `(.venv)` 가 보입니다.

> PowerShell 에서 "스크립트를 실행할 수 없습니다" 오류가 나면 아래 명령을 한 번 실행한 뒤 다시 켭니다.
> `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

## 3. 패키지 설치

```
pip install -r requirements.txt
```

## 4. 앱 실행

```
streamlit run app.py
```

브라우저가 열리고(`http://localhost:8501`) 왼쪽 메뉴에 네 개의 페이지가 보입니다.
끝낼 때는 터미널에서 `Ctrl + C` 를 누릅니다.

## 5. 시험 실행

```
pytest
```

`30 passed` 처럼 모두 통과하면 정상입니다.

## 1페이지 사용 순서

입력 상자를 클릭하고 문구 `tie5roan1` 을 친 뒤 Enter 를 누르면 시도 한 번이 됩니다.
한/영 상태와 상관없이 물리 키로 인식합니다.

1. **등록**: 사용 가능한 시도 50회. 평균과 표준편차를 만듭니다.
2. **보정**: 사용 가능한 시도 30회. 등록과 다른 시간대에 평소처럼 입력합니다. 끝나면 임계값 tau 가 정해집니다.
3. **시험용 PIN 설정**: 숫자 4~8자리. 실제 비밀번호를 쓰지 않습니다. 해시만 저장됩니다.
4. **감시**: 입력할 때마다 점수를 tau 와 비교합니다. 연속 3번 이상이면 재인증(PIN)을 요구하고,
   PIN 을 3번 틀리면 접근 제한 상태가 됩니다. 접근 제한은 새로고침해도 유지되고, 잠금 해제에서 PIN 을 넣어 풉니다.

Backspace 사용, 키 순서 틀림, 키 뗌 누락, CapsLock 켜짐인 시도는 사유와 함께 제외되고 채점하지 않습니다.

## 기록 파일 (`data/`, 커밋하지 않음)

| 파일 | 내용 |
|---|---|
| `data/state.json` | 등록·보정 결과, tau, PIN 해시, 현재 상태 |
| `data/attempts.csv` | 시도 기록 (시각, 단계, 사용 가능 여부, 제외 사유, 점수, tau, 이상 여부, 카운터, 처리 시간, 교대 표시 번호) |
| `data/security_events.csv` | 재인증이 끝날 때마다 한 줄 (event_id, 발생시각, 단말 ID, 이벤트 유형, 재인증 결과) |

등록부터 다시 하려면 앱을 끄고 `data/state.json` 을 지운 뒤 다시 실행합니다.

## 폴더 구조

| 경로 | 내용 |
|---|---|
| `app.py` | 왼쪽 메뉴와 페이지 고르기 |
| `views/detect.py` | 1페이지 화면 |
| `components/` | 키 누름/뗌 시각을 재는 입력 상자 (HTML/CSS/JS, 빌드 없음) |
| `core/features.py` | 제외 사유 확인, H/UD 특징 19개 추출 |
| `core/model.py` | 등록, 점수, 임계값, K 카운터 |
| `core/session.py` | 단계 진행, 재인증, 접근 제한 |
| `core/pin.py` | 시험용 PIN 해시 |
| `core/storage.py`, `core/events.py` | 로컬 기록 |
| `tests/` | pytest 시험 |
| `PROGRESS.md` | 진행 상황 (완료 / 미정 / 다음 한 단계) |
| `AGENTS.md` | 프로젝트 규칙 |
