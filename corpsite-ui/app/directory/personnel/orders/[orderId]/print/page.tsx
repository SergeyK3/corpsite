import { Suspense } from "react";

import PersonnelOrderPrintPageClient from "../../../_components/print/PersonnelOrderPrintPageClient";

export const dynamic = "force-dynamic";

type PageProps = {
  params: Promise<{ orderId: string }> | { orderId: string };
};

export default async function PersonnelOrderPrintPage({ params }: PageProps) {
  const resolved = await Promise.resolve(params);
  const orderId = Number(resolved.orderId);

  if (!Number.isFinite(orderId) || orderId <= 0) {
    return (
      <div className="p-6 text-sm text-red-700" data-testid="personnel-order-print-invalid-id">
        Некорректный идентификатор приказа.
      </div>
    );
  }

  return (
    <Suspense
      fallback={
        <div className="p-6 text-sm text-zinc-500">Загрузка печатной формы…</div>
      }
    >
      <PersonnelOrderPrintPageClient orderId={orderId} />
    </Suspense>
  );
}
