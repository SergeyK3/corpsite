-- ADR-034 local demo ONLY — remove demo tables and seed data.

DELETE FROM public.employee_certificates WHERE certificate_number LIKE 'DEMO-%';
DROP INDEX IF EXISTS public.ix_employee_certificates_employee_type;
DROP TABLE IF EXISTS public.employee_certificates;
DELETE FROM public.certificate_types WHERE code IN ('MED_SPEC', 'ACCRED');
DROP TABLE IF EXISTS public.certificate_types;
