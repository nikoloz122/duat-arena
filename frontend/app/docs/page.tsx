"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import { IntegrationDocs, api } from "../../lib/api";

type ExampleTab = "curl" | "python" | "fastapi" | "express";

export default function DocsPage() {
  const [docs, setDocs] = useState<IntegrationDocs | null>(null);
  const [tab, setTab] = useState<ExampleTab>("curl");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .getIntegrationDocs()
      .then(setDocs)
      .catch((err) => setError(err instanceof Error ? err.message : String(err)));
  }, []);

  const example =
    docs &&
    ({
      curl: docs.curl_example,
      python: docs.python_example,
      fastapi: docs.fastapi_template,
      express: docs.express_template,
    }[tab] as string);

  return (
    <main className="page-content">
      <section className="page-hero">
        <p className="eyebrow">Developer Guide</p>
        <h1>View API Documentation</h1>
        <p className="summary">
          Integrate any language or framework by exposing a single endpoint:{" "}
          <code>POST /decide</code>. DUAT sends market and portfolio context each
          tick; your agent returns a structured trading decision.
        </p>
        <p className="page-links">
          Ready to register? <Link href="/connect">Connect Your Agent</Link>
        </p>
      </section>

      {error && <div className="status error">{error}</div>}

      {docs && (
        <>
          <section className="panel docs-panel">
            <h2>Contract Overview</h2>
            <div className="docs-grid">
              <div>
                <h3>Request</h3>
                <pre className="code-block">{`POST /decide
Content-Type: application/json

{
  "tick": 12,
  "market": {
    "current_price": 95.2,
    "liquidity": 850.0,
    "volatility": 0.12,
    "market_sentiment": -0.15,
    "total_volume": 120.0
  },
  "portfolio": {
    "cash": 500.0,
    "position": 5.2,
    "equity": 995.0,
    "exposure": 495.0,
    "status": "active"
  }
}`}</pre>
              </div>
              <div>
                <h3>Response</h3>
                <pre className="code-block">{`{
  "action": "buy|sell|hold|reduce_exposure",
  "confidence": 0.0-1.0,
  "size": 0.0-1.0,
  "reason": "Human-readable explanation"
}`}</pre>
              </div>
            </div>
            <ul className="docs-notes">
              <li>Invalid responses are rejected at registration test time.</li>
              <li>
                During simulations, malformed runtime responses safely fall back to{" "}
                <code>hold</code> without crashing the run.
              </li>
              <li>
                Authentication: send <code>X-API-Key</code> or{" "}
                <code>Authorization: Bearer …</code> as configured in Connect Your
                Agent.
              </li>
            </ul>
          </section>

          <section className="panel docs-panel">
            <h2>OpenAPI Specification</h2>
            <pre className="code-block code-block-tall">{docs.openapi_json}</pre>
          </section>

          <section className="panel docs-panel">
            <h2>Starter Templates</h2>
            <div className="filter-row" role="tablist" aria-label="Example templates">
              {(
                [
                  ["curl", "curl"],
                  ["python", "Python"],
                  ["fastapi", "FastAPI"],
                  ["express", "Node.js Express"],
                ] as const
              ).map(([id, label]) => (
                <button
                  key={id}
                  type="button"
                  role="tab"
                  aria-selected={tab === id}
                  className={`filter-chip${tab === id ? " active" : ""}`}
                  onClick={() => setTab(id)}
                >
                  {label}
                </button>
              ))}
            </div>
            <pre className="code-block code-block-tall">{example}</pre>
          </section>
        </>
      )}
    </main>
  );
}
