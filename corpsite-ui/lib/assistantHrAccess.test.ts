import { describe, expect, it } from "vitest";
import { buildPersonnelSidebarNavItems, canSeePprMigrationNav, canSeeWorkingContactsNav } from "./personnelNav";
import type { MeInfo } from "./types";

describe("assistant HR migration navigation", () => {
  const assistant: MeInfo = { user_id: 1, is_sysadmin_assistant: true, role_code: "SYSADMIN_ASSISTANT" };
  it("requires the assistant's explicit Stage 0 capability", () => {
    expect(canSeePprMigrationNav(assistant)).toBe(false);
    const allowed = { ...assistant, ppr_stage_permissions: { "0": true } };
    expect(buildPersonnelSidebarNavItems(allowed).map(item => item.href)).toContain("/directory/personnel/ppr-migration");
  });
  it("preserves HR_HEAD and documentation viewer behavior", () => {
    expect(canSeePprMigrationNav({ user_id: 2, role_code: "HR_HEAD" })).toBe(true);
    expect(canSeePprMigrationNav({ user_id: 3, role_code: "DOCUMENTATION_VIEWER", is_documentation_viewer: true })).toBe(false);
  });
  it("shows working contacts only with the exact assistant read capability",()=>{
    expect(canSeeWorkingContactsNav(assistant)).toBe(false);
    const allowed={...assistant,has_working_contacts_read:true};
    expect(buildPersonnelSidebarNavItems(allowed).map(item=>item.href)).toContain("/directory/working-contacts");
    expect(canSeeWorkingContactsNav({user_id:3,is_documentation_viewer:true,has_working_contacts_read:true})).toBe(false);
    expect(canSeeWorkingContactsNav({user_id:4,role_code:"HR_HEAD"})).toBe(false);
  });
});
