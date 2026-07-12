"use client";

import Link from "next/link";

import { formatDateTime } from "../_lib/mappers";

type Props = {
  documentId?: number | null;
  promotedAt?: string | null;
  workspaceDriftDetected?: boolean;
  revisionRecommended?: boolean;
};

export default function FrozenWorkspaceBanner({
  documentId,
  promotedAt,
  workspaceDriftDetected,
  revisionRecommended,
}: Props) {
  return (
    <div
      className="rounded-xl border border-purple-200 bg-purple-50 px-4 py-4 dark:border-purple-900 dark:bg-purple-950/30"
      data-testid="workspace-frozen-banner"
    >
      <h3 className="text-sm font-semibold text-purple-950 dark:text-purple-100">Официальный проект создан</h3>
      <p className="mt-1 text-sm text-purple-900 dark:text-purple-200">
        Рабочее пространство заморожено после создания официального документа. Редактирование текста, переводов,
        подтверждений и согласований недоступно.
      </p>
      <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-sm text-purple-900 dark:text-purple-100">
        {documentId ? (
          <span>
            Документ:{" "}
            <Link
              href={`/directory/operational-orders/documents/${documentId}`}
              className="font-medium text-blue-700 underline hover:no-underline dark:text-blue-300"
            >
              #{documentId}
            </Link>
          </span>
        ) : null}
        {promotedAt ? <span>Promotion: {formatDateTime(promotedAt)}</span> : null}
        {workspaceDriftDetected ? <span className="text-amber-800">Обнаружено расхождение workspace</span> : null}
      </div>
      {revisionRecommended ? (
        <p className="mt-3 rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900" data-testid="revision-advisory">
          Содержимое рабочего пространства отличается от официального снимка. Создание новой редакции пока не
          реализовано.
        </p>
      ) : null}
    </div>
  );
}
