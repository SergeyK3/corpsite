/**
 * Safe PDF generation audit log — no PII body, cookies, HTML, or PDF bytes.
 */
export type PersonnelOrderPdfAuditEvent = {
  order_id: number | null;
  language: string | null;
  requesting_user_id: string | null;
  result: "ok" | "error";
  duration_ms: number;
  error_code?: string;
};

export function logPersonnelOrderPdfAudit(event: PersonnelOrderPdfAuditEvent): void {
  console.info(
    JSON.stringify({
      event: "personnel_order_pdf",
      order_id: event.order_id,
      language: event.language,
      requesting_user_id: event.requesting_user_id,
      result: event.result,
      duration_ms: event.duration_ms,
      ...(event.error_code ? { error_code: event.error_code } : {}),
    }),
  );
}
