"use client";
import { usePersonnelSectionLanguage } from "@/app/directory/personnel/_lib/personnelSectionLanguage";

export default function PersonnelTemplateIdentity({ templateId, versionId, versionNumber, status }: {
  templateId?: number | null; versionId?: number | null; versionNumber?: number | null; status?: string;
}) {
  const { language } = usePersonnelSectionLanguage();
  const kk = language === "kk";
  const template = templateId == null ? (versionId != null ? (kk ? "Үлгі" : "Шаблон") : (kk ? "Жаңа үлгі" : "Новый шаблон")) : `${kk ? "Үлгі" : "Шаблон"} №${templateId}`;
  return <span data-testid="template-identity">{template} · {versionId == null
    ? (kk ? "Нұсқа сақталмаған" : "Версия не сохранена")
    : `${versionNumber == null ? "" : `v${versionNumber} · `}${kk ? "Нұсқа ID" : "ID версии"} ${versionId} · ${status}`}</span>;
}
