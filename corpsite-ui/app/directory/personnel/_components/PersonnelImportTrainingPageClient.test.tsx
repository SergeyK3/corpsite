import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import PersonnelImportTrainingPageClient from "./PersonnelImportTrainingPageClient";

vi.mock("../_lib/importApi.client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../_lib/importApi.client")>();
  return {
    ...actual,
    getDepartmentRecodingOptions: vi.fn(async () => ({
      groups: [
        {
          value: "clinical",
          label: "Клинические",
          group_id: 1,
          effective_log_group: "clinical",
          effective_log_group_name: "Клинические",
        },
        {
          value: "paraclinical",
          label: "Параклинические",
          group_id: 2,
          effective_log_group: "paraclinical",
          effective_log_group_name: "Параклинические",
        },
        {
          value: "admin_household",
          label: "Административно-хозяйственные",
          group_id: 3,
          effective_log_group: "admin_household",
          effective_log_group_name: "Административно-хозяйственные",
        },
      ],
      departments: [],
    })),
    listEducationProfiles: vi.fn(async () => ({
      batch_id: 1,
      total: 0,
      items: [],
      limit: 50,
      offset: 0,
    })),
  };
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("PersonnelImportTrainingPageClient group dropdown", () => {
  it("shows Russian labels with slug values", async () => {
    render(<PersonnelImportTrainingPageClient batchId={1} />);

    await waitFor(() => {
      expect(screen.getByRole("option", { name: "Клинические" })).toBeTruthy();
    });

    const clinical = screen.getByRole("option", { name: "Клинические" }) as HTMLOptionElement;
    const paraclinical = screen.getByRole("option", { name: "Параклинические" }) as HTMLOptionElement;
    const admin = screen.getByRole("option", {
      name: "Административно-хозяйственные",
    }) as HTMLOptionElement;

    expect(clinical.value).toBe("clinical");
    expect(paraclinical.value).toBe("paraclinical");
    expect(admin.value).toBe("admin_household");
    expect(screen.queryByRole("option", { name: "clinical" })).toBeNull();
  });
});
