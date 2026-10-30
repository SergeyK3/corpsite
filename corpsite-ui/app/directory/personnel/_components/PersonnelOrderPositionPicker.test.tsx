import {cleanup,fireEvent,render,screen} from "@testing-library/react";
import {afterEach,expect,it,vi} from "vitest";
import PersonnelOrderPositionPicker from "./PersonnelOrderPositionPicker";
afterEach(cleanup);
const positions=[{id:1,name:"Архивариус"},{id:2,name:"Эксперт",name_kk:"Сарапшы"},{id:3,name:"Врач"}];
it("opens all positions rather than filtering by the current employee position",()=>{
 const onSelect=vi.fn();render(<PersonnelOrderPositionPicker label="Должность" value="Архивариус" positions={positions} loading={false} error={false} onSelect={onSelect}/>);
 fireEvent.click(screen.getByLabelText("Должность"));expect(screen.getAllByRole("option")).toHaveLength(3);
 fireEvent.click(screen.getByRole("option",{name:"Эксперт"}));expect(onSelect).toHaveBeenCalledWith(positions[1]);expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
});
it("searches Kazakh names only when an explicit search is entered",()=>{
 render(<PersonnelOrderPositionPicker label="Должность" value="Архивариус" positions={positions} loading={false} error={false} onSelect={()=>{}}/>);
 fireEvent.click(screen.getByLabelText("Должность"));fireEvent.change(screen.getByLabelText("Поиск: Должность"),{target:{value:"Сарапшы"}});expect(screen.getAllByRole("option")).toHaveLength(1);expect(screen.getByRole("option")).toHaveTextContent("Эксперт");
});
