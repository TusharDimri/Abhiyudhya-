import { NavLink, Navigate, useLocation, useParams } from "react-router-dom";
import Icon from "./Icon";
import { useAuth } from "../lib/auth";
import { useBootstrap } from "../hooks/useBootstrap";
import { MASTER_GROUP, visibleModules, groupOf } from "../lib/modules";
import ResourcePage from "./ResourcePage";
import DistrictManagers from "./DistrictManagers";

// Tabs that aren't record lists of their own: a district manager is a login
// (with the districts they look after) - the org admin adds them here, right
// after Districts. The super admin sees them read-only. (Department logins
// are the super admin's: Administration -> Department Logins.)
const EXTRA_TABS = {
  "district-managers": { label: "District Managers", after: "districts", roles: ["OA", "SA"], Page: DistrictManagers },
};

/* Every master-data list (schools, labs, job roles …) on one page, one tab
   each - the sidebar holds a single "Master Data" entry instead of a list. */
export default function MasterData() {
  const { resource } = useParams();
  const { user } = useAuth();
  const { data: boot } = useBootstrap();
  const { search } = useLocation();

  const tabs = visibleModules(boot, user?.role).filter(([, m]) => groupOf(m, user?.role) === MASTER_GROUP);
  for (const [key, extra] of Object.entries(EXTRA_TABS)) {
    if (!extra.roles.includes(user?.role)) continue;
    const at = tabs.findIndex(([k]) => k === extra.after);
    tabs.splice(at >= 0 ? at + 1 : tabs.length, 0, [key, extra]);
  }
  if (!boot) return null;
  if (!tabs.length) return <Navigate to="/app/dashboard" replace />;
  if (!resource || !tabs.some(([k]) => k === resource)) {
    return <Navigate to={`/app/master/${tabs[0][0]}${search}`} replace />;
  }
  const Extra = EXTRA_TABS[resource]?.Page;

  return (
    <div className="stack" style={{ gap: ".9rem" }}>
      <nav className="tabs" aria-label="Master data">
        {tabs.map(([key, m]) => (
          <NavLink key={key} to={`/app/master/${key}`} className={({ isActive }) => `tab ${isActive ? "on" : ""}`}>
            <Icon name={key} size={16} /> {m.label}
          </NavLink>
        ))}
      </nav>
      {/* a fresh list per tab: its own filters, paging and search */}
      {Extra ? <Extra key={resource} /> : <ResourcePage key={resource} />}
    </div>
  );
}
