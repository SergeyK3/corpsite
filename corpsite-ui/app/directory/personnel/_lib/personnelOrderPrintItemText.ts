import type { PersonnelOrderPrintLanguage } from "./personnelOrderPrintLanguage";
import {
  formatPersonnelOrderPrintDate,
  formatPersonnelOrderPrintRate,
  formatPersonnelOrderPrintRateValue,
} from "./personnelOrderPrintFormat";
import type { LocalizedText } from "./personnelOrderPrintLocalized";
import { resolveLocalizedText } from "./personnelOrderPrintLocalized";
import { russianEmployeeForOrder, russianOrderAssignment } from "./personnelOrderRussianWording";

export type PersonnelOrderPrintItemContext = {
  itemNumber: number;
  itemTypeCode: string;
  employeeName: string | null;
  effectiveDate: string | null;
  orgUnitName: LocalizedText | null;
  positionName: LocalizedText | null;
  toOrgUnitName: LocalizedText | null;
  toPositionName: LocalizedText | null;
  rate: number | string | null;
  toRate: number | string | null;
  concurrentRate: number | string | null;
  remainingRate: number | string | null;
  totalRate: number | string | null;
  terminationReason: string | null;
  payload: Record<string, unknown>;
};

function dash(value: string | null | undefined): string {
  const text = String(value || "").trim();
  return text || "—";
}

function renderHire(ctx: PersonnelOrderPrintItemContext, lang: "kk" | "ru"): string {
  const fio = dash(ctx.employeeName);
  const org = resolveLocalizedText(ctx.orgUnitName, lang);
  const position = resolveLocalizedText(ctx.positionName, lang);
  const rateValue = formatPersonnelOrderPrintRateValue(ctx.rate);
  const date = formatPersonnelOrderPrintDate(ctx.effectiveDate, lang);
  if (lang === "kk") {
    return `${fio} «${org}» бөлімшесіне «${position}» лауазымына ${rateValue} мөлшерлемесінде ${date} бастап жұмысқа қабылдансын.`;
  }
  const employee = russianEmployeeForOrder(fio);
  return employee
    ? `Принять сотрудника ${employee} с ${date} на должность ${russianOrderAssignment(position, org)} с оплатой ${rateValue} ставки.`
    : `Принять на работу ${fio} в подразделение «${org}» на должность «${position}» со ставкой ${rateValue} с ${date}.`;
}

function renderTransfer(ctx: PersonnelOrderPrintItemContext, lang: "kk" | "ru"): string {
  const fio = dash(ctx.employeeName);
  const org = resolveLocalizedText(ctx.toOrgUnitName || ctx.orgUnitName, lang);
  const position = resolveLocalizedText(ctx.toPositionName || ctx.positionName, lang);
  const rateValue =
    ctx.toRate != null && ctx.toRate !== ""
      ? formatPersonnelOrderPrintRateValue(ctx.toRate)
      : null;
  const date = formatPersonnelOrderPrintDate(ctx.effectiveDate, lang);
  if (lang === "kk") {
    const ratePart = rateValue ? `, ${rateValue} мөлшерлемесінде` : "";
    return `${fio} «${org}» бөлімшесіне «${position}» лауазымына${ratePart} ${date} бастап ауыстырылсын.`;
  }
  const employee = russianEmployeeForOrder(fio);
  if (employee) {
    const ratePart = rateValue ? ` с оплатой ${rateValue} ставки` : "";
    return `Перевести сотрудника ${employee} с ${date} на должность ${russianOrderAssignment(position, org)}${ratePart}.`;
  }
  const ratePart = rateValue ? ` со ставкой ${rateValue}` : "";
  return `Перевести ${fio} в подразделение «${org}» на должность «${position}»${ratePart} с ${date}.`;
}

function renderTermination(ctx: PersonnelOrderPrintItemContext, lang: "kk" | "ru"): string {
  const fio = dash(ctx.employeeName);
  const date = formatPersonnelOrderPrintDate(ctx.effectiveDate, lang);
  const reason = optionalReason(ctx.terminationReason);
  if (lang === "kk") {
    const reasonPart = reason ? ` Негіздеме: ${reason}.` : "";
    return `${fio} ${date} бастап жұмыстан босатылсын.${reasonPart}`;
  }
  const reasonPart = reason ? ` Основание: ${reason}.` : "";
  return `Уволить ${fio} с ${date}.${reasonPart}`;
}

function optionalReason(value: string | null | undefined): string | null {
  const text = String(value || "").trim();
  return text || null;
}

function renderConcurrentStart(ctx: PersonnelOrderPrintItemContext, lang: "kk" | "ru"): string {
  const fio = dash(ctx.employeeName);
  const concurrentValue = formatPersonnelOrderPrintRateValue(ctx.concurrentRate);
  const total =
    ctx.totalRate != null && ctx.totalRate !== ""
      ? formatPersonnelOrderPrintRate(ctx.totalRate, lang)
      : null;
  const date = formatPersonnelOrderPrintDate(ctx.effectiveDate, lang);
  if (lang === "kk") {
    const totalPart = total ? ` Жалпы мөлшерлеме: ${total}.` : "";
    return `${fio} үшін қоса атқару ${concurrentValue} мөлшерлемесінде ${date} бастап белгіленсін.${totalPart}`;
  }
  const employee = russianEmployeeForOrder(fio);
  const position = resolveLocalizedText(ctx.toPositionName || ctx.positionName, "ru");
  const unit = resolveLocalizedText(ctx.toOrgUnitName || ctx.orgUnitName, "ru");
  const assignment = russianOrderAssignment(position, unit);
  if (employee) {
    return `Разрешить сотруднику ${employee} с ${date} совмещение обязанностей по должности ${assignment} с оплатой ${concurrentValue} ставки.`;
  }
  const totalPart = total ? ` Итоговая ставка: ${total}.` : "";
  return `Установить ${fio} совмещение в размере ${concurrentValue} ставки с ${date}.${totalPart}`;
}

function renderConcurrentEnd(ctx: PersonnelOrderPrintItemContext, lang: "kk" | "ru"): string {
  const fio = dash(ctx.employeeName);
  const remaining =
    ctx.remainingRate != null && ctx.remainingRate !== ""
      ? formatPersonnelOrderPrintRate(ctx.remainingRate, lang)
      : null;
  const concurrent =
    ctx.concurrentRate != null && ctx.concurrentRate !== ""
      ? formatPersonnelOrderPrintRate(ctx.concurrentRate, lang)
      : null;
  const date = formatPersonnelOrderPrintDate(ctx.effectiveDate, lang);
  if (lang === "kk") {
    const rem = remaining ? ` Қалған мөлшерлеме: ${remaining}.` : "";
    const remConcurrent = concurrent ? ` Алынатын мөлшерлеме: ${concurrent}.` : "";
    return `${fio} үшін қоса атқару ${date} бастап тоқтатылсын.${rem}${remConcurrent}`;
  }
  const rem = remaining ? ` Остающаяся ставка: ${remaining}.` : "";
  const remConcurrent = concurrent ? ` Снимаемая ставка: ${concurrent}.` : "";
  return `Прекратить совмещение для ${fio} с ${date}.${rem}${remConcurrent}`;
}

function renderGeneric(ctx: PersonnelOrderPrintItemContext, lang: "kk" | "ru"): string {
  const fio = dash(ctx.employeeName);
  const date = formatPersonnelOrderPrintDate(ctx.effectiveDate, lang);
  if (lang === "kk") {
    return `${fio}, күні ${date}.`;
  }
  return `${fio}, дата ${date}.`;
}

export function renderPersonnelOrderPrintItemText(
  ctx: PersonnelOrderPrintItemContext,
  language: PersonnelOrderPrintLanguage,
): string[] {
  const type = String(ctx.itemTypeCode || "").trim().toUpperCase();
  const renderOne = (lang: "kk" | "ru") => {
    switch (type) {
      case "HIRE":
        return renderHire(ctx, lang);
      case "TRANSFER":
        return renderTransfer(ctx, lang);
      case "TERMINATION":
        return renderTermination(ctx, lang);
      case "CONCURRENT_DUTY_START":
        return renderConcurrentStart(ctx, lang);
      case "CONCURRENT_DUTY_END":
        return renderConcurrentEnd(ctx, lang);
      default:
        return renderGeneric(ctx, lang);
    }
  };

  if (language === "kk") return [renderOne("kk")];
  if (language === "ru") return [renderOne("ru")];
  const kk = renderOne("kk");
  const ru = renderOne("ru");
  return kk === ru ? [kk] : [kk, ru];
}
