const RISK_META = {
  genuine: { color: "var(--risk-genuine)", label: "Genuine" },
  suspicious: { color: "var(--risk-suspicious)", label: "Suspicious" },
  high_risk: { color: "var(--risk-high)", label: "High Risk" },
  failed: { color: "var(--text-tertiary)", label: "Analysis failed" },
  no_data: { color: "var(--text-tertiary)", label: "No data yet" },
};

export default function RiskScore({ riskLevel, riskScore, size = 108 }) {
  const meta = RISK_META[riskLevel] || RISK_META.no_data;
  const radius = (size - 12) / 2;
  const circumference = 2 * Math.PI * radius;
  const pct = riskScore == null ? 0 : Math.min(100, Math.max(0, riskScore)) / 100;
  const offset = circumference * (1 - pct);

  return (
    <div className="risk-score">
      <div className="risk-score-ring" style={{ width: size, height: size }}>
        <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke="var(--border)"
            strokeWidth="8"
          />
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke={meta.color}
            strokeWidth="8"
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            transform={`rotate(-90 ${size / 2} ${size / 2})`}
            style={{ transition: "stroke-dashoffset 0.6s ease" }}
          />
        </svg>
        <div className="risk-score-value">
          <span className="risk-score-number">{riskScore == null ? "—" : Math.round(riskScore)}</span>
          <span className="risk-score-max">/ 100</span>
        </div>
      </div>
      <div>
        <span className={`badge badge-${riskLevel || "failed"}`}>{meta.label}</span>
      </div>
    </div>
  );
}
