"use client";

import * as React from "react";

import {
  createDefaultIntakePhotoCropState,
  INTAKE_PHOTO_ASPECT,
  type IntakePhotoCropState,
  type IntakePhotoFaceAnalysis,
} from "../_lib/intakePhotoTypes";
import { analyzeIntakePhotoFace } from "../_lib/intakePhotoFaceCheck";
import { exportIntakePhotoJpeg } from "../_lib/intakePhotoExport";
import { validateIntakePhotoSourceFile } from "../_lib/intakePhotoValidation";

type Props = {
  imageSrc: string;
  readOnly?: boolean;
  faceAnalysis: IntakePhotoFaceAnalysis | null;
  onFaceAnalysisChange: (analysis: IntakePhotoFaceAnalysis | null) => void;
  onCancel: () => void;
  onSave: (blob: Blob) => Promise<void>;
  onReplace: () => void;
};

const VIEWPORT_WIDTH = 300;
const VIEWPORT_HEIGHT = Math.round(VIEWPORT_WIDTH / INTAKE_PHOTO_ASPECT);

export default function IntakePhotoCropEditor({
  imageSrc,
  readOnly,
  faceAnalysis,
  onFaceAnalysisChange,
  onCancel,
  onSave,
  onReplace,
}: Props) {
  const [crop, setCrop] = React.useState<IntakePhotoCropState>(createDefaultIntakePhotoCropState());
  const [dragStart, setDragStart] = React.useState<{ x: number; y: number; originX: number; originY: number } | null>(
    null,
  );
  const [saving, setSaving] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const imageRef = React.useRef<HTMLImageElement | null>(null);

  React.useEffect(() => {
    setCrop(createDefaultIntakePhotoCropState());
    onFaceAnalysisChange(null);
    setError(null);
  }, [imageSrc, onFaceAnalysisChange]);

  const runFaceCheck = React.useCallback(async () => {
    const image = imageRef.current;
    if (!image || !image.complete) return;
    try {
      const analysis = await analyzeIntakePhotoFace(image, {
        width: VIEWPORT_WIDTH,
        height: VIEWPORT_HEIGHT,
      });
      onFaceAnalysisChange(analysis);
    } catch {
      onFaceAnalysisChange({
        level: "warning",
        code: "CHECK_UNAVAILABLE",
        message: "Не удалось выполнить автоматическую проверку лица.",
        faceCount: null,
      });
    }
  }, [onFaceAnalysisChange]);

  React.useEffect(() => {
    void runFaceCheck();
  }, [crop, imageSrc, runFaceCheck]);

  const handlePointerDown = (event: React.PointerEvent<HTMLDivElement>) => {
    if (readOnly) return;
    event.currentTarget.setPointerCapture(event.pointerId);
    setDragStart({
      x: event.clientX,
      y: event.clientY,
      originX: crop.position.x,
      originY: crop.position.y,
    });
  };

  const handlePointerMove = (event: React.PointerEvent<HTMLDivElement>) => {
    if (!dragStart || readOnly) return;
    setCrop((current) => ({
      ...current,
      position: {
        x: dragStart.originX + (event.clientX - dragStart.x),
        y: dragStart.originY + (event.clientY - dragStart.y),
      },
    }));
  };

  const handlePointerUp = () => {
    setDragStart(null);
  };

  const handleSave = async () => {
    const image = imageRef.current;
    if (!image) return;
    setSaving(true);
    setError(null);
    try {
      const blob = await exportIntakePhotoJpeg(image, crop, VIEWPORT_WIDTH, VIEWPORT_HEIGHT);
      await onSave(blob);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Не удалось сохранить фото.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-3" data-testid="intake-photo-crop-editor">
      <div
        className="relative mx-auto overflow-hidden border border-zinc-300 bg-zinc-100 dark:border-zinc-600 dark:bg-zinc-900"
        style={{ width: VIEWPORT_WIDTH, height: VIEWPORT_HEIGHT }}
        data-testid="intake-photo-crop-viewport"
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onPointerLeave={handlePointerUp}
      >
        <img
          ref={imageRef}
          src={imageSrc}
          alt=""
          draggable={false}
          className="absolute left-1/2 top-1/2 max-w-none select-none"
          style={{
            transform: `translate(calc(-50% + ${crop.position.x}px), calc(-50% + ${crop.position.y}px)) scale(${crop.zoom}) rotate(${crop.rotation}deg)`,
          }}
          onLoad={() => {
            void runFaceCheck();
          }}
        />
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <label className="text-xs text-zinc-600 dark:text-zinc-300">
          Масштаб
          <input
            type="range"
            min="1"
            max="3"
            step="0.01"
            value={crop.zoom}
            disabled={readOnly}
            onChange={(event) => setCrop((current) => ({ ...current, zoom: Number(event.target.value) }))}
            data-testid="intake-photo-zoom"
            className="ml-2 align-middle"
          />
        </label>
        <button
          type="button"
          disabled={readOnly}
          onClick={() => setCrop((current) => ({ ...current, rotation: (current.rotation + 90) % 360 }))}
          data-testid="intake-photo-rotate"
          className="rounded border px-2 py-1 text-xs"
        >
          Повернуть
        </button>
        <button type="button" disabled={readOnly} onClick={onReplace} data-testid="intake-photo-replace" className="rounded border px-2 py-1 text-xs">
          Заменить
        </button>
      </div>

      {faceAnalysis?.level === "warning" && faceAnalysis.message ? (
        <p className="text-xs text-amber-700 dark:text-amber-300" data-testid="intake-photo-face-warning">
          {faceAnalysis.message}
        </p>
      ) : null}
      {error ? <p className="text-xs text-red-600">{error}</p> : null}

      <div className="flex flex-wrap gap-2">
        <button type="button" onClick={onCancel} className="rounded border px-3 py-1.5 text-sm">
          Отмена
        </button>
        <button
          type="button"
          disabled={readOnly || saving}
          onClick={() => void handleSave()}
          data-testid="intake-photo-save"
          className="rounded bg-sky-600 px-3 py-1.5 text-sm text-white disabled:opacity-60"
        >
          {saving ? "Сохранение..." : "Сохранить фото"}
        </button>
      </div>
    </div>
  );
}

export async function readIntakePhotoSourceFile(file: File): Promise<string> {
  const validationError = validateIntakePhotoSourceFile(file);
  if (validationError) throw new Error(validationError);

  const type = String(file.type || "").trim().toLowerCase();
  if (type === "image/heic" || type === "image/heif") {
    const heic2any = (await import("heic2any")).default;
    const converted = await heic2any({ blob: file, toType: "image/jpeg", quality: 0.92 });
    const blob = Array.isArray(converted) ? converted[0] : converted;
    return URL.createObjectURL(blob);
  }
  return URL.createObjectURL(file);
}
