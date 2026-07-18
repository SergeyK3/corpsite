import { describe, expect, it } from "vitest";

import {
  normalizePortfolioColumnPreview,
  renderPortfolioColumnPreview,
} from "./importEducationProfileDisplay";

describe("importEducationProfileDisplay", () => {
  it("renders primary preview text and extra count", () => {
    expect(
      renderPortfolioColumnPreview({
        count: 3,
        items: [{ text: "Жетысайский высший медицинский колледж, сестринское дело, 2021" }],
        extra_count: 2,
      })
    ).toEqual({
      primary: "Жетысайский высший медицинский колледж, сестринское дело, 2021",
      suffix: "+2 ещё",
    });
  });

  it("shows explicit empty state", () => {
    expect(renderPortfolioColumnPreview({ count: 0, items: [], extra_count: 0 })).toEqual({
      primary: "Нет сведений",
      suffix: null,
    });
  });
});
