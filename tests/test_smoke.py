"""pytest 가 제대로 연결됐는지 확인하는 가장 단순한 시험."""

import core


def test_smoke():
    # core 폴더를 불러올 수 있으면 통과
    assert core is not None
