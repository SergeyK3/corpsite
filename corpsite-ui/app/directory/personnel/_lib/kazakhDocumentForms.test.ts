import { describe, expect, it } from "vitest";
import { calculateKazakhDocumentName, calculateKazakhOrgUnitGenitive, calculateKazakhPersonForm, kazakhInflectWord } from "./kazakhDocumentForms";

describe("Kazakh document form proposals", () => {
  it('recognizes the surname-first source and proposes a surname-last document name with matching cases',()=>{
    const source={fio:'Фидахметова Нургул Маметовна'};
    expect(calculateKazakhDocumentName(source)).toEqual({value:'Нургул Маметовна Фидахметова',needsReview:false});
    expect(calculateKazakhPersonForm(source,'dative').value).toBe('Нургул Маметовна Фидахметоваға');
    expect(calculateKazakhPersonForm(source,'genitive').value).toBe('Нургул Маметовна Фидахметованың');
    expect(source.fio).toBe('Фидахметова Нургул Маметовна');
    expect(calculateKazakhDocumentName({fio:'Нургул Маметовна Фидахметова'}).value).toBe('Нургул Маметовна Фидахметова');
  });
  it('prefers the card name parts and leaves ambiguous strings for manual review',()=>{
    expect(calculateKazakhDocumentName({fio:'Неоднозначная Строка',first_name:'Нургул',middle_name:'Маметовна',last_name:'Фидахметова'}).value).toBe('Нургул Маметовна Фидахметова');
    expect(calculateKazakhDocumentName({fio:'Айдар Нургул Төлеген'})).toEqual({value:'',needsReview:true});
    expect(calculateKazakhPersonForm({fio:'Айдар Нургул Төлеген'},'dative')).toEqual({value:'',needsReview:true});
  });
  it("keeps an already saved genitive without declining it again",()=>{
    expect(calculateKazakhOrgUnitGenitive('терапия бөлімшесінің').value).toBe('терапия бөлімшесінің');
  });
  it('keeps the written final а in feminine ева surnames with back case endings',()=>{
    expect(calculateKazakhPersonForm({last_name:'Жаркенева',first_name:'Малика',middle_name:'Бауржановна'},'genitive').value).toBe('Малика Бауржановна Жаркеневаның');
    expect(calculateKazakhPersonForm({last_name:'Жаркенева',first_name:'Малика',middle_name:'Бауржановна'},'dative').value).toBe('Малика Бауржановна Жаркеневаға');
  });
  it("forms the ablative after the surname and flags ambiguous spelling", () => {
    expect(calculateKazakhPersonForm({first_name:"Алибек",middle_name:"Рапхатович",last_name:"Турымов"},"ablative")).toEqual({value:"Алибек Рапхатович Турымовтан",needsReview:false});
    expect(kazakhInflectWord("Серги", "ablative").needsReview).toBe(true);
  });
  it("forms the requested employee and unit proposals without changing their source spelling", () => {
    const employee = { first_name: "Альбина", middle_name: "Сериковна", last_name: "Маженова" };
    expect(calculateKazakhPersonForm(employee, "dative").value).toBe("Альбина Сериковна Маженоваға");
    expect(calculateKazakhPersonForm(employee, "genitive").value).toBe("Альбина Сериковна Маженованың");
    expect(calculateKazakhOrgUnitGenitive("Диспансер бөлімшесі").value).toBe("Диспансер бөлімшесінің");
  });

  it("matches the two employee-name blocks in the supplied unpaid-leave order sample", () => {
    expect(calculateKazakhPersonForm({ first_name: "Ассель", middle_name: "Адиловна", last_name: "Ильясова" }, "dative").value).toBe("Ассель Адиловна Ильясоваға");
    expect(calculateKazakhPersonForm({ first_name: "Ассель", middle_name: "Адиловна", last_name: "Ильясова" }, "genitive").value).toBe("Ассель Адиловна Ильясованың");
    expect(calculateKazakhOrgUnitGenitive("Сәулелік диагностика бөлімшесі").value).toBe("Сәулелік диагностика бөлімшесінің");
  });

  it("uses stem harmony for -ов/-ев, thin forms for -ин, and possession for ұлы/қызы", () => {
    expect(kazakhInflectWord("Омаров", "genitive").value).toBe("Омаровтың");
    expect(kazakhInflectWord("Әуезов", "dative").value).toBe("Әуезовке");
    expect(kazakhInflectWord("Оразалин", "dative").value).toBe("Оразалинге");
    expect(kazakhInflectWord("Сәрсенбайқызы", "dative").value).toBe("Сәрсенбайқызына");
  });

  it("marks hyphen, и/у and soft-sign endings for manual review", () => {
    expect(kazakhInflectWord("Иванова-Петрова", "dative").needsReview).toBe(true);
    expect(kazakhInflectWord("Серги", "dative").needsReview).toBe(true);
    expect(kazakhInflectWord("Фестиваль", "genitive").needsReview).toBe(true);
  });
});
