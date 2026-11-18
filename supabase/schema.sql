-- Edge Server(모의) 저장소: 보안 이벤트 테이블
-- Supabase 의 SQL Editor 에서 한 번 실행한다. 이 파일은 기록용이다.
-- 서버로 오는 값은 다섯 가지(event_id, occurred_at, terminal_id, event_type, reauth_result)뿐이고,
-- received_at 은 서버가 받은 시각을 스스로 채운다.

create table if not exists public.security_events (
  event_id      text primary key,
  occurred_at   timestamptz not null,
  terminal_id   text not null,
  event_type    text not null,
  reauth_result text not null check (reauth_result in ('SUCCESS','FAILURE')),
  received_at   timestamptz not null default now()
);
alter table public.security_events enable row level security;
create policy "demo insert" on public.security_events for insert to anon with check (true);
create policy "demo select" on public.security_events for select to anon using (true);
