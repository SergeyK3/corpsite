-- ADR-047 — Personal File migration volume inventory (read-only SELECT)
-- Run: psql "$DATABASE_URL" -f docs/adr/ADR-047-sql-inventory.sql
-- Or paste sections in any SQL client connected to Corpsite DB.

\echo '=== Core identity & operational ==='

SELECT 'persons' AS metric, COUNT(*) AS cnt FROM public.persons
UNION ALL SELECT 'persons_active', COUNT(*) FROM public.persons WHERE person_status = 'active'
UNION ALL SELECT 'employees', COUNT(*) FROM public.employees
UNION ALL SELECT 'employees_with_person_id', COUNT(*) FROM public.employees WHERE person_id IS NOT NULL
UNION ALL SELECT 'employees_active', COUNT(*) FROM public.employees WHERE is_active = TRUE
UNION ALL SELECT 'employees_operational_active', COUNT(*) FROM public.employees WHERE operational_status = 'active'
UNION ALL SELECT 'person_assignments', COUNT(*) FROM public.person_assignments
UNION ALL SELECT 'person_assignments_active', COUNT(*) FROM public.person_assignments WHERE lifecycle_status = 'active'
UNION ALL SELECT 'employee_events', COUNT(*) FROM public.employee_events
UNION ALL SELECT 'employee_identities', COUNT(*) FROM public.employee_identities
UNION ALL SELECT 'employee_identities_iin_active', COUNT(*) FROM public.employee_identities
    WHERE identity_type = 'IIN' AND valid_to IS NULL
UNION ALL SELECT 'employee_documents', COUNT(*) FROM public.employee_documents
UNION ALL SELECT 'employee_documents_active', COUNT(*) FROM public.employee_documents WHERE lifecycle_status = 'ACTIVE'
UNION ALL SELECT 'employee_documents_from_import', COUNT(*) FROM public.employee_documents
    WHERE source_normalized_record_id IS NOT NULL
UNION ALL SELECT 'employee_documents_superseded', COUNT(*) FROM public.employee_documents WHERE lifecycle_status = 'SUPERSEDED';

\echo '=== Import layer ==='

SELECT 'hr_import_batches' AS metric, COUNT(*) AS cnt FROM public.hr_import_batches
UNION ALL SELECT 'hr_import_rows', COUNT(*) FROM public.hr_import_rows
UNION ALL SELECT 'hr_import_rows_with_employee', COUNT(*) FROM public.hr_import_rows WHERE employee_id IS NOT NULL
UNION ALL SELECT 'hr_import_rows_with_profile_override', COUNT(*) FROM public.hr_import_rows
    WHERE profile_override IS NOT NULL
UNION ALL SELECT 'hr_import_document_candidates', COUNT(*) FROM public.hr_import_document_candidates
UNION ALL SELECT 'employee_import_profile_overrides', COUNT(*) FROM public.employee_import_profile_overrides
UNION ALL SELECT 'employee_import_profile_overrides_active', COUNT(*) FROM public.employee_import_profile_overrides
    WHERE profile_status = 'active'
UNION ALL SELECT 'hr_source_files', COUNT(*) FROM public.hr_source_files;

\echo '=== Normalized records ==='

SELECT record_kind, COUNT(*) AS cnt
FROM public.hr_import_normalized_records
GROUP BY record_kind
ORDER BY cnt DESC;

SELECT review_status, COUNT(*) AS cnt
FROM public.hr_import_normalized_records
GROUP BY review_status
ORDER BY cnt DESC;

SELECT
    COUNT(*) FILTER (WHERE employee_id IS NOT NULL) AS with_employee,
    COUNT(*) FILTER (WHERE employee_id IS NULL) AS without_employee,
    COUNT(*) FILTER (WHERE promoted_document_id IS NOT NULL) AS promoted_to_document
FROM public.hr_import_normalized_records;

\echo '=== Canonical registry ==='

SELECT 'hr_canonical_snapshots' AS metric, COUNT(*) AS cnt FROM public.hr_canonical_snapshots
UNION ALL SELECT 'hr_canonical_snapshots_active', COUNT(*) FROM public.hr_canonical_snapshots WHERE status = 'active'
UNION ALL SELECT 'hr_canonical_snapshot_entries', COUNT(*) FROM public.hr_canonical_snapshot_entries
UNION ALL SELECT 'hr_change_events', COUNT(*) FROM public.hr_change_events
UNION ALL SELECT 'hr_personnel_change_events', COUNT(*) FROM public.hr_personnel_change_events
UNION ALL SELECT 'hr_review_overrides', COUNT(*) FROM public.hr_review_overrides
UNION ALL SELECT 'hr_review_overrides_active', COUNT(*) FROM public.hr_review_overrides WHERE status = 'active';

SELECT
    COUNT(*) AS canonical_entries_total,
    COUNT(*) FILTER (WHERE employee_id IS NOT NULL) AS with_employee,
    COUNT(*) FILTER (WHERE iin IS NOT NULL) AS with_iin,
    COUNT(DISTINCT match_key) AS distinct_match_keys
FROM public.hr_canonical_snapshot_entries;

\echo '=== Linkage & auxiliary ==='

SELECT
    (SELECT COUNT(*) FROM public.persons) AS persons,
    (SELECT COUNT(*) FROM public.employees) AS employees,
    (SELECT COUNT(*) FROM public.employees WHERE person_id IS NOT NULL) AS employees_with_person,
    (SELECT COUNT(DISTINCT person_id) FROM public.employees WHERE person_id IS NOT NULL) AS distinct_persons_linked,
    (SELECT COUNT(*) FROM public.persons p
        WHERE NOT EXISTS (SELECT 1 FROM public.employees e WHERE e.person_id = p.person_id)
    ) AS persons_without_employee,
    (SELECT COUNT(*) FROM public.users WHERE employee_id IS NOT NULL) AS users_with_employee,
    (SELECT COUNT(*) FROM public.contacts) AS contacts,
    (SELECT COUNT(*) FROM public.contacts WHERE person_id IS NOT NULL) AS contacts_with_person;

\echo '=== employee_events breakdown ==='

SELECT event_type, COUNT(*) AS cnt
FROM public.employee_events
GROUP BY event_type
ORDER BY cnt DESC;

\echo '=== import batches by status ==='

SELECT status, COUNT(*) AS cnt
FROM public.hr_import_batches
GROUP BY status
ORDER BY cnt DESC;

\echo '=== Latest batch row counts (top 5) ==='

SELECT b.batch_id, b.file_name, b.status, b.total_rows, b.imported_at,
       COUNT(r.row_id) AS rows_in_db
FROM public.hr_import_batches b
LEFT JOIN public.hr_import_rows r ON r.batch_id = b.batch_id
GROUP BY b.batch_id, b.file_name, b.status, b.total_rows, b.imported_at
ORDER BY b.imported_at DESC NULLS LAST
LIMIT 5;

\echo '=== Profile override JSONB section sizes (employees with overrides) ==='

SELECT
    COUNT(*) AS overrides_total,
    COUNT(*) FILTER (WHERE profile_override ? 'education_records') AS has_education,
    COUNT(*) FILTER (WHERE profile_override ? 'training_records') AS has_training,
    COUNT(*) FILTER (WHERE profile_override ? 'certificate_records') AS has_certificates,
    COUNT(*) FILTER (WHERE profile_override ? 'category_records') AS has_categories,
    COUNT(*) FILTER (WHERE profile_override ? 'award_records') AS has_awards,
    COUNT(*) FILTER (WHERE profile_override ? 'degrees') AS has_degrees
FROM public.employee_import_profile_overrides;

\echo '=== Done ==='
