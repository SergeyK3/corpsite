"use client";

import {
  applicantWorkflowStatusBadgeClass,
  resolveApplicantWorkflowStatus,
  type ApplicantWorkflowStatusInput,
} from "../_lib/personnelApplicantWorkflow";

type Props = ApplicantWorkflowStatusInput & {
  className?: string;
};

export default function ApplicantWorkflowStatusBadge({
  status,
  intake_link_status,
  intake_draft_status,
  className = "",
}: Props) {
  const workflow = resolveApplicantWorkflowStatus({
    status,
    intake_link_status,
    intake_draft_status,
  });

  return (
    <span
      className={[
        "inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium",
        applicantWorkflowStatusBadgeClass({
          status,
          intake_link_status,
          intake_draft_status,
        }),
        className,
      ].join(" ")}
      data-testid={`applicant-workflow-status-${workflow.key}`}
    >
      {workflow.label}
    </span>
  );
}
