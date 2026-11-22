-- =====================================================================
-- AIfound DB 스키마 (Supabase / PostgreSQL)  — 팀 통합본
--   · 1~10번 테이블과 매칭 함수: 주희선 님 schema.sql 그대로 (컬럼 이름 변경 없음)
--   · 추가(김준희): profiles, 가입 트리거, 접근 규칙(RLS), 사진 버킷
-- 실행: Supabase 대시보드 > SQL Editor 에 통째로 붙여넣고 Run (여러 번 실행해도 안전)
-- =====================================================================

create extension if not exists vector;

-- 1. 보관함 (09, 14) -------------------------------------------------------
create table if not exists lockers (
  id        uuid primary key default gen_random_uuid(),
  name      text not null,               -- 예: '형남공학관 1층 행정실'
  code      text,                        -- 예: 'B-03'
  building  text not null,
  location  text,                        -- 찾아가는 길
  hours     text                         -- 예: '평일 09:00-18:00'
);

-- 2. 습득물 (10~15) --------------------------------------------------------
create table if not exists found_items (
  id              uuid primary key default gen_random_uuid(),
  finder_id       uuid references auth.users(id),
  category        text not null,          -- '이어폰','지갑','학생증·카드','휴대폰','기타'
  attrs           jsonb not null default '{}',
                  -- 12 화면에서 확인/수정한 값 {category, subcategory, brand, model, color, features[], title}
  description     text,                   -- 13 '물건 특징(선택)'
  building        text,                   -- 13 건물
  location_detail text,                   -- 13 상세 위치 (예: 3층 302호 앞)
  found_at        timestamptz not null default now(),
  locker_id       uuid references lockers(id),
  photo_path      text,                   -- 가림 처리된 사진의 Storage 경로
  status          text not null default 'stored',     -- stored / returned
  match_status    text not null default 'pending',    -- pending/searching/notified/no_match (15)
  embedding       vector(768),
  created_at      timestamptz not null default now()
);

-- 3. 분실 신고 (16) ---------------------------------------------------------
create table if not exists lost_reports (
  id          uuid primary key default gen_random_uuid(),
  owner_id    uuid not null references auth.users(id),
  category    text not null,
  attrs       jsonb not null default '{}',   -- {category, brand, model, color, features[]}
  description text,                          -- 특징 설명
  buildings   text[] not null default '{}',  -- 잃어버린 곳 (여러 개)
  lost_from   timestamptz not null,          -- 언제쯤: 12:00
  lost_to     timestamptz not null,          --          ~ 15:00
  photo_path  text,                          -- 참고 사진(선택)
  status      text not null default 'open',  -- open / closed
  embedding   vector(768),
  created_at  timestamptz not null default now()
);

-- 4. 매칭 결과 (18, 19, 21) — 주희선 파트가 채움 ------------------------------
create table if not exists matches (
  id             uuid primary key default gen_random_uuid(),
  found_item_id  uuid not null references found_items(id) on delete cascade,
  lost_report_id uuid not null references lost_reports(id) on delete cascade,
  score          int not null,
  detail         jsonb,
  reason         text,
  short_reason   text,
  ai_likelihood  int,
  status         text not null default 'candidate',
                 -- candidate / claimed / received / rejected / closed
  feedback       jsonb,
  seen           boolean not null default false,
  notified       boolean not null default false,
  claimed_at     timestamptz,
  pickup_deadline timestamptz,
  reminded       boolean not null default false,
  created_at     timestamptz not null default now(),
  unique (found_item_id, lost_report_id)
);

-- 5. 보관함 담당자 ------------------------------------------------------------
create table if not exists locker_staff (
  user_id   uuid not null references auth.users(id) on delete cascade,
  locker_id uuid not null references lockers(id) on delete cascade,
  primary key (user_id, locker_id)
);

-- 6. 수령 기록 (25) ----------------------------------------------------------
create table if not exists pickups (
  id            uuid primary key default gen_random_uuid(),
  match_id      uuid references matches(id),
  found_item_id uuid not null references found_items(id),
  receiver_id   uuid not null references auth.users(id),
  finder_id     uuid references auth.users(id),
  locker_id     uuid references lockers(id),
  code          text,
  verified_by   uuid references auth.users(id),
  received_at   timestamptz not null default now()
);

-- 7. 알림함 (27) -------------------------------------------------------------
create table if not exists notifications (
  id         uuid primary key default gen_random_uuid(),
  user_id    uuid not null references auth.users(id) on delete cascade,
  type       text not null,
  title      text not null,
  body       text,
  data       jsonb,
  read       boolean not null default false,
  created_at timestamptz not null default now()
);

-- 8. 알림 설정 (26) ----------------------------------------------------------
create table if not exists user_settings (
  user_id            uuid primary key references auth.users(id) on delete cascade,
  match_alert        boolean not null default true,
  owner_alert        boolean not null default true,
  pickup_reminder    boolean not null default false,
  interest_buildings text[] default '{}',
  quiet_start        time,
  quiet_end          time
);

-- 9. 푸시 토큰 ---------------------------------------------------------------
create table if not exists user_devices (
  fcm_token  text primary key,
  user_id    uuid not null references auth.users(id) on delete cascade,
  updated_at timestamptz not null default now()
);

-- 10. 벡터 검색 인덱스 + 매칭 함수 (주희선) ------------------------------------
create index if not exists found_items_embedding_idx
  on found_items using hnsw (embedding vector_cosine_ops);
create index if not exists lost_reports_embedding_idx
  on lost_reports using hnsw (embedding vector_cosine_ops);

create or replace function match_lost_for_found(p_found_id uuid, p_days int default 14, p_limit int default 20)
returns table (id uuid, owner_id uuid, category text, attrs jsonb, description text,
               buildings text[], lost_from timestamptz, lost_to timestamptz, similarity float)
language sql stable as $$
  select l.id, l.owner_id, l.category, l.attrs, l.description, l.buildings, l.lost_from, l.lost_to,
         1 - (l.embedding <=> f.embedding) as similarity
  from found_items f
  join lost_reports l
    on l.status = 'open'
   and l.embedding is not null
   and (l.category = f.category or '기타' in (l.category, f.category))
   and l.lost_from <= f.found_at + interval '1 hour'
   and l.lost_to   >= f.found_at - make_interval(days => p_days)
  where f.id = p_found_id and f.embedding is not null
  order by l.embedding <=> f.embedding
  limit p_limit;
$$;

create or replace function match_found_for_lost(p_lost_id uuid, p_days int default 14, p_limit int default 20)
returns table (id uuid, category text, attrs jsonb, description text, building text,
               location_detail text, found_at timestamptz, locker_id uuid, similarity float)
language sql stable as $$
  select f.id, f.category, f.attrs, f.description, f.building, f.location_detail, f.found_at, f.locker_id,
         1 - (f.embedding <=> l.embedding) as similarity
  from lost_reports l
  join found_items f
    on f.status = 'stored'
   and f.embedding is not null
   and (f.category = l.category or '기타' in (l.category, f.category))
   and f.found_at >= l.lost_from - interval '1 hour'
   and f.found_at <= l.lost_to + make_interval(days => p_days)
  where l.id = p_lost_id and l.embedding is not null
  order by f.embedding <=> l.embedding
  limit p_limit;
$$;

-- =====================================================================
-- 여기부터 김준희 추가분
-- =====================================================================

-- 11. 프로필 (03) -----------------------------------------------------------
create table if not exists profiles (
  id          uuid primary key references auth.users(id) on delete cascade,
  email       text not null,
  name        text,
  department  text,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);

-- 자주 쓰는 조회용 인덱스
create index if not exists found_items_list_idx on found_items (status, category, found_at desc);
create index if not exists found_items_finder_idx on found_items (finder_id);
create index if not exists lost_reports_owner_idx on lost_reports (owner_id, created_at desc);

-- 12. 가입하면 profiles·user_settings 한 줄씩 자동 생성 ------------------------
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer set search_path = public
as $$
begin
  insert into public.profiles (id, email) values (new.id, coalesce(new.email, ''))
  on conflict (id) do nothing;
  insert into public.user_settings (user_id) values (new.id)
  on conflict (user_id) do nothing;
  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

-- 13. 접근 규칙 (RLS) --------------------------------------------------------
--   · 서버(service_role 키)는 RLS 를 무시하므로 서버 기능에는 영향 없음
--   · 앱이 Supabase 에 직접 읽는 표(07, 08, 22~25)만 '로그인한 학생 / 내 것만' 허용
--   · 앱에서 직접 쓰기(insert/update/delete)는 profiles·user_settings 의 내 행 수정만 허용,
--     나머지 쓰기는 전부 서버 API 를 거친다
alter table profiles       enable row level security;
alter table lockers        enable row level security;
alter table found_items    enable row level security;
alter table lost_reports   enable row level security;
alter table matches        enable row level security;
alter table locker_staff   enable row level security;
alter table pickups        enable row level security;
alter table notifications  enable row level security;
alter table user_settings  enable row level security;
alter table user_devices   enable row level security;

-- 정책은 다시 실행해도 되게 지우고 만든다
drop policy if exists "profiles: 내 것 읽기"        on profiles;
drop policy if exists "profiles: 내 것 수정"        on profiles;
drop policy if exists "lockers: 로그인하면 읽기"     on lockers;
drop policy if exists "found: 로그인하면 읽기"       on found_items;
drop policy if exists "lost: 내 것 읽기"            on lost_reports;
drop policy if exists "matches: 관련된 사람 읽기"    on matches;
drop policy if exists "pickups: 관련된 사람 읽기"    on pickups;
drop policy if exists "notifications: 내 것 읽기"    on notifications;
drop policy if exists "notifications: 내 것 읽음표시" on notifications;
drop policy if exists "settings: 내 것 읽기"        on user_settings;
drop policy if exists "settings: 내 것 수정"        on user_settings;

create policy "profiles: 내 것 읽기" on profiles
  for select to authenticated using (id = auth.uid());
create policy "profiles: 내 것 수정" on profiles
  for update to authenticated using (id = auth.uid()) with check (id = auth.uid());

create policy "lockers: 로그인하면 읽기" on lockers
  for select to authenticated using (true);

-- 07 찾아보기: 로그인한 학생은 보관 중인 습득물 전체 + 내가 등록한 것
create policy "found: 로그인하면 읽기" on found_items
  for select to authenticated using (status = 'stored' or finder_id = auth.uid());

-- 23 내 분실 신고: 내 것만
create policy "lost: 내 것 읽기" on lost_reports
  for select to authenticated using (owner_id = auth.uid());

-- 18·19 매칭: 신고한 사람 또는 습득물을 등록한 사람
create policy "matches: 관련된 사람 읽기" on matches
  for select to authenticated using (
    exists (select 1 from lost_reports l where l.id = lost_report_id and l.owner_id = auth.uid())
    or exists (select 1 from found_items f where f.id = found_item_id and f.finder_id = auth.uid())
  );

-- 25 수령 기록: 찾아간 사람 또는 주운 사람
create policy "pickups: 관련된 사람 읽기" on pickups
  for select to authenticated using (receiver_id = auth.uid() or finder_id = auth.uid());

-- 27 알림함
create policy "notifications: 내 것 읽기" on notifications
  for select to authenticated using (user_id = auth.uid());
create policy "notifications: 내 것 읽음표시" on notifications
  for update to authenticated using (user_id = auth.uid()) with check (user_id = auth.uid());

-- 26 알림 설정
create policy "settings: 내 것 읽기" on user_settings
  for select to authenticated using (user_id = auth.uid());
create policy "settings: 내 것 수정" on user_settings
  for update to authenticated using (user_id = auth.uid()) with check (user_id = auth.uid());

-- locker_staff, user_devices 는 정책 없음 = 서버만 접근

-- 14. 사진 저장 버킷 (비공개) --------------------------------------------------
--   found/...  : 가림 처리된 습득물 사진 → 로그인한 학생 누구나 볼 수 있음 (07, 08)
--   lost/...   : 분실 신고 참고 사진 → 서버가 서명 URL 로만 제공
insert into storage.buckets (id, name, public)
values ('found-photos', 'found-photos', false)
on conflict (id) do nothing;

drop policy if exists "found-photos: 로그인하면 습득물 사진 읽기" on storage.objects;
create policy "found-photos: 로그인하면 습득물 사진 읽기" on storage.objects
  for select to authenticated
  using (bucket_id = 'found-photos' and (storage.foldername(name))[1] = 'found');

-- 15. 보관함 예시 데이터 — 주희선 님이 실제 행정실·안내데스크로 교체 ----------
-- insert into lockers (name, code, building, location, hours) values
--   ('형남공학관 1층 행정실', null, '형남공학관', '정문 들어와서 오른쪽', '평일 09:00-18:00');
