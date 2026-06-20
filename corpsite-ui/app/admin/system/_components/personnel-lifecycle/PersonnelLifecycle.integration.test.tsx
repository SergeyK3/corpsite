import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";

import LifecycleRunPanel from "./LifecycleRunPanel";
import EffectivePersonViewer from "./EffectivePersonViewer";
import ValidationPanel from "./ValidationPanel";
import PersonnelEventsPanel from "./PersonnelEventsPanel";
import OverrideDetailDrawer from "./OverrideDetailDrawer";
import type { OverrideDetail } from "../../_lib/personnelLifecycleApi.client";

vi.mock("../../_lib/personnelLifecycleApi.client", () => ({
  previewLifecycleRun: vi.fn(),
  executeLifecycleRun: vi.fn(),
  fetchEffectivePerson: vi.fn(),
  fetchLifecycleValidation: vi.fn(),
  fetchPersonnelEvents: vi.fn(),
  fetchPersonnelEvent: vi.fn(),
  approveOverride: vi.fn(),
  rejectOverride: vi.fn(),
  revokeOverride: vi.fn(),
  reconfirmOverride: vi.fn(),
  mapPersonnelLifecycleApiError: (_err: unknown, fallback: string) => fallback,
}));

import {
  previewLifecycleRun,
  executeLifecycleRun,
  fetchEffectivePerson,
  fetchLifecycleValidation,
  fetchPersonnelEvents,
  approveOverride,
} from "../../_lib/personnelLifecycleApi.client";

const mockedPreview = vi.mocked(previewLifecycleRun);
const mockedExecute = vi.mocked(executeLifecycleRun);
const mockedEffective = vi.mocked(fetchEffectivePerson);
const mockedValidation = vi.mocked(fetchLifecycleValidation);
const mockedEvents = vi.mocked(fetchPersonnelEvents);
const mockedApprove = vi.mocked(approveOverride);

describe("Personnel Lifecycle UI integration", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedEvents.mockResolvedValue({ items: [], total: 0, limit: 100, offset: 0 });
  });

  afterEach(() => {
    cleanup();
  });

  it("run preview flow renders report sections", async () => {
    mockedPreview.mockResolvedValue({
      previous_snapshot_id: 1,
      snapshot_id: 2,
      dry_run: true,
      refresh_cache: true,
      enqueue: false,
      sync_persons: false,
      run_status: "completed",
      duration_ms: 1200,
      effective_cache: { entries: 10 },
      monthly_diff: { changed: 3 },
      personnel_events: {},
      enrollment: {},
      person_sync: { created: 1 },
      validation: { ok: true },
      warnings: ["sample warning"],
      errors: [],
    });

    render(<LifecycleRunPanel />);

    fireEvent.change(screen.getByTestId("lifecycle-run-previous-snapshot"), {
      target: { value: "1" },
    });
    fireEvent.change(screen.getByTestId("lifecycle-run-current-snapshot"), {
      target: { value: "2" },
    });
    fireEvent.click(screen.getByTestId("lifecycle-run-preview-btn"));

    await waitFor(() => {
      expect(screen.getByTestId("lifecycle-run-report")).toBeInTheDocument();
    });
    expect(screen.getByTestId("lifecycle-report-effective-cache")).toBeInTheDocument();
    expect(screen.getByTestId("lifecycle-report-monthly-diff")).toBeInTheDocument();
    expect(screen.getByTestId("lifecycle-report-person-sync")).toBeInTheDocument();
    expect(screen.getByTestId("lifecycle-report-validation")).toBeInTheDocument();
    expect(mockedPreview).toHaveBeenCalled();
    expect(mockedExecute).not.toHaveBeenCalled();
  });

  it("run execute flow calls execute endpoint after confirm", async () => {
    mockedExecute.mockResolvedValue({
      run_id: 42,
      previous_snapshot_id: 1,
      snapshot_id: 2,
      dry_run: false,
      refresh_cache: true,
      enqueue: false,
      sync_persons: false,
      run_status: "completed",
      duration_ms: 500,
      effective_cache: {},
      monthly_diff: {},
      personnel_events: {},
      enrollment: {},
      person_sync: {},
      validation: {},
      warnings: [],
      errors: [],
    });

    render(<LifecycleRunPanel />);

    fireEvent.change(screen.getByTestId("lifecycle-run-previous-snapshot"), {
      target: { value: "1" },
    });
    fireEvent.change(screen.getByTestId("lifecycle-run-current-snapshot"), {
      target: { value: "2" },
    });
    fireEvent.click(screen.getByTestId("lifecycle-run-execute-btn"));
    const dialog = screen.getByRole("dialog");
    fireEvent.click(within(dialog).getByRole("button", { name: "Execute" }));

    await waitFor(() => {
      expect(mockedExecute).toHaveBeenCalled();
    });
  });

  it("events filtering passes filters to API", async () => {
    render(<PersonnelEventsPanel />);

    await waitFor(() => {
      expect(mockedEvents).toHaveBeenCalled();
    });

    fireEvent.change(screen.getByTestId("personnel-events-filter-event_type"), {
      target: { value: "HIRE" },
    });

    await waitFor(() => {
      expect(mockedEvents).toHaveBeenCalledWith(
        expect.objectContaining({ event_type: "HIRE" }),
      );
    });
  });

  it("override workflow shows approve for pending and calls API", async () => {
    const detail: OverrideDetail = {
      override_id: 7,
      scope_type: "PERSON",
      scope_key: "iin:123",
      field_path: "position",
      status: "pending_approval",
      tier: 1,
      owner_domain: "hr",
      stale_flag: false,
      metadata: {},
    };
    mockedApprove.mockResolvedValue({ ...detail, status: "active" });

    render(
      <OverrideDetailDrawer
        detail={detail}
        open
        hasHrGovernance
        onClose={vi.fn()}
        onUpdated={vi.fn()}
      />,
    );

    expect(screen.getByTestId("override-approve-btn")).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("override-approve-btn"));

    await waitFor(() => {
      expect(mockedApprove).toHaveBeenCalledWith(7, undefined);
    });
  });

  it("effective person viewer loads and renders payloads", async () => {
    mockedEffective.mockResolvedValue({
      snapshot_id: 2,
      entry_id: 10,
      person_key: "iin:770101234567",
      scope_type: "PERSON",
      record_kind: "roster",
      canonical_payload: { name: "Test" },
      effective_payload: { name: "Override Test" },
      applied_override_ids: [5],
    });

    render(<EffectivePersonViewer />);
    fireEvent.change(screen.getByTestId("effective-person-key-input"), {
      target: { value: "iin:770101234567" },
    });
    fireEvent.click(screen.getByTestId("effective-person-load-btn"));

    await waitFor(() => {
      expect(screen.getByTestId("effective-person-result")).toBeInTheDocument();
    });
    expect(screen.getByTestId("effective-person-canonical")).toBeInTheDocument();
    expect(screen.getByTestId("effective-person-effective")).toBeInTheDocument();
  });

  it("validation panel renders diagnostic cards", async () => {
    mockedValidation.mockResolvedValue({
      previous_snapshot_id: 1,
      snapshot_id: 2,
      checks: [
        { code: "duplicate_active_overrides", severity: "ok", count: 0 },
        { code: "duplicate_active_assignments", severity: "ok", count: 0 },
        { code: "active_assignment_without_person", severity: "ok", count: 0 },
        { code: "personnel_events_stuck_detected", severity: "warning", count: 2 },
        { code: "outdated_effective_cache", severity: "ok", count: 0 },
      ],
      warnings_count: 1,
      errors_count: 0,
      warnings: ["personnel events still detected: 2"],
      errors: [],
    });

    render(<ValidationPanel />);
    fireEvent.change(screen.getByTestId("validation-previous-snapshot"), {
      target: { value: "1" },
    });
    fireEvent.change(screen.getByTestId("validation-current-snapshot"), {
      target: { value: "2" },
    });
    fireEvent.click(screen.getByTestId("validation-run-btn"));

    await waitFor(() => {
      expect(screen.getByTestId("validation-results")).toBeInTheDocument();
    });
    expect(screen.getByTestId("validation-card-duplicate_active_overrides")).toBeInTheDocument();
    expect(screen.getByTestId("validation-card-personnel_events_stuck_detected")).toHaveTextContent("2");
  });
});
