"""통신 상태(link)를 파일에 저장한다. 모든 페이지가 같은 상태를 보게 하기 위해서다.

- disconnected: "통신 단절 (모의)" 스위치가 켜져 있는지
- link_ok: 마지막으로 확인한 Edge Server 연결이 정상이었는지
- messages: 최근 통신 알림 (최근 것이 뒤)
"""

import json
from datetime import datetime

from core.storage import DATA_DIR

LINK_PATH = DATA_DIR / "link.json"
MAX_MESSAGES = 20


def new_link_state():
    return {"disconnected": False, "link_ok": True, "messages": []}


def load_link(path=LINK_PATH):
    """통신 상태를 읽는다. 파일이 없으면 처음 상태."""
    if not path.exists():
        return new_link_state()
    return json.loads(path.read_text(encoding="utf-8"))


def update_link(path=LINK_PATH, **fields):
    """주어진 값만 바꿔서 저장한다(다른 값은 파일에 있던 그대로 둔다)."""
    state = load_link(path)
    state.update(fields)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
    return state


def is_disconnected(path=LINK_PATH):
    return load_link(path)["disconnected"]


def set_disconnected(value, path=LINK_PATH):
    """스위치를 켜거나 끈다. 켜면 그 자체로 연결이 끊긴 상태다."""
    if value:
        update_link(path, disconnected=True, link_ok=False)
    else:
        update_link(path, disconnected=False)


def add_messages(texts, path=LINK_PATH):
    """알림 문장들을 시각과 함께 남긴다. 오래된 것은 지운다."""
    if not texts:
        return
    now = datetime.now().astimezone().strftime("%H:%M:%S")
    messages = load_link(path)["messages"]
    messages += [{"time": now, "text": text} for text in texts]
    update_link(path, messages=messages[-MAX_MESSAGES:])
