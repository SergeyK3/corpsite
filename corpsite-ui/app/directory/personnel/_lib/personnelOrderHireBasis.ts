import {defaultHireBasis} from './personnelOrderHireTerms';
export type HireBasis = {ru: string; kk: string;kk_intentionally_empty?:boolean};
export const newHireBasis = (): HireBasis => ({ru:defaultHireBasis('ru'),kk:defaultHireBasis('kk')});
type BasisDocument = {basis_id?:unknown;description?:unknown};
export function hireBasisOverride(block?:{override_text?:string|null;generated_text?:string|null;effective_text?:string|null}):string|undefined {
  if(typeof block?.override_text==='string')return block.override_text;
  return !block?.generated_text&&typeof block?.effective_text==='string'?block.effective_text:undefined;
}

/** Legacy prose belongs only to its saved source language; never translate it. */
export function hireBasisFromPayload(payload: Record<string,unknown>, sourceLocale?:string|null, documents:BasisDocument[]=[]): HireBasis {
  const paired=payload.hire_basis;
  if(paired&&typeof paired==='object'&&!Array.isArray(paired)) {
    const value=paired as Record<string,unknown>;
    return {ru:typeof value.ru==='string'?value.ru:'',kk:typeof value.kk==='string'?value.kk:'',
      ...(value.kk_intentionally_empty===true?{kk_intentionally_empty:true}:{})};
  }
  const legacyLocale=sourceLocale==='kk'?'kk':'ru';
  const localized=(raw:unknown,locale:'ru'|'kk') => raw&&typeof raw==='object'
    ? String((raw as Record<string,unknown>)[locale]||'') : locale===legacyLocale&&typeof raw==='string'?raw:'';
  const entries=Array.isArray(payload.basis_entries)?payload.basis_entries as Record<string,unknown>[]:[];
  const linked=(id:unknown,locale:'ru'|'kk')=>localized(documents.find(row=>String(row.basis_id)===String(id))?.description,locale);
  const texts=(locale:'ru'|'kk')=>entries.length?entries.map(entry=>entry.document_type==='OTHER'?localized(entry.other_text,locale):linked(entry.basis_id,locale))
    : [...(Array.isArray(payload.basis_ids)?payload.basis_ids:[]).map(id=>linked(id,locale)),
      localized(payload.basis_other_text??(typeof payload.basis==='string'?payload.basis:''),locale)];
  return {ru:texts('ru').filter(Boolean).join('\n'),kk:texts('kk').filter(Boolean).join('\n')};
}

/** Editor-only proposal. Reading a document never fills or persists a basis. */
export function hireBasisForEditing(payload:Record<string,unknown>,sourceLocale?:string|null,documents:BasisDocument[]=[]):HireBasis {
  const basis=hireBasisFromPayload(payload,sourceLocale,documents);
  const standard=basis.ru.trim().toLocaleLowerCase('ru').replace(/\.$/,'')===defaultHireBasis('ru');
  return standard&&!basis.kk.trim()&&!basis.kk_intentionally_empty?{...basis,kk:defaultHireBasis('kk')}:basis;
}

export function setHireBasisText(value:HireBasis,locale:'ru'|'kk',text:string):HireBasis {
  const next={...value,[locale]:text};
  if(locale==='kk'){
    if(!text.trim())next.kk_intentionally_empty=true;
    else delete next.kk_intentionally_empty;
  }
  return next;
}
