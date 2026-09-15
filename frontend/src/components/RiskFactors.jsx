export default function RiskFactors({ factors }) {
  if (!factors || factors.length === 0) {
    return <p style={{ color: "var(--text-secondary)", fontSize: 13 }}>No risk factors recorded.</p>;
  }

  return (
    <ul className="factor-list">
      {factors.map((factor, i) => (
        <li key={i}>{factor}</li>
      ))}
    </ul>
  );
}
