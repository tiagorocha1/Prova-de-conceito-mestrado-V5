import React from "react";
import { BrowserRouter, Routes, Route, Link } from "react-router-dom";
import FaceDetectionComponent from "./FaceDetection";
import { PeopleList } from "./PeopleList";
import PresencaTable from "./PresencaTable";


function App() {
  return (
    <BrowserRouter>
      <nav
        style={{
          padding: "10px 20px",
          backgroundColor: "#4285F4",
          color: "#fff",
          display: "flex",
          gap: "20px",
        }}
      >
        <Link to="/presencas" style={{ color: "#fff", textDecoration: "none" }}>
         Presenças
        </Link>

        <Link to="/pessoas" style={{ color: "#fff", textDecoration: "none" }}>
          Pessoas
        </Link>

      </nav>
      <div style={{ padding: "20px", fontFamily: "Roboto, sans-serif" }}>
        <Routes>
          <Route path="/presencas" element={<PresencaTable />} />
          <Route path="/pessoas" element={<PeopleList />} />
        </Routes>
      </div>
    </BrowserRouter>
  );
}

export default App;
