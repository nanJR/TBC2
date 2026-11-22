-- The project's "auto-enable RLS on new tables" helper (run by the ensure_rls event
-- trigger) was callable by browser roles through /rest/v1/rpc. They never need it.
revoke execute on function public.rls_auto_enable() from public, anon, authenticated;
