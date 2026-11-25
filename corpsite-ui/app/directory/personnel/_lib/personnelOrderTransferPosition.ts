import type {TransferFields} from "../_components/PersonnelOrderTransferFields";

export type TransferPositionRecord={position_id:number;name:string;name_kk?:string|null;translation_status?:string;revision?:number};
export type TransferPositionSnapshot={position_id:number;name:string;name_kk:string;translation_status?:string;revision?:number};

/** Dictionary values and explicit overrides belong to the document, not HR data. */
export function applyTransferPosition(current:TransferFields,row:TransferPositionRecord,intent:"mount"|"ru"|"kk"|"restore"):TransferFields {
 const snapshot:TransferPositionSnapshot={position_id:row.position_id,name:row.name.trim(),name_kk:row.name_kk?.trim()||"",translation_status:row.translation_status,revision:row.revision};
 const previous=current.position_dictionary;
 const flags={...current.position_overrides};
 for(const locale of ["ru","kk"] as const){
  const key=locale==="ru"?"position_ru":"position_kk";
  const old=previous?.[locale==="ru"?"name":"name_kk"];
  // Old documents without provenance keep their text conservatively.
  if(flags[locale]===undefined && intent==="mount")flags[locale]=current[key]!== (old??snapshot[locale==="ru"?"name":"name_kk"]);
 }
 if(intent==="restore"){flags.ru=false;flags.kk=false;}
 else if(intent!=="mount")flags[intent]=false;
 return {...current,position_id:row.position_id,position_dictionary:snapshot,position_overrides:flags,
  position_ru:flags.ru?current.position_ru:snapshot.name,
  position_kk:flags.kk?current.position_kk:snapshot.name_kk};
}
