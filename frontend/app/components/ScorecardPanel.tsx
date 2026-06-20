import { Scorecard } from "../../lib/api";
import { agentLabel, gradeColor } from "../../lib/format";

export default function ScorecardPanel({ scorecards }: { scorecards: Scorecard[] }) {
  if (scorecards.length === 0) return null;
  const sorted = [...scorecards].sort((a, b) => (b.score ?? 0) - (a.score ?? 0));

  return (
    <section className="panel" aria-label="Strategy reliability scorecards">
      <h2>Strategy Reliability Scorecards</h2>
      <p className="caption">
        Per-bot and per-agent reliability under stress. Higher strategy reliability scores
        mean safer behavior (0–100).
      </p>

      <div className="scorecard-grid">
        {sorted.map((card) => (
          <article
            className={`scorecard${card.integrity.intervention_ticks > 0 ? " scorecard-flagged" : " scorecard-clean"}`}
            key={card.agent_id}
          >
            <div className="scorecard-head">
              <h3>{agentLabel(card.agent_id)}</h3>
            </div>

            <div className="scorecard-summary">
              <div className="score-metric">
                <span className="score-metric-label">Strategy Reliability Score</span>
                <span className="score-metric-value">{Math.round(card.score ?? 0)}/100</span>
              </div>
              <div className="score-metric">
                <span className="score-metric-label">Grade (A–F)</span>
                <span
                  className="grade-badge"
                  style={{ background: gradeColor(card.grade) }}
                >
                  {card.grade}
                </span>
              </div>
              <div className="score-metric">
                <span className="score-metric-label">Survival Status</span>
                <span className="score-metric-value score-metric-status">{card.status}</span>
              </div>
            </div>

            {card.category_order.map((key) => {
              const value = Math.max(0, Math.min(1, card.categories[key] ?? 0));
              return (
                <div className="metric-row" key={key}>
                  <div className="metric-label">
                    <span>{card.category_labels[key] ?? key}</span>
                    <span>{value.toFixed(2)}</span>
                  </div>
                  <div className="bar">
                    <div className="bar-fill" style={{ width: `${value * 100}%` }} />
                  </div>
                </div>
              );
            })}

            {card.integrity.intervention_ticks > 0 && (
              <p className="interceptions">
                <strong>Decision-boundary interceptions:</strong>{" "}
                {card.integrity.intervention_ticks}
              </p>
            )}

            {card.explanation.length > 0 && (
              <ul className="explain">
                {card.explanation.map((line, index) => (
                  <li key={index}>{line}</li>
                ))}
              </ul>
            )}

            <div className="fixes">
              <h4>Recommended Fixes</h4>
              {card.recommended_fixes.length === 0 ? (
                <p className="fixes-none">
                  No remediation needed — no integrity violations or risk failures detected.
                </p>
              ) : (
                <ul className="fixes-list">
                  {card.recommended_fixes.map((fix, index) => (
                    <li className="fix" key={index}>
                      <span className="fix-issue">{fix.issue}</span>
                      <span className="fix-suggested">{fix.suggested_fix}</span>
                      <span className="fix-reason">{fix.reason}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
