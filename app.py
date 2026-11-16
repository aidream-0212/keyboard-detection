"""키보드 행동 탐지 실습 앱 (P0: 화면 뼈대만 있음).

실행: streamlit run app.py
"""

import streamlit as st

# 왼쪽 메뉴에 보일 네 개의 페이지 제목
PAGES = [
    "1 키보드 행동 탐지",
    "2 Edge Server 관리자",
    "3 DDIL 통신 단절",
    "4 자원·전력",
]


def show_page(title):
    """페이지 제목과 '준비 중' 문구를 보여준다."""
    st.title(title)
    st.write("준비 중")


st.set_page_config(page_title="키보드 행동 탐지", layout="wide")

# 왼쪽 사이드바에서 페이지를 고른다
selected = st.sidebar.radio("메뉴", PAGES)

show_page(selected)
