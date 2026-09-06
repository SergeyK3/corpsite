"use client";

import * as React from "react";
import Image from "next/image";

import { getPprPersonPhoto } from "../_lib/pprQueryApi.client";

type Props = {
  personId: number | null;
  fullName: string;
};

export default function PprPersonPhoto({ personId, fullName }: Props) {
  const [photoBlob, setPhotoBlob] = React.useState<Blob | null>(null);
  const [loading, setLoading] = React.useState(personId != null);

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
  }, [personId]);

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

  return (
    <div
      className="flex h-32 w-24 shrink-0 items-center justify-center overflow-hidden rounded-lg border border-zinc-300 bg-zinc-100 text-center text-xs text-zinc-500 dark:border-zinc-700 dark:bg-zinc-900 sm:h-40 sm:w-[7.5rem]"
      data-testid="ppr-person-photo"
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
  );
}
