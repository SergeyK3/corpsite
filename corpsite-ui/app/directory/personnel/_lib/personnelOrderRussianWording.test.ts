import { describe, expect, it } from "vitest";
import { russianEmployeeGenitiveForOrder, savedRussianEmployeeNameForm } from "./personnelOrderRussianWording";

describe("Russian document name forms", () => {
  it.each([
    ["Тестова Анна Сергеевна", "Тестовой Анны Сергеевны"],
    ["Ильясова Ассель Адиловна", "Ильясовой Ассель Адиловны"],
    ["Маженова Альбина Сериковна", "Маженовой Альбины Сериковны"],
    ["Иванов Иван Иванович", "Иванова Ивана Ивановича"],
    ["Петров Павел Львович", "Петрова Павла Львовича"],
    ["Иванова Мария Ивановна", "Ивановой Марии Ивановны"],
  ])("suggests %s without changing the source", (fio, expected) => {
    const source = Object.freeze({ fio });
    expect(russianEmployeeGenitiveForOrder(source)).toBe(expected);
    expect(source.fio).toBe(fio);
  });
  it("prefers structured source fields and saved document forms", () => {
    const source = { fio: "Не использовать", last_name: "Тестова", first_name: "Анна", middle_name: "Сергеевна" };
    expect(russianEmployeeGenitiveForOrder(source)).toBe("Тестовой Анны Сергеевны");
    expect(russianEmployeeGenitiveForOrder({ ...source, document_forms_ru: { employee_full_name_genitive_ru: "Сохранённая форма" } })).toBe("Сохранённая форма");
    expect(russianEmployeeGenitiveForOrder({ ...source, employee_full_name_genitive_ru: "Прямая форма" })).toBe("Прямая форма");
    expect(savedRussianEmployeeNameForm({ name: { full_name_dative_ru: "Сохранённый дательный" } }, "dative")).toBe("Сохранённый дательный");
  });
  it.each([null, { fio: "Иванова А. И." }, { fio: "Иванова Анна" }, { fio: "Unknown Name Patronymic" }, { fio: "Дюма Анна Ивановна" }])("leaves incomplete or ambiguous inputs for manual entry: %j", source => {
    expect(russianEmployeeGenitiveForOrder(source)).toBe("");
  });
});
