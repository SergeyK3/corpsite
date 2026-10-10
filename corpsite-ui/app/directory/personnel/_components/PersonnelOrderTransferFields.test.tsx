import * as React from "react";
import {cleanup, fireEvent, render, screen, waitFor} from "@testing-library/react";
import {afterEach, expect, it, vi} from "vitest";
import PersonnelOrderTransferFields, {type TransferFields} from "./PersonnelOrderTransferFields";
import {getPositions} from "@/app/directory/employees/_lib/api.client";
import {apiFetchJson} from "@/lib/api";
vi.mock("@/app/directory/employees/_lib/api.client", () => ({getPositions:vi.fn()}));
vi.mock("@/lib/api", () => ({apiFetchJson:vi.fn()}));
afterEach(() => {cleanup();vi.clearAllMocks();});
const blank:TransferFields={position_ru:"",position_kk:"",org_unit_ru:"",org_unit_kk:"",rate:"",basis_ru:"",basis_kk:""};
function setup(initial=blank, jobs=[{job_nameru:"Врач",job_namekk:"Дәрігер",legacy_position_ids:[6]}], mode:"transfer"|"concurrent"="transfer") {
 vi.mocked(getPositions).mockResolvedValue({items:[{position_id:6,name:"Врач"},{position_id:61,name:"Аналитик ЭРОБ"}],total:2});
 vi.mocked(apiFetchJson).mockResolvedValue({items:jobs});
 function Form(){const [value,onChange]=React.useState(initial);return <><PersonnelOrderTransferFields value={value} onChange={onChange} mode={mode} orgUnits={[{unit_id:42,name:"Хирургия 1",name_kk:"№1 хирургия бөлімшесі",group_id:1},{unit_id:74,name:"Архив",group_id:3}]}/><output data-testid="value">{JSON.stringify(value)}</output></>;}
 return render(<Form/>);
}
async function pick(label:string,query:string,id:string) {
 const input=screen.getByRole("combobox",{name:label});fireEvent.focus(input);fireEvent.change(input,{target:{value:query}});
 await waitFor(() => expect(document.querySelector(`button[data-record-id="${id}"]`)).not.toBeNull());
 fireEvent.click(document.querySelector(`button[data-record-id="${id}"]`)!);
}
it.each(["RU","KK"])("links position and unit names by ID from %s", async locale => {
 setup();await pick(`Новая должность (${locale})`,locale==="RU"?"вра":"дәр","6");
 expect(screen.getByLabelText("Новая должность (RU)")).toHaveValue("Врач");expect(screen.getByLabelText("Новая должность (KK)")).toHaveValue("Дәрігер");
 await pick(`Новое подразделение (${locale})`,locale==="RU"?"хир":"хирургия","42");
 expect(screen.getByLabelText("Новое подразделение (RU)")).toHaveValue("Хирургия 1");expect(screen.getByLabelText("Новое подразделение (KK)")).toHaveValue("№1 хирургия бөлімшесі");
 expect(JSON.parse(screen.getByTestId("value").textContent!)).toMatchObject({position_id:6,org_unit_id:42});
});
it("leaves missing KK empty, accepts manual translation and preserves it when the same RU record is chosen",async()=>{
 setup();await pick("Новая должность (RU)","аналитик","61");expect(screen.getByLabelText("Новая должность (KK)")).toHaveValue("");
 fireEvent.change(screen.getByLabelText("Новая должность (KK)"),{target:{value:"ЭРОБ талдаушысы"}});fireEvent.blur(screen.getByLabelText("Новая должность (KK)"));
 await pick("Новая должность (RU)","аналитик","61");expect(screen.getByLabelText("Новая должность (RU)")).toHaveValue("Аналитик ЭРОБ");expect(screen.getByLabelText("Новая должность (KK)")).toHaveValue("ЭРОБ талдаушысы");
 await pick("Новая должность (KK)","61","61");expect(screen.getByLabelText("Новая должность (KK)")).toHaveValue("ЭРОБ талдаушысы");
 fireEvent.blur(screen.getByLabelText("Новая должность (KK)"));fireEvent.click(screen.getByRole("button",{name:"Открыть список: Новая должность (KK)"}));fireEvent.click(document.querySelector('button[data-record-id="61"]')!);expect(screen.getByLabelText("Новая должность (KK)")).toHaveValue("ЭРОБ талдаушысы");
 await pick("Новое подразделение (RU)","архив","74");expect(screen.getByLabelText("Новое подразделение (KK)")).toHaveValue("");
});
it("uses the existing bilingual basis generator without labels, punctuation or attached documents",async()=>{
 setup();await pick("Основание перевода (KK)","қызметтік","MEMO");
 expect(screen.getByLabelText("Основание перевода (RU)")).toHaveValue("служебная записка");expect(screen.getByLabelText("Основание перевода (KK)")).toHaveValue("қызметтік жазба");
 fireEvent.change(screen.getByLabelText("Основание перевода (KK)"),{target:{value:"қызметтік жазба №7"}});fireEvent.blur(screen.getByLabelText("Основание перевода (KK)"));
 await pick("Основание перевода (RU)","служебная","MEMO");expect(screen.getByLabelText("Основание перевода (KK)")).toHaveValue("қызметтік жазба №7");
 expect(JSON.parse(screen.getByTestId("value").textContent!)).not.toHaveProperty("basis_ids");
});
it("does not overwrite manual input after a late dictionary response",async()=>{
 setup({...blank,position_ru:"Ручная должность",position_kk:"Қолмен енгізілген лауазым",basis_ru:"Моё основание"});
 await waitFor(()=>expect(screen.queryByText("Загружается справочник должностей…")).not.toBeInTheDocument());
 expect(screen.getByLabelText("Новая должность (RU)")).toHaveValue("Ручная должность");expect(screen.getByLabelText("Новая должность (KK)")).toHaveValue("Қолмен енгізілген лауазым");expect(screen.getByLabelText("Основание перевода (RU)")).toHaveValue("Моё основание");
});

it("searches legacy names while filling the linked approved title", async () => {
 setup(blank,[{job_nameru:"Врач-статистик",job_namekk:"Дәрігер-статистик",legacy_position_ids:[61]}]);
 await pick("Новая должность (RU)","аналитик","61");
 expect(screen.getByLabelText("Новая должность (RU)")).toHaveValue("Врач-статистик");expect(screen.getByLabelText("Новая должность (KK)")).toHaveValue("Дәрігер-статистик");
});

it("uses additional placement for concurrency and clears outdated grammatical forms on a new ID", async () => {
 setup({...blank,position_id:6,position_genitive_ru:"врача",org_unit_genitive_ru:"отделения терапии"},undefined,"concurrent");
 expect(screen.getByLabelText("Дополнительная ставка")).toBeInTheDocument();expect(screen.getByLabelText("Общая ставка")).toBeInTheDocument();
 await pick("Дополнительная должность (RU)","аналитик","61");expect(screen.getByLabelText("Дополнительная должность в родительном падеже (RU)")).toHaveValue("");
 expect(screen.getByLabelText("Дополнительное подразделение в родительном падеже (RU)")).toHaveValue("отделения терапии");
 expect(screen.queryByLabelText("Новая должность (RU)")).not.toBeInTheDocument();
});
