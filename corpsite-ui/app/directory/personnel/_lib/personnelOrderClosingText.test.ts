import {expect,it} from "vitest";
import {withoutAutomaticOrderClosing} from "./personnelOrderClosingText";
import {formatPersonnelOrderActionStartDate} from "./personnelOrderPrintFormat";
it.each(["Контроль за исполнением приказа оставляю за собой.","Бұйрықты орындалу бақылауын өзімде қалдырамын.","Бұйрықтың орындалуын бақылауды өзіме қалдырамын."])("omits the retired automatic sentence: %s",value=>expect(withoutAutomaticOrderClosing(value)).toBeNull());
it("retains other instructions when removing automatic text",()=>expect(withoutAutomaticOrderClosing("Контроль за исполнением приказа оставляю за собой. Ознакомить сотрудника с приказом.")).toBe("Ознакомить сотрудника с приказом."));
it("formats the action date without changing its stored value",()=>{const date="2026-07-03";expect(formatPersonnelOrderActionStartDate(date,"ru")).toBe("03.07.2026");expect(formatPersonnelOrderActionStartDate(date,"kk")).toBe("2026 жылғы 3 шілдеден");expect(date).toBe("2026-07-03");});
