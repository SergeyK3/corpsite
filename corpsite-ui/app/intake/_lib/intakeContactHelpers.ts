import type { IntakeDraftPayload } from "./intakeApi.client";

export function contactsMirrorResidence(contacts: IntakeDraftPayload["contacts"]): boolean {
  const registration = contacts.registration_address.trim();
  if (!registration) return false;
  return contacts.residence_address === contacts.registration_address;
}

export function applyContactsRegistrationAddressChange(
  contacts: IntakeDraftPayload["contacts"],
  registrationAddress: string,
  mirrorResidence: boolean,
): IntakeDraftPayload["contacts"] {
  return {
    ...contacts,
    registration_address: registrationAddress,
    residence_address: mirrorResidence ? registrationAddress : contacts.residence_address,
  };
}

export function applyContactsResidenceMirror(
  contacts: IntakeDraftPayload["contacts"],
  mirrorResidence: boolean,
): IntakeDraftPayload["contacts"] {
  if (!mirrorResidence) return contacts;
  return {
    ...contacts,
    residence_address: contacts.registration_address,
  };
}

export function formatIntakeFullName(personal: IntakeDraftPayload["personal"]): string {
  return [personal.last_name, personal.first_name, personal.middle_name]
    .map((part) => part.trim())
    .filter(Boolean)
    .join(" ");
}
