import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../context/AuthContext.jsx";
import { adminEscalationsApi } from "../api/client.js";
import Button from "./Button.jsx";

const OPEN_COUNT_POLL_MS = 20000;

/**
 * Site header: brand link, role-appropriate nav (admin gets Manage Policies, Student
 * Questions, Ratings, and Analytics; everyone else gets Chat History and My Questions),
 * a role badge, and logout. For an admin, also polls the open-escalation count every
 * OPEN_COUNT_POLL_MS and shows it as a badge on "Student Questions" so a new question
 * is visible from anywhere in the admin UI.
 */
export default function AppHeader() {
  const { user, token, logout } = useAuth();
  const [openCount, setOpenCount] = useState(0);

  useEffect(() => {
    if (user?.role !== "admin") return undefined;

    let cancelled = false;
    const poll = () => {
      adminEscalationsApi
        .openCount(token)
        .then((data) => {
          if (!cancelled) setOpenCount(data.count);
        })
        .catch(() => {});
    };

    poll();
    const timer = setInterval(poll, OPEN_COUNT_POLL_MS);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [user?.role, token]);

  return (
    <header className="app-header">
      <Link to="/policies" className="brand-mark app-header-brand">
        UPMAN
      </Link>
      <div className="app-header-actions">
        {user?.role === "admin" ? (
          <>
            <Link to="/admin/policies" className="app-header-link">
              Manage Policies
            </Link>
            <Link to="/admin/questions" className="app-header-link">
              Student Questions
              {openCount > 0 && <span className="header-badge">{openCount}</span>}
            </Link>
            <Link to="/admin/ratings" className="app-header-link">
              Ratings
            </Link>
            <Link to="/admin/analytics" className="app-header-link">
              Analytics
            </Link>
          </>
        ) : (
          <>
            <Link to="/chat-history" className="app-header-link">
              Chat History
            </Link>
            <Link to="/my-questions" className="app-header-link">
              My Questions
            </Link>
          </>
        )}
        <span className="role-badge">{user?.role}</span>
        <Button variant="secondary" onClick={logout}>
          Log out
        </Button>
      </div>
    </header>
  );
}
