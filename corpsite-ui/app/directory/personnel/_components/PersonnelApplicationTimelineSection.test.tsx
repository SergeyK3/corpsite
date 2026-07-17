import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import PersonnelApplicationTimelineSection from "./PersonnelApplicationTimelineSection";

const getApplicationTimelineMock = vi.fn();

vi.mock("../_lib/personnelApplicationsApi.client", async () => {
  const actual = await vi.importActual<typeof import("../_lib/personnelApplicationsApi.client")>(
    "../_lib/personnelApplicationsApi.client",
  );
  return {
    ...actual,
    getApplicationTimeline: (...args: unknown[]) => getApplicationTimelineMock(...args),
  };
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("PersonnelApplicationTimelineSection", () => {
  it("renders timeline events", async () => {
    getApplicationTimelineMock.mockResolvedValue({
      application_id: 10,
      items: [
        {
          code: "registered",
          label: "Регистрация обращения",
          occurred_at: "2026-07-02T10:00:00Z",
        },
        {
          code: "cancelled",
          label: "Обращение отменено",
          occurred_at: "2026-07-03T10:00:00Z",
          detail: "Претендент отказался",
        },
      ],
    });

    render(<PersonnelApplicationTimelineSection applicationId={10} />);

    await waitFor(() => {
      expect(screen.getByTestId("personnel-application-timeline")).toBeInTheDocument();
    });

    expect(screen.getByText("Регистрация обращения")).toBeInTheDocument();
    expect(screen.getByText("Обращение отменено")).toBeInTheDocument();
    expect(screen.getByText("Претендент отказался")).toBeInTheDocument();
  });
});
