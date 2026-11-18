"""Edge Server(모의) 접속. Supabase 의 PostgreSQL 에 연결 문자열로 직접 접속한다.

접속 정보는 .streamlit/secrets.toml 의 DATABASE_URL 에 둔다(커밋하지 않는다).
"""

import tomllib
from pathlib import Path

import psycopg

SECRETS_PATH = Path(__file__).parent.parent / ".streamlit" / "secrets.toml"
CONNECT_TIMEOUT = 3  # 초. 서버가 안 잡혀도 화면이 오래 멈추지 않게 한다

INSERT_SQL = """
insert into public.security_events
    (event_id, occurred_at, terminal_id, event_type, reauth_result)
values
    (%(event_id)s, %(occurred_at)s, %(terminal_id)s, %(event_type)s, %(reauth_result)s)
on conflict (event_id) do nothing
"""

SELECT_SQL = """
select event_id, occurred_at, terminal_id, event_type, reauth_result, received_at
from public.security_events
order by occurred_at desc
limit %(limit)s
"""

COUNT_SQL = """
select count(*),
       count(*) filter (where reauth_result = 'SUCCESS'),
       count(*) filter (where reauth_result = 'FAILURE')
from public.security_events
"""


def load_database_url(path=SECRETS_PATH):
    """접속 주소를 읽는다. 파일이나 값이 없으면 None."""
    if not path.exists():
        return None
    secrets = tomllib.loads(path.read_text(encoding="utf-8-sig"))
    url = secrets.get("DATABASE_URL")
    if not url or "[YOUR-PASSWORD]" in url:
        return None
    return url


def send_event(database_url, payload):
    """이벤트 하나를 서버에 넣는다. 같은 event_id 가 이미 있으면 아무 일도 하지 않는다."""
    with psycopg.connect(database_url, connect_timeout=CONNECT_TIMEOUT) as conn:
        conn.execute(INSERT_SQL, payload)


def make_sender(path=SECRETS_PATH):
    """payload 하나를 받아 서버로 보내는 함수를 만든다. 접속 정보가 없으면 None."""
    database_url = load_database_url(path)
    if database_url is None:
        return None

    def send(payload):
        send_event(database_url, payload)

    return send


def make_pinger(path=SECRETS_PATH):
    """서버에 연결만 해 보는 함수를 만든다. 접속 정보가 없으면 None."""
    database_url = load_database_url(path)
    if database_url is None:
        return None

    def ping():
        with psycopg.connect(database_url, connect_timeout=CONNECT_TIMEOUT) as conn:
            conn.execute("select 1")

    return ping


def fetch_events(database_url, limit=200):
    """서버의 이벤트를 최근 것부터 dict 목록으로 가져온다."""
    with psycopg.connect(database_url, connect_timeout=CONNECT_TIMEOUT) as conn:
        cursor = conn.execute(SELECT_SQL, {"limit": limit})
        columns = [column.name for column in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]


def fetch_counts(database_url):
    """전체, 성공, 실패 건수를 가져온다."""
    with psycopg.connect(database_url, connect_timeout=CONNECT_TIMEOUT) as conn:
        total, success, failure = conn.execute(COUNT_SQL).fetchone()
    return {"total": total, "success": success, "failure": failure}


def short_error(error):
    """오류를 화면에 보여줄 한 줄로 줄인다."""
    lines = str(error).splitlines()
    first_line = lines[0] if lines else ""
    return f"{type(error).__name__}: {first_line[:200]}"
