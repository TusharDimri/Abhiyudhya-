import { useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "../lib/auth";
import { useBootstrap } from "../hooks/useBootstrap";
import { MODULES, NAV_GROUPS, NAV_GROUP_ORDER, isSectionHidden } from "../lib/modules";
import LocationButton from "./LocationButton";
import ScopeBadges from "./ScopeBadges";

// Special admin pages (not resource modules) with the roles allowed to see them.
const ADMIN_LINKS = [
  { to: "/app/admin/users", label: "Users & Access", icon: "👥", roles: ["SA", "OA", "DM"] },
  { to: "/app/admin/audit", label: "Audit Log", icon: "📜", roles: ["SA", "OA"] },
  { to: "/app/admin/trash", label: "Recycle Bin", icon: "♻️", roles: ["SA", "OA", "DM"] },
];

export default function Layout() {
  const { user, roleLabel, logout, organisation } = useAuth();
  const { data: boot } = useBootstrap();
  const [open, setOpen] = useState(false);
  const loc = useLocation();

  const visible = boot?.resources || {};
  const org = organisation || boot?.organisation;

  // group visible modules (backend already filtered by role via view_roles)
  const grouped = {};
  for (const [key, mod] of Object.entries(MODULES)) {
    if (!visible[key] || isSectionHidden(user?.role, key)) continue;
    (grouped[mod.group] ||= []).push({ key, ...mod });
  }
  const adminLinks = ADMIN_LINKS.filter((l) => l.roles.includes(user?.role));
  // each role opens on the section it actually works in
  const navGroups = NAV_GROUP_ORDER[user?.role] || NAV_GROUPS;

  const initials = (user?.full_name || "?").split(" ").map((s) => s[0]).slice(0, 2).join("").toUpperCase();
  const seg = loc.pathname.split("/")[2];
  const title = seg === "admin"
    ? (ADMIN_LINKS.find((l) => loc.pathname.startsWith(l.to))?.label || "Administration")
    : (MODULES[seg]?.label || (loc.pathname.includes("dashboard") ? "Dashboard" : "Abhiyudhya"));

  return (
    <div className="app-shell">
      <aside className={`sidebar ${open ? "open" : ""}`}>
        {/* The organisation's own identity leads - this is their workspace,
            not a tenant of someone else's. The platform name stays underneath
            so it is still clear what they are logged into. */}
        <div className="brand">
          {org?.logo_url ? (
            <img src={org.logo_url} alt="" className="brand-logo" />
          ) : (
            <div className="brand-icon">
              {boot?.is_platform_admin ? "🌐" : (org?.name || "Abhiyudhya").slice(0, 1).toUpperCase()}
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
          <NavLink to="/app/dashboard" className={({ isActive }) => `nav-item ${isActive ? "active" : ""}`}>
            <span className="ico">📊</span> Dashboard
          </NavLink>
          {navGroups.map((g) =>
            grouped[g]?.length ? (
              <div key={g}>
                <div className="nav-group-label">{g}</div>
                {grouped[g].map((m) => (
                  <NavLink key={m.key} to={`/app/${m.key}`} className={({ isActive }) => `nav-item ${isActive ? "active" : ""}`}>
                    <span className="ico">{m.icon}</span> {m.label}
                  </NavLink>
                ))}
              </div>
            ) : null
          )}
          {adminLinks.length > 0 && (
            <div>
              <div className="nav-group-label">Administration</div>
              {adminLinks.map((l) => (
                <NavLink key={l.to} to={l.to} className={({ isActive }) => `nav-item ${isActive ? "active" : ""}`}>
                  <span className="ico">{l.icon}</span> {l.label}
                </NavLink>
              ))}
            </div>
          )}
        </nav>
      </aside>

      <div className={`backdrop ${open ? "show" : ""}`} onClick={() => setOpen(false)} />

      <div className="main">
        <header className="topbar">
          <button className="hamburger" onClick={() => setOpen((o) => !o)}>☰</button>
          <span className="page-title">{title}</span>

          {org ? (
            <div className="org-brand" title={org.name}>
              {org.logo_url
                ? <img src={org.logo_url} alt={org.name} className="org-logo" />
                : <div className="org-logo-fallback">{(org.name || "?").slice(0, 2).toUpperCase()}</div>}
              <span className="org-name">{org.name}</span>
            </div>
          ) : boot?.is_platform_admin ? (
            <div className="org-brand platform" title="Platform administrator — all organisations">
              <div className="org-logo-fallback">🌐</div>
              <span className="org-name">All Organisations</span>
            </div>
          ) : null}

          <div className="user-chip">
            {user?.role === "VT" && <LocationButton />}
            <div style={{ textAlign: "right", lineHeight: 1.15 }} className="user-meta">
              <div style={{ fontWeight: 700, fontSize: ".85rem" }}>{user?.full_name}</div>
              <span className="role-pill">{roleLabel || user?.role}</span>
            </div>
            <div className="avatar">{initials}</div>
            <button className="btn btn-ghost btn-sm" onClick={logout}>Logout</button>
          </div>
        </header>
        <ScopeBadges profile={boot?.my_scope?.profile} options={boot?.options} />
        <main className="page">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
