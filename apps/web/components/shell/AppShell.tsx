"use client";

import { useEffect, useState } from "react";
import { SidePanel } from "./SidePanel";
import { TopBar } from "./TopBar";

const STORAGE_KEY = "orsyn.sidePanelCollapsed";

export function AppShell({ children }: { children: React.ReactNode }) {
  const [collapsed, setCollapsed] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);

  useEffect(() => {
    try {
      setCollapsed(localStorage.getItem(STORAGE_KEY) === "1");
    } catch {
      // storage blocked: keep the default
    }
  }, []);

  useEffect(() => {
    if (!drawerOpen) return;
    const onKey = (e: KeyboardEvent) =>
      e.key === "Escape" && setDrawerOpen(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [drawerOpen]);

  const toggleCollapsed = () => {
    const next = !collapsed;
    setCollapsed(next);
    try {
      localStorage.setItem(STORAGE_KEY, next ? "1" : "0");
    } catch {
      // storage blocked: state lasts for this visit only
    }
  };

  return (
    <div className="flex min-h-screen gap-3 p-3">
      <SidePanel
        collapsed={collapsed}
        drawerOpen={drawerOpen}
        onToggleCollapsed={toggleCollapsed}
        onCloseDrawer={() => setDrawerOpen(false)}
      />
      <div className="flex min-w-0 flex-1 flex-col gap-3">
        <TopBar
          drawerOpen={drawerOpen}
          onOpenDrawer={() => setDrawerOpen(true)}
        />
        <main className="min-w-0 flex-1">{children}</main>
      </div>
    </div>
  );
}
