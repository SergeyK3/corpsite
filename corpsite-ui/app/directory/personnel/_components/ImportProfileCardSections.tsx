"use client";

import * as React from "react";

import type { ImportProfile } from "../_lib/importApi.client";
import {
  CATEGORY_OPTIONS,
  categoryDisplayLabel,
  emptyAwardRow,
  emptyCategoryRow,
  emptyCertificateRow,
  emptyDegreeRow,
  emptyEducationRow,
  emptyTrainingRow,
  buildDegreesState,
  calcExperienceFromEducation,
  calcRecordValidityNote,
  RECORD_VALIDITY_EXPIRED_NOTE,
  EXPERIENCE_CALC_NOTE,
  extractYearFromText,
  formatDocumentDateForDisplay,
  getDegreeRecords,
  getProfessionalEducationRecords,
  splitCertificateRow,
  splitDegreeRow,
  splitEducationRow,
  splitTrainingRow,
  stripYearFromText,
} from "../_lib/importProfileEditor";
import PersonnelDayDateField from "@/lib/PersonnelDayDateField";

const SEX_LABELS: Record<string, string> = {
  M: "Мужской",
  F: "Женский",
};

const inputClass =
  "w-full rounded border border-zinc-300 px-2 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-950";

const yearOnlyDateClass = "text-red-600 dark:text-red-400";

function DocumentDateText({ value }: { value: string }) {
  const formatted = formatDocumentDateForDisplay(value);
  if (!formatted) return <>—</>;
  return (
    <span className={formatted.includes("(уточните дату)") ? yearOnlyDateClass : undefined}>{formatted}</span>
  );
}

function LabeledDocumentDateField({
  label,
  value,
  onChange,
  testId,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  testId?: string;
}) {
  return (
    <label className="block text-sm">
      {label ? <span className="mb-1 block text-xs text-zinc-500">{label}</span> : null}
      <DocumentDateField value={value} onChange={onChange} testId={testId} />
    </label>
  );
}

function DocumentDateField({
  value,
  onChange,
  testId,
}: {
  value: string;
  onChange: (v: string) => void;
  testId?: string;
}) {
  return (
    <PersonnelDayDateField
      value={value}
      onChange={onChange}
      testId={testId}
      className="block text-sm"
      inputClassName={inputClass}
    />
  );
}

function RecordValidityNote({ issuedAt }: { issuedAt: string }) {
  const note = calcRecordValidityNote(issuedAt);
  if (!note) return <>—</>;
  const expired = note === RECORD_VALIDITY_EXPIRED_NOTE;
  return (
    <span className={`text-xs ${expired ? "text-red-600 dark:text-red-400" : "text-zinc-600 dark:text-zinc-400"}`}>
      {note}
    </span>
  );
}

function Field({
  label,
  value,
  onChange,
  onBlur,
  onPaste,
  multiline = false,
  readOnly = false,
  yearOnlyDate = false,
}: {
  label: string;
  value: string;
  onChange?: (v: string) => void;
  onBlur?: () => void;
  onPaste?: (e: React.ClipboardEvent<HTMLInputElement | HTMLTextAreaElement>) => void;
  multiline?: boolean;
  readOnly?: boolean;
  yearOnlyDate?: boolean;
}) {
  const valueClass = yearOnlyDate ? yearOnlyDateClass : undefined;
  if (readOnly) {
    return (
      <div className="block text-sm">
        {label ? <span className="mb-1 block text-xs text-zinc-500">{label}</span> : null}
        <div className="rounded border border-zinc-200 bg-zinc-50 px-2 py-1.5 text-sm dark:border-zinc-800 dark:bg-zinc-900">
          {value ? <span className={valueClass}>{value}</span> : "—"}
        </div>
      </div>
    );
  }
  const fieldClass = yearOnlyDate ? `${inputClass} ${yearOnlyDateClass}` : inputClass;
  return (
    <label className="block text-sm">
      {label ? <span className="mb-1 block text-xs text-zinc-500">{label}</span> : null}
      {multiline ? (
        <textarea
          className={fieldClass}
          rows={3}
          value={value}
          onChange={(e) => onChange?.(e.target.value)}
          onBlur={onBlur}
          onPaste={onPaste}
        />
      ) : (
        <input
          className={fieldClass}
          value={value}
          onChange={(e) => onChange?.(e.target.value)}
          onBlur={onBlur}
          onPaste={onPaste}
        />
      )}
    </label>
  );
}

type Props = {
  profile: ImportProfile;
  departmentCanonical?: string;
  mode?: "view" | "edit";
  basicEditable?: boolean;
  showReviewStatus?: boolean;
  reviewStatus?: string;
  onReviewStatusChange?: (value: string) => void;
  /** When editing portfolio with read-only basic block, visually split snapshot vs editable sections. */
  showEditModeSnapshotSplit?: boolean;
  onProfileChange: (profile: ImportProfile) => void;
};

export default function ImportProfileCardSections({
  profile,
  departmentCanonical,
  mode = "view",
  basicEditable = false,
  showReviewStatus = false,
  reviewStatus = "pending",
  onReviewStatusChange,
  showEditModeSnapshotSplit = false,
  onProfileChange,
}: Props) {
  const basic = profile.basic ?? {
    full_name: "",
    iin: "",
    birth_date: "",
    sex: "",
    position_raw: "",
    department_source: "",
    experience_raw: "",
    employment_rate: null,
    qualification_raw: "",
    nationality: "",
    phone_raw: "",
  };
  const educationRecords = getProfessionalEducationRecords(profile);
  const trainingRecords = profile.training_records ?? [];
  const categoryRecords = profile.category_records ?? [];
  const certificateRecords = profile.certificate_records ?? [];
  const awardRecords = profile.award_records ?? [];
  const degrees = profile.degrees ?? {
    candidate_medical_sciences: false,
    doctor_medical_sciences: false,
    raw_text: "",
    records: [],
  };
  const degreeRecords = getDegreeRecords(degrees);
  const calculatedExperience = calcExperienceFromEducation(profile);
  const portfolioEditable = mode === "edit";
  const educationEditable = portfolioEditable;
  const basicReadOnly = !basicEditable;
  const snapshotSplitActive = showEditModeSnapshotSplit && portfolioEditable && basicReadOnly;

  const snapshotFrameClass =
    "rounded-xl border border-zinc-200 bg-zinc-50/90 p-4 dark:border-zinc-800 dark:bg-zinc-900/60";
  const portfolioFrameClass =
    "rounded-xl border border-blue-200 bg-blue-50/30 p-4 dark:border-blue-900/50 dark:bg-blue-950/20";

  function updateProfile(next: ImportProfile) {
    onProfileChange(next);
  }

  function updateBasic(key: keyof ImportProfile["basic"], value: string) {
    updateProfile({
      ...profile,
      basic: {
        ...profile.basic,
        [key]: key === "employment_rate" ? (value ? Number(value) : null) : value,
      },
    });
  }

  function updateNotes(value: string) {
    updateProfile({ ...profile, notes_raw: value });
  }

  function updateDegrees(next: typeof degreeRecords) {
    updateProfile({ ...profile, degrees: buildDegreesState(next) });
  }

  function updateDegreeRow(index: number, patch: Partial<(typeof degreeRecords)[number]>) {
    const next = degreeRecords.map((row, i) => (i === index ? { ...row, ...patch } : row));
    updateDegrees(next);
  }

  function updateEducation(index: number, patch: Partial<(typeof educationRecords)[number]>) {
    const next = educationRecords.map((row, i) => (i === index ? { ...row, ...patch } : row));
    updateProfile({
      ...profile,
      education_records: next,
      education: { ...profile.education, basic: next },
    });
  }

  function updateTraining(index: number, patch: Partial<(typeof trainingRecords)[number]>) {
    const next = trainingRecords.map((row, i) => (i === index ? { ...row, ...patch } : row));
    updateProfile({ ...profile, training_records: next });
  }

  function updateCategory(index: number, patch: Partial<(typeof categoryRecords)[number]>) {
    const next = categoryRecords.map((row, i) => (i === index ? { ...row, ...patch } : row));
    updateProfile({ ...profile, category_records: next });
  }

  function updateCertificate(index: number, patch: Partial<(typeof certificateRecords)[number]>) {
    const next = certificateRecords.map((row, i) => (i === index ? { ...row, ...patch } : row));
    updateProfile({ ...profile, certificate_records: next });
  }

  function updateAward(index: number, patch: Partial<(typeof awardRecords)[number]>) {
    const next = awardRecords.map((row, i) => (i === index ? { ...row, ...patch } : row));
    updateProfile({ ...profile, award_records: next });
  }

  function handleTrainingTitleBlur(index: number, title: string, completedAt: string) {
    if ((completedAt || "").trim()) return;
    const year = extractYearFromText(title);
    if (!year) return;
    updateTraining(index, {
      title: stripYearFromText(title),
      completed_at: year,
    });
  }

  function handleEducationInstitutionBlur(index: number, institution: string, completedAt: string) {
    if ((completedAt || "").trim()) return;
    const year = extractYearFromText(institution);
    if (!year) return;
    updateEducation(index, {
      institution: stripYearFromText(institution),
      completed_at: year,
    });
  }

  function addEducationRow() {
    const next = [...educationRecords, emptyEducationRow()];
    updateProfile({
      ...profile,
      education_records: next,
      education: { ...profile.education, basic: next },
    });
  }

  function removeEducationRow(index: number) {
    const next = educationRecords.filter((_, idx) => idx !== index);
    updateProfile({
      ...profile,
      education_records: next,
      education: { ...profile.education, basic: next },
    });
  }

  function splitEducationRowAt(index: number) {
    const next = splitEducationRow(educationRecords, index);
    updateProfile({
      ...profile,
      education_records: next,
      education: { ...profile.education, basic: next },
    });
  }

  function handleCertificateNameBlur(index: number, name: string, issuedAt: string) {
    if ((issuedAt || "").trim()) return;
    const year = extractYearFromText(name);
    if (!year) return;
    const cleaned = stripYearFromText(name);
    updateCertificate(index, {
      topic: cleaned,
      specialty: cleaned,
      issued_at: year,
    });
  }

  function handleDegreeLabelBlur(index: number, label: string, completedAt: string) {
    if ((completedAt || "").trim()) return;
    const year = extractYearFromText(label);
    if (!year) return;
    updateDegreeRow(index, {
      label: stripYearFromText(label),
      completed_at: year,
    });
  }

  const basicSection = (
      <section>
        <h3 className="mb-3 text-base font-semibold text-zinc-800 dark:text-zinc-200">Базовая информация</h3>
        {snapshotSplitActive ? (
          <p className="mb-3 text-xs text-zinc-500">
            Кадровый snapshot из HR-импорта — только просмотр. Организационное назначение изменяется в разделе «Назначение».
          </p>
        ) : null}
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="ФИО" value={basic.full_name} readOnly={basicReadOnly} onChange={(v) => updateBasic("full_name", v)} />
          <Field label="ИИН" value={basic.iin} readOnly={basicReadOnly} onChange={(v) => updateBasic("iin", v)} />
          <Field label="Дата рождения" value={basic.birth_date} readOnly={basicReadOnly} onChange={(v) => updateBasic("birth_date", v)} />
          {basicReadOnly ? (
            <Field label="Пол" value={SEX_LABELS[basic.sex] || basic.sex || "—"} readOnly />
          ) : (
            <label className="block text-sm">
              <span className="mb-1 block text-xs text-zinc-500">Пол</span>
              <select className={inputClass} value={basic.sex} onChange={(e) => updateBasic("sex", e.target.value)}>
                <option value="">—</option>
                <option value="M">Мужской</option>
                <option value="F">Женский</option>
              </select>
            </label>
          )}
          <Field label="Отделение (исходное)" value={basic.department_source} readOnly={basicReadOnly} onChange={(v) => updateBasic("department_source", v)} />
          <Field label="Отделение (канон.)" value={departmentCanonical || "—"} readOnly />
          <Field label="Должность" value={basic.position_raw} readOnly={basicReadOnly} onChange={(v) => updateBasic("position_raw", v)} />
          <Field label="Ставка" value={basic.employment_rate != null ? String(basic.employment_rate) : ""} readOnly={basicReadOnly} onChange={(v) => updateBasic("employment_rate", v)} />
          <Field label="Национальность" value={basic.nationality} readOnly={basicReadOnly} onChange={(v) => updateBasic("nationality", v)} />
          <Field label="Телефон" value={basic.phone_raw} readOnly={basicReadOnly} onChange={(v) => updateBasic("phone_raw", v)} />
          <Field label="Квалификация (исходный текст)" value={basic.qualification_raw} readOnly={basicReadOnly} onChange={(v) => updateBasic("qualification_raw", v)} multiline />
          {showReviewStatus ? (
            <label className="block text-sm sm:col-span-2">
              <span className="mb-1 block text-xs text-zinc-500">Статус проверки</span>
              <select className={inputClass} value={reviewStatus} onChange={(e) => onReviewStatusChange?.(e.target.value)}>
                <option value="pending">На проверке</option>
                <option value="reviewed">Проверено</option>
                <option value="needs_attention">Требует внимания</option>
              </select>
            </label>
          ) : null}
        </div>
      </section>
  );

  const portfolioSections = (
    <>
      <section>
        <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
          <div>
            <h3 className="text-base font-semibold text-zinc-800 dark:text-zinc-200">Блок информации «Учебное заведение»</h3>
            <p className="text-xs text-zinc-500">из столбца H исходного файла</p>
          </div>
          {educationEditable ? (
            <button
              type="button"
              className="rounded border border-zinc-300 px-3 py-1 text-xs dark:border-zinc-700"
              onClick={addEducationRow}
            >
              Добавить строку
            </button>
          ) : null}
        </div>
        {!educationEditable ? (
          <table className="min-w-full text-sm">
            <thead className="text-left text-xs text-zinc-500">
              <tr>
                <th className="py-1 pr-2">Учебное заведение</th>
                <th className="py-1 pr-2">Специальность</th>
                <th className="py-1">Дата окончания</th>
              </tr>
            </thead>
            <tbody>
              {educationRecords.length === 0 ? (
                <tr><td colSpan={3} className="py-2 text-zinc-500">—</td></tr>
              ) : (
                educationRecords.map((row, i) => (
                  <tr key={i} className="border-t border-zinc-100 dark:border-zinc-800">
                    <td className="py-2 pr-2">{row.institution || "—"}</td>
                    <td className="py-2 pr-2">{row.specialty || "—"}</td>
                    <td className="py-2"><DocumentDateText value={row.completed_at || ""} /></td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        ) : (
          <div className="space-y-3">
            {educationRecords.length === 0 ? (
              <p className="text-sm text-zinc-500">Нет строк. Нажмите «Добавить строку».</p>
            ) : null}
            {educationRecords.map((row, i) => (
              <div key={i} className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-800">
                <div className="grid gap-2 sm:grid-cols-3">
                  <Field
                    label="Учебное заведение"
                    value={row.institution || ""}
                    onChange={(v) => updateEducation(i, { institution: v })}
                    onBlur={() => handleEducationInstitutionBlur(i, row.institution || "", row.completed_at || "")}
                  />
                  <Field label="Специальность" value={row.specialty || ""} onChange={(v) => updateEducation(i, { specialty: v })} />
                  <LabeledDocumentDateField
                    label="Дата окончания"
                    value={row.completed_at || ""}
                    onChange={(v) => updateEducation(i, { completed_at: v })}
                  />
                </div>
                <div className="mt-2 flex flex-wrap gap-2">
                  <button
                    type="button"
                    className="rounded border border-zinc-300 px-2 py-1 text-xs dark:border-zinc-700"
                    onClick={() => splitEducationRowAt(i)}
                  >
                    Разделить строку
                  </button>
                  <button
                    type="button"
                    className="rounded border border-red-300 px-2 py-1 text-xs text-red-700 dark:border-red-900"
                    onClick={() => removeEducationRow(i)}
                  >
                    Удалить
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      <section>
        <h3 className="mb-1 text-base font-semibold text-zinc-800 dark:text-zinc-200">Стаж</h3>
        <p className="mb-2 text-xs text-zinc-500">{EXPERIENCE_CALC_NOTE}</p>
        {calculatedExperience ? (
          <p className="text-sm">{calculatedExperience}</p>
        ) : (
          <p className="text-sm text-zinc-500">—</p>
        )}
      </section>

      <section>
        <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
          <h3 className="text-base font-semibold text-zinc-800 dark:text-zinc-200">Блок информации «Повышение квалификации»</h3>
          {portfolioEditable ? (
            <button
              type="button"
              className="rounded border border-zinc-300 px-3 py-1 text-xs dark:border-zinc-700"
              onClick={() => updateProfile({ ...profile, training_records: [...trainingRecords, emptyTrainingRow()] })}
            >
              Добавить строку
            </button>
          ) : null}
        </div>
        {!portfolioEditable ? (
          <table className="min-w-full text-sm">
            <thead className="text-left text-xs text-zinc-500">
              <tr>
                <th className="py-1 pr-2">Курс</th>
                <th className="py-1 pr-2">Организация</th>
                <th className="py-1 pr-2">Дата</th>
                <th className="py-1">Часы</th>
              </tr>
            </thead>
            <tbody>
              {trainingRecords.length === 0 ? (
                <tr><td colSpan={4} className="py-2 text-zinc-500">—</td></tr>
              ) : (
                trainingRecords.map((row, i) => (
                  <tr key={i} className="border-t border-zinc-100 dark:border-zinc-800">
                    <td className="py-2 pr-2">{row.title || "—"}</td>
                    <td className="py-2 pr-2">{row.organization || "—"}</td>
                    <td className="py-2 pr-2"><DocumentDateText value={row.completed_at || ""} /></td>
                    <td className="py-2">{row.hours ?? "—"}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        ) : (
          <div className="space-y-3">
            {trainingRecords.length === 0 ? (
              <p className="text-sm text-zinc-500">Нет строк. Нажмите «Добавить строку».</p>
            ) : null}
            {trainingRecords.map((row, i) => (
              <div key={i} className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-800">
                <div className="grid gap-2 sm:grid-cols-2">
                  <Field
                    label="Название курса"
                    value={row.title || ""}
                    onChange={(v) => updateTraining(i, { title: v })}
                    onBlur={() => handleTrainingTitleBlur(i, row.title || "", row.completed_at || "")}
                  />
                  <Field label="Организация" value={row.organization || ""} onChange={(v) => updateTraining(i, { organization: v })} />
                  <LabeledDocumentDateField
                    label="Дата"
                    value={row.completed_at || ""}
                    onChange={(v) => updateTraining(i, { completed_at: v })}
                  />
                  <Field label="Часы" value={row.hours != null ? String(row.hours) : ""} onChange={(v) => updateTraining(i, { hours: v ? Number(v) : null })} />
                </div>
                <div className="mt-2 flex flex-wrap gap-2">
                  <button type="button" className="rounded border border-zinc-300 px-2 py-1 text-xs dark:border-zinc-700" onClick={() => updateProfile({ ...profile, training_records: splitTrainingRow(trainingRecords, i) })}>
                    Разделить строку
                  </button>
                  <button type="button" className="rounded border border-red-300 px-2 py-1 text-xs text-red-700 dark:border-red-900" onClick={() => updateProfile({ ...profile, training_records: trainingRecords.filter((_, idx) => idx !== i) })}>
                    Удалить
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      <section>
        <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
          <h3 className="text-base font-semibold text-zinc-800 dark:text-zinc-200">Блок информации «Квалификационная категория»</h3>
          {portfolioEditable ? (
            <button type="button" className="rounded border border-zinc-300 px-3 py-1 text-xs dark:border-zinc-700" onClick={() => updateProfile({ ...profile, category_records: [...categoryRecords, emptyCategoryRow()] })}>
              Добавить строку
            </button>
          ) : null}
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead className="text-left text-xs text-zinc-500">
              <tr>
                <th className="py-1 pr-2">Категория</th>
                <th className="py-1 pr-2">Дата</th>
                <th className="py-1 pr-2">Специальность</th>
                <th className="py-1 pr-2">Примечание</th>
                {portfolioEditable ? <th className="py-1 w-16" /> : null}
              </tr>
            </thead>
            <tbody>
              {categoryRecords.length === 0 ? (
                <tr><td colSpan={portfolioEditable ? 5 : 4} className="py-2 text-zinc-500">—</td></tr>
              ) : (
                categoryRecords.map((row, i) => (
                  <tr key={i} className="border-t border-zinc-100 dark:border-zinc-800">
                    <td className="py-2 pr-2 align-top">
                      {portfolioEditable ? (
                        <select className={inputClass} value={categoryDisplayLabel(row.category)} onChange={(e) => updateCategory(i, { category: e.target.value })}>
                          <option value="">—</option>
                          {CATEGORY_OPTIONS.map((option) => (
                            <option key={option} value={option}>{option}</option>
                          ))}
                        </select>
                      ) : (
                        categoryDisplayLabel(row.category) || "—"
                      )}
                    </td>
                    <td className="py-2 pr-2 align-top">
                      {portfolioEditable ? (
                        <DocumentDateField
                          value={row.issued_at || ""}
                          testId={`import-category-date-${i}`}
                          onChange={(v) => updateCategory(i, { issued_at: v })}
                        />
                      ) : (
                        <DocumentDateText value={row.issued_at || ""} />
                      )}
                    </td>
                    <td className="py-2 pr-2 align-top">
                      {portfolioEditable ? (
                        <Field label="" value={row.specialty || ""} onChange={(v) => updateCategory(i, { specialty: v })} />
                      ) : (
                        row.specialty || "—"
                      )}
                    </td>
                    <td className="py-2 pr-2 align-top">
                      <RecordValidityNote issuedAt={row.issued_at || ""} />
                    </td>
                    {portfolioEditable ? (
                      <td className="py-2 align-top">
                        <button type="button" className="rounded border border-red-300 px-2 py-1 text-xs text-red-700 dark:border-red-900" onClick={() => updateProfile({ ...profile, category_records: categoryRecords.filter((_, idx) => idx !== i) })}>
                          ×
                        </button>
                      </td>
                    ) : null}
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>

      <section>
        <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
          <div>
            <h3 className="text-base font-semibold text-zinc-800 dark:text-zinc-200">Блок информации «Сертификаты»</h3>
            <p className="text-xs text-zinc-500">из столбца сертификата исходного файла</p>
          </div>
          {portfolioEditable ? (
            <button
              type="button"
              className="rounded border border-zinc-300 px-3 py-1 text-xs dark:border-zinc-700"
              onClick={() => updateProfile({ ...profile, certificate_records: [...certificateRecords, emptyCertificateRow()] })}
            >
              Добавить строку
            </button>
          ) : null}
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead className="text-left text-xs text-zinc-500">
              <tr>
                <th className="py-1 pr-2">Вид</th>
                <th className="py-1 pr-2">Название</th>
                <th className="py-1 pr-2">Дата выдачи</th>
                <th className="py-1 pr-2">Действует до</th>
                <th className="py-1 pr-2">часы</th>
                <th className="py-1 pr-2">Ссылка</th>
                <th className="py-1 pr-2">Примечание</th>
                {portfolioEditable ? <th className="py-1" /> : null}
              </tr>
            </thead>
            <tbody>
              {certificateRecords.length === 0 ? (
                <tr><td colSpan={portfolioEditable ? 8 : 7} className="py-2 text-zinc-500">—</td></tr>
              ) : (
                certificateRecords.map((row, i) => (
                  <tr key={i} className="border-t border-zinc-100 dark:border-zinc-800">
                    <td className="py-2 pr-2 align-top">
                      {portfolioEditable ? (
                        <Field label="" value={row.kind || ""} onChange={(v) => updateCertificate(i, { kind: v })} />
                      ) : (
                        row.kind || "—"
                      )}
                    </td>
                    <td className="max-w-xs py-2 pr-2 align-top">
                      {portfolioEditable ? (
                        <Field
                          label=""
                          value={row.topic || row.specialty || ""}
                          onChange={(v) => updateCertificate(i, { topic: v, specialty: v })}
                          onBlur={() => handleCertificateNameBlur(i, row.topic || row.specialty || "", row.issued_at || "")}
                        />
                      ) : (
                        <span className="whitespace-pre-wrap">{row.topic || row.specialty || "—"}</span>
                      )}
                    </td>
                    <td className="py-2 pr-2 align-top">
                      {portfolioEditable ? (
                        <DocumentDateField
                          value={row.issued_at || ""}
                          testId={`import-certificate-issued-${i}`}
                          onChange={(v) => updateCertificate(i, { issued_at: v })}
                        />
                      ) : (
                        <DocumentDateText value={row.issued_at || ""} />
                      )}
                    </td>
                    <td className="py-2 pr-2 align-top">
                      {portfolioEditable ? (
                        <DocumentDateField
                          value={row.valid_until || ""}
                          testId={`import-certificate-valid-until-${i}`}
                          onChange={(v) => updateCertificate(i, { valid_until: v })}
                        />
                      ) : (
                        <DocumentDateText value={row.valid_until || ""} />
                      )}
                    </td>
                    <td className="py-2 pr-2 align-top">
                      {portfolioEditable ? (
                        <Field label="" value={row.hours != null ? String(row.hours) : ""} onChange={(v) => updateCertificate(i, { hours: v ? Number(v) : null })} />
                      ) : (
                        row.hours ?? "—"
                      )}
                    </td>
                    <td className="max-w-[10rem] py-2 pr-2 align-top">
                      {portfolioEditable ? (
                        <Field label="" value={row.link || ""} onChange={(v) => updateCertificate(i, { link: v })} />
                      ) : (
                        <span className="truncate" title={row.link || ""}>{row.link || "—"}</span>
                      )}
                    </td>
                    <td className="py-2 pr-2 align-top">
                      <RecordValidityNote issuedAt={row.issued_at || ""} />
                    </td>
                    {portfolioEditable ? (
                      <td className="py-2 align-top">
                        <div className="flex flex-col gap-1">
                          <button
                            type="button"
                            className="rounded border border-zinc-300 px-1.5 py-0.5 text-[10px] dark:border-zinc-700"
                            onClick={() => updateProfile({ ...profile, certificate_records: splitCertificateRow(certificateRecords, i) })}
                          >
                            +
                          </button>
                          <button
                            type="button"
                            className="rounded border border-red-300 px-1.5 py-0.5 text-[10px] text-red-700 dark:border-red-900"
                            onClick={() => updateProfile({ ...profile, certificate_records: certificateRecords.filter((_, idx) => idx !== i) })}
                          >
                            ×
                          </button>
                        </div>
                      </td>
                    ) : null}
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>

      <section>
        <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
          <h3 className="text-base font-semibold text-zinc-800 dark:text-zinc-200">Блок информации «Степень»</h3>
          {portfolioEditable ? (
            <button
              type="button"
              className="rounded border border-zinc-300 px-3 py-1 text-xs dark:border-zinc-700"
              onClick={() => updateDegrees([...degreeRecords, emptyDegreeRow()])}
            >
              Добавить строку
            </button>
          ) : null}
        </div>
        {!portfolioEditable ? (
          <table className="min-w-full text-sm">
            <thead className="text-left text-xs text-zinc-500">
              <tr>
                <th className="py-1 pr-2">Степень</th>
                <th className="py-1">дата</th>
              </tr>
            </thead>
            <tbody>
              {degreeRecords.length === 0 ? (
                <tr><td colSpan={2} className="py-2 text-zinc-500">—</td></tr>
              ) : (
                degreeRecords.map((row, i) => (
                  <tr key={i} className="border-t border-zinc-100 dark:border-zinc-800">
                    <td className="py-2 pr-2 align-top whitespace-pre-wrap">{row.label || "—"}</td>
                    <td className="py-2 align-top"><DocumentDateText value={row.completed_at || ""} /></td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        ) : (
          <div className="space-y-3">
            {degreeRecords.length === 0 ? (
              <p className="text-sm text-zinc-500">Нет строк. Нажмите «Добавить строку».</p>
            ) : null}
            {degreeRecords.map((row, i) => (
              <div key={i} className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-800">
                <div className="grid gap-2 sm:grid-cols-2">
                  <Field
                    label="Степень"
                    value={row.label || ""}
                    onChange={(v) => updateDegreeRow(i, { label: v })}
                    onBlur={() => handleDegreeLabelBlur(i, row.label || "", row.completed_at || "")}
                  />
                  <LabeledDocumentDateField
                    label="дата"
                    value={row.completed_at || ""}
                    onChange={(v) => updateDegreeRow(i, { completed_at: v })}
                  />
                </div>
                <div className="mt-2 flex flex-wrap gap-2">
                  <button
                    type="button"
                    className="rounded border border-zinc-300 px-2 py-1 text-xs dark:border-zinc-700"
                    onClick={() => updateDegrees(splitDegreeRow(degreeRecords, i))}
                  >
                    Разделить строку
                  </button>
                  <button
                    type="button"
                    className="rounded border border-red-300 px-2 py-1 text-xs text-red-700 dark:border-red-900"
                    onClick={() => updateDegrees(degreeRecords.filter((_, idx) => idx !== i))}
                  >
                    Удалить
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      <section>
        <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
          <h3 className="text-base font-semibold text-zinc-800 dark:text-zinc-200">Блок «Награды»</h3>
          {portfolioEditable ? (
            <button type="button" className="rounded border border-zinc-300 px-3 py-1 text-xs dark:border-zinc-700" onClick={() => updateProfile({ ...profile, award_records: [...awardRecords, emptyAwardRow()] })}>
              Добавить строку
            </button>
          ) : null}
        </div>
        {!portfolioEditable ? (
          <table className="min-w-full text-sm">
            <thead className="text-left text-xs text-zinc-500">
              <tr>
                <th className="py-1 pr-2">Награда</th>
                <th className="py-1">Дата</th>
              </tr>
            </thead>
            <tbody>
              {awardRecords.length === 0 ? (
                <tr><td colSpan={2} className="py-2 text-zinc-500">—</td></tr>
              ) : (
                awardRecords.map((row, i) => (
                  <tr key={i} className="border-t border-zinc-100 dark:border-zinc-800">
                    <td className="py-2 pr-2">{row.title || "—"}</td>
                    <td className="py-2"><DocumentDateText value={row.date || ""} /></td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        ) : (
          <div className="space-y-3">
            {awardRecords.map((row, i) => (
              <div key={i} className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-800">
                <div className="grid gap-2 sm:grid-cols-2">
                  <Field label="Вид награды" value={row.title || ""} onChange={(v) => updateAward(i, { title: v })} />
                  <LabeledDocumentDateField label="Дата" value={row.date || ""} onChange={(v) => updateAward(i, { date: v })} />
                </div>
                <button type="button" className="mt-2 rounded border border-red-300 px-2 py-1 text-xs text-red-700 dark:border-red-900" onClick={() => updateProfile({ ...profile, award_records: awardRecords.filter((_, idx) => idx !== i) })}>
                  Удалить
                </button>
              </div>
            ))}
          </div>
        )}
      </section>

      <section>
        <h3 className="mb-1 text-base font-semibold text-zinc-800 dark:text-zinc-200">Примечание</h3>
        <p className="mb-2 text-xs text-zinc-500">декрет, инвалид, пенсионер, прочие комментарии</p>
        <Field label="" value={profile.notes_raw || ""} onChange={updateNotes} multiline readOnly={!portfolioEditable} />
      </section>
    </>
  );

  if (snapshotSplitActive) {
    return (
      <div className="space-y-6">
        <div className={snapshotFrameClass}>{basicSection}</div>
        <div className={portfolioFrameClass}>
          <p className="mb-4 text-xs font-medium uppercase tracking-wide text-blue-800 dark:text-blue-200">
            Редактируемые разделы портфолио
          </p>
          <div className="space-y-8">{portfolioSections}</div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {basicSection}
      {portfolioSections}
    </div>
  );
}
