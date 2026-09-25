import type { PersonnelOrderPrintLanguage } from "./personnelOrderPrintLanguage";
import { formatPersonnelOrderPrintDateLines } from "./personnelOrderPrintFormat";
import { renderPersonnelOrderPrintItemText } from "./personnelOrderPrintItemText";
import {
  primaryPrintDictionary,
  printDictionariesForLanguage,
  statusMarkLinesForLanguage,
} from "./personnelOrderPrintLocale";
import { resolveLocalizedLines } from "./personnelOrderPrintLocalized";
import type { LocalizedText } from "./personnelOrderPrintLocalized";
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

/** Legacy editorial preambles may embed a directive; render it once below. */
export function preambleIncludesOrderVerb(
  preamble: LocalizedText,
  language: PersonnelOrderPrintLanguage,
): boolean {
  const lines = resolveLocalizedLines(preamble, language);
  const joined = lines.join(" ").toUpperCase();
  if (language === "kk") return joined.includes("БҰЙЫРАМЫН");
  if (language === "ru") return joined.includes("ПРИКАЗЫВАЮ");
  return joined.includes("ПРИКАЗЫВАЮ") || joined.includes("БҰЙЫРАМЫН");
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
  // An editorial override belongs only to its own locale.  Do not fall back
  // from a Kazakh override to a Russian print (or the reverse).
  const manual = (locale: "kk" | "ru") => String(item.body?.[locale] || "").trim() || null;
  const lines = language === "kk"
    ? (manual("kk") ? [manual("kk")!] : renderPersonnelOrderPrintItemText(item.context, "kk"))
    : language === "ru"
      ? (manual("ru") ? [manual("ru")!] : renderPersonnelOrderPrintItemText(item.context, "ru"))
      : [
        ...(manual("kk") ? [manual("kk")!] : renderPersonnelOrderPrintItemText(item.context, "kk")),
        ...(manual("ru") ? [manual("ru")!] : renderPersonnelOrderPrintItemText(item.context, "ru")),
      ];
  const tenure = item.itemTypeCode === "RETURN_FROM_CHILDCARE_LEAVE"
    ? []
    : language === "kk"
      ? ["Жұмыс өтілі әлі анықталмаған."]
      : language === "ru"
        ? ["Стаж работы ещё не определён."]
        : ["Жұмыс өтілі әлі анықталмаған.", "Стаж работы ещё не определён."];
  const body = [...lines, ...tenure]
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
  const preambleLines = model.preamble
    ? resolveLocalizedLines(model.preamble, language).filter((line) => !isOrderVerbLine(line))
    : [];
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
  const rawLines = model.basis.flatMap((entry) => resolveLocalizedLines(entry, language));
  const isChildcareReturn = String(model.documentTypeCode).toUpperCase() === "RETURN_FROM_CHILDCARE_LEAVE";
  const joined = rawLines.join(" ").toLocaleLowerCase(language === "kk" ? "kk-KZ" : "ru-RU");
  const personalApplication = language === "kk"
    ? joined.includes("жеке") && joined.includes("өтініш")
    : joined.includes("личн") && joined.includes("заявлен");
  // Legacy blocks can carry an old label or employee name. The print owns the
  // label, so canonicalize this approved basis before rendering it.
  const lines = isChildcareReturn && personalApplication
    ? [language === "kk" ? "Жеке өтініші." : "Личное заявление."]
    : rawLines;
  if (!lines.length) return "";

  const headings = dictionaries
    .map((dict) => `<div>${escapePersonnelOrderPrintHtml(
      isChildcareReturn ? (language === "kk" ? "Негіз" : "Основание") : dict.basis,
    )}:</div>`)
    .join("");
  const list = lines
    .map((line) => `<li>${escapePersonnelOrderPrintHtml(line)}</li>`)
    .join("");

  return `<section class="personnel-order-print-block personnel-order-print-basis" data-testid="personnel-order-print-basis">
  <div class="personnel-order-print-basis-heading">${headings}</div>
  <ul class="personnel-order-print-basis-list">${list}</ul>
</section>`;
}

function renderClosing(
  model: PersonnelOrderPrintViewModel,
  language: PersonnelOrderPrintLanguage,
): string {
  if (String(model.documentTypeCode).toUpperCase() === "RETURN_FROM_CHILDCARE_LEAVE") return "";
  if (!model.closing) return "";
  const lines = resolveLocalizedLines(model.closing, language);
  if (!lines.length) return "";
  const body = lines
    .map((line) => `<p class="m-0">${escapePersonnelOrderPrintHtml(line)}</p>`)
    .join("");
  return `<section class="personnel-order-print-block personnel-order-print-closing" data-testid="personnel-order-print-closing">${body}</section>`;
}

function renderTailDate(
  model: PersonnelOrderPrintViewModel,
  language: PersonnelOrderPrintLanguage,
): string {
  const dateLines = formatPersonnelOrderPrintDateLines(model.orderDate, language);
  const hasDate = dateLines.some((line) => String(line || "").trim() && line !== "—");
  if (!hasDate) return "";
  return `<section class="personnel-order-print-block personnel-order-print-tail-date" data-testid="personnel-order-print-tail-date">${linesHtml(dateLines)}</section>`;
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
    <div class="personnel-order-print-signature-position" data-testid="personnel-order-print-signature-position">${position}</div>
    <div class="personnel-order-print-signature-line" data-testid="personnel-order-print-signature-line">&nbsp;</div>
    <div class="personnel-order-print-signature-fio" data-testid="personnel-order-print-signature-fio">${fioHtml}</div>
  </div>
</section>`;
}

function renderAcknowledgement(
  model: PersonnelOrderPrintViewModel,
  language: PersonnelOrderPrintLanguage,
): string {
  const acknowledgementRows = model.acknowledgements.length
    ? model.acknowledgements
    : [{ employeeId: null, employeeName: null, acknowledgedOn: null }];
  const rows = acknowledgementRows
    .map((row) => {
      const fullName = String(row.employeeName || "").trim();
      const parts = fullName.split(/\s+/).filter(Boolean);
      const ruName = parts.length >= 2 ? `${parts[0]} ${parts[1][0]}.` : "";
      const kkName = parts.length >= 2 ? `${parts[1][0]}. ${parts[0]}` : "";
      const date = row.acknowledgedOn
        ? new Date(`${row.acknowledgedOn}T00:00:00`).toLocaleDateString("ru-RU")
        : null;
      const locales: Array<"kk" | "ru"> = language === "kk-ru" ? ["kk", "ru"] : [language];
      const content = locales.map((locale) => {
        const isKk = locale === "kk";
        const familiarization = isKk ? "Бұйрықпен таныстым:" : "С приказом ознакомлен(а):";
        const formattedName = isKk ? kkName : ruName;
        const dateLine = date || (isKk ? "«___» ______________ 20___ ж." : "«___» ______________ 20___ г.");
        return `<div class="personnel-order-print-ack-name">${escapePersonnelOrderPrintHtml(familiarization)} ___________________&nbsp;&nbsp;${escapePersonnelOrderPrintHtml(formattedName)}</div>
    <div class="personnel-order-print-ack-date">${escapePersonnelOrderPrintHtml(dateLine)}</div>`;
      }).join("");
      return `<div class="personnel-order-print-ack-row">
  <div class="personnel-order-print-ack-grid">
    ${content}
  </div>
</div>`;
    })
    .join("");

  return `<section class="personnel-order-print-block personnel-order-print-acknowledgement" data-testid="personnel-order-print-acknowledgement">
  ${rows}
</section>`;
}

function isOrderVerbLine(value: string): boolean {
  const normalized = value.trim().toUpperCase().replace(/:$/, "");
  return normalized === "ПРИКАЗЫВАЮ" || normalized === "БҰЙЫРАМЫН";
}

function renderExecutor(model: PersonnelOrderPrintViewModel, language: PersonnelOrderPrintLanguage): string {
  const label = language === "kk" ? "Орындаушы" : "Исполнитель";
  return `<section class="personnel-order-print-block personnel-order-print-executor" data-testid="personnel-order-print-executor">${escapePersonnelOrderPrintHtml(label)}: ${escapePersonnelOrderPrintHtml(model.executorName)}</section>`;
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
    ${renderClosing(model, language)}
    <div class="personnel-order-print-tail">
      ${renderTailDate(model, language)}
      ${renderSignature(model, language)}
      ${renderAcknowledgement(model, language)}
      ${renderExecutor(model, language)}
    </div>
  </div>
</article>`;
}
