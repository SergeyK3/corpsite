"use client";

import * as React from "react";

import {
  createMilitaryService,
  newPprCommandId,
  supersedeMilitaryService,
  voidMilitaryService,
  type PprMilitaryServiceRoute,
} from "../_lib/pprCommandApi.client";
import {
  formatPprDate,
  isPprDisplayValue,
  mapPprMutationError,
  militaryRecordKindLabel,
  obligationStatusLabel,
  personnelCompositionLabel,
  registrationStatusLabel,
} from "../_lib/pprCardPresentation";
import {
  buildMilitaryServiceRecordPayload,
  isStaleMutationError,
  validateMilitaryServiceFormForSubmit,
  type MilitaryServiceFormState,
} from "../_lib/pprMilitaryServiceForm";
import type {
  PprMilitaryRecordDetailsResponse,
  PprMilitaryRecordResponse,
} from "../_lib/pprQueryTypes";
import {
  PPR_MILITARY_RECORD_KIND_NOT_APPLICABLE,
  PPR_MILITARY_RECORD_KIND_REGISTRATION,
} from "../_lib/pprQueryTypes";

type Props = {
  active: PprMilitaryRecordResponse[];
  superseded: PprMilitaryRecordResponse[];
  voided: PprMilitaryRecordResponse[];
  route: PprMilitaryServiceRoute;
  editable?: boolean;
  onMutated?: () => void | Promise<void>;
};

type RecordFormState = MilitaryServiceFormState;

const EMPTY_FORM: RecordFormState = {
  record_kind: PPR_MILITARY_RECORD_KIND_REGISTRATION,
  obligation_status: "",
  registration_category: "",
  military_rank: "",
  military_specialty_code: "",
  personnel_composition: "",
  fitness_category: "",
  registration_status: "",
  commissariat_name: "",
  registered_at: "",
  deregistered_at: "",
  military_id_book_series: "",
  military_id_book_number: "",
  registration_certificate_series: "",
  registration_certificate_number: "",
  notes: "",
};

const RESTRICTED_FIELD_SPECS = [
  { key: "military_id_book_series", label: "Серия военного билета" },
  { key: "military_id_book_number", label: "Номер военного билета" },
  { key: "registration_certificate_series", label: "Серия справки" },
  { key: "registration_certificate_number", label: "Номер справки" },
] as const;

function StaleRefreshAction({
  testId,
  onRefresh,
}: {
  testId: string;
  onRefresh?: () => void | Promise<void>;
}) {
  if (!onRefresh) return null;
  return (
    <button
      type="button"
      className="mt-2 text-sm underline-offset-2 hover:underline"
      onClick={() => void onRefresh()}
      data-testid={testId}
    >
      Обновить данные
    </button>
  );
}

function restrictedFieldValue(
  record: PprMilitaryRecordResponse,
  key: (typeof RESTRICTED_FIELD_SPECS)[number]["key"],
): string | null | undefined {
  if (!(key in record)) return undefined;
  return (record as PprMilitaryRecordDetailsResponse)[key];
}

function MilitaryRecordCard({ record }: { record: PprMilitaryRecordResponse }) {
  const title =
    record.record_kind === PPR_MILITARY_RECORD_KIND_REGISTRATION
      ? record.military_rank || militaryRecordKindLabel(record.record_kind)
      : militaryRecordKindLabel(record.record_kind);

  const fieldRows: Array<{ label: string; value: string }> = [];

  const pushField = (label: string, value: string | null | undefined, formatter?: (v: string) => string) => {
    if (!isPprDisplayValue(value)) return;
    fieldRows.push({ label, value: formatter ? formatter(value as string) : (value as string) });
  };

  pushField("Вид", record.record_kind, militaryRecordKindLabel);
  pushField("Воинская обязанность", record.obligation_status, obligationStatusLabel);
  pushField("Категория учёта", record.registration_category);
  pushField("Воинское звание", record.military_rank);
  pushField("ВУС", record.military_specialty_code);
  pushField("Состав", record.personnel_composition, personnelCompositionLabel);
  pushField("Категория годности", record.fitness_category);
  pushField("Статус учёта", record.registration_status, registrationStatusLabel);
  pushField("Военкомат", record.commissariat_name);
  pushField("Дата постановки на учёт", record.registered_at, formatPprDate);
  pushField("Дата снятия с учёта", record.deregistered_at, formatPprDate);

  for (const spec of RESTRICTED_FIELD_SPECS) {
    pushField(spec.label, restrictedFieldValue(record, spec.key));
  }

  pushField("Примечание", record.notes);
  pushField("Статус", record.lifecycle_status);

  return (
    <div
      className="rounded-lg border border-zinc-200 px-3 py-2 text-sm dark:border-zinc-800"
      data-testid={`military-record-${record.record_id ?? "unknown"}`}
    >
      <div className="font-medium text-zinc-900 dark:text-zinc-50">{title}</div>
      {fieldRows.length > 0 ? (
        <dl className="mt-2 grid gap-1 text-xs text-zinc-600 dark:text-zinc-400 sm:grid-cols-2">
          {fieldRows.map((row) => (
            <div key={`${record.record_id ?? "unknown"}-${row.label}`}>
              <dt className="inline">{row.label}: </dt>
              <dd className="inline">{row.value}</dd>
            </div>
          ))}
        </dl>
      ) : null}
    </div>
  );
}

function CollapsibleGroup({
  title,
  records,
  defaultOpen = false,
}: {
  title: string;
  records: PprMilitaryRecordResponse[];
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = React.useState(defaultOpen);
  if (records.length === 0) return null;
  return (
    <div className="space-y-2">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="text-sm font-medium text-zinc-700 underline-offset-2 hover:underline dark:text-zinc-300"
        aria-expanded={open}
      >
        {title} ({records.length})
      </button>
      {open ? (
        <div className="space-y-2">
          {records.map((record) => (
            <MilitaryRecordCard
              key={record.record_id ?? `${record.record_kind}-${record.notes}-${record.military_rank}`}
              record={record}
            />
          ))}
        </div>
      ) : null}
    </div>
  );
}

function RecordFormFields({
  form,
  onChange,
}: {
  form: RecordFormState;
  onChange: (next: RecordFormState) => void;
}) {
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      <label className="block text-sm sm:col-span-2">
        <span className="mb-1 block text-zinc-700 dark:text-zinc-300">Вид записи</span>
        <select
          className="w-full rounded border border-zinc-300 px-2 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-950"
          value={form.record_kind}
          onChange={(e) => onChange({ ...form, record_kind: e.target.value })}
          data-testid="military-form-kind"
        >
          <option value={PPR_MILITARY_RECORD_KIND_REGISTRATION}>Сведения о воинском учёте</option>
          <option value={PPR_MILITARY_RECORD_KIND_NOT_APPLICABLE}>Не подлежит воинскому учёту</option>
        </select>
      </label>

      {form.record_kind === PPR_MILITARY_RECORD_KIND_REGISTRATION ? (
        <>
          <label className="block text-sm">
            <span className="mb-1 block">Воинская обязанность</span>
            <select
              className="w-full rounded border border-zinc-300 px-2 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-950"
              value={form.obligation_status}
              onChange={(e) => onChange({ ...form, obligation_status: e.target.value })}
              data-testid="military-form-obligation"
            >
              <option value="">—</option>
              <option value="liable">Военнообязанный</option>
              <option value="not_liable">Не военнообязанный</option>
              <option value="exempt">Освобождён</option>
              <option value="unknown">Не определено</option>
            </select>
          </label>
          <label className="block text-sm">
            <span className="mb-1 block">Категория учёта</span>
            <select
              className="w-full rounded border border-zinc-300 px-2 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-950"
              value={form.registration_category}
              onChange={(e) => onChange({ ...form, registration_category: e.target.value })}
              data-testid="military-form-category"
            >
              <option value="">—</option>
              <option value="I">I</option>
              <option value="II">II</option>
              <option value="III">III</option>
              <option value="IV">IV</option>
              <option value="V">V</option>
              <option value="other">Иная</option>
            </select>
          </label>
          <label className="block text-sm">
            <span className="mb-1 block">Воинское звание</span>
            <input
              className="w-full rounded border border-zinc-300 px-2 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-950"
              value={form.military_rank}
              onChange={(e) => onChange({ ...form, military_rank: e.target.value })}
              data-testid="military-form-rank"
            />
          </label>
          <label className="block text-sm">
            <span className="mb-1 block">Статус учёта</span>
            <select
              className="w-full rounded border border-zinc-300 px-2 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-950"
              value={form.registration_status}
              onChange={(e) => onChange({ ...form, registration_status: e.target.value })}
              data-testid="military-form-status"
            >
              <option value="">—</option>
              <option value="registered">Состоит на учёте</option>
              <option value="deregistered">Снят с учёта</option>
              <option value="reserved">В запасе</option>
              <option value="deferment">Отсрочка</option>
              <option value="unknown">Не определено</option>
            </select>
          </label>
          <label className="block text-sm">
            <span className="mb-1 block">ВУС</span>
            <input
              className="w-full rounded border border-zinc-300 px-2 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-950"
              value={form.military_specialty_code}
              onChange={(e) => onChange({ ...form, military_specialty_code: e.target.value })}
            />
          </label>
          <label className="block text-sm">
            <span className="mb-1 block">Состав</span>
            <select
              className="w-full rounded border border-zinc-300 px-2 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-950"
              value={form.personnel_composition}
              onChange={(e) => onChange({ ...form, personnel_composition: e.target.value })}
            >
              <option value="">—</option>
              <option value="soldiers">Рядовой и сержантский состав</option>
              <option value="sergeants">Сержантский состав</option>
              <option value="officers">Офицерский состав</option>
              <option value="other">Иной состав</option>
            </select>
          </label>
          <label className="block text-sm">
            <span className="mb-1 block">Категория годности</span>
            <input
              className="w-full rounded border border-zinc-300 px-2 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-950"
              value={form.fitness_category}
              onChange={(e) => onChange({ ...form, fitness_category: e.target.value })}
            />
          </label>
          <label className="block text-sm sm:col-span-2">
            <span className="mb-1 block">Военкомат</span>
            <input
              className="w-full rounded border border-zinc-300 px-2 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-950"
              value={form.commissariat_name}
              onChange={(e) => onChange({ ...form, commissariat_name: e.target.value })}
            />
          </label>
          <label className="block text-sm">
            <span className="mb-1 block">Дата постановки на учёт</span>
            <input
              type="date"
              className="w-full rounded border border-zinc-300 px-2 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-950"
              value={form.registered_at}
              onChange={(e) => onChange({ ...form, registered_at: e.target.value })}
              data-testid="military-form-registered"
            />
          </label>
          <label className="block text-sm">
            <span className="mb-1 block">Дата снятия с учёта</span>
            <input
              type="date"
              className="w-full rounded border border-zinc-300 px-2 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-950"
              value={form.deregistered_at}
              onChange={(e) => onChange({ ...form, deregistered_at: e.target.value })}
            />
          </label>
          <label className="block text-sm sm:col-span-2">
            <span className="mb-1 block">Примечание</span>
            <textarea
              className="min-h-16 w-full rounded border border-zinc-300 px-2 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-950"
              value={form.notes}
              onChange={(e) => onChange({ ...form, notes: e.target.value })}
              data-testid="military-form-notes"
            />
          </label>
        </>
      ) : (
        <label className="block text-sm sm:col-span-2">
          <span className="mb-1 block">Примечание (необязательно)</span>
          <textarea
            className="min-h-16 w-full rounded border border-zinc-300 px-2 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-950"
            value={form.notes}
            onChange={(e) => onChange({ ...form, notes: e.target.value })}
            data-testid="military-form-notes"
          />
        </label>
      )}
    </div>
  );
}

export default function PprCardMilitarySection({
  active,
  superseded,
  voided,
  route,
  editable = false,
  onMutated,
}: Props) {
  const [showCreate, setShowCreate] = React.useState(false);
  const [createForm, setCreateForm] = React.useState<RecordFormState>(EMPTY_FORM);
  const [createLoading, setCreateLoading] = React.useState(false);
  const [createError, setCreateError] = React.useState<string | null>(null);
  const [createSuccess, setCreateSuccess] = React.useState<string | null>(null);
  const [createStaleConflict, setCreateStaleConflict] = React.useState(false);

  const [voidTarget, setVoidTarget] = React.useState<PprMilitaryRecordResponse | null>(null);
  const [voidReason, setVoidReason] = React.useState("");
  const [voidLoading, setVoidLoading] = React.useState(false);
  const [voidError, setVoidError] = React.useState<string | null>(null);
  const [voidStaleConflict, setVoidStaleConflict] = React.useState(false);

  const [supersedeTarget, setSupersedeTarget] = React.useState<PprMilitaryRecordResponse | null>(null);
  const [supersedeForm, setSupersedeForm] = React.useState<RecordFormState>(EMPTY_FORM);
  const [supersedeLoading, setSupersedeLoading] = React.useState(false);
  const [supersedeError, setSupersedeError] = React.useState<string | null>(null);
  const [supersedeStaleConflict, setSupersedeStaleConflict] = React.useState(false);

  const createCommandIdRef = React.useRef<string | null>(null);
  const voidCommandIdRef = React.useRef<string | null>(null);
  const supersedeCommandIdRef = React.useRef<string | null>(null);

  async function handleCreateSubmit() {
    if (createLoading) return;
    const validation = validateMilitaryServiceFormForSubmit(createForm);
    if (!validation.ok) {
      setCreateError(validation.message);
      setCreateSuccess(null);
      return;
    }
    setCreateLoading(true);
    setCreateError(null);
    setCreateSuccess(null);
    setCreateStaleConflict(false);
    const commandId = createCommandIdRef.current ?? newPprCommandId();
    createCommandIdRef.current = commandId;
    try {
      await createMilitaryService(route, {
        command_id: commandId,
        record: buildMilitaryServiceRecordPayload(createForm),
      });
      createCommandIdRef.current = null;
      setCreateSuccess("Запись добавлена.");
      setCreateForm(EMPTY_FORM);
      setShowCreate(false);
      await onMutated?.();
    } catch (e) {
      createCommandIdRef.current = null;
      setCreateStaleConflict(isStaleMutationError(e));
      setCreateError(mapPprMutationError(e));
    } finally {
      setCreateLoading(false);
    }
  }

  async function handleVoidSubmit() {
    if (voidLoading || !voidTarget?.record_id || !voidTarget.updated_at) return;
    setVoidLoading(true);
    setVoidError(null);
    setVoidStaleConflict(false);
    const commandId = voidCommandIdRef.current ?? newPprCommandId();
    voidCommandIdRef.current = commandId;
    try {
      await voidMilitaryService(route, voidTarget.record_id, {
        command_id: commandId,
        reason: voidReason.trim(),
        expected_updated_at: voidTarget.updated_at,
      });
      voidCommandIdRef.current = null;
      setVoidTarget(null);
      setVoidReason("");
      await onMutated?.();
    } catch (e) {
      voidCommandIdRef.current = null;
      setVoidStaleConflict(isStaleMutationError(e));
      setVoidError(mapPprMutationError(e));
    } finally {
      setVoidLoading(false);
    }
  }

  async function handleSupersedeSubmit() {
    if (supersedeLoading || !supersedeTarget?.record_id || !supersedeTarget.updated_at) return;
    const validation = validateMilitaryServiceFormForSubmit(supersedeForm);
    if (!validation.ok) {
      setSupersedeError(validation.message);
      return;
    }
    setSupersedeLoading(true);
    setSupersedeError(null);
    setSupersedeStaleConflict(false);
    const commandId = supersedeCommandIdRef.current ?? newPprCommandId();
    supersedeCommandIdRef.current = commandId;
    try {
      await supersedeMilitaryService(route, supersedeTarget.record_id, {
        command_id: commandId,
        expected_updated_at: supersedeTarget.updated_at,
        replacement: buildMilitaryServiceRecordPayload(supersedeForm),
      });
      supersedeCommandIdRef.current = null;
      setSupersedeTarget(null);
      setSupersedeForm(EMPTY_FORM);
      await onMutated?.();
    } catch (e) {
      supersedeCommandIdRef.current = null;
      setSupersedeStaleConflict(isStaleMutationError(e));
      setSupersedeError(mapPprMutationError(e));
    } finally {
      setSupersedeLoading(false);
    }
  }

  if (active.length === 0 && superseded.length === 0 && voided.length === 0 && !showCreate) {
    return (
      <div className="space-y-3" data-testid="military-empty">
        <p className="text-sm text-zinc-500">Сведения о воинском учёте отсутствуют.</p>
        {editable ? (
          <button
            type="button"
            className="rounded border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-700"
            onClick={() => setShowCreate(true)}
            data-testid="military-create-btn"
          >
            Добавить
          </button>
        ) : null}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {editable ? (
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            className="rounded border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-700"
            onClick={() => {
              setShowCreate((v) => !v);
              setCreateError(null);
              setCreateSuccess(null);
            }}
            data-testid="military-create-btn"
          >
            {showCreate ? "Скрыть форму" : "Добавить"}
          </button>
        </div>
      ) : null}

      {showCreate && editable ? (
        <div className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-800" data-testid="military-create-form">
          <RecordFormFields form={createForm} onChange={setCreateForm} />
          {createError ? (
            <p className="mt-2 text-sm text-red-600 dark:text-red-400" data-testid="military-create-error">
              {createError}
            </p>
          ) : null}
          {createStaleConflict ? (
            <StaleRefreshAction testId="military-create-refresh" onRefresh={onMutated} />
          ) : null}
          {createSuccess ? (
            <p className="mt-2 text-sm text-green-700 dark:text-green-400" data-testid="military-create-success">
              {createSuccess}
            </p>
          ) : null}
          <div className="mt-3 flex gap-2">
            <button
              type="button"
              className="rounded border border-zinc-900 bg-zinc-900 px-3 py-1.5 text-sm text-white disabled:opacity-50 dark:border-zinc-100 dark:bg-zinc-100 dark:text-zinc-900"
              disabled={createLoading}
              onClick={() => void handleCreateSubmit()}
              data-testid="military-create-submit"
            >
              {createLoading ? "Сохранение…" : "Сохранить"}
            </button>
          </div>
        </div>
      ) : null}

      <div className="space-y-2">
        <h3 className="text-sm font-semibold text-zinc-800 dark:text-zinc-200">Действующая запись</h3>
        {active.length === 0 ? (
          <p className="text-sm text-zinc-500">Нет действующей записи.</p>
        ) : (
          active.map((record) => (
            <div key={record.record_id ?? record.military_rank} className="space-y-2">
              <MilitaryRecordCard record={record} />
              {editable && record.record_id != null ? (
                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    className="rounded border border-zinc-300 px-2 py-1 text-xs dark:border-zinc-700"
                    onClick={() => {
                      setSupersedeTarget(record);
                      setSupersedeForm(EMPTY_FORM);
                      setSupersedeError(null);
                    }}
                    data-testid={`military-supersede-btn-${record.record_id}`}
                  >
                    Заменить
                  </button>
                  <button
                    type="button"
                    className="rounded border border-zinc-300 px-2 py-1 text-xs dark:border-zinc-700"
                    onClick={() => {
                      setVoidTarget(record);
                      setVoidReason("");
                      setVoidError(null);
                    }}
                    data-testid={`military-void-btn-${record.record_id}`}
                  >
                    Аннулировать
                  </button>
                </div>
              ) : null}
            </div>
          ))
        )}
      </div>

      <CollapsibleGroup title="История замен" records={superseded} />
      <CollapsibleGroup title="Аннулированные записи" records={voided} />

      {voidTarget ? (
        <div
          className="rounded-lg border border-amber-200 bg-amber-50 p-3 dark:border-amber-900/50 dark:bg-amber-950/20"
          data-testid="military-void-form"
        >
          <p className="text-sm font-medium">Аннулирование записи #{voidTarget.record_id}</p>
          <label className="mt-2 block text-sm">
            <span className="mb-1 block">Причина</span>
            <input
              className="w-full rounded border border-zinc-300 px-2 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-950"
              value={voidReason}
              onChange={(e) => setVoidReason(e.target.value)}
              data-testid="military-void-reason"
            />
          </label>
          {voidError ? (
            <p className="mt-2 text-sm text-red-600 dark:text-red-400" data-testid="military-void-error">
              {voidError}
            </p>
          ) : null}
          {voidStaleConflict ? (
            <StaleRefreshAction testId="military-void-refresh" onRefresh={onMutated} />
          ) : null}
          <div className="mt-3 flex gap-2">
            <button
              type="button"
              className="rounded border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-700"
              disabled={voidLoading || !voidReason.trim()}
              onClick={() => void handleVoidSubmit()}
              data-testid="military-void-submit"
            >
              {voidLoading ? "Аннулирование…" : "Подтвердить"}
            </button>
            <button
              type="button"
              className="rounded border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-700"
              onClick={() => setVoidTarget(null)}
            >
              Отмена
            </button>
          </div>
        </div>
      ) : null}

      {supersedeTarget ? (
        <div
          className="rounded-lg border border-blue-200 bg-blue-50 p-3 dark:border-blue-900/50 dark:bg-blue-950/20"
          data-testid="military-supersede-form"
        >
          <p className="text-sm font-medium">Замена записи #{supersedeTarget.record_id}</p>
          <div className="mt-2">
            <RecordFormFields form={supersedeForm} onChange={setSupersedeForm} />
          </div>
          {supersedeError ? (
            <p className="mt-2 text-sm text-red-600 dark:text-red-400" data-testid="military-supersede-error">
              {supersedeError}
            </p>
          ) : null}
          {supersedeStaleConflict ? (
            <StaleRefreshAction testId="military-supersede-refresh" onRefresh={onMutated} />
          ) : null}
          <div className="mt-3 flex gap-2">
            <button
              type="button"
              className="rounded border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-700"
              disabled={supersedeLoading}
              onClick={() => void handleSupersedeSubmit()}
              data-testid="military-supersede-submit"
            >
              {supersedeLoading ? "Замена…" : "Заменить запись"}
            </button>
            <button
              type="button"
              className="rounded border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-700"
              onClick={() => setSupersedeTarget(null)}
            >
              Отмена
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
