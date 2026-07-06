import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import PositionCabinetNav from "@/components/PositionCabinetNav";
import {
  getPositionCabinetTabLabel,
  POSITION_CABINET_TAB_LABELS,
} from "@/lib/positionCabinetNav";

const usePathnameMock = vi.fn(() => "/tasks");

vi.mock("next/navigation", () => ({
  usePathname: () => usePathnameMock(),
}));

afterEach(() => {
  cleanup();
  usePathnameMock.mockReset();
  usePathnameMock.mockReturnValue("/tasks");
});

describe("PositionCabinetNav UI", () => {
  it("renders all three tab captions with visible text", () => {
    render(<PositionCabinetNav />);

    for (const section of ["tasks", "dashboards", "education"] as const) {
      const label = POSITION_CABINET_TAB_LABELS[section];
      const tab = screen.getByTestId(`position-cabinet-tab-${section}`);

      expect(tab).toHaveAttribute("href", section === "tasks" ? "/tasks" : `/${section}`);
      expect(tab).toHaveAccessibleName(label);
      expect(tab.textContent?.trim()).toBe(label);
      expect(getPositionCabinetTabLabel(section)).toBe(label);
    }
  });

  it("marks dashboards as active on /dashboards", () => {
    usePathnameMock.mockReturnValue("/dashboards");
    render(<PositionCabinetNav />);

    expect(screen.getByTestId("position-cabinet-tab-dashboards")).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(screen.getByTestId("position-cabinet-tab-education")).not.toHaveAttribute(
      "aria-current",
    );
  });

  it("marks education as active on /education", () => {
    usePathnameMock.mockReturnValue("/education");
    render(<PositionCabinetNav />);

    expect(screen.getByTestId("position-cabinet-tab-education")).toHaveAttribute(
      "aria-current",
      "page",
    );
  });
});
