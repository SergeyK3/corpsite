import { INTAKE_PDF_DOCUMENT_CSS } from "@/app/intake/_lib/intakePdfDocumentCss";
import type { PersonCardPdfViewModel } from "./personCardPdfViewModel";

const escapeHtml = (value: unknown) => String(value ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#39;");
const cell = (value: unknown) => escapeHtml(String(value ?? "").trim() || "—");

export function buildPersonCardPdfHtmlDocument(model: PersonCardPdfViewModel): string {
  const photo = model.photoDataUrl ? `<img src="${model.photoDataUrl}" alt="" class="intake-pdf-photo-image" />` : '<span class="intake-pdf-photo-caption">Место для фотографии 3×4</span>';
  const sections = model.sections.map((section) => {
    const table = section.rows.length ? `<table class="intake-pdf-data-table"><thead><tr>${section.headers.map((header) => `<th>${escapeHtml(header)}</th>`).join("")}</tr></thead><tbody>${section.rows.map((row) => `<tr>${row.map((value) => `<td>${cell(value)}</td>`).join("")}</tr>`).join("")}</tbody></table>` : `<p class="intake-pdf-empty">${escapeHtml(section.emptyMessage ?? "Нет сведений")}</p>`;
    return `<section class="intake-pdf-section intake-pdf-section-flow" data-testid="person-card-pdf-section-${escapeHtml(section.key)}"><h2 class="intake-pdf-section-title">${escapeHtml(section.title)}</h2>${table}</section>`;
  }).join("");
  return `<!DOCTYPE html><html lang="ru"><head><meta charset="utf-8" /><style>${INTAKE_PDF_DOCUMENT_CSS}</style></head><body><div class="intake-pdf-document"><header class="intake-pdf-header"><div class="intake-pdf-title-block"><h1 class="intake-pdf-title">ЛИЧНАЯ КАРТОЧКА</h1></div><div class="intake-pdf-header-main"><div class="intake-pdf-photo-slot">${photo}</div><table class="intake-pdf-header-fields"><tbody><tr><td class="intake-pdf-field-label">Ф.И.О.</td><td>${cell(model.fullName)}</td></tr><tr><td class="intake-pdf-field-label">ИИН</td><td>${cell(model.iin)}</td></tr><tr><td class="intake-pdf-field-label">Дата рождения</td><td>${cell(model.birthDate)}</td></tr></tbody></table></div></header>${sections}</div></body></html>`;
}
