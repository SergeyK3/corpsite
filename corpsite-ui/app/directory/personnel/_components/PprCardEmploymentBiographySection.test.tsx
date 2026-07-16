import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import PprCardEmploymentBiographySection from "./PprCardEmploymentBiographySection";
import type { PprExternalEmploymentRecordResponse } from "../_lib/pprQueryTypes";
import {
  PPR_EXTERNAL_EMPLOYMENT_RECORD_KIND_ATTESTATION_NONE,
  PPR_EXTERNAL_EMPLOYMENT_RECORD_KIND_EPISODE,
  PPR_EXTERNAL_EMPLOYMENT_RECORD_KIND_NARRATIVE_SUMMARY,
} from "../_lib/pprQueryTypes";
import { toApiError } from "@/lib/api";

const createMock = vi.fn();
const voidMock = vi.fn();
const supersedeMock = vi.fn();
let commandCounter = 0;

vi.mock("../_lib/pprCommandApi.client", () => ({
  createExternalEmployment: (...args: unknown[]) => createMock(...args),
  voidExternalEmployment: (...args: unknown[]) => voidMock(...args),
  supersedeExternalEmployment: (...args: unknown[]) => supersedeMock(...args),
  newPprCommandId: () => {
    commandCounter += 1;
    return `test-command-id-${commandCounter}`;
  },
}));

const personRoute = { kind: "person" as const, id: 501 };

const activeRecords: PprExternalEmploymentRecordResponse[] = [
  {
    record_id: 101,
    record_kind: PPR_EXTERNAL_EMPLOYMENT_RECORD_KIND_EPISODE,
    employer_name: "Новый работодатель",
    department_name: null,
    position_title: "Инженер",
    employment_type: null,
    started_at: "2020-01-01",
    ended_at: null,
    termination_reason: null,
    document_reference: null,
    source_system: "manual",
    source_id: null,
    provenance: null,
    notes: null,
    employee_context_id: null,
    verification_status: "pending",
    lifecycle_status: "active",
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-02-01T00:00:00Z",
  },
  {
    record_id: 100,
    record_kind: PPR_EXTERNAL_EMPLOYMENT_RECORD_KIND_NARRATIVE_SUMMARY,
    employer_name: null,
    department_name: null,
    position_title: null,
    employment_type: null,
    started_at: null,
    ended_at: null,
    termination_reason: null,
    document_reference: null,
    source_system: "manual",
    source_id: null,
    provenance: null,
    notes: "Сводный стаж 10 лет",
    employee_context_id: null,
    verification_status: "pending",
    lifecycle_status: "active",
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-02-01T00:00:00Z",
  },
];

beforeEach(() => {
  createMock.mockReset();
  voidMock.mockReset();
  supersedeMock.mockReset();
  commandCounter = 0;
});

afterEach(() => {
  cleanup();
});

describe("PprCardEmploymentBiographySection", () => {
  it("shows empty state", () => {
    render(
      <PprCardEmploymentBiographySection
        active={[]}
        superseded={[]}
        voided={[]}
        route={personRoute}
        editable
      />,
    );
    expect(screen.getByTestId("emp-bio-empty")).toBeInTheDocument();
  });

  it("renders active records in backend order without re-sorting", () => {
    render(
      <PprCardEmploymentBiographySection
        active={activeRecords}
        superseded={[]}
        voided={[]}
        route={personRoute}
      />,
    );

    const cards = screen.getAllByTestId(/emp-bio-record-/);
    expect(cards[0]).toHaveTextContent("Новый работодатель");
    expect(cards[1]).toHaveTextContent("Сводная запись о стаже");
  });

  it("read-only mode shows records without mutation controls", () => {
    render(
      <PprCardEmploymentBiographySection
        active={activeRecords}
        superseded={[]}
        voided={[]}
        route={personRoute}
        editable={false}
      />,
    );

    expect(screen.getByTestId("emp-bio-record-101")).toBeInTheDocument();
    expect(screen.queryByTestId("emp-bio-create-btn")).not.toBeInTheDocument();
    expect(screen.queryByTestId("emp-bio-supersede-btn-101")).not.toBeInTheDocument();
    expect(screen.queryByTestId("emp-bio-void-btn-101")).not.toBeInTheDocument();
  });

  it("creates episode record via person route", async () => {
    const onMutated = vi.fn();
    createMock.mockResolvedValue({ status: "committed" });

    render(
      <PprCardEmploymentBiographySection
        active={[]}
        superseded={[]}
        voided={[]}
        route={personRoute}
        editable
        onMutated={onMutated}
      />,
    );

    fireEvent.click(screen.getByTestId("emp-bio-create-btn"));
    fireEvent.change(screen.getByTestId("emp-bio-form-employer"), { target: { value: "ТОО Тест" } });
    fireEvent.change(screen.getByTestId("emp-bio-form-position"), { target: { value: "Инженер" } });
    fireEvent.change(screen.getByTestId("emp-bio-form-started"), { target: { value: "2018-03-01" } });
    fireEvent.click(screen.getByTestId("emp-bio-create-submit"));

    await waitFor(() => {
      expect(createMock).toHaveBeenCalledWith(
        personRoute,
        expect.objectContaining({
          command_id: "test-command-id-1",
          record: expect.objectContaining({
            record_kind: PPR_EXTERNAL_EMPLOYMENT_RECORD_KIND_EPISODE,
            employer_name: "ТОО Тест",
            position_title: "Инженер",
          }),
        }),
      );
      expect(onMutated).toHaveBeenCalled();
    });
  });

  it("voids record with expected_updated_at", async () => {
    voidMock.mockResolvedValue({ status: "committed" });
    render(
      <PprCardEmploymentBiographySection
        active={activeRecords}
        superseded={[]}
        voided={[]}
        route={personRoute}
        editable
      />,
    );

    fireEvent.click(screen.getByTestId("emp-bio-void-btn-101"));
    fireEvent.change(screen.getByTestId("emp-bio-void-reason"), { target: { value: "duplicate" } });
    fireEvent.click(screen.getByTestId("emp-bio-void-submit"));

    await waitFor(() => {
      expect(voidMock).toHaveBeenCalledWith(
        personRoute,
        101,
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
      <PprCardEmploymentBiographySection
        active={activeRecords}
        superseded={[]}
        voided={[]}
        route={personRoute}
        editable
      />,
    );

    fireEvent.click(screen.getByTestId("emp-bio-supersede-btn-101"));
    fireEvent.change(screen.getByTestId("emp-bio-form-employer"), { target: { value: "Replacement Co" } });
    fireEvent.change(screen.getByTestId("emp-bio-form-position"), { target: { value: "Lead" } });
    fireEvent.change(screen.getByTestId("emp-bio-form-started"), { target: { value: "2021-01-01" } });
    fireEvent.click(screen.getByTestId("emp-bio-supersede-submit"));

    await waitFor(() => {
      expect(supersedeMock).toHaveBeenCalledWith(
        personRoute,
        101,
        expect.objectContaining({
          expected_updated_at: "2024-02-01T00:00:00Z",
          replacement: expect.objectContaining({
            employer_name: "Replacement Co",
          }),
        }),
      );
    });
  });

  it("attestation_none create sends only record_kind", async () => {
    createMock.mockResolvedValue({ status: "committed" });
    render(
      <PprCardEmploymentBiographySection
        active={[]}
        superseded={[]}
        voided={[]}
        route={personRoute}
        editable
      />,
    );

    fireEvent.click(screen.getByTestId("emp-bio-create-btn"));
    fireEvent.change(screen.getByTestId("emp-bio-form-kind"), {
      target: { value: PPR_EXTERNAL_EMPLOYMENT_RECORD_KIND_ATTESTATION_NONE },
    });
    fireEvent.click(screen.getByTestId("emp-bio-create-submit"));

    await waitFor(() => {
      expect(createMock).toHaveBeenCalledWith(
        personRoute,
        expect.objectContaining({
          record: { record_kind: PPR_EXTERNAL_EMPLOYMENT_RECORD_KIND_ATTESTATION_NONE },
        }),
      );
    });
  });

  it("narrative_summary requires notes before API call", async () => {
    render(
      <PprCardEmploymentBiographySection
        active={[]}
        superseded={[]}
        voided={[]}
        route={personRoute}
        editable
      />,
    );

    fireEvent.click(screen.getByTestId("emp-bio-create-btn"));
    fireEvent.change(screen.getByTestId("emp-bio-form-kind"), {
      target: { value: PPR_EXTERNAL_EMPLOYMENT_RECORD_KIND_NARRATIVE_SUMMARY },
    });
    fireEvent.click(screen.getByTestId("emp-bio-create-submit"));

    await waitFor(() => {
      expect(screen.getByTestId("emp-bio-create-error")).toHaveTextContent(/текст сводной/i);
    });
    expect(createMock).not.toHaveBeenCalled();
  });

  it("supersede replacement contains only allowed write fields", async () => {
    supersedeMock.mockResolvedValue({ status: "committed" });
    render(
      <PprCardEmploymentBiographySection
        active={activeRecords}
        superseded={[]}
        voided={[]}
        route={personRoute}
        editable
      />,
    );

    fireEvent.click(screen.getByTestId("emp-bio-supersede-btn-101"));
    fireEvent.change(screen.getByTestId("emp-bio-form-employer"), { target: { value: "Replacement Co" } });
    fireEvent.change(screen.getByTestId("emp-bio-form-position"), { target: { value: "Lead" } });
    fireEvent.change(screen.getByTestId("emp-bio-form-started"), { target: { value: "2021-01-01" } });
    fireEvent.click(screen.getByTestId("emp-bio-supersede-submit"));

    await waitFor(() => {
      const replacement = supersedeMock.mock.calls[0]?.[2]?.replacement as Record<string, unknown>;
      expect(replacement).toEqual({
        record_kind: PPR_EXTERNAL_EMPLOYMENT_RECORD_KIND_EPISODE,
        employer_name: "Replacement Co",
        department_name: null,
        position_title: "Lead",
        started_at: "2021-01-01",
        ended_at: null,
      });
      expect(replacement).not.toHaveProperty("lifecycle_status");
      expect(replacement).not.toHaveProperty("record_id");
    });
  });

  it("shows validation error from API", async () => {
    createMock.mockRejectedValue(toApiError(422, { detail: "position_title is required" }));
    render(
      <PprCardEmploymentBiographySection
        active={[]}
        superseded={[]}
        voided={[]}
        route={personRoute}
        editable
      />,
    );

    fireEvent.click(screen.getByTestId("emp-bio-create-btn"));
    fireEvent.click(screen.getByTestId("emp-bio-create-submit"));

    await waitFor(() => {
      expect(screen.getByTestId("emp-bio-create-error")).toBeInTheDocument();
    });
  });

  it("shows stale conflict refresh action on void", async () => {
    const onMutated = vi.fn();
    voidMock.mockRejectedValue(toApiError(409, { detail: "stale token" }));
    render(
      <PprCardEmploymentBiographySection
        active={activeRecords}
        superseded={[]}
        voided={[]}
        route={personRoute}
        editable
        onMutated={onMutated}
      />,
    );

    fireEvent.click(screen.getByTestId("emp-bio-void-btn-101"));
    fireEvent.change(screen.getByTestId("emp-bio-void-reason"), { target: { value: "reason" } });
    fireEvent.click(screen.getByTestId("emp-bio-void-submit"));

    await waitFor(() => {
      expect(screen.getByTestId("emp-bio-void-error")).toHaveTextContent(/stale token|изменены/i);
      expect(screen.getByTestId("emp-bio-void-refresh")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("emp-bio-void-refresh"));
    expect(onMutated).toHaveBeenCalled();
  });

  it("blocks double submit while create is loading", async () => {
    let resolveCreate: ((value: unknown) => void) | undefined;
    createMock.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveCreate = resolve;
        }),
    );

    render(
      <PprCardEmploymentBiographySection
        active={[]}
        superseded={[]}
        voided={[]}
        route={personRoute}
        editable
      />,
    );

    fireEvent.click(screen.getByTestId("emp-bio-create-btn"));
    fireEvent.change(screen.getByTestId("emp-bio-form-employer"), { target: { value: "ТОО Тест" } });
    fireEvent.change(screen.getByTestId("emp-bio-form-position"), { target: { value: "Инженер" } });
    fireEvent.change(screen.getByTestId("emp-bio-form-started"), { target: { value: "2018-03-01" } });

    const submit = screen.getByTestId("emp-bio-create-submit");
    fireEvent.click(submit);
    fireEvent.click(submit);

    await waitFor(() => {
      expect(submit).toBeDisabled();
    });
    expect(createMock).toHaveBeenCalledTimes(1);

    resolveCreate?.({ status: "committed" });
    await waitFor(() => {
      expect(createMock).toHaveBeenCalledTimes(1);
    });
  });

  it("reuses command_id during in-flight create despite rerender", async () => {
    let resolveCreate: ((value: unknown) => void) | undefined;
    createMock.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveCreate = resolve;
        }),
    );

    const { rerender } = render(
      <PprCardEmploymentBiographySection
        active={[]}
        superseded={[]}
        voided={[]}
        route={personRoute}
        editable
      />,
    );

    fireEvent.click(screen.getByTestId("emp-bio-create-btn"));
    fireEvent.change(screen.getByTestId("emp-bio-form-employer"), { target: { value: "ТОО Тест" } });
    fireEvent.change(screen.getByTestId("emp-bio-form-position"), { target: { value: "Инженер" } });
    fireEvent.change(screen.getByTestId("emp-bio-form-started"), { target: { value: "2018-03-01" } });
    fireEvent.click(screen.getByTestId("emp-bio-create-submit"));

    rerender(
      <PprCardEmploymentBiographySection
        active={[]}
        superseded={[]}
        voided={[]}
        route={personRoute}
        editable
      />,
    );

    await waitFor(() => {
      expect(createMock).toHaveBeenCalledTimes(1);
      expect(createMock.mock.calls[0]?.[1]?.command_id).toBe("test-command-id-1");
    });

    resolveCreate?.({ status: "committed" });
  });

  it("uses employee route when provided", async () => {
    const employeeRoute = { kind: "employee" as const, id: "42" };
    createMock.mockResolvedValue({ status: "committed" });
    render(
      <PprCardEmploymentBiographySection
        active={[]}
        superseded={[]}
        voided={[]}
        route={employeeRoute}
        editable
      />,
    );

    fireEvent.click(screen.getByTestId("emp-bio-create-btn"));
    fireEvent.change(screen.getByTestId("emp-bio-form-kind"), {
      target: { value: PPR_EXTERNAL_EMPLOYMENT_RECORD_KIND_NARRATIVE_SUMMARY },
    });
    fireEvent.change(screen.getByTestId("emp-bio-form-notes"), { target: { value: "Summary text" } });
    fireEvent.click(screen.getByTestId("emp-bio-create-submit"));

    await waitFor(() => {
      expect(createMock).toHaveBeenCalledWith(employeeRoute, expect.any(Object));
    });
  });
});
