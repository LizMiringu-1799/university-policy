import { Navigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext.jsx";

/**
 * Route guard: redirects to /login when there's no session, or to /policies when a
 * `role` is required and the logged-in user doesn't have it. Renders nothing while
 * AuthContext is still resolving the stored token, to avoid a flash of the login page.
 */
export default function ProtectedRoute({ role, children }) {
  const { user, token, loading } = useAuth();

  if (loading) return null;
  if (!token || !user) return <Navigate to="/" replace />;
  if (role && user.role !== role) return <Navigate to="/policies" replace />;

  return children;
}
