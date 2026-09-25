// Date-range selector with presets + custom range. Value = {from, to} (ISO or "").
import DateInput from "./DateInput";
import { isoDaysAgo } from "../lib/dates";

const PRESETS = [
  { key: "30d", label: "30 days", days: 30 },
  { key: "90d", label: "90 days", days: 90 },
  { key: "12m", label: "12 months", days: 365 },
  { key: "all", label: "All time", days: null },
];


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
          <DateInput value={value.from || ""} onChange={(v) => onChange({ ...value, from: v })} placeholder="From" />
          <span className="muted">→</span>
          <DateInput value={value.to || ""} onChange={(v) => onChange({ ...value, to: v })} placeholder="To" />
        </div>
      )}
    </div>
  );
}
