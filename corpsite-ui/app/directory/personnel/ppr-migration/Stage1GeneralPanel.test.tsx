import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import Stage1GeneralPanel from "./Stage1GeneralPanel";

const apiFetchJson=vi.fn();
vi.mock("@/lib/api",()=>({apiFetchJson:(...args:unknown[])=>apiFetchJson(...args)}));
afterEach(()=>vi.clearAllMocks());
const draft={run:{stage1_run_id:8,stage0_cohort_run_id:4,status:"DRY_RUN_COMPLETED",current_position:1},counts:{PENDING:1},participants:[{position:1,employee_id:11,person_id:21,source_row_id:31,source_row_number:7,display_name:"Тестовый сотрудник",source:{full_name:"Тестовый сотрудник",iin:"900101000001"},current:{full_name:"Тестовый сотрудник",iin:null},proposal:{iin:"900101000001"},conflicts:[],status:"PENDING"}]};
describe("Stage1GeneralPanel",()=>{it("shows Russian draft review and masks IIN",async()=>{apiFetchJson.mockResolvedValue(draft);render(<Stage1GeneralPanel cohortRunId={4}/>);fireEvent.click(screen.getByRole("button",{name:"Проверить общие сведения"}));expect(await screen.findByText(/Статус: Проверка завершена/)).toBeInTheDocument();expect(screen.getAllByText(/90••••••••01/).length).toBeGreaterThan(0);expect(screen.getByText("Исходное → текущее → предлагается")).toBeInTheDocument();fireEvent.click(screen.getByRole("button",{name:"Утвердить запуск"}));await waitFor(()=>expect(apiFetchJson).toHaveBeenLastCalledWith("/personnel/ppr-migration/stage-1/approve",expect.anything()));});});
