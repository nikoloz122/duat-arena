import { IntegrityReport } from "../../lib/api";
import { agentLabel, severityColor } from "../../lib/format";

export default function IntegrityPanel({
  integrity,
  scenario,
}: {
  integrity: IntegrityReport;
  scenario: string;
}) {
  const intercepted = integrity.intervention_ticks;
  const high = integrity.categories
    .filter((c) => c.severity === "high")
    .reduce((sum, c) => sum + c.count, 0);
  const medium = integrity.categories
    .filter((c) => c.severity === "medium")
    .reduce((sum, c) => sum + c.count, 0);

  return (
    <section className="panel integrity-panel" aria-label="Integrity violations">
      <h2>Integrity Violations</h2>

      {intercepted > 0 ? (
        <div className="banner alert integrity-banner">
          <span className="integrity-stat">{intercepted}</span>
          <span>
            DUAT intercepted {intercepted} unsafe bot/agent decision
            {intercepted === 1 ? "" : "s"} during {scenario}.
          </span>
        </div>
      ) : (
        <div className="banner ok">
          DUAT intercepted 0 unsafe decisions during {scenario}. Every decision passed
          the safety boundary unchanged.
        </div>
      )}

      {integrity.total > 0 && (
        <>
          <p className="caption">
            {high} high-severity · {medium} medium-severity intervention reason(s). Each
            was normalized to a safe action before it reached the market.
          </p>

          <div className="badges">
            {integrity.categories.map((category) => (
              <span
                className="badge"
                key={category.key}
                style={{ background: severityColor(category.severity) }}
              >
                {category.count}× {category.label}
              </span>
            ))}
          </div>

          <div className="table-wrap">
            <table className="data">
              <thead>
                <tr>
                  <th>Tick</th>
                  <th>Agent</th>
                  <th>Category</th>
                  <th>Severity</th>
                  <th>Detail</th>
                </tr>
              </thead>
              <tbody>
                {integrity.timeline.map((entry, index) => (
                  <tr key={index}>
                    <td>{entry.tick}</td>
                    <td>{agentLabel(entry.agent)}</td>
                    <td>{entry.label}</td>
                    <td>
                      <span className="tag" style={{ background: severityColor(entry.severity) }}>
                        {entry.severity}
                      </span>
                    </td>
                    <td className="muted">{entry.note}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </section>
  );
}
