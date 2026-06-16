"use client";

import * as React from "react";

import {
  archiveEducationProfile,
  mapImportApiError,
  saveEducationProfile,
  type EducationProfileDetail,
  type ImportProfile,
} from "../_lib/importApi.client";

const SEX_OPTIONS = [
  { value: "", label: "—" },
  { value: "M", label: "Мужской" },
  { value: "F", label: "Женский" },
];

type Props = {
  batchId: number;
  detail: EducationProfileDetail;
  onClose: () => void;
  onSaved: (detail: EducationProfileDetail) => void;
};

function Field({
  label,
  value,
  onChange,
  multiline = false,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  multiline?: boolean;
}) {
  return (
    <label className="block text-sm">
      <span className="mb-1 block text-xs text-zinc-500">{label}</span>
      {multiline ? (
        <textarea
          className="w-full rounded border border-zinc-300 px-2 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-950"
          rows={3}
          value={value}
          onChange={(e) => onChange(e.target.value)}
        />
      ) : (
        <input
          className="w-full rounded border border-zinc-300 px-2 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-950"
          value={value}
          onChange={(e) => onChange(e.target.value)}
        />
      )}
    </label>
  );
}

export default function ImportEducationProfileCardModal({ batchId, detail, onClose, onSaved }: Props) {
  const [profile, setProfile] = React.useState<ImportProfile>(() =>
    structuredClone(detail.profile)
  );
  const [reviewStatus, setReviewStatus] = React.useState(detail.review_status);
  const [saving, setSaving] = React.useState(false);
  const [archiving, setArchiving] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const basic = profile.basic;
  const educationRows = profile.education_records?.length
    ? profile.education_records
    : profile.education?.basic ?? [];

  function updateBasic(key: keyof ImportProfile["basic"], value: string) {
    setProfile((prev) => ({
      ...prev,
      basic: { ...prev.basic, [key]: key === "employment_rate" ? (value ? Number(value) : null) : value },
    }));
  }

  function updateNotes(value: string) {
    setProfile((prev) => ({ ...prev, notes_raw: value }));
  }

  async function handleSave() {
    setSaving(true);
    setError(null);
    try {
      const saved = await saveEducationProfile(batchId, detail.profile_id, {
        profile,
        review_status: reviewStatus,
      });
      onSaved(saved);
      onClose();
    } catch (e) {
      setError(mapImportApiError(e));
    } finally {
      setSaving(false);
    }
  }

  async function handleArchive() {
    if (!window.confirm("Архивировать профиль в staging? Кадровый контур не изменится.")) return;
    setArchiving(true);
    setError(null);
    try {
      const saved = await archiveEducationProfile(batchId, detail.profile_id);
      onSaved(saved);
      onClose();
    } catch (e) {
      setError(mapImportApiError(e));
    } finally {
      setArchiving(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/50 p-4">
      <div className="my-4 w-full max-w-4xl rounded-xl border border-zinc-200 bg-white shadow-xl dark:border-zinc-800 dark:bg-zinc-950">
        <div className="flex items-start justify-between border-b border-zinc-200 px-6 py-4 dark:border-zinc-800">
          <div>
            <h2 className="text-lg font-semibold">{detail.full_name || "Карточка сотрудника"}</h2>
            <p className="text-sm text-zinc-500">
              row #{detail.row_id} · {detail.source_sheet}:{detail.source_row_number}
            </p>
          </div>
          <button type="button" onClick={onClose} className="text-zinc-500 hover:text-zinc-800">
            ✕
          </button>
        </div>

        <div className="max-h-[70vh] space-y-6 overflow-y-auto px-6 py-4">
          {error ? <div className="text-sm text-red-600">{error}</div> : null}

          <section>
            <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-zinc-500">
              1. Базовая информация
            </h3>
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="ФИО" value={basic.full_name} onChange={(v) => updateBasic("full_name", v)} />
              <Field label="ИИН" value={basic.iin} onChange={(v) => updateBasic("iin", v)} />
              <Field
                label="Дата рождения"
                value={basic.birth_date}
                onChange={(v) => updateBasic("birth_date", v)}
              />
              <label className="block text-sm">
                <span className="mb-1 block text-xs text-zinc-500">Пол</span>
                <select
                  className="w-full rounded border border-zinc-300 px-2 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-950"
                  value={basic.sex}
                  onChange={(e) => updateBasic("sex", e.target.value)}
                >
                  {SEX_OPTIONS.map((o) => (
                    <option key={o.value} value={o.value}>
                      {o.label}
                    </option>
                  ))}
                </select>
              </label>
              <Field
                label="Отделение (исходное)"
                value={basic.department_source}
                onChange={(v) => updateBasic("department_source", v)}
              />
              <div className="block text-sm">
                <span className="mb-1 block text-xs text-zinc-500">Отделение (canonical)</span>
                <div className="rounded border border-zinc-200 bg-zinc-50 px-2 py-1.5 text-sm dark:border-zinc-800 dark:bg-zinc-900">
                  {detail.department_recoding?.org_unit_name || "—"}
                </div>
              </div>
              <Field label="Должность" value={basic.position_raw} onChange={(v) => updateBasic("position_raw", v)} />
              <Field
                label="Ставка"
                value={basic.employment_rate != null ? String(basic.employment_rate) : ""}
                onChange={(v) => updateBasic("employment_rate", v)}
              />
              <Field
                label="Стаж"
                value={basic.experience_raw}
                onChange={(v) => updateBasic("experience_raw", v)}
                multiline
              />
              <label className="block text-sm">
                <span className="mb-1 block text-xs text-zinc-500">Статус проверки</span>
                <select
                  className="w-full rounded border border-zinc-300 px-2 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-950"
                  value={reviewStatus}
                  onChange={(e) => setReviewStatus(e.target.value)}
                >
                  <option value="pending">На проверке</option>
                  <option value="reviewed">Проверено</option>
                  <option value="needs_attention">Требует внимания</option>
                </select>
              </label>
            </div>
          </section>

          <section>
            <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-zinc-500">
              2. Учебное заведение
            </h3>
            <table className="min-w-full text-sm">
              <thead className="text-left text-xs text-zinc-500">
                <tr>
                  <th className="py-1 pr-2">Учебное заведение</th>
                  <th className="py-1">Год окончания</th>
                </tr>
              </thead>
              <tbody>
                {educationRows.length === 0 ? (
                  <tr>
                    <td colSpan={2} className="py-2 text-zinc-500">
                      —
                    </td>
                  </tr>
                ) : (
                  educationRows.map((row, i) => (
                    <tr key={i} className="border-t border-zinc-100 dark:border-zinc-800">
                      <td className="py-2 pr-2">{row.institution || "—"}</td>
                      <td className="py-2">{row.completed_at || "—"}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </section>

          <section>
            <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-zinc-500">
              3. Повышение квалификации
            </h3>
            <table className="min-w-full text-sm">
              <thead className="text-left text-xs text-zinc-500">
                <tr>
                  <th className="py-1 pr-2">Курс</th>
                  <th className="py-1 pr-2">Год</th>
                  <th className="py-1">Часы</th>
                </tr>
              </thead>
              <tbody>
                {profile.training_records.length === 0 ? (
                  <tr>
                    <td colSpan={3} className="py-2 text-zinc-500">
                      —
                    </td>
                  </tr>
                ) : (
                  profile.training_records.map((row, i) => (
                    <tr key={i} className="border-t border-zinc-100 dark:border-zinc-800">
                      <td className="py-2 pr-2">{row.title}</td>
                      <td className="py-2 pr-2">{row.completed_at || "—"}</td>
                      <td className="py-2">{row.hours ?? "—"}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </section>

          <section>
            <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-zinc-500">
              4. Квалификационная категория
            </h3>
            <table className="min-w-full text-sm">
              <thead className="text-left text-xs text-zinc-500">
                <tr>
                  <th className="py-1 pr-2">Категория</th>
                  <th className="py-1 pr-2">Дата</th>
                  <th className="py-1">Специальность</th>
                </tr>
              </thead>
              <tbody>
                {profile.category_records.length === 0 ? (
                  <tr>
                    <td colSpan={3} className="py-2 text-zinc-500">
                      —
                    </td>
                  </tr>
                ) : (
                  profile.category_records.map((row, i) => (
                    <tr key={i} className="border-t border-zinc-100 dark:border-zinc-800">
                      <td className="py-2 pr-2">{row.category}</td>
                      <td className="py-2 pr-2">{row.issued_at || "—"}</td>
                      <td className="py-2">{row.specialty || "—"}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </section>

          <section>
            <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-zinc-500">5. Сертификаты</h3>
            <table className="min-w-full text-sm">
              <thead className="text-left text-xs text-zinc-500">
                <tr>
                  <th className="py-1 pr-2">Вид</th>
                  <th className="py-1 pr-2">Тема</th>
                  <th className="py-1 pr-2">Дата</th>
                  <th className="py-1 pr-2">Часы</th>
                  <th className="py-1">Ссылка</th>
                </tr>
              </thead>
              <tbody>
                {profile.certificate_records.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="py-2 text-zinc-500">
                      —
                    </td>
                  </tr>
                ) : (
                  profile.certificate_records.map((row, i) => (
                    <tr key={i} className="border-t border-zinc-100 dark:border-zinc-800">
                      <td className="py-2 pr-2">{row.kind || "—"}</td>
                      <td className="py-2 pr-2">{row.topic || row.specialty || "—"}</td>
                      <td className="py-2 pr-2">{row.issued_at || "—"}</td>
                      <td className="py-2 pr-2">{row.hours ?? "—"}</td>
                      <td className="py-2">{row.link || "—"}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </section>

          <section>
            <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-zinc-500">6. Степень</h3>
            <p className="text-sm">
              {profile.degrees.candidate_medical_sciences ? "Кандидат медицинских наук" : null}
              {profile.degrees.doctor_medical_sciences ? "Доктор медицинских наук" : null}
              {!profile.degrees.candidate_medical_sciences && !profile.degrees.doctor_medical_sciences
                ? profile.degrees.raw_text || "—"
                : null}
            </p>
          </section>

          <section>
            <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-zinc-500">7. Награды</h3>
            <table className="min-w-full text-sm">
              <thead className="text-left text-xs text-zinc-500">
                <tr>
                  <th className="py-1 pr-2">Награда</th>
                  <th className="py-1">Дата</th>
                </tr>
              </thead>
              <tbody>
                {profile.award_records.length === 0 ? (
                  <tr>
                    <td colSpan={2} className="py-2 text-zinc-500">
                      —
                    </td>
                  </tr>
                ) : (
                  profile.award_records.map((row, i) => (
                    <tr key={i} className="border-t border-zinc-100 dark:border-zinc-800">
                      <td className="py-2 pr-2">{row.title}</td>
                      <td className="py-2">{row.date || "—"}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </section>

          <section>
            <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-zinc-500">8. Примечание</h3>
            <Field
              label=""
              value={profile.notes_raw || ""}
              onChange={updateNotes}
              multiline
            />
          </section>
        </div>

        <div className="flex flex-wrap justify-end gap-2 border-t border-zinc-200 px-6 py-4 dark:border-zinc-800">
          <button
            type="button"
            onClick={handleArchive}
            disabled={archiving || saving}
            className="rounded border border-zinc-300 px-4 py-2 text-sm text-zinc-700 hover:bg-zinc-50 disabled:opacity-50 dark:border-zinc-700 dark:text-zinc-300"
          >
            {archiving ? "Архивирование…" : "Архивировать"}
          </button>
          <button
            type="button"
            onClick={onClose}
            className="rounded border border-zinc-300 px-4 py-2 text-sm dark:border-zinc-700"
          >
            Отмена
          </button>
          <button
            type="button"
            onClick={handleSave}
            disabled={saving || archiving}
            className="rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {saving ? "Сохранение…" : "Сохранить"}
          </button>
        </div>
      </div>
    </div>
  );
}
