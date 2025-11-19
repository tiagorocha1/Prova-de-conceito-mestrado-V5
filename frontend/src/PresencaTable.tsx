import React, { useEffect, useState } from "react";
import { useAuth } from "./AuthContext";

interface Presenca {
  id: string;
  uuid: string | null;
  tempo_processamento_total: number | null;
  tempo_captura_frame: number | null;
  tempo_deteccao: number | null;
  tempo_reconhecimento: number | null;
  foto_captura: string | null;
  tag_video: string | null;
  tags: string[];
  data_captura_frame: string | null;
  timestamp_inicial: number | null;
  timestamp_final: number | null;
  tempo_fila: number | null;
  similarity_value: number | null;
  confusionCategory?: string | null;
  gold_standard?: string | null;
}

interface ApiResponse {
  presencas: Presenca[];
  total: number;
  tempo_processamento: number;
  tempo_fila: number;
  total_de_pessoas: number;
}

const PresencaTable: React.FC = () => {
  const { token } = useAuth();

  // filtros
  const [tagVideoFiltro, setTagVideoFiltro] = useState<string>("");
  const [dataFiltro, setDataFiltro] = useState<string>("");

  // paginação
  const [page, setPage] = useState<number>(1);
  const [limit] = useState<number>(1000);

  // dados
  const [presencas, setPresencas] = useState<Presenca[]>([]);
  const [total, setTotal] = useState<number>(0);
  const [tempoProcessamentoTotal, setTempoProcessamentoTotal] = useState<number>(0);
  const [tempoFilaTotal, setTempoFilaTotal] = useState<number>(0);
  const [totalPessoas, setTotalPessoas] = useState<number>(0);

  const [loading, setLoading] = useState<boolean>(false);
  const [erro, setErro] = useState<string | null>(null);

  // util: formata timestamp epoch(segundos) -> yyyy-mm-dd hh:mm:ss
  const formatTimestamp = (ts: number | null): string => {
    if (ts === null || ts === undefined) return "-";
    const date = new Date(ts * 1000);
    const yyyy = date.getFullYear();
    const mm = String(date.getMonth() + 1).padStart(2, "0");
    const dd = String(date.getDate()).padStart(2, "0");
    const hh = String(date.getHours()).padStart(2, "0");
    const mi = String(date.getMinutes()).padStart(2, "0");
    const ss = String(date.getSeconds()).padStart(2, "0");
    return `${yyyy}-${mm}-${dd} ${hh}:${mi}:${ss}`;
  };

  // util: formata número
  const fmt = (v: number | null, digits = 3): string => {
    if (v === null || v === undefined) return "-";
    if (Number.isInteger(v)) return String(v);
    return v.toFixed(digits);
  };

  // carrega dados da API /presencas
  const carregarPresencas = async () => {
    if (!token) return;
    setLoading(true);
    setErro(null);

    try {
      const params = new URLSearchParams();
      params.append("page", page.toString());
      params.append("limit", limit.toString());
      if (tagVideoFiltro.trim() !== "") params.append("tag_video", tagVideoFiltro.trim());
      if (dataFiltro.trim() !== "") params.append("data_captura_frame", dataFiltro.trim());

      const resp = await fetch(`http://localhost:8000/presencas?${params.toString()}`, {
        method: "GET",
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (!resp.ok) {
        const text = await resp.text();
        throw new Error(`Erro ao buscar presenças: ${resp.status} - ${text}`);
      }

      const data: ApiResponse = await resp.json();

      setPresencas(data.presencas || []);
      setTotal(data.total ?? 0);
      setTempoProcessamentoTotal(data.tempo_processamento ?? 0);
      setTempoFilaTotal(data.tempo_fila ?? 0);
      setTotalPessoas(data.total_de_pessoas ?? 0);
    } catch (err: any) {
      console.error(err);
      setErro(err.message || "Erro ao carregar presenças");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    carregarPresencas();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, tagVideoFiltro, dataFiltro, token]);

  const totalPaginas = Math.ceil(total / limit) || 1;

  // PATCH helper genérico
  const patchPresenca = async (
    presencaId: string,
    body: Record<string, any>
  ): Promise<Presenca | null> => {
    if (!token) return null;
    const resp = await fetch(`http://localhost:8000/presencas/${presencaId}`, {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify(body),
    });

    if (!resp.ok) {
      const text = await resp.text();
      throw new Error(`Erro ao atualizar presença: ${resp.status} - ${text}`);
    }

    // backend retorna subset dos campos
    const updated = await resp.json();

    // convertemos o retorno parcial em algo que bate com Presenca
    const mapped: Presenca = {
      id: updated.id,
      uuid: updated.uuid ?? null,
      tempo_processamento_total: updated.tempo_processamento_total ?? null,
      tempo_captura_frame: null,
      tempo_deteccao: null,
      tempo_reconhecimento: null,
      foto_captura: updated.foto_captura ?? null,
      tag_video: updated.tag_video ?? null,
      tags: [],
      data_captura_frame: null,
      timestamp_inicial: null,
      timestamp_final: null,
      tempo_fila: null,
      similarity_value: null,
      confusionCategory: updated.confusionCategory ?? "",
      gold_standard: updated.gold_standard ?? "",
    };

    return mapped;
  };

  // handler -> select de TP/TN/FP/FN
  const handleChangeConfusion = async (presencaId: string, newValue: string) => {
    try {
      const updated = await patchPresenca(presencaId, {
        confusionCategory: newValue,
      });
      if (updated) {
        setPresencas((current) =>
          current.map((p) =>
            p.id === presencaId
              ? { ...p, confusionCategory: updated.confusionCategory || "" }
              : p
          )
        );
      }
    } catch (err: any) {
      console.error(err);
      alert(err.message || "Falha ao atualizar classificação");
    }
  };

  // handler -> input gold_standard
  const handleChangeGoldStandard = async (presencaId: string, newValue: string) => {
    try {
      const updated = await patchPresenca(presencaId, {
        gold_standard: newValue,
      });
      if (updated) {
        setPresencas((current) =>
          current.map((p) =>
            p.id === presencaId
              ? { ...p, gold_standard: updated.gold_standard || "" }
              : p
          )
        );
      }
    } catch (err: any) {
      console.error(err);
      alert(err.message || "Falha ao atualizar gold standard");
    }
  };

  return (
    <div style={{ padding: "20px" }}>
      <h2>Registros de Presença</h2>

      {/* Filtros e resumo */}
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          gap: "16px",
          marginBottom: "16px",
          alignItems: "flex-end",
          background: "#f5f5f5",
          padding: "12px",
          borderRadius: "8px",
          border: "1px solid #ddd",
        }}
      >
        <div style={{ display: "flex", flexDirection: "column" }}>
          <label style={{ fontWeight: "bold" }}>Filtrar por tag_video:</label>
          <input
            type="text"
            value={tagVideoFiltro}
            onChange={(e) => {
              setPage(1);
              setTagVideoFiltro(e.target.value);
            }}
            placeholder="ex: A01-ENTRADA"
            style={{ padding: "6px 8px", minWidth: "200px" }}
          />
        </div>

        <div style={{ display: "flex", flexDirection: "column" }}>
          <label style={{ fontWeight: "bold" }}>Filtrar por data (data_captura_frame):</label>
          <input
            type="text"
            value={dataFiltro}
            onChange={(e) => {
              setPage(1);
              setDataFiltro(e.target.value);
            }}
            placeholder="ex: 14-03-2025"
            style={{ padding: "6px 8px", minWidth: "200px" }}
          />
        </div>

        <div style={{ fontSize: "14px", color: "#555" }}>
          <div>Total registros exibidos: {total}</div>
          <div>
            Página {page} / {totalPaginas}
          </div>
          <div>Pessoas distintas no filtro: {totalPessoas}</div>
          <div>Soma tempo processamento: {fmt(tempoProcessamentoTotal, 3)} s</div>
          <div>Soma tempo fila: {fmt(tempoFilaTotal, 3)} s</div>
        </div>
      </div>

      {erro && (
        <div
          style={{
            backgroundColor: "#ffe0e0",
            border: "1px solid #ff8080",
            padding: "10px",
            marginBottom: "16px",
            borderRadius: "6px",
            color: "#a00",
          }}
        >
          {erro}
        </div>
      )}

      {loading ? (
        <div>Carregando...</div>
      ) : (
        <div style={{ overflowX: "auto" }}>
          <table
            style={{
              borderCollapse: "collapse",
              width: "100%",
              minWidth: "1700px",
              fontSize: "13px",
            }}
          >
            <thead>
              <tr style={{ background: "#1976d2", color: "#fff", textAlign: "left" }}>
                {[
                  "Foto",
                  "UUID",
                  "Tag Vídeo",
                  "Data Captura",
                  "Início Proc.",
                  "Fim Proc.",
                  "Tempo Proc. Total (s)",
                  "Captura (s)",
                  "Detecção (s)",
                  "Reconhecimento (s)",
                  "Tempo Fila (s)",
                  "Similarity",
                  "Confusão",
                  "Gold Std",
                ].map((header) => (
                  <th
                    key={header}
                    style={{
                      padding: "8px 10px",
                      border: "1px solid #145a96",
                      fontWeight: "bold",
                      fontSize: "12px",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {header}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {presencas.length === 0 ? (
                <tr>
                  <td
                    colSpan={14}
                    style={{
                      padding: "16px",
                      border: "1px solid #ddd",
                      textAlign: "center",
                      color: "#666",
                    }}
                  >
                    Nenhum registro encontrado.
                  </td>
                </tr>
              ) : (
                presencas.map((p) => (
                  <tr key={p.id} style={{ background: "#fafafa" }}>
                    {/* Foto */}
                    <td
                      style={{
                        padding: "8px 10px",
                        border: "1px solid #ddd",
                        verticalAlign: "top",
                        fontSize: "12px",
                        whiteSpace: "nowrap",
                      }}
                    >
                      {p.foto_captura ? (
                        <img
                          src={p.foto_captura}
                          alt="captura"
                          style={{
                            width: "64px",
                            height: "64px",
                            objectFit: "cover",
                            borderRadius: "4px",
                            border: "1px solid #ccc",
                          }}
                        />
                      ) : (
                        "-"
                      )}
                    </td>

                    {/* UUID */}
                    <td style={tdStyle}>{p.uuid || "-"}</td>

                    {/* Tag vídeo */}
                    <td style={tdStyle}>{p.tag_video || "-"}</td>

                    {/* Data captura */}
                    <td style={tdStyle}>{p.data_captura_frame || "-"}</td>

                    {/* Inicio processamento */}
                    <td style={tdStyle}>{formatTimestamp(p.timestamp_inicial)}</td>

                    {/* Fim processamento */}
                    <td style={tdStyle}>{formatTimestamp(p.timestamp_final)}</td>

                    {/* Tempo processamento total */}
                    <td style={tdStyle}>{fmt(p.tempo_processamento_total)}</td>

                    {/* captura / detecção / reconhecimento */}
                    <td style={tdStyle}>{fmt(p.tempo_captura_frame)}</td>
                    <td style={tdStyle}>{fmt(p.tempo_deteccao)}</td>
                    <td style={tdStyle}>{fmt(p.tempo_reconhecimento)}</td>

                    {/* fila */}
                    <td style={tdStyle}>{fmt(p.tempo_fila)}</td>

                    {/* similarity */}
                    <td style={tdStyle}>{fmt(p.similarity_value)}</td>

                    {/* Confusão (select editável) */}
                    <td style={tdStyle}>
                      <select
                        value={p.confusionCategory || ""}
                        onChange={(e) => {
                          const novoValor = e.target.value;
                          handleChangeConfusion(p.id, novoValor);
                        }}
                        style={{
                          fontSize: "12px",
                          padding: "4px 6px",
                        }}
                      >
                        <option value="">-</option>
                        <option value="TP">TP</option>
                        <option value="TN">TN</option>
                        <option value="FP">FP</option>
                        <option value="FN">FN</option>
                      </select>
                    </td>

                    {/* Gold Standard (input editável) */}
                    <td style={tdStyle}>
                      <input
                        type="text"
                        defaultValue={p.gold_standard || ""}
                        style={{
                          fontSize: "12px",
                          padding: "4px 6px",
                          minWidth: "120px",
                        }}
                        onBlur={(e) => {
                          const novoValor = e.target.value.trim();
                          // só manda PATCH se mudou
                          if (novoValor !== (p.gold_standard || "")) {
                            handleChangeGoldStandard(p.id, novoValor);
                          }
                        }}
                      />
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}

      {/* paginação simples */}
      <div style={{ marginTop: "16px", display: "flex", gap: "8px", alignItems: "center" }}>
        <button
          disabled={page <= 1}
          onClick={() => setPage((p) => Math.max(1, p - 1))}
        >
          ← Anterior
        </button>
        <span style={{ fontSize: "14px" }}>
          Página {page} de {totalPaginas}
        </span>
        <button
          disabled={page >= totalPaginas}
          onClick={() => setPage((p) => Math.min(totalPaginas, p + 1))}
        >
          Próxima →
        </button>
      </div>
    </div>
  );
};

const tdStyle: React.CSSProperties = {
  padding: "8px 10px",
  border: "1px solid #ddd",
  verticalAlign: "top",
  fontSize: "12px",
  whiteSpace: "nowrap",
};

export default PresencaTable;
