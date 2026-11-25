import type {PersonnelOrderItem} from './personnelOrdersApi.client';
import type {OrgUnitSelectOption} from '@/lib/orgUnitsSelect';
import {russianReferenceCase} from './personnelOrderRussianWording';
import {departmentValues, type DepartmentDraft} from './personnelOrderDepartment';

export function concurrentDepartmentFromDraft(draft: DepartmentDraft): ConcurrentDepartmentSource | null {
  const value = departmentValues(draft);
  if (!value.name_ru.trim()) return null;
  return {org_unit_id:draft.unit?.unit_id ?? undefined,org_unit_ru:value.name_ru,
    org_unit_kk:value.genitive_kk,org_unit_genitive_ru:value.genitive_ru,
    description:'Подразделение заполнено из выбранного подразделения сотрудника. Для работы в другом подразделении выберите его отдельно.'};
}

const normalized = (value: unknown) => String(value || '').trim().replace(/\s+/g,' ').toLocaleLowerCase().replace(/ё/g,'е');
/** The additional-department genitive for the ordinary fractional-rate form only. */
export function concurrentDepartmentGenitive(value:string):string {
  return normalized(value)==='диспансер'?'диспансера':russianReferenceCase(value,'genitive');
}
export function departmentLooksLikePerson(value: unknown, names: readonly unknown[] = []): boolean {
  const text=normalized(value);
  if(!text)return false;
  if(names.some(name=>normalized(name)===text))return true;
  const words=text.split(' ');
  return words.length===3 && words.every(word=>/^[\p{Script=Cyrillic}-]+$/u.test(word))
    && !words.some(word=>/^(отдел|служб|центр|кабинет|лаборатор|управлен|бөлім|имени)/u.test(word))
    && words.some(word=>/(?:ович|евич|ильич|инич)(?:а|у|ем|е)?$|(?:овн|евн|ичн)(?:а|ы|е|у|ой)$/u.test(word));
}
export function concurrentDepartmentErrors(data: Record<string, unknown>, names: readonly unknown[] = []): string[] {
  return ([['org_unit_ru','Дополнительное подразделение (RU)'],['org_unit_kk','Дополнительное подразделение (KK)'],['org_unit_genitive_ru','Дополнительное подразделение в родительном падеже (RU)']] as const)
    .filter(([key])=>departmentLooksLikePerson(data[key],names))
    .map(([,label])=>`В поле «${label}» указано ФИО. Выберите подразделение или введите его название в нужной форме.`);
}
export type ConcurrentDepartmentSource = {
  org_unit_ru: string; org_unit_kk: string; org_unit_genitive_ru: string; org_unit_id?: number;
  description: string;
};
type Employee = {id?: string | number | null; fio?: string | null; has_current_assignment?: boolean;
  org_unit?: {unit_id?: number | null;name?: string | null;name_kk?: string | null} | null};

/** Only a preceding transfer for this employee may supply the default extra unit. */
export function resolveConcurrentDepartment(items: readonly PersonnelOrderItem[], employee: Employee | null,
  units: readonly OrgUnitSelectOption[], beforeItemNumber=Infinity): ConcurrentDepartmentSource | null {
  if(!employee?.id)return null;
  const transfers=items.filter(item=>item.item_status==='ACTIVE' && item.item_type_code==='TRANSFER'
    && String(item.employee_id)===String(employee.id) && item.item_number<beforeItemNumber);
  if(!transfers.length)return null;
  const destinations=transfers.map(item=>{
    const data=item.payload.transfer;
    return data && typeof data==='object' && !Array.isArray(data)?data as Record<string,unknown>:{};
  });
  // Different transfers are ambiguous. Do not silently choose a department.
  if(new Set(destinations.map(d=>JSON.stringify([d.org_unit_id || null,normalized(d.org_unit_ru),normalized(d.org_unit_kk)]))).size!==1)return null;
  const data=destinations[0];
  let ru=String(data.org_unit_ru || '').trim(),kk=String(data.org_unit_kk || '').trim();
  let description='Подразделение дополнительной работы заполнено из пункта перевода этого сотрудника. Для работы в другом подразделении выберите его отдельно.';
  if(!ru && !kk && !data.org_unit_id){
    if(employee.has_current_assignment!==true || !employee.org_unit?.unit_id)return null;
    const current=units.find(unit=>unit.unit_id===employee.org_unit?.unit_id && normalized(unit.name)===normalized(employee.org_unit?.name)
      && normalized(unit.name_kk)===normalized(employee.org_unit?.name_kk));
    if(!current)return null;
    ru=current.name;kk=current.name_kk || '';
    description='Подразделение дополнительной работы заполнено из подтверждённого текущего назначения сотрудника: в переводе новое подразделение не указано. Для другой дополнительной работы выберите подразделение отдельно.';
  }
  if(!ru || !kk || departmentLooksLikePerson(ru,[employee.fio]) || departmentLooksLikePerson(kk,[employee.fio]))return null;
  // An ID alone must not attach a translation belonging to another/manual title.
  const unit=units.find(unit=>(!data.org_unit_id || unit.unit_id===Number(data.org_unit_id))
    && normalized(unit.name)===normalized(ru) && normalized(unit.name_kk)===normalized(kk));
  return {org_unit_ru:ru,org_unit_kk:unit?.document_genitive_kk?.trim() || '',
    org_unit_genitive_ru:concurrentDepartmentGenitive(ru),org_unit_id:unit?.unit_id,description};
}
