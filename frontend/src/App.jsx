import { Routes, Route } from "react-router-dom";
import LoginPage from "./pages/LoginPage.jsx";
import RegisterPage from "./pages/RegisterPage.jsx";
import PolicyLibraryPage from "./pages/PolicyLibraryPage.jsx";
import PolicyReaderPage from "./pages/PolicyReaderPage.jsx";
import MyQuestionsPage from "./pages/MyQuestionsPage.jsx";
import AdminPoliciesPage from "./pages/admin/AdminPoliciesPage.jsx";
import AdminEscalationsPage from "./pages/admin/AdminEscalationsPage.jsx";
import ProtectedRoute from "./routes/ProtectedRoute.jsx";
import ThemeToggle from "./components/ThemeToggle.jsx";

/**
 * Top-level route table. `/` and `/register` are public; everything else requires a
 * session via ProtectedRoute, and the `/admin/*` routes additionally require role="admin".
 */
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
          path="/my-questions"
          element={
            <ProtectedRoute>
              <MyQuestionsPage />
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
        <Route
          path="/admin/questions"
          element={
            <ProtectedRoute role="admin">
              <AdminEscalationsPage />
            </ProtectedRoute>
          }
        />
      </Routes>
    </>
  );
}
