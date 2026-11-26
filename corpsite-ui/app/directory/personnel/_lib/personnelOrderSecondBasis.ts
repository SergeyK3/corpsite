export type SecondBasis = {
  basis_second_ru?:string; basis_second_kk?:string;
  basis_second_type_ru?:string; basis_second_type_kk?:string;
  basis_second_overrides?:{ru?:boolean;kk?:boolean};
};
export type LinkedBasisOption={id:string;ru:string;kk:string};

export function selectSecondBasis(current:SecondBasis, option:LinkedBasisOption, locale:'ru'|'kk', options:readonly LinkedBasisOption[]):SecondBasis {
  const other=locale==='ru'?'kk':'ru';
  const oldType=current[`basis_second_type_${other}`];
  const oldOption=options.find(row=>row.id===oldType);
  const existing=current[`basis_second_${other}`] || '';
  const manual=current.basis_second_overrides?.[other]
    ?? Boolean(existing && (!oldOption || existing!==oldOption[other]));
  const next:SecondBasis={
    ...current,[`basis_second_${locale}`]:option[locale],[`basis_second_type_${locale}`]:option.id,
    basis_second_overrides:{...current.basis_second_overrides,[locale]:false},
  };
  if(!manual){
    next[`basis_second_${other}`]=option[other] || '';
    next[`basis_second_type_${other}`]=option[other]?option.id:'';
  }
  return next;
}

export function editSecondBasis(current:SecondBasis,locale:'ru'|'kk',value:string):SecondBasis {
  return {...current,[`basis_second_${locale}`]:value,basis_second_overrides:{...current.basis_second_overrides,[locale]:true}};
}
