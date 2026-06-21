// FILE: corpsite-ui/app/admin/system/_components/tabs/UserLinkageReviewTab.tsx
"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import {
  approveUserLinkageReview,
  deferUserLinkageReview,
  fetchUserLinkageReviewAudit,
  fetchUserLinkageReviewQueue,
  mapUserLinkageReviewApiError,
  rejectUserLinkageReview,
  type UserLinkageReviewAuditItem,
  type UserLinkageReviewCandidate,
  type UserLinkageReviewSummary,
} from "../../_lib/userLinkageReviewApi.client";
import { formatDateTime } from "../../_lib/adminSystemLabels";
import ErrorBanner from "../shared/ErrorBanner";

const PAGE_SIZE = 50;

const CLASSIFICATION_OPTIONS = [
  "",
  "REVIEW_REQUIRED",
  "AMBIGUOUS",
  "IMPOSSIBLE",
  "EXCLUDED_SERVICE_ACCOUNT",
];

const STRATEGY_OPTIONS = ["", "LOGIN_SUFFIX", "NORMALIZED_FIO"];

const DECISION_OPTIONS = ["", "PENDING", "APPROVE", "REJECT", "DEFER"];

const EMPTY_SUMMARY: UserLinkageReviewSummary = {
  review_required: 0,
  ambiguous: 0,
  approved: 0,
  rejected: 0,
  deferred: 0,
  pending: 0,
};

function summaryCardClass(kind: "info" | "warn" | "success" | "danger" | "muted"): string {
  const base = "rounded-lg border px-3 py-2";
  switch (kind) {
    case "info":
      return `${base} border-blue-200 bg-blue-50 dark:border-blue-900 dark:bg-blue-950/40`;
    case "warn":
      return `${base} border-amber-200 bg-amber-50 dark:border-amber-900 dark:bg-amber-950/40`;
    case "success":
      return `${base} border-emerald-200 bg-emerald-50 dark:border-emerald-900 dark:bg-emerald-950/40`;
    case "danger":
      return `${base} border-rose-200 bg-rose-50 dark:border-rose-900 dark:bg-rose-950/40`;
    default:
      return `${base} border-zinc-200 bg-zinc-50 dark:border-zinc-700 dark:bg-zinc-900/40`;
  }
}

function decisionBadgeClass(state: string): string {
  switch (state) {
    case "APPROVE":
      return "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-200";
    case "REJECT":
      return "bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-200";
    case "DEFER":
      return "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-200";
    default:
      return "bg-zinc-100 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-200";
  }
}

export default function UserLinkageReviewTab() {
  const [candidates, setCandidates] = useState<UserLinkageReviewCandidate[]>([]);
  const [summary, setSummary] = useState<UserLinkageReviewSummary>(EMPTY_SUMMARY);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionBusyUserId, setActionBusyUserId] = useState<number | null>(null);
  const [auditItems, setAuditItems] = useState<UserLinkageReviewAuditItem[]>([]);
  const [auditLoading, setAuditLoading] = useState(false);
  const [reloadToken, setReloadToken] = useState(0);
  const [filters, setFilters] = useState({
    classification: "",
    strategy: "",
    decision_state: "",
    search: "",
  });

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetchUserLinkageReviewQueue({
        classification: filters.classification || undefined,
        strategy: filters.strategy || undefined,
        decision_state: filters.decision_state || undefined,
        search: filters.search || undefined,
        limit: PAGE_SIZE,
        offset,
      });
      setCandidates(res.candidates);
      setSummary(res.summary);
      setTotal(res.total);
    } catch (err) {
      setError(mapUserLinkageReviewApiError(err, "Не удалось загрузить очередь review"));
    } finally {
      setLoading(false);
    }
  }, [filters.classification, filters.decision_state, filters.search, filters.strategy, offset, reloadToken]);

  const loadAudit = useCallback(async () => {
    setAuditLoading(true);
    try {
      const res = await fetchUserLinkageReviewAudit({ limit: 20, offset: 0 });
      setAuditItems(res.items);
    } catch (err) {
      setError(mapUserLinkageReviewApiError(err, "Не удалось загрузить audit trail"));
    } finally {
      setAuditLoading(false);
    }
  }, [reloadToken]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    void loadAudit();
  }, [loadAudit]);

  const page = Math.floor(offset / PAGE_SIZE) + 1;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  const summaryCards = useMemo(
    () => [
      { label: "Review Required", value: summary.review_required, kind: "info" as const },
      { label: "Ambiguous", value: summary.ambiguous, kind: "warn" as const },
      { label: "Approved", value: summary.approved, kind: "success" as const },
      { label: "Rejected", value: summary.rejected, kind: "danger" as const },
      { label: "Deferred", value: summary.deferred, kind: "muted" as const },
    ],
    [summary],
  );

  async function runAction(
    userId: number,
    action: "approve" | "reject" | "defer",
  ): Promise<void> {
    setActionBusyUserId(userId);
    setError(null);
    try {
      const reason = window.prompt("Комментарий (необязательно):") ?? undefined;
      if (action === "approve") {
        await approveUserLinkageReview(userId, reason);
      } else if (action === "reject") {
        await rejectUserLinkageReview(userId, reason);
      } else {
        await deferUserLinkageReview(userId, reason);
      }
      setReloadToken((value) => value + 1);
    } catch (err) {
      setError(mapUserLinkageReviewApiError(err, "Не удалось сохранить решение"));
    } finally {
      setActionBusyUserId(null);
    }
  }

  return (
    <section className="space-y-4" data-testid="user-linkage-review-tab">
      <div
        className="rounded-lg border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-100"
        data-testid="user-linkage-review-warning"
      >
        This phase records review decisions only. No User ↔ Employee linkage is performed.
      </div>

      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="text-lg font-semibold">User Linkage Review</h2>
          <p className="text-sm text-zinc-600 dark:text-zinc-400">
            ADR-044 R2.3 — human review between preview and future execute.
          </p>
        </div>
        <button
          type="button"
          onClick={() => {
            setReloadToken((value) => value + 1);
          }}
          disabled={loading}
          className="rounded-lg border border-zinc-300 px-3 py-1 text-sm dark:border-zinc-600"
          data-testid="user-linkage-review-refresh"
        >
          Refresh
        </button>
      </div>

      <ErrorBanner message={error} />

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5" data-testid="user-linkage-review-summary">
        {summaryCards.map((card) => (
          <div key={card.label} className={summaryCardClass(card.kind)}>
            <p className="text-xs uppercase tracking-wide text-zinc-600 dark:text-zinc-400">
              {card.label}
            </p>
            <p className="mt-1 text-2xl font-semibold">{card.value}</p>
          </div>
        ))}
      </div>

      <div
        className="grid gap-2 rounded-lg border border-zinc-200 p-4 sm:grid-cols-2 lg:grid-cols-4 dark:border-zinc-700"
        data-testid="user-linkage-review-filters"
      >
        <label className="text-xs">
          classification
          <select
            value={filters.classification}
            onChange={(e) => {
              setOffset(0);
              setFilters((prev) => ({ ...prev, classification: e.target.value }));
            }}
            className="mt-1 w-full rounded border px-2 py-1 dark:border-zinc-600 dark:bg-zinc-900"
            data-testid="user-linkage-filter-classification"
          >
            {CLASSIFICATION_OPTIONS.map((value) => (
              <option key={value || "all"} value={value}>
                {value || "all"}
              </option>
            ))}
          </select>
        </label>
        <label className="text-xs">
          strategy
          <select
            value={filters.strategy}
            onChange={(e) => {
              setOffset(0);
              setFilters((prev) => ({ ...prev, strategy: e.target.value }));
            }}
            className="mt-1 w-full rounded border px-2 py-1 dark:border-zinc-600 dark:bg-zinc-900"
            data-testid="user-linkage-filter-strategy"
          >
            {STRATEGY_OPTIONS.map((value) => (
              <option key={value || "all"} value={value}>
                {value || "all"}
              </option>
            ))}
          </select>
        </label>
        <label className="text-xs">
          decision state
          <select
            value={filters.decision_state}
            onChange={(e) => {
              setOffset(0);
              setFilters((prev) => ({ ...prev, decision_state: e.target.value }));
            }}
            className="mt-1 w-full rounded border px-2 py-1 dark:border-zinc-600 dark:bg-zinc-900"
            data-testid="user-linkage-filter-decision"
          >
            {DECISION_OPTIONS.map((value) => (
              <option key={value || "all"} value={value}>
                {value || "all"}
              </option>
            ))}
          </select>
        </label>
        <label className="text-xs">
          search (login / user / employee)
          <input
            value={filters.search}
            onChange={(e) => {
              setOffset(0);
              setFilters((prev) => ({ ...prev, search: e.target.value }));
            }}
            className="mt-1 w-full rounded border px-2 py-1 dark:border-zinc-600 dark:bg-zinc-900"
            data-testid="user-linkage-filter-search"
          />
        </label>
      </div>

      {loading ? (
        <p className="text-sm text-zinc-500" data-testid="user-linkage-review-loading">
          Загрузка…
        </p>
      ) : candidates.length === 0 ? (
        <p className="text-sm text-zinc-500" data-testid="user-linkage-review-empty">
          Нет кандидатов по текущим фильтрам.
        </p>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-zinc-200 dark:border-zinc-700">
          <table className="min-w-full text-sm" data-testid="user-linkage-review-table">
            <thead className="bg-zinc-50 text-left text-xs uppercase dark:bg-zinc-900">
              <tr>
                <th className="px-3 py-2">login</th>
                <th className="px-3 py-2">user</th>
                <th className="px-3 py-2">proposed employee</th>
                <th className="px-3 py-2">strategy</th>
                <th className="px-3 py-2">classification</th>
                <th className="px-3 py-2">confidence</th>
                <th className="px-3 py-2">reason codes</th>
                <th className="px-3 py-2">decision</th>
                <th className="px-3 py-2">actions</th>
              </tr>
            </thead>
            <tbody>
              {candidates.map((row) => {
                const busy = actionBusyUserId === row.user_id;
                const canApprove =
                  row.classification === "REVIEW_REQUIRED" ||
                  row.classification === "AMBIGUOUS";
                return (
                  <tr
                    key={row.user_id}
                    className="border-t border-zinc-200 dark:border-zinc-800"
                    data-testid={`user-linkage-row-${row.user_id}`}
                  >
                    <td className="px-3 py-2 font-mono text-xs">{row.login ?? "—"}</td>
                    <td className="px-3 py-2">
                      <div>{row.user_full_name || "—"}</div>
                      <div className="text-xs text-zinc-500">#{row.user_id}</div>
                    </td>
                    <td className="px-3 py-2">
                      <div>{row.employee_name || "—"}</div>
                      <div className="text-xs text-zinc-500">
                        {row.proposed_employee_id ? `#${row.proposed_employee_id}` : "—"}
                      </div>
                    </td>
                    <td className="px-3 py-2">{row.match_strategy ?? "—"}</td>
                    <td className="px-3 py-2">{row.classification}</td>
                    <td className="px-3 py-2">{row.confidence ?? "—"}</td>
                    <td className="px-3 py-2 font-mono text-xs">
                      {row.reason_codes.length ? row.reason_codes.join(", ") : "—"}
                    </td>
                    <td className="px-3 py-2">
                      <span
                        className={`rounded px-2 py-0.5 text-xs ${decisionBadgeClass(row.decision_state)}`}
                      >
                        {row.decision_state}
                      </span>
                      {row.latest_decision_at ? (
                        <div className="mt-1 text-xs text-zinc-500">
                          {formatDateTime(row.latest_decision_at)}
                        </div>
                      ) : null}
                    </td>
                    <td className="px-3 py-2">
                      <div className="flex flex-wrap gap-1">
                        <button
                          type="button"
                          disabled={busy || !canApprove}
                          onClick={() => void runAction(row.user_id, "approve")}
                          className="rounded bg-emerald-600 px-2 py-1 text-xs text-white disabled:opacity-40"
                          data-testid={`user-linkage-approve-${row.user_id}`}
                        >
                          Approve
                        </button>
                        <button
                          type="button"
                          disabled={busy}
                          onClick={() => void runAction(row.user_id, "reject")}
                          className="rounded bg-rose-600 px-2 py-1 text-xs text-white disabled:opacity-40"
                          data-testid={`user-linkage-reject-${row.user_id}`}
                        >
                          Reject
                        </button>
                        <button
                          type="button"
                          disabled={busy}
                          onClick={() => void runAction(row.user_id, "defer")}
                          className="rounded bg-amber-600 px-2 py-1 text-xs text-white disabled:opacity-40"
                          data-testid={`user-linkage-defer-${row.user_id}`}
                        >
                          Defer
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {totalPages > 1 ? (
        <div className="flex items-center gap-2 text-sm">
          <button
            type="button"
            disabled={offset <= 0 || loading}
            onClick={() => setOffset((value) => Math.max(0, value - PAGE_SIZE))}
            className="rounded border px-2 py-1 dark:border-zinc-600"
          >
            Prev
          </button>
          <span>
            Page {page} / {totalPages}
          </span>
          <button
            type="button"
            disabled={offset + PAGE_SIZE >= total || loading}
            onClick={() => setOffset((value) => value + PAGE_SIZE)}
            className="rounded border px-2 py-1 dark:border-zinc-600"
          >
            Next
          </button>
        </div>
      ) : null}

      <section className="space-y-2" data-testid="user-linkage-review-audit">
        <h3 className="text-base font-semibold">Audit trail</h3>
        {auditLoading ? (
          <p className="text-sm text-zinc-500">Загрузка audit…</p>
        ) : auditItems.length === 0 ? (
          <p className="text-sm text-zinc-500">Пока нет решений.</p>
        ) : (
          <div className="overflow-x-auto rounded-lg border border-zinc-200 dark:border-zinc-700">
            <table className="min-w-full text-sm">
              <thead className="bg-zinc-50 text-left text-xs uppercase dark:bg-zinc-900">
                <tr>
                  <th className="px-3 py-2">when</th>
                  <th className="px-3 py-2">reviewer</th>
                  <th className="px-3 py-2">user</th>
                  <th className="px-3 py-2">employee</th>
                  <th className="px-3 py-2">decision</th>
                  <th className="px-3 py-2">reason</th>
                </tr>
              </thead>
              <tbody>
                {auditItems.map((item) => (
                  <tr
                    key={item.decision_id}
                    className="border-t border-zinc-200 dark:border-zinc-800"
                    data-testid={`user-linkage-audit-${item.decision_id}`}
                  >
                    <td className="px-3 py-2">{formatDateTime(item.created_at)}</td>
                    <td className="px-3 py-2">{item.reviewer_login ?? `#${item.reviewer_user_id}`}</td>
                    <td className="px-3 py-2">
                      {item.user_login ?? item.user_full_name ?? `#${item.user_id}`}
                    </td>
                    <td className="px-3 py-2">
                      {item.employee_name ?? (item.proposed_employee_id ? `#${item.proposed_employee_id}` : "—")}
                    </td>
                    <td className="px-3 py-2">{item.decision}</td>
                    <td className="px-3 py-2">{item.reason ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </section>
  );
}
