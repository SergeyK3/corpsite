"""Narrow CHECK normalization: no general cast removal or skipped constraints."""
import pytest
from scripts.personnel_vps_backup import canonical_check_definition

ORIGINAL="CHECK (((language)::text = ANY ((ARRAY['kk'::character varying, 'ru'::character varying])::text[])))"
RESTORED="CHECK (((language)::text = ANY (ARRAY[('kk'::character varying)::text, ('ru'::character varying)::text])))"


def test_reported_check_is_canonical_and_idempotent():
    assert canonical_check_definition(ORIGINAL)==RESTORED
    assert canonical_check_definition(RESTORED)==RESTORED


@pytest.mark.parametrize('changed',[
    RESTORED.replace("'ru'","'en'"),
    RESTORED.replace('ANY','ALL'),
    RESTORED.replace(' = ',' <> '),
    RESTORED+' NOT VALID',
    RESTORED+' NO INHERIT',
    ORIGINAL.replace('character varying','character varying(1)'),
    ORIGINAL.replace('::text[]','::integer[]'),
    ORIGINAL.replace("'ru'::character varying","NULL::character varying"),
])
def test_real_condition_and_constraint_changes_are_not_hidden(changed):
    assert canonical_check_definition(changed)!=canonical_check_definition(ORIGINAL)


@pytest.mark.parametrize('quoted',[
    "'"+ORIGINAL.replace("'","''")+"'",
    '"'+ORIGINAL+'"',
    '$definition$'+ORIGINAL+'$definition$',
    '/* outer /* nested */ '+ORIGINAL+' */',
    '-- '+ORIGINAL+'\n',
    "E'"+ORIGINAL.replace("'","\\'")+"'",
])
def test_quoted_sql_and_comments_are_opaque(quoted):
    assert canonical_check_definition(quoted)==quoted


def test_multiple_arrays_and_escaped_literals_preserve_surrounding_sql():
    old="CHECK (x = ANY ((ARRAY['a''b'::character varying])::text[]) OR "+ORIGINAL[7:-1]+')'
    expected="CHECK (x = ANY (ARRAY[('a''b'::character varying)::text]) OR "+RESTORED[7:-1]+')'
    assert canonical_check_definition(old)==expected
