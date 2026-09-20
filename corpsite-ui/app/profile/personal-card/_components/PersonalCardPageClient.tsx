"use client";

import { useCallback, useEffect, useState } from "react";

import PositionCabinetSectionShell from "@/components/PositionCabinetSectionShell";
import { formatPersonnelDayDateForDisplay } from "@/lib/personnelDayDate";
import { getMyOperationalAssignment, getMyPersonalCard, type SelfOperationalAssignment, type SelfPersonalCard } from "../_lib/selfPersonalCardApi.client";
import { displayEmploymentRate, displayOperationalStatus } from "../_lib/operationalAssignmentDisplay";
import { downloadMyPersonalCardPdf } from "../_lib/selfPersonCardPdfOpen.client";
import { ContactsEditor, EducationEditor, EmploymentEditor, LanguagesEditor, type EmploymentRecordForEdit } from "./SelfEditors";

type TabId = "overview" | "contacts" | "education" | "employment" | "languages" | "other";
type LoadState = { kind: "loading" } | { kind: "ready"; card: SelfPersonalCard; operationalAssignment: SelfOperationalAssignment } | { kind: "person-not-linked" } | { kind: "unavailable" };

const TABS: { id: TabId; label: string }[] = [
  { id: "overview", label: "Обзор" }, { id: "contacts", label: "Контакты" }, { id: "education", label: "Образование" }, { id: "employment", label: "Трудовая биография" }, { id: "languages", label: "Иностранные языки" }, { id: "other", label: "Другие сведения" },
];
const SECTION_TITLES: Record<string, string> = {
  "PPR-TRAINING": "Обучение и повышение квалификации",
  "PPR-FAMILY": "Родственники",
  "PPR-EMPLOYMENT-BIOGRAPHY": "Трудовая биография",
  "PPR-MILITARY": "Воинский учёт",
};
const emptyText = "Сведения пока не заполнены.";

function recordText(record: Record<string, unknown>): string {
  const values = [record.institution_name, record.title, record.full_name, record.employer_name, record.record_kind]
    .filter((value): value is string => typeof value === "string" && value.trim().length > 0);
  return values[0] ?? "Запись добавлена";
}

const educationKindLabels: Record<string, string> = { basic: "Основное", internship: "Интернатура", residency: "Резидентура", masters: "Магистратура", phd: "Докторантура", other: "Другое" };
const institutionTypeLabels: Record<string, string> = { university: "ВУЗ", college: "Колледж", other: "Другое", unknown: "Не указано" };

function textValue(value: unknown): string {
  return typeof value === "string" && value.trim() ? value : "—";
}

function dateValue(value: unknown): string {
  return typeof value === "string" && value.trim() ? formatPersonnelDayDateForDisplay(value, "document") : "—";
}

function RecordFields({ fields }: { fields: Array<[string, string]> }) {
  return <dl className="grid gap-x-6 gap-y-3 sm:grid-cols-2">{fields.map(([label, value]) => <div key={label}><dt className="text-sm text-zinc-500 dark:text-zinc-400">{label}</dt><dd className="mt-1 break-words text-base text-zinc-900 dark:text-zinc-100">{value}</dd></div>)}</dl>;
}

function EducationRecords({ card }: { card: SelfPersonalCard }) {
  const records = card.sections["PPR-EDUCATION"]?.active ?? [];
  if (!records.length) return <p className="text-base text-zinc-600 dark:text-zinc-400">{emptyText}</p>;
  return <div className="space-y-4" data-testid="self-education-records">{records.map((raw, index) => {
    const record = raw as Record<string, unknown>;
    const kind = textValue(record.education_kind);
    const institutionType = textValue(record.institution_type);
    return <article key={`education-${index}`} className="rounded-lg border border-zinc-200 p-4 dark:border-zinc-800"><RecordFields fields={[
      ["Вид образования", educationKindLabels[kind] ?? kind], ["Тип учреждения", institutionTypeLabels[institutionType] ?? institutionType],
      ["Учебное заведение", textValue(record.institution_name)], ["Специальность", textValue(record.specialty)],
      ["Квалификация", textValue(record.qualification)], ["Дата начала", dateValue(record.started_at)],
      ["Дата окончания", dateValue(record.completed_at)], ["Номер диплома", textValue(record.diploma_number)],
      ["Дата документа", dateValue(record.document_date)],
    ]} /></article>;
  })}</div>;
}

function EmploymentRecords({ card, onEdit }: { card: SelfPersonalCard; onEdit: (record: EmploymentRecordForEdit) => void }) {
  const records = card.sections["PPR-EMPLOYMENT-BIOGRAPHY"]?.active ?? [];
  if (!records.length) return <p className="mt-3 text-base text-zinc-600 dark:text-zinc-400">{emptyText}</p>;
  return <div className="mt-3 space-y-4" data-testid="self-employment-records">{records.map((raw, index) => {
    const record = raw as Record<string, unknown>;
    const editable = record.record_id != null && record.updated_at != null ? {
      record_id: Number(record.record_id), updated_at: String(record.updated_at), record_kind: textValue(record.record_kind),
      employer_name: typeof record.employer_name === "string" ? record.employer_name : null,
      position_title: typeof record.position_title === "string" ? record.position_title : null,
      started_at: typeof record.started_at === "string" ? record.started_at : null,
      ended_at: typeof record.ended_at === "string" ? record.ended_at : null,
      termination_reason: typeof record.termination_reason === "string" ? record.termination_reason : null,
    } : null;
    return <article key={`employment-${index}`} className="rounded-lg border border-zinc-200 p-4 dark:border-zinc-800" data-testid={`self-employment-record-${record.record_id ?? index}`}><div className="mb-3 flex items-center justify-end">{editable && <button type="button" className="rounded-md border border-blue-600 px-3 py-1.5 text-sm font-medium text-blue-700 hover:bg-blue-50" onClick={() => onEdit(editable)}>Редактировать</button>}</div><RecordFields fields={[
      ["Организация", textValue(record.employer_name)], ["Должность", textValue(record.position_title)],
      ["Тип занятости", textValue(record.employment_type)],
      ["Дата начала", dateValue(record.started_at)], ["Дата окончания", dateValue(record.ended_at)],
      ["Причина увольнения", textValue(record.termination_reason)],
    ]} /></article>;
  })}</div>;
}

function Card({ title, children, testId }: { title?: string; children: React.ReactNode; testId?: string }) {
  return <section data-testid={testId} className="rounded-xl border border-zinc-200 bg-white p-4 text-base shadow-sm dark:border-zinc-800 dark:bg-zinc-950 sm:p-5">{title && <h2 className="text-lg font-semibold">{title}</h2>}{children}</section>;
}

function Records({ sectionCode, card }: { sectionCode: string; card: SelfPersonalCard }) {
  const section = card.sections[sectionCode];
  if (!section?.active.length) return <p className="mt-3 text-base text-zinc-600 dark:text-zinc-400">{emptyText}</p>;
  return <ul className="mt-3 list-disc space-y-2 pl-5 text-base">{section.active.map((record, index) => <li key={`${sectionCode}-${index}`}>{recordText(record as Record<string, unknown>)}</li>)}</ul>;
}

function Overview({ card, operationalAssignment }: { card: SelfPersonalCard; operationalAssignment: SelfOperationalAssignment }) {
  const [pdfError, setPdfError] = useState<string | null>(null);
  async function downloadPdf() { setPdfError(null); const result = await downloadMyPersonalCardPdf(); if (!result.ok) setPdfError(result.error); }
  return <div className="space-y-4"><Card testId="self-overview"><div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between"><div><h2 className="text-xl font-semibold">{card.general.full_name}</h2><dl className="mt-4 grid gap-3 sm:grid-cols-2"><div><dt className="text-sm text-zinc-500">ИИН</dt><dd className="mt-1">{operationalAssignment.iin ?? card.general.iin ?? "Не указан"}</dd></div><div><dt className="text-sm text-zinc-500">Дата рождения</dt><dd className="mt-1">{card.general.birth_date ?? "Не указана"}</dd></div></dl></div><button type="button" onClick={() => void downloadPdf()} className="w-full rounded-md border border-zinc-300 px-4 py-2 text-sm font-medium hover:bg-zinc-100 dark:border-zinc-700 dark:hover:bg-zinc-900 sm:w-auto" data-testid="self-personal-card-download-pdf">Скачать PDF</button></div>{pdfError && <p className="mt-4 rounded-md border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-800 dark:border-red-800 dark:bg-red-950/40 dark:text-red-200" role="alert">{pdfError}</p>}</Card><Card title="Текущее место работы" testId="self-operational-assignment"><dl className="mt-3 grid gap-3 sm:grid-cols-2"><div><dt className="text-sm text-zinc-500">Подразделение</dt><dd className="mt-1">{operationalAssignment.org_unit_name ?? "Не указано"}</dd></div><div><dt className="text-sm text-zinc-500">Должность</dt><dd className="mt-1">{operationalAssignment.position_name ?? "Не указана"}</dd></div><div><dt className="text-sm text-zinc-500">Статус</dt><dd className="mt-1">{displayOperationalStatus(operationalAssignment.operational_status) ?? "Не указан"}</dd></div><div><dt className="text-sm text-zinc-500">Ставка</dt><dd className="mt-1">{displayEmploymentRate(operationalAssignment.employment_rate) ?? "Не указана"}</dd></div></dl></Card></div>;
}

function PersonalCardTabs({ card, operationalAssignment, onSaved }: { card: SelfPersonalCard; operationalAssignment: SelfOperationalAssignment; onSaved: () => Promise<void> }) {
  const [activeTab, setActiveTab] = useState<TabId>("overview");
  const [employmentToEdit, setEmploymentToEdit] = useState<EmploymentRecordForEdit | null>(null);
  const otherSections = Object.keys(card.sections).filter((code) => code !== "PPR-EDUCATION" && code !== "PPR-EMPLOYMENT-BIOGRAPHY");
  return <div className="space-y-4" data-testid="self-personal-card-ready"><div role="tablist" aria-label="Разделы личной карточки" className="-mx-1 flex gap-2 overflow-x-auto px-1 pb-1">{TABS.map((tab) => <button key={tab.id} type="button" role="tab" aria-selected={activeTab === tab.id} aria-controls={`self-card-panel-${tab.id}`} onClick={() => setActiveTab(tab.id)} className={`shrink-0 rounded-md px-3 py-2 text-sm font-medium transition ${activeTab === tab.id ? "bg-blue-600 text-white" : "border border-zinc-300 bg-white text-zinc-800 hover:bg-zinc-100 dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-200 dark:hover:bg-zinc-900"}`}>{tab.label}</button>)}</div><div role="tabpanel" id={`self-card-panel-${activeTab}`} className="min-w-0">{activeTab === "overview" && <Overview card={card} operationalAssignment={operationalAssignment} />}{activeTab === "contacts" && <div className="space-y-4"><Card title="Контакты"><p className="mt-2 text-base text-zinc-600 dark:text-zinc-400">Укажите актуальные способы связи и адреса.</p></Card><ContactsEditor onSaved={onSaved} /></div>}{activeTab === "education" && <div className="space-y-4"><section className="rounded-xl border border-zinc-200 bg-white p-4 text-base shadow-sm dark:border-zinc-800 dark:bg-zinc-950 sm:p-5"><EducationRecords card={card} /></section><EducationEditor onSaved={onSaved} /></div>}{activeTab === "employment" && <div className="space-y-4"><Card title="Трудовая биография"><EmploymentRecords card={card} onEdit={setEmploymentToEdit} /></Card><EmploymentEditor editRecord={employmentToEdit} onEditClosed={() => setEmploymentToEdit(null)} onSaved={async () => { await onSaved(); setEmploymentToEdit(null); }} /></div>}{activeTab === "languages" && <div className="space-y-4"><Card title="Иностранные языки"><p className="mt-3 text-base text-zinc-700 dark:text-zinc-300">{card.additional.foreign_languages.length ? card.additional.foreign_languages.map((item) => `${item.language} — ${item.proficiency}`).join(", ") : emptyText}</p></Card><LanguagesEditor onSaved={onSaved} /></div>}{activeTab === "other" && <div className="grid gap-4">{otherSections.length ? otherSections.map((code) => <Card key={code} title={SECTION_TITLES[code] ?? code}><Records sectionCode={code} card={card} /></Card>) : <Card title="Другие сведения"><p className="text-base text-zinc-600 dark:text-zinc-400">{emptyText}</p></Card>}</div>}</div></div>;
}

export default function PersonalCardPageClient() {
  const [state, setState] = useState<LoadState>({ kind: "loading" });
  const reload = useCallback(async (signal?: AbortSignal) => {
    const response = await getMyPersonalCard({ signal });
    if (response.status !== "READY") { setState(response.status === "PERSON_NOT_LINKED" ? { kind: "person-not-linked" } : { kind: "unavailable" }); return; }
    const assignment = await getMyOperationalAssignment({ signal });
    if (assignment.status !== "READY") { setState({ kind: "unavailable" }); return; }
    setState({ kind: "ready", card: response.card, operationalAssignment: assignment.operational_assignment });
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    void reload(controller.signal).catch((error: unknown) => { if (!(error instanceof DOMException && error.name === "AbortError")) setState({ kind: "unavailable" }); });
    return () => controller.abort();
  }, []);
  return <PositionCabinetSectionShell title="Личная карточка">{state.kind === "loading" && <p data-testid="self-personal-card-loading" className="text-base">Загрузка личной карточки…</p>}{state.kind === "ready" && <PersonalCardTabs card={state.card} operationalAssignment={state.operationalAssignment} onSaved={() => reload()} />}{state.kind === "person-not-linked" && <div className="rounded-xl border border-zinc-200 p-4 text-base dark:border-zinc-800" data-testid="self-personal-card-person-not-linked"><p className="font-medium">Личная карточка ещё не создана.</p><p className="mt-2 text-zinc-600 dark:text-zinc-400">Обратитесь в отдел кадров, чтобы создать и связать вашу личную карточку.</p></div>}{state.kind === "unavailable" && <div className="rounded-xl border border-zinc-200 p-4 text-base dark:border-zinc-800" data-testid="self-personal-card-unavailable">Карточка пока недоступна. Обратитесь в отдел кадров.</div>}</PositionCabinetSectionShell>;
}
