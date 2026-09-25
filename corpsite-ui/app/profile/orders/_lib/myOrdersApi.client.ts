"use client";

import { buildHeaders, readJsonSafe, toApiError } from "@/lib/api";
import { resolveApiUrl } from "@/lib/apiBase";

export type OrderLocale = "kk" | "ru";
export type ConfirmationStatus = "CONFIRMED" | "UNCONFIRMED";
export type MyOrder = {
  order_id: number;
  order_number: string | null;
  order_date: string | null;
  title: string;
  item_text: string | null;
  confirmation_status: ConfirmationStatus;
};
export type MyOrderDetail = MyOrder & {
  warning: string | null;
  preamble: string | null;
  basis: string | null;
  tenure_text?: string | null;
};
export type MyOrdersResponse = {
  status: "READY" | "NO_EMPLOYEE_LINK" | "PERSON_NOT_LINKED" | "IDENTITY_AMBIGUOUS";
  orders: MyOrder[];
};

async function get<T>(path: string): Promise<T> {
  const response = await fetch(resolveApiUrl(path), {
    headers: buildHeaders({ Accept: "application/json" }),
    cache: "no-store",
  });
  const body = await readJsonSafe(response);
  if (!response.ok) throw toApiError(response.status, body, { method: "GET", url: path });
  return body as T;
}

export const getMyOrders = (year?: string, confirmation = "all", locale: OrderLocale = "kk") =>
  get<MyOrdersResponse>(`/api/ppr/me/orders?${new URLSearchParams({
    ...(year ? { year } : {}), confirmation, locale,
  })}`);

export const getMyOrder = (orderId: number, locale: OrderLocale = "kk") =>
  get<MyOrderDetail>(`/api/ppr/me/orders/${orderId}?${new URLSearchParams({ locale })}`);
