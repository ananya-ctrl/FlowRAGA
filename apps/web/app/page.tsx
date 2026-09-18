import Link from "next/link";

const principles = [
  ["Open by default", "Open-weight models and portable infrastructure without a paid-provider dependency."],
  ["Observable", "Every retrieval stage will expose evidence, latency, quality, and resource usage."],
  ["Production-minded", "Security, ownership, background jobs, and tests are architectural requirements."],
];

export default function Home() {
  return (
    <main>
      <nav aria-label="Primary navigation">
        <a className="brand" href="#top" aria-label="FlowRAGA home">FlowRAGA</a>
        <div className="nav-actions">
          <Link href="/login">Sign in</Link>
          <Link className="nav-cta" href="/signup">Create account</Link>
        </div>
      </nav>

      <section id="top" className="hero">
        <p className="eyebrow">Visual RAG engineering workspace</p>
        <h1>Build retrieval systems you can actually understand.</h1>
        <p className="lede">
          Design, test, compare, and export reliable RAG pipelines using open-source models and transparent evaluation.
        </p>
        <div className="actions">
          <Link className="primary" href="/signup">Start building</Link>
          <a className="secondary" href="#principles">Engineering principles</a>
        </div>
      </section>

      <section id="principles" className="grid" aria-label="Engineering principles">
        {principles.map(([title, copy], index) => (
          <article key={title}>
            <span>0{index + 1}</span>
            <h2>{title}</h2>
            <p>{copy}</p>
          </article>
        ))}
      </section>
    </main>
  );
}
