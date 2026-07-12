/**
 * Shared print-document CSS for HTML preview and official PDF.
 * Layout utilities are scoped under `.personnel-order-print-document` to avoid UI leakage.
 */
export const PERSONNEL_ORDER_PRINT_DOCUMENT_CSS = `
.personnel-order-print-document {
  position: relative;
  margin: 0 auto;
  background: #fff;
  color: #000;
  font-family: "Times New Roman", Times, serif;
  font-size: 14pt;
  line-height: 1.35;
  box-sizing: border-box;
}

.personnel-order-print-document *,
.personnel-order-print-document *::before,
.personnel-order-print-document *::after {
  box-sizing: border-box;
}

.personnel-order-print-document .personnel-order-print-body {
  position: relative;
  z-index: 10;
  display: flex;
  flex-direction: column;
  gap: 2rem;
}

.personnel-order-print-document .personnel-order-print-header {
  text-align: center;
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.personnel-order-print-document .personnel-order-print-org {
  margin: 0 auto;
  max-width: 90%;
  font-size: 14pt;
  font-weight: 700;
  line-height: 1.35;
  letter-spacing: 0.025em;
}

.personnel-order-print-document .personnel-order-print-org > div + div,
.personnel-order-print-document .personnel-order-print-doc-type > div + div,
.personnel-order-print-document .personnel-order-print-title > div + div,
.personnel-order-print-document .personnel-order-print-order-verb > div + div,
.personnel-order-print-document .personnel-order-print-basis-heading > div + div,
.personnel-order-print-document .personnel-order-print-ack-heading > div + div,
.personnel-order-print-document .personnel-order-print-signature-position > div + div {
  margin-top: 0.125rem;
}

.personnel-order-print-document .personnel-order-print-doc-type {
  padding-top: 0.25rem;
  font-size: 16pt;
  font-weight: 700;
  line-height: 1.3;
  text-transform: uppercase;
  letter-spacing: 0.18em;
}

.personnel-order-print-document .personnel-order-print-meta {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1.5rem;
  padding-top: 0.25rem;
  text-align: left;
  align-items: start;
}

.personnel-order-print-document .personnel-order-print-meta-number {
  font-weight: 500;
}

.personnel-order-print-document .personnel-order-print-meta-date {
  text-align: right;
}

.personnel-order-print-document .personnel-order-print-title {
  padding-top: 0.25rem;
  font-size: 14pt;
  font-weight: 700;
  line-height: 1.35;
}

.personnel-order-print-document .personnel-order-print-items {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.personnel-order-print-document .personnel-order-print-preamble {
  text-align: left;
  display: flex;
  flex-direction: column;
  gap: 0.375rem;
}

.personnel-order-print-document .personnel-order-print-order-verb {
  text-align: center;
  text-transform: uppercase;
  letter-spacing: 0.025em;
  font-size: 14pt;
  font-weight: 700;
  line-height: 1.35;
}

.personnel-order-print-document .personnel-order-print-items-list {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.personnel-order-print-document .personnel-order-print-item-grid {
  display: grid;
  grid-template-columns: 2rem minmax(0, 1fr);
  column-gap: 0.25rem;
}

.personnel-order-print-document .personnel-order-print-item-num {
  padding-top: 0.125rem;
  text-align: right;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

.personnel-order-print-document .personnel-order-print-item-body {
  min-width: 0;
  text-align: left;
  display: flex;
  flex-direction: column;
  gap: 0.625rem;
  orphans: 2;
  widows: 2;
}

.personnel-order-print-document .personnel-order-print-item-body p {
  orphans: 2;
  widows: 2;
}

.personnel-order-print-document .m-0 {
  margin: 0;
}

.personnel-order-print-document .personnel-order-print-basis {
  margin-top: 1.5rem;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.personnel-order-print-document .personnel-order-print-basis-heading {
  font-weight: 600;
}

.personnel-order-print-document .personnel-order-print-basis-list {
  margin: 0;
  padding-left: 1.25rem;
  list-style: disc;
  text-align: left;
  line-height: 1.625;
}

.personnel-order-print-document .personnel-order-print-basis-list > li + li {
  margin-top: 0.25rem;
}

.personnel-order-print-document .personnel-order-print-closing {
  margin-top: 1.5rem;
  text-align: left;
  display: flex;
  flex-direction: column;
  gap: 0.375rem;
}

.personnel-order-print-document .personnel-order-print-tail {
  display: flex;
  flex-direction: column;
  gap: 3rem;
  break-inside: avoid;
  page-break-inside: avoid;
}

.personnel-order-print-document .personnel-order-print-signature,
.personnel-order-print-document .personnel-order-print-acknowledgement {
  margin-top: 0;
}

.personnel-order-print-document .personnel-order-print-signature-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.2fr) minmax(7rem, 1fr) minmax(0, 1.2fr);
  align-items: end;
  column-gap: 1rem;
  row-gap: 0.25rem;
}

.personnel-order-print-document .personnel-order-print-signature-position {
  min-width: 0;
  line-height: 1.375;
}

.personnel-order-print-document .personnel-order-print-signature-line {
  border-bottom: 1px solid #000;
  padding-bottom: 0.125rem;
  text-align: center;
  line-height: 1;
}

.personnel-order-print-document .personnel-order-print-signature-fio {
  min-width: 0;
  text-align: right;
  font-weight: 500;
  line-height: 1.375;
}

.personnel-order-print-document .personnel-order-print-fio-placeholder {
  display: inline-block;
  min-width: 8rem;
}

.personnel-order-print-document .personnel-order-print-spacer {
  min-height: 1.25rem;
}

.personnel-order-print-document .personnel-order-print-acknowledgement {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.personnel-order-print-document .personnel-order-print-ack-heading {
  font-weight: 500;
}

.personnel-order-print-document .personnel-order-print-ack-row {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.personnel-order-print-document .personnel-order-print-ack-grid {
  display: grid;
  grid-template-columns: minmax(7rem, 1fr) minmax(0, 1.6fr) auto;
  align-items: end;
  column-gap: 1rem;
  row-gap: 0.25rem;
}

.personnel-order-print-document .personnel-order-print-ack-caption {
  padding-top: 0.125rem;
  text-align: center;
  color: #52525b;
  font-size: 11pt;
  line-height: 1.3;
}

.personnel-order-print-document .personnel-order-print-ack-name {
  padding-bottom: 1rem;
  font-weight: 500;
  line-height: 1.375;
}

.personnel-order-print-document .personnel-order-print-ack-date {
  padding-bottom: 1rem;
  white-space: nowrap;
}

.personnel-order-print-document .personnel-order-print-block,
.personnel-order-print-document .personnel-order-print-item,
.personnel-order-print-document .personnel-order-print-ack-row,
.personnel-order-print-document .personnel-order-print-signature,
.personnel-order-print-document .personnel-order-print-closing {
  break-inside: avoid;
  page-break-inside: avoid;
}

.personnel-order-print-document .personnel-order-print-watermark {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  pointer-events: none;
  z-index: 0;
  color: #d4d4d8;
  -webkit-print-color-adjust: exact;
  print-color-adjust: exact;
}

.personnel-order-print-document .personnel-order-print-watermark > div {
  transform: rotate(-28deg);
  text-align: center;
  font-size: 2.25rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: rgba(161, 161, 170, 0.55);
  user-select: none;
  line-height: 1.15;
}

.personnel-order-print-document .personnel-order-print-watermark .leading-tight {
  line-height: 1.25;
}
`;

/** Full standalone CSS for Playwright setContent (includes @page). */
export const PERSONNEL_ORDER_PDF_DOCUMENT_CSS = `
@page {
  size: A4;
  margin: 15mm 18mm 18mm 25mm;
}

html, body {
  margin: 0;
  padding: 0;
  background: #fff;
  color: #000;
}

${PERSONNEL_ORDER_PRINT_DOCUMENT_CSS}
`;
