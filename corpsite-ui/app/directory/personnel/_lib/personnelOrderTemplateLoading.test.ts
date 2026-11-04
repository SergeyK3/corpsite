import {afterEach,expect,it,vi} from "vitest";
import {loadTemplateWithTimeout,TEMPLATE_REQUEST_TIMEOUT_MS} from "./personnelOrderTemplateLoading";
afterEach(()=>vi.useRealTimers());
it("passes through success and rejection without leaving timers",async()=>{
 vi.useFakeTimers();
 await expect(loadTemplateWithTimeout(Promise.resolve(50))).resolves.toBe(50);
 await expect(loadTemplateWithTimeout(Promise.reject(new Error("503")))).rejects.toThrow("503");
 expect(vi.getTimerCount()).toBe(0);
});
it("turns a stalled read into a retryable timeout and ignores late success",async()=>{
 vi.useFakeTimers();let finish!:(value:number)=>void;
 const request=loadTemplateWithTimeout(new Promise<number>(resolve=>{finish=resolve;}));
 const rejected=expect(request).rejects.toThrow("Превышено время ожидания");
 await vi.advanceTimersByTimeAsync(TEMPLATE_REQUEST_TIMEOUT_MS);
 await rejected;finish(50);
 await expect(request).rejects.toThrow("Повторите загрузку");
 await expect(loadTemplateWithTimeout(Promise.resolve(50))).resolves.toBe(50);
 expect(vi.getTimerCount()).toBe(0);
});
