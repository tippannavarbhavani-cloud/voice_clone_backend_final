import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend } from "recharts";
import RiskScore from "../components/RiskScore";
import { getDashboard } from "../services/api";

export default function Dashboard() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    getDashboard()
      .then(setData)
      .catch(() => setError("Could not load dashboard data."));
  }, []);

  if (error) return <div className="error-banner">{error}</div>;
  if (!data) return <p style={{ color: "var(--text-secondary)" }}>Loading…</p>;

  const stats = data.detection_statistics;

  return (
    <div>
      <div className="grid-2" style={{ marginBottom: 18 }}>
        <div className="panel">
          <p className="panel-title">Current risk status</p>
          <RiskScore riskLevel={data.current_risk_status} riskScore={data.current_risk_score} />
        </div>

        <div className="panel">
          <p className="panel-title">Totals</p>
          <div className="grid-3" style={{ gap: 10 }}>
            <StatBlock label="Genuine" value={stats.genuine_count} color="var(--risk-genuine)" />
            <StatBlock label="Suspicious" value={stats.suspicious_count} color="var(--risk-suspicious)" />
            <StatBlock label="High Risk" value={stats.high_risk_count} color="var(--risk-high)" />
          </div>
        </div>
      </div>

      <div className="panel" style={{ marginBottom: 18 }}>
        <p className="panel-title">Detections over the last 7 days</p>
        <ResponsiveContainer width="100%" height={220}>
          <BarChart data={stats.daily_chart}>
            <XAxis dataKey="date" stroke="var(--text-tertiary)" fontSize={11} tickFormatter={(d) => d.slice(5)} />
            <YAxis stroke="var(--text-tertiary)" fontSize={11} allowDecimals={false} />
            <Tooltip
              contentStyle={{ background: "var(--surface-raised)", border: "1px solid var(--border)", borderRadius: 6 }}
              labelStyle={{ color: "var(--text-primary)" }}
            />
            <Legend wrapperStyle={{ fontSize: 12 }} />
            <Bar dataKey="genuine" stackId="a" fill="var(--risk-genuine)" name="Genuine" radius={[0, 0, 0, 0]} />
            <Bar dataKey="suspicious" stackId="a" fill="var(--risk-suspicious)" name="Suspicious" />
            <Bar dataKey="high_risk" stackId="a" fill="var(--risk-high)" name="High Risk" radius={[3, 3, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div className="grid-2">
        <div className="panel">
          <p className="panel-title">Recent detections</p>
          {data.recent_detections.length === 0 ? (
            <p style={{ color: "var(--text-secondary)", fontSize: 13 }}>No analyses yet.</p>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              {data.recent_detections.map((item) => (
                <div key={item.id} style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 500 }}>{item.sample.original_filename}</div>
                    <div style={{ fontSize: 12, color: "var(--text-secondary)" }}>
                      {new Date(item.created_at).toLocaleString()}
                    </div>
                  </div>
                  <span className={`badge badge-${item.risk_level}`}>{item.risk_score.toFixed(0)}</span>
                </div>
              ))}
            </div>
          )}
          <Link to="/history" style={{ fontSize: 12.5, color: "var(--accent)", display: "inline-block", marginTop: 14 }}>
            View all history
          </Link>
        </div>

        <div className="panel">
          <p className="panel-title">Top risk factors (last 30 days)</p>
          {data.top_risk_factors.length === 0 ? (
            <p style={{ color: "var(--text-secondary)", fontSize: 13 }}>Nothing flagged recently.</p>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              {data.top_risk_factors.map((f, i) => (
                <div key={i} style={{ display: "flex", justifyContent: "space-between", fontSize: 13 }}>
                  <span style={{ color: "var(--text-secondary)" }}>{f.factor}</span>
                  <span style={{ fontFamily: "var(--font-data)", color: "var(--text-primary)" }}>{f.count}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function StatBlock({ label, value, color }) {
  return (
    <div style={{ textAlign: "center", padding: "10px 6px", background: "var(--bg)", borderRadius: 6 }}>
      <div style={{ fontFamily: "var(--font-data)", fontSize: 22, fontWeight: 600, color }}>{value}</div>
      <div style={{ fontSize: 11.5, color: "var(--text-secondary)", marginTop: 2 }}>{label}</div>
    </div>
  );
}
