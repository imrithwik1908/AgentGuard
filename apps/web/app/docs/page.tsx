import Link from "next/link";

const install = `python -m pip install "agentguard-reliability @ git+https://github.com/imrithwik1908/AgentGuard.git#subdirectory=packages/python-sdk"`;

const sdkExample = `import os

from agentguard import AgentGuard
from agentguard.integrations.openai import instrument_openai
from openai import OpenAI

ag = AgentGuard(
    base_url="https://your-agentguard-api.example.com",
    project="support-agent",
    version="candidate-v2",
    api_key=os.environ["AGENTGUARD_API_KEY"],
)

llm = instrument_openai(OpenAI(), agentguard=ag)

@ag.trace_run("answer-question", input_arg="question")
def answer(question: str) -> str:
    with ag.retrieval("retrieve-policy", query={"question": question}) as span:
        docs = retrieve(question)
        span.set_output({"documents": [{"id": doc.id, "score": doc.score} for doc in docs]})

    response = llm.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "Answer only from the supplied policy context."},
            {"role": "user", "content": question},
        ],
    )
    return response.choices[0].message.content`;

const publish = `cd packages/python-sdk
rm -rf dist build *.egg-info
python -m pip install -U build twine
python -m build
python -m twine check dist/*

TWINE_USERNAME=__token__ \\
TWINE_PASSWORD="pypi-your-token" \\
python -m twine upload dist/*`;

export default function DocsPage() {
  return (
    <div className="space-y-10">
      <section className="border-b border-slate-200 pb-8">
        <div className="text-xs font-medium uppercase tracking-[0.22em] text-cyan-700">
          Documentation
        </div>
        <div className="mt-4 grid gap-8 lg:grid-cols-[minmax(0,1fr)_320px]">
          <div>
            <h1 className="max-w-4xl text-4xl font-semibold tracking-normal text-ink-950">
              Build confidence in AI application changes.
            </h1>
            <p className="mt-4 max-w-3xl text-base leading-7 text-slate-600">
              AgentGuard records how an AI application runs, evaluates behavior across versions,
              surfaces regressions, and gives teams evidence for release decisions.
            </p>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-white/80 p-4">
            <div className="text-sm font-semibold text-ink-950">Install the SDK today</div>
            <code className="mt-3 block rounded-xl bg-slate-950 p-3 text-xs text-slate-100">
              {install}
            </code>
            <p className="mt-3 text-sm leading-5 text-slate-600">
              PyPI release is prepared but not published yet. Install directly from GitHub for now.
              Distribution name: <strong>agentguard-reliability</strong>. Import name:{" "}
              <strong>agentguard</strong>.
            </p>
          </div>
        </div>
      </section>

      <section className="grid gap-8 lg:grid-cols-[240px_minmax(0,1fr)]">
        <nav className="hidden lg:block">
          <div className="sticky top-28 space-y-2 text-sm">
            {[
              ["Quickstart", "#quickstart"],
              ["Workflow", "#workflow"],
              ["SDK", "#sdk"],
              ["Web app", "#web-app"],
              ["Reference", "#reference"],
              ["Publishing", "#publishing"]
            ].map(([label, href]) => (
              <a key={href} className="block rounded-full px-3 py-2 text-slate-600 hover:bg-white hover:text-ink-950" href={href}>
                {label}
              </a>
            ))}
          </div>
        </nav>

        <div className="space-y-12">
          <DocSection
            id="quickstart"
            eyebrow="Start here"
            title="First successful integration"
            body="Create a project and version in Setup, install the SDK, wrap one AI request, then open Runs to verify telemetry arrived."
          >
            <CodeBlock code={sdkExample} />
          </DocSection>

          <DocSection
            id="workflow"
            eyebrow="Product model"
            title="Instrument → Test → Evaluate → Investigate → Release"
            body="Every page maps back to the same release workflow. Users should not need to understand trace databases before they can decide whether a candidate is safe."
          >
            <div className="grid gap-3 md:grid-cols-5">
              <Flow title="Instrument" body="SDK records runs and steps." />
              <Flow title="Test" body="Suites define expected behavior." />
              <Flow title="Evaluate" body="Checks turn runs into evidence." />
              <Flow title="Investigate" body="Failures open run details." />
              <Flow title="Release" body="Paired cases drive ship/block." />
            </div>
          </DocSection>

          <DocSection
            id="sdk"
            eyebrow="SDK reference"
            title="Python instrumentation"
            body="Start with the run decorator and provider integration. Add retrieval or tool helpers where AgentGuard needs evidence, and use manual trace/span contexts only for custom operations."
          >
            <ReferenceGrid
              items={[
                ["AgentGuard(...)", "Creates a client bound to one project and version."],
                ["@ag.trace_run(...)", "Automatically records one complete synchronous or async application execution."],
                ["instrument_openai(...)", "Automatically records OpenAI-compatible chat completion calls, models, timing, errors, and token usage."],
                ["ag.retrieval(...)", "Records retrieved document IDs, scores, and related evidence."],
                ["ag.tool(...)", "Records tool names, arguments, outputs, timing, and exceptions."],
                ["ag.trace(...) / trace.span(...)", "Low-level contexts for operations not covered by a helper."],
                ["span.set_output(...)", "Stores step output for later investigation."],
                ["raise_on_failure", "Defaults false so telemetry problems do not crash user apps."]
              ]}
            />
          </DocSection>

          <DocSection
            id="web-app"
            eyebrow="Control plane"
            title="How to use the website"
            body="The web app is where users set up projects, define test suites, compare versions, inspect failed runs, and decide whether to release."
          >
            <ReferenceGrid
              items={[
                ["Overview", "Current candidate status and one recommended next action."],
                ["Test Suites", "Behavioral cases your AI app should keep passing."],
                ["Releases", "Baseline-vs-candidate comparison and release decision."],
                ["Runs", "Debugging surface for one execution."],
                ["Setup", "Projects and versions."],
                ["Docs", "SDK, concepts, references, and publishing guidance."]
              ]}
            />
          </DocSection>

          <DocSection
            id="reference"
            eyebrow="Repository docs"
            title="Full documentation set"
            body="The repo docs are organized as tutorials, how-to guides, reference, and explanation so users can either learn the product or quickly look up exact details."
          >
            <div className="grid gap-3 md:grid-cols-2">
              <DocLink title="Getting Started" href="https://github.com/imrithwik1908/AgentGuard/tree/main/docs/getting-started.md" />
              <DocLink title="Core Concepts" href="https://github.com/imrithwik1908/AgentGuard/tree/main/docs/concepts.md" />
              <DocLink title="Python SDK" href="https://github.com/imrithwik1908/AgentGuard/tree/main/docs/sdk.md" />
              <DocLink title="API Reference" href="https://github.com/imrithwik1908/AgentGuard/tree/main/docs/api-reference.md" />
              <DocLink title="Configuration" href="https://github.com/imrithwik1908/AgentGuard/tree/main/docs/configuration.md" />
              <DocLink title="Troubleshooting" href="https://github.com/imrithwik1908/AgentGuard/tree/main/docs/troubleshooting.md" />
            </div>
          </DocSection>

          <DocSection
            id="publishing"
            eyebrow="PyPI"
            title="Publish the SDK"
            body="PyPI publishing requires a PyPI account token. Build and validate the package first, then upload with twine."
          >
            <CodeBlock code={publish} />
          </DocSection>
        </div>
      </section>
    </div>
  );
}

function DocSection({
  id,
  eyebrow,
  title,
  body,
  children
}: {
  id: string;
  eyebrow: string;
  title: string;
  body: string;
  children: React.ReactNode;
}) {
  return (
    <section id={id} className="scroll-mt-28 border-b border-slate-200 pb-10 last:border-b-0">
      <div className="text-xs font-medium uppercase tracking-[0.2em] text-cyan-700">{eyebrow}</div>
      <h2 className="mt-2 text-2xl font-semibold text-ink-950">{title}</h2>
      <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">{body}</p>
      <div className="mt-5">{children}</div>
    </section>
  );
}

function CodeBlock({ code }: { code: string }) {
  return (
    <pre className="overflow-x-auto rounded-2xl bg-slate-950 p-4 text-xs leading-6 text-slate-100">
      {code}
    </pre>
  );
}

function Flow({ title, body }: { title: string; body: string }) {
  return (
    <div className="border-l-2 border-cyan-500 py-1 pl-3">
      <div className="text-sm font-semibold text-ink-950">{title}</div>
      <div className="mt-1 text-sm leading-5 text-slate-600">{body}</div>
    </div>
  );
}

function ReferenceGrid({ items }: { items: [string, string][] }) {
  return (
    <div className="grid gap-x-6 gap-y-4 md:grid-cols-2">
      {items.map(([term, description]) => (
        <div key={term}>
          <div className="font-mono text-sm font-semibold text-ink-950">{term}</div>
          <div className="mt-1 text-sm leading-5 text-slate-600">{description}</div>
        </div>
      ))}
    </div>
  );
}

function DocLink({ title, href }: { title: string; href: string }) {
  return (
    <a className="rounded-xl border border-slate-200 bg-white/70 px-4 py-3 text-sm font-medium text-ink-950 hover:border-cyan-400" href={href}>
      {title}
    </a>
  );
}
