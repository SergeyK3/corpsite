import { describe, expect, it } from "vitest";

import { mapApiTreeNodesToUi } from "./api.client";

describe("mapApiTreeNodesToUi", () => {
  it("maps backend title and code to UI tree nodes", () => {
    const nodes = mapApiTreeNodesToUi([
      {
        id: "55",
        title: "Новое подразделение",
        code: "NEW-01",
        type: "unit",
        children: [],
      },
    ]);

    expect(nodes[0]).toMatchObject({
      id: "55",
      title: "Новое подразделение",
      code: "NEW-01",
      type: "unit",
    });
  });

  it("falls back from name to title when backend sends name only", () => {
    const nodes = mapApiTreeNodesToUi([
      {
        id: "77",
        name: "Отдел из API",
        children: [],
      },
    ]);

    expect(nodes[0].title).toBe("Отдел из API");
  });

  it("includes newly created child unit after fresh tree reload", () => {
    const before = mapApiTreeNodesToUi([
      {
        id: "10",
        title: "ММЦ",
        code: "MMC",
        children: [{ id: "101", title: "Старое отделение", code: "OLD" }],
      },
    ]);
    expect(before[0].children).toHaveLength(1);

    const after = mapApiTreeNodesToUi([
      {
        id: "10",
        title: "ММЦ",
        code: "MMC",
        children: [
          { id: "101", title: "Старое отделение", code: "OLD" },
          { id: "303", title: "Новое подразделение", code: "NEW-01" },
        ],
      },
    ]);
    expect(after[0].children).toHaveLength(2);
    expect(after[0].children?.[1]).toMatchObject({
      id: "303",
      title: "Новое подразделение",
      code: "NEW-01",
    });
  });
});
