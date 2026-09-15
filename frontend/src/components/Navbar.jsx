import { useNavigate } from "react-router-dom";
import { LogOut } from "lucide-react";
import { logoutUser } from "../services/api";

const PAGE_META = {
  "/dashboard": { title: "Dashboard", subtitle: "Current risk posture at a glance" },
  "/analyze": { title: "Analyze", subtitle: "Check a call or clip for voice cloning" },
  "/history": { title: "History", subtitle: "Every past analysis, searchable" },
  "/settings": { title: "Settings", subtitle: "Detection and verification preferences" },
};

export default function Navbar({ user, currentPath }) {
  const navigate = useNavigate();
  const meta = PAGE_META[currentPath] || { title: "TrueLine", subtitle: "" };

  const handleLogout = async () => {
    await logoutUser();
    navigate("/login");
  };

  return (
    <header className="navbar">
      <div>
        <div className="navbar-title">{meta.title}</div>
        <div className="navbar-subtitle">{meta.subtitle}</div>
      </div>
      <div className="navbar-user">
        {user && <span className="navbar-username">{user.username}</span>}
        <button className="btn btn-secondary" onClick={handleLogout}>
          <LogOut size={14} />
          Log out
        </button>
      </div>
    </header>
  );
}
