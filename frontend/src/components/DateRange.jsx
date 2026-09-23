// Date-range selector with presets + custom range. Value = {from, to} (ISO or "").
const PRESETS = [
  { key: "30d", label: "30 days", days: 30 },
  { key: "90d", label: "90 days", days: 90 },
  { key: "12m", label: "12 months", days: 365 },
  { key: "all", label: "All time", days: null },
];

function isoDaysAgo(days) {
  const d = new Date();
  d.setDate(d.getDate() - days);
  return d.toISOString().slice(0, 10);
}

export default function DateRange({ value, onChange, preset, onPreset }) {
  return (
    <div className="range-bar">
      <div className="seg">
        {PRESETS.map((p) => (
          <button
            key={p.key}
            className={preset === p.key ? "active" : ""}
            onClick={() => {
              onPreset(p.key);
              onChange(p.days ? { from: isoDaysAgo(p.days), to: "" } : { from: "", to: "" });
            }}
          >
            {p.label}
          </button>
        ))}
        <button className={preset === "custom" ? "active" : ""} onClick={() => onPreset("custom")}>Custom</button>
      </div>
      {preset === "custom" && (
        <div className="custom-dates">
          <input className="input" type="date" value={value.from || ""} onChange={(e) => onChange({ ...value, from: e.target.value })} />
          <span className="muted">→</span>
          <input className="input" type="date" value={value.to || ""} onChange={(e) => onChange({ ...value, to: e.target.value })} />
        </div>
      )}
    </div>
  );
}
