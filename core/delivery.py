"""미전송 이벤트를 Edge Server 로 보낼지 정하고, 보낸 결과를 알림 문장으로 남긴다.

판단·재인증·접근 제한은 여기와 무관하다. 통신 상태가 바꾸는 것은 '언제 전달되는가'뿐이다.
"""

from core import link, outbox, server


def deliver(new_event=False, send=None, ping=None,
            outbox_path=outbox.OUTBOX_PATH, link_path=link.LINK_PATH):
    """미전송 이벤트를 보내 본다. 결과를 dict 로 돌려준다.

    new_event: 방금 이벤트를 하나 저장했으면 True (알림을 남기기 위해)
    send, ping: 서버로 보내는 함수와 연결만 확인하는 함수. 주지 않으면 secrets.toml 로 만든다.
    """
    state = link.load_link(link_path)
    was_ok = state["link_ok"]
    pending_before = len(outbox.list_pending(outbox_path))
    sent = 0

    if state["disconnected"]:
        now_ok = False                       # 스위치가 켜져 있으면 서버에 연락하지 않는다
    elif pending_before > 0:
        sent = try_send(send, outbox_path)
        now_ok = sent == pending_before
    elif not was_ok:
        now_ok = try_ping(ping)              # 보낼 것은 없지만 연결이 돌아왔는지 확인한다
    else:
        now_ok = True                        # 보낼 것도 없고 문제도 없었다

    pending_after = pending_before - sent
    messages = make_messages(was_ok, now_ok, new_event, sent, pending_after)
    link.update_link(link_path, link_ok=now_ok)
    link.add_messages(messages, link_path)
    return {"connected": now_ok, "sent": sent, "pending": pending_after, "messages": messages}


def make_messages(was_ok, now_ok, new_event, sent, pending):
    """상황에 맞는 알림 문장을 만든다. 같은 실패를 5초마다 되풀이해 알리지 않는다."""
    messages = []
    if not now_ok and pending > 0 and (new_event or was_ok):
        messages.append(f"[연결 안 됨] 이벤트를 로컬에 저장했습니다. 미전송 {pending}건")
    if now_ok and not was_ok:
        messages.append("[연결 복구] Edge Server 연결 확인")
        if sent > 0:
            messages.append(f"[전송 완료] 미전송 이벤트 {sent}건 전송")
    return messages


def try_send(send, outbox_path):
    """미전송 이벤트를 보내고 보낸 건수를 돌려준다. 어떤 오류도 밖으로 내보내지 않는다."""
    try:
        if send is None:
            send = server.make_sender()
        if send is None:
            return 0  # 접속 정보가 없다
        return outbox.send_pending(send, outbox_path)
    except Exception:
        return 0


def try_ping(ping):
    """서버에 연결만 해 본다. 되면 True."""
    try:
        if ping is None:
            ping = server.make_pinger()
        if ping is None:
            return False
        ping()
        return True
    except Exception:
        return False


def pending_count(outbox_path=outbox.OUTBOX_PATH):
    return len(outbox.list_pending(outbox_path))
