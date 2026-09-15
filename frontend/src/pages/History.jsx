import { useEffect, useState } from "react";
import { getHistory, getHistoryDetail, deleteHistoryItem } from "../services/api";
import RiskFactors from "../components/RiskFactors";

const RISK_FILTERS = [
  { value: "", label: "All" },
  { value: "genuine", label: "Genuine" },
  { value: "suspicious", label: "Suspicious" },
  { value: "high_risk", label: "High Risk" },
];

export default function History() {
  const [items, setItems] = useState([]);
  const [count, setCount] = useState(0);
  const [riskFilter, setRiskFilter] = useState("");
  const [selected, setSelected] = useState(null);
  const [loading, setLoading] = useState(true);

  const load = () => {
    setLoading(true);
    const params = riskFilter ? { risk_level: riskFilter } : {};
    getHistory(params)
      .then((data) => {
        setItems(data.results || data);
        setCount(data.count ?? (data.results || data).length);
      })
      .finally(() => setLoading(false));
  };

  useEffect(load, [riskFilter]);

  const handleViewDetails = async (id) => {
    const detail = await getHistoryDetail(id);
    setSelected(detail);
  };

  const handleDelete = async (id) => {
    await deleteHistoryItem(id);
    setSelected(null);
    load();
  };

  return (
    <div>
      <div className="panel">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
          <p className="panel-title" style={{ margin: 0 }}>
            {count} analyses
          </p>
          <select value={riskFilter} onChange={(e) => setRiskFilter(e.target.value)} style={{
            background: "var(--bg)", border: "1px solid var(--border-strong)", borderRadius: 5,
            color: "var(--text-primary)", padding: "7px 10px", fontSize: 13,
          }}>
            {RISK_FILTERS.map((f) => (
              <option key={f.value} value={f.value}>{f.label}</option>
            ))}
          </select>
        </div>

        {loading ? (
          <p style={{ color: "var(--text-secondary)" }}>Loading…</p>
        ) : items.length === 0 ? (
          <div className="empty-state">No analyses match this filter yet.</div>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>File</th>
                <th>Date / time</th>
                <th>Risk score</th>
                <th>Risk level</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.id}>
                  <td>{item.sample.original_filename}</td>
                  <td>{new Date(item.created_at).toLocaleString()}</td>
                  <td style={{ fontFamily: "var(--font-data)" }}>{item.risk_score.toFixed(0)}</td>
                  <td><span className={`badge badge-${item.risk_level}`}>{item.risk_level.replace("_", " ")}</span></td>
                  <td>
                    <button className="btn btn-secondary" onClick={() => handleViewDetails(item.id)}>
                      View details
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {selected && (
        <div
          style={{
            position: "fixed", inset: 0, background: "rgba(0,0,0,0.5)",
            display: "flex", alignItems: "center", justifyContent: "center", padding: 20, zIndex: 10,
          }}
          onClick={() => setSelected(null)}
        >
          <div className="panel" style={{ maxWidth: 480, width: "100%" }} onClick={(e) => e.stopPropagation()}>
            <p className="panel-title">{selected.sample.original_filename}</p>
            <div style={{ display: "flex", gap: 10, alignItems: "center", marginBottom: 16 }}>
              <span className={`badge badge-${selected.risk_level}`}>{selected.risk_level.replace("_", " ")}</span>
              <span style={{ fontFamily: "var(--font-data)", fontSize: 20 }}>{selected.risk_score.toFixed(0)}/100</span>
            </div>
            <p className="panel-title">Risk factors</p>
            <RiskFactors factors={selected.risk_factors} />
            <div style={{ display: "flex", gap: 10, marginTop: 20 }}>
              <button className="btn btn-secondary" onClick={() => setSelected(null)} style={{ flex: 1 }}>
                Close
              </button>
              <button className="btn btn-danger" onClick={() => handleDelete(selected.id)} style={{ flex: 1 }}>
                Delete
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
