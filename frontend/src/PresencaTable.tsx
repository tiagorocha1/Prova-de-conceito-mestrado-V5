import React, { useEffect, useState, useCallback } from "react";
import { useAuth } from "./AuthContext";

interface Presenca {
  id: string; // _id do MongoDB convertido para string
  uuid: string;
  tempo_processamento_total: string;
  tempo_captura_frame: string;
  tempo_deteccao: string;
  tempo_reconhecimento: string;
  foto_captura: string;
  tags: string[];
  tag_video: string;
  data_captura_frame?: string;
}

const PresencaTable: React.FC = () => {
  const [presencas, setPresencas] = useState<Presenca[]>([]);
  const [total, setTotal] = useState<number>(0);
  const [tempoProcessamentoFonte, setTempoProcessamentoFonte] = useState<number>(0); // Novo estado para o somatório
  const [totalPessoas, setTotalPessoas] = useState<number>(0);
  const [page, setPage] = useState<number>(1);
  const [loading, setLoading] = useState<boolean>(false);
  const [filterDate, setFilterDate] = useState<string>(""); // Estado para filtro por data
  const [filterTag, setFilterTag] = useState<string>("");   // Estado para filtro por tag_video
  const limit = 10; // Número de registros por página

  const { token } = useAuth();

  const fetchPresencas = useCallback(async (currentPage: number) => {
    setLoading(true);
    try {
      // Monta a URL com os parâmetros de paginação e filtros (caso preenchidos)
      let url = `http://localhost:8000/presencas?page=${currentPage}&limit=${limit}`;
      if (filterDate) {
        url += `&data_captura_frame=${filterDate}`;
      }
      if (filterTag) {
        url += `&tag_video=${filterTag}`;
      }

      const res = await fetch(url, { headers: { Authorization: `Bearer ${token}` } });
      const data = await res.json();
      setPresencas(data.presencas);
      setTotal(data.total);
      setTempoProcessamentoFonte(data.tempo_processamento_fonte); // Atualiza o somatório
      setTotalPessoas(data.total_de_pessoas); // Atualiza o total de pessoas
    } catch (error) {
      console.error("Erro ao buscar presenças:", error);
    }
    setLoading(false);
  }, [token, limit, filterDate, filterTag]);

  // Atualiza a listagem sempre que a página ou os filtros mudarem
  useEffect(() => {
    fetchPresencas(page);
  }, [fetchPresencas, page]);

  const deletePresenca = async (id: string) => {
    try {
      const res = await fetch(`http://localhost:8000/presencas/${id}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
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
      <h2>Registros de Presença</h2>
      {/* Filtros */}
      <div style={{ marginBottom: "20px", display: "flex", gap: "20px", alignItems: "center" }}>
        <div>
          <label htmlFor="dateFilter">Filtrar por data: </label>
          <input 
            type="date"
            id="dateFilter"
            value={filterDate}
            onChange={(e) => {
              setFilterDate(e.target.value);
              setPage(1); // Reseta para a página 1 ao filtrar
            }}
          />
        </div>
        <div>
          <label htmlFor="tagFilter">Filtrar por Tag: </label>
          <input 
            type="text"
            id="tagFilter"
            placeholder="Digite a tag"
            value={filterTag}
            onChange={(e) => {
              setFilterTag(e.target.value);
              setPage(1);
            }}
          />
        </div>
        <button 
          onClick={() => fetchPresencas(1)}
          style={{
            padding: "6px 12px",
            backgroundColor: "#4285F4",
            color: "#fff",
            border: "none",
            borderRadius: "4px",
            cursor: "pointer",
          }}
        >
          Buscar
        </button>
      </div>

      {/* Exibe o somatório do tempo de processamento da fonte */}
      <div style={{ marginBottom: "20px", fontWeight: "bold", color: "#FF0000" }}>
        Tempo Processamento Fonte: {tempoProcessamentoFonte} ms (
        {(tempoProcessamentoFonte / 1000).toFixed(2)} s / {(tempoProcessamentoFonte / 60000).toFixed(2)} min)
      </div>

      <div style={{ marginBottom: "20px", fontWeight: "bold"}}>
        Total de Pessoas: {totalPessoas} 
      </div>


      {loading ? (
        <p>Carregando...</p>
      ) : (
        <>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr>
                <th style={{ border: "1px solid #ccc", padding: "8px" }}>Foto Captura</th>
                <th style={{ border: "1px solid #ccc", padding: "8px" }}>Fonte</th>
                <th style={{ border: "1px solid #ccc", padding: "8px" }}>Tags</th>
                <th style={{ border: "1px solid #ccc", padding: "8px" }}>Captura (ms)</th>
                <th style={{ border: "1px solid #ccc", padding: "8px" }}>Detecção (ms)</th>
                <th style={{ border: "1px solid #ccc", padding: "8px" }}>Reconhecimento (ms)</th>
                <th style={{ border: "1px solid #ccc", padding: "8px" }}>Tempo Total (ms)</th>
                <th style={{ border: "1px solid #ccc", padding: "8px" }}>Data Captura</th>
                <th style={{ border: "1px solid #ccc", padding: "8px" }}>Ação</th>
              </tr>
            </thead>
            <tbody>
              {presencas.map((p) => (
                <tr key={p.id}>
                  <td style={{ border: "1px solid #ccc", padding: "8px", textAlign: "center" }}>
                    {p.foto_captura ? (
                      <img src={p.foto_captura} alt="Foto" style={{ width: "80px" }} />
                    ) : (
                      "Sem foto"
                    )}
                  </td>
                  <td style={{ border: "1px solid #ccc", padding: "8px" }}>{p.tag_video}</td>
                  <td style={{ border: "1px solid #ccc", padding: "8px" }}>
                    {p.tags && p.tags.length > 0 ? p.tags.join(", ") : "Nenhuma"}
                  </td>
                  <td style={{ border: "1px solid #ccc", padding: "8px" }}>{p.tempo_captura_frame}</td>
                  <td style={{ border: "1px solid #ccc", padding: "8px" }}>{p.tempo_deteccao}</td>
                  <td style={{ border: "1px solid #ccc", padding: "8px" }}>{p.tempo_reconhecimento}</td>
                  <td style={{ border: "1px solid #ccc", padding: "8px" }}>{p.tempo_processamento_total}</td>
                  <td style={{ border: "1px solid #ccc", padding: "8px" }}>
                    {p.data_captura_frame || "Sem data"}
                  </td>
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
          <div
            style={{
              marginTop: "10px",
              display: "flex",
              justifyContent: "center",
              alignItems: "center",
              gap: "10px",
            }}
          >
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
            <span>
              Página {page} de {totalPages}
            </span>
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
