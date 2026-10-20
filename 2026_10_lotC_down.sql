-- ROLLBACK of 2026_10_lotC_up.sql. DESTROYS saved scenarios, folders, broker profiles and events.
-- Export them first if you want to keep them:
--   copy (select * from public.scenarios) to stdout with csv header;   -- or use the Supabase table export
-- The application tolerates the tables being absent: saving then reports "Storage is not available", nothing else breaks.
begin;
drop table if exists public.events;
drop table if exists public.broker_profiles;
drop table if exists public.scenarios;
drop table if exists public.folders;
commit;
