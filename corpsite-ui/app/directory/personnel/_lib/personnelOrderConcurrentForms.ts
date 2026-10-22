import {savedKazakhEmployeeNameForm} from "./personnelOrderDocumentForms";
import {calculateKazakhPersonForm} from "./kazakhDocumentForms";
import {russianEmployeeDativeForOrder} from "./personnelOrderRussianWording";

/** Use saved forms first. Do not infer KK name parts from an RU display FIO. */
export function concurrentEmployeeDatives(employee: unknown) {
  const record = employee && typeof employee === "object" ? employee as Record<string, unknown> : {};
  let kk = savedKazakhEmployeeNameForm(record, "dative");
  if (!kk && [record.first_name, record.last_name].every(part => typeof part === "string" && /^\p{Script=Cyrillic}{2,}$/u.test(part.trim()))
      && (!record.middle_name || typeof record.middle_name === "string" && /^\p{Script=Cyrillic}{2,}$/u.test(record.middle_name.trim()))) {
    const proposal = calculateKazakhPersonForm(record, "dative");
    if (!proposal.needsReview) kk = proposal.value;
  }
  return {employee_full_name_dative_ru: russianEmployeeDativeForOrder(record), employee_full_name_dative_kk: kk};
}

/** Existing nonempty overrides and explicit manual edits (even empty) win. */
export function refreshAutomaticForm(current: string, previous: string | undefined, next: string, manual: boolean) {
  return !manual && (!current || current === previous) ? next : current;
}
