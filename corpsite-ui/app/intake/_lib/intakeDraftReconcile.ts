import { normalizeIntakeAdditionalPayload } from "./intakeAdditional";
import { normalizeIntakeEducationEntry } from "./intakeEducation";
import { reconcileIntakePersonalBlock } from "./intakePersonalFields";
import {
  reconcileIntakeMilitaryDraftOnLoad,
} from "./intakeMilitaryDictionary";
import {
  normalizeIntakeTrainingEntry,
  reconcileTrainingEntryHours,
} from "./intakeTraining";
import { emptyIntakeDraftPayload, type IntakeDraftPayload } from "./intakeApi.client";

export function reconcileIntakeDraftPayload(payload: IntakeDraftPayload): IntakeDraftPayload {
  const military = {
    ...emptyIntakeDraftPayload().military,
    ...payload.military,
    specialty_name: payload.military?.specialty_name ?? "",
  };
  return {
    ...payload,
    personal: reconcileIntakePersonalBlock({
      ...emptyIntakeDraftPayload().personal,
      ...payload.personal,
    }),
    education: (payload.education ?? []).map((item) => normalizeIntakeEducationEntry(item)),
    training: (payload.training ?? []).map((item) =>
      reconcileTrainingEntryHours(normalizeIntakeTrainingEntry(item)),
    ),
    additional: normalizeIntakeAdditionalPayload(payload.additional),
    military: reconcileIntakeMilitaryDraftOnLoad(military),
  };
}
