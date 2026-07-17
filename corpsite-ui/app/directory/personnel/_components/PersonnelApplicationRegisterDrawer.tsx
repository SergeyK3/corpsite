"use client";

import * as React from "react";

import OrgScopeFilter from "@/components/OrgScopeFilter";
import OrgUnitScopeFilter from "@/components/OrgUnitScopeFilter";
import { hrRelationshipLabel } from "../_lib/pprCardPresentation";
import {
  mapPersonnelApplicationBlockReason,
  formatPersonnelApplicationDate,
} from "../_lib/personnelApplicationLabels";
import {
  mapPersonnelApplicationsApiError,
  previewPersonnelApplication,
  registerPersonnelApplication,
  PERSONNEL_APPLICATIONS_BASE_PATH,
  type PersonnelApplicationPreviewResponse,
  type PersonnelApplicationRegisterResponse,
} from "../_lib/personnelApplicationsApi.client";
import { usePersonnelOrderPositionOptions } from "@/lib/usePersonnelOrderPositionOptions";
import type { PersonnelOrderPositionSelectGroup } from "@/lib/taskOrgFilters";

type Props = {
  open: boolean;
  onClose: () => void;
  onRegistered: (result: PersonnelApplicationRegisterResponse) => void;
  onToast: (message: string, kind?: "success" | "error") => void;
};

function renderPositionSelectOptions(groups: readonly PersonnelOrderPositionSelectGroup[]) {
  if (groups.length === 0) return null;
  return groups.map((group) => (
    <optgroup key={group.key} label={group.label}>
      {group.items.map((position) => (
        <option key={position.id} value={String(position.id)}>
          {position.label}
        </option>
      ))}
    </optgroup>
  ));
}

function todayIsoDate(): string {
  const now = new Date();
  const y = now.getFullYear();
  const m = String(now.getMonth() + 1).padStart(2, "0");
  const d = String(now.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

export default function PersonnelApplicationRegisterDrawer({
  open,
  onClose,
  onRegistered,
  onToast,
}: Props) {
  const [iin, setIin] = React.useState("");
  const [preview, setPreview] = React.useState<PersonnelApplicationPreviewResponse | null>(null);
  const [previewLoading, setPreviewLoading] = React.useState(false);
  const [previewError, setPreviewError] = React.useState<string | null>(null);
  const [submitting, setSubmitting] = React.useState(false);

  const [fullName, setFullName] = React.useState("");
  const [birthDate, setBirthDate] = React.useState("");
  const [applicationReceivedAt, setApplicationReceivedAt] = React.useState(todayIsoDate());
  const [vacancyConfirmed, setVacancyConfirmed] = React.useState(true);
  const [orgGroupId, setOrgGroupId] = React.useState<number | null>(null);
  const [orgUnitId, setOrgUnitId] = React.useState<number | null>(null);
  const [positionId, setPositionId] = React.useState<number | null>(null);
  const [employmentRate, setEmploymentRate] = React.useState("1");
  const [mobilePhone, setMobilePhone] = React.useState("");
  const [email, setEmail] = React.useState("");
  const [hrNote, setHrNote] = React.useState("");

  const { positionGroups, loading: positionsLoading } = usePersonnelOrderPositionOptions({
    enabled: open,
    orgUnitId,
    orgGroupId,
  });

  React.useEffect(() => {
    if (!open) return;
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, onClose]);

  React.useEffect(() => {
    if (!open) {
      setIin("");
      setPreview(null);
      setPreviewError(null);
      setFullName("");
      setBirthDate("");
      setApplicationReceivedAt(todayIsoDate());
      setVacancyConfirmed(true);
      setOrgGroupId(null);
      setOrgUnitId(null);
      setPositionId(null);
      setEmploymentRate("1");
      setMobilePhone("");
      setEmail("");
      setHrNote("");
    }
  }, [open]);

  React.useEffect(() => {
    if (preview?.person_exists && preview.full_name) {
      setFullName(preview.full_name);
    }
  }, [preview]);

  const showRegistrationForm =
    preview != null && preview.can_register && (!preview.person_exists || !preview.has_active_application);

  async function handlePreview() {
    setPreviewLoading(true);
    setPreviewError(null);
    setPreview(null);
    try {
      const result = await previewPersonnelApplication(iin.trim());
      setPreview(result);
      if (!result.can_register && result.block_reason) {
        setPreviewError(mapPersonnelApplicationBlockReason(result.block_reason));
      } else if (result.has_active_application) {
        setPreviewError("У person уже есть активное кадровое обращение.");
      }
    } catch (e) {
      setPreviewError(mapPersonnelApplicationsApiError(e, "Не удалось проверить ИИН"));
    } finally {
      setPreviewLoading(false);
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!showRegistrationForm) return;
    if (!preview?.person_exists && !fullName.trim()) {
      onToast("Укажите ФИО для нового person", "error");
      return;
    }
    if (!vacancyConfirmed) {
      onToast("Для регистрации требуется подтверждение вакансии", "error");
      return;
    }
    setSubmitting(true);
    try {
      const result = await registerPersonnelApplication({
        iin: iin.trim(),
        full_name: fullName.trim() || null,
        birth_date: birthDate.trim() || null,
        application_received_at: applicationReceivedAt,
        vacancy_check_status: "confirmed_visually",
        intended_org_group_id: orgGroupId,
        intended_org_unit_id: orgUnitId,
        intended_position_id: positionId,
        intended_employment_rate: Number(employmentRate) || 1,
        contact_mobile_phone: mobilePhone.trim() || null,
        contact_email: email.trim() || null,
        hr_note: hrNote.trim() || null,
        idempotency_key: `ui-register:${Date.now()}:${iin.trim()}`,
      });
      onRegistered(result);
      onToast(
        result.action === "created" ? "Кадровое обращение зарегистрировано" : "Открыто существующее обращение",
        "success",
      );
      onClose();
    } catch (err) {
      onToast(mapPersonnelApplicationsApiError(err, "Не удалось зарегистрировать обращение"), "error");
    } finally {
      setSubmitting(false);
    }
  }

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex justify-end" data-testid="personnel-application-register-drawer">
      <button type="button" aria-label="Закрыть" className="absolute inset-0 bg-black/30" onClick={onClose} />
      <aside className="relative flex h-full w-full max-w-2xl flex-col border-l border-zinc-200 bg-white shadow-xl dark:border-zinc-800 dark:bg-zinc-950">
        <div className="flex items-start justify-between gap-3 border-b border-zinc-200 px-4 py-4 dark:border-zinc-800">
          <div>
            <h2 className="text-lg font-semibold text-zinc-900 dark:text-zinc-50">Зарегистрировать претендента</h2>
            <p className="mt-1 text-sm text-zinc-500">Регистрация бумажного кадрового обращения</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-700"
          >
            Закрыть
          </button>
        </div>

        <form onSubmit={handleSubmit} className="flex min-h-0 flex-1 flex-col">
          <div className="min-h-0 flex-1 space-y-6 overflow-y-auto px-4 py-4">
            <section className="space-y-3" data-testid="register-drawer-iin-block">
              <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">ИИН</h3>
              <div className="flex flex-wrap gap-2">
                <input
                  value={iin}
                  onChange={(e) => setIin(e.target.value)}
                  placeholder="12 цифр"
                  className="min-w-[14rem] flex-1 rounded-lg border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900"
                  data-testid="register-drawer-iin-input"
                />
                <button
                  type="button"
                  disabled={previewLoading || !iin.trim()}
                  onClick={() => void handlePreview()}
                  className="rounded-lg bg-zinc-900 px-3 py-2 text-sm font-medium text-white hover:bg-zinc-800 disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900"
                  data-testid="register-drawer-preview-button"
                >
                  {previewLoading ? "Проверка…" : "Проверить"}
                </button>
              </div>
              {previewError ? (
                <p className="text-sm text-red-700 dark:text-red-300" data-testid="register-drawer-preview-error">
                  {previewError}
                </p>
              ) : null}
              {preview ? (
                <div
                  className="rounded-lg border border-zinc-200 bg-zinc-50 p-3 text-sm dark:border-zinc-800 dark:bg-zinc-900/40"
                  data-testid="register-drawer-preview-result"
                >
                  <p>
                    Person: {preview.person_exists ? "найден" : "не найден"}
                    {preview.person_id ? ` (#${preview.person_id})` : ""}
                  </p>
                  {preview.full_name ? <p>ФИО: {preview.full_name}</p> : null}
                  {preview.hr_relationship_context ? (
                    <p>Контекст: {hrRelationshipLabel(preview.hr_relationship_context)}</p>
                  ) : null}
                  <p>Активное обращение: {preview.has_active_application ? "да" : "нет"}</p>
                  <p>Активный сотрудник: {preview.has_active_employee ? "да" : "нет"}</p>
                  {!preview.can_register && preview.block_reason ? (
                    <p className="mt-2 text-amber-800 dark:text-amber-200">
                      {mapPersonnelApplicationBlockReason(preview.block_reason)}
                    </p>
                  ) : null}
                </div>
              ) : null}
            </section>

            {showRegistrationForm ? (
              <section className="space-y-4" data-testid="register-drawer-form">
                <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">Основные данные</h3>
                <label className="block space-y-1 text-sm">
                  <span className="text-zinc-600 dark:text-zinc-400">ФИО</span>
                  <input
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                    required={!preview?.person_exists}
                    className="w-full rounded-lg border border-zinc-300 px-3 py-2 dark:border-zinc-700 dark:bg-zinc-900"
                    data-testid="register-drawer-full-name"
                  />
                </label>
                <div className="grid gap-3 sm:grid-cols-2">
                  <label className="block space-y-1 text-sm">
                    <span className="text-zinc-600 dark:text-zinc-400">Дата рождения</span>
                    <input
                      type="date"
                      value={birthDate}
                      onChange={(e) => setBirthDate(e.target.value)}
                      className="w-full rounded-lg border border-zinc-300 px-3 py-2 dark:border-zinc-700 dark:bg-zinc-900"
                    />
                  </label>
                  <label className="block space-y-1 text-sm">
                    <span className="text-zinc-600 dark:text-zinc-400">Дата поступления заявления</span>
                    <input
                      type="date"
                      value={applicationReceivedAt}
                      onChange={(e) => setApplicationReceivedAt(e.target.value)}
                      required
                      className="w-full rounded-lg border border-zinc-300 px-3 py-2 dark:border-zinc-700 dark:bg-zinc-900"
                      data-testid="register-drawer-received-at"
                    />
                  </label>
                </div>
                <label className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={vacancyConfirmed}
                    onChange={(e) => setVacancyConfirmed(e.target.checked)}
                    data-testid="register-drawer-vacancy-confirmed"
                  />
                  <span>Вакансия проверена визуально</span>
                </label>

                <OrgScopeFilter
                  basePath={PERSONNEL_APPLICATIONS_BASE_PATH}
                  label="Подразделение"
                  value={orgGroupId}
                  onChange={(groupId) => {
                    setOrgGroupId(groupId);
                    setOrgUnitId(null);
                    setPositionId(null);
                  }}
                />
                <OrgUnitScopeFilter
                  basePath={PERSONNEL_APPLICATIONS_BASE_PATH}
                  label="Структурное подразделение"
                  allLabel="Выберите подразделение"
                  orgGroupId={orgGroupId}
                  value={orgUnitId}
                  onChange={(unitId) => {
                    setOrgUnitId(unitId);
                    setPositionId(null);
                  }}
                />
                <label className="block space-y-1 text-sm">
                  <span className="text-zinc-600 dark:text-zinc-400">Должность</span>
                  <select
                    value={positionId ?? ""}
                    onChange={(e) => setPositionId(e.target.value ? Number(e.target.value) : null)}
                    className="w-full rounded-lg border border-zinc-300 px-3 py-2 dark:border-zinc-700 dark:bg-zinc-900"
                    disabled={positionsLoading}
                    data-testid="register-drawer-position"
                  >
                    <option value="">—</option>
                    {renderPositionSelectOptions(positionGroups)}
                  </select>
                </label>
                <label className="block space-y-1 text-sm">
                  <span className="text-zinc-600 dark:text-zinc-400">Ставка</span>
                  <input
                    value={employmentRate}
                    onChange={(e) => setEmploymentRate(e.target.value)}
                    className="w-full rounded-lg border border-zinc-300 px-3 py-2 dark:border-zinc-700 dark:bg-zinc-900"
                  />
                </label>
                <div className="grid gap-3 sm:grid-cols-2">
                  <label className="block space-y-1 text-sm">
                    <span className="text-zinc-600 dark:text-zinc-400">Мобильный телефон</span>
                    <input
                      value={mobilePhone}
                      onChange={(e) => setMobilePhone(e.target.value)}
                      className="w-full rounded-lg border border-zinc-300 px-3 py-2 dark:border-zinc-700 dark:bg-zinc-900"
                    />
                  </label>
                  <label className="block space-y-1 text-sm">
                    <span className="text-zinc-600 dark:text-zinc-400">Email</span>
                    <input
                      type="email"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      className="w-full rounded-lg border border-zinc-300 px-3 py-2 dark:border-zinc-700 dark:bg-zinc-900"
                    />
                  </label>
                </div>
                <label className="block space-y-1 text-sm">
                  <span className="text-zinc-600 dark:text-zinc-400">Примечание HR</span>
                  <textarea
                    value={hrNote}
                    onChange={(e) => setHrNote(e.target.value)}
                    rows={3}
                    className="w-full rounded-lg border border-zinc-300 px-3 py-2 dark:border-zinc-700 dark:bg-zinc-900"
                  />
                </label>
                {preview?.person_exists ? (
                  <p className="text-xs text-zinc-500">
                    Будет использован существующий person #{preview.person_id}. Дата заявления:{" "}
                    {formatPersonnelApplicationDate(applicationReceivedAt)}.
                  </p>
                ) : null}
              </section>
            ) : null}
          </div>

          {showRegistrationForm ? (
            <div className="border-t border-zinc-200 px-4 py-3 dark:border-zinc-800">
              <button
                type="submit"
                disabled={submitting}
                className="w-full rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50 sm:w-auto"
                data-testid="register-drawer-submit"
              >
                {submitting ? "Регистрация…" : "Зарегистрировать"}
              </button>
            </div>
          ) : null}
        </form>
      </aside>
    </div>
  );
}
