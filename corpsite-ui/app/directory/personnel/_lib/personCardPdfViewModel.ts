import { PERSONAL_CARD_PDF_SECTIONS, type PersonalCardSectionKey } from "@/app/intake/_lib/personalCardSections";
import type {
  PprCompositeReadResponse,
  PprEducationRecordResponse,
  PprExternalEmploymentRecordResponse,
  PprMilitaryRecordResponse,
  PprRelativeRecordResponse,
  PprTrainingRecordResponse,
} from "./pprQueryTypes";

export type PersonCardPdfSection = {
  key: PersonalCardSectionKey;
  title: string;
  headers: string[];
  rows: string[][];
  emptyMessage?: string;
};

export type PersonCardPdfViewModel = {
  personId: number;
  fullName: string;
  iin: string | null;
  birthDate: string | null;
  photoDataUrl: string | null;
  sections: PersonCardPdfSection[];
};

export type PersonCardContacts = {
  mobile_phone: string | null;
  email: string | null;
  registration_address: string | null;
  residence_address: string | null;
};

/** The current operational assignment is deliberately not a PPR field. */
export type PersonCardCurrentAssignment = {
  departmentGroupName: string;
  orgUnitName: string;
  positionName: string;
  statusLabel: string;
  rate: string;
};

const sectionRecords = <T>(ppr: PprCompositeReadResponse, code: string): T[] =>
  (ppr.sections[code]?.active ?? []) as T[];
const text = (value: unknown): string => String(value ?? "").trim();
const period = (from: unknown, to: unknown): string => [text(from), text(to)].filter(Boolean).join(" — ");

export function buildPersonCardPdfViewModel(input: {
  personId: number;
  ppr: PprCompositeReadResponse;
  contacts: PersonCardContacts | null;
  photoDataUrl: string | null;
  currentAssignment: PersonCardCurrentAssignment | null;
}): PersonCardPdfViewModel {
  const { ppr } = input;
  const education = sectionRecords<PprEducationRecordResponse>(ppr, "PPR-EDUCATION");
  const training = sectionRecords<PprTrainingRecordResponse>(ppr, "PPR-TRAINING");
  const employment = sectionRecords<PprExternalEmploymentRecordResponse>(ppr, "PPR-EMPLOYMENT-BIOGRAPHY");
  const military = sectionRecords<PprMilitaryRecordResponse>(ppr, "PPR-MILITARY");
  const relatives = sectionRecords<PprRelativeRecordResponse>(ppr, "PPR-FAMILY");
  const contacts = input.contacts;
  const rows: Partial<Record<PersonalCardSectionKey, Omit<PersonCardPdfSection, "key" | "title">>> = {
    general: {
      headers: ["Поле", "Значение"],
      rows: [
        ["Ф.И.О.", ppr.general.full_name], ["ИИН", ppr.general.iin ?? ppr.identity.iin ?? ""],
        ["Дата рождения", ppr.general.birth_date ?? ""], ["Телефон", contacts?.mobile_phone ?? ""],
        ["Email", contacts?.email ?? ""], ["Адрес регистрации", contacts?.registration_address ?? ""],
        ["Адрес проживания", contacts?.residence_address ?? ""],
      ],
    },
    education: { headers: ["Вид", "Учебное заведение", "Период", "Специальность / квалификация", "Документ"], rows: education.map((item) => [text(item.education_kind), text(item.institution_name), period(item.started_at, item.completed_at), [text(item.specialty), text(item.qualification)].filter(Boolean).join(" / "), [text(item.diploma_number), text(item.document_date)].filter(Boolean).join(" · ")]) },
    training: { headers: ["Вид", "Наименование", "Организация", "Период", "Документ / часы"], rows: training.map((item) => [text(item.training_kind), text(item.title), text(item.organization_name), period(item.started_at, item.completed_at), [text(item.document_type), text(item.certificate_number), text(item.hours)].filter(Boolean).join(" · ")]) },
    qualification_category: { headers: ["Специальность", "Категория", "Дата"], rows: (ppr.additional.qualification_categories ?? []).map((item) => [text(item.specialty), text(item.category), text(item.assigned_at)]) },
    employment_biography: { headers: ["Организация", "Подразделение", "Должность", "Период", "Примечание"], rows: employment.map((item) => [text(item.employer_name), text(item.department_name), text(item.position_title), period(item.started_at, item.ended_at), text(item.notes)]) },
    current_organization: input.currentAssignment
      ? {
          headers: ["Группа отделений", "Подразделение", "Должность", "Статус", "Ставка"],
          rows: [[
            input.currentAssignment.departmentGroupName,
            input.currentAssignment.orgUnitName,
            input.currentAssignment.positionName,
            input.currentAssignment.statusLabel,
            input.currentAssignment.rate,
          ]],
        }
      : {
          headers: [],
          rows: [],
          emptyMessage: "Сведения о работе в текущей организации пока не сформированы",
        },
    military: { headers: ["Статус", "Категория", "Звание", "Состав", "Военкомат"], rows: military.map((item) => [text(item.registration_status ?? item.obligation_status), text(item.registration_category), text(item.military_rank), text(item.personnel_composition), text(item.commissariat_name)]) },
    relatives: { headers: ["Степень родства", "Ф.И.О.", "Дата рождения", "Место работы", "Адрес"], rows: relatives.map((item) => [text(item.relationship_label ?? item.relationship_type), text(item.full_name), text(item.birth_date), text(item.organization_name), text(item.residence_address)]) },
    foreign_languages: { headers: ["Язык", "Уровень владения"], rows: ppr.additional.foreign_languages.map((item) => [text(item.language), text(item.proficiency)]) },
    note: { headers: ["Примечание"], rows: ppr.additional.source_note_hint ? [[text(ppr.additional.source_note_hint)]] : [] },
    additional: { headers: ["Раздел", "Сведения"], rows: [
      ...ppr.additional.awards.map((item) => ["Награда", [text(item.name), text(item.issued_by), text(item.awarded_at)].filter(Boolean).join(" · ")]),
      ...ppr.additional.academic_degrees.map((item) => ["Учёная степень", [text(item.label ?? item.degree ?? item.degree_other), text(item.field_of_science)].filter(Boolean).join(" · ")]),
      ...ppr.additional.academic_titles.map((item) => ["Учёное звание", [text(item.label ?? item.academic_title ?? item.academic_title_other), text(item.field_of_science)].filter(Boolean).join(" · ")]),
    ] },
  };
  return {
    personId: input.personId,
    fullName: ppr.general.full_name,
    iin: ppr.general.iin ?? ppr.identity.iin,
    birthDate: ppr.general.birth_date,
    photoDataUrl: input.photoDataUrl,
    sections: PERSONAL_CARD_PDF_SECTIONS.map((section) => ({ key: section.key, title: section.title, ...(rows[section.key] ?? { headers: [], rows: [] }) })),
  };
}
