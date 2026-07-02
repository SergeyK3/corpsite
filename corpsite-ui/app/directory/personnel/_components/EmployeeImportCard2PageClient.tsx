"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";

import { HR_PROCESSES_NAV_HREF } from "@/lib/personnelNav";
import ImportProfileCardSections from "./ImportProfileCardSections";
import EmployeeOperationalAssignmentSection from "./EmployeeOperationalAssignmentSection";
import {
  EmployeeImportCardSection,
  EmployeeImportCardSectionNav,
  EmployeeImportCardSectionPlaceholder,
} from "./EmployeeImportCardSection";
import EmployeeAccountSections from "../../employees/_components/EmployeeAccountSections";
import { buildHrChangeEventsHref } from "../_lib/hrChangeEventsApi.client";
import {
  archiveEducationProfile,
  cloneImportProfile,
  getEmployeeImportCard2,
  mapImportApiError,
  normalizeImportProfile,
  saveEmployeeImportCard2,
  type EmployeeImportCard2Detail,
  type ImportProfile,
} from "../_lib/importApi.client";
import {
  extractEditableSectionsOverride,
  normalizeEditableProfile,
  validateEditableProfile,
} from "../_lib/importProfileEditor";

type Props = {
  employeeId: string;
};

function profileSignature(profile: ImportProfile | null): string {
  if (!profile) return "";
  return JSON.stringify(extractEditableSectionsOverride(normalizeEditableProfile(profile)));
}

function HrContourStatusBadge({ detail, isArchived }: { detail: EmployeeImportCard2Detail; isArchived: boolean }) {
  if (isArchived) {
    return (
      <span className="rounded-full border border-zinc-300 bg-zinc-100 px-2 py-0.5 text-xs text-zinc-700 dark:border-zinc-600 dark:bg-zinc-800 dark:text-zinc-200">
        архив staging
      </span>
    );
  }
  if (detail.has_override) {
    return (
      <span className="rounded-full border border-blue-200 bg-blue-50 px-2 py-0.5 text-xs text-blue-800 dark:border-blue-900 dark:bg-blue-950/40 dark:text-blue-200">
        есть override
      </span>
    );
  }
  return (
    <span className="rounded-full border border-zinc-200 bg-zinc-50 px-2 py-0.5 text-xs text-zinc-600 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-300">
      snapshot
    </span>
  );
}

export default function EmployeeImportCard2PageClient({ employeeId }: Props) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const provisionAccount = searchParams.get("provisionAccount") === "1";
  const [loading, setLoading] = React.useState(true);
  const [saving, setSaving] = React.useState(false);
  const [archiving, setArchiving] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [success, setSuccess] = React.useState<string | null>(null);
  const [detail, setDetail] = React.useState<EmployeeImportCard2Detail | null>(null);
  const [profile, setProfile] = React.useState<ImportProfile | null>(null);
  const [draft, setDraft] = React.useState<ImportProfile | null>(null);
  const [editing, setEditing] = React.useState(false);
  const [saveFlash, setSaveFlash] = React.useState(false);
  const saveFlashTimerRef = React.useRef<number | null>(null);
  const [assignmentRefreshToken, setAssignmentRefreshToken] = React.useState(0);

  React.useEffect(() => {
    return () => {
      if (saveFlashTimerRef.current) window.clearTimeout(saveFlashTimerRef.current);
    };
  }, []);

  const loadCard = React.useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getEmployeeImportCard2(employeeId);
      const normalized = cloneImportProfile(normalizeEditableProfile(normalizeImportProfile(data.profile)));
      setDetail(data);
      setProfile(normalized);
      setDraft(cloneImportProfile(normalized));
      setEditing(false);
    } catch (e) {
      setDetail(null);
      setProfile(null);
      setDraft(null);
      setError(mapImportApiError(e, "Не удалось загрузить карту импорта."));
    } finally {
      setLoading(false);
    }
  }, [employeeId]);

  React.useEffect(() => {
    void loadCard();
  }, [loadCard]);

  const isArchived = detail?.profile_status === "archived";
  const isEditable = editing && !isArchived && !!draft;
  const isDirty = isEditable && profileSignature(draft) !== profileSignature(profile);
  const displayName = detail?.full_name || draft?.basic.full_name || "—";

  function handleStartEdit() {
    setEditing(true);
    setError(null);
    setSuccess(null);
  }

  function handleCancelEdit() {
    if (isDirty && !window.confirm("Отменить несохранённые изменения?")) return;
    if (profile) setDraft(cloneImportProfile(profile));
    setEditing(false);
    setError(null);
  }

  function handleClose() {
    if (isDirty && !window.confirm("Есть несохранённые изменения. Закрыть карту без сохранения?")) {
      return;
    }
    router.push(HR_PROCESSES_NAV_HREF);
  }

  async function handleSave() {
    if (!draft || !detail) return;
    const prepared = normalizeEditableProfile(draft);
    const validationErrors = validateEditableProfile(prepared);
    if (validationErrors.length > 0) {
      setError(validationErrors.join("\n"));
      return;
    }
    setSaving(true);
    setError(null);
    setSuccess(null);
    setSaveFlash(false);
    try {
      const saved = await saveEmployeeImportCard2(employeeId, extractEditableSectionsOverride(prepared) as ImportProfile);
      const normalized = cloneImportProfile(normalizeEditableProfile(normalizeImportProfile(saved.profile)));
      setDetail({
        ...detail,
        profile_status: saved.profile_status,
        review_status: saved.review_status,
        has_override: true,
        profile: normalized,
      });
      setProfile(normalized);
      setDraft(cloneImportProfile(normalized));
      setEditing(false);
      setSuccess("Сохранено в staging");
      setSaveFlash(true);
      if (saveFlashTimerRef.current) window.clearTimeout(saveFlashTimerRef.current);
      saveFlashTimerRef.current = window.setTimeout(() => setSaveFlash(false), 1500);
    } catch (e) {
      setError(mapImportApiError(e));
    } finally {
      setSaving(false);
    }
  }

  async function handleArchive() {
    if (!detail) return;
    if (!window.confirm("Архивировать карту в staging? Кадровый контур не изменится.")) return;
    setArchiving(true);
    setError(null);
    setSuccess(null);
    try {
      const saved = await archiveEducationProfile(detail.batch_id, detail.profile_id ?? detail.row_id);
      setDetail({
        ...detail,
        profile_status: saved.profile_status,
        review_status: saved.review_status,
        has_override: true,
      });
      setEditing(false);
      setSuccess("Профиль архивирован в staging");
    } catch (e) {
      setError(mapImportApiError(e));
    } finally {
      setArchiving(false);
    }
  }

  const saveButtonLabel = saving ? "Сохранение…" : saveFlash ? "Сохранено" : "Сохранить";
  const saveButtonClass = saveFlash
    ? "rounded bg-green-600 px-4 py-2 text-sm font-medium text-white"
    : "rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50";

  const pageToolbar = isEditable ? (
    <>
      <button type="button" onClick={handleSave} disabled={!draft || saving} className={saveButtonClass}>
        {saveButtonLabel}
      </button>
      <button
        type="button"
        onClick={handleCancelEdit}
        disabled={saving}
        className="rounded border border-zinc-300 px-4 py-2 text-sm dark:border-zinc-700 disabled:opacity-50"
      >
        Отмена
      </button>
      <button type="button" onClick={handleClose} disabled={saving} className="rounded border border-zinc-300 px-4 py-2 text-sm dark:border-zinc-700">
        Закрыть
      </button>
    </>
  ) : (
    <button type="button" onClick={handleClose} className="rounded border border-zinc-300 px-4 py-2 text-sm dark:border-zinc-700">
      Закрыть
    </button>
  );

  const hrSectionActions = isEditable ? null : !isArchived && draft ? (
    <>
      <button
        type="button"
        onClick={handleStartEdit}
        className="rounded border border-zinc-300 bg-white px-3 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-900"
      >
        Редактировать портфолио
      </button>
      <button
        type="button"
        onClick={handleArchive}
        disabled={archiving}
        className="rounded border border-zinc-300 bg-white px-3 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-900 disabled:opacity-50"
      >
        {archiving ? "Архивирование…" : "Архивировать staging"}
      </button>
    </>
  ) : null;

  const hrSnapshotSummary = detail ? (
    <div className="mb-4 grid gap-2 rounded-lg border border-zinc-100 bg-zinc-50/80 p-3 text-sm dark:border-zinc-800 dark:bg-zinc-900/40 sm:grid-cols-3">
      <div>
        <div className="text-xs text-zinc-500">Batch / строка</div>
        <div className="font-medium">#{detail.batch_id} · {detail.row_id}</div>
      </div>
      <div>
        <div className="text-xs text-zinc-500">Должность (snapshot)</div>
        <div className="font-medium">{detail.position_raw || draft?.basic.position_raw || "—"}</div>
      </div>
      <div>
        <div className="text-xs text-zinc-500">Отделение (snapshot)</div>
        <div className="font-medium">{detail.department_source || draft?.basic.department_source || "—"}</div>
      </div>
    </div>
  ) : null;

  return (
    <div className="flex max-h-[calc(100dvh-8.5rem)] min-h-[min(100dvh-8.5rem,640px)] flex-col overflow-hidden">
      <div className="shrink-0 border-b border-zinc-200 bg-white px-4 py-3 dark:border-zinc-800 dark:bg-zinc-950 sm:px-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-xl font-semibold text-zinc-900 dark:text-zinc-50">{displayName}</h1>
            <p className="mt-0.5 text-xs text-zinc-500">
              Карточка сотрудника · HR Import + Operational Directory
              {detail ? (
                <>
                  {" · "}
                  <Link
                    href={buildHrChangeEventsHref({ employee_id: Number(employeeId) })}
                    className="font-medium text-blue-700 hover:underline dark:text-blue-300"
                  >
                    История изменений реестра
                  </Link>
                </>
              ) : null}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">{pageToolbar}</div>
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto px-4 py-5 sm:px-6">
        {detail?.missing_from_latest_import ? (
          <div className="mb-4 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
            Сотрудник отсутствует в последней выгрузке (batch #{detail.latest_batch_id ?? "—"}).
            Карта построена по batch #{detail.card_batch_id}. Данные могут быть устаревшими.
          </div>
        ) : null}
        {success ? (
          <div className="mb-4 rounded-lg border border-green-200 bg-green-50 px-3 py-2 text-sm text-green-800">
            {success}
          </div>
        ) : null}
        {error ? (
          <div className="mb-4 whitespace-pre-wrap rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
            {error}
          </div>
        ) : null}

        {loading ? (
          <div className="py-16 text-center text-sm text-zinc-500">Загрузка карты сотрудника…</div>
        ) : !draft || !detail ? (
          <div className="py-16 text-center text-sm text-zinc-500">Для сотрудника не найдена строка HR-импорта.</div>
        ) : (
          <>
            <EmployeeImportCardSectionNav />

            <div className="space-y-5">
              <EmployeeImportCardSection
                id="assignment"
                title="Назначение"
                description="Текущее организационное назначение в Operational Directory. Изменения — через workflow перевода или зачисления."
                footer={
                  <EmployeeImportCardSectionPlaceholder label="Приказы / штатное расписание" hint="Модуль планируется." />
                }
              >
                <EmployeeOperationalAssignmentSection
                  employeeId={employeeId}
                  batchId={detail.batch_id}
                  rowId={detail.row_id}
                  refreshToken={assignmentRefreshToken}
                  onAssignmentChanged={() => setAssignmentRefreshToken((t) => t + 1)}
                />
              </EmployeeImportCardSection>

              <EmployeeImportCardSection
                id="hr-contour"
                title="Кадровый контур"
                description="HR Import snapshot и редактируемое портфолио. Организационное назначение — в разделе «Назначение»."
                status={<HrContourStatusBadge detail={detail} isArchived={isArchived} />}
                actions={hrSectionActions}
                footer={
                  <EmployeeImportCardSectionPlaceholder label="Личное дело / архив документов" hint="Модуль планируется." />
                }
              >
                {isEditable ? (
                  <p className="mb-4 rounded-lg border border-blue-100 bg-blue-50/60 px-3 py-2 text-xs text-blue-900 dark:border-blue-900/40 dark:bg-blue-950/30 dark:text-blue-100">
                    Организационное назначение изменяется в разделе{" "}
                    <button
                      type="button"
                      className="font-medium underline hover:no-underline"
                      onClick={() =>
                        document.getElementById("assignment")?.scrollIntoView({ behavior: "smooth", block: "start" })
                      }
                    >
                      «Назначение»
                    </button>
                    .
                  </p>
                ) : null}
                {hrSnapshotSummary}
                <ImportProfileCardSections
                  profile={draft}
                  departmentCanonical={detail.department_recoding?.org_unit_name}
                  mode={isEditable ? "edit" : "view"}
                  basicEditable={false}
                  showEditModeSnapshotSplit={isEditable}
                  onProfileChange={isEditable ? setDraft : setProfile}
                />
              </EmployeeImportCardSection>

              <EmployeeImportCardSection
                id="access"
                title="Доступ"
                description="Учётная запись Corpsite и каналы уведомлений. Управление доступом — отдельно от кадрового контура."
                footer={
                  <EmployeeImportCardSectionPlaceholder label="Расширенные политики доступа" hint="Модуль планируется." />
                }
              >
                <EmployeeAccountSections
                  employeeId={employeeId}
                  initialUserCreateOpen={provisionAccount}
                  refreshToken={assignmentRefreshToken}
                  embedded
                  showEvents={false}
                />
              </EmployeeImportCardSection>
            </div>
          </>
        )}
      </div>

      {isEditable ? (
        <div className="shrink-0 border-t border-zinc-200 bg-white px-4 py-3 dark:border-zinc-800 dark:bg-zinc-950 sm:px-6">
          <div className="flex flex-wrap justify-end gap-2">{pageToolbar}</div>
        </div>
      ) : null}
    </div>
  );
}
