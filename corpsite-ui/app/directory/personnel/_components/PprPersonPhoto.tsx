"use client";

import * as React from "react";
import Image from "next/image";

import { getPprPersonPhoto, uploadPprPersonPhoto } from "../_lib/pprQueryApi.client";

const MAX_PHOTO_BYTES = 512_000;

type Props = {
  personId: number | null;
  fullName: string;
  canManagePhoto?: boolean;
};

function uploadErrorMessage(error: unknown): string {
  return error instanceof Error && error.message ? error.message : "Не удалось загрузить фото.";
}

export default function PprPersonPhoto({ personId, fullName, canManagePhoto = false }: Props) {
  const [photoBlob, setPhotoBlob] = React.useState<Blob | null>(null);
  const [loading, setLoading] = React.useState(personId != null);
  const [refreshKey, setRefreshKey] = React.useState(0);
  const [uploading, setUploading] = React.useState(false);
  const [message, setMessage] = React.useState<string | null>(null);
  const inputRef = React.useRef<HTMLInputElement>(null);

  React.useEffect(() => {
    const controller = new AbortController();
    setPhotoBlob(null);
    setLoading(personId != null);

    if (personId == null) return () => controller.abort();

    void getPprPersonPhoto(personId, { signal: controller.signal })
      .then((blob) => {
        if (!controller.signal.aborted) setPhotoBlob(blob);
      })
      .catch(() => {
        if (!controller.signal.aborted) setPhotoBlob(null);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });

    return () => controller.abort();
  }, [personId, refreshKey]);

  const photoUrl = React.useMemo(
    () => (photoBlob == null ? null : URL.createObjectURL(photoBlob)),
    [photoBlob],
  );

  React.useEffect(
    () => () => {
      if (photoUrl != null) URL.revokeObjectURL(photoUrl);
    },
    [photoUrl],
  );

  const onFileSelected = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (file == null || personId == null || uploading) return;
    setMessage(null);
    if (file.type.toLowerCase() !== "image/jpeg") {
      setMessage("Можно загрузить только JPEG-файл.");
      return;
    }
    if (file.size === 0 || file.size > MAX_PHOTO_BYTES) {
      setMessage("Размер фотографии должен быть не более 500 КБ.");
      return;
    }

    const replacing = photoBlob != null;
    setUploading(true);
    try {
      await uploadPprPersonPhoto(personId, file);
      setRefreshKey((value) => value + 1);
      setMessage(replacing ? "Фотография успешно заменена." : "Фотография успешно загружена.");
    } catch (error) {
      setMessage(uploadErrorMessage(error));
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="w-24 shrink-0 sm:h-40 sm:w-[7.5rem]" data-testid="ppr-person-photo">
      <div
        className="flex h-32 w-24 items-center justify-center overflow-hidden rounded-lg border border-zinc-300 bg-zinc-100 text-center text-xs text-zinc-500 dark:border-zinc-700 dark:bg-zinc-900 sm:h-40 sm:w-[7.5rem]"
      >
        {photoUrl != null ? (
          <Image
            src={photoUrl}
            alt={`Фото сотрудника ${fullName}`}
            width={120}
            height={160}
            unoptimized
            className="h-full w-full object-cover"
          />
        ) : (
          <span className="px-2">{loading ? "Загрузка фото…" : "Фото отсутствует"}</span>
        )}
      </div>
      {canManagePhoto && personId != null ? (
        <div className="mt-2">
          <input
            ref={inputRef}
            type="file"
            accept="image/jpeg,.jpg,.jpeg"
            className="sr-only"
            aria-label="Выбрать фотографию"
            onChange={(event) => void onFileSelected(event)}
          />
          <button
            type="button"
            className="w-full rounded border border-zinc-300 px-2 py-1 text-xs font-medium text-zinc-800 disabled:cursor-wait disabled:opacity-60 dark:border-zinc-700 dark:text-zinc-100"
            onClick={() => inputRef.current?.click()}
            disabled={uploading}
          >
            {uploading ? "Загрузка…" : photoBlob != null ? "Заменить фото" : "Загрузить фото"}
          </button>
          {message != null ? (
            <p role="status" className="mt-1 text-xs text-zinc-700 dark:text-zinc-300">
              {message}
            </p>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
