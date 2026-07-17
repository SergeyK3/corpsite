"use client";

import * as React from "react";

import {
  buildIntakePublicUrl,
  copyTextToClipboard,
} from "../_lib/personnelApplicantWorkflow";

type Props = {
  intakeUrlPath: string | null | undefined;
  showOpenFormButton?: boolean;
  copyButtonTestId?: string;
  openFormButtonTestId?: string;
  copyNoticeTestId?: string;
  actionsDisabled?: boolean;
};

export default function PersonnelApplicationIntakeLinkPanel({
  intakeUrlPath,
  showOpenFormButton = false,
  copyButtonTestId = "intake-copy-link-button",
  openFormButtonTestId = "intake-open-form-button",
  copyNoticeTestId = "intake-copy-notice",
  actionsDisabled = false,
}: Props) {
  const [copyNotice, setCopyNotice] = React.useState<string | null>(null);
  const path = String(intakeUrlPath || "").trim();
  const activeLinkUrl = buildIntakePublicUrl(path || null);

  React.useEffect(() => {
    if (!copyNotice) return;
    const timer = window.setTimeout(() => setCopyNotice(null), 2500);
    return () => window.clearTimeout(timer);
  }, [copyNotice]);

  if (!path) return null;

  async function handleCopyLink() {
    if (!activeLinkUrl) return;
    const copied = await copyTextToClipboard(activeLinkUrl);
    setCopyNotice(copied ? "Ссылка скопирована" : "Не удалось скопировать ссылку");
  }

  function handleOpenForm() {
    if (!activeLinkUrl) return;
    window.open(activeLinkUrl, "_blank", "noopener,noreferrer");
  }

  return (
    <div className="space-y-2" data-testid="personnel-application-intake-link-panel">
      <div className="rounded-lg border border-sky-200 bg-sky-50 px-3 py-2 text-sm dark:border-sky-900 dark:bg-sky-950/30">
        <p className="font-medium text-sky-900 dark:text-sky-200">Ссылка для претендента</p>
        <code className="mt-1 block break-all text-xs text-sky-800 dark:text-sky-300">
          {activeLinkUrl || path}
        </code>
        {copyNotice ? (
          <p className="mt-1 text-xs text-emerald-700 dark:text-emerald-300" data-testid={copyNoticeTestId}>
            {copyNotice}
          </p>
        ) : null}
      </div>

      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          disabled={actionsDisabled}
          onClick={() => void handleCopyLink()}
          className="rounded-lg border border-sky-300 px-3 py-1.5 text-sm text-sky-900 hover:bg-sky-50 disabled:opacity-50 dark:border-sky-900 dark:text-sky-200 dark:hover:bg-sky-950/40"
          data-testid={copyButtonTestId}
        >
          Скопировать ссылку
        </button>
        {showOpenFormButton ? (
          <button
            type="button"
            disabled={actionsDisabled}
            onClick={handleOpenForm}
            className="rounded-lg border border-zinc-300 px-3 py-1.5 text-sm hover:bg-zinc-50 disabled:opacity-50 dark:border-zinc-700 dark:hover:bg-zinc-900"
            data-testid={openFormButtonTestId}
          >
            Открыть форму
          </button>
        ) : null}
      </div>
    </div>
  );
}
