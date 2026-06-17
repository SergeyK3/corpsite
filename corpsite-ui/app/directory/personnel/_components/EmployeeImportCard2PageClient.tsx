"use client";

import * as React from "react";
import { useRouter } from "next/navigation";

import ImportProfileCardSections from "./ImportProfileCardSections";
import EmployeeAccountSections from "../../employees/_components/EmployeeAccountSections";
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

export default function EmployeeImportCard2PageClient({ employeeId }: Props) {
  const router = useRouter();
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
    router.push("/directory/personnel");
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

  const toolbar = isEditable ? (
    <>
      <button
        type="button"
        onClick={handleArchive}
        disabled={archiving || saving}
        className="rounded border border-zinc-300 px-4 py-2 text-sm dark:border-zinc-700 disabled:opacity-50"
      >
        {archiving ? "Архивирование…" : "Архивировать"}
      </button>
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
      <button
        type="button"
        onClick={handleClose}
        disabled={saving}
        className="rounded border border-zinc-300 px-4 py-2 text-sm dark:border-zinc-700"
      >
        Закрыть
      </button>
    </>
  ) : (
    <>
      {!isArchived && draft ? (
        <button
          type="button"
          onClick={handleStartEdit}
          className="rounded border border-zinc-300 px-4 py-2 text-sm dark:border-zinc-700"
        >
          Редактировать
        </button>
      ) : null}
      {!isArchived ? (
        <button
          type="button"
          onClick={handleArchive}
          disabled={archiving}
          className="rounded border border-zinc-300 px-4 py-2 text-sm dark:border-zinc-700 disabled:opacity-50"
        >
          {archiving ? "Архивирование…" : "Архивировать"}
        </button>
      ) : null}
      <button
        type="button"
        onClick={handleClose}
        className="rounded border border-zinc-300 px-4 py-2 text-sm dark:border-zinc-700"
      >
        Закрыть
      </button>
    </>
  );

  return (
    <div className="flex max-h-[calc(100dvh-8.5rem)] min-h-[min(100dvh-8.5rem,640px)] flex-col overflow-hidden">
      <div className="shrink-0 border-b border-zinc-200 bg-white px-4 py-3 dark:border-zinc-800 dark:bg-zinc-950 sm:px-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-xl font-semibold text-zinc-900 dark:text-zinc-50">{displayName}</h1>
            {detail ? (
              <p className="mt-0.5 text-xs text-zinc-500">
                Batch #{detail.batch_id} · строка {detail.row_id}
                {isArchived ? " · архив" : ""}
              </p>
            ) : null}
          </div>
          <div className="flex flex-wrap gap-2">{toolbar}</div>
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto px-4 py-5 sm:px-6">
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
          <div className="py-16 text-center text-sm text-zinc-500">Загрузка карты импорта…</div>
        ) : !draft ? (
          <div className="py-16 text-center text-sm text-zinc-500">Для сотрудника не найдена строка HR-импорта.</div>
        ) : (
          <ImportProfileCardSections
            profile={draft}
            departmentCanonical={detail?.department_recoding?.org_unit_name}
            mode={isEditable ? "edit" : "view"}
            basicEditable={false}
            onProfileChange={isEditable ? setDraft : setProfile}
          />
        )}

        {!loading && employeeId ? (
          <div className="mt-8 border-t border-zinc-200 pt-8 dark:border-zinc-800">
            <EmployeeAccountSections employeeId={employeeId} />
          </div>
        ) : null}
      </div>

      <div className="shrink-0 border-t border-zinc-200 bg-white px-4 py-3 dark:border-zinc-800 dark:bg-zinc-950 sm:px-6">
        <div className="flex flex-wrap justify-end gap-2">{toolbar}</div>
      </div>
    </div>
  );
}
