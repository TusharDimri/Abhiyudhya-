import { useSearchParams } from "react-router-dom";
import Icon from "./Icon";
import { Eye, FileCheck2, UserCheck } from "lucide-react";
import ResourcePage from "./ResourcePage";

/* An org admin's Students page, in two tabs:
     View Students    the list with its filters, and each student's history
     Verify Students  students waiting for verification - Verify opens the
                      whole record, with Verify at the bottom
     TC to verify     leaving students whose TC the principal has recorded -
                      check it and mark them as left
   Both open on the district / school picked above the list.              */
const PENDING = { verification_status: "pending" };
const TC_TO_VERIFY = { leaving_stage: "tc_issued" };
const TABS = [["view", "View Students", Eye], ["verify", "Verify Students", UserCheck], ["leaving", "TC to verify", FileCheck2]];

export default function OrgStudents() {
  const [sp, setSp] = useSearchParams();
  const tab = TABS.some(([k]) => k === sp.get("tab")) ? sp.get("tab") : "view";
  // switching tab starts that tab afresh (its own filters and paging)
  const go = (next) => setSp(new URLSearchParams(next), { replace: false });

  return (
    <div className="stack" style={{ gap: "1rem" }}>
      <div className="page-head">
        <div>
          <div className="crumb">People &amp; Students</div>
          <h1><span className="page-ico"><Icon name="students" size={20} /></span>Students</h1>
        </div>
      </div>

      <nav className="tabs" aria-label="Students">
        {TABS.map(([k, label, TabIcon]) => (
          <button key={k} type="button" className={`tab ${tab === k ? "on" : ""}`} onClick={() => go({ tab: k })}><TabIcon size={16} /> {label}</button>
        ))}
      </nav>

      {tab === "view" && <ResourcePage key="view" resourceKey="students" embedded readOnly onlyActions={["history", "record"]} />}
      {tab === "verify" && <ResourcePage key="verify" resourceKey="students" scopeKey="students:verify" embedded readOnly onlyActions={["verify"]} fixedParams={PENDING} />}
      {tab === "leaving" && <ResourcePage key="leaving" resourceKey="students" scopeKey="students:leaving" embedded readOnly onlyActions={["leftverify"]} fixedParams={TC_TO_VERIFY} />}
    </div>
  );
}
