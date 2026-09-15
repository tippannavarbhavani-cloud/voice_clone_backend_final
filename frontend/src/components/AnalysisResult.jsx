import RiskScore from "./RiskScore";
import RiskFactors from "./RiskFactors";

export default function AnalysisResult({ result }) {
  if (!result) return null;

  const isFailed = result.risk_level === "failed";

  return (
    <div className="panel" style={{ marginTop: 20 }}>
      <p className="panel-title">Result</p>

      {isFailed ? (
        <div className="error-banner" style={{ marginBottom: 0 }}>
          Analysis failed: {result.error_message || "the audio could not be processed."}
        </div>
      ) : (
        <>
          <RiskScore riskLevel={result.risk_level} riskScore={result.risk_score} />

          <div className="grid-2" style={{ marginTop: 20 }}>
            <div>
              <p className="panel-title">Risk factors</p>
              <RiskFactors factors={result.risk_factors} />
            </div>
            <div>
              <p className="panel-title">Details</p>
              <dl style={{ margin: 0, fontSize: 13, color: "var(--text-secondary)" }}>
                <div style={{ display: "flex", justifyContent: "space-between", padding: "6px 0" }}>
                  <dt>Source</dt>
                  <dd style={{ margin: 0, color: "var(--text-primary)" }}>{result.sample?.source || "—"}</dd>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", padding: "6px 0" }}>
                  <dt>Duration</dt>
                  <dd style={{ margin: 0, color: "var(--text-primary)" }}>
                    {result.sample?.duration_seconds ? `${result.sample.duration_seconds}s` : "—"}
                  </dd>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", padding: "6px 0" }}>
                  <dt>Noise reduction</dt>
                  <dd style={{ margin: 0, color: "var(--text-primary)" }}>
                    {result.noise_reduction_applied ? "Applied" : "Not applied"}
                  </dd>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", padding: "6px 0" }}>
                  <dt>Processing time</dt>
                  <dd style={{ margin: 0, color: "var(--text-primary)" }}>{result.processing_time_ms} ms</dd>
                </div>
              </dl>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
