"use client";

import * as React from "react";
import PersonnelOrderCreateDialog from "./PersonnelOrderCreateDialog";
import {getPersonnelOrderAddItemContext, mapPersonnelOrdersApiError, type PersonnelOrderAddItemContext, type PersonnelOrderDetailResponse} from "../_lib/personnelOrdersApi.client";

export default function PersonnelOrderInheritedItemForm({orderId, onAdded, onCancel}: {
  orderId: number;
  onAdded: (order: PersonnelOrderDetailResponse) => void;
  onCancel: () => void;
}) {
  const [context, setContext] = React.useState<PersonnelOrderAddItemContext | null>(null);
  const [error, setError] = React.useState("");
  const [attempt, setAttempt] = React.useState(0);
  React.useEffect(() => {
    let cancelled = false;
    setContext(null); setError("");
    getPersonnelOrderAddItemContext(orderId).then(result => {
      if (!cancelled) setContext(result);
    }).catch(caught => {
      if (!cancelled) setError(mapPersonnelOrdersApiError(caught, "Не удалось определить закреплённый шаблон приказа."));
    });
    return () => {cancelled = true;};
  }, [orderId, attempt]);
  const itemContext = React.useMemo(() => context?.available && context.template && context.item_type_code
    ? {orderId, template: context.template, itemTypeCode: context.item_type_code, employeeIds: context.employee_ids ?? []}
    : undefined, [context, orderId]);
  if (error) return <div className="p-4"><p role="alert">{error}</p><button type="button" onClick={() => setAttempt(value => value + 1)}>Повторить загрузку</button></div>;
  if (!context) return <p role="status" className="p-4">Загрузка закреплённого шаблона…</p>;
  if (!itemContext) return <p role="alert" className="p-4">{context.reason || "Добавление недоступно: версия шаблона не определена."}</p>;
  return <PersonnelOrderCreateDialog open itemContext={itemContext} onClose={onCancel} onCreated={() => undefined} onItemAdded={onAdded} />;
}
