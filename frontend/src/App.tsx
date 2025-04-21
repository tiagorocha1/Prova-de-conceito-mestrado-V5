// App.tsx
import React from "react";
import { BrowserRouter, Routes, Route, Link } from "react-router-dom";
import FaceDetectionComponent from "./FaceDetection";
import { PeopleList } from "./PeopleList";
import PresencaTable from "./PresencaTable";
import Presentes from "./Presentes";
import Login from "./Login";
import { useAuth } from "./AuthContext";
import FrameEstatisticas from "./FrameEstatisticas";
import FrameAgrupamentos from "./FrameAgrupamentos";

function App() {
  const { token, logout } = useAuth();

 
  if (!token) {
    return <Login />;
  }

  return (
    <BrowserRouter>
      <nav
        style={{
          padding: "10px 20px",
          backgroundColor: "#4285F4",
          color: "#fff",
          display: "flex",
          gap: "20px",
          alignItems: "center",
        }}
      >
        <Link to="/presencas" style={{ color: "#fff", textDecoration: "none" }}>
          Presenças
        </Link>
        <Link to="/pessoas" style={{ color: "#fff", textDecoration: "none" }}>
          Pessoas
        </Link>
        <Link to="/presentes" style={{ color: "#fff", textDecoration: "none" }}>
          Presentes
        </Link>

        <Link to="/estatisticas-frames" style={{ color: "#fff", textDecoration: "none" }}>
          Estatísticas
        </Link>

        <Link to="/agrupamentos" style={{ color: "#fff", textDecoration: "none" }}>
          Agrupamentos
        </Link>
        <button
          onClick={logout}
          style={{
            marginLeft: "auto",
            background: "none",
            border: "1px solid #fff",
            color: "#fff",
            padding: "4px 8px",
            cursor: "pointer",
          }}
        >
          Logout
        </button>
      </nav>
      <div style={{ padding: "20px", fontFamily: "Roboto, sans-serif" }}>
        <Routes>
          <Route path="/presencas" element={<PresencaTable />} />
          <Route path="/pessoas" element={<PeopleList />} />
          <Route path="/presentes" element={<Presentes />} />
          <Route path="/estatisticas-frames" element={<FrameEstatisticas />} />
          <Route path="/agrupamentos" element={<FrameAgrupamentos />} /> 
          {/* Você pode adicionar outras rotas protegidas aqui */}
        </Routes>
      </div>
    </BrowserRouter>
  );
}

export default App;
