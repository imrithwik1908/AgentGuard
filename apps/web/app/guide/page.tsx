import Link from "next/link";

export default function GuidePage() {
  return (
    <div className="space-y-8">
      <section className="surface rounded-[2rem] p-6">
        <div className="text-xs font-medium uppercase tracking-[0.22em] text-cyan-700">
          Product guide
        </div>
        <h1 className="mt-3 text-3xl font-semibold text-ink-950">How to use AgentGuard</h1>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
          AgentGuard is for AI app changes: prompts, models, retrieval logic, tools, or
          orchestration. It records what happened, evaluates expected behavior, shows regressions
          first, and helps you decide whether a candidate version is safe to ship.
        </p>
      </section>

      <section className="grid gap-4 lg:grid-cols-3">
        <Step
          title="1. Connect the app"
          body="Install the Python SDK in an app or run the demo agent. AgentGuard records each execution as a run with internal steps for debugging."
        />
        <Step
          title="2. Define expectations"
          body="Create a test suite with questions and expected answer signals. Run cases against a version to generate checks."
        />
        <Step
          title="3. Decide on release"
          body="Compare baseline and candidate versions. The release workflow reports pass rate, score movement, regressions, and a decision."
        />
      </section>

      <section className="surface rounded-[2rem] p-6">
        <h2 className="text-lg font-semibold text-ink-950">SDK quickstart</h2>
        <pre className="mt-4 rounded-2xl bg-ink-950 p-4 text-xs leading-6 text-slate-100">
{`from agentguard import AgentGuard

client = AgentGuard(
    base_url="https://your-agentguard-api.example.com",
    project="research-agent",
    version="v1",
    api_key="ag_..."  # optional unless auth is enabled
)

with client.trace("answer-question", input={"question": question}) as trace:
    with trace.span("retrieve", type="RETRIEVER") as span:
        span.set_output({"documents": docs})
    with trace.span("generate", type="LLM") as span:
        span.set_output({"answer": answer})
    trace.set_output({"answer": answer})`}
        </pre>
      </section>

      <section className="surface rounded-[2rem] p-6">
        <h2 className="text-lg font-semibold text-ink-950">What is real today?</h2>
        <ul className="mt-3 space-y-2 text-sm text-slate-700">
          <li>Run ingestion, storage, hierarchy, timing waterfall, and SDK instrumentation are real.</li>
          <li>Test suites, deterministic evaluators, release decisions, and CI gate APIs are real.</li>
          <li>Provider integrations are configurable records; live external judge calls need real secrets and adapter policy.</li>
          <li>No billing, marketplace, or enterprise admin layer is claimed.</li>
        </ul>
        <div className="mt-5 flex flex-wrap gap-3">
          <Link className="rounded-full bg-ink-900 px-4 py-2 text-sm font-medium text-white" href="/datasets">
            Run test suites
          </Link>
          <Link className="rounded-full border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700" href="/evaluations">
            Review releases
          </Link>
        </div>
      </section>
    </div>
  );
}

function Step({ title, body }: { title: string; body: string }) {
  return (
    <div className="surface rounded-[2rem] p-5">
      <h2 className="text-lg font-semibold text-ink-950">{title}</h2>
      <p className="mt-3 text-sm leading-6 text-slate-600">{body}</p>
    </div>
  );
}
