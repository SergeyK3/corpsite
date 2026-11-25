import {expect, it} from "vitest";
import {savedRussianEmployeeNameForm} from "./personnelOrderRussianWording";
import {buildItemPayload, itemPayloadDraftFromRecord} from "./personnelOrderPayload";
import {russianTransferAccusative} from "./personnelOrderTransferAccusative";

it("preserves a manually confirmed female accusative when saving and reopening", () => {
  const source = {document_forms_ru: {employee_full_name_accusative_ru: "Тестову Анну Ивановну"}, to_rate: 0.75};
  const draft = itemPayloadDraftFromRecord(source);
  expect(draft.employee_full_name_accusative_ru).toBe("Тестову Анну Ивановну");
  expect(buildItemPayload("TRANSFER", draft)).toEqual(source);
  draft.employee_full_name_accusative_ru = "Ручная подтверждённая форма";
  expect(itemPayloadDraftFromRecord(buildItemPayload("TRANSFER", draft)).employee_full_name_accusative_ru).toBe("Ручная подтверждённая форма");
  expect(source.document_forms_ru.employee_full_name_accusative_ru).toBe("Тестову Анну Ивановну");
});

it.each([
  {document_forms_ru: {employee_full_name_accusative_ru: "Тестову Анну Ивановну"}},
  {name: {full_name_accusative_ru: "Тестову Анну Ивановну"}},
  {employee_full_name_accusative_ru: "Тестову Анну Ивановну"},
])("uses the existing saved-form contract: %j", source => {
  expect(savedRussianEmployeeNameForm(source, "accusative")).toBe("Тестову Анну Ивановну");
});

it("never derives the accusative from a nominative or dative", () => {
  expect(savedRussianEmployeeNameForm({fio:"Тестова Анна Ивановна", document_forms_ru:{employee_full_name_dative_ru:"Тестовой Анне Ивановне"}}, "accusative")).toBe("");
});

it.each([
  ["Кашкинбаева Гульжан Нурахметовна", "Кашкинбаеву Гульжан Нурахметовну"],
  ["Иванов Иван Иванович", "Иванова Ивана Ивановича"],
  ["Иванова Анна Ивановна", "Иванову Анну Ивановну"],
  ["Петров Сергей Петрович", "Петрова Сергея Петровича"],
  ["Толстой Павел Ильич", "Толстого Павла Ильича"],
  ["Достоевский Лев Петрович", "Достоевского Льва Петровича"],
  ["Жуковский Пётр Сергеевич", "Жуковского Петра Сергеевича"],
  ["Белая Мария Сергеевна", "Белую Марию Сергеевну"],
  ["Синяя Наталья Ивановна", "Синюю Наталью Ивановну"],
  ["Ким Ассель Адиловна", "Ким Ассель Адиловну"],
  ["Блок Любовь Ильинична", "Блок Любовь Ильиничну"],
  ["Шевченко Юлия Ивановна", "Шевченко Юлию Ивановну"],
  ["Седых Андрей Никитич", "Седых Андрея Никитича"],
  ["Ким Игорь Петрович", "Кима Игоря Петровича"],
  ["Дюма Николя Петрович", "Дюма Николя Петровича"],
  ["Иванова-Петрова Анна-Мария Петровна", "Иванову-Петрову Анну-Марию Петровну"],
  ["КАШКИНБАЕВА ГУЛЬЖАН НУРАХМЕТОВНА", "КАШКИНБАЕВУ ГУЛЬЖАН НУРАХМЕТОВНУ"],
])("suggests the accusative of %s without changing indeclinable components", (fio, expected) => {
  const source = Object.freeze({fio});
  expect(russianTransferAccusative(source)).toBe(expected);
  expect(source.fio).toBe(fio);
});

it.each([
  [{last_name:"Кашкинбаева",first_name:"Гульжан",middle_name:"Нурахметовна",fio:"Другое отображаемое имя"}, "Кашкинбаеву Гульжан Нурахметовну"],
  [{fio:"Петров Никита",gender:"M"}, "Петрова Никиту"],
  [{fio:"Петрова Гульжан",sex:"F"}, "Петрову Гульжан"],
  [{fio:"Ким Мари",gender:"female"}, "Ким Мари"],
  [{fio:"Иванов Алексей",gender:"male"}, "Иванова Алексея"],
  [{fio:"Ким Али Алиев оглы",gender:"male"}, ""], // Four components cannot be split reliably.
  [{fio:"Ким Али Алиұлы"}, "Кима Али Алиұлы"],
  [{fio:"Ким Айгуль Алиқызы"}, "Ким Айгуль Алиқызы"],
])("uses name components and reliable gender: %j", (source, expected) => {
  expect(russianTransferAccusative(source)).toBe(expected);
});

it.each([
  {fio:"Ким Саша"},
  {fio:"Неизвестный"},
  {fio:"Иванов И. И."},
  {fio:"Иванов Иван Неизвестно"},
  {fio:"Иванов Иван Иванович",gender:"female"},
  {fio:"Кашкинбаева Гульжан Нурахметовна",gender:"male"},
  {fio:"Иванов Иван",gender:"M",sex:"F"},
  {fio:"Иванова Ивана Ивановича"}, // An already declined source is not a nominative.
  {fio:"Боец Иван Иванович"}, // A fleeting vowel needs a confirmed form.
  {fio:"Иванов А-Б Иванович"},
  {fio:"Иванов <Иван> Иванович"},
  {last_name:"Иванов",first_name:"",middle_name:"Иванович"},
])("requires manual input for ambiguous gender or source form: %j", source => {
  expect(russianTransferAccusative(source)).toBe("");
});

it("prefers a saved manual accusative, never transforms the dative, and leaves other fields intact", () => {
  const source={fio:"Кашкинбаева Гульжан Нурахметовна",document_forms_ru:{employee_full_name_accusative_ru:"Ручная проверенная форма",employee_full_name_dative_ru:"Другая форма"},document_forms_kk:{employee_full_name_dative_kk:"KK unchanged"}};
  const before=structuredClone(source);
  expect(russianTransferAccusative(source)).toBe("Ручная проверенная форма");
  expect(russianTransferAccusative({document_forms_ru:{employee_full_name_dative_ru:"Другая форма"}})).toBe("");
  expect(source).toEqual(before);
});
