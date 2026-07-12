"use client";

import { workspaceStageBadgeClass, workspaceStageLabel } from "../_lib/status";

type Props = { stage: string };

export default function WorkspaceStageBadge({ stage }: Props) {
  return (
    <span
      className={`inline-flex rounded-md border px-2 py-0.5 text-xs font-medium ${workspaceStageBadgeClass(stage)}`}
      data-testid={`workspace-stage-badge-${stage}`}
    >
      {workspaceStageLabel(stage)}
    </span>
  );
}
