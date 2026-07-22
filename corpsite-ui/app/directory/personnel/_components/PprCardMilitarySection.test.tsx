import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import PprCardMilitarySection from "./PprCardMilitarySection";
import type { PprMilitaryRecordResponse } from "../_lib/pprQueryTypes";
import {
  PPR_MILITARY_RECORD_KIND_NOT_APPLICABLE,
  PPR_MILITARY_RECORD_KIND_REGISTRATION,
} from "../_lib/pprQueryTypes";
import { toApiError } from "@/lib/api";

const createMock = vi.fn();
const voidMock = vi.fn();
const supersedeMock = vi.fn();
let commandCounter = 0;

vi.mock("../_lib/pprCommandApi.client", () => ({
  createMilitaryService: (...args: unknown[]) => createMock(...args),
  voidMilitaryService: (...args: unknown[]) => voidMock(...args),
  supersedeMilitaryService: (...args: unknown[]) => supersedeMock(...args),
  newPprCommandId: () => {
    commandCounter += 1;
    return `test-command-id-${commandCounter}`;
  },
}));

const personRoute = { kind: "person" as const, id: 501 };

async function pickComboboxOption(testId: string, query: string, optionLabel?: string) {
  const input = screen.getByTestId(testId);
  fireEvent.click(input);
  if (query) {
    fireEvent.change(input, { target: { value: query } });
  }
  const list = await screen.findByTestId(`${testId}-list`);
  const options = Array.from(list.querySelectorAll('[role="option"]'));
  const target = optionLabel
    ? options.find((option) => option.textContent === optionLabel)
    : options[0];
  if (!target) {
    throw new Error(`Combobox option not found: ${optionLabel ?? query}`);
  }
  fireEvent.click(target);
}

async function fillMilitaryRank(rankLabel: string, compositionQuery = "Рядовой состав") {
  fireEvent.click(screen.getByTestId("military-create-btn"));
  await pickComboboxOption("military-form-composition", compositionQuery, "Рядовой состав");
  await pickComboboxOption("military-form-rank", rankLabel, rankLabel);
}

const registrationRecord: PprMilitaryRecordResponse = {
  record_id: 201,
  record_kind: PPR_MILITARY_RECORD_KIND_REGISTRATION,
  obligation_status: "liable",
  registration_category: "II",
  military_rank: "рядовой",
  military_specialty_code: "1234567",
  personnel_composition: "soldiers",
  fitness_category: "А",
  registration_status: "registered",
  commissariat_name: "Алмалинский РВК",
  registered_at: "2015-05-01",
  deregistered_at: null,
  notes: null,
  source_type: "entered",
  provenance: null,
  metadata: null,
  employee_context_id: null,
  verification_status: "pending",
  lifecycle_status: "active",
  created_at: "2024-01-01T00:00:00Z",
  updated_at: "2024-02-01T00:00:00Z",
};

const notApplicableRecord: PprMilitaryRecordResponse = {
  record_id: 202,
  record_kind: PPR_MILITARY_RECORD_KIND_NOT_APPLICABLE,
  obligation_status: null,
  registration_category: null,
  military_rank: null,
  military_specialty_code: null,
  personnel_composition: null,
  fitness_category: null,
  registration_status: null,
  commissariat_name: null,
  registered_at: null,
  deregistered_at: null,
  notes: "Не подлежит воинскому учёту",
  source_type: "entered",
  provenance: null,
  metadata: null,
  employee_context_id: null,
  verification_status: "pending",
  lifecycle_status: "active",
  created_at: "2024-01-01T00:00:00Z",
  updated_at: "2024-02-01T00:00:00Z",
};

const historyRecord: PprMilitaryRecordResponse = {
  ...registrationRecord,
  record_id: 199,
  military_rank: "сержант (устар.)",
  lifecycle_status: "superseded",
  updated_at: "2024-01-15T00:00:00Z",
};

beforeEach(() => {
  createMock.mockReset();
  voidMock.mockReset();
  supersedeMock.mockReset();
  commandCounter = 0;
});

afterEach(() => {
  cleanup();
});

describe("PprCardMilitarySection", () => {
  it("shows empty state", () => {
    render(
      <PprCardMilitarySection active={[]} superseded={[]} voided={[]} route={personRoute} editable />,
    );
    expect(screen.getByTestId("military-empty")).toBeInTheDocument();
  });

  it("renders registration active record with query fields only", () => {
    render(
      <PprCardMilitarySection
        active={[registrationRecord]}
        superseded={[]}
        voided={[]}
        route={personRoute}
      />,
    );

    const card = screen.getByTestId("military-record-201");
    expect(card).toHaveTextContent("рядовой");
    expect(card).toHaveTextContent("Рядовой состав");
    expect(card).not.toHaveTextContent("Рядовой и сержантский состав");
    expect(card).toHaveTextContent("Алмалинский РВК");
    expect(card).toHaveTextContent("Военнообязанный");
    expect(card).not.toHaveTextContent("***");
  });

  it("renders not_applicable active record", () => {
    render(
      <PprCardMilitarySection
        active={[notApplicableRecord]}
        superseded={[]}
        voided={[]}
        route={personRoute}
      />,
    );

    const card = screen.getByTestId("military-record-202");
    expect(card).toHaveTextContent("Не подлежит воинскому учёту");
    expect(card).toHaveTextContent("Не подлежит воинскому учёту");
    expect(card).not.toHaveTextContent("Воинское звание:");
    expect(card).not.toHaveTextContent("Военкомат:");
  });

  it("shows history in collapsed groups", () => {
    render(
      <PprCardMilitarySection
        active={[registrationRecord]}
        superseded={[historyRecord]}
        voided={[]}
        route={personRoute}
      />,
    );

    expect(screen.getByRole("button", { name: /История замен \(1\)/ })).toHaveAttribute(
      "aria-expanded",
      "false",
    );
    expect(screen.queryByText("сержант (устар.)")).not.toBeInTheDocument();
  });

  it("expands history on click", () => {
    render(
      <PprCardMilitarySection
        active={[registrationRecord]}
        superseded={[historyRecord]}
        voided={[]}
        route={personRoute}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /История замен \(1\)/ }));
    expect(screen.getByTestId("military-record-199")).toBeInTheDocument();
    expect(screen.getByTestId("military-record-199")).toHaveTextContent("сержант (устар.)");
  });

  it("shows restricted fields only when present in DTO", () => {
    const withRestricted = {
      ...registrationRecord,
      military_id_book_series: "АБ",
      military_id_book_number: "7654321",
    };

    const { rerender } = render(
      <PprCardMilitarySection active={[registrationRecord]} superseded={[]} voided={[]} route={personRoute} />,
    );
    expect(screen.queryByText(/Серия военного билета/)).not.toBeInTheDocument();

    rerender(
      <PprCardMilitarySection active={[withRestricted]} superseded={[]} voided={[]} route={personRoute} />,
    );
    expect(screen.getByText(/Серия военного билета/)).toBeInTheDocument();
    expect(screen.getByText(/Номер военного билета/)).toBeInTheDocument();
    expect(screen.getByText("АБ")).toBeInTheDocument();
    expect(screen.getByText("7654321")).toBeInTheDocument();
  });

  it("does not show redacted placeholder values", () => {
    const redacted = {
      ...registrationRecord,
      military_id_book_number: "***",
    };

    render(
      <PprCardMilitarySection active={[redacted]} superseded={[]} voided={[]} route={personRoute} />,
    );

    expect(screen.queryByText("***")).not.toBeInTheDocument();
    expect(screen.queryByText(/Номер военного билета/)).not.toBeInTheDocument();
  });

  it("creates registration record via person route", async () => {
    const onMutated = vi.fn();
    createMock.mockResolvedValue({ status: "committed" });

    render(
      <PprCardMilitarySection
        active={[]}
        superseded={[]}
        voided={[]}
        route={personRoute}
        editable
        onMutated={onMutated}
      />,
    );

    await fillMilitaryRank("Рядовой");
    fireEvent.change(screen.getByTestId("military-form-obligation"), { target: { value: "liable" } });
    fireEvent.click(screen.getByTestId("military-create-submit"));

    await waitFor(() => {
      expect(createMock).toHaveBeenCalledWith(
        personRoute,
        expect.objectContaining({
          command_id: "test-command-id-1",
          record: expect.objectContaining({
            record_kind: PPR_MILITARY_RECORD_KIND_REGISTRATION,
            military_rank: "Рядовой",
            personnel_composition: "soldiers",
            obligation_status: "liable",
          }),
        }),
      );
      expect(onMutated).toHaveBeenCalled();
    });
  });

  it("creates not_applicable record with notes only", async () => {
    createMock.mockResolvedValue({ status: "committed" });

    render(
      <PprCardMilitarySection
        active={[]}
        superseded={[]}
        voided={[]}
        route={personRoute}
        editable
      />,
    );

    fireEvent.click(screen.getByTestId("military-create-btn"));
    fireEvent.change(screen.getByTestId("military-form-kind"), {
      target: { value: PPR_MILITARY_RECORD_KIND_NOT_APPLICABLE },
    });
    fireEvent.change(screen.getByTestId("military-form-notes"), {
      target: { value: "Не подлежит" },
    });
    fireEvent.click(screen.getByTestId("military-create-submit"));

    await waitFor(() => {
      expect(createMock).toHaveBeenCalledWith(
        personRoute,
        expect.objectContaining({
          record: {
            record_kind: PPR_MILITARY_RECORD_KIND_NOT_APPLICABLE,
            notes: "Не подлежит",
          },
        }),
      );
    });
  });

  it("voids record with expected_updated_at", async () => {
    voidMock.mockResolvedValue({ status: "committed" });
    render(
      <PprCardMilitarySection
        active={[registrationRecord]}
        superseded={[]}
        voided={[]}
        route={personRoute}
        editable
      />,
    );

    fireEvent.click(screen.getByTestId("military-void-btn-201"));
    fireEvent.change(screen.getByTestId("military-void-reason"), { target: { value: "duplicate" } });
    fireEvent.click(screen.getByTestId("military-void-submit"));

    await waitFor(() => {
      expect(voidMock).toHaveBeenCalledWith(
        personRoute,
        201,
        expect.objectContaining({
          command_id: "test-command-id-1",
          reason: "duplicate",
          expected_updated_at: "2024-02-01T00:00:00Z",
        }),
      );
    });
  });

  it("supersedes record with replacement payload preserving prefilled fields", async () => {
    supersedeMock.mockResolvedValue({ status: "committed" });
    render(
      <PprCardMilitarySection
        active={[registrationRecord]}
        superseded={[]}
        voided={[]}
        route={personRoute}
        editable
      />,
    );

    fireEvent.click(screen.getByTestId("military-edit-btn-201"));
    expect(screen.getByTestId("military-form-composition")).toHaveValue("Рядовой состав");
    expect(screen.getByTestId("military-form-rank")).toHaveValue("Рядовой");
    expect(screen.getByTestId("military-form-obligation")).toHaveValue("liable");

    await pickComboboxOption("military-form-rank", "", "Ефрейтор");
    fireEvent.click(screen.getByTestId("military-supersede-submit"));

    await waitFor(() => {
      expect(supersedeMock).toHaveBeenCalledWith(
        personRoute,
        201,
        expect.objectContaining({
          expected_updated_at: "2024-02-01T00:00:00Z",
          replacement: expect.objectContaining({
            military_rank: "Ефрейтор",
            personnel_composition: "soldiers",
            obligation_status: "liable",
            registration_category: "II",
          }),
        }),
      );
    });
  });

  it("shows stale conflict refresh action on void", async () => {
    const onMutated = vi.fn();
    voidMock.mockRejectedValue(toApiError(409, { detail: "stale token" }));
    render(
      <PprCardMilitarySection
        active={[registrationRecord]}
        superseded={[]}
        voided={[]}
        route={personRoute}
        editable
        onMutated={onMutated}
      />,
    );

    fireEvent.click(screen.getByTestId("military-void-btn-201"));
    fireEvent.change(screen.getByTestId("military-void-reason"), { target: { value: "reason" } });
    fireEvent.click(screen.getByTestId("military-void-submit"));

    await waitFor(() => {
      expect(screen.getByTestId("military-void-error")).toBeInTheDocument();
      expect(screen.getByTestId("military-void-refresh")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("military-void-refresh"));
    expect(onMutated).toHaveBeenCalled();
  });

  it("uses employee route when provided", async () => {
    const employeeRoute = { kind: "employee" as const, id: "42" };
    createMock.mockResolvedValue({ status: "committed" });
    render(
      <PprCardMilitarySection
        active={[]}
        superseded={[]}
        voided={[]}
        route={employeeRoute}
        editable
      />,
    );

    await fillMilitaryRank("Рядовой");
    fireEvent.click(screen.getByTestId("military-create-submit"));

    await waitFor(() => {
      expect(createMock).toHaveBeenCalledWith(employeeRoute, expect.any(Object));
    });
  });

  it("create form drops registration fields from payload after switching to not_applicable", async () => {
    createMock.mockResolvedValue({ status: "committed" });
    render(
      <PprCardMilitarySection
        active={[]}
        superseded={[]}
        voided={[]}
        route={personRoute}
        editable
      />,
    );

    fireEvent.click(screen.getByTestId("military-create-btn"));
    await pickComboboxOption("military-form-composition", "Рядовой состав");
    await pickComboboxOption("military-form-rank", "Рядовой");
    fireEvent.change(screen.getByTestId("military-form-obligation"), { target: { value: "liable" } });
    fireEvent.change(screen.getByTestId("military-form-category"), { target: { value: "II" } });
    fireEvent.change(screen.getByTestId("military-form-kind"), {
      target: { value: PPR_MILITARY_RECORD_KIND_NOT_APPLICABLE },
    });
    fireEvent.change(screen.getByTestId("military-form-notes"), {
      target: { value: "Не подлежит" },
    });
    fireEvent.click(screen.getByTestId("military-create-submit"));

    await waitFor(() => {
      const record = createMock.mock.calls[0]?.[1]?.record as Record<string, unknown>;
      expect(record).toEqual({
        record_kind: PPR_MILITARY_RECORD_KIND_NOT_APPLICABLE,
        notes: "Не подлежит",
      });
      expect(record).not.toHaveProperty("military_rank");
      expect(record).not.toHaveProperty("obligation_status");
      expect(record).not.toHaveProperty("registration_category");
      expect(record).not.toHaveProperty("military_id_book_number");
    });
  });

  it("supersede form drops registration fields from replacement after switching to not_applicable", async () => {
    supersedeMock.mockResolvedValue({ status: "committed" });
    render(
      <PprCardMilitarySection
        active={[registrationRecord]}
        superseded={[]}
        voided={[]}
        route={personRoute}
        editable
      />,
    );

    fireEvent.click(screen.getByTestId("military-edit-btn-201"));
    await pickComboboxOption("military-form-composition", "Рядовой состав");
    await pickComboboxOption("military-form-rank", "Рядовой");
    fireEvent.change(screen.getByTestId("military-form-obligation"), { target: { value: "liable" } });
    fireEvent.change(screen.getByTestId("military-form-kind"), {
      target: { value: PPR_MILITARY_RECORD_KIND_NOT_APPLICABLE },
    });
    fireEvent.change(screen.getByTestId("military-form-notes"), {
      target: { value: "Не подлежит" },
    });
    fireEvent.click(screen.getByTestId("military-supersede-submit"));

    await waitFor(() => {
      const replacement = supersedeMock.mock.calls[0]?.[2]?.replacement as Record<string, unknown>;
      expect(replacement).toEqual({
        record_kind: PPR_MILITARY_RECORD_KIND_NOT_APPLICABLE,
        notes: "Не подлежит",
      });
      expect(replacement).not.toHaveProperty("military_rank");
      expect(replacement).not.toHaveProperty("registration_status");
    });
  });

  it("after refresh shows active replacement in ACTIVE and prior record in HISTORY", () => {
    const recordA = {
      ...historyRecord,
      record_id: 201,
      military_rank: "рядовой (A)",
      lifecycle_status: "superseded",
    };
    const recordB = {
      ...registrationRecord,
      record_id: 202,
      military_rank: "ефрейтор (B)",
      lifecycle_status: "active",
      updated_at: "2024-03-15T00:00:00Z",
    };

    render(
      <PprCardMilitarySection
        active={[recordB]}
        superseded={[recordA]}
        voided={[]}
        route={personRoute}
      />,
    );

    expect(screen.getByRole("heading", { name: "Действующая запись" })).toBeInTheDocument();
    expect(screen.getByTestId("military-record-202")).toHaveTextContent("ефрейтор (B)");
    expect(screen.queryByText("рядовой (A)")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /История замен \(1\)/ }));
    expect(screen.getByTestId("military-record-201")).toHaveTextContent("рядовой (A)");
  });

  it("read-only mode hides mutation controls", () => {
    render(
      <PprCardMilitarySection
        active={[registrationRecord]}
        superseded={[]}
        voided={[]}
        route={personRoute}
        editable={false}
      />,
    );

    expect(screen.getByTestId("military-record-201")).toBeInTheDocument();
    expect(screen.queryByTestId("military-create-btn")).not.toBeInTheDocument();
    expect(screen.queryByTestId("military-edit-btn-201")).not.toBeInTheDocument();
    expect(screen.queryByTestId("military-void-btn-201")).not.toBeInTheDocument();
  });

  it("places composition field before military rank in the form", () => {
    render(
      <PprCardMilitarySection active={[]} superseded={[]} voided={[]} route={personRoute} editable />,
    );

    fireEvent.click(screen.getByTestId("military-create-btn"));

    const compositionLabel = screen.getByText("Состав");
    const rankLabel = screen.getByText("Воинское звание");
    expect(
      rankLabel.compareDocumentPosition(compositionLabel) & Node.DOCUMENT_POSITION_PRECEDING,
    ).toBeTruthy();
  });

  it("shows only five current composition options without legacy label", async () => {
    render(
      <PprCardMilitarySection active={[]} superseded={[]} voided={[]} route={personRoute} editable />,
    );

    fireEvent.click(screen.getByTestId("military-create-btn"));
    const composition = screen.getByTestId("military-form-composition");
    fireEvent.click(composition);

    const list = await screen.findByTestId("military-form-composition-list");
    const options = list.querySelectorAll('[role="option"]');
    expect(options).toHaveLength(5);
    expect(Array.from(options).map((option) => option.textContent)).toEqual([
      "Рядовой состав",
      "Сержантский состав",
      "Офицерский состав",
      "Командный состав",
      "Иной состав",
    ]);
    expect(Array.from(options).map((option) => option.textContent)).not.toContain(
      "Рядовой и сержантский состав",
    );
  });

  it("filters rank options by composition and supports search", async () => {
    render(
      <PprCardMilitarySection active={[]} superseded={[]} voided={[]} route={personRoute} editable />,
    );

    fireEvent.click(screen.getByTestId("military-create-btn"));
    await pickComboboxOption("military-form-composition", "Офицерский состав");

    const rank = screen.getByTestId("military-form-rank");
    expect(rank).not.toBeDisabled();

    fireEvent.focus(rank);
    fireEvent.click(rank);
    fireEvent.change(rank, { target: { value: "лейт" } });

    const list = await screen.findByTestId("military-form-rank-list");
    expect(Array.from(list.querySelectorAll('[role="option"]')).map((option) => option.textContent)).toEqual([
      "Лейтенант",
      "Старший лейтенант",
    ]);
  });

  it("clears incompatible rank when composition changes", async () => {
    render(
      <PprCardMilitarySection active={[]} superseded={[]} voided={[]} route={personRoute} editable />,
    );

    fireEvent.click(screen.getByTestId("military-create-btn"));
    await pickComboboxOption("military-form-composition", "Офицерский состав");
    await pickComboboxOption("military-form-rank", "Полковник", "Полковник");
    expect(screen.getByTestId("military-form-rank")).toHaveValue("Полковник");

    await pickComboboxOption("military-form-composition", "Рядовой состав");
    expect(screen.getByTestId("military-form-rank")).toHaveValue("");
  });

  it("disables rank until composition is selected", () => {
    render(
      <PprCardMilitarySection active={[]} superseded={[]} voided={[]} route={personRoute} editable />,
    );

    fireEvent.click(screen.getByTestId("military-create-btn"));
    expect(screen.getByTestId("military-form-rank")).toBeDisabled();
    expect(screen.getByTestId("military-form-rank")).toHaveAttribute(
      "placeholder",
      "Сначала выберите состав",
    );
  });

  it("persists selected composition and rank in create payload", async () => {
    createMock.mockResolvedValue({ status: "committed" });

    render(
      <PprCardMilitarySection active={[]} superseded={[]} voided={[]} route={personRoute} editable />,
    );

    fireEvent.click(screen.getByTestId("military-create-btn"));
    await pickComboboxOption("military-form-composition", "Команд");
    await pickComboboxOption("military-form-rank", "Генерал-майор");
    fireEvent.change(screen.getByTestId("military-form-obligation"), { target: { value: "liable" } });
    fireEvent.click(screen.getByTestId("military-create-submit"));

    await waitFor(() => {
      expect(createMock).toHaveBeenCalledWith(
        personRoute,
        expect.objectContaining({
          record: expect.objectContaining({
            personnel_composition: "senior_officers",
            military_rank: "Генерал-майор",
          }),
        }),
      );
    });
  });

  it("displays legacy rank-only records with inferred composition label", () => {
    const legacyRecord = {
      ...registrationRecord,
      personnel_composition: null,
      military_rank: "Ефрейтор",
    };

    render(
      <PprCardMilitarySection active={[legacyRecord]} superseded={[]} voided={[]} route={personRoute} />,
    );

    const card = screen.getByTestId("military-record-201");
    expect(card).toHaveTextContent("Ефрейтор");
    expect(card).toHaveTextContent("Рядовой состав");
  });

  it("shows chevron on composition and rank comboboxes", () => {
    render(
      <PprCardMilitarySection active={[]} superseded={[]} voided={[]} route={personRoute} editable />,
    );

    fireEvent.click(screen.getByTestId("military-create-btn"));
    expect(screen.getByTestId("military-form-composition-chevron")).toHaveTextContent("▼");
    expect(screen.getByTestId("military-form-rank-chevron")).toHaveTextContent("▼");
  });

  it("changes composition without clearing the field first", async () => {
    render(
      <PprCardMilitarySection active={[]} superseded={[]} voided={[]} route={personRoute} editable />,
    );

    fireEvent.click(screen.getByTestId("military-create-btn"));
    await pickComboboxOption("military-form-composition", "", "Рядовой состав");
    expect(screen.getByTestId("military-form-composition")).toHaveValue("Рядовой состав");

    fireEvent.focus(screen.getByTestId("military-form-composition"));
    fireEvent.click(screen.getByTestId("military-form-composition"));
    fireEvent.click(screen.getByText("Офицерский состав"));
    expect(screen.getByTestId("military-form-composition")).toHaveValue("Офицерский состав");
  });

  it("accepts only seven digits in VUS number field", () => {
    render(
      <PprCardMilitarySection active={[]} superseded={[]} voided={[]} route={personRoute} editable />,
    );

    fireEvent.click(screen.getByTestId("military-create-btn"));
    const vus = screen.getByTestId("military-form-specialty-code");
    fireEvent.change(vus, { target: { value: "868123А" } });
    expect(vus).toHaveValue("868123");
    fireEvent.change(vus, { target: { value: "1234567890" } });
    expect(vus).toHaveValue("1234567");
  });

  it("keeps composition after Tab and leaves rank dropdown closed", async () => {
    render(
      <PprCardMilitarySection active={[]} superseded={[]} voided={[]} route={personRoute} editable />,
    );

    fireEvent.click(screen.getByTestId("military-create-btn"));
    await pickComboboxOption("military-form-composition", "", "Офицерский состав");
    expect(screen.getByTestId("military-form-composition")).toHaveValue("Офицерский состав");

    fireEvent.keyDown(screen.getByTestId("military-form-composition"), { key: "Tab" });
    fireEvent.focus(screen.getByTestId("military-form-rank"));

    await waitFor(() => {
      expect(screen.getByTestId("military-form-composition")).toHaveValue("Офицерский состав");
    });
    expect(screen.queryByTestId("military-form-rank-list")).not.toBeInTheDocument();
  });

  it("keeps composition when rank changes from Капитан to Старший лейтенант", async () => {
    render(
      <PprCardMilitarySection active={[]} superseded={[]} voided={[]} route={personRoute} editable />,
    );

    fireEvent.click(screen.getByTestId("military-create-btn"));
    await pickComboboxOption("military-form-composition", "", "Офицерский состав");
    await pickComboboxOption("military-form-rank", "", "Капитан");
    await pickComboboxOption("military-form-rank", "", "Старший лейтенант");

    expect(screen.getByTestId("military-form-composition")).toHaveValue("Офицерский состав");
    expect(screen.getByTestId("military-form-rank")).toHaveValue("Старший лейтенант");
  });

  it("does not clear confirmed composition or rank on blur", async () => {
    render(
      <PprCardMilitarySection active={[]} superseded={[]} voided={[]} route={personRoute} editable />,
    );

    fireEvent.click(screen.getByTestId("military-create-btn"));
    await pickComboboxOption("military-form-composition", "", "Офицерский состав");
    await pickComboboxOption("military-form-rank", "", "Капитан");

    fireEvent.blur(screen.getByTestId("military-form-composition"));
    fireEvent.blur(screen.getByTestId("military-form-rank"));

    await waitFor(() => {
      expect(screen.getByTestId("military-form-composition")).toHaveValue("Офицерский состав");
      expect(screen.getByTestId("military-form-rank")).toHaveValue("Капитан");
    });
  });

  it("hides add button when an active record exists", () => {
    render(
      <PprCardMilitarySection
        active={[registrationRecord]}
        superseded={[]}
        voided={[]}
        route={personRoute}
        editable
      />,
    );

    expect(screen.queryByTestId("military-create-btn")).not.toBeInTheDocument();
    expect(screen.getByTestId("military-edit-hint")).toBeInTheDocument();
    expect(screen.getByTestId("military-edit-btn-201")).toBeInTheDocument();
  });

  it("saves composition and rank changes through supersede instead of create", async () => {
    supersedeMock.mockResolvedValue({ status: "committed" });
    const officerRecord = {
      ...registrationRecord,
      personnel_composition: "officers",
      military_rank: "Старший лейтенант",
    };

    render(
      <PprCardMilitarySection
        active={[officerRecord]}
        superseded={[]}
        voided={[]}
        route={personRoute}
        editable
      />,
    );

    fireEvent.click(screen.getByTestId("military-edit-btn-201"));
    expect(screen.getByTestId("military-form-composition")).toHaveValue("Офицерский состав");
    expect(screen.getByTestId("military-form-rank")).toHaveValue("Старший лейтенант");

    await pickComboboxOption("military-form-composition", "", "Сержантский состав");
    await pickComboboxOption("military-form-rank", "", "Сержант 3 класса");
    fireEvent.click(screen.getByTestId("military-supersede-submit"));

    await waitFor(() => {
      expect(createMock).not.toHaveBeenCalled();
      expect(supersedeMock).toHaveBeenCalledWith(
        personRoute,
        201,
        expect.objectContaining({
          replacement: expect.objectContaining({
            personnel_composition: "sergeants",
            military_rank: "Сержант 3 класса",
          }),
        }),
      );
    });
  });

  it("shows error without success message when supersede fails", async () => {
    supersedeMock.mockRejectedValue(toApiError(409, { detail: "stale token" }));
    render(
      <PprCardMilitarySection
        active={[registrationRecord]}
        superseded={[]}
        voided={[]}
        route={personRoute}
        editable
      />,
    );

    fireEvent.click(screen.getByTestId("military-edit-btn-201"));
    fireEvent.click(screen.getByTestId("military-supersede-submit"));

    await waitFor(() => {
      expect(screen.getByTestId("military-supersede-error")).toBeInTheDocument();
    });
    expect(screen.queryByTestId("military-supersede-success")).not.toBeInTheDocument();
    expect(screen.getByTestId("military-form-rank")).toHaveValue("Рядовой");
  });
});
