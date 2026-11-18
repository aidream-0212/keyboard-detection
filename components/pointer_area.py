"""포인터(마우스·터치패드) 연습 영역 컴포넌트.

가상의 메뉴 버튼과 스크롤 목록이 있다. 누른 메뉴는 아무 일도 하지 않는다(연습용).
"""

from pathlib import Path

import streamlit as st

FOLDER = Path(__file__).parent

# 컴포넌트 등록은 한 번만 한다
_pointer_area = st.components.v2.component(
    "pointer_practice_area",
    html=(FOLDER / "pointer_area.html").read_text(encoding="utf-8"),
    css=(FOLDER / "pointer_area.css").read_text(encoding="utf-8"),
    js=(FOLDER / "pointer_area.js").read_text(encoding="utf-8"),
)


KEY = "pointer_area"


def pointer_area(last_id, on_batch):
    """연습 영역을 화면에 놓는다.

    새 묶음이 오면 on_batch(묶음) 이 스크립트보다 먼저 한 번 불린다.
        묶음 = {"id": 3, "events": [{"type": "move", "t": ..., "x": ..., "y": ...}, ...]}
    last_id 는 파이썬이 마지막으로 처리한 묶음 번호다. 브라우저는 이보다 큰 번호를 붙인다.

    콜백에서 처리하는 이유: 콜백은 스크립트보다 먼저 실행되므로, 처리 결과가 이어지는 화면에
    바로 반영된다. 처리 후 st.rerun() 으로 한 번 더 다시 그릴 필요가 없어 앱이 가벼워진다.
    """
    def handle():
        batch = st.session_state[KEY].batch
        if batch is not None:
            on_batch(batch)

    _pointer_area(key=KEY, data={"last_id": last_id}, on_batch_change=handle)
