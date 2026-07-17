"use client";

import * as React from "react";
import { useParams } from "next/navigation";

import {
  INTAKE_STEPS,
  autosaveIntakeDraft,
  emptyIntakeDraftPayload,
  mapIntakeApiError,
  openIntakeSession,
  submitIntakeDraft,
  type IntakeDraftPayload,
} from "../_lib/intakeApi.client";

function Field({
  label,
  value,
  onChange,
  readOnly,
  type = "text",
  required = false,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  readOnly?: boolean;
  type?: string;
  required?: boolean;
}) {
  return (
    <label className="block">
      <span className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
        {label}
        {required ? " *" : ""}
      </span>
      <input
        type={type}
        value={value}
        readOnly={readOnly}
        onChange={(e) => onChange(e.target.value)}
        className="mt-1 w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm read-only:bg-zinc-50 dark:border-zinc-700 dark:bg-zinc-950 dark:read-only:bg-zinc-900"
      />
    </label>
  );
}

function StepPersonal({
  payload,
  onChange,
  readOnly,
}: {
  payload: IntakeDraftPayload;
  onChange: (p: IntakeDraftPayload) => void;
  readOnly?: boolean;
}) {
  const p = payload.personal;
  const set = (key: keyof typeof p, value: string) =>
    onChange({ ...payload, personal: { ...p, [key]: value } });
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      <Field label="Фамилия" value={p.last_name} onChange={(v) => set("last_name", v)} readOnly={readOnly} required />
      <Field label="Имя" value={p.first_name} onChange={(v) => set("first_name", v)} readOnly={readOnly} required />
      <Field label="Отчество" value={p.middle_name} onChange={(v) => set("middle_name", v)} readOnly={readOnly} />
      <Field label="Дата рождения" value={p.birth_date} onChange={(v) => set("birth_date", v)} readOnly={readOnly} type="date" />
      <Field label="Место рождения" value={p.birth_place} onChange={(v) => set("birth_place", v)} readOnly={readOnly} />
      <Field label="Пол" value={p.gender} onChange={(v) => set("gender", v)} readOnly={readOnly} />
      <Field label="Гражданство" value={p.citizenship} onChange={(v) => set("citizenship", v)} readOnly={readOnly} />
      <Field label="Национальность" value={p.nationality} onChange={(v) => set("nationality", v)} readOnly={readOnly} />
    </div>
  );
}

function StepContacts({
  payload,
  onChange,
  readOnly,
}: {
  payload: IntakeDraftPayload;
  onChange: (p: IntakeDraftPayload) => void;
  readOnly?: boolean;
}) {
  const c = payload.contacts;
  const set = (key: keyof typeof c, value: string) =>
    onChange({ ...payload, contacts: { ...c, [key]: value } });
  return (
    <div className="grid gap-4">
      <Field label="Мобильный телефон" value={c.mobile_phone} onChange={(v) => set("mobile_phone", v)} readOnly={readOnly} required />
      <Field label="Email" value={c.email} onChange={(v) => set("email", v)} readOnly={readOnly} type="email" />
      <Field label="Адрес регистрации" value={c.registration_address} onChange={(v) => set("registration_address", v)} readOnly={readOnly} />
      <Field label="Адрес проживания" value={c.residence_address} onChange={(v) => set("residence_address", v)} readOnly={readOnly} />
    </div>
  );
}

function CardListStep<T extends Record<string, string>>({
  title,
  items,
  emptyItem,
  fields,
  readOnly,
  onChange,
}: {
  title: string;
  items: T[];
  emptyItem: T;
  fields: Array<{ key: keyof T; label: string }>;
  readOnly?: boolean;
  onChange: (items: T[]) => void;
}) {
  return (
    <div className="space-y-4">
      {items.length === 0 ? (
        <p className="text-sm text-zinc-500">Записей пока нет.</p>
      ) : (
        items.map((item, index) => (
          <div key={index} className="rounded-xl border border-zinc-200 p-4 dark:border-zinc-800">
            <div className="grid gap-3 sm:grid-cols-2">
              {fields.map((f) => (
                <Field
                  key={String(f.key)}
                  label={f.label}
                  value={String(item[f.key] ?? "")}
                  readOnly={readOnly}
                  onChange={(v) => {
                    const next = [...items];
                    next[index] = { ...item, [f.key]: v };
                    onChange(next);
                  }}
                />
              ))}
            </div>
            {!readOnly ? (
              <button
                type="button"
                className="mt-3 text-sm text-red-600 hover:underline"
                onClick={() => onChange(items.filter((_, i) => i !== index))}
              >
                Удалить
              </button>
            ) : null}
          </div>
        ))
      )}
      {!readOnly ? (
        <button
          type="button"
          className="rounded-lg border border-dashed border-zinc-300 px-4 py-2 text-sm text-zinc-700 hover:bg-zinc-50 dark:border-zinc-700 dark:text-zinc-300"
          onClick={() => onChange([...items, { ...emptyItem }])}
        >
          Добавить {title.toLowerCase()}
        </button>
      ) : null}
    </div>
  );
}

function StepMilitary({
  payload,
  onChange,
  readOnly,
}: {
  payload: IntakeDraftPayload;
  onChange: (p: IntakeDraftPayload) => void;
  readOnly?: boolean;
}) {
  const m = payload.military;
  const set = (key: keyof typeof m, value: string) =>
    onChange({ ...payload, military: { ...m, [key]: value } });
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      <Field label="Статус" value={m.status} onChange={(v) => set("status", v)} readOnly={readOnly} />
      <Field label="Звание" value={m.rank} onChange={(v) => set("rank", v)} readOnly={readOnly} />
      <Field label="Категория" value={m.category} onChange={(v) => set("category", v)} readOnly={readOnly} />
      <Field label="Состав" value={m.composition} onChange={(v) => set("composition", v)} readOnly={readOnly} />
      <Field label="Военно-учётная специальность" value={m.specialty_code} onChange={(v) => set("specialty_code", v)} readOnly={readOnly} />
      <Field label="Категория годности" value={m.fitness_category} onChange={(v) => set("fitness_category", v)} readOnly={readOnly} />
      <Field label="Военкомат" value={m.commissariat} onChange={(v) => set("commissariat", v)} readOnly={readOnly} />
      <Field label="Группа учёта" value={m.registration_group} onChange={(v) => set("registration_group", v)} readOnly={readOnly} />
      <Field label="Категория учёта" value={m.registration_category} onChange={(v) => set("registration_category", v)} readOnly={readOnly} />
    </div>
  );
}

export default function IntakePageClient() {
  const params = useParams<{ token: string }>();
  const token = String(params?.token || "").trim();

  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [payload, setPayload] = React.useState<IntakeDraftPayload>(emptyIntakeDraftPayload());
  const [readOnly, setReadOnly] = React.useState(false);
  const [submitted, setSubmitted] = React.useState(false);
  const [stepIndex, setStepIndex] = React.useState(0);
  const [saving, setSaving] = React.useState(false);
  const [saveNotice, setSaveNotice] = React.useState<string | null>(null);
  const [submitting, setSubmitting] = React.useState(false);

  const autosaveTimer = React.useRef<number | null>(null);

  React.useEffect(() => {
    if (!token) {
      setError("Ссылка недействительна.");
      setLoading(false);
      return;
    }
    let cancelled = false;
    setLoading(true);
    void openIntakeSession(token)
      .then((session) => {
        if (cancelled) return;
        setPayload(session.payload ?? emptyIntakeDraftPayload());
        setReadOnly(Boolean(session.read_only));
        setSubmitted(session.status === "submitted" || session.read_only);
        const idx = INTAKE_STEPS.findIndex((s) => s.id === session.payload?.current_step);
        setStepIndex(idx >= 0 ? idx : 0);
      })
      .catch((e) => {
        if (!cancelled) setError(mapIntakeApiError(e, "Не удалось открыть анкету"));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [token]);

  const scheduleAutosave = React.useCallback(
    (next: IntakeDraftPayload) => {
      if (readOnly || !token) return;
      if (autosaveTimer.current) window.clearTimeout(autosaveTimer.current);
      autosaveTimer.current = window.setTimeout(() => {
        setSaving(true);
        void autosaveIntakeDraft(token, next)
          .then(() => setSaveNotice("Сохранено"))
          .catch(() => setSaveNotice("Ошибка автосохранения"))
          .finally(() => setSaving(false));
      }, 800);
    },
    [readOnly, token],
  );

  const updatePayload = React.useCallback(
    (next: IntakeDraftPayload) => {
      setPayload(next);
      scheduleAutosave(next);
    },
    [scheduleAutosave],
  );

  const currentStep = INTAKE_STEPS[stepIndex];

  function goNext() {
    const nextIndex = Math.min(stepIndex + 1, INTAKE_STEPS.length - 1);
    const next = { ...payload, current_step: INTAKE_STEPS[nextIndex].id };
    setPayload(next);
    setStepIndex(nextIndex);
    scheduleAutosave(next);
  }

  function goBack() {
    const nextIndex = Math.max(stepIndex - 1, 0);
    const next = { ...payload, current_step: INTAKE_STEPS[nextIndex].id };
    setPayload(next);
    setStepIndex(nextIndex);
    scheduleAutosave(next);
  }

  async function handleSubmit() {
    if (!token || readOnly) return;
    setSubmitting(true);
    setError(null);
    try {
      await submitIntakeDraft(token, payload);
      setSubmitted(true);
      setReadOnly(true);
    } catch (e) {
      setError(mapIntakeApiError(e, "Не удалось отправить анкету"));
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-zinc-50 dark:bg-zinc-950">
        <p className="text-sm text-zinc-500">Загрузка анкеты…</p>
      </div>
    );
  }

  if (error && !payload.personal.last_name && !submitted) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-zinc-50 px-4 dark:bg-zinc-950">
        <div className="max-w-md rounded-xl border border-red-200 bg-white p-6 text-center dark:border-red-900 dark:bg-zinc-900">
          <h1 className="text-lg font-semibold text-zinc-900 dark:text-zinc-50">Анкета недоступна</h1>
          <p className="mt-2 text-sm text-red-700 dark:text-red-300">{error}</p>
        </div>
      </div>
    );
  }

  if (submitted) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-zinc-50 px-4 dark:bg-zinc-950">
        <div className="max-w-md rounded-xl border border-emerald-200 bg-white p-8 text-center dark:border-emerald-900 dark:bg-zinc-900">
          <h1 className="text-xl font-semibold text-zinc-900 dark:text-zinc-50">Анкета отправлена</h1>
          <p className="mt-3 text-sm text-zinc-600 dark:text-zinc-400">
            Ваши сведения переданы в отдел кадров. Дальнейшее редактирование недоступно.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-zinc-950">
      <div className="mx-auto max-w-3xl px-4 py-8">
        <header className="mb-6">
          <h1 className="text-2xl font-semibold text-zinc-900 dark:text-zinc-50">Анкета нового сотрудника</h1>
          <p className="mt-1 text-sm text-zinc-500">
            Шаг {stepIndex + 1} из {INTAKE_STEPS.length}: {currentStep.title}
          </p>
          <div className="mt-3 h-2 overflow-hidden rounded-full bg-zinc-200 dark:bg-zinc-800">
            <div
              className="h-full bg-sky-600 transition-all"
              style={{ width: `${((stepIndex + 1) / INTAKE_STEPS.length) * 100}%` }}
            />
          </div>
          {saveNotice ? <p className="mt-2 text-xs text-zinc-500">{saving ? "Сохранение…" : saveNotice}</p> : null}
        </header>

        <main className="rounded-xl border border-zinc-200 bg-white p-6 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
          {error ? <p className="mb-4 text-sm text-red-600">{error}</p> : null}

          {currentStep.id === "personal" ? (
            <StepPersonal payload={payload} onChange={updatePayload} readOnly={readOnly} />
          ) : null}
          {currentStep.id === "contacts" ? (
            <StepContacts payload={payload} onChange={updatePayload} readOnly={readOnly} />
          ) : null}
          {currentStep.id === "education" ? (
            <CardListStep
              title="образование"
              items={payload.education}
              emptyItem={{ institution: "", year_from: "", year_to: "", specialty: "", qualification: "", diploma_number: "" }}
              fields={[
                { key: "institution", label: "Учебное заведение" },
                { key: "year_from", label: "Год поступления" },
                { key: "year_to", label: "Год окончания" },
                { key: "specialty", label: "Специальность" },
                { key: "qualification", label: "Квалификация" },
                { key: "diploma_number", label: "№ диплома" },
              ]}
              readOnly={readOnly}
              onChange={(items) => updatePayload({ ...payload, education: items })}
            />
          ) : null}
          {currentStep.id === "training" ? (
            <CardListStep
              title="обучение"
              items={payload.training}
              emptyItem={{ institution: "", year: "", course_name: "", hours: "" as unknown as never }}
              fields={[
                { key: "institution", label: "Организация" },
                { key: "year", label: "Год" },
                { key: "course_name", label: "Курс" },
              ]}
              readOnly={readOnly}
              onChange={(items) => updatePayload({ ...payload, training: items })}
            />
          ) : null}
          {currentStep.id === "relatives" ? (
            <CardListStep
              title="родственника"
              items={payload.relatives}
              emptyItem={{ relationship: "", full_name: "", birth_year: "", work_place: "" }}
              fields={[
                { key: "relationship", label: "Степень родства" },
                { key: "full_name", label: "ФИО" },
                { key: "birth_year", label: "Год рождения" },
                { key: "work_place", label: "Место работы" },
              ]}
              readOnly={readOnly}
              onChange={(items) => updatePayload({ ...payload, relatives: items })}
            />
          ) : null}
          {currentStep.id === "employment_biography" ? (
            <CardListStep
              title="место работы"
              items={payload.employment_biography}
              emptyItem={{ organization: "", position: "", year_from: "", year_to: "", reason_for_leaving: "" }}
              fields={[
                { key: "organization", label: "Организация" },
                { key: "position", label: "Должность" },
                { key: "year_from", label: "С" },
                { key: "year_to", label: "По" },
                { key: "reason_for_leaving", label: "Причина увольнения" },
              ]}
              readOnly={readOnly}
              onChange={(items) => updatePayload({ ...payload, employment_biography: items })}
            />
          ) : null}
          {currentStep.id === "military" ? (
            <StepMilitary payload={payload} onChange={updatePayload} readOnly={readOnly} />
          ) : null}
          {currentStep.id === "review" ? (
            <div className="space-y-3 text-sm text-zinc-700 dark:text-zinc-300">
              <p>Проверьте введённые сведения перед отправкой в отдел кадров.</p>
              <ul className="list-disc space-y-1 pl-5">
                <li>
                  ФИО: {payload.personal.last_name} {payload.personal.first_name} {payload.personal.middle_name}
                </li>
                <li>Телефон: {payload.contacts.mobile_phone || "—"}</li>
                <li>Образование: {payload.education.length} зап.</li>
                <li>Родственники: {payload.relatives.length} зап.</li>
              </ul>
            </div>
          ) : null}

          <div className="mt-8 flex items-center justify-between gap-3">
            <button
              type="button"
              disabled={stepIndex === 0 || readOnly}
              onClick={goBack}
              className="rounded-lg border border-zinc-300 px-4 py-2 text-sm disabled:opacity-40 dark:border-zinc-700"
            >
              Назад
            </button>
            {currentStep.id === "review" ? (
              <button
                type="button"
                disabled={readOnly || submitting}
                onClick={() => void handleSubmit()}
                className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700 disabled:opacity-50"
                data-testid="intake-submit-button"
              >
                {submitting ? "Отправка…" : "Отправить в отдел кадров"}
              </button>
            ) : (
              <button
                type="button"
                disabled={readOnly}
                onClick={goNext}
                className="rounded-lg bg-sky-600 px-4 py-2 text-sm font-medium text-white hover:bg-sky-700 disabled:opacity-50"
              >
                Далее
              </button>
            )}
          </div>
        </main>

        <p className="mt-4 text-center text-xs text-zinc-500">
          Данные сохраняются автоматически. Вы можете продолжить позже.
        </p>
      </div>
    </div>
  );
}
