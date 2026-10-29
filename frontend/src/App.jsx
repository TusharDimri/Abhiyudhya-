import { Suspense, lazy } from "react";
import { Routes, Route, Navigate, useParams, useLocation } from "react-router-dom";
import { useAuth } from "./lib/auth";
import { NOTIFY_ROLES } from "./lib/notifications";
import { isSectionHidden, MODULES, MASTER_GROUP, groupOf } from "./lib/modules";
import Layout from "./components/Layout";
import { useBootstrap } from "./hooks/useBootstrap";
import Login from "./pages/Login";

// Code-split heavy screens (Dashboard pulls in the charting lib) so the
// login/initial load stays small.
const Dashboard = lazy(() => import("./pages/Dashboard"));
const ResourcePage = lazy(() => import("./components/ResourcePage"));
const AdminUsers = lazy(() => import("./pages/admin/Users"));
const AdminAudit = lazy(() => import("./pages/admin/Audit"));
// const AdminTrash = lazy(() => import("./pages/admin/Trash"));   // Recycle Bin, switched off
const MasterData = lazy(() => import("./components/MasterData"));
const DepartmentLogins = lazy(() => import("./components/DistrictManagers").then((m) => ({ default: m.DepartmentLogins })));
const Profile = lazy(() => import("./pages/Profile"));
const StudentsHub = lazy(() => import("./components/StudentsHub"));
const OrgStudents = lazy(() => import("./components/OrgStudents"));
const MyNotifications = lazy(() => import("./components/MyNotifications"));

// while the app checks who is logged in: the app's outline - sidebar, top bar
// and a page of blocks - rather than an empty screen
function FullSpinner() {
  return (
    <div className="app-skeleton" aria-label="Loading" aria-busy="true">
      <aside className="app-skeleton-side">
        {Array.from({ length: 7 }).map((_, i) => <div key={i} className="skeleton" />)}
      </aside>
      <div className="app-skeleton-main">
        <div className="app-skeleton-top"><div className="skeleton" style={{ width: 140, height: 18 }} /></div>
        <div className="app-skeleton-page">
          <div className="skeleton" style={{ width: 220, height: 26 }} />
          <div className="app-skeleton-cards">
            {Array.from({ length: 6 }).map((_, i) => <div key={i} className="skeleton" />)}
          </div>
          <div className="skeleton" style={{ height: 260, borderRadius: 12 }} />
        </div>
      </div>
    </div>
  );
}

function PageFallback() {
  return <div className="skeleton" style={{ width: "100%", height: 220, borderRadius: 12 }} />;
}

function Protected({ children }) {
  const { user, loading } = useAuth();
  if (loading) return <FullSpinner />;
  if (!user) return <Navigate to="/login" replace />;
  return children;
}

// An admin page this role doesn't have is not reachable by URL either.
function OnlyFor({ roles, children }) {
  const { user } = useAuth();
  return roles.includes(user?.role) ? children : <Navigate to="/app/dashboard" replace />;
}

// A section hidden from this role (lib/modules.js), or one the server doesn't
// give it, is not reachable by URL either.
function SectionRoute() {
  const { resource } = useParams();
  const { user } = useAuth();
  const { data: boot } = useBootstrap();
  const { search } = useLocation();
  // their own notifications (the admin-only list of everyone's stays hidden)
  if (resource === "notifications" && NOTIFY_ROLES.includes(user?.role)) return <MyNotifications />;
  if (isSectionHidden(user?.role, resource)) return <Navigate to="/app/dashboard" replace />;
  if (boot && !boot.resources?.[resource] && groupOf(MODULES[resource], user?.role) !== MASTER_GROUP) {
    return <Navigate to="/app/dashboard" replace />;
  }
  // master-data lists live on the tabbed Master Data page
  if (groupOf(MODULES[resource], user?.role) === MASTER_GROUP) return <Navigate to={`/app/master/${resource}${search}`} replace />;
  // a trainer's Students page: View / Manage tabs, adding many at once
  if (resource === "students" && user?.role === "VT") return <StudentsHub />;
  // an org admin's Students page: View / Verify tabs
  if (resource === "students" && user?.role === "OA") return <OrgStudents />;
  return <ResourcePage />;
}

export default function App() {
  const { user, loading } = useAuth();
  return (
    <Routes>
      <Route path="/login" element={loading ? <FullSpinner /> : user ? <Navigate to="/app/dashboard" replace /> : <Login />} />
      <Route path="/app" element={<Protected><Layout /></Protected>}>
        <Route index element={<Navigate to="dashboard" replace />} />
        <Route path="dashboard" element={<Suspense fallback={<PageFallback />}><Dashboard /></Suspense>} />
        <Route path="admin/department-logins" element={<OnlyFor roles={["SA"]}><Suspense fallback={<PageFallback />}><DepartmentLogins /></Suspense></OnlyFor>} />
        <Route path="admin/users" element={<OnlyFor roles={["SA", "OA"]}><Suspense fallback={<PageFallback />}><AdminUsers /></Suspense></OnlyFor>} />
        <Route path="admin/audit" element={<OnlyFor roles={["SA", "OA"]}><Suspense fallback={<PageFallback />}><AdminAudit /></Suspense></OnlyFor>} />
        {/* Recycle Bin: switched off - nothing can be deleted, so nothing to restore */}
        {/* <Route path="admin/trash" element={<Suspense fallback={<PageFallback />}><AdminTrash /></Suspense>} /> */}
        <Route path="profile" element={<Suspense fallback={<PageFallback />}><Profile /></Suspense>} />
        <Route path="master" element={<Suspense fallback={<PageFallback />}><MasterData /></Suspense>} />
        <Route path="master/:resource" element={<Suspense fallback={<PageFallback />}><MasterData /></Suspense>} />
        <Route path=":resource" element={<Suspense fallback={<PageFallback />}><SectionRoute /></Suspense>} />
      </Route>
      <Route path="*" element={<Navigate to="/app/dashboard" replace />} />
    </Routes>
  );
}
