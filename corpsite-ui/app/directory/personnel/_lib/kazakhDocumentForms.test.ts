import { describe, expect, it } from "vitest";
import { calculateKazakhOrgUnitGenitive, calculateKazakhPersonForm, kazakhInflectWord } from "./kazakhDocumentForms";

describe("Kazakh document form proposals", () => {
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
