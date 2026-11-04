export type MedicalSpecialtySearchRow = {name:string;name_kk?:string|null;search_aliases?:string[]};

const normalize=(text:string)=>text.normalize('NFKC').toLocaleLowerCase().replace(/ё/g,'е').replace(/[^\p{L}\p{N}]+/gu,' ').trim();

export function matchesMedicalSpecialtyWords(row:MedicalSpecialtySearchRow,query:string):boolean {
  const haystack=normalize([row.name,row.name_kk||'',...(row.search_aliases||[])].join(' '));
  const words=normalize(query).split(/\s+/).filter(Boolean);
  return words.every(word=>haystack.includes(word));
}
