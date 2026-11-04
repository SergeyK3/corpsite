"""HIRE position wrappers belong to the template, never to the saved title."""
import re
from typing import Any, Mapping

_PAIRS = (('«', '»'), ('“', '”'), ('"', '"'))
_POSITION_TOKEN = r'(\{\{\s*position\.(?:title_ru|title_kk|document_nominative_ru|document_possessive_kk)\s*\}\})'


def hire_body_template_without_position_quotes(value: str) -> str:
    for opening, closing in _PAIRS:
        value = re.sub(re.escape(opening) + _POSITION_TOKEN + re.escape(closing), r'\1', value)
    return value


def hire_generated_body_without_position_quotes(value: str, locale: str, payload: Mapping[str, Any]) -> str:
    """Project only a known generated assignment clause, preserving its values.

    Both complete saved names must match. No regex is applied to name contents,
    and no quote characters elsewhere in the document are replaced.
    """
    def mapping(key):
        result = payload.get(key)
        return result if isinstance(result, Mapping) else {}
    position = mapping('document_position')
    unit = mapping('document_org_unit')
    ru = mapping('document_forms_ru')
    kk = mapping('document_forms_kk')
    positions = [position.get('name' if locale == 'ru' else 'name_kk'),
                 position.get('document_nominative_ru' if locale == 'ru' else 'document_possessive_kk'),
                 payload.get('position_title_' + locale), payload.get('source_position_name') if locale == 'ru' else None,
                 ru.get('position_document_nominative_ru') if locale == 'ru' else kk.get('position_document_possessive_kk')]
    units = [unit.get('name' if locale == 'ru' else 'name_kk'),
             payload.get('source_org_unit_name') if locale == 'ru' else payload.get('org_unit_title_kk'),
             unit.get('document_genitive_kk') if locale == 'kk' else None,
             kk.get('org_unit_document_genitive_kk') if locale == 'kk' else None]
    for key, values in (('position_name', positions), ('org_unit_name', units)):
        saved = payload.get(key)
        values.append(saved.get(locale) if isinstance(saved, Mapping) else saved if locale == 'ru' else None)
    for title in sorted({text for text in positions if isinstance(text, str) and text}, key=len, reverse=True):
        for department in sorted({text for text in units if isinstance(text, str) and text}, key=len, reverse=True):
            for opening, closing in _PAIRS:
                if locale == 'ru':
                    before = f'в подразделение «{department}» на должность {opening}{title}{closing} со ставкой'
                    after = f'в подразделение «{department}» на должность {title} со ставкой'
                else:
                    before = f'«{department}» бөлімшесіне {opening}{title}{closing} лауазымына'
                    after = f'«{department}» бөлімшесіне {title} лауазымына'
                if before in value:
                    return value.replace(before, after, 1)
    return value
