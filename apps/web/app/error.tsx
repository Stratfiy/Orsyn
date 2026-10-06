"use client";

import { messages } from "@/lib/messages";

export default function ErrorPage({
  reset,
}: {
  error: Error;
  reset: () => void;
}) {
  return (
    <section
      role="alert"
      className="rounded-card border-line border bg-white p-6"
    >
      <h1 className="text-bad text-2xl font-semibold">{messages.errorTitle}</h1>
      <p className="text-ink-2 mt-2">{messages.errorLine}</p>
      <button
        type="button"
        onClick={reset}
        className="bg-accent mt-4 min-h-11 rounded-md px-4 font-medium text-white"
      >
        {messages.retry}
      </button>
    </section>
  );
}
