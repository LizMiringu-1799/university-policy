import { Routes, Route } from "react-router-dom";
import LoginPage from "./pages/LoginPage.jsx";
import RegisterPage from "./pages/RegisterPage.jsx";
import PolicyLibraryPage from "./pages/PolicyLibraryPage.jsx";
import PolicyReaderPage from "./pages/PolicyReaderPage.jsx";
import AdminPoliciesPage from "./pages/admin/AdminPoliciesPage.jsx";
import ProtectedRoute from "./routes/ProtectedRoute.jsx";
import ThemeToggle from "./components/ThemeToggle.jsx";

export default function App() {
  return (
    <>
      <ThemeToggle />
      <Routes>
        <Route path="/" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route
          path="/policies"
          element={
            <ProtectedRoute>
              <PolicyLibraryPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/policies/:id"
          element={
            <ProtectedRoute>
              <PolicyReaderPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/admin/policies"
          element={
            <ProtectedRoute role="admin">
              <AdminPoliciesPage />
            </ProtectedRoute>
          }
        />
      </Routes>
    </>
  );
}
