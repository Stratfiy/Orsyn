import { messages } from "@/lib/messages";

export default function HomePage() {
  return (
    <section className="rounded-card border-line border bg-white p-6">
      <h1 className="text-2xl font-semibold">{messages.home}</h1>
      <p className="text-muted mt-2">{messages.homeLine}</p>
    </section>
  );
}
