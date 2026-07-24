import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import EmploymentVerificationPageClient from "./EmploymentVerificationPageClient";

const {
  apiAuthMe,
  listPendingEmploymentTasks,
  getEmploymentTaskReview,
  confirmEmploymentTask,
  rejectEmploymentTask,
  replace,
} = vi.hoisted(() => ({
  apiAuthMe: vi.fn(),
  listPendingEmploymentTasks: vi.fn(),
  getEmploymentTaskReview: vi.fn(),
  confirmEmploymentTask: vi.fn(),
  rejectEmploymentTask: vi.fn(),
  replace: vi.fn(),
}));

let searchParams = new URLSearchParams("");

vi.mock("@/lib/api", () => ({
  apiAuthMe,
}));

vi.mock("@/lib/personnelNav", () => ({
  canSeeHrProcessesNav: () => true,
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace }),
  useSearchParams: () => searchParams,
}));

vi.mock("next/link", () => ({
  default: ({
    children,
    href,
    onClick,
    className,
    ...rest
  }: {
    children: React.ReactNode;
    href: string;
    onClick?: (event: React.MouseEvent) => void;
    className?: string;
  }) => (
    <a
      href={href}
      className={className}
      onClick={(event) => {
        event.preventDefault();
        onClick?.(event as unknown as React.MouseEvent);
      }}
      {...rest}
    >
      {children}
    </a>
  ),
}));

vi.mock("../_lib/personnelVerificationApi.client", async (importOriginal) => {
  const actual =
    await importOriginal<typeof import("../_lib/personnelVerificationApi.client")>();
  return {
    ...actual,
    listPendingEmploymentTasks,
    getEmploymentTaskReview,
    confirmEmploymentTask,
    rejectEmploymentTask,
  };
});

function makeTask(taskId: number, overrides: Partial<typeof TASK_A> = {}) {
  return {
    task_id: taskId,
    person_id: 5,
    control_point: "employment_episode",
    object_type: "person_external_employment",
    object_id: 100 + taskId,
    object_version_id: 200 + taskId,
    policy_id: 1,
    policy_version: 1,
    status: "pending",
    created_at: "2026-07-24T08:00:00+00:00",
    updated_at: "2026-07-24T08:00:00+00:00",
    closed_at: null,
    prior_updated_at: "2026-07-24T07:00:00+00:00",
    ...overrides,
  };
}

function makeReview(
  task: ReturnType<typeof makeTask>,
  priorEmployer: string,
  revisionEmployer: string,
  priorPosition: string,
  revisionPosition: string,
) {
  return {
    task,
    person_id: task.person_id,
    person_full_name: "Иванова Анна",
    prior: {
      employment_id: task.object_id,
      record_kind: "episode",
      employer_name: priorEmployer,
      department_name: "Терапия",
      position_title: priorPosition,
      employment_type: null,
      started_at: "2020-01-01",
      ended_at: null,
      termination_reason: null,
      document_reference: null,
      notes: null,
      lifecycle_status: "active",
      updated_at: "2026-07-24T07:00:00+00:00",
    },
    revision: {
      employment_id: task.object_version_id,
      record_kind: "episode",
      employer_name: revisionEmployer,
      department_name: "Терапия",
      position_title: revisionPosition,
      employment_type: null,
      started_at: "2021-01-01",
      ended_at: null,
      termination_reason: null,
      document_reference: null,
      notes: "исправление",
      lifecycle_status: "active",
      updated_at: "2026-07-24T08:00:00+00:00",
    },
    verification_state: "pending",
  };
}

const TASK_A = makeTask(1);
const TASK_B = makeTask(2);
const REVIEW_A = makeReview(
  TASK_A,
  "ТОО Кардио",
  "ТОО Кардио",
  "тестовый тестолог",
  "тестовый тестолог",
);
const REVIEW_B = makeReview(
  TASK_B,
  "ТОО База",
  "ТОО Кардио111",
  "базовая должность",
  "кардиотестолог",
);

const TASK = makeTask(11);
const REVIEW = makeReview(TASK, "Клиника А", "Клиника Б", "Врач", "Хирург");

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  searchParams = new URLSearchParams("");
});

beforeEach(() => {
  apiAuthMe.mockResolvedValue({ user_id: 1, has_personnel_admin: true });
  listPendingEmploymentTasks.mockResolvedValue({ items: [], count: 0 });
  getEmploymentTaskReview.mockResolvedValue(REVIEW);
  confirmEmploymentTask.mockResolvedValue({
    task: { ...TASK, status: "completed" },
    attestation: {
      attestation_id: 1,
      decision: "verified",
      decided_at: "2026-07-24T09:00:00+00:00",
      comment: null,
    },
    prior_employment_id: 101,
    revision_employment_id: 202,
    prior_lifecycle_status: "superseded",
    revision_lifecycle_status: "active",
  });
  rejectEmploymentTask.mockResolvedValue({
    task: { ...TASK, status: "rejected" },
    attestation: {
      attestation_id: 2,
      decision: "rejected",
      decided_at: "2026-07-24T09:00:00+00:00",
      comment: null,
    },
    prior_employment_id: 101,
    revision_employment_id: 202,
    prior_lifecycle_status: "active",
    revision_lifecycle_status: "voided",
  });
});

describe("EmploymentVerificationPageClient", () => {
  it("shows empty queue state", async () => {
    render(<EmploymentVerificationPageClient />);
    expect(
      await screen.findByTestId("employment-verification-empty"),
    ).toHaveTextContent("Нет заданий на проверку");
  });

  it("loads queue and opens task comparison", async () => {
    listPendingEmploymentTasks.mockResolvedValue({ items: [TASK], count: 1 });
    getEmploymentTaskReview.mockResolvedValue(REVIEW);

    render(<EmploymentVerificationPageClient />);
    expect(await screen.findByText("Иванова Анна")).toBeInTheDocument();
    expect(screen.getByText("Клиника А — Врач")).toBeInTheDocument();
    expect(screen.getByText("Клиника Б — Хирург")).toBeInTheDocument();

    fireEvent.click(screen.getByTestId("employment-verification-open-11"));
    expect(replace).toHaveBeenCalledWith(
      "/directory/personnel/employment-verification?task_id=11",
    );

    expect(
      await screen.findByTestId("employment-verification-task-panel"),
    ).toBeInTheDocument();
    expect(screen.getByTestId("compare-row-employer_name")).toHaveAttribute(
      "data-changed",
      "true",
    );
    expect(screen.getByTestId("compare-row-department_name")).toHaveAttribute(
      "data-changed",
      "false",
    );
  });

  it("confirms revision, closes panel, refreshes queue, and clears task_id", async () => {
    listPendingEmploymentTasks
      .mockResolvedValueOnce({ items: [TASK], count: 1 })
      .mockResolvedValueOnce({ items: [], count: 0 });
    searchParams = new URLSearchParams("task_id=11");
    render(<EmploymentVerificationPageClient />);

    expect(
      await screen.findByTestId("employment-verification-confirm"),
    ).toBeEnabled();
    fireEvent.click(screen.getByTestId("employment-verification-confirm"));
    const confirmButtons = screen.getAllByRole("button", { name: "Подтвердить" });
    fireEvent.click(confirmButtons[confirmButtons.length - 1]);

    await waitFor(() => {
      expect(confirmEmploymentTask).toHaveBeenCalledWith(11, {
        expected_prior_updated_at: "2026-07-24T07:00:00+00:00",
      });
    });
    await waitFor(() => {
      expect(replace).toHaveBeenCalledWith(
        "/directory/personnel/employment-verification",
      );
    });
    expect(
      await screen.findByTestId("employment-verification-action-success"),
    ).toHaveTextContent("Решение сохранено. Очередь обновлена.");
    expect(
      screen.queryByTestId("employment-verification-task-panel"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByTestId("employment-verification-confirm"),
    ).not.toBeInTheDocument();
    expect(
      await screen.findByTestId("employment-verification-empty"),
    ).toBeInTheDocument();
    expect(listPendingEmploymentTasks).toHaveBeenCalledTimes(2);
  });

  it("rejects revision, closes panel, refreshes queue, and clears task_id", async () => {
    listPendingEmploymentTasks
      .mockResolvedValueOnce({ items: [TASK], count: 1 })
      .mockResolvedValueOnce({ items: [], count: 0 });
    searchParams = new URLSearchParams("task_id=11");
    render(<EmploymentVerificationPageClient />);

    fireEvent.click(await screen.findByTestId("employment-verification-reject"));
    const rejectButtons = screen.getAllByRole("button", { name: "Отклонить" });
    fireEvent.click(rejectButtons[rejectButtons.length - 1]);

    await waitFor(() => {
      expect(rejectEmploymentTask).toHaveBeenCalledWith(11, {
        expected_prior_updated_at: "2026-07-24T07:00:00+00:00",
      });
    });
    await waitFor(() => {
      expect(replace).toHaveBeenCalledWith(
        "/directory/personnel/employment-verification",
      );
    });
    expect(
      await screen.findByTestId("employment-verification-action-success"),
    ).toHaveTextContent("Решение сохранено. Очередь обновлена.");
    expect(
      screen.queryByTestId("employment-verification-task-panel"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByTestId("employment-verification-reject"),
    ).not.toBeInTheDocument();
    expect(
      await screen.findByTestId("employment-verification-empty"),
    ).toBeInTheDocument();
    expect(listPendingEmploymentTasks).toHaveBeenCalledTimes(2);
  });

  it("after reject A, opening B shows only B review and rejects B", async () => {
    listPendingEmploymentTasks
      .mockResolvedValueOnce({ items: [TASK_A], count: 1 })
      .mockResolvedValueOnce({ items: [TASK_B], count: 1 })
      .mockResolvedValueOnce({ items: [], count: 0 });

    getEmploymentTaskReview.mockImplementation(async (taskId: number) => {
      if (taskId === 1) return REVIEW_A;
      if (taskId === 2) return REVIEW_B;
      throw new Error(`unexpected task ${taskId}`);
    });

    rejectEmploymentTask
      .mockResolvedValueOnce({
        task: { ...TASK_A, status: "rejected" },
        attestation: {
          attestation_id: 2,
          decision: "rejected",
          decided_at: "2026-07-24T09:00:00+00:00",
          comment: null,
        },
        prior_employment_id: TASK_A.object_id,
        revision_employment_id: TASK_A.object_version_id,
        prior_lifecycle_status: "active",
        revision_lifecycle_status: "voided",
      })
      .mockResolvedValueOnce({
        task: { ...TASK_B, status: "rejected" },
        attestation: {
          attestation_id: 3,
          decision: "rejected",
          decided_at: "2026-07-24T09:05:00+00:00",
          comment: null,
        },
        prior_employment_id: TASK_B.object_id,
        revision_employment_id: TASK_B.object_version_id,
        prior_lifecycle_status: "active",
        revision_lifecycle_status: "voided",
      });

    searchParams = new URLSearchParams("task_id=1");
    render(<EmploymentVerificationPageClient />);

    expect(await screen.findByTestId("employment-verification-task-panel")).toBeInTheDocument();
    expect(screen.getAllByText("ТОО Кардио — тестовый тестолог").length).toBeGreaterThan(0);

    fireEvent.click(screen.getByTestId("employment-verification-reject"));
    const rejectAButtons = screen.getAllByRole("button", { name: "Отклонить" });
    fireEvent.click(rejectAButtons[rejectAButtons.length - 1]);

    await waitFor(() => {
      expect(rejectEmploymentTask).toHaveBeenCalledWith(1, {
        expected_prior_updated_at: "2026-07-24T07:00:00+00:00",
      });
    });
    expect(
      await screen.findByTestId("employment-verification-action-success"),
    ).toBeInTheDocument();
    expect(
      screen.queryByTestId("employment-verification-task-panel"),
    ).not.toBeInTheDocument();
    expect(await screen.findByText("ТОО Кардио111 — кардиотестолог")).toBeInTheDocument();

    // Stale URL may still point at rejected task A; open B must switch atomically.
    searchParams = new URLSearchParams("task_id=1");
    fireEvent.click(screen.getByTestId("employment-verification-open-2"));

    expect(replace).toHaveBeenCalledWith(
      "/directory/personnel/employment-verification?task_id=2",
    );
    const panelB = await screen.findByTestId("employment-verification-task-panel");
    expect(panelB).toHaveTextContent("ТОО Кардио111 — кардиотестолог");
    expect(panelB).toHaveTextContent("ТОО База — базовая должность");
    expect(panelB).not.toHaveTextContent("тестовый тестолог");
    expect(screen.queryByText(/Task 1 is not pending/i)).not.toBeInTheDocument();

    fireEvent.click(screen.getByTestId("employment-verification-reject"));
    const rejectBButtons = screen.getAllByRole("button", { name: "Отклонить" });
    fireEvent.click(rejectBButtons[rejectBButtons.length - 1]);

    await waitFor(() => {
      expect(rejectEmploymentTask).toHaveBeenLastCalledWith(2, {
        expected_prior_updated_at: "2026-07-24T07:00:00+00:00",
      });
    });
    expect(rejectEmploymentTask).toHaveBeenCalledTimes(2);
    expect(
      screen.queryByTestId("employment-verification-task-panel"),
    ).not.toBeInTheDocument();
    expect(
      await screen.findByTestId("employment-verification-empty"),
    ).toBeInTheDocument();
  });

  it("ignores stale review response from previously selected task", async () => {
    let resolveA: ((value: typeof REVIEW_A) => void) | null = null;
    const delayedA = new Promise<typeof REVIEW_A>((resolve) => {
      resolveA = resolve;
    });
    let reviewACalls = 0;

    listPendingEmploymentTasks.mockResolvedValue({ items: [TASK_A, TASK_B], count: 2 });
    getEmploymentTaskReview.mockImplementation((taskId: number) => {
      if (taskId === 2) return Promise.resolve(REVIEW_B);
      if (taskId === 1) {
        reviewACalls += 1;
        // First call serves the queue row; later call is the detail request we delay.
        if (reviewACalls === 1) return Promise.resolve(REVIEW_A);
        return delayedA;
      }
      return Promise.reject(new Error(`unexpected ${taskId}`));
    });

    render(<EmploymentVerificationPageClient />);
    expect(await screen.findByTestId("employment-verification-open-2")).toBeInTheDocument();

    fireEvent.click(screen.getByTestId("employment-verification-open-1"));
    expect(screen.getByTestId("employment-verification-detail-loading")).toBeInTheDocument();
    expect(
      screen.queryByTestId("employment-verification-task-panel"),
    ).not.toBeInTheDocument();

    fireEvent.click(screen.getByTestId("employment-verification-open-2"));
    const panelB = await screen.findByTestId("employment-verification-task-panel");
    expect(panelB).toHaveTextContent("ТОО Кардио111 — кардиотестолог");
    expect(panelB).not.toHaveTextContent("тестовый тестолог");

    resolveA?.(REVIEW_A);
    await waitFor(() => {
      expect(screen.getByTestId("employment-verification-task-panel")).toHaveTextContent(
        "ТОО Кардио111 — кардиотестолог",
      );
    });
    expect(screen.getByTestId("employment-verification-task-panel")).not.toHaveTextContent(
      "тестовый тестолог",
    );
  });

  it("hides confirm/reject actions for non-pending task review", async () => {
    const nonPending = {
      ...REVIEW,
      task: { ...TASK, status: "rejected" },
      verification_state: "rejected",
    };
    listPendingEmploymentTasks.mockResolvedValue({ items: [TASK], count: 1 });
    getEmploymentTaskReview.mockResolvedValue(nonPending);
    searchParams = new URLSearchParams("task_id=11");
    render(<EmploymentVerificationPageClient />);

    expect(
      await screen.findByTestId("employment-verification-task-panel"),
    ).toBeInTheDocument();
    expect(
      screen.getByTestId("employment-verification-actions-unavailable"),
    ).toBeInTheDocument();
    expect(
      screen.queryByTestId("employment-verification-confirm"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByTestId("employment-verification-reject"),
    ).not.toBeInTheDocument();
  });

  it("blocks in-flight double confirm submit", async () => {
    let resolveConfirm: ((value: unknown) => void) | null = null;
    confirmEmploymentTask.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveConfirm = resolve;
        }),
    );
    listPendingEmploymentTasks.mockResolvedValue({ items: [TASK], count: 1 });
    getEmploymentTaskReview.mockResolvedValue(REVIEW);
    searchParams = new URLSearchParams("task_id=11");
    render(<EmploymentVerificationPageClient />);

    fireEvent.click(await screen.findByTestId("employment-verification-confirm"));
    const confirmButtons = screen.getAllByRole("button", { name: "Подтвердить" });
    fireEvent.click(confirmButtons[confirmButtons.length - 1]);

    await waitFor(() => {
      expect(confirmEmploymentTask).toHaveBeenCalledTimes(1);
    });
    expect(screen.getByTestId("employment-verification-confirm")).toBeDisabled();

    // Second confirm while first request is in flight must not call API again.
    fireEvent.click(screen.getByTestId("employment-verification-confirm"));
    const confirmAgain = screen.queryAllByRole("button", { name: "Подтвердить" });
    if (confirmAgain.length > 0) {
      fireEvent.click(confirmAgain[confirmAgain.length - 1]);
    }
    expect(confirmEmploymentTask).toHaveBeenCalledTimes(1);

    resolveConfirm?.({
      task: { ...TASK, status: "completed" },
      attestation: {
        attestation_id: 1,
        decision: "verified",
        decided_at: "2026-07-24T09:00:00+00:00",
        comment: null,
      },
      prior_employment_id: 101,
      revision_employment_id: 202,
      prior_lifecycle_status: "superseded",
      revision_lifecycle_status: "active",
    });
    listPendingEmploymentTasks.mockResolvedValue({ items: [], count: 0 });
    await waitFor(() => {
      expect(
        screen.queryByTestId("employment-verification-task-panel"),
      ).not.toBeInTheDocument();
    });
    expect(confirmEmploymentTask).toHaveBeenCalledTimes(1);
  });

  it("shows friendly messages for 403/404/409 and closes on decision conflict", async () => {
    const { VerificationApiError } = await import(
      "../_lib/personnelVerificationApi.client"
    );
    listPendingEmploymentTasks.mockRejectedValue(
      new VerificationApiError(
        "forbidden",
        403,
        "Недостаточно прав для проверки трудовой биографии.",
      ),
    );
    render(<EmploymentVerificationPageClient />);
    expect(
      await screen.findByTestId("employment-verification-queue-error"),
    ).toHaveTextContent("Недостаточно прав");

    cleanup();
    listPendingEmploymentTasks.mockResolvedValue({ items: [TASK], count: 1 });
    getEmploymentTaskReview.mockRejectedValue(
      new VerificationApiError("not_found", 404, "Задание или запись не найдены."),
    );
    searchParams = new URLSearchParams("task_id=11");
    render(<EmploymentVerificationPageClient />);
    expect(
      await screen.findByTestId("employment-verification-detail-error"),
    ).toHaveTextContent("не найдены");

    cleanup();
    listPendingEmploymentTasks
      .mockResolvedValueOnce({ items: [TASK], count: 1 })
      .mockResolvedValueOnce({ items: [], count: 0 });
    getEmploymentTaskReview.mockResolvedValue(REVIEW);
    confirmEmploymentTask.mockRejectedValue(
      new VerificationApiError(
        "conflict",
        409,
        "Task 11 is not pending (status='rejected')",
      ),
    );
    searchParams = new URLSearchParams("task_id=11");
    render(<EmploymentVerificationPageClient />);
    fireEvent.click(await screen.findByTestId("employment-verification-confirm"));
    const confirmButtons = screen.getAllByRole("button", { name: "Подтвердить" });
    fireEvent.click(confirmButtons[confirmButtons.length - 1]);

    expect(
      await screen.findByTestId("employment-verification-detail-error"),
    ).toHaveTextContent("уже обработано");
    expect(screen.queryByText(/Task 11 is not pending/i)).not.toBeInTheDocument();
    expect(
      screen.queryByTestId("employment-verification-task-panel"),
    ).not.toBeInTheDocument();
  });
});
