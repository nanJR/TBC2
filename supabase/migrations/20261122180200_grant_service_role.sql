-- This project gives service_role no data rights on new tables by default. The back end
-- (the only client of these tables) gets just what it needs: no DELETE anywhere, and the
-- audit log is append-only.
grant select, insert, update on public.profiles, public.screenings, public.cases,
  public.patients, public.actions, public.van_slots, public.abha_records to service_role;
grant select, insert on public.audit_log to service_role;
