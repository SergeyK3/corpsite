"use client";

import * as React from "react";

import ImportProfileCardSections from "./ImportProfileCardSections";
import {
  archiveEducationProfile,
  cloneImportProfile,
  mapImportApiError,
  normalizeImportProfile,
  saveEducationProfile,
  type EducationProfileDetail,
  type ImportProfile,
} from "../_lib/importApi.client";
import { extractEditableSectionsOverride, normalizeEditableProfile, validateEditableProfile } from "../_lib/importProfileEditor";

type Props = {
  batchId: number;
  detail: EducationProfileDetail;
  onClose: () => void;
  onSaved: (detail: EducationProfileDetail) => void;
};

export default function ImportEducationProfileCardModal({ batchId, detail, onClose, onSaved }: Props) {
  const [profile, setProfile] = React.useState<ImportProfile>(() =>
    cloneImportProfile(normalizeEditableProfile(normalizeImportProfile(detail.profile)))
  );
  const [reviewStatus, setReviewStatus] = React.useState(detail.review_status);
  const [saving, setSaving] = React.useState(false);
  const [archiving, setArchiving] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [saveFlash, setSaveFlash] = React.useState(false);
  const saveFlashTimerRef = React.useRef<number | null>(null);

  React.useEffect(() => {
    return () => {
      if (saveFlashTimerRef.current) window.clearTimeout(saveFlashTimerRef.current);
    };
  }, []);

  async function handleSave() {
    const prepared = normalizeEditableProfile(profile);
    const validationErrors = validateEditableProfile(prepared);
    if (validationErrors.length > 0) {
      setError(validationErrors.join("\n"));
      return;
    }
    setSaving(true);
    setError(null);
    setSaveFlash(false);
    try {
      const saved = await saveEducationProfile(batchId, detail.profile_id, {
        profile: extractEditableSectionsOverride(prepared) as ImportProfile,
        review_status: reviewStatus,
      });
      setProfile(cloneImportProfile(normalizeEditableProfile(normalizeImportProfile(saved.profile))));
      setSaveFlash(true);
      onSaved(saved);
      if (saveFlashTimerRef.current) window.clearTimeout(saveFlashTimerRef.current);
      saveFlashTimerRef.current = window.setTimeout(() => setSaveFlash(false), 1500);
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

  const saveButtonLabel = saving ? "Сохранение…" : saveFlash ? "Сохранено" : "Сохранить";
  const saveButtonClass = saveFlash
    ? "rounded bg-green-600 px-4 py-2 text-sm font-medium text-white"
    : "rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50";

  const toolbar = (
    <>
      <button
        type="button"
        onClick={handleArchive}
        disabled={archiving || saving}
        className="rounded border border-zinc-300 px-4 py-2 text-sm text-zinc-700 hover:bg-zinc-50 disabled:opacity-50 dark:border-zinc-700 dark:text-zinc-300"
      >
        {archiving ? "Архивирование…" : "Архивировать"}
      </button>
      <button type="button" onClick={handleSave} disabled={saving || archiving} className={saveButtonClass}>
        {saveButtonLabel}
      </button>
      <button
        type="button"
        onClick={onClose}
        disabled={saving}
        className="rounded border border-zinc-300 px-4 py-2 text-sm dark:border-zinc-700 disabled:opacity-50"
      >
        Закрыть
      </button>
    </>
  );

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-2 sm:p-4">
      <div className="flex max-h-[calc(100dvh-1rem)] w-full max-w-5xl flex-col overflow-hidden rounded-xl border border-zinc-200 bg-white shadow-2xl dark:border-zinc-800 dark:bg-zinc-950">
        <div className="shrink-0 border-b border-zinc-200 px-4 py-3 dark:border-zinc-800 sm:px-6">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0">
              <h2 className="text-xl font-semibold text-zinc-900 dark:text-zinc-50">
                {detail.full_name || "Карточка сотрудника"}
              </h2>
              <p className="text-sm text-zinc-500">
                staging · rows {detail.source_row_ids?.join(", ") ?? detail.row_id}
                {detail.source_sheet ? ` · ${detail.source_sheet}:${detail.source_row_number}` : ""}
              </p>
            </div>
            <div className="flex flex-wrap gap-2">{toolbar}</div>
          </div>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto px-4 py-5 sm:px-6">
          {error ? <div className="mb-4 text-sm text-red-600">{error}</div> : null}
          <ImportProfileCardSections
            profile={profile}
            departmentCanonical={detail.department_recoding?.org_unit_name}
            mode="edit"
            basicEditable
            showReviewStatus
            reviewStatus={reviewStatus}
            onReviewStatusChange={setReviewStatus}
            onProfileChange={setProfile}
          />
        </div>

        <div className="shrink-0 border-t border-zinc-200 bg-white px-4 py-3 dark:border-zinc-800 dark:bg-zinc-950 sm:px-6">
          <div className="flex flex-wrap justify-end gap-2">{toolbar}</div>
        </div>
      </div>
    </div>
  );
}
