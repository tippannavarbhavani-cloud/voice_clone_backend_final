import { Navigate } from "react-router-dom";
import { tokenStore } from "../services/api";

export default function ProtectedRoute({ children }) {
  if (!tokenStore.getAccess()) {
    return <Navigate to="/login" replace />;
  }
  return children;
}
