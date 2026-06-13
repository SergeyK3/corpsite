-- ADR-034 local demo ONLY — do not run on VPS/production.
-- Schema for certificate_types + employee_certificates (demonstration read-model).

CREATE TABLE IF NOT EXISTS public.certificate_types (
    certificate_type_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS public.employee_certificates (
    certificate_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    employee_id BIGINT NOT NULL,
    certificate_type_id BIGINT NOT NULL,
    certificate_number TEXT NULL,
    issued_at DATE NULL,
    expires_at DATE NULL,
    is_current BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT fk_employee_certificates_employee
        FOREIGN KEY (employee_id)
        REFERENCES public.employees(employee_id),
    CONSTRAINT fk_employee_certificates_type
        FOREIGN KEY (certificate_type_id)
        REFERENCES public.certificate_types(certificate_type_id)
);

CREATE INDEX IF NOT EXISTS ix_employee_certificates_employee_type
ON public.employee_certificates (employee_id, certificate_type_id)
WHERE is_current = TRUE;
