import { describe, expect, it } from "vitest";

import { emptyIntakeDraftPayload } from "./intakeApi.client";
import {
  applyContactsRegistrationAddressChange,
  applyContactsResidenceMirror,
  contactsMirrorResidence,
  formatIntakeFullName,
} from "./intakeContactHelpers";

describe("intakeContactHelpers", () => {
  it("detects when residence mirrors registration", () => {
    const payload = emptyIntakeDraftPayload();
    payload.contacts.registration_address = "г. Алматы, ул. Абая 1";
    payload.contacts.residence_address = "г. Алматы, ул. Абая 1";
    expect(contactsMirrorResidence(payload.contacts)).toBe(true);
  });

  it("copies registration address to residence when mirror is enabled", () => {
    const payload = emptyIntakeDraftPayload();
    payload.contacts.registration_address = "г. Алматы, ул. Абая 1";
    const next = applyContactsResidenceMirror(payload.contacts, true);
    expect(next.residence_address).toBe("г. Алматы, ул. Абая 1");
  });

  it("keeps residence unchanged when mirror is disabled", () => {
    const payload = emptyIntakeDraftPayload();
    payload.contacts.registration_address = "г. Алматы, ул. Абая 1";
    payload.contacts.residence_address = "г. Астана, ул. Кенесары 2";
    const next = applyContactsRegistrationAddressChange(payload.contacts, "г. Шымкент", false);
    expect(next.registration_address).toBe("г. Шымкент");
    expect(next.residence_address).toBe("г. Астана, ул. Кенесары 2");
  });

  it("updates mirrored residence together with registration", () => {
    const payload = emptyIntakeDraftPayload();
    payload.contacts.registration_address = "г. Алматы, ул. Абая 1";
    payload.contacts.residence_address = "г. Алматы, ул. Абая 1";
    const next = applyContactsRegistrationAddressChange(payload.contacts, "г. Алматы, ул. Абая 10", true);
    expect(next.registration_address).toBe("г. Алматы, ул. Абая 10");
    expect(next.residence_address).toBe("г. Алматы, ул. Абая 10");
  });

  it("formats applicant full name from personal payload", () => {
    const payload = emptyIntakeDraftPayload();
    payload.personal.last_name = "Петров";
    payload.personal.first_name = "Пётр";
    payload.personal.middle_name = "Петрович";
    expect(formatIntakeFullName(payload.personal)).toBe("Петров Пётр Петрович");
  });
});
