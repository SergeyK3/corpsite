import type {PersonnelOrderDetailResponse,PersonnelOrderEditorialState} from './personnelOrdersApi.client';

/** Both preview and print read the order's frozen paper heading, never the template picker name. */
export function personnelOrderPrintTitle(detail:PersonnelOrderDetailResponse,locale:'ru'|'kk',editorial?:PersonnelOrderEditorialState|null):string|null {
  const block=editorial?.order_blocks.find(row=>row.block_type==='title' && row.locale===locale);
  const snapshot=detail.print_title_snapshot;
  // A genuine document edit retains its priority. A copied picker label is
  // still an internal name, even if an older path stored it as an override.
  const manual=block?.override_text?.trim();
  if(manual && (!snapshot || snapshot.legacy || manual!==snapshot[`template_title_${locale}`]?.trim()))return manual;
  if(!snapshot || snapshot.legacy)return null; // Historical documents require an explicit snapshot update.
  return snapshot[`print_title_${locale}`]?.trim() || `[Печатный заголовок ${locale.toUpperCase()}: требуется согласование]`;
}
