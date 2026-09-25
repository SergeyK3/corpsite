"use client";
import * as React from "react";
import { listPersonnelOrderDocumentItems, patchPersonnelOrderDocumentItem, type PersonnelOrderDetailResponse, type PersonnelOrderDocumentItem } from "../_lib/personnelOrdersApi.client";

export default function PersonnelOrderBasisForm({ detail, onSaved }: { detail: PersonnelOrderDetailResponse; onSaved: () => Promise<void> }) {
  const [items, setItems] = React.useState<PersonnelOrderDocumentItem[]>([]);
  const [revision, setRevision] = React.useState(detail.order.document_revision ?? 1);
  const [basis, setBasis] = React.useState<"PERSONAL_APPLICATION" | "OTHER">("PERSONAL_APPLICATION");
  const [message, setMessage] = React.useState<string | null>(null);
  React.useEffect(() => { void listPersonnelOrderDocumentItems(detail.order.order_id).then((r) => { setItems(r.items); setRevision(r.document_revision); }); }, [detail.order.order_id]);
  async function save() { const item = items[0]; if (!item) return; try { await patchPersonnelOrderDocumentItem(detail.order.order_id, item.item_id, { expected_document_revision: revision, item_type_code: item.item_type_code, employee_id: item.employee_id || null, effective_date: item.effective_date || null, document_subject_context: { position_name: item.position_name || null, org_unit_name: item.org_unit_name || null, specialty: item.specialty || null, rate: item.rate || null, basis_type: basis }, reason_code: null, reason_text: null }); setMessage("Изменения сохранены"); await onSaved(); } catch { setMessage("Не удалось сохранить изменения."); } }
  return <section data-testid="personnel-order-basis-form" className="space-y-2"><label className="block text-sm">Основание<select aria-label="Основание" value={basis} onChange={(e) => setBasis(e.target.value as "PERSONAL_APPLICATION" | "OTHER")} className="mt-1 w-full rounded border p-2"><option value="PERSONAL_APPLICATION">Личное заявление</option><option value="OTHER">Другое</option></select></label><button type="button" onClick={() => void save()} className="rounded bg-blue-600 px-3 py-2 text-sm text-white">Сохранить изменения</button>{message ? <p role="status">{message}</p> : null}</section>;
}
