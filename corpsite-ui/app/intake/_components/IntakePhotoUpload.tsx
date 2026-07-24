"use client";

import * as React from "react";

import IntakePhotoCropEditor, { readIntakePhotoSourceFile } from "./IntakePhotoCropEditor";
import {
  buildIntakePhotoPublicUrl,
  deleteIntakePhotoOnBehalf,
  deleteIntakePhotoPublic,
  fetchIntakePhotoOnBehalfBlob,
  uploadIntakePhotoOnBehalf,
  uploadIntakePhotoPublic,
} from "../_lib/intakePhotoApi.client";
import type { IntakePhotoFaceAnalysis } from "../_lib/intakePhotoTypes";
import type { IntakeDraftPayload } from "../_lib/intakeApi.client";

type Props = {
  mode: "public" | "hr-on-behalf";
  intakeToken?: string;
  applicationId?: number;
  payload: IntakeDraftPayload;
  readOnly?: boolean;
  onPayloadChange: (payload: IntakeDraftPayload) => void;
};

export default function IntakePhotoUpload({
  mode,
  intakeToken,
  applicationId,
  payload,
  readOnly,
  onPayloadChange,
}: Props) {
  const photoFileId = String(payload.personal.photo_file_id ?? "").trim();
  const [draftSrc, setDraftSrc] = React.useState<string | null>(null);
  const [faceAnalysis, setFaceAnalysis] = React.useState<IntakePhotoFaceAnalysis | null>(null);
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [cacheBust, setCacheBust] = React.useState(() => String(Date.now()));
  const [onBehalfPreviewUrl, setOnBehalfPreviewUrl] = React.useState<string | null>(null);
  const fileInputRef = React.useRef<HTMLInputElement | null>(null);

  const publicPhotoUrl = React.useMemo(() => {
    if (mode !== "public" || !photoFileId || !intakeToken) return null;
    return buildIntakePhotoPublicUrl(intakeToken, cacheBust);
  }, [cacheBust, intakeToken, mode, photoFileId]);

  React.useEffect(() => {
    return () => {
      if (draftSrc?.startsWith("blob:")) URL.revokeObjectURL(draftSrc);
    };
  }, [draftSrc]);

  React.useEffect(() => {
    if (mode !== "hr-on-behalf" || !photoFileId || !applicationId || draftSrc) {
      setOnBehalfPreviewUrl(null);
      return;
    }
    let cancelled = false;
    let objectUrl: string | null = null;
    void fetchIntakePhotoOnBehalfBlob(applicationId)
      .then((blob) => {
        if (cancelled) return;
        objectUrl = URL.createObjectURL(blob);
        setOnBehalfPreviewUrl(objectUrl);
      })
      .catch(() => {
        if (!cancelled) setOnBehalfPreviewUrl(null);
      });
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [applicationId, cacheBust, draftSrc, mode, photoFileId]);

  const savedPhotoUrl = mode === "public" ? publicPhotoUrl : onBehalfPreviewUrl;

  const openFilePicker = () => fileInputRef.current?.click();

  const handleFileSelected = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    setError(null);
    try {
      const src = await readIntakePhotoSourceFile(file);
      if (draftSrc?.startsWith("blob:")) URL.revokeObjectURL(draftSrc);
      setDraftSrc(src);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Не удалось загрузить файл.");
    }
  };

  const applyMutationPayload = (nextPayload: IntakeDraftPayload) => {
    onPayloadChange(nextPayload);
    setCacheBust(String(Date.now()));
  };

  const handleSave = async (blob: Blob) => {
    setBusy(true);
    setError(null);
    try {
      const result =
        mode === "public"
          ? await uploadIntakePhotoPublic(String(intakeToken), blob)
          : await uploadIntakePhotoOnBehalf(Number(applicationId), blob);
      applyMutationPayload(result.payload);
      if (draftSrc?.startsWith("blob:")) URL.revokeObjectURL(draftSrc);
      setDraftSrc(null);
      setFaceAnalysis(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Не удалось сохранить фото.");
      throw e;
    } finally {
      setBusy(false);
    }
  };

  const handleDelete = async () => {
    setBusy(true);
    setError(null);
    try {
      const result =
        mode === "public"
          ? await deleteIntakePhotoPublic(String(intakeToken))
          : await deleteIntakePhotoOnBehalf(Number(applicationId));
      applyMutationPayload(result.payload);
      if (draftSrc?.startsWith("blob:")) URL.revokeObjectURL(draftSrc);
      setDraftSrc(null);
      setFaceAnalysis(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Не удалось удалить фото.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-3 sm:col-span-2" data-testid="intake-photo-upload">
      <div>
        <div className="text-sm font-medium text-zinc-900 dark:text-zinc-50">Фотография 3×4</div>
        <p className="mt-1 text-xs text-zinc-500">JPEG, PNG или HEIC до 10 МБ. После сохранения фото будет сжато до 600×800 px.</p>
      </div>

      <input
        ref={fileInputRef}
        type="file"
        accept="image/jpeg,image/png,image/heic,image/heif"
        className="hidden"
        data-testid="intake-photo-file-input"
        onChange={(event) => void handleFileSelected(event)}
      />

      {draftSrc ? (
        <IntakePhotoCropEditor
          imageSrc={draftSrc}
          readOnly={readOnly}
          faceAnalysis={faceAnalysis}
          onFaceAnalysisChange={setFaceAnalysis}
          onCancel={() => {
            if (draftSrc.startsWith("blob:")) URL.revokeObjectURL(draftSrc);
            setDraftSrc(null);
            setFaceAnalysis(null);
          }}
          onSave={handleSave}
          onReplace={openFilePicker}
        />
      ) : savedPhotoUrl ? (
        <div className="space-y-3">
          <div
            className="mx-auto w-[180px] overflow-hidden border border-zinc-300 dark:border-zinc-600"
            style={{ aspectRatio: "3 / 4" }}
            data-testid="intake-photo-preview"
          >
            <img src={savedPhotoUrl} alt="Фото сотрудника" className="h-full w-full object-cover" />
          </div>
          <div className="flex flex-wrap gap-2">
            {!readOnly ? (
              <>
                <button
                  type="button"
                  disabled={busy}
                  onClick={openFilePicker}
                  data-testid="intake-photo-replace-saved"
                  className="rounded border px-3 py-1.5 text-sm"
                >
                  Заменить
                </button>
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => void handleDelete()}
                  data-testid="intake-photo-delete"
                  className="rounded border border-red-300 px-3 py-1.5 text-sm text-red-700"
                >
                  Удалить
                </button>
              </>
            ) : null}
          </div>
        </div>
      ) : (
        <div className="space-y-2">
          <div
            className="mx-auto flex w-[180px] items-center justify-center border border-dashed border-zinc-300 px-3 text-center text-xs text-zinc-500 dark:border-zinc-600"
            style={{ aspectRatio: "3 / 4" }}
            data-testid="intake-photo-empty-slot"
          >
            Место для фотографии 3×4
          </div>
          {!readOnly ? (
            <button
              type="button"
              disabled={busy}
              onClick={openFilePicker}
              data-testid="intake-photo-upload-button"
              className="rounded bg-sky-600 px-3 py-1.5 text-sm text-white disabled:opacity-60"
            >
              Загрузить фото
            </button>
          ) : null}
        </div>
      )}

      {error ? <p className="text-xs text-red-600">{error}</p> : null}
    </div>
  );
}
