import Link from "next/link";
import { messages } from "@/lib/messages";

export default function NotFound() {
  return (
    <section className="rounded-card border-line border bg-white p-6">
      <h1 className="text-2xl font-semibold">{messages.notFoundTitle}</h1>
      <p className="text-ink-2 mt-2">{messages.notFoundLine}</p>
      <Link
        href="/"
        className="text-accent mt-4 inline-flex min-h-11 items-center underline"
      >
        {messages.backHome}
      </Link>
    </section>
  );
}
