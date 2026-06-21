// FILE: corpsite-ui/app/admin/system/_lib/userLinkageOperationsLabels.test.ts
import { describe, expect, it } from "vitest";

import {
  diagnosisLabel,
  diagnosisTone,
  itemActionLabel,
  itemStatusLabel,
  operationLabel,
  recommendedActionLabel,
  runStatusClass,
  runStatusLabel,
} from "./userLinkageOperationsLabels";

describe("userLinkageOperationsLabels", () => {
  it("maps operation codes to Russian labels", () => {
    expect(operationLabel("USER_LINKAGE_MANUAL_LINK")).toBe("Ручная привязка");
    expect(operationLabel("USER_LINKAGE_REPAIR_PREVIEW")).toBe("Диагностика привязки");
    expect(operationLabel("UNKNOWN_OP")).toBe("UNKNOWN_OP");
  });

  it("maps run and item statuses to Russian labels", () => {
    expect(runStatusLabel("completed")).toBe("Завершён");
    expect(itemStatusLabel("APPLIED")).toBe("Применено");
    expect(itemStatusLabel("NOOP_ALREADY_LINKED")).toBe("Уже привязан");
  });

  it("maps actions and diagnosis codes to Russian labels", () => {
    expect(itemActionLabel("LINK")).toBe("Привязка");
    expect(diagnosisLabel("LINK_OK")).toBe("Привязка в порядке");
    expect(diagnosisLabel("CONFLICT_REQUIRES_MANUAL_DECISION")).toBe("Конфликт: требуется ручное решение");
    expect(recommendedActionLabel("NO_ACTION")).toBe("Действий не требуется");
  });

  it("assigns diagnosis tone colors", () => {
    expect(diagnosisTone("LINK_OK")).toBe("green");
    expect(diagnosisTone("REVIEW_REQUIRED")).toBe("yellow");
    expect(diagnosisTone("MANUAL_DECISION")).toBe("orange");
    expect(diagnosisTone("CONFLICT_REQUIRES_MANUAL_DECISION")).toBe("red");
    expect(diagnosisTone("NO_CANDIDATE_FOUND")).toBe("muted");
  });

  it("returns status badge classes", () => {
    expect(runStatusClass("completed")).toContain("emerald");
    expect(runStatusClass("failed")).toContain("rose");
  });
});
