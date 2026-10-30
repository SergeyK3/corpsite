import {render,screen,fireEvent,waitFor,cleanup} from "@testing-library/react";
import {afterEach,it,expect,vi} from "vitest";
import {apiFetchJson} from "@/lib/api";
import {programKindOptions} from "./educationProgramKinds";
import PprCardVersionedSectionEditor from "../_components/PprCardVersionedSectionEditor";
import ProgramKindsPage from "../../education-program-kinds/page";
vi.mock("@/lib/api",()=>({apiFetchJson:vi.fn()}));
vi.mock("./pprQueryApi.client",()=>({createPprCardRecord:vi.fn(),supersedePprCardRecord:vi.fn(),voidPprCardRecord:vi.fn()}));
afterEach(()=>{cleanup();vi.mocked(apiFetchJson).mockReset();});
const entry={code:"custom",name_ru:"Новая программа",name_kk:"Жаңа бағдарлама",is_active:true,revision:1,sort_order:80,usage_count:3};

it("offers newly registered kinds without a client release and keeps the saved inactive kind selectable",async()=>{
  vi.mocked(apiFetchJson).mockResolvedValue({items:[entry],total:1,schema_ready:true});
  render(<PprCardVersionedSectionEditor personId={1} section="education" active={[]} onSaved={vi.fn()}/>);
  fireEvent.click(screen.getByText("Добавить запись"));
  expect(await screen.findByRole("option",{name:"Новая программа"})).toHaveValue("custom");
  expect(programKindOptions([{...entry,is_active:false}])).toEqual([]);
  expect(programKindOptions([{...entry,is_active:false}],"custom")).toEqual([{value:"custom",label:"Новая программа (неактивно)"}]);
});

it("edits RU/KK names and deactivates by revision without deleting a used value",async()=>{
  vi.mocked(apiFetchJson).mockResolvedValue({items:[entry],total:1,schema_ready:true,can_manage:true});
  render(<ProgramKindsPage/>);
  fireEvent.click(await screen.findByText("Редактировать custom"));
  expect(screen.getByLabelText("Код")).toBeDisabled();
  fireEvent.change(screen.getByLabelText("Название RU"),{target:{value:"Исправленная программа"}});
  fireEvent.change(screen.getByLabelText("Название KK"),{target:{value:"Түзетілген бағдарлама"}});
  fireEvent.click(screen.getByLabelText("Активно"));
  fireEvent.click(screen.getByText("Сохранить"));
  await waitFor(()=>expect(apiFetchJson).toHaveBeenCalledWith("/api/ppr/education-program-kinds/custom",{method:"PATCH",body:{name_ru:"Исправленная программа",name_kk:"Түзетілген бағдарлама",sort_order:80,is_active:false,expected_revision:1}}));
  expect(vi.mocked(apiFetchJson).mock.calls.some(([,o])=>o?.method==='DELETE')).toBe(false);
});
