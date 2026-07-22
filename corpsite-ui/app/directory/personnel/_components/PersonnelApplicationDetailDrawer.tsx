"use client";

import * as React from "react";
import Link from "next/link";

import { buildPersonalCardHref } from "@/lib/employeeCardNav";
import {
  canOpenApplicantIntakeReview,
  canOpenApplicantPersonalCard,
} from "../_lib/personnelApplicantWorkflow";
import ApplicantWorkflowStatusBadge from "./ApplicantWorkflowStatusBadge";
import {
  formatPersonnelApplicationDate,
  formatPersonnelApplicationDateTime,
  personnelApplicationStatusLabel,
} from "../_lib/personnelApplicationLabels";
import PersonnelApplicationIntakeSection from "./PersonnelApplicationIntakeSection";
import PersonnelApplicationIntakeReviewDrawer from "./PersonnelApplicationIntakeReviewDrawer";
import PersonnelApplicationResolutionSection from "./PersonnelApplicationResolutionSection";
import PersonnelApplicationEmploymentSection from "./PersonnelApplicationEmploymentSection";
import PersonnelApplicationTimelineSection from "./PersonnelApplicationTimelineSection";
import PersonnelApplicationLifecycleAuditSection from "./PersonnelApplicationLifecycleAuditSection";
import PersonnelApplicationCancelSection from "./PersonnelApplicationCancelSection";
import {
  getPersonnelApplication,
  mapPersonnelApplicationsApiError,
  type PersonnelApplicationDetail,
} from "../_lib/personnelApplicationsApi.client";

type Props = {
  applicationId: number | null;
  open: boolean;
  journalReturnHref: string;
  onClose: () => void;
};

function Field({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div>
      <div className="text-xs font-medium uppercase tracking-wide text-zinc-500">{label}</div>
      <div className="mt-0.5 text-sm text-zinc-800 dark:text-zinc-200">{value}</div>
    </div>
  );
}

export default function PersonnelApplicationDetailDrawer({
  applicationId,
  open,
  journalReturnHref,
  onClose,
}: Props) {
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [detail, setDetail] = React.useState<PersonnelApplicationDetail | null>(null);
  const [reviewOpen, setReviewOpen] = React.useState(false);

  const reloadDetail = React.useCallback(() => {
    if (applicationId == null) return;
    void getPersonnelApplication(applicationId)
      .then(setDetail)
      .catch((e) => setError(mapPersonnelApplicationsApiError(e, "Не удалось загрузить обращение")));
  }, [applicationId]);

  React.useEffect(() => {
    if (!open) return;
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, onClose]);

  React.useEffect(() => {
    if (!open || applicationId == null) {
      setDetail(null);
      setError(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    void getPersonnelApplication(applicationId)
      .then((data) => {
        if (!cancelled) setDetail(data);
      })
      .catch((e) => {
        if (!cancelled) {
          setDetail(null);
          setError(mapPersonnelApplicationsApiError(e, "Не удалось загрузить обращение"));
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [applicationId, open]);

  if (!open) return null;

  return (
    <>
      <PersonnelApplicationIntakeReviewDrawer
        applicationId={applicationId}
        open={reviewOpen}
        onClose={() => setReviewOpen(false)}
        onTransferred={reloadDetail}
      />
      <div className="fixed inset-0 z-50 flex justify-end" data-testid="personnel-application-detail-drawer">
      <button type="button" aria-label="Закрыть" className="absolute inset-0 bg-black/30" onClick={onClose} />
      <aside className="relative flex h-full w-full max-w-3xl flex-col border-l border-zinc-200 bg-white shadow-xl dark:border-zinc-800 dark:bg-zinc-950">
        <div className="flex items-start justify-between gap-3 border-b border-zinc-200 px-4 py-4 dark:border-zinc-800">
          <div>
            <h2 className="text-lg font-semibold text-zinc-900 dark:text-zinc-50">
              Кадровое обращение #{applicationId ?? "—"}
            </h2>
            {detail ? (
              <p className="mt-1 text-sm text-zinc-500">
                {detail.full_name || "—"} · person #{detail.person_id}
              </p>
            ) : null}
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-700"
          >
            Закрыть
          </button>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4">
          {loading ? (
            <div className="space-y-3" data-testid="personnel-application-detail-loading">
              {Array.from({ length: 6 }).map((_, i) => (
                <div key={i} className="h-10 animate-pulse rounded-lg bg-zinc-100 dark:bg-zinc-900" />
              ))}
            </div>
          ) : null}
          {error ? (
            <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800 dark:border-red-900 dark:bg-red-950/40 dark:text-red-200">
              {error}
            </div>
          ) : null}
          {detail ? (
            <div className="space-y-6">
              <section className="space-y-3">
                <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">Регистрация</h3>
                <div className="grid gap-3 sm:grid-cols-2">
                  <Field label="ФИО" value={detail.full_name || "—"} />
                  <Field label="ИИН" value={<span className="font-mono">{detail.iin || "—"}</span>} />
                  <Field
                    label="Статус"
                    value={
                      <ApplicantWorkflowStatusBadge
                        status={detail.status}
                        intake_link_status={detail.intake_link_status}
                        intake_draft_status={detail.intake_draft_status}
                      />
                    }
                  />
                  <Field
                    label="Дата поступления заявления"
                    value={formatPersonnelApplicationDate(detail.application_received_at)}
                  />
                  <Field label="Источник" value={detail.application_source} />
                  <Field label="Проверка вакансии" value={detail.vacancy_check_status} />
                </div>
              </section>

              <section className="space-y-3">
                <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">Предполагаемое трудоустройство</h3>
                <div className="grid gap-3 sm:grid-cols-2">
                  <Field label="Подразделение" value={detail.intended_org_unit_name || "—"} />
                  <Field label="Группа" value={detail.intended_org_group_name || "—"} />
                  <Field label="Должность" value={detail.intended_position_name || "—"} />
                  <Field label="Ставка" value={detail.intended_employment_rate ?? "—"} />
                  <Field label="Текст вакансии" value={detail.intended_vacancy_text || "—"} />
                </div>
              </section>

              <section className="space-y-3">
                <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">Контакты эпизода</h3>
                <div className="grid gap-3 sm:grid-cols-2">
                  <Field label="Мобильный телефон" value={detail.contact_mobile_phone || "—"} />
                  <Field label="Email" value={detail.contact_email || "—"} />
                </div>
              </section>

              {detail ? (
                <PersonnelApplicationIntakeSection
                  detail={detail}
                  onRefresh={reloadDetail}
                  onOpenReview={() => setReviewOpen(true)}
                  readOnly={Boolean(detail.is_read_only)}
                />
              ) : null}

              <PersonnelApplicationResolutionSection detail={detail} onRefresh={reloadDetail} />

              <PersonnelApplicationEmploymentSection detail={detail} journalReturnHref={journalReturnHref} />

              {detail.is_read_only ? (
                <section className="space-y-3" data-testid="personnel-application-archive-summary">
                  <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">Архив</h3>
                  <div className="grid gap-3 sm:grid-cols-2">
                    <Field
                      label="Дата завершения"
                      value={formatPersonnelApplicationDateTime(detail.completed_at)}
                    />
                    <Field
                      label="Дата закрытия"
                      value={formatPersonnelApplicationDateTime(detail.closed_at)}
                    />
                    {detail.cancel_reason ? (
                      <Field label="Причина отмены" value={detail.cancel_reason} />
                    ) : null}
                  </div>
                </section>
              ) : null}

              <PersonnelApplicationCancelSection detail={detail} onCancelled={reloadDetail} />

              <PersonnelApplicationTimelineSection applicationId={detail.application_id} />

              <PersonnelApplicationLifecycleAuditSection applicationId={detail.application_id} />

              <section className="space-y-3">
                <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">Audit</h3>
                <div className="grid gap-3 sm:grid-cols-2">
                  <Field
                    label="Зарегистрировал"
                    value={detail.registered_by_name || `#${detail.registered_by_user_id}`}
                  />
                  <Field label="Дата регистрации" value={formatPersonnelApplicationDateTime(detail.registered_at)} />
                  <Field label="Примечание HR" value={detail.hr_note || "—"} />
                  <Field label="Статус (raw)" value={personnelApplicationStatusLabel(detail.status)} />
                </div>
              </section>

              {canOpenApplicantIntakeReview(detail) ? (
                <button
                  type="button"
                  onClick={() => setReviewOpen(true)}
                  className="inline-flex rounded-lg border border-emerald-300 px-3 py-1.5 text-sm text-emerald-800 hover:bg-emerald-50 dark:border-emerald-900 dark:text-emerald-300 dark:hover:bg-emerald-950/30"
                  data-testid="personnel-application-open-intake-review"
                >
                  Открыть анкету для проверки
                </button>
              ) : null}

              {canOpenApplicantPersonalCard(detail.status) ? (
                <Link
                  href={buildPersonalCardHref(
                    { personId: detail.person_id },
                    { returnTo: journalReturnHref },
                  )}
                  className="inline-flex text-sm text-blue-700 underline-offset-2 hover:underline dark:text-blue-300"
                  data-testid="personnel-application-open-person-card"
                >
                  Открыть личную карточку
                </Link>
              ) : canOpenApplicantIntakeReview(detail) ? null : (
                <p
                  className="text-sm text-zinc-500 dark:text-zinc-400"
                  data-testid="personnel-application-person-card-locked"
                >
                  Личная карточка станет доступна после проверки анкеты и переноса в PPR.
                </p>
              )}
            </div>
          ) : null}
        </div>
      </aside>
    </div>
    </>
  );
}
