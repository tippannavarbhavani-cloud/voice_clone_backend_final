import { useEffect, useState } from "react";
import { getPreferences, updatePreferences, getProfile } from "../services/api";

export default function Settings() {
  const [prefs, setPrefs] = useState(null);
  const [profile, setProfile] = useState(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    getPreferences().then(setPrefs);
    getProfile().then(setProfile);
  }, []);

  const save = async (patch) => {
    const updated = await updatePreferences(patch);
    setPrefs(updated);
    setSaved(true);
    setTimeout(() => setSaved(false), 1500);
  };

  if (!prefs) return <p style={{ color: "var(--text-secondary)" }}>Loading…</p>;

  return (
    <div>
      <div className="grid-2">
        <div className="panel">
          <p className="panel-title">Detection preferences</p>

          <div className="field">
            <label>Sensitivity</label>
            <select
              value={prefs.sensitivity}
              onChange={(e) => save({ sensitivity: e.target.value })}
            >
              <option value="strict">Strict — flags more as risky</option>
              <option value="balanced">Balanced</option>
              <option value="lenient">Lenient — flags less as risky</option>
            </select>
          </div>

          <ToggleRow
            label="Voice isolation (noise reduction)"
            desc="Clean up background noise before every analysis."
            checked={prefs.enable_noise_reduction}
            onChange={(v) => save({ enable_noise_reduction: v })}
          />
        </div>

        <div className="panel">
          <p className="panel-title">Verification preferences</p>

          <ToggleRow
            label="Alert on High Risk"
            desc="Automatically log a security alert for High Risk results."
            checked={prefs.alert_on_high_risk}
            onChange={(v) => save({ alert_on_high_risk: v })}
          />
          <ToggleRow
            label="Require re-verification"
            desc="Flag High Risk calls as needing manual review before proceeding."
            checked={prefs.require_reverification_on_high_risk}
            onChange={(v) => save({ require_reverification_on_high_risk: v })}
          />

          <div className="field" style={{ marginTop: 8 }}>
            <label>Retain history (days, 0 = forever)</label>
            <input
              type="number"
              min="0"
              value={prefs.retain_history_days}
              onChange={(e) => setPrefs({ ...prefs, retain_history_days: e.target.value })}
              onBlur={(e) => save({ retain_history_days: Number(e.target.value) })}
            />
          </div>
        </div>
      </div>

      <div className="panel" style={{ marginTop: 18 }}>
        <p className="panel-title">Account</p>
        {profile ? (
          <div className="grid-2">
            <div className="field">
              <label>Username</label>
              <input type="text" value={profile.username} disabled />
            </div>
            <div className="field">
              <label>Email</label>
              <input type="email" value={profile.email} disabled />
            </div>
          </div>
        ) : (
          <p style={{ color: "var(--text-secondary)", fontSize: 13 }}>Loading account info…</p>
        )}
      </div>

      {saved && (
        <p style={{ color: "var(--risk-genuine)", fontSize: 13, marginTop: 14 }}>Preferences saved.</p>
      )}
    </div>
  );
}

function ToggleRow({ label, desc, checked, onChange }) {
  return (
    <div className="toggle-row">
      <div>
        <div className="toggle-row-label">{label}</div>
        <div className="toggle-row-desc">{desc}</div>
      </div>
      <label className="switch">
        <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} />
        <span className="switch-track"></span>
      </label>
    </div>
  );
}
