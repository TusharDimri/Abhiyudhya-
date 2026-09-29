import { useSearchParams } from "react-router-dom";
import Icon from "./Icon";
import { ArrowUpCircle, Eye, PencilLine, Plus, Settings2 } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import ResourcePage from "./ResourcePage";
import AddStudents from "./AddStudents";
import PromoteDialog from "./PromoteDialog";

/* A trainer's Students page, in two tabs:
     View Students    the list, with the filters that matter - nothing to change
     Manage Students  Add students (many at once) · Promote · Edit
   (Verifying students is the admin's job.)                                  */
const MANAGE = [
  { key: "add", label: "Add Students", icon: Plus },
  { key: "promote", label: "Promote Students", icon: ArrowUpCircle },
  { key: "edit", label: "Edit Students", icon: PencilLine },
];

export default function StudentsHub() {
  const qc = useQueryClient();
  const [sp, setSp] = useSearchParams();
  const tab = sp.get("tab") === "manage" ? "manage" : "view";
  const part = MANAGE.some((m) => m.key === sp.get("manage")) ? sp.get("manage") : "add";
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
        <button type="button" className={`tab ${tab === "view" ? "on" : ""}`} onClick={() => go({ tab: "view" })}><Eye size={16} /> View Students</button>
        <button type="button" className={`tab ${tab === "manage" ? "on" : ""}`} onClick={() => go({ tab: "manage", manage: part })}><Settings2 size={16} /> Manage Students</button>
      </nav>

      {tab === "view" && <ResourcePage key="view" resourceKey="students" embedded readOnly onlyActions={["history", "record"]} />}

      {tab === "manage" && (
        <>
          <div className="seg manage-seg" role="group" aria-label="Manage">
            {MANAGE.map((m) => (
              <button key={m.key} type="button" className={part === m.key ? "on" : ""} onClick={() => go({ tab: "manage", manage: m.key })}>
                <m.icon size={15} /> {m.label}
              </button>
            ))}
          </div>
          {part === "add" && <AddStudents />}
          {part === "promote" && (
            <PromoteDialog
              inline
              onDone={() => {
                for (const key of [["list", "students"], ["promotion"], ["roster"]]) qc.invalidateQueries({ queryKey: key });
              }}
            />
          )}
          {part === "edit" && <ResourcePage key="edit" resourceKey="students" embedded hideCreate onlyActions={["history", "status", "record"]} />}
        </>
      )}
    </div>
  );
}
