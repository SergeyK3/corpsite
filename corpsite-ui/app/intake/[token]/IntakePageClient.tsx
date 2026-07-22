"use client";

import * as React from "react";
import { useParams } from "next/navigation";

import IntakeDictionaryCombobox from "../_components/IntakeDictionaryCombobox";
import IntakeMilitaryCombobox from "../_components/IntakeMilitaryCombobox";
import {
  INTAKE_CITIZENSHIP_CATALOG,
  INTAKE_CITIZENSHIP_POPULAR,
  INTAKE_NATIONALITY_CATALOG,
  INTAKE_NATIONALITY_POPULAR,
} from "../_lib/intakePersonalDictionary";
import {
  applyIntakeMilitaryCompositionChange,
  getIntakeMilitaryRankOptions,
  INTAKE_MILITARY_COMPOSITION_CATALOG,
  normalizeIntakeMilitaryComposition,
  reconcileIntakeMilitaryDraftOnLoad,
} from "../_lib/intakeMilitaryDictionary";
import {
  INTAKE_EDUCATION_TYPE_OPTIONS,
  INTAKE_STEPS,
  autosaveIntakeDraft,
  emptyIntakeDraftPayload,
  mapIntakeApiError,
  openIntakeSession,
  submitIntakeDraft,
  type IntakeDraftPayload,
  type IntakeEducation,
} from "../_lib/intakeApi.client";
import {
  applyContactsRegistrationAddressChange,
  applyContactsResidenceMirror,
  contactsMirrorResidence,
  formatIntakeFullName,
} from "../_lib/intakeContactHelpers";
import {
  formatIntakeEducationReviewLine,
  formatIntakePeriodForDisplay,
  formatIntakeTrainingReviewLine,
  parseIntakePeriodInput,
  type IntakePeriodPrecision,
} from "../_lib/intakePeriodFormat";
import { formatPersonnelDate } from "@/lib/personnelDateFormat";
import { sanitizeMilitarySpecialtyCodeInput } from "@/lib/militarySpecialtyCode";

function SelectField<V extends string>({
  label,
  value,
  onChange,
  readOnly,
  required = false,
  options,
}: {
  label: string;
  value: V;
  onChange: (v: V) => void;
  readOnly?: boolean;
  required?: boolean;
  options: ReadonlyArray<{ value: V; label: string }>;
}) {
  return (
    <label className="block">
      <span className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
        {label}
        {required ? " *" : ""}
      </span>
      <select
        value={value}
        disabled={readOnly}
        onChange={(e) => {
          const selected = options.find((option) => option.value === e.target.value);
          if (selected) onChange(selected.value);
        }}
        className="mt-1 w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm disabled:bg-zinc-50 dark:border-zinc-700 dark:bg-zinc-950 dark:disabled:bg-zinc-900"
      >
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </label>
  );
}

function Field({
  label,
  value,
  onChange,
  readOnly,
  type = "text",
  required = false,
  testId,
  maxLength,
  inputMode,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  readOnly?: boolean;
  type?: string;
  required?: boolean;
  testId?: string;
  maxLength?: number;
  inputMode?: React.HTMLAttributes<HTMLInputElement>["inputMode"];
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
        data-testid={testId}
        maxLength={maxLength}
        inputMode={inputMode}
        onChange={(e) => onChange(e.target.value)}
        className="mt-1 w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm read-only:bg-zinc-50 dark:border-zinc-700 dark:bg-zinc-950 dark:read-only:bg-zinc-900"
      />
    </label>
  );
}

function IntakePeriodField({
  label,
  value,
  onChange,
  readOnly,
  precision,
  required = false,
  testId,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  readOnly?: boolean;
  precision: IntakePeriodPrecision;
  required?: boolean;
  testId?: string;
}) {
  const [focused, setFocused] = React.useState(false);
  const [draft, setDraft] = React.useState("");
  const display = formatIntakePeriodForDisplay(value, precision);

  React.useEffect(() => {
    if (!focused) setDraft(display);
  }, [display, focused]);

  return (
    <label className="block">
      <span className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
        {label}
        {required ? " *" : ""}
      </span>
      <input
        type="text"
        inputMode={precision === "year" ? "numeric" : "text"}
        value={focused ? draft : display}
        readOnly={readOnly}
        data-testid={testId}
        placeholder={precision === "year" ? "ГГГГ" : "ДД.ММ.ГГГГ"}
        onFocus={() => {
          setDraft(display);
          setFocused(true);
        }}
        onBlur={() => {
          setFocused(false);
          if (draft.trim() === display.trim()) return;
          onChange(parseIntakePeriodInput(draft, precision));
        }}
        onChange={(e) => {
          const nextDraft = e.target.value;
          setDraft(nextDraft);
          onChange(parseIntakePeriodInput(nextDraft, precision));
        }}
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
      <IntakeDictionaryCombobox
        label="Гражданство"
        value={p.citizenship}
        onChange={(v) => set("citizenship", v)}
        readOnly={readOnly}
        popular={INTAKE_CITIZENSHIP_POPULAR}
        catalog={INTAKE_CITIZENSHIP_CATALOG}
        testId="intake-citizenship"
      />
      <IntakeDictionaryCombobox
        label="Национальность"
        value={p.nationality}
        onChange={(v) => set("nationality", v)}
        readOnly={readOnly}
        popular={INTAKE_NATIONALITY_POPULAR}
        catalog={INTAKE_NATIONALITY_CATALOG}
        testId="intake-nationality"
      />
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
  const [mirrorResidence, setMirrorResidence] = React.useState(() => contactsMirrorResidence(c));

  const set = (key: keyof typeof c, value: string) =>
    onChange({ ...payload, contacts: { ...c, [key]: value } });

  return (
    <div className="grid gap-4">
      <Field label="Мобильный телефон" value={c.mobile_phone} onChange={(v) => set("mobile_phone", v)} readOnly={readOnly} required />
      <Field label="Email" value={c.email} onChange={(v) => set("email", v)} readOnly={readOnly} type="email" />
      <Field
        label="Адрес регистрации"
        value={c.registration_address}
        onChange={(v) =>
          onChange({
            ...payload,
            contacts: applyContactsRegistrationAddressChange(c, v, mirrorResidence),
          })
        }
        readOnly={readOnly}
      />
      {!readOnly ? (
        <label className="flex items-center gap-2 text-sm text-zinc-700 dark:text-zinc-300">
          <input
            type="checkbox"
            checked={mirrorResidence}
            data-testid="intake-residence-mirror"
            onChange={(e) => {
              const checked = e.target.checked;
              setMirrorResidence(checked);
              onChange({
                ...payload,
                contacts: applyContactsResidenceMirror(c, checked),
              });
            }}
          />
          Адрес проживания совпадает с адресом регистрации
        </label>
      ) : null}
      <Field
        label="Адрес проживания"
        value={c.residence_address}
        testId="intake-residence-address"
        onChange={(v) => {
          setMirrorResidence(false);
          set("residence_address", v);
        }}
        readOnly={readOnly || mirrorResidence}
      />
    </div>
  );
}

type CardListFieldDef<T extends Record<string, string>> = {
  [K in keyof T]: {
    key: K;
    label: string;
    required?: boolean;
    periodPrecision?: IntakePeriodPrecision;
    testId?: string;
    options?: ReadonlyArray<{ value: Extract<T[K], string>; label: string }>;
  };
}[keyof T];

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
  fields: CardListFieldDef<T>[];
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
              {fields.map((f) =>
                f.options ? (
                  <SelectField
                    key={String(f.key)}
                    label={f.label}
                    value={String(item[f.key] ?? f.options[0]?.value ?? "")}
                    readOnly={readOnly}
                    required={f.required}
                    options={f.options}
                    onChange={(v) => {
                      const next = [...items];
                      next[index] = { ...item, [f.key]: v };
                      onChange(next);
                    }}
                  />
                ) : f.periodPrecision ? (
                  <IntakePeriodField
                    key={String(f.key)}
                    label={f.label}
                    value={String(item[f.key] ?? "")}
                    readOnly={readOnly}
                    required={f.required}
                    precision={f.periodPrecision}
                    testId={f.testId}
                    onChange={(v) => {
                      const next = [...items];
                      next[index] = { ...item, [f.key]: v };
                      onChange(next);
                    }}
                  />
                ) : (
                  <Field
                    key={String(f.key)}
                    label={f.label}
                    value={String(item[f.key] ?? "")}
                    readOnly={readOnly}
                    required={f.required}
                    onChange={(v) => {
                      const next = [...items];
                      next[index] = { ...item, [f.key]: v };
                      onChange(next);
                    }}
                  />
                ),
              )}
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

function reconcileIntakeDraftPayload(payload: IntakeDraftPayload): IntakeDraftPayload {
  const military = {
    ...emptyIntakeDraftPayload().military,
    ...payload.military,
    specialty_name: payload.military?.specialty_name ?? "",
  };
  return {
    ...payload,
    military: reconcileIntakeMilitaryDraftOnLoad(military),
  };
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
  const composition = normalizeIntakeMilitaryComposition(m.composition);
  const rankOptions = React.useMemo(
    () => getIntakeMilitaryRankOptions(composition),
    [composition],
  );
  const set = (key: keyof typeof m, value: string) =>
    onChange({ ...payload, military: { ...m, [key]: value } });

  return (
    <div className="grid gap-4 sm:grid-cols-2">
      <IntakeMilitaryCombobox
        label="Состав"
        value={composition}
        onChange={(nextComposition) =>
          onChange({
            ...payload,
            military: {
              ...m,
              ...applyIntakeMilitaryCompositionChange(nextComposition, m.rank),
            },
          })
        }
        options={INTAKE_MILITARY_COMPOSITION_CATALOG}
        readOnly={readOnly}
        testId="intake-military-composition"
      />
      <IntakeMilitaryCombobox
        label="Воинское звание"
        value={m.rank}
        onChange={(v) => set("rank", v)}
        options={rankOptions}
        readOnly={readOnly}
        disabled={!composition}
        allowFreeText={composition === "other"}
        testId="intake-military-rank"
      />
      <Field label="Статус" value={m.status} onChange={(v) => set("status", v)} readOnly={readOnly} />
      <Field label="Категория" value={m.category} onChange={(v) => set("category", v)} readOnly={readOnly} />
      <Field
        label="Номер ВУС"
        value={m.specialty_code}
        onChange={(v) => set("specialty_code", sanitizeMilitarySpecialtyCodeInput(v))}
        readOnly={readOnly}
        testId="intake-military-specialty-code"
        maxLength={7}
        inputMode="numeric"
      />
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
        setPayload(reconcileIntakeDraftPayload(session.payload ?? emptyIntakeDraftPayload()));
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
          <h1 className="text-2xl font-semibold text-zinc-900 dark:text-zinc-50">
            Анкета сотрудника. Шаг {stepIndex + 1} из {INTAKE_STEPS.length} – {currentStep.title}
          </h1>
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
            <CardListStep<IntakeEducation>
              title="образование"
              items={payload.education}
              emptyItem={{
                education_type: "basic",
                institution: "",
                year_from: "",
                year_to: "",
                specialty: "",
                qualification: "",
                diploma_number: "",
              }}
              fields={[
                {
                  key: "education_type",
                  label: "Вид образования",
                  required: true,
                  options: INTAKE_EDUCATION_TYPE_OPTIONS,
                },
                { key: "institution", label: "Учебное заведение" },
                {
                  key: "year_from",
                  label: "Год поступления",
                  periodPrecision: "year",
                  testId: "intake-education-year-from",
                },
                {
                  key: "year_to",
                  label: "Год окончания",
                  periodPrecision: "year",
                  testId: "intake-education-year-to",
                },
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
              emptyItem={{ institution: "", year: "", course_name: "", hours: "" }}
              fields={[
                { key: "institution", label: "Организация" },
                { key: "year", label: "Год", periodPrecision: "year", testId: "intake-training-year" },
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
                { key: "birth_year", label: "Год рождения", periodPrecision: "year", testId: "intake-relative-birth-year" },
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
                { key: "year_from", label: "С", periodPrecision: "year", testId: "intake-employment-year-from" },
                { key: "year_to", label: "По", periodPrecision: "year", testId: "intake-employment-year-to" },
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
            <div className="space-y-3 text-sm text-zinc-700 dark:text-zinc-300" data-testid="intake-review-summary">
              <p>Проверьте введённые сведения перед отправкой в отдел кадров.</p>
              <ul className="list-disc space-y-1 pl-5">
                <li>ФИО: {formatIntakeFullName(payload.personal) || "—"}</li>
                <li>Дата рождения: {formatPersonnelDate(payload.personal.birth_date, { precision: "day", empty: "—" })}</li>
                <li>Телефон: {payload.contacts.mobile_phone || "—"}</li>
                <li>Email: {payload.contacts.email || "—"}</li>
                <li>
                  Образование:{" "}
                  {payload.education.length === 0
                    ? "0 зап."
                    : payload.education.map((item, index) => (
                        <span key={`education-${index}`} data-testid={`intake-review-education-${index}`}>
                          {index > 0 ? "; " : ""}
                          {formatIntakeEducationReviewLine(item)}
                        </span>
                      ))}
                </li>
                <li>
                  Обучение:{" "}
                  {payload.training.length === 0
                    ? "0 зап."
                    : payload.training.map((item, index) => (
                        <span key={`training-${index}`} data-testid={`intake-review-training-${index}`}>
                          {index > 0 ? "; " : ""}
                          {formatIntakeTrainingReviewLine(item)}
                        </span>
                      ))}
                </li>
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
