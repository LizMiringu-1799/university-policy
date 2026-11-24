import { Navigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext.jsx";

/**
 * Route guard: redirects to /login when there's no session, or to /policies when a
 * `role` is required and the logged-in user doesn't have it. `forbidRole` is the inverse:
 * users with that role are sent to /admin/policies (used to keep admins off /welcome). Renders nothing while
 * AuthContext is still resolving the stored token, to avoid a flash of the login page.
 */
export default function ProtectedRoute({ role, forbidRole, children }) {
  const { user, token, loading } = useAuth();

  if (loading) return null;
  if (!token || !user) return <Navigate to="/" replace />;
  if (role && user.role !== role) return <Navigate to="/policies" replace />;
  if (forbidRole && user.role === forbidRole) return <Navigate to="/admin/policies" replace />;

  return children;
}
