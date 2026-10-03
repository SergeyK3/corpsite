import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import DataCleanupCenter from "./DataCleanupCenter";

vi.mock("../../test-personnel-data/_components/TestPersonnelDataAdminClient", () => ({
  default: () => <div>Тестовый раздел</div>,
}));
vi.mock("./TechnicalPersonnelOrdersPanel", () => ({
  default: () => <div>Раздел технических приказов</div>,
}));

afterEach(cleanup);

describe("DataCleanupCenter category tabs", () => {
  it("marks the test-personnel category active initially and updates styling and aria state on switch", () => {
    render(<DataCleanupCenter />);

    const testPersonnel = screen.getByRole("tab", { name: "Тестовые сотрудники и пользователи" });
    const technicalOrders = screen.getByRole("tab", { name: "Технические кадровые приказы" });

    expect(testPersonnel).toHaveAttribute("aria-selected", "true");
    expect(technicalOrders).toHaveAttribute("aria-selected", "false");
    expect(testPersonnel).toHaveClass("bg-blue-600", "text-white", "ring-2");
    expect(technicalOrders).toHaveClass("bg-zinc-100", "text-zinc-800");
    expect(screen.getByText("Тестовый раздел")).toBeInTheDocument();

    fireEvent.click(technicalOrders);

    expect(testPersonnel).toHaveAttribute("aria-selected", "false");
    expect(technicalOrders).toHaveAttribute("aria-selected", "true");
    expect(technicalOrders).toHaveClass("bg-blue-600", "text-white", "ring-2");
    expect(testPersonnel).toHaveClass("bg-zinc-100", "text-zinc-800");
    expect(screen.getByText("Раздел технических приказов")).toBeInTheDocument();
  });
});
