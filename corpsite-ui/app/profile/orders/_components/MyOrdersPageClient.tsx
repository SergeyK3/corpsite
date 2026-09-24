"use client";

import { useEffect, useMemo, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import PositionCabinetSectionShell from "@/components/PositionCabinetSectionShell";
import { getMyOrder, getMyOrders, type MyOrder, type MyOrderDetail, type OrderLocale } from "../_lib/myOrdersApi.client";

type UiText = {
  title: string; description: string; year: string; status: string; all: string;
  confirmedFilter: string; unconfirmedFilter: string; open: string; close: string;
  print: string; printPreliminary: string; confirmed: string; unconfirmed: string;
  warning: string; watermark: string; loading: string; loadError: string; openError: string;
  empty: string; noDate: string; noNumber: string; language: string;
  dialog: string; preamble: string; basis: string;
};

const ui: Record<OrderLocale, UiText> = {
  kk: {
    title: "Менің бұйрықтарым",
    description: "Сіз қызметкер ретінде көрсетілген кадрлық бұйрықтар",
    year: "Жыл", status: "Мәртебе", all: "Барлығы",
    confirmedFilter: "Расталған", unconfirmedFilter: "Расталмаған",
    open: "Ашу", close: "Жабу", print: "Басып шығару",
    printPreliminary: "Алдын ала нұсқаны басып шығару",
    confirmed: "Кадр қызметімен расталған",
    unconfirmed: "Кадр қызметімен расталмаған",
    warning: "Бұйрық кадр қызметімен әлі расталмаған. Мәліметтер түпнұсқамен салыстырып тексерілгеннен кейін нақтылануы мүмкін.",
    watermark: "РАСТАЛМАҒАН",
    loading: "Бұйрықтар жүктелуде…",
    loadError: "Бұйрықтарды жүктеу мүмкін болмады.",
    openError: "Бұйрықты ашу мүмкін болмады.",
    empty: "Жеке карточкаңызға қатысты бұйрықтар әзірге жоқ.",
    noDate: "Күні көрсетілмеген", noNumber: "көрсетілмеген",
    language: "Бұйрық мазмұнының тілі", dialog: "Бұйрықты қарау",
    preamble: "Бұйрық преамбуласы", basis: "Бұйрықтың негіздемесі",
  },
  ru: {
    title: "Мои приказы",
    description: "Кадровые приказы, в которых вы указаны как работник",
    year: "Год", status: "Статус", all: "Все",
    confirmedFilter: "Подтверждённые", unconfirmedFilter: "Неподтверждённые",
    open: "Открыть", close: "Закрыть", print: "Распечатать",
    printPreliminary: "Распечатать предварительную версию",
    confirmed: "Подтверждено кадровой службой",
    unconfirmed: "Не подтверждено кадровой службой",
    warning: "Приказ ещё не подтверждён кадровой службой. Сведения могут быть уточнены после сверки с оригиналом.",
    watermark: "НЕ ПОДТВЕРЖДЕНО",
    loading: "Загрузка приказов…",
    loadError: "Не удалось загрузить приказы.",
    openError: "Не удалось открыть приказ.",
    empty: "Приказов, связанных с вашей личной карточкой, пока нет.",
    noDate: "Дата не указана", noNumber: "не указан",
    language: "Язык содержания приказа", dialog: "Просмотр приказа",
    preamble: "Преамбула приказа", basis: "Основание приказа",
  },
};

const missingContent: Record<OrderLocale, { item: string; preamble: string; basis: string }> = {
  kk: { item: "Бұйрық тармағының мәтіні электрондық нұсқада жоқ", preamble: "Бұйрықтың кіріспе мәтіні электрондық нұсқада жоқ", basis: "Негіздеме электрондық нұсқада жоқ" },
  ru: { item: "Текст пункта приказа отсутствует в электронной версии", preamble: "Преамбула приказа отсутствует в электронной версии", basis: "Основание отсутствует в электронной версии" },
};

const normalizeLocale = (value: string | null): OrderLocale => value === "ru" ? "ru" : "kk";

export default function MyOrdersPageClient() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const locale = normalizeLocale(searchParams.get("lang"));
  const text = ui[locale];
  const [orders, setOrders] = useState<MyOrder[]>([]);
  const [year, setYear] = useState("");
  const [confirmation, setConfirmation] = useState("all");
  const [selected, setSelected] = useState<MyOrderDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (searchParams.get("lang") === locale) return;
    const params = new URLSearchParams(searchParams.toString());
    params.set("lang", locale);
    router.replace(`${pathname}?${params.toString()}`, { scroll: false });
  }, [locale, pathname, router, searchParams]);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    getMyOrders(year || undefined, confirmation, locale)
      .then((response) => { if (alive) setOrders(response.orders); })
      .catch(() => alive && setError(ui[locale].loadError))
      .finally(() => alive && setLoading(false));
    return () => { alive = false; };
  }, [year, confirmation, locale]);

  const years = useMemo(() => [...new Set(orders.map((order) => order.order_date?.slice(0, 4)).filter(Boolean))] as string[], [orders]);
  const dateText = (value: string | null) => value ? new Intl.DateTimeFormat("ru-RU").format(new Date(`${value}T00:00:00`)) : text.noDate;
  const statusText = (status: MyOrder["confirmation_status"]) => status === "CONFIRMED" ? text.confirmed : text.unconfirmed;
  const setLocale = (nextLocale: OrderLocale) => {
    const params = new URLSearchParams(searchParams.toString());
    params.set("lang", nextLocale);
    router.replace(`${pathname}?${params.toString()}`, { scroll: false });
  };
  const open = async (id: number) => {
    try { setSelected(await getMyOrder(id, locale)); }
    catch { setError(ui[locale].openError); }
  };
  const draft = selected?.confirmation_status === "UNCONFIRMED";

  return <PositionCabinetSectionShell title={text.title}>
    <p className="mb-5 text-zinc-600 dark:text-zinc-400">{text.description}</p>
    <div className="mb-5 flex flex-wrap gap-3" data-testid="my-orders-filters">
      <label>{text.year} <select value={year} onChange={(event) => setYear(event.target.value)} className="ml-1 rounded border p-2"><option value="">{text.all}</option>{years.map((value) => <option key={value} value={value}>{value}</option>)}</select></label>
      <label>{text.status} <select value={confirmation} onChange={(event) => setConfirmation(event.target.value)} className="ml-1 rounded border p-2"><option value="all">{text.all}</option><option value="confirmed">{text.confirmedFilter}</option><option value="unconfirmed">{text.unconfirmedFilter}</option></select></label>
      <fieldset className="flex items-center gap-2" aria-label={text.language}><legend className="sr-only">{text.language}</legend><button type="button" className="rounded border px-3 py-2" aria-pressed={locale === "kk"} onClick={() => setLocale("kk")}>Қазақша</button><span aria-hidden="true">|</span><button type="button" className="rounded border px-3 py-2" aria-pressed={locale === "ru"} onClick={() => setLocale("ru")}>Русский</button></fieldset>
    </div>
    {error && <p role="alert">{error}</p>}
    {loading ? <p>{text.loading}</p> : orders.length === 0 ? <div data-testid="my-orders-empty" className="rounded-xl border p-5">{text.empty}</div> : <div className="space-y-3" data-testid="my-orders-list">{orders.map((order) => <article key={order.order_id} className="rounded-xl border border-zinc-200 p-4 dark:border-zinc-800"><div className="flex flex-wrap items-start justify-between gap-3"><div><p className="font-semibold">{order.title}</p><p>{dateText(order.order_date)} · № {order.order_number || text.noNumber}</p><p className="mt-2 text-zinc-600 dark:text-zinc-400">{order.item_text || missingContent[locale].item}</p><p className={order.confirmation_status === "CONFIRMED" ? "mt-2 text-green-700" : "mt-2 text-amber-700"}>{statusText(order.confirmation_status)}</p></div><button className="rounded-md border px-3 py-2" onClick={() => open(order.order_id)}>{text.open}</button></div></article>)}</div>}
    {selected && <div className="fixed inset-0 z-50 overflow-auto bg-black/40 p-4 print:static print:bg-white print:p-0" role="dialog" aria-modal="true" aria-label={text.dialog}><article className="relative my-8 mx-auto max-w-3xl bg-white p-6 text-zinc-900 shadow dark:bg-zinc-950 dark:text-zinc-100 print:my-0 print:max-w-none print:shadow-none" data-testid="my-order-document"><div className="mb-5 flex justify-end gap-2 print:hidden"><button className="rounded border px-3 py-2" onClick={() => setSelected(null)}>{text.close}</button><button className="rounded border px-3 py-2" onClick={() => window.print()}>{draft ? text.printPreliminary : text.print}</button></div>{draft && <><div className="mb-4 rounded border border-amber-500 bg-amber-50 p-3 text-amber-900">{selected.warning || text.warning}</div><div className="pointer-events-none absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 rotate-[-28deg] text-4xl font-bold text-red-600/25" data-testid="my-order-unconfirmed-watermark">{text.watermark}</div></>}<p className="text-sm">{dateText(selected.order_date)} · № {selected.order_number || text.noNumber}</p><h2 className="mt-2 text-xl font-bold">{selected.title}</h2><p className={draft ? "mt-3 text-amber-700" : "mt-3 text-green-700"}>{statusText(selected.confirmation_status)}</p><section className="mt-6 whitespace-pre-wrap" aria-label={text.preamble}>{selected.preamble || missingContent[locale].preamble}</section><p className="mt-4 whitespace-pre-wrap">{selected.item_text || missingContent[locale].item}</p><section className="mt-4 whitespace-pre-wrap" aria-label={text.basis}>{selected.basis || missingContent[locale].basis}</section></article></div>}
  </PositionCabinetSectionShell>;
}
