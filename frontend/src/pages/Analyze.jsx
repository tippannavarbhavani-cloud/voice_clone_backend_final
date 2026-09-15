import { useState } from "react";
import AudioUploader from "../components/AudioUploader";
import AnalysisResult from "../components/AnalysisResult";

export default function Analyze() {
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [result, setResult] = useState(null);
  const [liveUpdate, setLiveUpdate] = useState(null);
  const [error, setError] = useState(null);

  return (
    <div>
      <div className="grid-2">
        <div className="panel">
          <p className="panel-title">Submit audio</p>
          <AudioUploader
            onAnalyzing={setIsAnalyzing}
            onResult={(r) => {
              setResult(r);
              setError(null);
            }}
            onError={setError}
            onLiveUpdate={setLiveUpdate}
          />
        </div>

        <div className="panel">
          <p className="panel-title">Processing</p>
          {error && <div className="error-banner">{error}</div>}

          {isAnalyzing && (
            <div style={{ textAlign: "center", padding: "20px 0" }}>
              <div className="waveform-loader">
                <span></span><span></span><span></span><span></span><span></span><span></span><span></span>
              </div>
              <p style={{ fontSize: 13, color: "var(--text-secondary)", marginTop: 12 }}>
                Isolating voice and checking for cloning patterns…
              </p>
            </div>
          )}

          {liveUpdate && (
            <div style={{ textAlign: "center", padding: "12px 0" }}>
              <span className={`badge badge-${liveUpdate.risk_level}`}>
                Live: {liveUpdate.risk_level} ({liveUpdate.risk_score.toFixed(0)})
              </span>
              <p style={{ fontSize: 12, color: "var(--text-secondary)", marginTop: 8 }}>
                Updating as the call continues…
              </p>
            </div>
          )}

          {!isAnalyzing && !liveUpdate && !error && (
            <p style={{ fontSize: 13, color: "var(--text-secondary)" }}>
              Submit a clip on the left to see live processing status here.
            </p>
          )}
        </div>
      </div>

      <AnalysisResult result={result} />
    </div>
  );
}
