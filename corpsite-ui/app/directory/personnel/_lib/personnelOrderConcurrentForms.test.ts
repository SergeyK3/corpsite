import {expect, it} from "vitest";
import {concurrentEmployeeDatives, refreshAutomaticForm} from "./personnelOrderConcurrentForms";

it("prefers explicit saved KK forms, including the nested employee contract", () => {
  expect(concurrentEmployeeDatives({fio:"Любая исходная запись",document_forms_kk:{employee_full_name_dative_kk:"Подтверждённая форма"}}).employee_full_name_dative_kk).toBe("Подтверждённая форма");
  expect(concurrentEmployeeDatives({name:{full_name_dative_kk:"Сохранённая форма"}}).employee_full_name_dative_kk).toBe("Сохранённая форма");
});
it("uses the existing unambiguous rule on structured source parts without translating them", () => {
  const source={first_name:"Альбина",middle_name:"Сериковна",last_name:"Маженова"};
  expect(concurrentEmployeeDatives(source).employee_full_name_dative_kk).toBe("Альбина Сериковна Маженоваға");
  expect(source.last_name).toBe("Маженова");
});
it.each([{fio:"Маженова Альбина Сериковна"},{first_name:"Альбина",last_name:"Серги"},{first_name:"А.",last_name:"Маженова"},{first_name:"Альбина",last_name:"Иванова-Петрова"},{first_name:"Albina",last_name:"Mazhenova"}])("does not guess KK from insufficient or ambiguous data %j", source => {
  expect(concurrentEmployeeDatives(source).employee_full_name_dative_kk).toBe("");
});
it("updates automatic values, preserves manual values and explicitly emptied fields", () => {
  expect(refreshAutomaticForm("старое", "старое", "новое", false)).toBe("новое");
  expect(refreshAutomaticForm("ручное", "старое", "новое", false)).toBe("ручное");
  expect(refreshAutomaticForm("", "старое", "новое", true)).toBe("");
  expect(refreshAutomaticForm("старое", "старое", "новое", true)).toBe("старое");
});
