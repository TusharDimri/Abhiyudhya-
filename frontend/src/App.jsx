import { Suspense, lazy } from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import { useAuth } from "./lib/auth";
import Layout from "./components/Layout";
import Login from "./pages/Login";

// Code-split heavy screens (Dashboard pulls in the charting lib) so the
// login/initial load stays small.
const Dashboard = lazy(() => import("./pages/Dashboard"));
const ResourcePage = lazy(() => import("./components/ResourcePage"));
const AdminUsers = lazy(() => import("./pages/admin/Users"));
const AdminAudit = lazy(() => import("./pages/admin/Audit"));
const AdminTrash = lazy(() => import("./pages/admin/Trash"));

function FullSpinner() {
  return (
    <div style={{ height: "100vh", display: "grid", placeItems: "center" }}>
      <div className="skeleton" style={{ width: 180, height: 20 }} />
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

export default function App() {
  const { user, loading } = useAuth();
  return (
    <Routes>
      <Route path="/login" element={loading ? <FullSpinner /> : user ? <Navigate to="/app/dashboard" replace /> : <Login />} />
      <Route path="/app" element={<Protected><Layout /></Protected>}>
        <Route index element={<Navigate to="dashboard" replace />} />
        <Route path="dashboard" element={<Suspense fallback={<PageFallback />}><Dashboard /></Suspense>} />
        <Route path="admin/users" element={<Suspense fallback={<PageFallback />}><AdminUsers /></Suspense>} />
        <Route path="admin/audit" element={<Suspense fallback={<PageFallback />}><AdminAudit /></Suspense>} />
        <Route path="admin/trash" element={<Suspense fallback={<PageFallback />}><AdminTrash /></Suspense>} />
        <Route path=":resource" element={<Suspense fallback={<PageFallback />}><ResourcePage /></Suspense>} />
      </Route>
      <Route path="*" element={<Navigate to="/app/dashboard" replace />} />
    </Routes>
  );
}
