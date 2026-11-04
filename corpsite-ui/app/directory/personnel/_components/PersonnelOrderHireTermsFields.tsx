"use client";
import PersonnelOrderHireBasisFields from "./PersonnelOrderHireBasisFields";
import type {HireBasis} from "../_lib/personnelOrderHireBasis";

export default function PersonnelOrderHireTermsFields({rate, onRateChange, basis, onBasisChange, disabled = false}: {
  rate: string; onRateChange: (value: string) => void;
  basis: HireBasis; onBasisChange: (value: HireBasis) => void; disabled?: boolean;
}) {
  return <fieldset disabled={disabled} className="space-y-3" data-testid="hire-terms-fields">
    <label className="block space-y-1"><span>Ставка</span>
      <input aria-label="Ставка" data-testid="personnel-order-hire-rate-input" inputMode="decimal" maxLength={20}
        value={rate} onChange={event => onRateChange(event.target.value)} className="block w-full rounded border bg-transparent p-2"/>
    </label>
    <PersonnelOrderHireBasisFields value={basis} onChange={onBasisChange} disabled={disabled}/>
  </fieldset>;
}
