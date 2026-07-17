"use client";

import * as React from "react";

import {
  intakeDraftStatusLabel,
  intakeLinkStatusBadgeClass,
  intakeLinkStatusLabel,
} from "@/app/intake/_lib/intakeLabels";
import {
  formatPersonnelApplicationDateTime,
} from "../_lib/personnelApplicationLabels";
import {
  issueIntakeLink,
  mapPersonnelApplicationsApiError,
  reissueIntakeLink,
  revokeIntakeLink,
  type PersonnelApplicationDetail,
} from "../_lib/personnelApplicationsApi.client";

type Props = {
  detail: PersonnelApplicationDetail;
  onRefresh: () => void;
  onOpenReview?: (applicationId: number) => void;
  readOnly?: boolean;
};

export default function PersonnelApplicationIntakeSection({ detail, onRefresh, onOpenReview, readOnly = false }: Props) {
  const [busy, setBusy] = React.useState<string | null>(null);
  const [actionError, setActionError] = React.useState<string | null>(null);
  const [issuedLinkPath, setIssuedLinkPath] = React.useState<string | null>(null);

  const linkStatus = detail.intake_link_status;
  const draftStatus = detail.intake_draft_status;
  const canIssue = !linkStatus || linkStatus === "revoked" || linkStatus === "expired";
  const canReissue = linkStatus === "issued" || linkStatus === "opened";
  const canRevoke = linkStatus === "issued" || linkStatus === "opened";
  const canOpenReview =
    draftStatus === "submitted" ||
    linkStatus === "submitted" ||
    detail.status === "under_review" ||
    detail.status === "review_completed";

  async function runAction(action: "issue" | "reissue" | "revoke") {
    setBusy(action);
    setActionError(null);
    try {
      if (action === "issue") {
        const result = await issueIntakeLink(detail.application_id);
        setIssuedLinkPath(result.intake_url_path);
      } else if (action === "reissue") {
        const result = await reissueIntakeLink(detail.application_id);
        setIssuedLinkPath(result.intake_url_path);
      } else {
        await revokeIntakeLink(detail.application_id);
        setIssuedLinkPath(null);
      }
      onRefresh();
    } catch (e) {
      setActionError(mapPersonnelApplicationsApiError(e, "Не удалось выполнить действие"));
    } finally {
      setBusy(null);
    }
  }

  return (
    <section className="space-y-3" data-testid="personnel-application-intake-section">
      <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">Анкета претендента</h3>
      <div className="grid gap-3 sm:grid-cols-2">
        <div>
          <div className="text-xs font-medium uppercase tracking-wide text-zinc-500">Статус ссылки</div>
          <div className="mt-1">
            <span
              className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${intakeLinkStatusBadgeClass(linkStatus)}`}
            >
              {intakeLinkStatusLabel(linkStatus)}
            </span>
          </div>
        </div>
        <div>
          <div className="text-xs font-medium uppercase tracking-wide text-zinc-500">Статус анкеты</div>
          <div className="mt-0.5 text-sm text-zinc-800 dark:text-zinc-200">
            {intakeDraftStatusLabel(draftStatus)}
          </div>
        </div>
        <div>
          <div className="text-xs font-medium uppercase tracking-wide text-zinc-500">Дата открытия</div>
          <div className="mt-0.5 text-sm text-zinc-800 dark:text-zinc-200">
            {formatPersonnelApplicationDateTime(detail.intake_opened_at)}
          </div>
        </div>
        <div>
          <div className="text-xs font-medium uppercase tracking-wide text-zinc-500">Дата отправки</div>
          <div className="mt-0.5 text-sm text-zinc-800 dark:text-zinc-200">
            {formatPersonnelApplicationDateTime(detail.intake_submitted_at)}
          </div>
        </div>
      </div>

      {actionError ? (
        <p className="text-sm text-red-600 dark:text-red-400">{actionError}</p>
      ) : null}

      {issuedLinkPath ? (
        <div className="rounded-lg border border-sky-200 bg-sky-50 px-3 py-2 text-sm dark:border-sky-900 dark:bg-sky-950/30">
          <p className="font-medium text-sky-900 dark:text-sky-200">Ссылка для претендента</p>
          <code className="mt-1 block break-all text-xs text-sky-800 dark:text-sky-300">{issuedLinkPath}</code>
        </div>
      ) : null}

      {!readOnly ? (
      <div className="flex flex-wrap gap-2">
        {canIssue ? (
          <button
            type="button"
            disabled={busy != null}
            onClick={() => void runAction("issue")}
            className="rounded-lg bg-sky-600 px-3 py-1.5 text-sm text-white hover:bg-sky-700 disabled:opacity-50"
            data-testid="intake-issue-link-button"
          >
            {busy === "issue" ? "Выдача…" : "Выдать ссылку"}
          </button>
        ) : null}
        {canReissue ? (
          <button
            type="button"
            disabled={busy != null}
            onClick={() => void runAction("reissue")}
            className="rounded-lg border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-700"
            data-testid="intake-reissue-link-button"
          >
            {busy === "reissue" ? "Перевыпуск…" : "Перевыпустить ссылку"}
          </button>
        ) : null}
        {canRevoke ? (
          <button
            type="button"
            disabled={busy != null}
            onClick={() => void runAction("revoke")}
            className="rounded-lg border border-red-300 px-3 py-1.5 text-sm text-red-700 dark:border-red-900 dark:text-red-300"
            data-testid="intake-revoke-link-button"
          >
            {busy === "revoke" ? "Отзыв…" : "Отозвать ссылку"}
          </button>
        ) : null}
        {canOpenReview ? (
          <button
            type="button"
            onClick={() => onOpenReview?.(detail.application_id)}
            className="rounded-lg border border-emerald-300 px-3 py-1.5 text-sm text-emerald-800 dark:border-emerald-900 dark:text-emerald-300"
            data-testid="intake-open-review-button"
          >
            Открыть анкету
          </button>
        ) : null}
      </div>
      ) : null}
    </section>
  );
}
