import { resolveApiUrl } from "@/lib/apiBase";
import type { PersonnelOrderPdfAuthContext } from "./personnelOrderPdfAuth";
import { buildPersonCardPdfHtmlDocument } from "./personCardPdfDocumentHtml";
import {
  buildPersonCardPdfViewModel,
  type PersonCardContacts,
  type PersonCardCurrentAssignment,
} from "./personCardPdfViewModel";
import type { PprCompositeReadResponse } from "./pprQueryTypes";

export class PersonCardPdfDataError extends Error {
  constructor(public status: number, public code: string, message: string) { super(message); }
}

function headers(auth: PersonnelOrderPdfAuthContext): Record<string, string> {
  const result: Record<string, string> = { Accept: "application/json" };
  if (auth.authorizationHeader) result.Authorization = auth.authorizationHeader;
  if (auth.devUserId) result["X-User-Id"] = auth.devUserId;
  return result;
}

async function json<T>(path: string, auth: PersonnelOrderPdfAuthContext): Promise<T> {
  const response = await fetch(resolveApiUrl(path, { serverSide: true }), { headers: headers(auth), cache: "no-store" });
  if (!response.ok) {
    const status = response.status;
    if (status === 401) throw new PersonCardPdfDataError(401, "UNAUTHORIZED", "Требуется авторизация.");
    if (status === 403) throw new PersonCardPdfDataError(403, "FORBIDDEN", "Недостаточно прав для просмотра карточки.");
    if (status === 404) throw new PersonCardPdfDataError(404, "NOT_FOUND", "Личная карточка не найдена.");
    throw new PersonCardPdfDataError(status, "UPSTREAM_ERROR", "Не удалось загрузить личную карточку.");
  }
  return response.json() as Promise<T>;
}

async function photo(personId: number, auth: PersonnelOrderPdfAuthContext): Promise<string | null> {
  try {
    const response = await fetch(resolveApiUrl(`/api/ppr/persons/${personId}/photo`, { serverSide: true }), { headers: { ...headers(auth), Accept: "image/jpeg" }, cache: "no-store" });
    if (!response.ok) return null;
    const bytes = Buffer.from(await response.arrayBuffer());
    return bytes.length && bytes[0] === 0xff && bytes[1] === 0xd8 ? `data:image/jpeg;base64,${bytes.toString("base64")}` : null;
  } catch { return null; }
}

type ContactsResponse = { canonical: PersonCardContacts | null; fallback: PersonCardContacts | null };

type OperationalAssignmentResponse = {
  has_assignment: boolean;
  department_group_name?: string | null;
  org_unit_name?: string | null;
  position_name?: string | null;
  status?: string | null;
  employment_rate?: string | null;
};

async function currentAssignment(
  personId: number,
  auth: PersonnelOrderPdfAuthContext,
): Promise<PersonCardCurrentAssignment | null> {
  let assignment: OperationalAssignmentResponse;
  try {
    assignment = await json<OperationalAssignmentResponse>(`/api/ppr/persons/${personId}/operational-assignment`, auth);
  } catch (error) {
    if (error instanceof PersonCardPdfDataError && error.status === 404) return null;
    throw error;
  }
  if (!assignment.has_assignment) return null;
  const departmentGroupName = String(assignment.department_group_name ?? "").trim();
  const orgUnitName = String(assignment.org_unit_name ?? "").trim();
  const positionName = String(assignment.position_name ?? "").trim();
  const statusLabel = String(assignment.status ?? "").trim();
  const rate = String(assignment.employment_rate ?? "").trim();
  return departmentGroupName && orgUnitName && positionName && statusLabel && rate
    ? { departmentGroupName, orgUnitName, positionName, statusLabel, rate }
    : null;
}

export async function loadPersonCardPdfDocument(personId: number, auth: PersonnelOrderPdfAuthContext): Promise<{ html: string; filename: string }> {
  if (!Number.isSafeInteger(personId) || personId <= 0) throw new PersonCardPdfDataError(422, "INVALID_PERSON_ID", "Некорректный идентификатор сотрудника.");
  const [ppr, contactResponse, photoDataUrl] = await Promise.all([
    json<PprCompositeReadResponse>(`/api/ppr/persons/${personId}`, auth),
    json<ContactsResponse>(`/api/ppr/persons/${personId}/contacts`, auth),
    photo(personId, auth),
  ]);
  const assignment = await currentAssignment(personId, auth);
  const model = buildPersonCardPdfViewModel({
    personId,
    ppr,
    contacts: contactResponse.canonical ?? contactResponse.fallback,
    photoDataUrl,
    currentAssignment: assignment,
  });
  return { html: buildPersonCardPdfHtmlDocument(model), filename: `personal-card-${personId}.pdf` };
}
