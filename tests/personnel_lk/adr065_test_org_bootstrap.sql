-- Applied after revision r1s2t3u4v5w6 and before s2t3u4v5w6x.
-- Provides the single parented DISP required by the published seed migration.
INSERT INTO public.org_units (name, code, parent_unit_id, group_id, is_active)
SELECT 'ADR-065 test root', 'ADR065_ROOT', NULL, 3, TRUE
WHERE NOT EXISTS (SELECT 1 FROM public.org_units WHERE code = 'ADR065_ROOT');

INSERT INTO public.org_units (name, code, parent_unit_id, group_id, is_active)
SELECT 'ADR-065 test dispensary', 'DISP', r.unit_id, 3, TRUE
FROM public.org_units r
WHERE r.code = 'ADR065_ROOT'
  AND NOT EXISTS (SELECT 1 FROM public.org_units WHERE code = 'DISP');
