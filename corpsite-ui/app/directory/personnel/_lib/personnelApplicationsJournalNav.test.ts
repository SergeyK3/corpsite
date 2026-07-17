import { describe, expect, it } from "vitest";

import { RETURN_TO_QUERY_PARAM } from "@/lib/taskNav";
import {
  buildPersonnelApplicationsJournalHref,
  buildPersonnelApplicationsListLoadKey,
  buildPersonalCardHrefFromJournal,
  isPersonnelApplicationsJournalReturnHref,
  parsePersonnelApplicationsJournalState,
  resolvePersonalCardBackHref,
} from "./personnelApplicationsJournalNav";

describe("personnelApplicationsJournalNav", () => {
  it("parses journal state from search params", () => {
    const sp = new URLSearchParams(
      "q=petrov&sort=full_name_asc&offset=50&limit=50&org_unit_id=3&application_id=10",
    );
    expect(parsePersonnelApplicationsJournalState(sp)).toEqual({
      q: "petrov",
      sort: "full_name_asc",
      view: "active",
      limit: 50,
      offset: 50,
      application_id: 10,
      org_unit_id: 3,
    });
  });

  it("parses archive view from search params", () => {
    const sp = new URLSearchParams("view=archive&sort=closed_at_desc");
    expect(parsePersonnelApplicationsJournalState(sp)).toEqual({
      q: "",
      sort: "closed_at_desc",
      view: "archive",
      limit: 50,
      offset: 0,
      application_id: null,
    });
  });

  it("builds journal href with filters and application_id", () => {
    const href = buildPersonnelApplicationsJournalHref({
      q: "petrov",
      sort: "full_name_asc",
      view: "archive",
      limit: 50,
      offset: 50,
      application_id: 10,
      org_unit_id: 3,
    });
    expect(href).toBe(
      "/directory/personnel-applications?q=petrov&view=archive&sort=full_name_asc&org_unit_id=3&offset=50&application_id=10",
    );
  });

  it("builds list load key without application_id", () => {
    const withDrawer = {
      q: "petrov",
      sort: "application_received_at_desc",
      view: "active" as const,
      limit: 50,
      offset: 0,
      application_id: 10,
    };
    const withoutDrawer = { ...withDrawer, application_id: null };
    expect(buildPersonnelApplicationsListLoadKey(withDrawer)).toBe(
      buildPersonnelApplicationsListLoadKey(withoutDrawer),
    );
  });

  it("builds personal card href with encoded return_to", () => {
    const href = buildPersonalCardHrefFromJournal(
      5,
      "/directory/personnel-applications?q=petrov&application_id=10",
    );
    const url = new URL(href, "http://localhost");
    expect(url.pathname).toBe("/directory/personnel/persons/5/card");
    expect(url.searchParams.get(RETURN_TO_QUERY_PARAM)).toBe(
      "/directory/personnel-applications?q=petrov&application_id=10",
    );
  });

  it("resolves personal card back href from return_to", () => {
    expect(
      resolvePersonalCardBackHref("/directory/personnel-applications?application_id=10"),
    ).toBe("/directory/personnel-applications?application_id=10");
    expect(resolvePersonalCardBackHref("https://evil.test")).toBe("/directory/staff");
  });

  it("detects personnel applications journal return href", () => {
    expect(isPersonnelApplicationsJournalReturnHref("/directory/personnel-applications")).toBe(true);
    expect(
      isPersonnelApplicationsJournalReturnHref(
        "/directory/personnel-applications?application_id=10&q=petrov",
      ),
    ).toBe(true);
    expect(isPersonnelApplicationsJournalReturnHref("/directory/staff")).toBe(false);
  });
});
