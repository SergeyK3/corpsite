import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import UserCreateDrawer from "./UserCreateDrawer";

const formSpy = vi.fn();

vi.mock("./UserCreateForm", () => ({
  default: (props: Record<string, unknown>) => {
    formSpy(props);
    return (
      <div data-testid="user-create-form">
        {props.initialOrgGroupId != null ? `group:${props.initialOrgGroupId}` : "group:none"}
        {props.initialOrgUnitId != null ? ` unit:${props.initialOrgUnitId}` : " unit:none"}
      </div>
    );
  },
}));

describe("UserCreateDrawer OPS-029 wiring", () => {
  afterEach(() => {
    cleanup();
    formSpy.mockClear();
  });

  it("forwards org scope props to UserCreateForm", () => {
    render(
      <UserCreateDrawer
        open
        fullName="Козгамбаева Ляззат"
        initialOrgGroupId={2}
        initialOrgUnitId={44}
        initialValues={{
          login: "kozgambaeva.lt",
          password: "",
          role_id: "",
          org_unit_id: "44",
          is_active: true,
        }}
        onClose={() => {}}
        onSubmit={() => {}}
      />,
    );

    expect(screen.getByTestId("user-create-form")).toHaveTextContent("group:2 unit:44");
    expect(formSpy).toHaveBeenCalledWith(
      expect.objectContaining({
        fullName: "Козгамбаева Ляззат",
        initialOrgGroupId: 2,
        initialOrgUnitId: 44,
      }),
    );
    expect(formSpy.mock.calls[0]?.[0]).not.toHaveProperty("orgUnitLabel");
    expect(formSpy.mock.calls[0]?.[0]).not.toHaveProperty("roleOptions");
  });

  it("renders nothing when closed", () => {
    render(
      <UserCreateDrawer
        open={false}
        fullName="Test"
        initialValues={{
          login: "",
          password: "",
          role_id: "",
          org_unit_id: "",
          is_active: true,
        }}
        onClose={() => {}}
        onSubmit={() => {}}
      />,
    );

    expect(screen.queryByTestId("user-create-form")).not.toBeInTheDocument();
    expect(formSpy).not.toHaveBeenCalled();
  });
});
