"use client";
import {setHireBasisText,type HireBasis} from '../_lib/personnelOrderHireBasis';
export default function PersonnelOrderHireBasisFields({value,onChange,disabled=false}:{value:HireBasis;onChange:(value:HireBasis)=>void;disabled?:boolean}) {
  return <fieldset disabled={disabled} className="grid gap-3 sm:col-span-2 sm:grid-cols-2" data-testid="hire-basis-fields">
    {(['ru','kk'] as const).map(locale=><label key={locale} className="block space-y-1"><span>Основание ({locale.toUpperCase()})</span>
      <textarea aria-label={`Основание (${locale.toUpperCase()})`} maxLength={2000} value={value[locale]}
        onChange={event=>onChange(setHireBasisText(value,locale,event.target.value))} className="block w-full rounded border bg-transparent p-2"/>
    </label>)}
  </fieldset>;
}
