import type {EmployeeDTO} from "@/app/directory/employees/_lib/types";
import {calculateKazakhPersonForm, firstNonEmpty} from "./kazakhDocumentForms";
import {russianEmployeeGenitiveForOrder, savedRussianEmployeeNameForm} from "./personnelOrderRussianWording";
import {resolvePersonnelOrderDocumentForms, savedKazakhEmployeeNameForm} from "./personnelOrderDocumentForms";

export function recallBasis(locale: "ru" | "kk", genitive: string): string {
  const name=genitive.trim();
  return name ? locale === "ru" ? `Докладная записка и личное согласие ${name}` : `Баяндау хат және ${name} жеке келісімі` : "";
}

export function recallEmployeePrefill(employee: EmployeeDTO) {
  const current=employee.has_current_assignment !== false;
  const forms=resolvePersonnelOrderDocumentForms(current ? employee.position : null, employee);
  const storedRu=savedRussianEmployeeNameForm(employee,"genitive");
  const storedKk=savedKazakhEmployeeNameForm(employee,"genitive");
  const calculatedKk=calculateKazakhPersonForm(employee,"genitive");
  const surname=firstNonEmpty(employee.last_name,employee.fio?.trim().split(/\s+/)[0]);
  const hasName=Boolean(employee.first_name?.trim() || (employee.fio?.trim().split(/\s+/).length || 0)>1);
  const genitiveRu=storedRu || russianEmployeeGenitiveForOrder(employee);
  // Uncertain suggestions require explicit manual input. Never fill the
  // nominative FIO in place of the missing case form.
  const genitiveKk=storedKk || (hasName && /^[\p{L}]+$/u.test(surname) && !calculatedKk.needsReview ? calculatedKk.value : "");
  return {
    fullName: employee.fio || "",
    positionRu: current ? firstNonEmpty(forms.position_document_nominative_ru,employee.position?.job_nameru,employee.position?.name) : "",
    positionKk: current ? firstNonEmpty(employee.position?.job_namekk,employee.position?.name_kk) : "",
    unitRu: current ? employee.org_unit?.name || "" : "",
    unitKk: current ? employee.org_unit?.name_kk || "" : "",
    genitiveRu,genitiveKk,
    suggestedRu: !storedRu && Boolean(genitiveRu),suggestedKk: !storedKk && Boolean(genitiveKk),
    basisRu:recallBasis("ru",genitiveRu),basisKk:recallBasis("kk",genitiveKk),
  };
}
