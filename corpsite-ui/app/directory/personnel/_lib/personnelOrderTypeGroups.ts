import {
  PERSONNEL_ORDER_CREATE_TYPES,
  PERSONNEL_ORDER_TYPE_LABELS,
  personnelOrderTypeLabel,
} from "./personnelOrderLabels";
import type { PersonnelSectionLanguage } from "./personnelSectionLanguage";

export type PersonnelOrderCreateType = (typeof PERSONNEL_ORDER_CREATE_TYPES)[number];

export const PERSONNEL_ORDER_GROUPS = [
  { id: "annual", ru: "Трудовой отпуск", kk: "Еңбек демалысы" },
  { id: "parenthood", ru: "Беременность, роды и уход за ребёнком", kk: "Жүктілік, босану және бала күтімі" },
  { id: "unpaid", ru: "Отпуск без содержания", kk: "Жалақы сақталмайтын демалыс" },
  { id: "other_leave", ru: "Другие отпуска", kk: "Басқа демалыстар" },
  { id: "employment", ru: "Приём, увольнение, назначение, перевод", kk: "Жұмысқа қабылдау, еңбек шартын бұзу, тағайындау, ауыстыру" },
  { id: "concurrent_pay", ru: "Совмещение и доплаты", kk: "Қоса атқару және қосымша ақы" },
  { id: "record_changes", ru: "Учётные данные и изменения приказов", kk: "Есепке алу деректері және бұйрықтарға өзгерістер" },
] as const;

export type PersonnelOrderGroupId = (typeof PERSONNEL_ORDER_GROUPS)[number]["id"];

// Display grouping only. These are the existing creation codes, not new actions.
export const PERSONNEL_ORDER_TYPE_GROUP: Record<PersonnelOrderCreateType, PersonnelOrderGroupId> = {
  HIRE: "employment",
  TRANSFER: "employment",
  TERMINATION: "employment",
  CONCURRENT_DUTY_START: "concurrent_pay",
  CONCURRENT_DUTY_END: "concurrent_pay",
  RETURN_FROM_CHILDCARE_LEAVE: "parenthood",
  "LEAVE.ANNUAL.RECALL": "annual",
  "LEAVE.ANNUAL.GRANT": "annual",
  "LEAVE.UNPAID.GRANT": "unpaid",
  "LEAVE.CHILDCARE.GRANT": "parenthood",
  SUPPLEMENTARY_PAY: "concurrent_pay",
};

export function personnelOrderGroupTypes(group: PersonnelOrderGroupId): PersonnelOrderCreateType[] {
  return PERSONNEL_ORDER_CREATE_TYPES.filter(type => PERSONNEL_ORDER_TYPE_GROUP[type] === group);
}

function normalize(text: string): string {
  return text.toLocaleLowerCase().replace(/ё/g, "е").trim();
}

export function searchPersonnelOrderTypes(query: string): PersonnelOrderCreateType[] {
  const words = normalize(query).split(/\s+/).filter(Boolean);
  return PERSONNEL_ORDER_CREATE_TYPES.filter(type => {
    const names = normalize([
      personnelOrderTypeLabel(type, "ru"), personnelOrderTypeLabel(type, "kk"),
      PERSONNEL_ORDER_TYPE_LABELS[type],
    ].join(" "));
    return words.every(word => names.includes(word));
  });
}

export function personnelOrderGroupLabel(group: PersonnelOrderGroupId, language: PersonnelSectionLanguage): string {
  const labels = PERSONNEL_ORDER_GROUPS.find(item => item.id === group)!;
  return labels[language] || labels.ru;
}
