import { describe, expect, it, vi } from "vitest";

vi.mock("./intakePdfRenderer", () => ({
  getIntakePdfRenderer: () => ({
    render: vi.fn(async () => Buffer.from("%PDF-1.7 canonical-v2")),
  }),
}));

import { renderIntakePdfResponse } from "./intakePdfRouteHandler";
import type { IntakePdfLoadedModel } from "./intakePdfData.server";

const canonicalV2Model = {
  filename: "anketa-225-nurtaev.pdf",
  model: {
    applicationId: 225,
    fullName: "Нуртаев Арман Серикович",
    payload: {
      schema_version: 2,
      contacts: { email: null, mobile_phone: "+77772378855", residence_address: null, registration_address: null },
      education: [{ record_id: "b2c7e524-cf07-4a84-9a8d-7f52a88fb8f4", start_date: "2013-09-01", end_date: "2020-06-30" }],
      employment_biography: [{ record_id: "d83f745d-37f8-4331-82bd-9c6a2af1631a", start_date: "2020-08-01", end_date: null }],
      relatives: [{ record_id: "13d3c656-2f10-4f7c-ab97-0302130f27bd", birth_date: "1996-11-21", workplace: "домохозяйка" }],
      military: { status: "not_provided", rank: null, category: null },
      training: [{ record_id: "2d943c97-cfe4-40a1-af04-57b8210e5a31", hours: 840 }],
    },
  },
} as unknown as IntakePdfLoadedModel;

describe("renderIntakePdfResponse", () => {
  it("returns a non-empty PDF for a canonical v2 payload with null optional values", async () => {
    const response = await renderIntakePdfResponse(async () => canonicalV2Model);
    const bytes = Buffer.from(await response.arrayBuffer());

    expect(response.status).toBe(200);
    expect(response.headers.get("content-type")).toBe("application/pdf");
    expect(response.headers.get("content-disposition")).toContain("anketa-225-nurtaev.pdf");
    expect(bytes.byteLength).toBeGreaterThan(5);
    expect(bytes.subarray(0, 5).toString("utf8")).toBe("%PDF-");
  });
});
