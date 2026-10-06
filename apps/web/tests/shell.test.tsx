import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { AppShell } from "@/components/shell/AppShell";

describe("AppShell", () => {
  it("renders nav with label Main", () => {
    render(
      <AppShell>
        <div>Content</div>
      </AppShell>,
    );

    const nav = screen.getByRole("navigation", { name: "Main" });
    expect(nav).toBeInTheDocument();
  });

  it("renders Home link in nav", () => {
    render(
      <AppShell>
        <div>Content</div>
      </AppShell>,
    );

    const homeLink = screen.getByRole("link", { name: "Home" });
    expect(homeLink).toBeInTheDocument();
    expect(homeLink).toHaveAttribute("href", "/");
  });

  it("renders header containing Orsyn", () => {
    render(
      <AppShell>
        <div>Content</div>
      </AppShell>,
    );

    const header = screen.getByRole("banner");
    expect(header).toHaveTextContent("Orsyn");
  });

  it("collapse button has aria-expanded=true initially", () => {
    render(
      <AppShell>
        <div>Content</div>
      </AppShell>,
    );

    const collapseBtn = screen.getByRole("button", {
      name: "Collapse side panel",
    });
    expect(collapseBtn).toHaveAttribute("aria-expanded", "true");
    expect(collapseBtn).toHaveAttribute("aria-controls", "side-panel");
  });

  it("clicking collapse button toggles aria-expanded and label", async () => {
    const user = userEvent.setup();
    render(
      <AppShell>
        <div>Content</div>
      </AppShell>,
    );

    const collapseBtn = screen.getByRole("button", {
      name: "Collapse side panel",
    });

    await user.click(collapseBtn);

    expect(collapseBtn).toHaveAttribute("aria-expanded", "false");
    expect(collapseBtn).toHaveAttribute("aria-label", "Expand side panel");
  });

  it("collapse button click writes to localStorage", async () => {
    const user = userEvent.setup();
    render(
      <AppShell>
        <div>Content</div>
      </AppShell>,
    );

    const collapseBtn = screen.getByRole("button", {
      name: "Collapse side panel",
    });

    await user.click(collapseBtn);

    expect(localStorage.getItem("orsyn.sidePanelCollapsed")).toBe("1");
  });

  it("expanding panel clears localStorage", async () => {
    const user = userEvent.setup();
    render(
      <AppShell>
        <div>Content</div>
      </AppShell>,
    );

    const collapseBtn = screen.getByRole("button", {
      name: "Collapse side panel",
    });

    await user.click(collapseBtn);
    expect(localStorage.getItem("orsyn.sidePanelCollapsed")).toBe("1");

    await user.click(collapseBtn);
    expect(localStorage.getItem("orsyn.sidePanelCollapsed")).toBe("0");
  });

  it("Home link remains accessible when collapsed", async () => {
    const user = userEvent.setup();
    render(
      <AppShell>
        <div>Content</div>
      </AppShell>,
    );

    const collapseBtn = screen.getByRole("button", {
      name: "Collapse side panel",
    });

    await user.click(collapseBtn);

    const homeLink = screen.getByRole("link", { name: "Home" });
    expect(homeLink).toBeInTheDocument();
    expect(homeLink).toBeVisible();
  });

  it("drawer button opens with aria-expanded=false initially", () => {
    render(
      <AppShell>
        <div>Content</div>
      </AppShell>,
    );

    const drawerBtn = screen.getByRole("button", { name: "Open menu" });
    expect(drawerBtn).toHaveAttribute("aria-expanded", "false");
  });

  it("clicking drawer button toggles aria-expanded", async () => {
    const user = userEvent.setup();
    render(
      <AppShell>
        <div>Content</div>
      </AppShell>,
    );

    const drawerBtn = screen.getByRole("button", { name: "Open menu" });

    await user.click(drawerBtn);

    expect(drawerBtn).toHaveAttribute("aria-expanded", "true");
  });

  it("pressing Escape closes drawer", async () => {
    const user = userEvent.setup();
    render(
      <AppShell>
        <div>Content</div>
      </AppShell>,
    );

    const drawerBtn = screen.getByRole("button", { name: "Open menu" });

    await user.click(drawerBtn);
    expect(drawerBtn).toHaveAttribute("aria-expanded", "true");

    await user.keyboard("{Escape}");

    expect(drawerBtn).toHaveAttribute("aria-expanded", "false");
    expect(drawerBtn).toHaveAttribute("aria-label", "Open menu");
  });
});
