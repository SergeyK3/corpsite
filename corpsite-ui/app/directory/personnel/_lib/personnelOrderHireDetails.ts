import {formatPersonnelOrderPrintDate} from './personnelOrderPrintFormat';
import type {MedicalSpecialtySnapshot} from '../_components/PersonnelOrderMedicalSpecialtyPicker';
export type HireCertificate = {specialty:MedicalSpecialtySnapshot|null;issued_on:string;name_ru?:string;name_kk?:string};
export function certificateSpecialtyName(certificate:HireCertificate|undefined,locale:'ru'|'kk'):string {
  const key=locale==='ru'?'name_ru':'name_kk';
  return certificate?.[key]??certificate?.specialty?.[key]??'';
}
export type HireDetails = {
  education: {code: string; ru: string; kk: string};
  service_length: {ru: string; kk: string};
  service_length_years?: string;
  certificate?: HireCertificate;
};

export const emptyHireDetails = (): HireDetails => ({education: {code: "", ru: "", kk: ""}, service_length: {ru: "", kk: ""}, service_length_years: "",certificate:{specialty:null,issued_on:''}});

export function hireYearsError(value: string): string {
  return value.trim() && !/^[0-9]+(?:[.,][0-9]+)?$/.test(value.trim()) ? "Введите неотрицательное количество лет, например 17,3" : "";
}

export function normalizeHireYears(value: string): string {
  const error = hireYearsError(value);
  if (error) throw Error(error);
  return value.trim().replace(",", ".").replace(/^0+(?=[0-9])/, "");
}

export function hireDetailsPayload(details: HireDetails): HireDetails {
  return {...details, ...(details.service_length_years !== undefined ? {service_length_years: normalizeHireYears(details.service_length_years)} : {})};
}

function yearsText(raw: string, locale: "ru" | "kk"): string {
  if (!raw.trim() || hireYearsError(raw)) return "";
  const canonical = normalizeHireYears(raw);
  const last = Number(canonical.slice(-2));
  const unit = locale === "kk" ? "жыл" : canonical.includes(".") ? "года"
    : last % 10 === 1 && last !== 11 ? "год" : [2,3,4].includes(last % 10) && ![12,13,14].includes(last) ? "года" : "лет";
  return `${canonical.replace(".", ",")} ${unit}`;
}

export function hireDetailsFromPayload(payload: Record<string, unknown>): HireDetails | undefined {
  const raw = payload.hire_details;
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) return undefined;
  const source = raw as Record<string, unknown>;
  const certificate=source.certificate&&typeof source.certificate==='object'?source.certificate as Record<string,unknown>:null;
  const texts = (value: unknown, keys: string[]) => {
    const record = value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : {};
    return Object.fromEntries(keys.map(key => [key, typeof record[key] === "string" ? record[key] : ""]));
  };
  return {education: texts(source.education, ["code", "ru", "kk"]), service_length: texts(source.service_length, ["ru", "kk"]),
    ...(certificate?{certificate:{specialty:certificate.specialty&&typeof certificate.specialty==='object'?certificate.specialty:null,issued_on:typeof certificate.issued_on==='string'?certificate.issued_on:'',
      ...(typeof certificate.name_ru==='string'?{name_ru:certificate.name_ru}:{}),...(typeof certificate.name_kk==='string'?{name_kk:certificate.name_kk}:{})}}:{}),
    ...(Object.prototype.hasOwnProperty.call(source, "service_length_years") ? {service_length_years: String(source.service_length_years ?? "")} : {})} as HireDetails;
}

export function hireDetailsLines(payload: Record<string, unknown>, locale: "ru" | "kk"): string[] {
  const details = hireDetailsFromPayload(payload);
  if (!details) return [];
  // Legacy prose stays opaque. Only an explicitly supplied numeric field
  // replaces its presentation, including an explicit empty value or zero.
  const tenure = details.service_length_years !== undefined
    ? yearsText(details.service_length_years, locale) : details.service_length[locale].trim();
  return [
    details.education[locale].trim() ? `${locale === "ru" ? "Образование" : "Білімі"}: ${details.education[locale].trim()}` : "",
    tenure ? `${locale === "ru" ? "Трудовой стаж" : "Еңбек өтілі"}: ${tenure}` : "",
    certificateSpecialtyName(details.certificate,locale).trim()
      ? `Сертификат: ${certificateSpecialtyName(details.certificate,locale).trim()}`:'',
    details.certificate?.issued_on ? `${locale==='ru'?'Дата выдачи сертификата':'Сертификаттың берілген күні'}: ${formatPersonnelOrderPrintDate(details.certificate.issued_on,locale)}`:'',
  ].filter(Boolean);
}
