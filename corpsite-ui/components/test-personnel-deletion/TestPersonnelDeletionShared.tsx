import {
  REASON_OPTIONS,
  type TestPersonnelRequest,
  type TestPersonnelTarget,
} from "@/lib/testPersonnelDeletion";

const STATUS_LABELS: Record<string, string> = {
  DRAFT: "Черновик",
  PENDING_HR_APPROVAL: "Ожидает согласования руководителя отдела кадров",
  APPROVED: "Одобрено",
  REJECTED: "Отклонено",
  CANCELLED: "Отменено",
  EXPIRED: "Срок действия истёк",
  REAPPROVAL_REQUIRED: "Требуется повторное согласование",
};

const CATEGORY_LABELS: Record<string, string> = {
  BLOCK: "Блокирующая связь",
  TOMBSTONE_REQUIRED: "Требуется обезличивание технического следа",
  HR_ATTESTATION_REQUIRED: "Требуется подтверждение HR",
  INFORMATIONAL: "Информационная связь",
};

export function statusLabel(status: string): string {
  return STATUS_LABELS[status] ?? status;
}

export function categoryLabel(category: string): string {
  return CATEGORY_LABELS[category] ?? category;
}

export function reasonLabel(reasonCode: TestPersonnelRequest["reason_code"]): string {
  return REASON_OPTIONS.find((option) => option.value === reasonCode)?.label ?? reasonCode;
}

export function shortHash(value: string | null | undefined): string {
  const hash = String(value ?? "");
  return hash.length > 12 ? `${hash.slice(0, 12)}…` : hash || "—";
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return "—";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString("ru-RU");
}

export function targetIsBlocked(target: TestPersonnelTarget): boolean {
  return target.eligibility_status === "BLOCKED" ||
    target.stage_admissibility?.create === false ||
    target.blocking_codes.length > 0;
}

function Codes({ title, codes }: { title: string; codes: string[] }) {
  if (!codes.length) return null;
  return (
    <div className="mt-1">
      <span className="font-medium">{title}:</span> {codes.join(", ")}
    </div>
  );
}

export function TargetManifest({
  targets,
  selectable = false,
  selected = new Set<string>(),
  onToggle,
}: {
  targets: TestPersonnelTarget[];
  selectable?: boolean;
  selected?: Set<string>;
  onToggle?: (target: TestPersonnelTarget) => void;
}) {
  if (!targets.length) {
    return <p className="rounded-lg border border-dashed p-4 text-sm text-zinc-600">Записи отсутствуют.</p>;
  }
  return (
    <div className="overflow-x-auto rounded-xl border border-zinc-200 dark:border-zinc-800">
      <table className="min-w-full divide-y divide-zinc-200 text-left text-sm dark:divide-zinc-800">
        <thead className="bg-zinc-50 dark:bg-zinc-900">
          <tr>
            {selectable ? <th className="px-3 py-2">Выбор</th> : null}
            <th className="px-3 py-2">Запись</th>
            <th className="px-3 py-2">ИИН</th>
            <th className="px-3 py-2">Статус и связи</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-zinc-200 dark:divide-zinc-800">
          {targets.map((target) => {
            const key = `${target.person_id}:${target.application_id}`;
            const blocked = targetIsBlocked(target);
            return (
              <tr key={key} data-testid={`target-${key}`}>
                {selectable ? (
                  <td className="px-3 py-3 align-top">
                    <input
                      type="checkbox"
                      aria-label={`Выбрать ${target.subject}`}
                      checked={selected.has(key)}
                      disabled={blocked}
                      onChange={() => onToggle?.(target)}
                    />
                  </td>
                ) : null}
                <td className="px-3 py-3 align-top">
                  <div className="font-medium">{target.subject}</div>
                  <div className="text-xs text-zinc-500">Person #{target.person_id}, Application #{target.application_id}</div>
                </td>
                <td className="px-3 py-3 align-top font-mono">{target.masked_iin ?? "не указан"}</td>
                <td className="px-3 py-3 align-top">
                  <div className="font-medium">{blocked ? "BLOCK — выбор запрещён" : "Разрешено для запроса"}</div>
                  <Codes title={categoryLabel("BLOCK")} codes={target.blocking_codes} />
                  <Codes title={categoryLabel("TOMBSTONE_REQUIRED")} codes={target.tombstone_required_codes} />
                  <Codes title={categoryLabel("HR_ATTESTATION_REQUIRED")} codes={target.hr_attestation_codes} />
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export function RequestSummary({ request }: { request: TestPersonnelRequest }) {
  const validityDeadline = request.approval_expires_at ?? request.expires_at;
  return (
    <dl className="grid gap-2 text-sm sm:grid-cols-2 lg:grid-cols-3">
      <div><dt className="text-zinc-500">Статус</dt><dd className="font-medium">{statusLabel(request.status)}</dd></div>
      <div><dt className="text-zinc-500">Инициатор</dt><dd>{request.initiated_by_display_name ?? `Пользователь #${request.initiated_by_user_id}`}</dd></div>
      <div><dt className="text-zinc-500">Причина</dt><dd>{reasonLabel(request.reason_code)}</dd></div>
      <div><dt className="text-zinc-500">Количество целей</dt><dd>{request.targets?.length ?? "—"}</dd></div>
      <div><dt className="text-zinc-500">Hash manifest</dt><dd className="font-mono" title={request.target_set_hash}>{shortHash(request.target_set_hash)}</dd></div>
      <div><dt className="text-zinc-500">Создан</dt><dd>{formatDateTime(request.created_at)}</dd></div>
      <div><dt className="text-zinc-500">Срок действия</dt><dd>{formatDateTime(validityDeadline)}</dd></div>
    </dl>
  );
}

export function StateNotice({ status }: { status: string }) {
  if (status === "EXPIRED") {
    return <p role="status" className="rounded-lg bg-amber-50 p-3 text-sm text-amber-900">Срок согласования истёк. Создайте или повторно отправьте актуальный запрос.</p>;
  }
  if (status === "REAPPROVAL_REQUIRED") {
    return <p role="status" className="rounded-lg bg-amber-50 p-3 text-sm text-amber-900">Связанные данные изменились. Требуется повторное согласование.</p>;
  }
  return null;
}
