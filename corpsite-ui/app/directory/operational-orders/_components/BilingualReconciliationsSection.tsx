"use client";

import * as React from "react";

import { createReconciliation, invalidateReconciliation } from "../_lib/api";
import { formatDateTime } from "../_lib/mappers";
import type { BilingualReconciliation, DraftBlock, OperationalOrdersPermissions, WorkspaceDetail } from "../_lib/types";
import {
  isCurrentReconciliationStatus,
  isHistoricalReconciliationStatus,
  reconciliationStatusBadgeClass,
  reconciliationStatusLabel,
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

function blockMeta(blocks: DraftBlock[], blockId: number): { label: string; block?: DraftBlock } {
  const block = blocks.find((b) => b.block_id === blockId);
  if (!block) return { label: `#${blockId}` };
  return {
    block,
    label: `${block.block_type} · seq ${block.sequence}`,
  };
}

function ReconciliationCard({
  item,
  blocks,
  showActions,
  pending,
  onInvalidate,
}: {
  item: BilingualReconciliation;
  blocks: DraftBlock[];
  showActions: boolean;
  pending: boolean;
  onInvalidate: (id: number) => void;
}) {
  const ru = blockMeta(blocks, item.ru_block_id);
  const kk = blockMeta(blocks, item.kk_block_id);

  return (
    <article className="rounded-lg border p-3 dark:border-zinc-700" data-testid={`reconciliation-${item.id}`}>
      <div className="flex flex-wrap items-center gap-2">
        <span className={`rounded-md border px-2 py-0.5 text-xs ${reconciliationStatusBadgeClass(item.status)}`}>
          {reconciliationStatusLabel(item.status)}
        </span>
        <span className="text-xs text-zinc-400">#{item.id}</span>
      </div>
      <div className="mt-3 grid gap-3 md:grid-cols-[1fr_auto_1fr] md:items-center">
        <div className="rounded-lg bg-zinc-50 p-3 dark:bg-zinc-900">
          <div className="text-xs font-semibold text-zinc-500">Русский текст</div>
          <div className="text-sm">{ru.label}</div>
          <div className="text-xs text-zinc-500">v{item.ru_block_version}</div>
          <CompactFingerprint value={item.ru_content_fingerprint} label="fp" />
        </div>
        <div className="text-center text-lg text-zinc-400">↔</div>
        <div className="rounded-lg bg-zinc-50 p-3 dark:bg-zinc-900">
          <div className="text-xs font-semibold text-zinc-500">Казахский текст</div>
          <div className="text-sm">{kk.label}</div>
          <div className="text-xs text-zinc-500">v{item.kk_block_version}</div>
          <CompactFingerprint value={item.kk_content_fingerprint} label="fp" />
        </div>
      </div>
      <dl className="mt-3 grid gap-1 text-sm md:grid-cols-2">
        <div>
          <dt className="text-xs text-zinc-500">Согласовал</dt>
          <dd>{item.reconciled_by_user_id ? `user #${item.reconciled_by_user_id}` : "—"}</dd>
        </div>
        <div>
          <dt className="text-xs text-zinc-500">Дата согласования</dt>
          <dd>{formatDateTime(item.reconciled_at)}</dd>
        </div>
        {item.invalidated_at ? (
          <>
            <div>
              <dt className="text-xs text-zinc-500">Инвалидация</dt>
              <dd>{formatDateTime(item.invalidated_at)}</dd>
            </div>
            <div>
              <dt className="text-xs text-zinc-500">Причина</dt>
              <dd>{item.invalidation_reason ?? "—"}</dd>
            </div>
          </>
        ) : null}
      </dl>
      {showActions && item.status === "RECONCILED" ? (
        <button type="button" className="mt-2 rounded border px-2 py-1 text-xs text-red-700" disabled={pending} onClick={() => onInvalidate(item.id)}>
          Инвалидировать
        </button>
      ) : null}
    </article>
  );
}

export default function BilingualReconciliationsSection({
  detail,
  frozen,
  perms,
  pending,
  onUpdated,
  onError,
}: Props) {
  const items = detail.bilingual_reconciliations ?? [];
  const current = items.filter((r) => isCurrentReconciliationStatus(r.status));
  const history = items.filter((r) => isHistoricalReconciliationStatus(r.status));

  const [showCreate, setShowCreate] = React.useState(false);
  const [ruBlockId, setRuBlockId] = React.useState("");
  const [kkBlockId, setKkBlockId] = React.useState("");

  const ruBlocks = detail.blocks.filter((b) => b.locale === "ru");
  const kkBlocks = detail.blocks.filter((b) => b.locale === "kk");
  const canReconcile = !frozen && Boolean(perms.reconcile);

  async function mutate(action: () => Promise<WorkspaceDetail>) {
    try {
      const updated = await action();
      onUpdated(updated);
    } catch (e) {
      onError(e);
    }
  }

  return (
    <section className="rounded-xl border p-4 dark:border-zinc-800" id="section-reconciliations">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm font-semibold">Согласование RU/KK</h3>
        {canReconcile ? (
          <button type="button" className="rounded border px-2 py-1 text-xs" onClick={() => setShowCreate((v) => !v)}>
            {showCreate ? "Скрыть форму" : "Создать согласование"}
          </button>
        ) : null}
      </div>

      {showCreate && canReconcile ? (
        <div className="mb-4 rounded-lg border border-dashed p-3 dark:border-zinc-700">
          <div className="grid gap-2 md:grid-cols-2">
            <label className="text-sm">
              RU block
              <select className="mt-1 w-full rounded border px-2 py-1 dark:border-zinc-700 dark:bg-zinc-950" value={ruBlockId} onChange={(e) => setRuBlockId(e.target.value)}>
                <option value="">Выберите</option>
                {ruBlocks.map((b) => (
                  <option key={b.block_id} value={b.block_id}>
                    {b.block_type} · seq {b.sequence} · v{b.version}
                  </option>
                ))}
              </select>
            </label>
            <label className="text-sm">
              KK block
              <select className="mt-1 w-full rounded border px-2 py-1 dark:border-zinc-700 dark:bg-zinc-950" value={kkBlockId} onChange={(e) => setKkBlockId(e.target.value)}>
                <option value="">Выберите</option>
                {kkBlocks.map((b) => (
                  <option key={b.block_id} value={b.block_id}>
                    {b.block_type} · seq {b.sequence} · v{b.version}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <button
            type="button"
            className="mt-3 rounded bg-blue-600 px-3 py-1.5 text-sm text-white disabled:opacity-50"
            disabled={pending || !ruBlockId || !kkBlockId}
            onClick={() => {
              const ru = detail.blocks.find((b) => String(b.block_id) === ruBlockId);
              const kk = detail.blocks.find((b) => String(b.block_id) === kkBlockId);
              if (!ru || !kk) return;
              void mutate(() =>
                createReconciliation(detail.workspace.workspace_id, {
                  ru_block_id: ru.block_id,
                  kk_block_id: kk.block_id,
                  ru_block_expected_version: ru.version,
                  kk_block_expected_version: kk.version,
                  expected_version: detail.workspace.version,
                }),
              );
            }}
          >
            Согласовать пару
          </button>
        </div>
      ) : null}

      {!items.length ? (
        <p className="text-sm text-zinc-500" data-testid="reconciliations-empty">
          Двуязычное согласование ещё не выполнено
        </p>
      ) : (
        <div className="space-y-4">
          {current.map((item) => (
            <ReconciliationCard
              key={item.id}
              item={item}
              blocks={detail.blocks}
              pending={pending}
              showActions={canReconcile}
              onInvalidate={(id) => {
                const rec = items.find((r) => r.id === id);
                if (!rec) return;
                void mutate(() =>
                  invalidateReconciliation(detail.workspace.workspace_id, id, {
                    invalidation_reason: "Invalidated via UI",
                    expected_version: detail.workspace.version,
                    reconciliation_expected_version: rec.version,
                  }),
                );
              }}
            />
          ))}
          {history.length ? (
            <details>
              <summary className="cursor-pointer text-xs font-semibold uppercase tracking-wide text-zinc-500">История ({history.length})</summary>
              <div className="mt-2 space-y-3">
                {history.map((item) => (
                  <ReconciliationCard key={item.id} item={item} blocks={detail.blocks} pending={pending} showActions={false} onInvalidate={() => {}} />
                ))}
              </div>
            </details>
          ) : null}
        </div>
      )}
    </section>
  );
}
