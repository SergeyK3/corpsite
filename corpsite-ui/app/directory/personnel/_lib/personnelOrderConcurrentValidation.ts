import type {ItemPayloadDraft} from './personnelOrderPayload';
import {concurrentDepartmentErrors} from './personnelOrderConcurrentDepartment';
import {blankReplacement, replacementBlockers} from '../_components/PersonnelOrderReplacementFields';

/** Recomputed from the current draft, including after a failed save. */
export function concurrentDraftBlockers(draft: ItemPayloadDraft, effectiveDate: string): string[] {
  if (!draft.concurrent) return [];
  const labels: Record<string,string> = {
    position_ru:'Дополнительная должность (RU)', position_kk:'Дополнительная должность (KK)',
    org_unit_ru:'Дополнительное подразделение (RU)', org_unit_kk:'Дополнительное подразделение (KK)',
    position_genitive_ru:'Дополнительная должность в родительном падеже (RU)',
    org_unit_genitive_ru:'Дополнительное подразделение в родительном падеже (RU)',
    rate:'Дополнительная ставка',basis_ru:'Основание совмещения (RU)',basis_kk:'Основание совмещения (KK)',
  };
  if (draft.replacement) labels.total_rate = 'Общая ставка';
  const data = draft.concurrent;
  const missing = Object.entries(labels).filter(([key]) => !String(data[key as keyof typeof data] ?? '').trim())
    .map(([,label]) => `Заполните поле «${label}».`);
  if (!effectiveDate) missing.push('Заполните дату действия.');
  if (!draft.employee_full_name_dative_ru?.trim()) missing.push('Заполните ФИО в дательном падеже (RU).');
  if (!draft.employee_full_name_dative_kk?.trim()) missing.push('Заполните ФИО в дательном падеже (KK).');
  const rate=Number(String(data.rate).replace(',','.')), total=Number(String(data.total_rate).replace(',','.'));
  if (data.rate && (!Number.isFinite(rate) || rate<=0)) missing.push('Дополнительная ставка должна быть положительной.');
  if (String(data.total_rate ?? '').trim() && (!Number.isFinite(total) || total<=rate)) missing.push('Общая ставка должна быть больше дополнительной.');
  missing.push(...concurrentDepartmentErrors(data));
  if (draft.replacement) missing.push(...replacementBlockers({...blankReplacement(),...draft.replacement},'RATE',effectiveDate));
  return missing;
}
