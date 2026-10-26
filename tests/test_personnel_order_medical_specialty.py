import unittest
from copy import deepcopy
from app.services.personnel_order_medical_specialty import specialty_values
from app.services.personnel_order_template_application_service import _render
from app.services.personnel_order_template_specs import get_personnel_order_template_spec
from app.services.personnel_order_transfer_contract import transfer_values
from app.services.personnel_order_concurrent_contract import concurrent_values
from tests.test_personnel_order_concurrent_contract import DATA, TEXTS

SPECIALTY = {"medical_specialty_id": 57, "name_ru": "Акушерство и гинекология", "name_kk": "Акушерия және гинекология"}


class SpecialtyRenderingTests(unittest.TestCase):
    def render(self, kind, snapshot, *, body=None):
        template = {**(get_personnel_order_template_spec("TRANSFER").initial_texts if kind == "TRANSFER" else TEXTS), "item_type_code": kind}
        if body:
            template.update(body)
        values = (transfer_values({**DATA, "position_ru": "Врач", "position_kk": "дәрігер"}) if kind == "TRANSFER" else concurrent_values(DATA, "2026-10-25"))
        values.update({"employee.full_name": "Тестовый Сотрудник", "employee.full_name_dative_ru": "Тестовому Сотруднику", "employee.full_name_accusative_ru": "Тестового Сотрудника", "effective_date": "2026-10-25"})
        original = deepcopy(template)
        values.update(specialty_values(kind, {"medical_specialty": snapshot}, template))
        result = _render(template, values, draft_preview=True)
        self.assertEqual(template, original)
        return result

    def test_transfer_uses_exact_language_and_does_not_decorate_basis(self):
        result = self.render("TRANSFER", SPECIALTY)
        self.assertIn("(Акушерство и гинекология)", result["body_template_ru"])
        self.assertIn("(Акушерия және гинекология)", result["body_template_kk"])
        self.assertNotIn("Акушерство", result["basis_template_ru"])

    def test_concurrent_suffix_is_after_full_placement_before_rate_in_both_languages(self):
        result = self.render("CONCURRENT_DUTY_START", SPECIALTY)
        self.assertIn("врача отделения терапии (Акушерство и гинекология) на 0,5", result["body_template_ru"])
        self.assertIn("терапия бөлімшесінің дәрігер (Акушерия және гинекология) 0,5 ставкада", result["body_template_kk"])

    def test_empty_or_cleared_specialty_preserves_original_text_exactly(self):
        for kind in ("TRANSFER", "CONCURRENT_DUTY_START"):
            plain = self.render(kind, None)
            selected = self.render(kind, SPECIALTY)
            self.assertNotEqual(plain["body_template_ru"], selected["body_template_ru"])
            if kind == "CONCURRENT_DUTY_START":
                self.assertIn("0,5 ставкада терапия бөлімшесінің дәрігер", plain["body_template_kk"])
                self.assertIn("врача отделения терапии на 0,5", plain["body_template_ru"])
            else:
                self.assertNotIn("Акушер", plain["body_template_ru"])

    def test_repeated_render_does_not_accumulate_parentheses(self):
        for kind in ("TRANSFER", "CONCURRENT_DUTY_START"):
            self.assertEqual(self.render(kind, SPECIALTY), self.render(kind, SPECIALTY))
            self.assertEqual(self.render(kind, SPECIALTY)["body_template_ru"].count("(Акушерство и гинекология)"), 1)

    def test_replacement_and_other_types_do_not_gain_a_specialty(self):
        self.assertEqual(specialty_values("HIRE", {"medical_specialty": SPECIALTY}, {}), {})
        self.assertEqual(specialty_values("CONCURRENT_DUTY_START", {"medical_specialty": SPECIALTY, "replacement": {"mode": "RATE"}}, TEXTS), {})

    def test_missing_kazakh_name_is_not_invented(self):
        with self.assertRaisesRegex(ValueError, "RU и KK"):
            specialty_values("TRANSFER", {"medical_specialty": {**SPECIALTY, "name_kk": ""}}, {})

    def test_malformed_snapshot_is_rejected(self):
        for snapshot in ("invalid", {**SPECIALTY, "medical_specialty_id": -1}):
            with self.assertRaises(ValueError):
                specialty_values("TRANSFER", {"medical_specialty": snapshot}, {})


if __name__ == "__main__":
    unittest.main()
