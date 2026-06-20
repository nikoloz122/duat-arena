import { ReplayEvent } from "../../lib/api";
import { agentLabel } from "../../lib/format";

export default function ReplayTimeline({ events }: { events: ReplayEvent[] }) {
  if (events.length === 0) return null;

  return (
    <section className="panel" aria-label="Replay timeline">
      <h2>Replay Timeline</h2>
      <p className="caption">
        Tick-by-tick decisions. Flags mark chaos events and safety-boundary interceptions.
      </p>

      <div className="table-wrap">
        <table className="data">
          <thead>
            <tr>
              <th>Tick</th>
              <th>Agent</th>
              <th>Intended</th>
              <th>Executed</th>
              <th>Reason</th>
              <th>Flags</th>
            </tr>
          </thead>
          <tbody>
            {events.map((event, index) => {
              const intercepted = event.normalization_notes.length > 0;
              const chaos = Boolean(event.scenario_event);
              return (
                <tr key={index}>
                  <td>{event.tick}</td>
                  <td>{agentLabel(event.agent)}</td>
                  <td>{event.intended_action}</td>
                  <td>{event.executed_action}</td>
                  <td className="muted">{event.reason}</td>
                  <td>
                    {chaos && (
                      <span className="tag" style={{ background: "#cf6800", marginRight: 6 }}>
                        chaos
                      </span>
                    )}
                    {intercepted && (
                      <span className="tag" style={{ background: "#cf222e" }}>
                        intercepted
                      </span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}
