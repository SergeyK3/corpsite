import * as React from "react";
import {cleanup,fireEvent,render,screen} from "@testing-library/react";
import {afterEach,expect,it} from "vitest";
import PersonnelOrderDepartmentPicker from "../_components/PersonnelOrderDepartmentPicker";
import {departmentFromPayload,departmentFromUnit,departmentSnapshot,departmentValues} from "./personnelOrderDepartment";
import {buildItemPayload,itemPayloadDraftFromRecord} from "./personnelOrderPayload";
const a={unit_id:1,name:"Отдел терапии",name_kk:"Терапия бөлімі",document_genitive_kk:"Терапия бөлімінің",group_id:1};
const b={unit_id:2,name:"Отдел хирургии",name_kk:"Хирургия бөлімі",document_genitive_kk:"Хирургия бөлімінің",group_id:99};
afterEach(cleanup);
it("changes the whole dictionary pair and clears only the previous unit's overrides",()=>{
 function Harness(){const [value,setValue]=React.useState<ReturnType<typeof departmentFromUnit>>({...departmentFromUnit(a),overrides:{genitive_kk:"OLD_UNIT"}});return <PersonnelOrderDepartmentPicker value={value} options={[a,b]} onChange={setValue}/>;}
 render(<Harness/>);
 fireEvent.change(screen.getByLabelText("Подразделение"),{target:{value:"2"}});
 expect(screen.getByTestId("department-name_ru")).toHaveTextContent(b.name);expect(screen.getByTestId("department-name_kk")).toHaveTextContent(b.name_kk);
 expect(screen.getByTestId("department-genitive_kk")).toHaveTextContent(b.document_genitive_kk);
 expect(screen.getByLabelText("Для текста KK (ілік септік) — вручную")).toHaveValue("");
 const manual=screen.getByLabelText("Для текста KK (ілік септік) — вручную");
 fireEvent.change(manual,{target:{value:"MANUAL"}});expect(screen.getByTestId("department-genitive_kk")).toHaveTextContent("MANUAL");
 fireEvent.change(manual,{target:{value:""}});expect(screen.getByTestId("department-genitive_kk")).toHaveTextContent(b.document_genitive_kk);
});
it("leaves a new nominal KK case blank instead of retaining or guessing another unit's form",()=>{
 const value={...departmentFromUnit(a),overrides:{name_kk:b.name_kk}};
 expect(departmentValues(value).genitive_kk).toBe("");
});
it("roundtrips explicit manual wording and derives all compatibility fields from one source",()=>{
 const canonical={...departmentFromUnit(b),overrides:{genitive_kk:"Ручная KK",genitive_ru:"Ручная RU"}};
 const draft=itemPayloadDraftFromRecord({document_org_unit:departmentSnapshot(canonical),allowance:{percent:35,basis_type:"RECIPIENT_BASE_SALARY",employee_dative_ru:"Тесту",employee_dative_kk:"Тестке",basis_ru:"Заявление",basis_kk:"Өтініш"},allowance_recipient:{position_ru:"Врач",position_kk:"дәрігері",org_unit_ru:"STALE",org_unit_kk:"STALE"}});
 const saved=buildItemPayload("SUPPLEMENTARY_PAY",draft);
 expect(saved.allowance_recipient).toMatchObject({org_unit_id:2,org_unit_ru:b.name,org_unit_kk:"Ручная KK",org_unit_genitive_ru:"Ручная RU"});
 expect(saved.org_unit_title_kk).toBe(b.name_kk);expect(saved.document_forms_kk).toMatchObject({org_unit_document_genitive_kk:"Ручная KK"});
 expect(departmentFromPayload(saved)).toEqual(canonical);expect(JSON.stringify(saved)).not.toContain("STALE");
});
