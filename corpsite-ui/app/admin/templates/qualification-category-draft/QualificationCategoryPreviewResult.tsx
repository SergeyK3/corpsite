"use client";
import { useRef } from "react";
import type { PersonnelOrderTemplatePreview } from "../_lib/personnelOrderTemplatesApi.client";
import QualificationCategoryOrderDocument from "./QualificationCategoryOrderDocument";

export default function QualificationCategoryPreviewResult({ previews, testId = "category-preview", templateId, templateVersionId }: {
  previews: Record<"ru" | "kk", PersonnelOrderTemplatePreview>;
  testId?: string;
  templateId?: number | null;
  templateVersionId?: number | null;
}) {
  const printRef = useRef<HTMLDivElement>(null);
  function print() {
    if (!printRef.current) return;
    const popup = window.open("", "_blank");
    if (!popup) return;
    const sheet = popup.document.createElement("style");
    sheet.textContent = '@page{size:A4 landscape;margin:15mm}body{margin:0;color:black;background:white}[data-category-bilingual-preview]{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8mm;min-width:0!important}[data-category-bilingual-preview]>section{min-width:0;padding:4mm;border:1px solid #ddd}';
    popup.document.head.appendChild(sheet);
    popup.document.body.appendChild(printRef.current.cloneNode(true));
    popup.document.title = "Предпросмотр черновика RU/KK";
    popup.document.close();
    popup.focus();
    popup.print();
  }
  return <div className="min-w-0 space-y-3">
    <button type="button" className="rounded border p-2" onClick={print}>Печатный предпросмотр KK/RU</button>
    <div style={{maxWidth: "100%", overflowX: "auto"}}>
      <div ref={printRef} style={{display: "grid", gridTemplateColumns: "repeat(2, minmax(26rem, 1fr))", gap: "1rem", minWidth: "53rem", alignItems: "start"}} data-category-bilingual-preview data-template-id={templateId} data-template-version-id={templateVersionId} data-testid={testId}>
        {(["kk", "ru"] as const).map(locale => <QualificationCategoryOrderDocument key={locale} locale={locale} previews={previews} />)}
      </div>
    </div>
  </div>;
}
