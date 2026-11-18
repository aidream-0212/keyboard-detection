# keyboard-detection

키보드 행동(H/UD) 기반 사용자 변경 탐지 실습 프로젝트입니다. (AIoT 수업 실습 자료)

현재 단계는 **P3** 입니다. 1페이지(키보드 행동 탐지)가 이 노트북 안에서 끝까지 동작하고,
보안 이벤트를 모의 Edge Server(Supabase)로 보내 2페이지에서 봅니다.
3페이지에서 통신 단절을 흉내 내고 복구 후 전달을 확인합니다. 4페이지에서 자원·전력을 봅니다.

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

`82 passed` 처럼 실패 없이 모두 통과하면 정상입니다. 시험은 네트워크 없이 돕니다.

## 1페이지 사용 순서

입력 상자를 클릭하고 문구 `tie5roan1` 을 친 뒤 Enter 를 누르면 시도 한 번이 됩니다.
한/영 상태와 상관없이 물리 키로 인식합니다.

1. **등록**: 사용 가능한 시도 50회. 평균과 표준편차를 만듭니다.
2. **보정**: 사용 가능한 시도 30회. 등록과 다른 시간대에 평소처럼 입력합니다. 끝나면 임계값 tau 가 정해집니다.
3. **시험용 PIN 설정**: 숫자 4~8자리. 실제 비밀번호를 쓰지 않습니다. 해시만 저장됩니다.
4. **감시**: 입력할 때마다 점수를 tau 와 비교합니다. 연속 3번 이상이면 재인증(PIN)을 요구하고,
   PIN 을 3번 틀리면 접근 제한 상태가 됩니다. 접근 제한은 새로고침해도 유지되고, 잠금 해제에서 PIN 을 넣어 풉니다.

Backspace 사용, 키 순서 틀림, 키 뗌 누락, CapsLock 켜짐인 시도는 사유와 함께 제외되고 채점하지 않습니다.

### 포인터(마우스·터치패드) 경로

1페이지 아래쪽 연습 영역(가상 메뉴 버튼과 스크롤 목록)에서 포인터를 평소처럼 씁니다.
클릭하거나 0.5초 멈출 때마다 동작 하나로 세고, 특징 7개(걸린 시간, 지나간 길이, 곧은 정도,
평균·최대 속도, 평균 가속도, 평균 꺾임)를 뽑습니다. 등록 50 → 보정 30 → 감시는 키보드와 같은 모델·정책입니다.
키보드든 포인터든 연속 이상 3번이면 같은 재인증을 요구합니다. 시험용 PIN 은 키보드 단계에서 한 번만 정합니다.

## 2페이지와 서버 전송 (모의 Edge Server)

Supabase 가 Edge Server 의 저장소 역할을 대신합니다. 재인증이 끝나면 보안 이벤트 한 건이
로컬(`data/outbox.db`)에 먼저 저장되고, 그다음 서버로 전송됩니다.
서버로 가는 값은 event_id, 발생시각, 단말 ID, 이벤트 유형, 재인증 결과 다섯 가지뿐입니다.

1. Supabase 의 SQL Editor 에서 `supabase/schema.sql` 을 한 번 실행합니다.
2. `.streamlit/secrets.toml` 을 만들고 접속 주소를 넣습니다(이 파일은 커밋되지 않습니다).

   ```toml
   DATABASE_URL = "postgresql://사용자:비밀번호@호스트:5432/postgres"
   ```

접속 정보가 없거나 서버에 닿지 않아도 1페이지는 그대로 동작합니다. 2페이지는 연결하지 못했다고 알려줍니다.

## 3페이지: 통신 단절 (모의)

노트북 한 대에서 스위치로 통신 단절을 흉내 냅니다. 현장 네트워크 시험이 아닙니다.

- "통신 단절 (모의)" 스위치를 켜면 서버에 연락하지 않습니다. 이 값은 `data/link.json` 에 저장되어 모든 페이지가 같이 봅니다.
- 그동안 생긴 보안 이벤트는 로컬에 남고 "미전송 N건"으로 보입니다. 1페이지의 판단·재인증·접근 제한은 그대로입니다.
- 스위치를 끄거나 네트워크가 돌아오면, 앱이 열려 있는 동안 약 5초 안에 자동으로 보냅니다. "지금 재전송" 버튼도 있습니다.
- 전달 시간표에서 발생 시각과 서버 수신 시각을 나란히 보고 늦게 도착한 이벤트를 확인합니다.

## 4페이지: 자원·전력과 측정 도구

4페이지는 측정 조건, 앱 프로세스의 실시간 CPU·메모리, 시도별 처리 시간 통계, 조건별 측정 결과 표를 보여줍니다.
조건별 결과는 아래 측정 도구로 만듭니다. 결과는 `power_experiment/` 에 저장되고 커밋하지 않습니다.

```
python tools/power_monitor.py check
python tools/power_monitor.py run idle --seconds 60
python tools/power_monitor.py run detection --seconds 60
python tools/power_monitor.py run reauth --seconds 60
python tools/power_monitor.py run edge --seconds 60
```

- 전력은 Windows Energy Meter Interface(EMI)에서 읽힌 값만 씁니다. 읽을 수 없으면 "측정 불가"입니다.
- 이 노트북(i7-1065G7)의 EMI 값은 CPU 패키지 전력(RAPL)이며, 노트북 전체 전력이 아닙니다.
- CPU 사용률을 W 로 바꾸지 않습니다.

## 기록 파일 (`data/`, 커밋하지 않음)

| 파일 | 내용 |
|---|---|
| `data/state.json` | 등록·보정 결과, tau, PIN 해시, 현재 상태 |
| `data/attempts.csv` | 시도 기록 (시각, 단계, 사용 가능 여부, 제외 사유, 점수, tau, 이상 여부, 카운터, 처리 시간, 교대 표시 번호) |
| `data/security_events.csv` | 재인증이 끝날 때마다 한 줄 (event_id, 발생시각, 단말 ID, 이벤트 유형, 재인증 결과) |
| `data/outbox.db` | 서버로 보낼 이벤트와 보냄 여부 (SQLite) |
| `data/link.json` | 통신 단절(모의) 스위치, 연결 상태, 최근 통신 알림 |

등록부터 다시 하려면 앱을 끄고 `data/state.json` 을 지운 뒤 다시 실행합니다.

## 폴더 구조

| 경로 | 내용 |
|---|---|
| `app.py` | 왼쪽 메뉴와 페이지 고르기 |
| `views/detect.py` | 1페이지 화면 |
| `components/` | 키 누름/뗌 시각을 재는 입력 상자 (HTML/CSS/JS, 빌드 없음) |
| `core/features.py` | 제외 사유 확인, H/UD 특징 19개 추출 |
| `core/pointer.py` | 포인터 동작 나누기, 특징 7개 추출 |
| `components/pointer_area.*` | 포인터 연습 영역 (HTML/CSS/JS, 빌드 없음) |
| `core/model.py` | 등록, 점수, 임계값, K 카운터 |
| `core/session.py` | 단계 진행, 재인증, 접근 제한 |
| `core/pin.py` | 시험용 PIN 해시 |
| `core/storage.py`, `core/events.py` | 로컬 기록, 보안 이벤트 남기기 |
| `core/outbox.py`, `core/server.py` | 로컬에 먼저 저장 후 전송, 서버 접속 |
| `views/admin.py` | 2페이지 화면 |
| `core/link.py`, `core/delivery.py` | 통신 상태 저장, 재전송 판단과 알림 |
| `views/ddil.py`, `views/link_status.py` | 3페이지 화면, 사이드바·1페이지 상태 줄과 자동 재전송 |
| `views/resources.py`, `core/resources.py` | 4페이지 화면, 처리 시간 통계와 조건별 결과 표 |
| `tools/power_monitor.py` | 자원·전력 측정 도구 (CPU·메모리, Windows EMI 전력) |
| `supabase/schema.sql` | 서버 테이블 구조 기록 |
| `tests/` | pytest 시험 |
| `PROGRESS.md` | 진행 상황 (완료 / 미정 / 다음 한 단계) |
| `AGENTS.md` | 프로젝트 규칙 |
