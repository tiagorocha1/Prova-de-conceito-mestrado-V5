import React, { useEffect, useState, useCallback } from "react";

interface Presenca {
  id: string; // _id do MongoDB convertido para string
  uuid: string;
  data_captura_frame: string;
  hora_captura_frame: string;
  foto_captura: string;
  tags: string[];
  inicio: number;              // Timestamp de início (em milissegundos)
  fim: number;                 // Timestamp de fim (em milissegundos)
  tempo_processamento: number; // Tempo de processamento (em milissegundos)
}

const PresencaTable: React.FC = () => {
  const [presencas, setPresencas] = useState<Presenca[]>([]);
  const [total, setTotal] = useState<number>(0);
  const [page, setPage] = useState<number>(1);
  const [loading, setLoading] = useState<boolean>(false);
  const limit = 10; // Número de registros por página

  // Obtém a data local no formato YYYY-MM-DD
  const todayDate = new Date();
  const localDate = `${todayDate.getFullYear()}-${("0" + (todayDate.getMonth() + 1)).slice(-2)}-${("0" + todayDate.getDate()).slice(-2)}`;

  const fetchPresencas = useCallback(async (currentPage: number) => {
    setLoading(true);
    try {
      const res = await fetch(
        `http://localhost:8000/presencas?date=${localDate}&page=${currentPage}&limit=${limit}`
      );
      const data = await res.json();
      setPresencas(data.presencas);
      setTotal(data.total);
    } catch (error) {
      console.error("Erro ao buscar presenças:", error);
    }
    setLoading(false);
  }, [localDate, limit]);

  useEffect(() => {
    fetchPresencas(page);
  }, [fetchPresencas, page]);

  const deletePresenca = async (id: string) => {
    try {
      const res = await fetch(`http://localhost:8000/presencas/${id}`, {
        method: "DELETE",
      });
      if (res.ok) {
        fetchPresencas(page);
      } else {
        console.error("Erro ao deletar presença", id);
      }
    } catch (error) {
      console.error("Erro ao deletar presença:", error);
    }
  };

  const totalPages = Math.ceil(total / limit);

  return (
    <div style={{ padding: "20px", fontFamily: "Roboto, sans-serif" }}>
      <h2>Registros de Presença - {localDate}</h2>
      {loading ? (
        <p>Carregando...</p>
      ) : (
        <>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr>
                <th style={{ border: "1px solid #ccc", padding: "8px" }}>ID</th>
                <th style={{ border: "1px solid #ccc", padding: "8px" }}>Pessoa (UUID)</th>
                <th style={{ border: "1px solid #ccc", padding: "8px" }}>Data Captura Frame</th>
                <th style={{ border: "1px solid #ccc", padding: "8px" }}>Hora Captura Frame</th>
                <th style={{ border: "1px solid #ccc", padding: "8px" }}>Foto Captura</th>
                <th style={{ border: "1px solid #ccc", padding: "8px" }}>Tags</th>
                <th style={{ border: "1px solid #ccc", padding: "8px" }}>Início</th>
                <th style={{ border: "1px solid #ccc", padding: "8px" }}>Fim</th>
                <th style={{ border: "1px solid #ccc", padding: "8px" }}>Tempo Processamento (ms)</th>
                <th style={{ border: "1px solid #ccc", padding: "8px" }}>Ação</th>
              </tr>
            </thead>
            <tbody>
              {presencas.map((p) => (
                <tr key={p.id}>
                  <td style={{ border: "1px solid #ccc", padding: "8px" }}>{p.id}</td>
                  <td style={{ border: "1px solid #ccc", padding: "8px" }}>{p.uuid}</td>
                  <td style={{ border: "1px solid #ccc", padding: "8px" }}>{p.data_captura_frame}</td>
                  <td style={{ border: "1px solid #ccc", padding: "8px" }}>{p.hora_captura_frame}</td>
                  <td style={{ border: "1px solid #ccc", padding: "8px", textAlign: "center" }}>
                    {p.foto_captura ? (
                      <img src={p.foto_captura} alt="Foto" style={{ width: "80px" }} />
                    ) : (
                      "Sem foto"
                    )}
                  </td>
                  <td style={{ border: "1px solid #ccc", padding: "8px" }}>
                    {p.tags && p.tags.length > 0 ? p.tags.join(", ") : "Nenhuma"}
                  </td>
                  <td style={{ border: "1px solid #ccc", padding: "8px" }}>{p.inicio}</td>
                  <td style={{ border: "1px solid #ccc", padding: "8px" }}>{p.fim}</td>
                  <td style={{ border: "1px solid #ccc", padding: "8px" }}>{p.tempo_processamento}</td>
                  <td style={{ border: "1px solid #ccc", padding: "8px", textAlign: "center" }}>
                    <button
                      onClick={() => deletePresenca(p.id)}
                      style={{
                        backgroundColor: "#d93025",
                        color: "#fff",
                        border: "none",
                        padding: "6px 12px",
                        borderRadius: "4px",
                        cursor: "pointer",
                      }}
                    >
                      Deletar
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <div style={{ marginTop: "10px", display: "flex", justifyContent: "center", alignItems: "center", gap: "10px" }}>
            <button
              onClick={() => setPage((prev) => Math.max(prev - 1, 1))}
              disabled={page === 1}
              style={{
                padding: "8px 12px",
                backgroundColor: "#4285F4",
                color: "#fff",
                border: "none",
                borderRadius: "4px",
                cursor: page === 1 ? "not-allowed" : "pointer",
              }}
            >
              Anterior
            </button>
            <span>Página {page} de {totalPages}</span>
            <button
              onClick={() => setPage((prev) => Math.min(prev + 1, totalPages))}
              disabled={page === totalPages}
              style={{
                padding: "8px 12px",
                backgroundColor: "#4285F4",
                color: "#fff",
                border: "none",
                borderRadius: "4px",
                cursor: page === totalPages ? "not-allowed" : "pointer",
              }}
            >
              Próxima
            </button>
          </div>
        </>
      )}
    </div>
  );
};

export default PresencaTable;
