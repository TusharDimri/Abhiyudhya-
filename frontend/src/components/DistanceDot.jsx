/* How far from their school a trainer was when they marked attendance.
   Green: on campus. Yellow: nearby - accepted (the limit is 1 km), but worth
   a glance. Grey: no location on the entry. The distance shows on hover. */
export const ON_CAMPUS_M = 300;

const describe = (m) => (m < 1000 ? `${Math.round(m)} m` : `${(m / 1000).toFixed(1)} km`);

export default function DistanceDot({ metres }) {
  if (metres == null || metres === "") {
    return <span className="dist-dot none" title="No location on this entry" aria-label="No location" />;
  }
  const near = Number(metres) <= ON_CAMPUS_M;
  const text = `${describe(Number(metres))} from the school`;
  return (
    <span className="dist-cell" title={text}>
      <span className={`dist-dot ${near ? "green" : "yellow"}`} aria-hidden="true" />
      <span className="dist-text">{describe(Number(metres))}</span>
    </span>
  );
}

export function DistanceLegend() {
  return (
    <div className="dist-legend">
      <span><span className="dist-dot green" /> within {ON_CAMPUS_M} m of the school</span>
      <span><span className="dist-dot yellow" /> {ON_CAMPUS_M} m – 1 km away</span>
      <span><span className="dist-dot none" /> no location recorded</span>
    </div>
  );
}

/* A trainer's own attendance: green once the Principal has verified
   (endorsed) it, orange until then - waiting, or returned for a fix. */
const ENDORSEMENT = {
  endorsed: { dot: "green", text: "Verified" },
  submitted: { dot: "orange", text: "Awaiting verification" },
  returned: { dot: "orange", text: "Returned - needs a fix" },
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
