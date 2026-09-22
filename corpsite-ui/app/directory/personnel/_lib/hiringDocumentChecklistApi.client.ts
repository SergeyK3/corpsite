import { apiFetchJson } from "@/lib/api";

export type HiringDocumentChecklist = {
  title: string;
  items: string[];
  note: string;
  show_additional_notes: boolean;
  additional_notes_lines: number;
  can_edit: boolean;
};

export type HiringDocumentChecklistUpdate = Omit<HiringDocumentChecklist, "can_edit">;

const PATH = "/directory/hiring-document-checklist";

export function getHiringDocumentChecklist(): Promise<HiringDocumentChecklist> {
  return apiFetchJson<HiringDocumentChecklist>(PATH);
}

export function updateHiringDocumentChecklist(
  value: HiringDocumentChecklistUpdate,
): Promise<HiringDocumentChecklist> {
  return apiFetchJson<HiringDocumentChecklist>(PATH, { method: "PUT", body: value });
}
