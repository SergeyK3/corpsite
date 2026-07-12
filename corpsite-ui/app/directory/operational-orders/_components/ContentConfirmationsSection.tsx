"use client";

import * as React from "react";

import {
  createConfirmation,
  parseContentConfirmations,
  revokeConfirmation,
} from "../_lib/api";
import { formatDateTime, formatPartyReference } from "../_lib/mappers";
import type { OperationalOrdersPermissions, WorkspaceDetail } from "../_lib/types";
import {
  confirmationRoleLabel,
  confirmationStatusBadgeClass,
  confirmationStatusLabel,
  isCurrentConfirmationStatus,
  isHistoricalConfirmationStatus,
} from "../_lib/status";
import CompactFingerprint from "./CompactFingerprint";

type Props = {
  detail: WorkspaceDetail;
  frozen: boolean;
  perms: OperationalOrdersPermissions;
  pending: boolean;
  onUpdated: (detail: WorkspaceDetail) => void;
  onError: (err: unknown) => void;
};

const ROLES = ["CONTENT_AUTHOR", "TRANSLATOR", "DOCUMENT_OPERATOR"] as const;

export default function ContentConfirmationsSection({
  detail,
  frozen,
  perms,
  pending,
  onUpdated,
  onError,
}: Props) {
  const confirmations = parseContentConfirmations(detail);
  const current = confirmations.filter((c) => isCurrentConfirmationStatus(c.status));
  const history = confirmations.filter((c) => isHistoricalConfirmationStatus(c.status));

  const [showCreate, setShowCreate] = React.useState(false);
  const [blockId, setBlockId] = React.useState("");
  const [role, setRole] = React.useState<(typeof ROLES)[number]>("DOCUMENT_OPERATOR");
  const [confirmerRef, setConfirmerRef] = React.useState("");
  const [confirmerName, setConfirmerName] = React.useState("");
  const [operatorRecorded, setOperatorRecorded] = React.useState(true);

  const canConfirm = !frozen && Boolean(perms.content_confirm);

  async function mutate(action: () => Promise<WorkspaceDetail>) {
    try {
      const updated = await action();
      onUpdated(updated);
    } catch (e) {
      onError(e);
    }
  }

  function blockLabel(blockIdNum: number): string {
    const block = detail.blocks.find((b) => b.block_id === blockIdNum);
    if (!block) return `#${blockIdNum}`;
    return `${block.locale.toUpperCase()} · ${block.block_type} · seq ${block.sequence}`;
  }

  return (
    <section className="rounded-xl border p-4 dark:border-zinc-800" id="section-confirmations">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm font-semibold">Подтверждения содержания</h3>
        {canConfirm ? (
          <button type="button" className="rounded border px-2 py-1 text-xs" onClick={() => setShowCreate((v) => !v)}>
            {showCreate ? "Скрыть форму" : "Подтвердить блок"}
          </button>
        ) : null}
      </div>

      {showCreate && canConfirm ? (
        <div className="mb-4 rounded-lg border border-dashed p-3 dark:border-zinc-700">
          <div className="grid gap-2 md:grid-cols-2">
            <label className="text-sm md:col-span-2">
              Блок
              <select className="mt-1 w-full rounded border px-2 py-1 dark:border-zinc-700 dark:bg-zinc-950" value={blockId} onChange={(e) => setBlockId(e.target.value)}>
                <option value="">Выберите блок</option>
                {detail.blocks.map((b) => (
                  <option key={b.block_id} value={b.block_id}>
                    {b.locale.toUpperCase()} · {b.block_type} · #{b.block_id} · v{b.version}
                  </option>
                ))}
              </select>
            </label>
            <label className="text-sm">
              Роль
              <select className="mt-1 w-full rounded border px-2 py-1 dark:border-zinc-700 dark:bg-zinc-950" value={role} onChange={(e) => setRole(e.target.value as (typeof ROLES)[number])}>
                {ROLES.map((r) => (
                  <option key={r} value={r}>
                    {confirmationRoleLabel(r)}
                  </option>
                ))}
              </select>
            </label>
            <label className="text-sm">
              PERSON reference
              <input className="mt-1 w-full rounded border px-2 py-1 dark:border-zinc-700 dark:bg-zinc-950" value={confirmerRef} onChange={(e) => setConfirmerRef(e.target.value)} />
            </label>
            <label className="text-sm md:col-span-2 flex items-center gap-2">
              <input type="checkbox" checked={operatorRecorded} onChange={(e) => setOperatorRecorded(e.target.checked)} />
              operator_recorded (proxy operator)
            </label>
          </div>
          <button
            type="button"
            className="mt-3 rounded bg-blue-600 px-3 py-1.5 text-sm text-white disabled:opacity-50"
            disabled={pending || !blockId || !confirmerRef.trim()}
            onClick={() => {
              const block = detail.blocks.find((b) => String(b.block_id) === blockId);
              if (!block) return;
              void mutate(() =>
                createConfirmation(detail.workspace.workspace_id, {
                  block_id: block.block_id,
                  confirmation_role: role,
                  confirmer: {
                    reference_type: "PERSON",
                    reference: confirmerRef.trim(),
                    display_name: confirmerName.trim() || null,
                  },
                  block_expected_version: block.version,
                  expected_version: detail.workspace.version,
                  operator_recorded: operatorRecorded,
                }),
              );
            }}
          >
            Создать подтверждение
          </button>
        </div>
      ) : null}

      {!confirmations.length ? (
        <p className="text-sm text-zinc-500" data-testid="confirmations-empty">
          Подтверждений пока нет
        </p>
      ) : (
        <div className="space-y-4">
          {current.length ? (
            <div className="space-y-3">
              {current.map((c) => (
                <article key={c.id} className="rounded-lg border p-3 dark:border-zinc-700" data-testid={`confirmation-${c.id}`}>
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-medium">{blockLabel(c.block_id)}</span>
                    <span className={`rounded-md border px-2 py-0.5 text-xs ${confirmationStatusBadgeClass(c.status)}`}>
                      {confirmationStatusLabel(c.status)}
                    </span>
                  </div>
                  <dl className="mt-2 grid gap-1 text-sm md:grid-cols-2">
                    <div>
                      <dt className="text-xs text-zinc-500">Роль</dt>
                      <dd>{confirmationRoleLabel(c.confirmation_role)}</dd>
                    </div>
                    <div>
                      <dt className="text-xs text-zinc-500">Подтверждающий</dt>
                      <dd>{formatPartyReference(c.confirmer_party_type, c.confirmer_party_reference, c.confirmer_display_name)}</dd>
                    </div>
                    <div>
                      <dt className="text-xs text-zinc-500">Версия блока</dt>
                      <dd>{c.block_version}</dd>
                    </div>
                    <div>
                      <dt className="text-xs text-zinc-500">Подтверждено</dt>
                      <dd>{formatDateTime(c.confirmed_at)}</dd>
                    </div>
                  </dl>
                  <CompactFingerprint value={c.content_fingerprint} />
                  {canConfirm ? (
                    <button
                      type="button"
                      className="mt-2 rounded border px-2 py-1 text-xs text-red-700"
                      disabled={pending}
                      onClick={() =>
                        void mutate(() =>
                          revokeConfirmation(detail.workspace.workspace_id, c.id, {
                            revocation_reason: "Revoked via UI",
                            expected_version: detail.workspace.version,
                            confirmation_expected_version: c.version,
                          }),
                        )
                      }
                    >
                      Отозвать
                    </button>
                  ) : null}
                </article>
              ))}
            </div>
          ) : null}
          {history.length ? (
            <details>
              <summary className="cursor-pointer text-xs font-semibold uppercase tracking-wide text-zinc-500">История ({history.length})</summary>
              <div className="mt-2 space-y-3">
                {history.map((c) => (
                  <article key={c.id} className="rounded-lg border p-3 opacity-80 dark:border-zinc-700">
                    <div className="font-medium">{blockLabel(c.block_id)} · {confirmationStatusLabel(c.status)}</div>
                    <div className="text-sm">{confirmationRoleLabel(c.confirmation_role)}</div>
                    {c.revocation_reason ? <div className="text-xs text-zinc-500">{c.revocation_reason}</div> : null}
                  </article>
                ))}
              </div>
            </details>
          ) : null}
        </div>
      )}
    </section>
  );
}
