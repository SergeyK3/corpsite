// FILE: corpsite-ui/app/admin/system/_components/personnel-lifecycle/OverrideDetailDrawer.tsx
"use client";

import { useState } from "react";

import {
  approveOverride,
  mapPersonnelLifecycleApiError,
  rejectOverride,
  reconfirmOverride,
  revokeOverride,
  type OverrideDetail,
} from "../../_lib/personnelLifecycleApi.client";
import {
  canApproveOverride,
  canReconfirmOverride,
  canRejectOverride,
  canRevokeOverride,
  effectiveOverrideValue,
  overrideStatusClass,
} from "../../_lib/personnelLifecycleLabels";
import { formatActorLabel, formatDateTime } from "../../_lib/adminSystemLabels";
import ErrorBanner, { SuccessBanner } from "../shared/ErrorBanner";
import JsonViewer from "../shared/JsonViewer";
import ConfirmDialog from "../shared/ConfirmDialog";

type OverrideDetailDrawerProps = {
  detail: OverrideDetail | null;
  loading?: boolean;
  open: boolean;
  hasHrGovernance: boolean;
  onClose: () => void;
  onUpdated: () => void;
};

export default function OverrideDetailDrawer({
  detail,
  loading = false,
  open,
  hasHrGovernance,
  onClose,
  onUpdated,
}: OverrideDetailDrawerProps) {
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [comment, setComment] = useState("");
  const [confirmAction, setConfirmAction] = useState<"revoke" | null>(null);

  if (!open) return null;

  async function runAction(
    action: "approve" | "reject" | "revoke" | "reconfirm",
  ): Promise<void> {
    if (!detail) return;
    setBusy(true);
    setError(null);
    setSuccess(null);
    try {
      if (action === "approve") {
        await approveOverride(detail.override_id, comment ? { comment } : undefined);
      } else if (action === "reject") {
        const reason = comment.trim();
        if (!reason) throw new Error("Укажите reason/comment для reject");
        await rejectOverride(detail.override_id, { reason });
      } else if (action === "revoke") {
        const reason = comment.trim();
        if (reason.length < 10) throw new Error("Revoke reason должен быть не короче 10 символов");
        await revokeOverride(detail.override_id, { reason });
      } else {
        await reconfirmOverride(detail.override_id, comment ? { reason: comment } : undefined);
      }
      setSuccess(`Override #${detail.override_id}: ${action} выполнен`);
      setComment("");
      onUpdated();
    } catch (err) {
      setError(mapPersonnelLifecycleApiError(err, `Не удалось выполнить ${action}`));
    } finally {
      setBusy(false);
      setConfirmAction(null);
    }
  }

  const showApprove = detail && hasHrGovernance && canApproveOverride(detail.status);
  const showReject = detail && hasHrGovernance && canRejectOverride(detail.status);
  const showRevoke = detail && canRevokeOverride(detail.status);
  const showReconfirm = detail && canReconfirmOverride(detail.status, detail.stale_flag);

  return (
    <div
      className="fixed inset-0 z-50 flex justify-end bg-black/30"
      role="dialog"
      aria-modal="true"
      data-testid="override-detail-drawer"
    >
      <div className="h-full w-full max-w-xl overflow-y-auto border-l border-zinc-200 bg-white p-4 dark:border-zinc-700 dark:bg-zinc-950">
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-lg font-semibold">
            Override #{detail?.override_id ?? "…"}
          </h3>
          <button
            type="button"
            onClick={onClose}
            className="rounded border px-2 py-1 text-sm dark:border-zinc-600"
          >
            Закрыть
          </button>
        </div>

        <ErrorBanner message={error} />
        <SuccessBanner message={success} />

        {loading ? (
          <p className="text-sm text-zinc-500" data-testid="override-detail-loading">
            Загрузка…
          </p>
        ) : !detail ? (
          <p className="text-sm text-zinc-500">Override не найден.</p>
        ) : (
          <div className="space-y-4 text-sm">
            <dl className="grid gap-2 sm:grid-cols-2">
              <Field label="status">
                <span className={`rounded px-1.5 py-0.5 text-xs ${overrideStatusClass(detail.status)}`}>
                  {detail.status}
                </span>
              </Field>
              <Field label="tier" value={String(detail.tier)} />
              <Field label="owner_domain" value={detail.owner_domain} />
              <Field label="scope_type" value={detail.scope_type} />
              <Field label="field_path" value={detail.field_path} />
              <Field label="created_by" value={formatActorLabel(detail.created_by_user_id)} />
              <Field label="created_at" value={formatDateTime(detail.created_at)} />
              <Field label="approved_by" value={formatActorLabel(detail.approved_by_user_id)} />
              <Field label="approved_at" value={formatDateTime(detail.approved_at)} />
            </dl>

            <JsonViewer title="canonical value" value={detail.canonical_value} />
            <JsonViewer title="override value" value={detail.override_value} />
            <JsonViewer title="effective value" value={effectiveOverrideValue(detail)} />

            {detail.justification ? (
              <div>
                <div className="text-xs text-zinc-500">justification</div>
                <p className="mt-1 whitespace-pre-wrap">{detail.justification}</p>
              </div>
            ) : null}

            {detail.evidence_url ? (
              <div>
                <div className="text-xs text-zinc-500">evidence</div>
                <a
                  href={detail.evidence_url}
                  target="_blank"
                  rel="noreferrer"
                  className="text-blue-600 hover:underline dark:text-blue-400"
                >
                  {detail.evidence_url}
                </a>
              </div>
            ) : null}

            <JsonViewer title="history / metadata" value={detail.metadata} />

            {(showApprove || showReject || showRevoke || showReconfirm) ? (
              <div className="space-y-2 rounded-lg border border-zinc-200 p-3 dark:border-zinc-700">
                <label className="block text-xs">
                  comment / reason
                  <textarea
                    value={comment}
                    onChange={(e) => setComment(e.target.value)}
                    rows={2}
                    className="mt-1 w-full rounded border px-2 py-1 dark:border-zinc-600 dark:bg-zinc-900"
                    data-testid="override-action-comment"
                  />
                </label>
                <div className="flex flex-wrap gap-2">
                  {showApprove ? (
                    <ActionButton
                      label="Approve"
                      testId="override-approve-btn"
                      disabled={busy}
                      onClick={() => void runAction("approve")}
                    />
                  ) : null}
                  {showReject ? (
                    <ActionButton
                      label="Reject"
                      testId="override-reject-btn"
                      disabled={busy}
                      onClick={() => void runAction("reject")}
                    />
                  ) : null}
                  {showRevoke ? (
                    <ActionButton
                      label="Revoke"
                      testId="override-revoke-btn"
                      disabled={busy}
                      onClick={() => setConfirmAction("revoke")}
                    />
                  ) : null}
                  {showReconfirm ? (
                    <ActionButton
                      label="Reconfirm"
                      testId="override-reconfirm-btn"
                      disabled={busy}
                      onClick={() => void runAction("reconfirm")}
                    />
                  ) : null}
                </div>
              </div>
            ) : null}
          </div>
        )}
      </div>

      <ConfirmDialog
        open={confirmAction === "revoke"}
        title="Revoke override?"
        message="Override будет отозван. Укажите reason не короче 10 символов в поле comment."
        confirmLabel="Revoke"
        onConfirm={() => void runAction("revoke")}
        onCancel={() => setConfirmAction(null)}
      />
    </div>
  );
}

function Field({
  label,
  value,
  children,
}: {
  label: string;
  value?: string;
  children?: React.ReactNode;
}) {
  return (
    <div>
      <dt className="text-xs text-zinc-500">{label}</dt>
      <dd className="font-medium break-all">{children ?? value}</dd>
    </div>
  );
}

function ActionButton({
  label,
  testId,
  disabled,
  onClick,
}: {
  label: string;
  testId: string;
  disabled: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className="rounded-lg border border-zinc-300 px-3 py-1 text-sm disabled:opacity-50 dark:border-zinc-600"
      data-testid={testId}
    >
      {label}
    </button>
  );
}
