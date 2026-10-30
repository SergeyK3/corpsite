import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { educationPrintModel } from "./educationPrint";
import { buildPersonnelOrderPrintDocumentHtml } from "./personnelOrderPrintDocumentHtml";
import type { PersonnelOrderPrintViewModel } from "./personnelOrderPrintViewModel";
import PersonnelOrderPrintLanguageDialog from "../_components/print/PersonnelOrderPrintLanguageDialog";
import PersonnelOrderPrintToolbar from "../_components/print/PersonnelOrderPrintToolbar";

function model(): PersonnelOrderPrintViewModel {
  return { orderId: 1, orderNumber: "TEST", orderDate: "2026-10-29", status: "DRAFT", statusMark: "draft",
    documentTypeCode: "EDUCATION_INFORMATION_CHANGE", organization: { ru: "RU organization" },
    title: { ru: "RU title", kk: "KK title" }, preamble: { ru: "RU preamble", kk: "KK preamble" },
    placeOfIssue: { ru: "RU city", kk: "KK city" }, closing: null, signatory: { position: { ru: "RU signatory" }, fio: null },
    items: [{ itemId: 1, itemNumber: 1, itemTypeCode: "EDUCATION_INFORMATION_CHANGE", employeeId: null, employeeName: "TEST", effectiveDate: "2026-11-01",
      context: { itemNumber: 1, itemTypeCode: "EDUCATION_INFORMATION_CHANGE", employeeName: "TEST", effectiveDate: "2026-11-01", orgUnitName: null, positionName: null, toOrgUnitName: null, toPositionName: null, rate: null, toRate: null, concurrentRate: null, remainingRate: null, totalRate: null, terminationReason: null, payload: {} },
      body: { ru: "RU body", kk: "KK body" }, basis: { ru: "RU basis", kk: "KK basis" } }],
    basis: [{ ru: "RU basis", kk: "KK basis" }], acknowledgements: [], executorName: "TEST" };
}
afterEach(cleanup);

it.each(["ru", "kk"] as const)("prints only the selected %s texts without fallback or snapshot mutation", language => {
  const source = model(), original = structuredClone(source);
  const html = buildPersonnelOrderPrintDocumentHtml(source, language);
  for (const part of ["title", "preamble", "body", "basis", "city"]) {
    expect(html).toContain(language.toUpperCase() + " " + part);
    expect(html).not.toContain((language === "ru" ? "KK" : "RU") + " " + part);
  }
  if (language === "kk") { expect(html).not.toContain("RU organization"); expect(html).not.toContain("RU signatory"); }
  expect(source).toEqual(original);
});

it("blocks bilingual education rendering and preserves other document types", () => {
  expect(() => buildPersonnelOrderPrintDocumentHtml(model(), "kk-ru")).toThrow(/отдельные документы RU и KK/);
  const other = { ...model(), documentTypeCode: "SERVICE_LENGTH_CHANGE" };
  expect(educationPrintModel(other, "kk-ru")).toBe(other);
  const html = buildPersonnelOrderPrintDocumentHtml(other, "kk-ru");
  expect(html).toContain("RU title"); expect(html).toContain("KK title");
});

it.each(["title", "preamble", "body", "basis"])("blocks missing KK %s instead of substituting RU", part => {
  const source = model();
  if (part === "title") source.title.kk = null;
  if (part === "preamble") source.preamble!.kk = null;
  if (part === "body") source.items[0].body!.kk = null;
  if (part === "basis") source.items[0].basis!.kk = null;
  expect(() => buildPersonnelOrderPrintDocumentHtml(source, "kk")).toThrow(/Текст другого языка не подставляется/);
});

it("offers separate RU and KK documents in the education dialog and toolbar", () => {
  const confirm = vi.fn();
  const view = render(<PersonnelOrderPrintLanguageDialog open onClose={vi.fn()} onConfirm={confirm} documentTypeCode="EDUCATION_INFORMATION_CHANGE" initialLanguage="kk-ru" />);
  expect(screen.getAllByRole("radio")).toHaveLength(2);
  expect(screen.queryByLabelText("Қазақша / Русский")).not.toBeInTheDocument();
  fireEvent.click(screen.getByLabelText("Қазақша")); fireEvent.click(screen.getByTestId("personnel-order-pdf-open"));
  expect(confirm).toHaveBeenCalledWith("kk", "pdf");
  view.unmount();
  render(<PersonnelOrderPrintToolbar backHref="/" language="kk-ru" onLanguageChange={vi.fn()} onOpenPdf={vi.fn()} documentTypeCode="EDUCATION_INFORMATION_CHANGE" />);
  expect(screen.queryByRole("option", { name: "Қазақша / Русский" })).not.toBeInTheDocument();
  expect(screen.getByTestId("personnel-order-print-pdf-button")).toBeDisabled();
  expect(screen.getByTestId("personnel-order-print-button")).toBeDisabled();
});
