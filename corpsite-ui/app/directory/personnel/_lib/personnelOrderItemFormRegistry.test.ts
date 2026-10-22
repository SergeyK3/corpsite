import { describe, expect, it } from "vitest";

import {
  detectUiItemTypeFromRecord,
  getItemFormRegistry,
  itemFormTypeOptionsForOrder,
  requiresEmployeeForFormType,
  resolveBackendItemTypeCode,
  resolveDefaultItemFormTypeForOrder,
  usesActiveEmployeeSearch,
} from "./personnelOrderItemFormRegistry";

describe("personnelOrderItemFormRegistry", () => {
  it("maps TRANSFER with full target placement", () => {
    const config = getItemFormRegistry("TRANSFER");
    expect(config?.showCurrentPlacement).toBe(true);
    expect(config?.showTargetPlacement).toBe(true);
    expect(config?.clearTargetOnEmployeeChange).toBe(true);
    expect(resolveBackendItemTypeCode("TRANSFER")).toBe("TRANSFER");
  });

  it("maps RATE_CHANGE to backend TRANSFER without target org", () => {
    const config = getItemFormRegistry("RATE_CHANGE");
    expect(config?.showTargetPlacement).toBe(false);
    expect(config?.showTargetRate).toBe(true);
    expect(resolveBackendItemTypeCode("RATE_CHANGE")).toBe("TRANSFER");
  });

  it("maps TERMINATION without target placement", () => {
    const config = getItemFormRegistry("TERMINATION");
    expect(config?.showTerminationReason).toBe(true);
    expect(config?.showTargetPlacement).toBe(false);
  });

  it("keeps HIRE as legacy pending without employee requirement", () => {
    const config = getItemFormRegistry("HIRE");
    expect(config?.hireLegacyPending).toBe(true);
    expect(config?.employeeRequired).toBe(false);
    expect(usesActiveEmployeeSearch("HIRE")).toBe(false);
  });

  it("requires active employee search for existing-employee actions", () => {
    expect(usesActiveEmployeeSearch("TRANSFER")).toBe(true);
    expect(usesActiveEmployeeSearch("TERMINATION")).toBe(true);
    expect(usesActiveEmployeeSearch("RATE_CHANGE")).toBe(true);
    expect(requiresEmployeeForFormType("TRANSFER")).toBe(true);
    expect(requiresEmployeeForFormType("HIRE")).toBe(false);
  });

  it("detects RATE_CHANGE UI type from TRANSFER payload with to_rate only", () => {
    expect(
      detectUiItemTypeFromRecord({
        item_id: 1,
        order_id: 1,
        item_number: 1,
        item_type_code: "TRANSFER",
        item_status: "ACTIVE",
        payload: { to_rate: 0.5 },
      }),
    ).toBe("RATE_CHANGE");
  });

  it("keeps TRANSFER when org or position target is present", () => {
    expect(
      detectUiItemTypeFromRecord({
        item_id: 1,
        order_id: 1,
        item_number: 1,
        item_type_code: "TRANSFER",
        item_status: "ACTIVE",
        payload: { to_org_unit_id: 10, to_rate: 1 },
      }),
    ).toBe("TRANSFER");
  });

  it.each([{org_unit_id:43},{position_id:6},{org_unit_ru:"Хирургия 2"},{position_kk:"Дәрігер"}])("reopens nested TRANSFER placement %j despite the compatibility to_rate", transfer => {
    const saved = JSON.parse(JSON.stringify({item_id:1,order_id:1,item_number:1,item_type_code:"TRANSFER",item_status:"ACTIVE",payload:{transfer:{...transfer,rate:1},to_rate:1}}));
    expect(detectUiItemTypeFromRecord(saved)).toBe("TRANSFER");
  });

  it.each([null,{},[],{rate:0.5},{org_unit_ru:" "}])("preserves legacy RATE_CHANGE with no nested destination %j",transfer=>{
    expect(detectUiItemTypeFromRecord({item_id:1,order_id:1,item_number:1,item_type_code:"TRANSFER",item_status:"ACTIVE",payload:{transfer,to_employment_rate:0.5}})).toBe("RATE_CHANGE");
  });

  it.each(["HIRE","TERMINATION","CONCURRENT_DUTY_START","CONCURRENT_DUTY_END","SUPPLEMENTARY_PAY","LEAVE.ANNUAL.GRANT","LEAVE.UNPAID.GRANT","LEAVE.CHILDCARE.GRANT","LEAVE.ANNUAL.RECALL","RETURN_FROM_CHILDCARE_LEAVE"])("preserves existing type %s",item_type_code=>{
    expect(detectUiItemTypeFromRecord({item_id:1,order_id:1,item_number:1,item_type_code,item_status:"ACTIVE",payload:{to_rate:1,transfer:{org_unit_id:43}}})).toBe(item_type_code);
  });

  it("defaults item type from order type", () => {
    expect(resolveDefaultItemFormTypeForOrder("HIRE")).toBe("HIRE");
    expect(resolveDefaultItemFormTypeForOrder("COMPOSITE")).toBe("TRANSFER");
  });

  it("limits item type options for simple orders", () => {
    const hireOptions = itemFormTypeOptionsForOrder("HIRE");
    expect(hireOptions.map((row) => row.value)).toEqual(["HIRE"]);
    const transferOptions = itemFormTypeOptionsForOrder("TRANSFER");
    expect(transferOptions.map((row) => row.value)).toEqual(["TRANSFER", "RATE_CHANGE", "CONCURRENT_DUTY_START"]);
  });

  it("uses HR-friendly field order for HIRE", () => {
    const config = getItemFormRegistry("HIRE");
    expect(config?.fieldSectionOrder).toEqual([
      "item_type",
      "org_placement",
      "effective_date",
      "employee",
      "additional",
    ]);
  });
});
