"""Saved-version preview through the shared template renderer, without orders."""
from app.services.personnel_order_category_contract import TYPE, category_values
from app.services.personnel_order_template_draft_service import get_draft, TemplateDraftError


def preview_saved_category(template_id, expected_template_version_id, expected_revision, sample):
    from app.services.personnel_order_template_application_service import _render
    draft = get_draft(TYPE, template_id)
    if draft is None:
        raise TemplateDraftError('TEMPLATE_DRAFT_NOT_FOUND', 'Сохранённый черновик не найден.')
    if (draft['template_version_id'], draft['revision']) != (expected_template_version_id, expected_revision):
        raise TemplateDraftError('TEMPLATE_REVISION_CONFLICT', 'Черновик изменён. Откройте актуальную версию.', conflict=True)
    try:
        from app.services.personnel_order_category_classifier_contract import CONTRACT, is_classifier_template
        if is_classifier_template(draft) != (sample.get('contract') == CONTRACT):
            raise ValueError('Данные проверки не соответствуют контракту сохранённой версии.')
        variables = category_values(sample)
        rendered = _render(draft, variables)
    except ValueError as exc:
        raise TemplateDraftError('CATEGORY_SAMPLE_INVALID', str(exc)) from exc
    return dict(template_id=template_id, template_version_id=expected_template_version_id, revision=expected_revision,
                variables=variables, previews={locale:dict(title=rendered['title_'+locale], preamble=rendered['preamble_'+locale],
                    directive='ПРИКАЗЫВАЮ:' if locale=='ru' else 'БҰЙЫРАМЫН:', body=rendered['body_template_'+locale],
                    basis=rendered['basis_template_'+locale]) for locale in ('ru','kk')})
