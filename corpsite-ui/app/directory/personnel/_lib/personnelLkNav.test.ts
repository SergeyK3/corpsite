import { describe, expect, it } from "vitest";

import {
  buildApplicantsRedirectTarget,
  buildPersonnelLkRegistryHref,
  migrateApplicantsSearchParamsToLkQuery,
  parsePersonnelLkRegistryState,
} from "./personnelLkNav";
import { PERSONNEL_LK_WORKPLACE_BASE_PATH } from "./personnelApplicationsJournalNav";

describe("personnelLkNav", () => {
  it("parses registry state from search params", () => {
    const sp = new URLSearchParams(
      "q=petrov&record_kind=applicant&status=all&application_status=registered&offset=50&org_unit_id=3&application_id=10",
    );
    expect(parsePersonnelLkRegistryState(sp)).toEqual({
      q: "petrov",
      record_kind: "applicant",
      status: "all",
      application_status: "registered",
      limit: 50,
      offset: 50,
      application_id: 10,
      org_unit_id: 3,
    });
  });

  it("builds registry href with filters and application_id", () => {
    const href = buildPersonnelLkRegistryHref({
      q: "petrov",
      record_kind: "employee",
      status: "inactive",
      application_status: "",
      limit: 50,
      offset: 0,
      application_id: 10,
      org_unit_id: 3,
    });
    expect(href).toBe(
      "/directory/personnel/lk?q=petrov&record_kind=employee&status=inactive&org_unit_id=3&application_id=10",
    );
  });

  it("migrates legacy applicants query params to lk", () => {
    const qs = migrateApplicantsSearchParamsToLkQuery(
      new URLSearchParams(
        "q=petrov&org_group_id=1&org_unit_id=2&position_id=3&application_id=10&register=1&view=archive&sort=full_name_asc",
      ),
    );
    expect(qs).toBe(
      "q=petrov&org_group_id=1&org_unit_id=2&position_id=3&application_id=10&register=1",
    );
    expect(buildApplicantsRedirectTarget(new URLSearchParams(qs))).toBe(
      `${PERSONNEL_LK_WORKPLACE_BASE_PATH}?${qs}`,
    );
  });
});
