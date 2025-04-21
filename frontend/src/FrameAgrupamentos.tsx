import React, { useEffect, useState } from "react";
import { useAuth } from "./AuthContext";
import "./FrameAgrupamentos.css";

interface Agrupamento {
  tag_video: string;
  total_frames: number;
  menor_qtd_faces_detectadas: number;
  uuid_menor_qtd: string;
  maior_qtd_faces_detectadas: number;
  uuid_maior_qtd: string;
  frames_sem_pessoas: number;
  total_pessoas: number;
  fps: number;
  duracao: number;
  grafico_detectados: string;      
  grafico_reconhecidos: string;

}

const FrameAgrupamentos: React.FC = () => {
  const { token } = useAuth();
  const [agrupamentos, setAgrupamentos] = useState<Agrupamento[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    const fetchAgrupamentos = async () => {
      setLoading(true);
      setErro(null);
      try {
        const res = await fetch("http://localhost:8000/frames/agrupamentos", {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        });

        if (!res.ok) {
          throw new Error("Erro ao buscar agrupamentos");
        }

        const data = await res.json();
        setAgrupamentos(data);
      } catch (err) {
        console.error(err);
        setErro("Erro ao carregar agrupamentos");
      }
      setLoading(false);
    };

    fetchAgrupamentos();
  }, [token]);

  return (
    <div style={{ padding: "20px", fontFamily: "Roboto, sans-serif" }}>
      <h2>Agrupamentos por Tag de Vídeo</h2>
      {loading && <p>Carregando...</p>}
      {erro && <p style={{ color: "red" }}>{erro}</p>}
      {!loading && !erro && (
        <table style={{ width: "100%", borderCollapse: "collapse", marginTop: "20px" }}>
          <thead>
            <tr>
              <th style={thStyle}>ID</th>
              <th style={thStyle}>Min Detec.</th>
              <th style={thStyle}>Max Detec.</th>
              <th style={thStyle}>Pessoas Total</th>
              <th style={thStyle}>Duração</th>
              <th style={thStyle}>FPS</th>
              <th style={thStyle}>Total Frames</th>
              <th style={thStyle}>Frames Vazios</th>
              <th style={thStyle}>Gráfico Detecção</th>
              <th style={thStyle}>Gráfico Reconhecimento</th>

            </tr>
          </thead>
          <tbody>
            {agrupamentos.map((a, index) => (
              <tr key={index}>
                <td style={tdStyle}>{a.tag_video}</td>
                <td style={tdStyle}>{a.menor_qtd_faces_detectadas}</td>
                <td style={tdStyle}>{a.maior_qtd_faces_detectadas}</td>
                <td style={tdStyle}>{a.total_pessoas}</td>
                <td style={tdStyle}>{a.duracao}</td>
                <td style={tdStyle}>{a.fps}</td>
                <td style={tdStyle}>{a.total_frames}</td>
                <td style={tdStyle}>{a.frames_sem_pessoas}</td>
                <td style={tdStyle}>
                 
                  <img src={`${process.env.REACT_APP_API_URL}${a.grafico_detectados}`} alt="Gráfico Detec." style={{ width: "140px" }} className="zoomable-img"/>

                </td>
                <td style={tdStyle}>
                  
                  <img src={`${process.env.REACT_APP_API_URL}${a.grafico_reconhecidos}`} alt="Gráfico Detec." style={{ width: "140px" }} className="zoomable-img"/>

                </td>

              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
};

const thStyle: React.CSSProperties = {
  border: "1px solid #ccc",
  padding: "8px",
  backgroundColor: "#f2f2f2",
  fontWeight: "bold",
};

const tdStyle: React.CSSProperties = {
  border: "1px solid #ccc",
  padding: "8px",
  textAlign: "center",
};

export default FrameAgrupamentos;
