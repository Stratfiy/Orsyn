import { messages } from "@/lib/messages";

export default function Loading() {
  return (
    <div role="status" className="rounded-card border-line border bg-white p-6">
      <span className="sr-only">{messages.loading}</span>
      <div className="bg-line h-7 w-40 animate-pulse rounded" />
      <div className="bg-line mt-4 h-4 w-64 max-w-full animate-pulse rounded" />
    </div>
  );
}
