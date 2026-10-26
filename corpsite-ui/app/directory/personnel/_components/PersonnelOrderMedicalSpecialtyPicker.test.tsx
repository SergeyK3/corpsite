import * as React from "react";
import {afterEach,expect,it,vi} from "vitest";
import {cleanup,fireEvent,render,screen,waitFor} from "@testing-library/react";
import Picker,{type MedicalSpecialtySnapshot} from "./PersonnelOrderMedicalSpecialtyPicker";
import {apiFetchJson} from "@/lib/api";
import {buildItemPayload,emptyItemPayloadDraft,itemPayloadDraftFromRecord} from "../_lib/personnelOrderPayload";
vi.mock("@/lib/api",()=>({apiFetchJson:vi.fn()}));
afterEach(()=>{cleanup();vi.clearAllMocks();});
const snapshot:MedicalSpecialtySnapshot={medical_specialty_id:57,name_ru:"Акушерство и гинекология",name_kk:"Акушерия және гинекология"};
it("searches active RU/KK and allows replacement and explicit clearing",async()=>{
 vi.mocked(apiFetchJson).mockResolvedValue({items:[{medical_specialty_id:57,name:snapshot.name_ru,name_kk:snapshot.name_kk,is_active:true},{medical_specialty_id:1,name:"Врач-акушер-гинеколог",name_kk:"Старое",is_active:false}],total:2});
 function Harness(){const [value,setValue]=React.useState<MedicalSpecialtySnapshot|null>(null);return <Picker value={value} onChange={setValue}/>;}
 render(<Harness/>);await waitFor(()=>expect(screen.queryByText("Загружаются специальности…")).not.toBeInTheDocument());
 fireEvent.change(screen.getByLabelText("Медицинская специальность (необязательно)"),{target:{value:"Акушерия"}});fireEvent.click(await screen.findByRole("option"));expect(screen.getByLabelText("Медицинская специальность (необязательно)")).toHaveValue(`${snapshot.name_ru} / ${snapshot.name_kk}`);expect(screen.queryByText(/Выбрано:/)).not.toBeInTheDocument();
 fireEvent.click(screen.getByRole("button",{name:"Очистить специальность"}));expect(screen.queryByText(/Выбрано:/)).not.toBeInTheDocument();
 fireEvent.change(screen.getByLabelText("Медицинская специальность (необязательно)"),{target:{value:"Врач"}});expect(screen.queryByRole("option")).not.toBeInTheDocument();
});

it('shows a saved snapshot immediately, preserves it when search is abandoned, and replaces or clears it after reopening',async()=>{
 const second={medical_specialty_id:58,name_ru:'Терапия',name_kk:'Терапия'};
 vi.mocked(apiFetchJson).mockResolvedValue({items:[{medical_specialty_id:57,name:snapshot.name_ru,name_kk:snapshot.name_kk,is_active:true},{medical_specialty_id:58,name:second.name_ru,name_kk:second.name_kk,is_active:true}],total:2});
 let saved:MedicalSpecialtySnapshot|null=snapshot;
 function Harness(){const[value,setValue]=React.useState(saved);return <><Picker value={value} onChange={setValue}/><button onClick={()=>{saved=JSON.parse(JSON.stringify(value));}}>TEST save</button></>;}
 let view=render(<Harness/>);
 const label='Медицинская специальность (необязательно)';
 expect(screen.getByRole('combobox',{name:label})).toHaveValue(`${snapshot.name_ru} / ${snapshot.name_kk}`);
 expect(screen.queryByText(/Выбрано:/)).not.toBeInTheDocument();
 await waitFor(()=>expect(screen.queryByText('Загружаются специальности…')).not.toBeInTheDocument());
 fireEvent.focus(screen.getByLabelText(label));fireEvent.change(screen.getByLabelText(label),{target:{value:'unknown'}});fireEvent.blur(screen.getByLabelText(label));
 expect(screen.getByLabelText(label)).toHaveValue(`${snapshot.name_ru} / ${snapshot.name_kk}`);
 fireEvent.focus(screen.getByLabelText(label));fireEvent.change(screen.getByLabelText(label),{target:{value:'Терапия'}});
 fireEvent.click(screen.getByRole('option',{name:'Терапия / Терапия'}));
 expect(screen.getByLabelText(label)).toHaveValue('Терапия / Терапия');
 fireEvent.click(screen.getByRole('button',{name:'TEST save'}));view.unmount();view=render(<Harness/>);
 expect(screen.getByLabelText(label)).toHaveValue('Терапия / Терапия');
 fireEvent.click(screen.getByRole('button',{name:'Очистить специальность'}));
 expect(screen.getByLabelText(label)).toHaveValue('');
 fireEvent.click(screen.getByRole('button',{name:'TEST save'}));view.unmount();render(<Harness/>);
 expect(screen.getByLabelText(label)).toHaveValue('');expect(saved).toBeNull();
});
it.each(["TRANSFER","CONCURRENT_DUTY_START"])("round-trips %s independently of position and preserves explicit clearing",kind=>{
 const plain=buildItemPayload(kind,emptyItemPayloadDraft());expect(plain).not.toHaveProperty("medical_specialty");
 const saved=buildItemPayload(kind,{...emptyItemPayloadDraft(),medical_specialty:snapshot});
 expect(itemPayloadDraftFromRecord(saved).medical_specialty).toEqual(snapshot);
 expect(buildItemPayload(kind,itemPayloadDraftFromRecord(saved)).medical_specialty).toEqual(snapshot);
 expect(buildItemPayload(kind,{...itemPayloadDraftFromRecord(saved),medical_specialty:null}).medical_specialty).toBeNull();
 expect(saved).not.toHaveProperty("medical_specialty_id");
});
it("shows retry on dictionary failure without making the field required",async()=>{
 vi.mocked(apiFetchJson).mockRejectedValue(new Error("Unavailable"));render(<Picker onChange={vi.fn()}/>);expect(await screen.findByRole("alert")).toHaveTextContent("оставить поле пустым");expect(screen.getByRole("button",{name:"Повторить загрузку"})).toBeInTheDocument();
});
