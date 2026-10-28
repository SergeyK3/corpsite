"use client";
import { useEffect, useState } from "react";
import { editablePersonnelOrderTemplateDraftText, previewPersonnelOrderTemplateDraft,
  type PersonnelOrderTemplateDraftText, type PersonnelOrderTemplatePreview } from "../_lib/personnelOrderTemplatesApi.client";
import QualificationCategoryPreviewResult from "./QualificationCategoryPreviewResult";

/** The server renders editor texts with synthetic category data, without saving. */
export default function QualificationCategoryTemplatePreview({ values, refresh }: {
  values: PersonnelOrderTemplateDraftText;
  refresh: number;
}) {
  const [previews, setPreviews] = useState<Record<"ru" | "kk", PersonnelOrderTemplatePreview> | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    setPreviews(null); setError("");
    const timer = setTimeout(() => {
      void previewPersonnelOrderTemplateDraft("QUALIFICATION_CATEGORY", editablePersonnelOrderTemplateDraftText(values))
        .then(result => { if (active) setPreviews(result.previews); })
        .catch(cause => {
          if (active) setError(cause?.details?.detail?.message || cause?.message || "Не удалось сформировать предпросмотр.");
        });
    }, 200);
    return () => { active = false; clearTimeout(timer); };
  }, [values, refresh]);
  return <section className="mt-4 min-w-0 space-y-3" data-testid="qualification-category-template-preview">
    <h3 className="font-semibold">Предварительный просмотр приказа</h3>
    <p className="text-sm">Синтетические данные. Слева — қазақша (KK), справа — русский (RU).</p>
    {error ? <p role="alert" className="text-red-700">{error}</p> : previews
      ? <QualificationCategoryPreviewResult previews={previews} />
      : <p role="status">Формирование предпросмотра…</p>}
  </section>;
}
