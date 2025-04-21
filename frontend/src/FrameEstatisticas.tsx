import React, { useState, useEffect } from "react";
import { useAuth } from "./AuthContext";

const FrameEstatisticas: React.FC = () => {
  const [tag, setTag] = useState<string>("");
  const [estatisticas, setEstatisticas] = useState<any>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [erro, setErro] = useState<string | null>(null);

  const { token } = useAuth();

  const buscarEstatisticas = async () => {
    if (!tag.trim()) return;

    setLoading(true);
    setErro(null);
    try {
      const res = await fetch(`http://localhost:8000/frames/estatisticas?tag_video=${encodeURIComponent(tag)}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error("Erro ao buscar estatísticas");
      const data = await res.json();
      setEstatisticas(data);
    } catch (err) {
      console.error(err);
      setErro("Erro ao buscar estatísticas.");
    }
    setLoading(false);
  };

  return (
    <div style={{ padding: "20px", fontFamily: "Roboto, sans-serif" }}>
      <h2>Estatísticas de Frames por Tag</h2>

      <div style={{ marginBottom: "20px", display: "flex", gap: "10px", alignItems: "center" }}>
        <input
          type="text"
          placeholder="Digite a tag do vídeo"
          value={tag}
          onChange={(e) => setTag(e.target.value)}
          style={{ padding: "6px", width: "200px", fontSize: "14px" }}
        />
        <button
          onClick={buscarEstatisticas}
          style={{
            padding: "6px 12px",
            backgroundColor: "#4285F4",
            color: "#fff",
            border: "none",
            borderRadius: "4px",
            cursor: "pointer",
            fontSize: "14px",
          }}
        >
          Buscar
        </button>
      </div>

      {loading && <p>Carregando...</p>}
      {erro && <p style={{ color: "red" }}>{erro}</p>}

      {estatisticas && (
        <div
          style={{
            border: "1px solid #ccc",
            borderRadius: "12px",
            padding: "24px",
            backgroundColor: "#ffffff",
            maxWidth: "700px",
            boxShadow: "0 2px 6px rgba(0,0,0,0.1)",
            lineHeight: "1.8",
          }}
        >
          <h3 style={{ marginBottom: "16px", color: "#333" }}>
            Estatísticas da tag: <strong>{estatisticas.tag_video}</strong>
          </h3>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px" }}>
            <div><strong>Total de frames:</strong> {estatisticas.total_frames}</div>
            <div><strong>Frames sem pessoas:</strong> {estatisticas.frames_sem_pessoas}</div>
            <div>
              <strong>Menor qtd. detectada:</strong> {estatisticas.menor_qtd_faces_detectadas}
              {estatisticas.uuid_menor_qtd && (
                <div style={{ fontSize: "12px", color: "#666" }}>
                  UUID: {estatisticas.uuid_menor_qtd}
                </div>
              )}
            </div>
            <div>
              <strong>Maior qtd. detectada:</strong> {estatisticas.maior_qtd_faces_detectadas}
              {estatisticas.uuid_maior_qtd && (
                <div style={{ fontSize: "12px", color: "#666" }}>
                  UUID: {estatisticas.uuid_maior_qtd}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default FrameEstatisticas;
