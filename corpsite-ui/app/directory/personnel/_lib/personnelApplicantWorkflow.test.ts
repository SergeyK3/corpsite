import { describe, expect, it } from "vitest";

import {
  canCreateHireOrderFromApplicantCard,
  canDisplayApplicantIntakeLink,
  canOpenApplicantPersonalCard,
  formatApplicantIntakeUrlDisplay,
  resolveApplicantIntakeUrlPath,
  resolveApplicantWorkflowStatus,
} from "./personnelApplicantWorkflow";

describe("personnelApplicantWorkflow", () => {
  it("maps registered status to new application", () => {
    expect(resolveApplicantWorkflowStatus({ status: "registered" })).toEqual({
      key: "new_application",
      label: "Новое заявление",
    });
  });

  it("maps intake pending with issued link to awaiting fill", () => {
    expect(
      resolveApplicantWorkflowStatus({
        status: "intake_pending",
        intake_link_status: "issued",
      }),
    ).toEqual({
      key: "awaiting_fill",
      label: "Ожидает заполнения",
    });
  });

  it("maps intake pending with opened link to filling", () => {
    expect(
      resolveApplicantWorkflowStatus({
        status: "intake_pending",
        intake_link_status: "opened",
      }),
    ).toEqual({
      key: "filling",
      label: "Заполняет",
    });
  });

  it("maps submitted intake to filled card label", () => {
    expect(resolveApplicantWorkflowStatus({ status: "intake_submitted" })).toEqual({
      key: "card_filled",
      label: "Личная карточка заполнена",
    });
  });

  it("maps review completed to ready for processing", () => {
    expect(resolveApplicantWorkflowStatus({ status: "review_completed" })).toEqual({
      key: "ready_for_processing",
      label: "Готово к оформлению",
    });
  });

  it("gates personal card until intake submitted", () => {
    expect(canOpenApplicantPersonalCard("registered")).toBe(false);
    expect(canOpenApplicantPersonalCard("intake_pending")).toBe(false);
    expect(canOpenApplicantPersonalCard("intake_submitted")).toBe(true);
    expect(canOpenApplicantPersonalCard("review_completed")).toBe(true);
  });

  it("gates hire order until intake submitted", () => {
    expect(canCreateHireOrderFromApplicantCard("intake_pending")).toBe(false);
    expect(canCreateHireOrderFromApplicantCard("intake_submitted")).toBe(true);
    expect(canCreateHireOrderFromApplicantCard("review_completed")).toBe(true);
  });

  it("allows intake link display only for active link statuses", () => {
    expect(canDisplayApplicantIntakeLink("issued")).toBe(true);
    expect(canDisplayApplicantIntakeLink("opened")).toBe(true);
    expect(canDisplayApplicantIntakeLink("submitted")).toBe(true);
    expect(canDisplayApplicantIntakeLink("revoked")).toBe(false);
    expect(canDisplayApplicantIntakeLink(null)).toBe(false);
  });

  it("resolves intake path from session cache for active links", () => {
    sessionStorage.setItem("personnel-intake-link:42", "/intake/token-1");
    expect(resolveApplicantIntakeUrlPath(42, "issued")).toBe("/intake/token-1");
    expect(resolveApplicantIntakeUrlPath(42, "revoked")).toBeNull();
    sessionStorage.removeItem("personnel-intake-link:42");
  });

  it("truncates long intake urls for table display", () => {
    const longUrl = `http://localhost/intake/${"x".repeat(60)}`;
    expect(formatApplicantIntakeUrlDisplay(longUrl, 20)).toBe(`${longUrl.slice(0, 19)}…`);
  });
});
