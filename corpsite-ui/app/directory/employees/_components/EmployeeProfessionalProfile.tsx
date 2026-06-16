// FILE: corpsite-ui/app/directory/employees/_components/EmployeeProfessionalProfile.tsx
"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import {
  listEmployeeDocuments,
  mapDocumentsApiError,
  type EmployeeDocumentRow,
} from "../../personnel/_lib/documentsApi.client";
import {
  buildProfessionalProfileSummary,
  documentExpiryStatus,
  expiryStatusMeta,
  fmtProfileDate,
  RISK_META,
} from "../_lib/professionalProfile";

type Props = {
  employeeId: string;
};

export default function EmployeeProfessionalProfile({ employeeId }: Props) {
  const [loading, setLoading] = useState(true);
  const [available, setAvailable] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [documents, setDocuments] = useState<EmployeeDocumentRow[]>([]);

  useEffect(() => {
    let cancelled = false;
    const numericId = Number(employeeId);

    if (!Number.isFinite(numericId) || numericId <= 0) {
      setDocuments([]);
      setAvailable(false);
      setLoading(false);
      return;
    }

    (async () => {
      setLoading(true);
      setError(null);
      try {
        const body = await listEmployeeDocuments({
          employee_id: numericId,
          lifecycle_status: "ACTIVE",
          limit: 100,
        });
        if (cancelled) return;
        setDocuments(Array.isArray(body.items) ? body.items : []);
        setAvailable(true);
      } catch (e) {
        if (cancelled) return;
        setDocuments([]);
        setAvailable(false);
        setError(mapDocumentsApiError(e, "Не удалось загрузить документы сотрудника."));
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
