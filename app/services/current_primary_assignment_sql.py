"""Current primary assignment selected for the personnel roster and position scopes."""

CURRENT_PRIMARY_ASSIGNMENT_LATERAL_SQL = """
 LEFT JOIN LATERAL (
     SELECT pa.assignment_id, pa.position_id, pa.org_unit_id, pa.rate,
            NULLIF(to_jsonb(pa)->>'manual_type_code','')::smallint AS manual_type_code
     FROM (
         SELECT pa.*, COUNT(*) OVER () AS candidate_count
         FROM public.person_assignments pa
         WHERE pa.person_id = e.person_id
           AND pa.active_flag IS TRUE
           AND pa.is_primary IS TRUE
           AND pa.lifecycle_status = 'active'
           AND pa.start_date <= CURRENT_DATE
           AND (pa.end_date IS NULL OR pa.end_date >= CURRENT_DATE)
     ) pa
     WHERE pa.candidate_count = 1
 ) current_pa ON TRUE
"""
