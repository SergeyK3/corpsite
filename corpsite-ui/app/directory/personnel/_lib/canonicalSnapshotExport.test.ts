import { describe, expect, it } from "vitest";

import { buildCanonicalSnapshotExportUrl } from "./importApi.client";

describe("canonical snapshot export URL", () => {
  it("builds default roster export URL", () => {
    expect(buildCanonicalSnapshotExportUrl()).toContain(
      "/directory/personnel/canonical-snapshot/export.xlsx",
    );
    expect(buildCanonicalSnapshotExportUrl()).toContain("source_type=roster");
  });

  it("includes snapshot_id and metadata flags", () => {
    const url = buildCanonicalSnapshotExportUrl({
      snapshot_id: 12,
      include_metadata: true,
    });
    expect(url).toContain("snapshot_id=12");
    expect(url).toContain("include_metadata=true");
  });
});
