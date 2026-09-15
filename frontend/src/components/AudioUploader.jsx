import { useRef, useState } from "react";
import { Upload, Mic, Link2, Radio, Square } from "lucide-react";
import { analyzeFile, analyzeUrl, buildLiveDetectSocketUrl } from "../services/api";

const TABS = [
  { id: "upload", label: "Upload file", icon: Upload },
  { id: "record", label: "Record", icon: Mic },
  { id: "url", label: "From URL", icon: Link2 },
  { id: "live", label: "Live call", icon: Radio },
];

export default function AudioUploader({ onAnalyzing, onResult, onError, onLiveUpdate }) {
  const [activeTab, setActiveTab] = useState("upload");
  const [selectedFile, setSelectedFile] = useState(null);
  const [audioUrl, setAudioUrl] = useState("");
  const [isRecording, setIsRecording] = useState(false);
  const [isLiveActive, setIsLiveActive] = useState(false);

  const mediaRecorderRef = useRef(null);
  const recordedChunksRef = useRef([]);
  const liveSocketRef = useRef(null);
  const liveRecorderRef = useRef(null);

  const runAnalysis = async (task) => {
    onAnalyzing(true);
    onError(null);
    try {
      const result = await task();
      onResult(result);
    } catch (err) {
      onError(err.response?.data?.audio_file?.[0] || err.response?.data?.detail || "Analysis failed. Please try again.");
    } finally {
      onAnalyzing(false);
    }
  };

  // ---------- Upload ----------
  const handleFileSubmit = () => {
    if (!selectedFile) return;
    runAnalysis(() => analyzeFile(selectedFile, "upload"));
  };

  // ---------- Record ----------
  const startRecording = async () => {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const recorder = new MediaRecorder(stream);
    recordedChunksRef.current = [];
    recorder.ondataavailable = (e) => recordedChunksRef.current.push(e.data);
    recorder.start();
    mediaRecorderRef.current = recorder;
    setIsRecording(true);
  };

  const stopRecording = () => {
    const recorder = mediaRecorderRef.current;
    if (!recorder) return;
    recorder.onstop = () => {
      const blob = new Blob(recordedChunksRef.current, { type: "audio/webm" });
      const file = new File([blob], "recording.webm", { type: "audio/webm" });
      runAnalysis(() => analyzeFile(file, "recording"));
    };
    recorder.stop();
    recorder.stream.getTracks().forEach((t) => t.stop());
    setIsRecording(false);
  };

  // ---------- URL ----------
  const handleUrlSubmit = () => {
    if (!audioUrl.trim()) return;
    runAnalysis(() => analyzeUrl(audioUrl.trim()));
  };

  // ---------- Live call ----------
  const startLiveCall = async () => {
    onError(null);
    const socket = new WebSocket(buildLiveDetectSocketUrl());
    liveSocketRef.current = socket;

    socket.onopen = async () => {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream, { mimeType: "audio/webm" });
      recorder.ondataavailable = (e) => {
        if (e.data.size > 0 && socket.readyState === WebSocket.OPEN) {
          socket.send(e.data);
        }
      };
      recorder.start(2000);
      liveRecorderRef.current = recorder;
      setIsLiveActive(true);
    };

    socket.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === "partial") {
        onLiveUpdate?.(data);
      } else if (data.type === "final") {
        onLiveUpdate?.(null);
        onResult(data);
        setIsLiveActive(false);
      } else if (data.type === "connected") {
        onError(null);
      }
    };

    socket.onerror = () => {
      onError("Live call connection failed. Check your access token and try again.");
      setIsLiveActive(false);
    };

    socket.onclose = () => {
      setIsLiveActive(false);
    };
  };

  const endLiveCall = () => {
    liveRecorderRef.current?.stop();
    if (liveSocketRef.current?.readyState === WebSocket.OPEN) {
      liveSocketRef.current.send("stop");
    }
  };

  return (
    <div>
      <div className="tabs">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            className={`tab${activeTab === tab.id ? " active" : ""}`}
            onClick={() => setActiveTab(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {activeTab === "upload" && (
        <div>
          <div className="field">
            <label>Audio file (mp3, wav, m4a, flac, ogg)</label>
            <input
              type="file"
              accept=".mp3,.wav,.m4a,.flac,.ogg,.webm"
              onChange={(e) => setSelectedFile(e.target.files[0] || null)}
            />
          </div>
          <button className="btn btn-primary btn-full" onClick={handleFileSubmit} disabled={!selectedFile}>
            Analyze file
          </button>
        </div>
      )}

      {activeTab === "record" && (
        <div>
          <p style={{ color: "var(--text-secondary)", fontSize: 13, marginBottom: 14 }}>
            Record a short clip directly from your microphone, then analyze it.
          </p>
          {!isRecording ? (
            <button className="btn btn-primary btn-full" onClick={startRecording}>
              <Mic size={15} /> Start recording
            </button>
          ) : (
            <button className="btn btn-danger btn-full" onClick={stopRecording}>
              <Square size={14} /> Stop &amp; analyze
            </button>
          )}
        </div>
      )}

      {activeTab === "url" && (
        <div>
          <div className="field">
            <label>Audio URL</label>
            <input
              type="url"
              placeholder="https://example.com/call-recording.wav"
              value={audioUrl}
              onChange={(e) => setAudioUrl(e.target.value)}
            />
          </div>
          <button className="btn btn-primary btn-full" onClick={handleUrlSubmit} disabled={!audioUrl.trim()}>
            Analyze URL
          </button>
        </div>
      )}

      {activeTab === "live" && (
        <div>
          <p style={{ color: "var(--text-secondary)", fontSize: 13, marginBottom: 14 }}>
            Stream a live call for ongoing analysis. You'll get periodic risk updates, then a final
            result when you end the call.
          </p>
          {!isLiveActive ? (
            <button className="btn btn-primary btn-full" onClick={startLiveCall}>
              <Radio size={15} /> Start live call
            </button>
          ) : (
            <button className="btn btn-danger btn-full" onClick={endLiveCall}>
              <Square size={14} /> End call
            </button>
          )}
        </div>
      )}
    </div>
  );
}
