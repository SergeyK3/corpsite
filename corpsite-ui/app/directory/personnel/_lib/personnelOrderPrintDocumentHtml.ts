import type { PersonnelOrderPrintLanguage } from "./personnelOrderPrintLanguage";
import { formatPersonnelOrderPrintDateLines } from "./personnelOrderPrintFormat";
import { renderPersonnelOrderPrintItemText } from "./personnelOrderPrintItemText";
import {
  primaryPrintDictionary,
  printDictionariesForLanguage,
  statusMarkLinesForLanguage,
} from "./personnelOrderPrintLocale";
import { resolveLocalizedLines } from "./personnelOrderPrintLocalized";
import type {
  PersonnelOrderPrintItemViewModel,
  PersonnelOrderPrintViewModel,
} from "./personnelOrderPrintViewModel";

/** Escape text for trusted internal HTML templates (ViewModel → markup). */
export function escapePersonnelOrderPrintHtml(value: string): string {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function linesHtml(lines: string[], className?: string): string {
  return lines
    .map((line) => {
      const cls = className ? ` class="${className}"` : "";
      return `<div${cls}>${escapePersonnelOrderPrintHtml(line)}</div>`;
    })
    .join("");
}

function renderStatusMark(
  model: PersonnelOrderPrintViewModel,
  language: PersonnelOrderPrintLanguage,
): string {
  if (model.statusMark === "none") return "";
  const lines = statusMarkLinesForLanguage(model.statusMark, language);
  return `<div class="personnel-order-print-watermark" aria-hidden="true" data-testid="personnel-order-print-status-mark" data-status-mark="${escapePersonnelOrderPrintHtml(model.statusMark)}"><div>${linesHtml(lines, "leading-tight")}</div></div>`;
}

function renderHeader(
  model: PersonnelOrderPrintViewModel,
  language: PersonnelOrderPrintLanguage,
): string {
  const dictionaries = printDictionariesForLanguage(language);
  const primary = primaryPrintDictionary(language);
  const orgLines = resolveLocalizedLines(model.organization, language);
  const titleLines = resolveLocalizedLines(model.title, language);
  const placeLines = resolveLocalizedLines(model.placeOfIssue, language);
  const dateLines = formatPersonnelOrderPrintDateLines(model.orderDate, language);
  const orderNumber = model.orderNumber?.trim() || "—";

  const org =
    orgLines.length > 0
      ? `<div class="personnel-order-print-org">${linesHtml(orgLines)}</div>`
      : "";

  const docType = `<div class="personnel-order-print-doc-type">${dictionaries
    .map((dict) => `<div>${escapePersonnelOrderPrintHtml(dict.documentType)}</div>`)
    .join("")}</div>`;

  const meta = `<div class="personnel-order-print-meta">
  <div class="personnel-order-print-meta-number">${escapePersonnelOrderPrintHtml(primary.orderNumber)} ${escapePersonnelOrderPrintHtml(orderNumber)}</div>
  <div class="personnel-order-print-meta-date">
    ${linesHtml(dateLines)}
    ${linesHtml(placeLines)}
  </div>
</div>`;

  const title =
    titleLines.length > 0
      ? `<div class="personnel-order-print-title">${linesHtml(titleLines)}</div>`
      : "";

  return `<header class="personnel-order-print-block personnel-order-print-header" data-testid="personnel-order-print-header">${org}${docType}${meta}${title}</header>`;
}

function renderItem(
  item: PersonnelOrderPrintItemViewModel,
  language: PersonnelOrderPrintLanguage,
): string {
  // Prefer editorial effective body; fall back to deterministic templates.
  const editorialLines = item.body ? resolveLocalizedLines(item.body, language) : [];
  const lines =
    editorialLines.length > 0
      ? editorialLines
      : renderPersonnelOrderPrintItemText(item.context, language);
  const body = lines
    .map((line) => `<p class="m-0">${escapePersonnelOrderPrintHtml(line)}</p>`)
    .join("");
  return `<li class="personnel-order-print-item" data-testid="personnel-order-print-item-${item.itemId}">
  <div class="personnel-order-print-item-grid">
    <div class="personnel-order-print-item-num">${item.itemNumber}.</div>
    <div class="personnel-order-print-item-body">${body}</div>
  </div>
</li>`;
}

function renderItems(
  model: PersonnelOrderPrintViewModel,
  language: PersonnelOrderPrintLanguage,
): string {
  const dictionaries = printDictionariesForLanguage(language);
  const preambleLines = model.preamble ? resolveLocalizedLines(model.preamble, language) : [];
  const preamble =
    preambleLines.length > 0
      ? `<div class="personnel-order-print-block personnel-order-print-preamble">${preambleLines
          .map((line) => `<p class="m-0">${escapePersonnelOrderPrintHtml(line)}</p>`)
          .join("")}</div>`
      : "";

  const verb = `<div class="personnel-order-print-block personnel-order-print-order-verb">${dictionaries
    .map((dict) => `<div>${escapePersonnelOrderPrintHtml(dict.orderVerb)}</div>`)
    .join("")}</div>`;

  const items =
    model.items.length === 0
      ? `<p>${escapePersonnelOrderPrintHtml(primaryPrintDictionary(language).itemsEmpty)}</p>`
      : `<ol class="personnel-order-print-items-list">${model.items
          .map((item) => renderItem(item, language))
          .join("")}</ol>`;

  return `<section class="personnel-order-print-items" data-testid="personnel-order-print-items">${preamble}${verb}${items}</section>`;
}

function renderBasis(
  model: PersonnelOrderPrintViewModel,
  language: PersonnelOrderPrintLanguage,
): string {
  if (!model.basis.length) return "";
  const dictionaries = printDictionariesForLanguage(language);
  const lines = model.basis.flatMap((entry) => resolveLocalizedLines(entry, language));
  if (!lines.length) return "";

  const headings = dictionaries
    .map((dict) => `<div>${escapePersonnelOrderPrintHtml(dict.basis)}:</div>`)
    .join("");
  const list = lines
    .map((line) => `<li>${escapePersonnelOrderPrintHtml(line)}</li>`)
    .join("");

  return `<section class="personnel-order-print-block personnel-order-print-basis" data-testid="personnel-order-print-basis">
  <div class="personnel-order-print-basis-heading">${headings}</div>
  <ul class="personnel-order-print-basis-list">${list}</ul>
</section>`;
}

function renderSignature(
  model: PersonnelOrderPrintViewModel,
  language: PersonnelOrderPrintLanguage,
): string {
  const positionLines = model.signatory?.position
    ? resolveLocalizedLines(model.signatory.position, language)
    : [];
  const fio = String(model.signatory?.fio || "").trim();
  const position =
    positionLines.length > 0
      ? linesHtml(positionLines)
      : `<div class="personnel-order-print-spacer">&nbsp;</div>`;
  const fioHtml = fio
    ? escapePersonnelOrderPrintHtml(fio)
    : `<span class="personnel-order-print-fio-placeholder">&nbsp;</span>`;

  return `<section class="personnel-order-print-signature personnel-order-print-block" data-testid="personnel-order-print-signature">
  <div class="personnel-order-print-signature-grid">
    <div class="personnel-order-print-signature-position">${position}</div>
    <div class="personnel-order-print-signature-line">&nbsp;</div>
    <div class="personnel-order-print-signature-fio">${fioHtml}</div>
  </div>
</section>`;
}

function renderAcknowledgement(
  model: PersonnelOrderPrintViewModel,
  language: PersonnelOrderPrintLanguage,
): string {
  if (!model.acknowledgements.length) return "";
  const dictionaries = printDictionariesForLanguage(language);
  const primary = primaryPrintDictionary(language);
  const heading = dictionaries
    .map((dict) => `<div>${escapePersonnelOrderPrintHtml(dict.familiarization)}</div>`)
    .join("");

  const rows = model.acknowledgements
    .map((row, index) => {
      const name =
        String(row.employeeName || "").trim() || `№${row.employeeId ?? index + 1}`;
      return `<div class="personnel-order-print-ack-row">
  <div class="personnel-order-print-ack-grid">
    <div>
      <div class="personnel-order-print-signature-line">&nbsp;</div>
      <div class="personnel-order-print-ack-caption">${escapePersonnelOrderPrintHtml(primary.signatureCaption)}</div>
    </div>
    <div class="personnel-order-print-ack-name">${escapePersonnelOrderPrintHtml(name)}</div>
    <div class="personnel-order-print-ack-date">${escapePersonnelOrderPrintHtml(primary.familiarizationDate)}</div>
  </div>
</div>`;
    })
    .join("");

  return `<section class="personnel-order-print-block personnel-order-print-acknowledgement" data-testid="personnel-order-print-acknowledgement">
  <div class="personnel-order-print-ack-heading">${heading}</div>
  ${rows}
</section>`;
}

/**
 * Shared print document markup (article) for HTML preview and official PDF.
 * Uses ViewModel + locale/item helpers — no React / react-dom/server.
 */
export function buildPersonnelOrderPrintDocumentHtml(
  model: PersonnelOrderPrintViewModel,
  language: PersonnelOrderPrintLanguage,
): string {
  return `<article class="personnel-order-print-document" data-testid="personnel-order-print-document" data-language="${escapePersonnelOrderPrintHtml(language)}" data-status="${escapePersonnelOrderPrintHtml(model.status)}">
  ${renderStatusMark(model, language)}
  <div class="personnel-order-print-body">
    ${renderHeader(model, language)}
    ${renderItems(model, language)}
    ${renderBasis(model, language)}
    ${renderSignature(model, language)}
    ${renderAcknowledgement(model, language)}
  </div>
</article>`;
}
