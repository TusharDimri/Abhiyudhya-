/* An org admin's way into the data: pick a district, then a school (or, for
   the districts list, a state). Nothing is listed until the pick is made. */

function Pick({ label, value, options, onChange, placeholder, disabled }) {
  return (
    <label className="scope-pick">
      <span>{label}</span>
      <select className={`select ${value ? "on" : ""}`} value={value || ""} disabled={disabled} onChange={(e) => onChange(e.target.value)}>
        <option value="">{placeholder}</option>
        {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
    </label>
  );
}

export default function ScopePicker({ needs, scope, setScope, boot }) {
  const opts = boot?.options || {};
  const schools = (opts.schools || []).filter((s) => !scope.district_id || String(s.district_id) === String(scope.district_id));
  return (
    <div className="scope-bar">
      {needs === "state" ? (
        <Pick label="State" value={scope.state_id} options={opts.states || []} placeholder="Select a state"
          onChange={(v) => setScope({ ...scope, state_id: v })} />
      ) : (
        <>
          <Pick label="District" value={scope.district_id} options={opts.districts || []} placeholder="Select a district"
            onChange={(v) => setScope({ ...scope, district_id: v, school_id: "" })} />
          {needs === "school" && (
            <Pick label="School" value={scope.school_id} options={schools} disabled={!scope.district_id}
              placeholder={scope.district_id ? "Select a school" : "Select a district first"}
              onChange={(v) => setScope({ ...scope, school_id: v })} />
          )}
        </>
      )}
    </div>
  );
}

export function ScopeEmpty({ needs, label }) {
  const what = needs === "state" ? "a state" : needs === "district" ? "a district" : "a district, then a school";
  return (
    <div className="card scope-empty">
      <div className="scope-empty-ico">🧭</div>
      <b>Choose {what} to see its {label.toLowerCase()}.</b>
      <span className="muted">Nothing is shown until you pick one - then you can filter further.</span>
    </div>
  );
}
