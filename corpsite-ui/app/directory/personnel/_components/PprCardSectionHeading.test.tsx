import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { PprCardSectionHeading, PPR_CARD_SECTION_HEADING_CLASS } from "./PprCardSectionHeading";
import { PprCardSection } from "./PprCardSection";

afterEach(() => {
  cleanup();
});

describe("PprCardSectionHeading", () => {
  it("renders accessible section title with accent bar classes", () => {
    render(<PprCardSectionHeading id="military-heading">Воинский учёт</PprCardSectionHeading>);

    const heading = screen.getByRole("heading", { name: "Воинский учёт" });
    expect(heading).toHaveAttribute("id", "military-heading");
    expect(heading.className).toContain("border-l-[3px]");
    expect(heading.className).toContain("border-amber-600");
    expect(heading.className).toContain("font-semibold");
    expect(PPR_CARD_SECTION_HEADING_CLASS).toContain("text-[15px]");
  });
});

describe("PprCardSection", () => {
  it("enables PPR heading variant on section shell", () => {
    render(
      <PprCardSection id="military" title="Воинский учёт" description="Описание раздела.">
        <p>content</p>
      </PprCardSection>,
    );

    const heading = screen.getByRole("heading", { name: "Воинский учёт" });
    expect(heading.className).toContain("border-amber-600");
  });
});
