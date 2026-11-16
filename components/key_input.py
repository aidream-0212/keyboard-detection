"""키 누름/뗌 시각을 재는 입력 상자(커스텀 컴포넌트).

Streamlit 의 글자 입력창은 키를 누르고 뗀 시각을 알려주지 않는다.
그래서 같은 폴더의 HTML/CSS/JS 파일을 읽어 st.components.v2 로 등록해 쓴다.
"""

from pathlib import Path

import streamlit as st

FOLDER = Path(__file__).parent

# 컴포넌트 등록은 한 번만 한다 (이 파일이 처음 불릴 때)
_key_input = st.components.v2.component(
    "key_timing_input",
    html=(FOLDER / "key_input.html").read_text(encoding="utf-8"),
    css=(FOLDER / "key_input.css").read_text(encoding="utf-8"),
    js=(FOLDER / "key_input.js").read_text(encoding="utf-8"),
)


def key_input(last_id):
    """입력 상자를 화면에 놓는다.

    Enter 를 뗀 순간의 시도 하나를 돌려준다. 새 시도가 없으면 None.
        {"id": 3, "events": [{"code": "KeyT", "type": "down", "t": 1234.5}, ...], "caps_lock": False}
    last_id 는 파이썬이 마지막으로 처리한 시도 번호다. 브라우저는 이보다 큰 번호를 붙인다.
    """
    result = _key_input(
        key="key_input",
        data={"last_id": last_id},
        on_attempt_change=lambda: None,  # 이게 있어야 result.attempt 가 항상 존재한다
    )
    return result.attempt
