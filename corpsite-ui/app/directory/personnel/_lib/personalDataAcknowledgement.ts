/** Project FIO order: canonical/RU = surname-given-patronymic; KK cases = given-patronymic-surname. */
export type PersonalDataAcknowledgementParts=Record<'new_surname_ru'|'new_given_name_ru'|'new_surname_kk'|'new_given_name_kk',string>;
export function readPersonalDataAcknowledgementParts(personal:Record<string,unknown>|undefined):PersonalDataAcknowledgementParts{
 return Object.fromEntries(['new_surname_ru','new_given_name_ru','new_surname_kk','new_given_name_kk'].map(key=>[key,typeof personal?.[key]==='string'?personal[key]:''])) as PersonalDataAcknowledgementParts;
}
export function personalDataOriginalGivenNames(payload:Record<string,unknown>|null|undefined):{ru:string;kk:string}{
 const record=(v:unknown):Record<string,unknown>=>v&&typeof v==='object'?v as Record<string,unknown>:{};
 const text=(v:unknown)=>typeof v==='string'?v.trim():'';
 const component=(v:unknown,index:number)=>{const parts=text(v).split(/\s+/u).filter(Boolean);return parts.length>=2?parts[index]||'':'';};
 const canonical=text(payload?.source_employee_name)||text(record(payload?.unresolved_subject).full_name);
 const name=(locale:'ru'|'kk')=>{
  const saved=text(payload?.[`source_given_name_${locale}`]);if(saved)return saved;
  const forms=record(payload?.[`document_forms_${locale}`]);
  const fromCases=['genitive','dative','ablative','accusative'].map(form=>component(forms[`employee_full_name_${form}_${locale}`],locale==='kk'?0:1)).find(Boolean)||'';
  return locale==='kk'?fromCases||component(canonical,1):component(canonical,1)||fromCases;
 };
 return {ru:name('ru'),kk:name('kk')};
}
export function personalDataAcknowledgementNames(payload:Record<string,unknown>|null|undefined):{ru:string;kk:string}{
 const personal=payload?.personal_data as Record<string,unknown>|undefined;
 const original=personalDataOriginalGivenNames(payload);
 const name=(locale:'ru'|'kk')=>{
  const surname=personal?.[`new_surname_${locale}`],newName=personal?.[`new_given_name_${locale}`];
  const givenName=typeof newName==='string'&&newName.trim()?newName:original[locale];
  if(typeof surname!=='string'||!surname.trim())return '';
  const firstLetter=typeof givenName==='string'?givenName.match(/\p{L}/u)?.[0]:undefined;
  const initial=firstLetter?firstLetter+'.':'';
  if(!initial)return surname.trim();
  return locale==='kk'?`${initial} ${surname.trim()}`:`${surname.trim()} ${initial}`;
 };
 return {ru:name('ru'),kk:name('kk')};
}
