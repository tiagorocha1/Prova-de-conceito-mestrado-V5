// App.tsx
import React from "react";
import { BrowserRouter, Routes, Route, Link } from "react-router-dom";

import { useAuth } from "./AuthContext";

import Login from "./Login";
import { PeopleList } from "./PeopleList";
import PresencaTable from "./PresencaTable";
import Presentes from "./Presentes";
import FrameEstatisticas from "./FrameEstatisticas";
import FrameAgrupamentos from "./FrameAgrupamentos";
import FontesDashboard from "./FontesDashboard";


function App() {
  const { token, logout } = useAuth();

  if (!token) {
    return <Login />;
  }

  return (
    <BrowserRouter>
      {/* NAVBAR */}
      <header
        style={{
          backgroundColor: "#1976d2",
          color: "#fff",
          padding: "10px 20px",
          display: "flex",
          alignItems: "center",
          boxShadow: "0 2px 4px rgba(0,0,0,0.15)",
          fontFamily: "Roboto, sans-serif",
        }}
      >
        {/* Left side: links */}
        <nav
          style={{
            display: "flex",
            gap: "16px",
            flexWrap: "wrap",
            alignItems: "center",
          }}
        >
          <NavItem to="/presencas" label="Presenças" />
          <NavItem to="/pessoas" label="Pessoas" />
          <NavItem to="/presentes" label="Presentes" />
          <NavItem to="/estatisticas-frames" label="Estatísticas" />
          <NavItem to="/agrupamentos" label="Agrupamentos" />
          <NavItem to="/fontes" label="Fontes / Execuções" />
        </nav>

        {/* Right side: Logout */}
        <button
          onClick={logout}
          style={{
            marginLeft: "auto",
            backgroundColor: "rgba(255,255,255,0.15)",
            border: "1px solid rgba(255,255,255,0.6)",
            color: "#fff",
            padding: "6px 10px",
            fontSize: "13px",
            lineHeight: 1.2,
            borderRadius: "4px",
            cursor: "pointer",
          }}
          onMouseOver={(e) => {
            (e.currentTarget as HTMLButtonElement).style.backgroundColor =
              "rgba(255,255,255,0.25)";
          }}
          onMouseOut={(e) => {
            (e.currentTarget as HTMLButtonElement).style.backgroundColor =
              "rgba(255,255,255,0.15)";
          }}
        >
          Logout
        </button>
      </header>

      {/* PAGE CONTENT */}
      <main
        style={{
          padding: "20px",
          fontFamily: "Roboto, sans-serif",
          backgroundColor: "#f5f5f5",
          minHeight: "calc(100vh - 56px)",
        }}
      >
        <div
          style={{
            backgroundColor: "#fff",
            border: "1px solid #ddd",
            borderRadius: "8px",
            boxShadow: "0 2px 4px rgba(0,0,0,0.05)",
            padding: "20px",
          }}
        >
          <Routes>
            <Route path="/presencas" element={<PresencaTable />} />
            <Route path="/pessoas" element={<PeopleList />} />
            <Route path="/presentes" element={<Presentes />} />
            <Route path="/estatisticas-frames" element={<FrameEstatisticas />} />
            <Route path="/agrupamentos" element={<FrameAgrupamentos />} />
            <Route path="/fontes" element={<FontesDashboard />} />
            <Route path="*" element={<PresencaTable />} />
          </Routes>
        </div>
      </main>
    </BrowserRouter>
  );
}

// componente pequeno pra deixar os links todos consistentes e com hover
const NavItem: React.FC<{ to: string; label: string }> = ({ to, label }) => (
  <Link
    to={to}
    style={{
      color: "#fff",
      textDecoration: "none",
      fontSize: "14px",
      fontWeight: 500,
      padding: "6px 8px",
      borderRadius: "4px",
    }}
    onMouseOver={(e) => {
      (e.currentTarget as HTMLAnchorElement).style.backgroundColor =
        "rgba(255,255,255,0.15)";
    }}
    onMouseOut={(e) => {
      (e.currentTarget as HTMLAnchorElement).style.backgroundColor = "transparent";
    }}
  >
    {label}
  </Link>
);

export default App;
