import { Link } from "react-router-dom";
import { useAuth } from "../context/AuthContext.jsx";
import Button from "./Button.jsx";

export default function AppHeader() {
  const { user, logout } = useAuth();

  return (
    <header className="app-header">
      <Link to="/policies" className="brand-mark app-header-brand">
        UPMAN
      </Link>
      <div className="app-header-actions">
        {user?.role === "admin" && (
          <Link to="/admin/policies" className="app-header-link">
            Manage Policies
          </Link>
        )}
        <span className="role-badge">{user?.role}</span>
        <Button variant="secondary" onClick={logout}>
          Log out
        </Button>
      </div>
    </header>
  );
}
