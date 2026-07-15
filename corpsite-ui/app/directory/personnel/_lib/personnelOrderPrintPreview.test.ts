import { describe, expect, it, vi } from "vitest";

import {
  openPersonnelOrderPrintPreview,
  PERSONNEL_ORDER_PRINT_POPUP_BLOCKED_MESSAGE,
} from "./personnelOrderPrintPreview.client";

describe("personnelOrderPrintPreview", () => {
  it("reports blocked pop-up when window.open returns null", () => {
    vi.stubGlobal("open", vi.fn(() => null));

    expect(openPersonnelOrderPrintPreview(42, "ru")).toBe(false);
    expect(PERSONNEL_ORDER_PRINT_POPUP_BLOCKED_MESSAGE).toContain("всплывающ");

    vi.unstubAllGlobals();
  });

  it("returns true when preview window opens", () => {
    vi.stubGlobal("open", vi.fn(() => ({}) as Window));

    expect(openPersonnelOrderPrintPreview(42, "ru")).toBe(true);

    vi.unstubAllGlobals();
  });
});
