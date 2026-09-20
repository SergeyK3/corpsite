import { resolveApiUrl } from "@/lib/apiBase";
import type { PersonnelOrderPdfAuthContext } from "@/app/directory/personnel/_lib/personnelOrderPdfAuth";
import { buildPersonCardPdfHtmlDocument } from "@/app/directory/personnel/_lib/personCardPdfDocumentHtml";
import {
  buildPersonCardPdfViewModel,
  type SelfCardPdfProjection,
} from "@/app/directory/personnel/_lib/personCardPdfViewModel";
import { displayEmploymentRate, displayOperationalStatus } from "./operationalAssignmentDisplay";

export class SelfPersonCardPdfDataError extends Error {
  constructor(public status: number, public code: string, message: string) {
    super(message);
  }
}

type SelfCardResponse =
  | { status: "READY"; card: SelfCardPdfProjection }
  | { status: "NO_EMPLOYEE_LINK" | "PERSON_NOT_LINKED" | "IDENTITY_AMBIGUOUS"; card: null };

type SelfOperationalAssignmentResponse =
  | {
      status: "READY";
      operational_assignment: {
        department_group_name: string | null;
        org_unit_name: string | null;
        position_name: string | null;
        operational_status: string | null;
        employment_rate: number | null;
        iin: string | null;
      };
    }
  | { status: "NO_EMPLOYEE_LINK" | "PERSON_NOT_LINKED" | "IDENTITY_AMBIGUOUS"; operational_assignment: null };

function headers(auth: PersonnelOrderPdfAuthContext): Record<string, string> {
  const result: Record<string, string> = { Accept: "application/json" };
  if (auth.authorizationHeader) result.Authorization = auth.authorizationHeader;
  if (auth.devUserId) result["X-User-Id"] = auth.devUserId;
  return result;
}

/**
 * Fetches self-resolved data only. No Person/Employee endpoint, personnel
 * visibility path, intake source, photo endpoint, or browser-supplied ID
 * participates here.
 */
export async function loadSelfPersonCardPdfDocument(
  auth: PersonnelOrderPdfAuthContext,
): Promise<{ html: string; filename: string }> {
  const response = await fetch(resolveApiUrl("/api/ppr/me", { serverSide: true }), {
    headers: headers(auth),
    cache: "no-store",
  });
  if (!response.ok) {
    if (response.status === 401) throw new SelfPersonCardPdfDataError(401, "UNAUTHORIZED", "Требуется авторизация.");
    if (response.status === 403) throw new SelfPersonCardPdfDataError(403, "FORBIDDEN", "PDF личной карточки недоступен.");
    throw new SelfPersonCardPdfDataError(502, "SELF_CARD_UNAVAILABLE", "Личная карточка временно недоступна.");
  }

  const selfCard = await response.json() as SelfCardResponse;
  if (selfCard.status === "PERSON_NOT_LINKED") {
    throw new SelfPersonCardPdfDataError(409, "PERSON_NOT_LINKED", "Личная карточка ещё не создана.");
  }
  if (selfCard.status !== "READY" || !selfCard.card) {
    throw new SelfPersonCardPdfDataError(409, "SELF_CARD_UNAVAILABLE", "Личная карточка временно недоступна.");
  }

  const assignmentResponse = await fetch(resolveApiUrl("/api/ppr/me/operational-assignment", { serverSide: true }), {
    headers: headers(auth),
    cache: "no-store",
  });
  if (!assignmentResponse.ok) {
    throw new SelfPersonCardPdfDataError(502, "SELF_CARD_UNAVAILABLE", "Личная карточка временно недоступна.");
  }
  const assignment = await assignmentResponse.json() as SelfOperationalAssignmentResponse;
  if (assignment.status !== "READY" || !assignment.operational_assignment) {
    throw new SelfPersonCardPdfDataError(409, "SELF_CARD_UNAVAILABLE", "Личная карточка временно недоступна.");
  }

  const operational = assignment.operational_assignment;
  const model = buildPersonCardPdfViewModel({
    ppr: {
      ...selfCard.card,
      // The IIN is full only in the authenticated employee's self projection.
      general: { ...selfCard.card.general, iin: operational.iin ?? selfCard.card.general.iin },
    },
    contacts: null,
    photoDataUrl: null,
    currentAssignment: {
      departmentGroupName: operational.department_group_name ?? "",
      orgUnitName: operational.org_unit_name ?? "",
      positionName: operational.position_name ?? "",
      statusLabel: displayOperationalStatus(operational.operational_status) ?? "",
      rate: displayEmploymentRate(operational.employment_rate) ?? "",
    },
  });
  return {
    html: buildPersonCardPdfHtmlDocument(model),
    filename: "personal-card.pdf",
  };
}
