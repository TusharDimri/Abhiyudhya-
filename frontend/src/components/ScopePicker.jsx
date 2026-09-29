/* An admin's way into the data. Nothing is listed until the pick is made:
     org admin     District -> School (a state, for the districts list)
     super admin   Organisation first, then the same
   `needs` is how far a list goes: "org" (set-up lists), "state", "district"
   or "school". */
import { useQuery } from "@tanstack/react-query";
import { Compass } from "lucide-react";
import api from "../lib/api";

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

// a super admin's lists come from the organisation they picked
function useOrgList(resource, orgId, extra = "", enabled = true) {
  return useQuery({
    queryKey: ["scope-options", resource, orgId, extra],
    queryFn: async () => (await api.get(`/${resource}?page_size=200&organisation_id=${orgId}${extra}`)).data.data
      .map((r) => ({ value: r.id, label: r.name, district_id: r.district_id })),
    enabled: !!orgId && enabled,
    staleTime: 60000,
  });
}

export default function ScopePicker({ needs, scope, setScope, boot, isSA }) {
  const opts = boot?.options || {};
  const org = scope.organisation_id;
  const wantsPlace = needs !== "org";
  const saStates = useOrgList("states", org, "", isSA && needs === "state");
  const saDistricts = useOrgList("districts", org, "", isSA && ["district", "school"].includes(needs));
  const saSchools = useOrgList("schools", org, scope.district_id ? `&district_id=${scope.district_id}` : "",
    isSA && needs === "school" && !!scope.district_id);

  const states = isSA ? saStates.data || [] : opts.states || [];
  const districts = isSA ? saDistricts.data || [] : opts.districts || [];
  const schools = isSA ? saSchools.data || []
    : (opts.schools || []).filter((s) => !scope.district_id || String(s.district_id) === String(scope.district_id));
  const orgFirst = isSA && !org;

  return (
    <div className="scope-bar">
      {isSA && (
        <Pick label="Organisation" value={org} options={opts.organisations || []} placeholder="Select an organisation"
          onChange={(v) => setScope({ organisation_id: v, state_id: "", district_id: "", school_id: "" })} />
      )}
      {wantsPlace && needs === "state" && (
        <Pick label="State" value={scope.state_id} options={states} disabled={orgFirst}
          placeholder={orgFirst ? "Select an organisation first" : "Select a state"}
          onChange={(v) => setScope({ ...scope, state_id: v })} />
      )}
      {wantsPlace && ["district", "school"].includes(needs) && (
        <Pick label="District" value={scope.district_id} options={districts} disabled={orgFirst}
          placeholder={orgFirst ? "Select an organisation first" : "Select a district"}
          onChange={(v) => setScope({ ...scope, district_id: v, school_id: "" })} />
      )}
      {wantsPlace && needs === "school" && (
        <Pick label="School" value={scope.school_id} options={schools} disabled={!scope.district_id}
          placeholder={scope.district_id ? "Select a school" : "Select a district first"}
          onChange={(v) => setScope({ ...scope, school_id: v })} />
      )}
    </div>
  );
}

export function ScopeEmpty({ needs, label, isSA }) {
  const place = needs === "state" ? "a state" : needs === "district" ? "a district" : needs === "school" ? "a district, then a school" : "";
  const what = isSA ? (place ? `an organisation, then ${place}` : "an organisation") : place;
  return (
    <div className="card scope-empty">
      <div className="scope-empty-ico"><Compass size={30} strokeWidth={1.5} /></div>
      <b>Choose {what} to see its {label.toLowerCase()}.</b>
      <span className="muted">Nothing is shown until you pick - then you can filter further.</span>
    </div>
  );
}
