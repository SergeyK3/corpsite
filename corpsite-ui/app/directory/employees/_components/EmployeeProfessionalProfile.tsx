// FILE: corpsite-ui/app/directory/employees/_components/EmployeeProfessionalProfile.tsx
"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import {
  listEmployeeDocuments,
  getEmployeeTrainingHoursSummary,
  mapDocumentsApiError,
  type EmployeeDocumentRow,
  type TrainingHoursSummary,
} from "../../personnel/_lib/documentsApi.client";
import {
  buildProfessionalProfileSummary,
  documentExpiryStatus,
  expiryStatusMeta,
  fmtProfileDate,
  RISK_META,
  trainingHoursStatusMeta,
} from "../_lib/professionalProfile";

type Props = {
  employeeId: string;
};

export default function EmployeeProfessionalProfile({ employeeId }: Props) {
  const [loading, setLoading] = useState(true);
  const [available, setAvailable] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [documents, setDocuments] = useState<EmployeeDocumentRow[]>([]);
  const [trainingSummary, setTrainingSummary] = useState<TrainingHoursSummary | null>(null);
  const [trainingError, setTrainingError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const numericId = Number(employeeId);

    if (!Number.isFinite(numericId) || numericId <= 0) {
      setDocuments([]);
      setTrainingSummary(null);
      setAvailable(false);
      setLoading(false);
      return;
    }

    (async () => {
      setLoading(true);
      setError(null);
      setTrainingError(null);
      try {
        const docsBody = await listEmployeeDocuments({
          employee_id: numericId,
          lifecycle_status: "ACTIVE",
          limit: 100,
        });
        if (cancelled) return;
        setDocuments(Array.isArray(docsBody.items) ? docsBody.items : []);
        setAvailable(true);
      } catch (e) {
        if (cancelled) return;
        setDocuments([]);
        setTrainingSummary(null);
        setAvailable(false);
        setError(mapDocumentsApiError(e, "Не удалось загрузить документы сотрудника."));
      }

      try {
        const summary = await getEmployeeTrainingHoursSummary({ employee_id: numericId });
        if (cancelled) return;
        setTrainingSummary(summary);
      } catch (e) {
        if (cancelled) return;
        setTrainingSummary(null);
        setTrainingError(
          mapDocumentsApiError(e, "Не удалось загрузить сводку по часам обучения.")
        );
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [employeeId]);

  const profile = useMemo(() => {
    const numericId = Number(employeeId);
    if (!Number.isFinite(numericId) || numericId <= 0) {
      return buildProfessionalProfileSummary({
        employeeId: 0,
        documents: [],
        available: false,
      });
    }

    return buildProfessionalProfileSummary({
      employeeId: numericId,
      documents,
      available,
    });
  }, [available, documents, employeeId]);

  if (!loading && !available && !error) {
    return null;
  }

  const riskMeta = RISK_META[profile.riskLevel];
  const trainingMeta = trainingSummary
    ? trainingHoursStatusMeta(trainingSummary.training_hours_status)
    : null;
  const trainingProgressPct = trainingSummary
    ? Math.min(
        100,
        Math.round(
          (trainingSummary.training_hours_last_5y / trainingSummary.training_hours_required) * 100
        )
      )
    : 0;

  return (
    <section>
      <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
        <div>
          <h3 className="text-sm font-medium text-zinc-900 dark:text-zinc-50">
            Профессиональный профиль
          </h3>
          <p className="mt-0.5 text-xs text-zinc-500 dark:text-zinc-400">
            Сводка на основе зарегистрированных документов
          </p>
        </div>
        <Link
          href="/directory/personnel/documents"
          className="text-xs font-medium text-blue-600 transition hover:text-blue-500 dark:text-blue-400 dark:hover:text-blue-300"
        >
          Реестр документов →
        </Link>
      </div>

      {loading ? (
        <div className="rounded-xl border border-zinc-200 bg-zinc-50 px-4 py-3 text-sm text-zinc-600 dark:border-zinc-800 dark:bg-zinc-900/40 dark:text-zinc-400">
          Загрузка профиля…
        </div>
      ) : error ? (
        <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900 dark:border-amber-900/55 dark:bg-amber-950/35 dark:text-amber-200">
          {error}
        </div>
      ) : (
        <div className="space-y-4">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <div className="rounded-xl border border-zinc-200 bg-zinc-50 p-4 dark:border-zinc-800 dark:bg-zinc-950">
              <div className="text-xs text-zinc-600 dark:text-zinc-400">Основная специальность</div>
              <div className="mt-1 text-sm font-medium text-zinc-900 dark:text-zinc-50">
                {profile.mainSpecialty}
              </div>
            </div>

            <div className="rounded-xl border border-zinc-200 bg-zinc-50 p-4 dark:border-zinc-800 dark:bg-zinc-950">
              <div className="text-xs text-zinc-600 dark:text-zinc-400">Квалификационная категория</div>
              <div className="mt-1 text-sm font-medium text-zinc-900 dark:text-zinc-50">
                {profile.category}
              </div>
            </div>

            <div className="rounded-xl border border-zinc-200 bg-zinc-50 p-4 dark:border-zinc-800 dark:bg-zinc-950">
              <div className="text-xs text-zinc-600 dark:text-zinc-400">Контроль документов</div>
              <div className="mt-1">
                <span
                  className={`inline-flex rounded-md px-2 py-0.5 text-xs font-semibold ${riskMeta.className}`}
                >
                  {riskMeta.label}
                </span>
              </div>
            </div>

            <div className="rounded-xl border border-zinc-200 bg-zinc-50 p-4 dark:border-zinc-800 dark:bg-zinc-950">
              <div className="text-xs text-zinc-600 dark:text-zinc-400">Ближайший срок</div>
              <div className="mt-1 text-sm font-medium text-zinc-900 dark:text-zinc-50">
                {fmtProfileDate(profile.nearestExpiration)}
              </div>
            </div>
          </div>

          {trainingError ? (
            <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900 dark:border-amber-900/55 dark:bg-amber-950/35 dark:text-amber-200">
              {trainingError}
            </div>
          ) : trainingSummary ? (
            <div className="rounded-xl border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
              <div className="mb-3 flex flex-wrap items-start justify-between gap-2">
                <div>
                  <h4 className="text-sm font-medium text-zinc-900 dark:text-zinc-50">
                    Норма часов обучения (5 лет)
                  </h4>
                  <p className="mt-0.5 text-xs text-zinc-500 dark:text-zinc-400">
                    Окно: {fmtProfileDate(trainingSummary.window_start)} —{" "}
                    {fmtProfileDate(trainingSummary.as_of)}
                  </p>
                </div>
                {trainingMeta ? (
                  <span
                    className={`inline-flex rounded-md px-2 py-0.5 text-xs font-semibold ${trainingMeta.className}`}
                  >
                    {trainingMeta.label}
                  </span>
                ) : null}
              </div>

              <div className="mb-2 flex flex-wrap items-baseline gap-x-4 gap-y-1 text-sm">
                <span className="font-semibold text-zinc-900 dark:text-zinc-50">
                  {trainingSummary.training_hours_last_5y} / {trainingSummary.training_hours_required}{" "}
                  ч
                </span>
                {trainingSummary.training_hours_remaining > 0 ? (
                  <span className="text-zinc-600 dark:text-zinc-400">
                    Осталось: {trainingSummary.training_hours_remaining} ч
                  </span>
                ) : null}
                {trainingSummary.incomplete_documents_count > 0 ? (
                  <span className="text-amber-700 dark:text-amber-300">
                    Неполных документов: {trainingSummary.incomplete_documents_count}
                  </span>
                ) : null}
              </div>

              <div className="h-2 overflow-hidden rounded-full bg-zinc-200 dark:bg-zinc-800">
                <div
                  className={[
                    "h-full rounded-full transition-all",
                    trainingSummary.training_hours_status === "MET"
                      ? "bg-emerald-500"
                      : trainingSummary.training_hours_status === "INCOMPLETE"
                        ? "bg-amber-500"
                        : "bg-orange-500",
                  ].join(" ")}
                  style={{ width: `${trainingProgressPct}%` }}
                />
              </div>
            </div>
          ) : null}

          <div className="overflow-hidden rounded-xl border border-zinc-200 dark:border-zinc-800">
            <div className="border-b border-zinc-200 bg-zinc-100 px-3 py-2 text-xs font-medium uppercase tracking-wide text-zinc-600 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-400">
              Подтверждающие документы
            </div>
            <div className="overflow-x-auto">
              <table className="min-w-full border-collapse text-sm">
                <thead>
                  <tr className="border-b border-zinc-200 text-left dark:border-zinc-800">
                    <th className="px-3 py-2 text-[11px] font-medium uppercase tracking-wide text-zinc-600 dark:text-zinc-400">
                      Тип документа
                    </th>
                    <th className="px-3 py-2 text-[11px] font-medium uppercase tracking-wide text-zinc-600 dark:text-zinc-400">
                      Действует до
                    </th>
                    <th className="px-3 py-2 text-[11px] font-medium uppercase tracking-wide text-zinc-600 dark:text-zinc-400">
                      Статус
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {profile.documents.length === 0 ? (
                    <tr>
                      <td colSpan={3} className="px-3 py-6 text-center text-zinc-500">
                        Подтверждающие документы не зарегистрированы
                      </td>
                    </tr>
                  ) : (
                    profile.documents.map((row) => {
                      const statusKey = documentExpiryStatus(row);
                      const statusMeta = expiryStatusMeta(statusKey);
                      return (
                        <tr
                          key={row.document_id}
                          className="border-t border-zinc-200 dark:border-zinc-800"
                        >
                          <td className="px-3 py-2 text-zinc-900 dark:text-zinc-50">
                            {row.document_type_name}
                          </td>
                          <td className="px-3 py-2 text-zinc-700 dark:text-zinc-300">
                            {fmtProfileDate(row.valid_until)}
                          </td>
                          <td className="px-3 py-2">
                            <span
                              className={`inline-flex rounded-md px-2 py-0.5 text-xs font-medium ${statusMeta.className}`}
                            >
                              {statusMeta.label}
                            </span>
                          </td>
                        </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
