import {readFileSync, readdirSync, writeFileSync} from "node:fs";
import path from "node:path";
import {expect, it} from "vitest";
import {buildPersonnelOrderPrintViewModel} from "./personnelOrderPrintViewModel";
import {buildPersonnelOrderPrintDocumentHtml} from "./personnelOrderPrintDocumentHtml";
import type {PersonnelOrderDetailResponse, PersonnelOrderEditorialState} from "./personnelOrdersApi.client";

type Fixture = {detail: PersonnelOrderDetailResponse; editorial: PersonnelOrderEditorialState};
const synthetic = {
  detail: {
    order: {order_id: 1, order_type_code: "COMPOSITE", order_class: "PERSONNEL", status: "DRAFT", source_mode: "MANUAL", created_by: 1},
    items: ["TRANSFER", "SUPPLEMENTARY_PAY"].map((code, index) => ({item_id: index + 1, item_number: index + 1, item_type_code: code, item_status: "ACTIVE", employee_id: 7, employee_name: "Тестовый Сотрудник", payload: {}})),
    localized_texts: [], attachments: [], prints: [], events: [],
  },
  editorial: {
    order_id: 1, order_status: "DRAFT", editable: true,
    order_blocks: ["ru", "kk"].flatMap(locale => [
      {locale, block_type: "title", generated_text: `Common title ${locale}`},
      {locale, block_type: "preamble", generated_text: `Common preamble ${locale}`},
    ]),
    items: [1, 2].map(id => ({order_item_id: id, blocks: ["ru", "kk"].flatMap(locale => [
      {locale, block_type: "body", generated_text: `Saved item ${id} ${locale}`, override_text: id === 2 && locale === "ru" ? "Ручная правка" : null},
      {locale, block_type: "basis", generated_text: `Basis ${id} ${locale}`},
    ])})),
  },
} as unknown as Fixture;

const fixtureDir = process.env.COMPOSITE_PRINT_FIXTURE_DIR;
const fixtures: Array<[string, Fixture]> = [["synthetic composite", synthetic]];
if (fixtureDir) {
  for (const name of readdirSync(fixtureDir).filter(name => name.endsWith(".json"))) {
    fixtures.push([name, JSON.parse(readFileSync(path.join(fixtureDir, name), "utf8")) as Fixture]);
  }
  if (fixtures.length !== 5) throw new Error("Expected all four local database scenarios before checking print.");
}

for (const [name, fixture] of fixtures) {
  it.each(["ru", "kk"] as const)(`${name}: prints one common header and each saved item (%s)`, language => {
    const model = buildPersonnelOrderPrintViewModel(fixture.detail, {editorial: fixture.editorial});
    const html = buildPersonnelOrderPrintDocumentHtml(model, language);
    const document = new DOMParser().parseFromString(html, "text/html");
    expect(document.querySelectorAll('[data-testid="personnel-order-print-header"]')).toHaveLength(1);
    expect(document.querySelectorAll(".personnel-order-print-preamble")).toHaveLength(1);
    expect(model.items).toHaveLength(2);
    expect(model.items[0].employeeId).toBe(model.items[1].employeeId);
    expect(model.acknowledgements).toHaveLength(1);
    for (const item of model.items) {
      const block = fixture.editorial.items.find(group => group.order_item_id === item.itemId)?.blocks.find(block => block.locale === language && block.block_type === "body");
      const expected = block?.override_text || block?.generated_text;
      expect(expected).toBeTruthy();
      expect(document.querySelector(`[data-testid="personnel-order-print-item-${item.itemId}"]`)?.textContent).toContain(expected);
    }
    expect(document.body.textContent).not.toContain("{{");
    if (fixtureDir && name.endsWith(".json")) writeFileSync(path.join(fixtureDir, `${name.slice(0, -5)}-${language}.html`), html, "utf8");
  });
}
