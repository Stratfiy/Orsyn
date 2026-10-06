import Link from "next/link";
import { messages } from "@/lib/messages";

export const SIDE_PANEL_ID = "side-panel";

type Props = {
  collapsed: boolean;
  drawerOpen: boolean;
  onToggleCollapsed: () => void;
  onCloseDrawer: () => void;
};

const btn = "text-ink-2 flex size-11 items-center justify-center rounded-md";

export function SidePanel({
  collapsed,
  drawerOpen,
  onToggleCollapsed,
  onCloseDrawer,
}: Props) {
  return (
    <>
      {drawerOpen && (
        <div
          aria-hidden="true"
          onClick={onCloseDrawer}
          className="fixed inset-0 z-20 bg-black/30 md:hidden"
        />
      )}
      <aside
        id={SIDE_PANEL_ID}
        data-collapsed={collapsed}
        className={`border-line fixed inset-y-3 left-3 z-30 flex w-64 flex-col gap-2 rounded-xl border bg-white p-2 transition-transform md:static md:z-auto md:translate-x-0 md:transition-none ${
          collapsed ? "md:w-[60px]" : "md:w-56"
        } ${drawerOpen ? "" : "invisible -translate-x-[110%] md:visible"}`}
      >
        <div className="flex justify-end">
          <button
            type="button"
            onClick={onCloseDrawer}
            aria-label={messages.closeMenu}
            className={`${btn} md:hidden`}
          >
            <svg
              width="20"
              height="20"
              viewBox="0 0 20 20"
              fill="none"
              aria-hidden="true"
            >
              <path
                d="M5 5l10 10M15 5L5 15"
                stroke="currentColor"
                strokeWidth="1.75"
              />
            </svg>
          </button>
          <button
            type="button"
            onClick={onToggleCollapsed}
            aria-label={collapsed ? messages.expand : messages.collapse}
            aria-expanded={!collapsed}
            aria-controls={SIDE_PANEL_ID}
            className={`${btn} max-md:hidden`}
          >
            <svg
              width="20"
              height="20"
              viewBox="0 0 20 20"
              fill="none"
              aria-hidden="true"
            >
              <rect
                x="3"
                y="4"
                width="14"
                height="12"
                rx="2"
                stroke="currentColor"
                strokeWidth="1.5"
              />
              <path d="M8 4v12" stroke="currentColor" strokeWidth="1.5" />
            </svg>
          </button>
        </div>
        <nav aria-label={messages.navLabel}>
          <Link
            href="/"
            aria-current="page"
            className="text-accent flex min-h-11 items-center gap-3 rounded-md px-3 font-medium"
          >
            <svg
              width="20"
              height="20"
              viewBox="0 0 20 20"
              fill="none"
              aria-hidden="true"
              className="shrink-0"
            >
              <path
                d="M3 9l7-6 7 6v8H3z"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinejoin="round"
              />
            </svg>
            <span className={collapsed ? "md:sr-only" : ""}>
              {messages.home}
            </span>
          </Link>
        </nav>
      </aside>
    </>
  );
}
