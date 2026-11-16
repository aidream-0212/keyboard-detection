# keyboard-detection

키보드 행동(H/UD) 기반 사용자 변경 탐지 실습 프로젝트입니다. (AIoT 수업 실습 자료)

현재 단계는 **P0(뼈대)** 입니다. 화면에는 메뉴 4개와 "준비 중" 문구만 있고, 탐지 기능은 아직 없습니다.

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

`1 passed` 가 나오면 정상입니다.

## 폴더 구조

| 경로 | 내용 |
|---|---|
| `app.py` | Streamlit 화면 |
| `core/` | 핵심 계산 함수 (이후 단계에서 추가) |
| `tests/` | pytest 시험 |
| `PROGRESS.md` | 진행 상황 (완료 / 미정 / 다음 한 단계) |
| `AGENTS.md` | 프로젝트 규칙 |
