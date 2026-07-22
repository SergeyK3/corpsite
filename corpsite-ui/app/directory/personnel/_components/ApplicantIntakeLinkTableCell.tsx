"use client";

import * as React from "react";

import {
  intakeDraftStatusLabel,
  intakeLinkStatusBadgeClass,
  intakeLinkStatusLabel,
} from "@/app/intake/_lib/intakeLabels";
import {
  buildIntakePublicUrl,
  copyTextToClipboard,
  formatApplicantIntakeUrlDisplay,
} from "../_lib/personnelApplicantWorkflow";

export type ApplicantIntakeLinkDisplayState =
  | "not_issued"
  | "active"
  | "submitted"
  | "reissue_required"
  | "revoked"
  | "expired";

type Props = {
  applicationId: number;
  displayState?: ApplicantIntakeLinkDisplayState | string | null;
  intakeUrlPath?: string | null;
  intakeLinkStatus?: string | null;
  intakeDraftStatus?: string | null;
};

function displayStateLabel(displayState: string): string {
  switch (displayState) {
    case "reissue_required":
      return "Требует перевыпуска";
    case "revoked":
      return intakeLinkStatusLabel("revoked");
    case "expired":
      return intakeLinkStatusLabel("expired");
    default:
      return "—";
  }
}

function resolveIntakeStatusLabel(
  intakeLinkStatus: string | null | undefined,
  intakeDraftStatus: string | null | undefined,
): string {
  if (String(intakeDraftStatus || "").trim() === "submitted") {
    return intakeDraftStatusLabel(intakeDraftStatus);
  }
  return intakeLinkStatusLabel(intakeLinkStatus);
}

export default function ApplicantIntakeLinkTableCell({
  applicationId,
  displayState,
  intakeUrlPath,
  intakeLinkStatus,
  intakeDraftStatus,
}: Props) {
  const [copyNotice, setCopyNotice] = React.useState(false);
  const state = String(displayState || "not_issued").trim() as ApplicantIntakeLinkDisplayState;
  const path = String(intakeUrlPath || "").trim();
  const url = buildIntakePublicUrl(path || null);
  const canCopyOrOpen =
    Boolean(path && url) && (state === "active" || state === "submitted");
  const statusLabel = resolveIntakeStatusLabel(intakeLinkStatus, intakeDraftStatus);

  React.useEffect(() => {
    if (!copyNotice) return;
    const timer = window.setTimeout(() => setCopyNotice(false), 2000);
    return () => window.clearTimeout(timer);
  }, [copyNotice]);

  async function handleCopy() {
    if (!url) return;
    const copied = await copyTextToClipboard(url);
    setCopyNotice(copied);
  }

  function handleOpen() {
    if (!url) return;
    window.open(url, "_blank", "noopener,noreferrer");
  }

  const statusBadge = (
    <span
      className={`inline-flex max-w-full rounded-full px-2 py-0.5 text-xs font-medium leading-snug ${intakeLinkStatusBadgeClass(intakeLinkStatus)}`}
      data-testid={`applicant-intake-link-status-badge-${applicationId}`}
    >
      {statusLabel}
    </span>
  );

  if (!canCopyOrOpen) {
    if (state === "not_issued") {
      return (
        <div
          className="flex min-w-0 flex-col gap-1.5"
          data-testid={`applicant-intake-link-empty-${applicationId}`}
        >
          {statusBadge}
        </div>
      );
    }

    return (
      <div
        className="flex min-w-0 flex-col gap-1.5"
        data-testid={`applicant-intake-link-status-${applicationId}`}
      >
        {statusBadge}
        <span className="text-xs leading-snug text-zinc-600 dark:text-zinc-300">
          {displayStateLabel(state)}
        </span>
      </div>
    );
  }

  const displayUrl = formatApplicantIntakeUrlDisplay(url!);

  return (
    <div
      className="flex min-w-0 flex-col gap-1.5"
      onClick={(event) => event.stopPropagation()}
      data-testid={`applicant-intake-link-cell-${applicationId}`}
    >
      <code
        className="block min-w-0 overflow-hidden text-xs leading-snug text-zinc-700 line-clamp-2 break-all dark:text-zinc-300"
        title={url!}
        data-testid={`applicant-intake-link-url-${applicationId}`}
      >
        {displayUrl}
      </code>
      {statusBadge}
      <div className="flex flex-wrap gap-1">
        <button
          type="button"
          onClick={() => void handleCopy()}
          className="inline-flex shrink-0 items-center rounded border border-zinc-300 px-2 py-1 text-xs leading-none text-zinc-800 hover:bg-zinc-50 dark:border-zinc-700 dark:text-zinc-200 dark:hover:bg-zinc-900"
          data-testid={`applicant-intake-link-copy-${applicationId}`}
        >
          Копировать
        </button>
        <button
          type="button"
          onClick={handleOpen}
          className="inline-flex shrink-0 items-center rounded border border-zinc-300 px-2 py-1 text-xs leading-none text-zinc-800 hover:bg-zinc-50 dark:border-zinc-700 dark:text-zinc-200 dark:hover:bg-zinc-900"
          data-testid={`applicant-intake-link-open-${applicationId}`}
          aria-label="Открыть личную карточку претендента"
          title="Открыть"
        >
          Открыть
        </button>
      </div>
      {copyNotice ? (
        <span className="text-xs text-emerald-700 dark:text-emerald-300">Скопировано</span>
      ) : null}
    </div>
  );
}
