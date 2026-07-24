export const INTAKE_PDF_DOCUMENT_CSS = `
.intake-pdf-document {
  margin: 0 auto;
  background: #fff;
  color: #000;
  font-family: "Times New Roman", Times, serif;
  font-size: 10pt;
  line-height: 1.35;
  box-sizing: border-box;
}

.intake-pdf-document *,
.intake-pdf-document *::before,
.intake-pdf-document *::after {
  box-sizing: border-box;
}

.intake-pdf-document .intake-pdf-header {
  margin-bottom: 1rem;
}

.intake-pdf-document .intake-pdf-header-top {
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  align-items: start;
  gap: 0.5rem;
  margin-bottom: 0.75rem;
}

.intake-pdf-document .intake-pdf-organization {
  margin: 0;
  min-height: 1.2em;
  font-size: 10pt;
  font-weight: 600;
}

.intake-pdf-document .intake-pdf-title-block {
  justify-self: center;
  text-align: center;
}

.intake-pdf-document .intake-pdf-title {
  margin: 0;
  padding: 0;
  font-size: 11pt;
  font-weight: 700;
  text-align: center;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: #000;
  background: transparent;
  white-space: nowrap;
}

.intake-pdf-document .intake-pdf-generated-date {
  margin: 0.2rem 0 0;
  font-size: 10pt;
  text-align: center;
}

.intake-pdf-document .intake-pdf-index-box {
  justify-self: end;
  width: 4.5cm;
}

.intake-pdf-document .intake-pdf-index-values {
  width: 100%;
  margin: 0;
}

.intake-pdf-document .intake-pdf-index-values td {
  width: 50%;
  height: 1.1cm;
  padding: 0.1rem 0.25rem;
  text-align: center;
  vertical-align: middle;
}

.intake-pdf-document .intake-pdf-alphabet {
  font-size: 20pt;
  font-weight: 700;
  text-align: center;
  vertical-align: middle;
  line-height: 1;
}

.intake-pdf-document .intake-pdf-index-labels {
  display: grid;
  grid-template-columns: 1fr 1fr;
  margin-top: 0.1rem;
  font-size: 8pt;
  text-align: center;
}

.intake-pdf-document .intake-pdf-header-main {
  display: flex;
  align-items: stretch;
  gap: 0;
}

.intake-pdf-document .intake-pdf-photo-slot {
  flex: 0 0 auto;
  box-sizing: border-box;
  width: 3cm;
  height: 4cm;
  border: 1px solid #000;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  overflow: hidden;
  text-align: center;
}

.intake-pdf-document .intake-pdf-photo-caption {
  padding: 0.25rem;
  font-size: 8pt;
  line-height: 1.2;
  color: #333;
}

.intake-pdf-document .intake-pdf-photo-image {
  width: 3cm;
  height: 4cm;
  max-width: 100%;
  max-height: 100%;
  object-fit: cover;
  object-position: center;
  display: block;
}

.intake-pdf-document .intake-pdf-header-fields {
  flex: 1 1 auto;
  margin: 0;
  height: 4cm;
  table-layout: fixed;
}

.intake-pdf-document .intake-pdf-header-fields tbody {
  height: 100%;
}

.intake-pdf-document .intake-pdf-header-fields tr {
  height: 20%;
}

.intake-pdf-document .intake-pdf-header-fields td {
  padding: 0.08rem 0.25rem;
  vertical-align: middle;
  line-height: 1.15;
}

.intake-pdf-document .intake-pdf-header-fields .intake-pdf-field-label {
  width: 27%;
  font-weight: 600;
  white-space: nowrap;
}

.intake-pdf-document .intake-pdf-header-fields .intake-pdf-split-row td:nth-child(1) {
  width: 8%;
  font-weight: 600;
  white-space: nowrap;
}

.intake-pdf-document .intake-pdf-header-fields .intake-pdf-split-row td:nth-child(2) {
  width: 16%;
}

.intake-pdf-document .intake-pdf-header-fields .intake-pdf-split-row td:nth-child(3) {
  width: 20%;
  font-weight: 600;
  white-space: nowrap;
}

.intake-pdf-document .intake-pdf-header-fields .intake-pdf-split-row td:nth-child(4) {
  width: 16%;
}

.intake-pdf-document .intake-pdf-section {
  margin-top: 1rem;
  break-inside: avoid-page;
  page-break-inside: avoid;
}

.intake-pdf-document .intake-pdf-section-title {
  margin: 0 0 0.5rem;
  font-size: 11pt;
  font-weight: 700;
}

.intake-pdf-document .intake-pdf-subsection-title {
  margin: 0.75rem 0 0.35rem;
  font-size: 10pt;
  font-weight: 700;
}

.intake-pdf-document table {
  width: 100%;
  border-collapse: collapse;
  table-layout: fixed;
  break-inside: auto;
  page-break-inside: auto;
}

.intake-pdf-document thead {
  display: table-header-group;
}

.intake-pdf-document tr {
  break-inside: avoid;
  page-break-inside: avoid;
}

.intake-pdf-document th,
.intake-pdf-document td {
  border: 1px solid #000;
  padding: 0.35rem 0.45rem;
  vertical-align: top;
  word-break: break-word;
  overflow-wrap: anywhere;
  hyphens: auto;
}

.intake-pdf-document th {
  font-weight: 700;
  background: #f5f5f5;
  text-align: left;
}

.intake-pdf-document .intake-pdf-fields td:first-child {
  width: 34%;
  font-weight: 600;
}

.intake-pdf-document .intake-pdf-empty {
  margin: 0;
  color: #333;
  font-style: italic;
}

.intake-pdf-document .intake-pdf-summary-block {
  margin: 0 0 0.75rem;
  padding: 0.6rem 0.75rem;
  border: 1px solid #666;
  background: #fafafa;
  break-inside: avoid-page;
  page-break-inside: avoid;
}

.intake-pdf-document .intake-pdf-summary-title {
  margin: 0;
  font-size: 10pt;
  font-weight: 700;
}

.intake-pdf-document .intake-pdf-summary-value {
  margin: 0.35rem 0 0;
  font-size: 12pt;
  font-weight: 700;
}

.intake-pdf-document .intake-pdf-summary-detail,
.intake-pdf-document .intake-pdf-summary-meta {
  margin: 0.25rem 0 0;
  font-size: 9pt;
  color: #333;
}

@page {
  size: A4;
  margin: 15mm 18mm 18mm 25mm;
}
`;
