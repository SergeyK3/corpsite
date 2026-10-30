from app.services.directory_service import _employee_document_forms


def test_explicit_person_and_employee_forms_are_exposed_without_calculating_missing_cases():
    row={"person_document_source":{"document_forms_ru":{"employee_full_name_genitive_ru":" Person RU "}},
         "employee_document_source":{"document_forms_ru":{"employee_full_name_genitive_ru":"Employee RU","position_document_genitive_ru":"Position RU"},
                                     "name":{"full_name_genitive_kk":"Saved KK"}}}
    assert _employee_document_forms(row,"ru")=={"employee_full_name_genitive_ru":"Employee RU","position_document_genitive_ru":"Position RU"}
    assert _employee_document_forms(row,"kk")=={"employee_full_name_genitive_kk":"Saved KK"}
    assert _employee_document_forms({"employee_document_source":{"full_name":"Тестов Айдар Ерланович"}},"ru")=={}
