import { useState } from "react";
import Icon from "./Icon";
import { ChevronsLeft, ChevronsRight, Globe, LogOut, Menu } from "lucide-react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "../lib/auth";
import { useBootstrap } from "../hooks/useBootstrap";
import { MODULES, NAV_GROUPS, NAV_GROUP_ORDER, MASTER_GROUP, isSectionHidden, groupOf, labelOf } from "../lib/modules";
import LocationButton from "./LocationButton";
import ScopeBadges from "./ScopeBadges";
import NotificationBell from "./NotificationBell";
import { NOTIFY_ROLES } from "../lib/notifications";

// Roles whose login carries a profile page of their own.
const PROFILE_ROLES = ["VT", "PR"];

// the nav group the admin pages below join (Organisations sits in it too)
const ADMIN_GROUP = "Administration";

// Special admin pages (not resource modules) with the roles allowed to see them.
const ADMIN_LINKS = [
  { to: "/app/admin/department-logins", label: "Department Logins", icon: "department-logins", roles: ["SA"] },
  { to: "/app/admin/users", label: "Users & Access", icon: "users", roles: ["SA", "OA"] },
  { to: "/app/admin/audit", label: "Audit Log", icon: "audit", roles: ["SA", "OA"] },
  // Recycle Bin: switched off - nothing can be deleted any more, so there's
  // nothing to restore. Uncomment to bring it back (pages/admin/Trash.jsx).
  // { to: "/app/admin/trash", label: "Recycle Bin", icon: "♻️", roles: ["SA", "OA", "DM"] },
];

export default function Layout() {
  const { user, roleLabel, logout, organisation } = useAuth();
  const { data: boot } = useBootstrap();
  const [open, setOpen] = useState(false);
  // desktop: a narrow icon-only sidebar, remembered in this browser
  const [collapsed, setCollapsed] = useState(() => {
    try { return localStorage.getItem("rnaf.sidebar") === "collapsed"; } catch { return false; }
  });
  const toggleCollapsed = () => setCollapsed((c) => {
    try { localStorage.setItem("rnaf.sidebar", c ? "open" : "collapsed"); } catch { /* not remembered */ }
    return !c;
  });
  const loc = useLocation();

  const visible = boot?.resources || {};
  const org = organisation || boot?.organisation;

  // group visible modules (backend already filtered by role via view_roles)
  const grouped = {};
  for (const [key, mod] of Object.entries(MODULES)) {
    if (!visible[key] || isSectionHidden(user?.role, key)) continue;
    (grouped[groupOf(mod, user?.role)] ||= []).push({ key, ...mod });
  }
  const adminLinks = ADMIN_LINKS.filter((l) => l.roles.includes(user?.role));
  // each role opens on the section it actually works in
  const navGroups = NAV_GROUP_ORDER[user?.role] || NAV_GROUPS;

  const initials = (user?.full_name || "?").split(" ").map((s) => s[0]).slice(0, 2).join("").toUpperCase();
  const seg = loc.pathname.split("/")[2];
  const title = seg === "admin"
    ? (ADMIN_LINKS.find((l) => loc.pathname.startsWith(l.to))?.label || "Administration")
    : seg === "master" ? MASTER_GROUP
    : seg === "profile" ? "My Profile"
    : (labelOf(MODULES[seg], user?.role) || (loc.pathname.includes("dashboard") ? "Dashboard" : "Abhiyudhya"));

  const item = ({ isActive }) => `nav-item ${isActive ? "active" : ""}`;

  return (
    <div className={`app-shell ${collapsed ? "collapsed" : ""} role-${(user?.role || "").toLowerCase()}`}>
      <aside className={`sidebar ${open ? "open" : ""}`}>
        {/* The organisation's own identity leads - this is their workspace,
            not a tenant of someone else's. The platform name stays underneath
            so it is still clear what they are logged into. */}
        <div className="brand">
          {org?.logo_src ? (
            <img src={org.logo_src} alt="" className="brand-logo" />
          ) : (
            <div className="brand-icon">
              {boot?.is_platform_admin ? <Globe size={18} /> : (org?.name || "Abhiyudhya").slice(0, 1).toUpperCase()}
            </div>
          )}
          <span className="brand-text">
            <span className="brand-name">
              {boot?.is_platform_admin ? "All Organisations" : (org?.name || "Abhiyudhya")}
            </span>
            <span className="brand-sub">Abhiyudhya · {roleLabel || user?.role}</span>
          </span>
        </div>
        <nav className="nav-scroll" onClick={() => setOpen(false)}>
          <NavLink to="/app/dashboard" className={item} title="Dashboard">
            <span className="ico"><Icon name="dashboard" /></span> <span className="nav-label">Dashboard</span>
          </NavLink>
          {NOTIFY_ROLES.includes(user?.role) && (
            <NavLink to="/app/notifications" className={item} title="Notifications">
              <span className="ico"><Icon name="notifications" /></span> <span className="nav-label">Notifications</span>
            </NavLink>
          )}
          {navGroups.map((g) =>
            grouped[g]?.length || (g === ADMIN_GROUP && adminLinks.length) ? (
              <div key={g}>
                <div className="nav-group-label">{g}</div>
                {g === MASTER_GROUP ? (
                  // one entry: the lists are tabs on the Master Data page
                  <NavLink to="/app/master" className={item} title={MASTER_GROUP}>
                    <span className="ico"><Icon name="master" /></span> <span className="nav-label">{MASTER_GROUP}</span>
                  </NavLink>
                ) : (grouped[g] || []).map((m) => (
                  <NavLink key={m.key} to={`/app/${m.key}`} className={item} title={labelOf(m, user?.role)}>
                    <span className="ico"><Icon name={m.key} /></span> <span className="nav-label">{labelOf(m, user?.role)}</span>
                  </NavLink>
                ))}
                {/* Users & Access, Audit Log: under the same heading, not a second "Administration" */}
                {g === ADMIN_GROUP && adminLinks.map((l) => (
                  <NavLink key={l.to} to={l.to} className={item} title={l.label}>
                    <span className="ico"><Icon name={l.icon} /></span> <span className="nav-label">{l.label}</span>
                  </NavLink>
                ))}
              </div>
            ) : null
          )}
          {PROFILE_ROLES.includes(user?.role) && (
            <div>
              <div className="nav-group-label">Profile</div>
              <NavLink to="/app/profile" className={item} title="My Profile">
                <span className="ico"><Icon name="profile" /></span> <span className="nav-label">My Profile</span>
              </NavLink>
            </div>
          )}
        </nav>
        <button type="button" className="collapse-btn" onClick={toggleCollapsed}
          title={collapsed ? "Expand the sidebar" : "Collapse the sidebar"} aria-expanded={!collapsed}>
          <span aria-hidden="true">{collapsed ? <ChevronsRight size={18} /> : <ChevronsLeft size={18} />}</span>
          <span className="nav-label">Collapse</span>
        </button>
      </aside>

      <div className={`backdrop ${open ? "show" : ""}`} onClick={() => setOpen(false)} />

      <div className="main">
        <header className="topbar">
          <button className="hamburger" onClick={() => setOpen((o) => !o)} aria-label="Menu"><Menu size={22} /></button>
          <span className="page-title">{title}</span>

          {org ? (
            <div className="org-brand" title={org.name}>
              {org.logo_src
                ? <img src={org.logo_src} alt={org.name} className="org-logo" />
                : <div className="org-logo-fallback">{(org.name || "?").slice(0, 2).toUpperCase()}</div>}
              <span className="org-name">{org.name}</span>
            </div>
          ) : boot?.is_platform_admin ? (
            <div className="org-brand platform" title="Platform administrator — all organisations">
              <div className="org-logo-fallback"><Globe size={16} /></div>
              <span className="org-name">All Organisations</span>
            </div>
          ) : null}

          <div className="user-chip">
            {user?.role === "VT" && <LocationButton />}
            {NOTIFY_ROLES.includes(user?.role) && <NotificationBell />}
            <div className="user-meta">
              <span className="user-name">{user?.full_name}</span>
              <span className="role-pill">{roleLabel || user?.role}</span>
            </div>
            <div className="avatar" aria-hidden="true">{initials}</div>
            <span className="topbar-divider" aria-hidden="true" />
            <button className="btn btn-ghost btn-sm logout-btn" onClick={logout} title="Log out">
              <LogOut size={16} aria-hidden="true" /> <span className="logout-label">Logout</span>
            </button>
          </div>
        </header>
        {!PROFILE_ROLES.includes(user?.role) && <ScopeBadges profile={boot?.my_scope?.profile} options={boot?.options} />}
        <main className="page">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
