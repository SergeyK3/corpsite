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

const registrationRecord: PprMilitaryRecordResponse = {
  record_id: 201,
  record_kind: PPR_MILITARY_RECORD_KIND_REGISTRATION,
  obligation_status: "liable",
  registration_category: "II",
  military_rank: "рядовой",
  military_specialty_code: "123456",
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
      military_id_book_number: "1234567",
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
    expect(screen.getByText("1234567")).toBeInTheDocument();
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

    fireEvent.click(screen.getByTestId("military-create-btn"));
    fireEvent.change(screen.getByTestId("military-form-rank"), { target: { value: "рядовой" } });
    fireEvent.change(screen.getByTestId("military-form-obligation"), { target: { value: "liable" } });
    fireEvent.click(screen.getByTestId("military-create-submit"));

    await waitFor(() => {
      expect(createMock).toHaveBeenCalledWith(
        personRoute,
        expect.objectContaining({
          command_id: "test-command-id-1",
          record: expect.objectContaining({
            record_kind: PPR_MILITARY_RECORD_KIND_REGISTRATION,
            military_rank: "рядовой",
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

  it("supersedes record with replacement payload", async () => {
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

    fireEvent.click(screen.getByTestId("military-supersede-btn-201"));
    fireEvent.change(screen.getByTestId("military-form-rank"), { target: { value: "ефрейтор" } });
    fireEvent.change(screen.getByTestId("military-form-status"), { target: { value: "registered" } });
    fireEvent.click(screen.getByTestId("military-supersede-submit"));

    await waitFor(() => {
      expect(supersedeMock).toHaveBeenCalledWith(
        personRoute,
        201,
        expect.objectContaining({
          expected_updated_at: "2024-02-01T00:00:00Z",
          replacement: expect.objectContaining({
            military_rank: "ефрейтор",
            registration_status: "registered",
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

    fireEvent.click(screen.getByTestId("military-create-btn"));
    fireEvent.change(screen.getByTestId("military-form-rank"), { target: { value: "рядовой" } });
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
    fireEvent.change(screen.getByTestId("military-form-rank"), { target: { value: "рядовой" } });
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

    fireEvent.click(screen.getByTestId("military-supersede-btn-201"));
    fireEvent.change(screen.getByTestId("military-form-rank"), { target: { value: "рядовой" } });
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
    expect(screen.queryByTestId("military-supersede-btn-201")).not.toBeInTheDocument();
    expect(screen.queryByTestId("military-void-btn-201")).not.toBeInTheDocument();
  });
});
