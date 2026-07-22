"use client";

import * as React from "react";

import {
  createExternalEmployment,
  newPprCommandId,
  supersedeExternalEmployment,
  voidExternalEmployment,
  type PprEmploymentBiographyRoute,
} from "../_lib/pprCommandApi.client";
import { formatPersonnelDateRange } from "@/lib/personnelDateFormat";
import {
  externalEmploymentRecordKindLabel,
  mapPprMutationError,
} from "../_lib/pprCardPresentation";
import {
  buildExternalEmploymentRecordPayload,
  isStaleMutationError,
  validateExternalEmploymentFormForSubmit,
  type EmploymentBiographyFormState,
} from "../_lib/pprEmploymentBiographyForm";
import type { PprExternalEmploymentRecordResponse } from "../_lib/pprQueryTypes";
import {
  PPR_EXTERNAL_EMPLOYMENT_RECORD_KIND_ATTESTATION_NONE,
  PPR_EXTERNAL_EMPLOYMENT_RECORD_KIND_EPISODE,
  PPR_EXTERNAL_EMPLOYMENT_RECORD_KIND_NARRATIVE_SUMMARY,
} from "../_lib/pprQueryTypes";

type Props = {
  active: PprExternalEmploymentRecordResponse[];
  superseded: PprExternalEmploymentRecordResponse[];
  voided: PprExternalEmploymentRecordResponse[];
  route: PprEmploymentBiographyRoute;
  editable?: boolean;
  onMutated?: () => void | Promise<void>;
};

type RecordFormState = EmploymentBiographyFormState;

const EMPTY_FORM: RecordFormState = {
  record_kind: PPR_EXTERNAL_EMPLOYMENT_RECORD_KIND_EPISODE,
  employer_name: "",
  department_name: "",
  position_title: "",
  started_at: "",
  ended_at: "",
  notes: "",
};

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

function EmploymentRecordCard({ record }: { record: PprExternalEmploymentRecordResponse }) {
  const title =
    record.record_kind === PPR_EXTERNAL_EMPLOYMENT_RECORD_KIND_EPISODE
      ? record.employer_name || "Работодатель не указан"
      : externalEmploymentRecordKindLabel(record.record_kind);

  return (
    <div
      className="rounded-lg border border-zinc-200 px-3 py-2 text-sm dark:border-zinc-800"
      data-testid={`emp-bio-record-${record.record_id ?? "unknown"}`}
    >
      <div className="font-medium text-zinc-900 dark:text-zinc-50">{title}</div>
      <dl className="mt-2 grid gap-1 text-xs text-zinc-600 dark:text-zinc-400 sm:grid-cols-2">
        <div>
          <dt className="inline">Вид: </dt>
          <dd className="inline">{externalEmploymentRecordKindLabel(record.record_kind)}</dd>
        </div>
        {record.position_title ? (
          <div>
            <dt className="inline">Должность: </dt>
            <dd className="inline">{record.position_title}</dd>
          </div>
        ) : null}
        {record.department_name ? (
          <div>
            <dt className="inline">Подразделение: </dt>
            <dd className="inline">{record.department_name}</dd>
          </div>
        ) : null}
        {record.record_kind === PPR_EXTERNAL_EMPLOYMENT_RECORD_KIND_EPISODE ? (
          <div>
            <dt className="inline">Период: </dt>
            <dd className="inline">
              {formatPersonnelDateRange(record.started_at, record.ended_at, { precision: "year" })}
            </dd>
          </div>
        ) : null}
        {record.notes ? (
          <div className="sm:col-span-2">
            <dt className="inline">Примечание: </dt>
            <dd className="inline">{record.notes}</dd>
          </div>
        ) : null}
        <div>
          <dt className="inline">Статус: </dt>
          <dd className="inline">{record.lifecycle_status}</dd>
        </div>
      </dl>
    </div>
  );
}

function CollapsibleGroup({
  title,
  records,
  defaultOpen = false,
}: {
  title: string;
  records: PprExternalEmploymentRecordResponse[];
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
            <EmploymentRecordCard
              key={record.record_id ?? `${record.record_kind}-${record.notes}-${record.employer_name}`}
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
          data-testid="emp-bio-form-kind"
        >
          <option value={PPR_EXTERNAL_EMPLOYMENT_RECORD_KIND_EPISODE}>Эпизод</option>
          <option value={PPR_EXTERNAL_EMPLOYMENT_RECORD_KIND_NARRATIVE_SUMMARY}>Сводная запись</option>
          <option value={PPR_EXTERNAL_EMPLOYMENT_RECORD_KIND_ATTESTATION_NONE}>Нет стажа</option>
        </select>
      </label>

      {form.record_kind === PPR_EXTERNAL_EMPLOYMENT_RECORD_KIND_EPISODE ? (
        <>
          <label className="block text-sm sm:col-span-2">
            <span className="mb-1 block">Работодатель</span>
            <input
              className="w-full rounded border border-zinc-300 px-2 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-950"
              value={form.employer_name}
              onChange={(e) => onChange({ ...form, employer_name: e.target.value })}
              data-testid="emp-bio-form-employer"
            />
          </label>
          <label className="block text-sm">
            <span className="mb-1 block">Должность</span>
            <input
              className="w-full rounded border border-zinc-300 px-2 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-950"
              value={form.position_title}
              onChange={(e) => onChange({ ...form, position_title: e.target.value })}
              data-testid="emp-bio-form-position"
            />
          </label>
          <label className="block text-sm">
            <span className="mb-1 block">Подразделение</span>
            <input
              className="w-full rounded border border-zinc-300 px-2 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-950"
              value={form.department_name}
              onChange={(e) => onChange({ ...form, department_name: e.target.value })}
            />
          </label>
          <label className="block text-sm">
            <span className="mb-1 block">Начало</span>
            <input
              type="date"
              className="w-full rounded border border-zinc-300 px-2 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-950"
              value={form.started_at}
              onChange={(e) => onChange({ ...form, started_at: e.target.value })}
              data-testid="emp-bio-form-started"
            />
          </label>
          <label className="block text-sm">
            <span className="mb-1 block">Окончание</span>
            <input
              type="date"
              className="w-full rounded border border-zinc-300 px-2 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-950"
              value={form.ended_at}
              onChange={(e) => onChange({ ...form, ended_at: e.target.value })}
            />
          </label>
        </>
      ) : form.record_kind === PPR_EXTERNAL_EMPLOYMENT_RECORD_KIND_NARRATIVE_SUMMARY ? (
        <label className="block text-sm sm:col-span-2">
          <span className="mb-1 block">Текст записи *</span>
          <textarea
            className="min-h-20 w-full rounded border border-zinc-300 px-2 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-950"
            value={form.notes}
            onChange={(e) => onChange({ ...form, notes: e.target.value })}
            data-testid="emp-bio-form-notes"
          />
        </label>
      ) : (
        <label className="block text-sm sm:col-span-2">
          <span className="mb-1 block">Примечание (необязательно)</span>
          <textarea
            className="min-h-20 w-full rounded border border-zinc-300 px-2 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-950"
            value={form.notes}
            onChange={(e) => onChange({ ...form, notes: e.target.value })}
            data-testid="emp-bio-form-notes"
          />
        </label>
      )}
    </div>
  );
}

export default function PprCardEmploymentBiographySection({
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

  const [voidTarget, setVoidTarget] = React.useState<PprExternalEmploymentRecordResponse | null>(null);
  const [voidReason, setVoidReason] = React.useState("");
  const [voidLoading, setVoidLoading] = React.useState(false);
  const [voidError, setVoidError] = React.useState<string | null>(null);
  const [voidStaleConflict, setVoidStaleConflict] = React.useState(false);

  const [supersedeTarget, setSupersedeTarget] = React.useState<PprExternalEmploymentRecordResponse | null>(
    null,
  );
  const [supersedeForm, setSupersedeForm] = React.useState<RecordFormState>(EMPTY_FORM);
  const [supersedeLoading, setSupersedeLoading] = React.useState(false);
  const [supersedeError, setSupersedeError] = React.useState<string | null>(null);
  const [supersedeStaleConflict, setSupersedeStaleConflict] = React.useState(false);

  const createCommandIdRef = React.useRef<string | null>(null);
  const voidCommandIdRef = React.useRef<string | null>(null);
  const supersedeCommandIdRef = React.useRef<string | null>(null);

  async function handleCreateSubmit() {
    if (createLoading) return;
    const validation = validateExternalEmploymentFormForSubmit(createForm);
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
      await createExternalEmployment(route, {
        command_id: commandId,
        record: buildExternalEmploymentRecordPayload(createForm),
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
      await voidExternalEmployment(route, voidTarget.record_id, {
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
    const validation = validateExternalEmploymentFormForSubmit(supersedeForm);
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
      await supersedeExternalEmployment(route, supersedeTarget.record_id, {
        command_id: commandId,
        expected_updated_at: supersedeTarget.updated_at,
        replacement: buildExternalEmploymentRecordPayload(supersedeForm),
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
      <div className="space-y-3" data-testid="emp-bio-empty">
        <p className="text-sm text-zinc-500">Записи трудовой биографии отсутствуют.</p>
        {editable ? (
          <button
            type="button"
            className="rounded border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-700"
            onClick={() => setShowCreate(true)}
            data-testid="emp-bio-create-btn"
          >
            Добавить запись
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
            data-testid="emp-bio-create-btn"
          >
            {showCreate ? "Скрыть форму" : "Добавить запись"}
          </button>
        </div>
      ) : null}

      {showCreate && editable ? (
        <div className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-800" data-testid="emp-bio-create-form">
          <RecordFormFields form={createForm} onChange={setCreateForm} />
          {createError ? (
            <p className="mt-2 text-sm text-red-600 dark:text-red-400" data-testid="emp-bio-create-error">
              {createError}
            </p>
          ) : null}
          {createStaleConflict ? (
            <StaleRefreshAction testId="emp-bio-create-refresh" onRefresh={onMutated} />
          ) : null}
          {createSuccess ? (
            <p className="mt-2 text-sm text-green-700 dark:text-green-400" data-testid="emp-bio-create-success">
              {createSuccess}
            </p>
          ) : null}
          <div className="mt-3 flex gap-2">
            <button
              type="button"
              className="rounded border border-zinc-900 bg-zinc-900 px-3 py-1.5 text-sm text-white disabled:opacity-50 dark:border-zinc-100 dark:bg-zinc-100 dark:text-zinc-900"
              disabled={createLoading}
              onClick={() => void handleCreateSubmit()}
              data-testid="emp-bio-create-submit"
            >
              {createLoading ? "Сохранение…" : "Сохранить"}
            </button>
          </div>
        </div>
      ) : null}

      <div className="space-y-2">
        <h3 className="text-sm font-semibold text-zinc-800 dark:text-zinc-200">Действующие записи</h3>
        {active.length === 0 ? (
          <p className="text-sm text-zinc-500">Нет действующих записей.</p>
        ) : (
          active.map((record) => (
            <div key={record.record_id ?? record.employer_name} className="space-y-2">
              <EmploymentRecordCard record={record} />
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
                    data-testid={`emp-bio-supersede-btn-${record.record_id}`}
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
                    data-testid={`emp-bio-void-btn-${record.record_id}`}
                  >
                    Аннулировать
                  </button>
                </div>
              ) : null}
            </div>
          ))
        )}
      </div>

      <CollapsibleGroup title="Заменённые записи" records={superseded} />
      <CollapsibleGroup title="Аннулированные записи" records={voided} />

      {voidTarget ? (
        <div
          className="rounded-lg border border-amber-200 bg-amber-50 p-3 dark:border-amber-900/50 dark:bg-amber-950/20"
          data-testid="emp-bio-void-form"
        >
          <p className="text-sm font-medium">Аннулирование записи #{voidTarget.record_id}</p>
          <label className="mt-2 block text-sm">
            <span className="mb-1 block">Причина</span>
            <input
              className="w-full rounded border border-zinc-300 px-2 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-950"
              value={voidReason}
              onChange={(e) => setVoidReason(e.target.value)}
              data-testid="emp-bio-void-reason"
            />
          </label>
          {voidError ? (
            <p className="mt-2 text-sm text-red-600 dark:text-red-400" data-testid="emp-bio-void-error">
              {voidError}
            </p>
          ) : null}
          {voidStaleConflict ? (
            <StaleRefreshAction testId="emp-bio-void-refresh" onRefresh={onMutated} />
          ) : null}
          <div className="mt-3 flex gap-2">
            <button
              type="button"
              className="rounded border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-700"
              disabled={voidLoading || !voidReason.trim()}
              onClick={() => void handleVoidSubmit()}
              data-testid="emp-bio-void-submit"
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
          data-testid="emp-bio-supersede-form"
        >
          <p className="text-sm font-medium">Замена записи #{supersedeTarget.record_id}</p>
          <div className="mt-2">
            <RecordFormFields form={supersedeForm} onChange={setSupersedeForm} />
          </div>
          {supersedeError ? (
            <p className="mt-2 text-sm text-red-600 dark:text-red-400" data-testid="emp-bio-supersede-error">
              {supersedeError}
            </p>
          ) : null}
          {supersedeStaleConflict ? (
            <StaleRefreshAction testId="emp-bio-supersede-refresh" onRefresh={onMutated} />
          ) : null}
          <div className="mt-3 flex gap-2">
            <button
              type="button"
              className="rounded border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-700"
              disabled={supersedeLoading}
              onClick={() => void handleSupersedeSubmit()}
              data-testid="emp-bio-supersede-submit"
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
