import { messages } from "@/lib/messages";
import { SIDE_PANEL_ID } from "./SidePanel";

type Props = { drawerOpen: boolean; onOpenDrawer: () => void };

export function TopBar({ drawerOpen, onOpenDrawer }: Props) {
  return (
    <header className="border-line flex min-h-14 items-center gap-2 rounded-xl border bg-white px-2 md:px-4">
      <button
        type="button"
        onClick={onOpenDrawer}
        aria-label={messages.openMenu}
        aria-expanded={drawerOpen}
        aria-controls={SIDE_PANEL_ID}
        className="text-ink-2 flex size-11 items-center justify-center rounded-md md:hidden"
      >
        <svg
          width="20"
          height="20"
          viewBox="0 0 20 20"
          fill="none"
          aria-hidden="true"
        >
          <path
            d="M3 5h14M3 10h14M3 15h14"
            stroke="currentColor"
            strokeWidth="1.75"
          />
        </svg>
      </button>
      <span className="font-heading text-lg font-semibold">
        {messages.product}
      </span>
    </header>
  );
}
