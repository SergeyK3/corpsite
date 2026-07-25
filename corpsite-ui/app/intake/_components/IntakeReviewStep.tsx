"use client";

import * as React from "react";

import type { IntakeDraftPayload } from "../_lib/intakeApi.client";
import { INTAKE_STEPS } from "../_lib/intakeApi.client";
import type { IntakeDateValidationIssue } from "../_lib/intakeDateValidation";
import {
  buildIntakeReviewSections,
  type IntakeReviewField,
  type IntakeReviewRecordCard,
  type IntakeReviewSectionContent,
} from "../_lib/intakeReviewContent";
import { shouldShowIntakePersonnelNumberField } from "../_lib/intakePersonalFields";

type Props = {
  payload: IntakeDraftPayload;
  mode: "public" | "hr-on-behalf";
  reviewNotice?: string | null;
  dateValidationIssues: IntakeDateValidationIssue[];
  onNavigateToStep: (stepIndex: number) => void;
  onNavigateToDateIssue: (issue: IntakeDateValidationIssue) => void;
};

function ReviewFieldList({ fields }: { fields: IntakeReviewField[] }) {
  if (fields.length === 0) return null;
  return (
    <dl className="grid gap-2 sm:grid-cols-2">
      {fields.map((field) => (
        <div key={`${field.label}:${field.value}`}>
          <dt className="text-xs font-medium uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
            {field.label}
          </dt>
          <dd className="mt-0.5 text-sm text-zinc-900 dark:text-zinc-100">{field.value}</dd>
        </div>
      ))}
    </dl>
  );
}

function ReviewRecordCardView({
  card,
  testId,
}: {
  card: IntakeReviewRecordCard;
  testId: string;
}) {
  if (card.lines.length === 0) return null;
  return (
    <article
      className="rounded-lg border border-zinc-200 bg-zinc-50 p-3 dark:border-zinc-700 dark:bg-zinc-900/40"
      data-testid={testId}
    >
      <h4 className="text-sm font-medium text-zinc-900 dark:text-zinc-50">{card.title}</h4>
      <ReviewFieldList fields={card.lines} />
    </article>
  );
}

function ReviewSectionBlock({
  section,
  onEdit,
}: {
  section: IntakeReviewSectionContent;
  onEdit: () => void;
}) {
  const hasSubsections = section.subsections.length > 0;
  const hasRecords = section.records.some((record) => record.lines.length > 0);
  const hasFields = section.fields.length > 0;
  const isEmpty = !hasFields && !hasRecords && section.subsections.every((part) => part.empty);

  return (
    <section
      className="rounded-xl border border-zinc-200 p-4 dark:border-zinc-700"
      data-testid={section.testId}
    >
      <div className="mb-3 flex flex-wrap items-start justify-between gap-2">
        <h3 className="text-base font-semibold text-zinc-900 dark:text-zinc-50">{section.title}</h3>
        <button
          type="button"
          className="rounded-lg border border-zinc-300 px-2.5 py-1 text-xs font-medium text-zinc-700 hover:bg-zinc-50 dark:border-zinc-600 dark:text-zinc-200 dark:hover:bg-zinc-800"
          data-testid={section.editTestId}
          onClick={onEdit}
        >
          Изменить
        </button>
      </div>

      {isEmpty ? (
        <p className="text-sm text-zinc-500 dark:text-zinc-400">Нет сведений</p>
      ) : (
        <div className="space-y-3">
          <ReviewFieldList fields={section.fields} />
          {section.records.map((record, index) => (
            <ReviewRecordCardView
              key={`${section.stepId}-record-${index}`}
              card={record}
              testId={`intake-review-${section.stepId}-item-${index}`}
            />
          ))}
          {hasSubsections
            ? section.subsections.map((subsection) => (
                <div key={subsection.testId} className="space-y-2" data-testid={subsection.testId}>
                  <h4 className="text-sm font-medium text-zinc-800 dark:text-zinc-200">{subsection.title}</h4>
                  {subsection.empty ? (
                    <p className="text-sm text-zinc-500 dark:text-zinc-400">Нет сведений</p>
                  ) : (
                    <div className="space-y-2">
                      {subsection.records.map((record, index) => (
                        <ReviewRecordCardView
                          key={`${subsection.testId}-${index}`}
                          card={record}
                          testId={`${subsection.testId}-item-${index}`}
                        />
                      ))}
                    </div>
                  )}
                </div>
              ))
            : null}
        </div>
      )}
    </section>
  );
}

export default function IntakeReviewStep({
  payload,
  mode,
  reviewNotice,
  dateValidationIssues,
  onNavigateToStep,
  onNavigateToDateIssue,
}: Props) {
  const sections = React.useMemo(
    () =>
      buildIntakeReviewSections(
        payload,
        shouldShowIntakePersonnelNumberField(mode, payload.personal.personnel_number),
      ),
    [mode, payload],
  );

  function navigateToSection(stepId: string) {
    const stepIndex = INTAKE_STEPS.findIndex((step) => step.id === stepId);
    if (stepIndex >= 0) onNavigateToStep(stepIndex);
  }

  return (
    <div className="space-y-4 text-sm text-zinc-700 dark:text-zinc-300" data-testid="intake-review-summary">
      <p>
        {mode === "hr-on-behalf"
          ? "Проверьте сведения перед сохранением от имени претендента."
          : "Проверьте введённые сведения перед отправкой в отдел кадров."}
      </p>
      {mode === "hr-on-behalf" && reviewNotice ? (
        <p className="text-amber-700 dark:text-amber-300" data-testid="intake-on-behalf-review-notice">
          {reviewNotice}
        </p>
      ) : null}

      <div className="space-y-4">
        {sections.map((section) => (
          <ReviewSectionBlock
            key={section.stepId}
            section={section}
            onEdit={() => navigateToSection(section.stepId)}
          />
        ))}
      </div>

      {dateValidationIssues.length > 0 ? (
        <div
          className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-amber-900 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-200"
          data-testid="intake-review-date-issues"
        >
          <p className="font-medium">Исправьте ошибки перед отправкой:</p>
          <ul className="mt-1 list-disc pl-5">
            {dateValidationIssues.map((issue) => (
              <li key={issue.field}>
                <button
                  type="button"
                  className="text-left underline decoration-amber-700/60 underline-offset-2 hover:decoration-amber-900 dark:decoration-amber-300/60 dark:hover:decoration-amber-100"
                  data-testid={`intake-review-date-issue-${issue.field}`}
                  onClick={() => onNavigateToDateIssue(issue)}
                >
                  {issue.message}
                </button>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}
