"use client";

import * as React from "react";

import { intakeLinkStatusLabel } from "@/app/intake/_lib/intakeLabels";
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

export default function ApplicantIntakeLinkTableCell({
  applicationId,
  displayState,
  intakeUrlPath,
}: Props) {
  const [copyNotice, setCopyNotice] = React.useState(false);
  const state = String(displayState || "not_issued").trim() as ApplicantIntakeLinkDisplayState;
  const path = String(intakeUrlPath || "").trim();
  const url = buildIntakePublicUrl(path || null);
  const canCopyOrOpen =
    Boolean(path && url) && (state === "active" || state === "submitted");

  React.useEffect(() => {
    if (!copyNotice) return;
    const timer = window.setTimeout(() => setCopyNotice(false), 2000);
    return () => window.clearTimeout(timer);
  }, [copyNotice]);

  if (!canCopyOrOpen) {
    if (state === "not_issued") {
      return (
        <span className="text-zinc-400" data-testid={`applicant-intake-link-empty-${applicationId}`}>
          —
        </span>
      );
    }
    return (
      <span
        className="text-sm text-zinc-600 dark:text-zinc-300"
        data-testid={`applicant-intake-link-status-${applicationId}`}
      >
        {displayStateLabel(state)}
      </span>
    );
  }

  const displayUrl = formatApplicantIntakeUrlDisplay(url!);

  async function handleCopy() {
    const copied = await copyTextToClipboard(url!);
    setCopyNotice(copied);
  }

  function handleOpen() {
    window.open(url!, "_blank", "noopener,noreferrer");
  }

  return (
    <div
      className="flex min-w-[11rem] flex-col gap-1"
      onClick={(event) => event.stopPropagation()}
      data-testid={`applicant-intake-link-cell-${applicationId}`}
    >
      <code
        className="block max-w-xs truncate text-xs text-zinc-700 dark:text-zinc-300"
        title={url!}
        data-testid={`applicant-intake-link-url-${applicationId}`}
      >
        {displayUrl}
      </code>
      <div className="flex flex-wrap items-center gap-1">
        <button
          type="button"
          onClick={() => void handleCopy()}
          className="rounded border border-zinc-300 px-2 py-0.5 text-xs text-zinc-800 hover:bg-zinc-50 dark:border-zinc-700 dark:text-zinc-200 dark:hover:bg-zinc-900"
          data-testid={`applicant-intake-link-copy-${applicationId}`}
        >
          Копировать
        </button>
        <button
          type="button"
          onClick={handleOpen}
          className="rounded border border-zinc-300 px-2 py-0.5 text-xs text-zinc-800 hover:bg-zinc-50 dark:border-zinc-700 dark:text-zinc-200 dark:hover:bg-zinc-900"
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
