-- ADR-034 local demo ONLY — demonstration seed (DEMO-* certificate numbers).
-- Run after adr034_professional_documents_schema.sql.

INSERT INTO public.certificate_types (code, name, is_active)
VALUES
    ('MED_SPEC', 'Сертификат специалиста', TRUE),
    ('ACCRED', 'Аккредитация', TRUE)
ON CONFLICT (code) DO UPDATE SET
    name = EXCLUDED.name,
    is_active = EXCLUDED.is_active;

DELETE FROM public.employee_certificates
WHERE certificate_number LIKE 'DEMO-%';

INSERT INTO public.employee_certificates (
    employee_id,
    certificate_type_id,
    certificate_number,
    issued_at,
    expires_at,
    is_current
)
SELECT
    picked.employee_id,
    ct.certificate_type_id,
    picked.cert_number,
    CURRENT_DATE - 365,
    picked.expires_at,
    TRUE
FROM public.certificate_types ct
JOIN (
    SELECT *
    FROM (
        SELECT
            e.employee_id,
            ROW_NUMBER() OVER (ORDER BY e.employee_id) AS rn,
            CASE ROW_NUMBER() OVER (ORDER BY e.employee_id)
                WHEN 1 THEN CURRENT_DATE + 365
                WHEN 2 THEN CURRENT_DATE + 45
                WHEN 3 THEN CURRENT_DATE + 20
                WHEN 4 THEN CURRENT_DATE - 10
            END AS expires_at,
            CASE ROW_NUMBER() OVER (ORDER BY e.employee_id)
                WHEN 1 THEN 'DEMO-VALID'
                WHEN 2 THEN 'DEMO-60'
                WHEN 3 THEN 'DEMO-30'
                WHEN 4 THEN 'DEMO-EXP'
            END AS cert_number,
            CASE ROW_NUMBER() OVER (ORDER BY e.employee_id)
                WHEN 3 THEN 'ACCRED'
                ELSE 'MED_SPEC'
            END AS type_code
        FROM public.employees e
        WHERE e.is_active = TRUE
    ) ranked
    WHERE ranked.rn BETWEEN 1 AND 4
) picked ON ct.code = picked.type_code;
