/* How far from their school a trainer was when they marked attendance.
   Green: at the school (up to 750 m). Yellow: 751 m to 1.2 km - worth a
   glance. Red: further than 1.2 km. Grey: no location on the entry.
   The exact distance shows on hover. */
export const ON_CAMPUS_M = 750;
export const NEARBY_M = 1200;

const describe = (m) => (m < 1000 ? `${Math.round(m)} m` : `${(m / 1000).toFixed(1)} km`);

export default function DistanceDot({ metres }) {
  if (metres == null || metres === "") {
    return <span className="dist-dot none" title="No location on this entry" aria-label="No location" />;
  }
  const m = Number(metres);
  const colour = m <= ON_CAMPUS_M ? "green" : m <= NEARBY_M ? "yellow" : "red";
  const text = `${describe(m)} from the school`;
  return (
    <span className="dist-cell" title={text}>
      <span className={`dist-dot ${colour}`} aria-hidden="true" />
      <span className="dist-text">{describe(Number(metres))}</span>
    </span>
  );
}

export function DistanceLegend() {
  return (
    <div className="dist-legend">
      <span><span className="dist-dot green" /> within {ON_CAMPUS_M} m of the school</span>
      <span><span className="dist-dot yellow" /> {ON_CAMPUS_M + 1} m – {NEARBY_M / 1000} km away</span>
      <span><span className="dist-dot red" /> more than {NEARBY_M / 1000} km away</span>
      <span><span className="dist-dot none" /> no location recorded</span>
    </div>
  );
}

/* A trainer's own attendance: green once the Principal has verified
   (endorsed) it, orange while it waits. */
const ENDORSEMENT = {
  endorsed: { dot: "green", text: "Verified" },
  submitted: { dot: "orange", text: "Awaiting verification" },
};

export function EndorsementDot({ value }) {
  const e = ENDORSEMENT[value] || { dot: "none", text: value || "—" };
  return (
    <span className="dist-cell" title={e.text}>
      <span className={`dist-dot ${e.dot}`} aria-hidden="true" />
      <span className="dist-text">{e.text}</span>
    </span>
  );
}

export function EndorsementLegend() {
  return (
    <div className="dist-legend">
      <span><span className="dist-dot green" /> verified by the Principal</span>
      <span><span className="dist-dot orange" /> not verified yet</span>
    </div>
  );
}
