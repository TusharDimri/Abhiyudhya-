import { NavLink, Navigate, useLocation, useParams } from "react-router-dom";
import { useAuth } from "../lib/auth";
import { useBootstrap } from "../hooks/useBootstrap";
import { MASTER_GROUP, visibleModules } from "../lib/modules";
import ResourcePage from "./ResourcePage";

/* Every master-data list (schools, labs, job roles …) on one page, one tab
   each - the sidebar holds a single "Master Data" entry instead of a list. */
export default function MasterData() {
  const { resource } = useParams();
  const { user } = useAuth();
  const { data: boot } = useBootstrap();
  const { search } = useLocation();

  const tabs = visibleModules(boot, user?.role).filter(([, m]) => m.group === MASTER_GROUP);
  if (!boot) return null;
  if (!tabs.length) return <Navigate to="/app/dashboard" replace />;
  if (!resource || !tabs.some(([k]) => k === resource)) {
    return <Navigate to={`/app/master/${tabs[0][0]}${search}`} replace />;
  }

  return (
    <div className="stack" style={{ gap: ".9rem" }}>
      <nav className="tabs" aria-label="Master data">
        {tabs.map(([key, m]) => (
          <NavLink key={key} to={`/app/master/${key}`} className={({ isActive }) => `tab ${isActive ? "on" : ""}`}>
            <span aria-hidden="true">{m.icon}</span> {m.label}
          </NavLink>
        ))}
      </nav>
      {/* a fresh list per tab: its own filters, paging and search */}
      <ResourcePage key={resource} />
    </div>
  );
}
