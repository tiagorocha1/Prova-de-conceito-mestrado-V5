import React, { useEffect, useState } from "react";
import { useAuth } from "./AuthContext";

interface Fonte {
  id: string;
  tag_video: string | null;
  modelo_utilizado: string | null;
  duracao: number | null;
  total_pessoas_gold_standard: number | null;

  timestamp_inicial: number | null;
  timestamp_final: number | null;

  total_faces_analisadas: number | null;
  total_clusters_gerados: number | null;

  total_de_frames: number | null;
  tempo_total_processamento: number | null;
  quantidade_faces_nao_reconhecidas: number | null;

  true_positives: number | null;
  true_negatives: number | null;
  false_positives: number | null;
  false_negatives: number | null;

  accuracy: number | null;
  precision: number | null;
  recall: number | null;
  f1_score: number | null;

  covering: number | null;
  inter_cluster_distance: number | null;
  intra_cluster_distance: number | null;
  silhouette: number | null;
  homogeneity: number | null;
  completeness: number | null;
  v_measure: number | null;

  time_to_complete_video_total_time: number | null;
  auxiliary_db_size: number | null;
}

interface ApiResponse {
  fontes: Fonte[];
  total: number;
  page: number;
  limit: number;
}

const FontesDashboard: React.FC = () => {
  const { token } = useAuth();

  // filtros
  const [tagVideoFiltro, setTagVideoFiltro] = useState<string>("");
  const [modeloFiltro, setModeloFiltro] = useState<string>("");

  // paginação
  const [page, setPage] = useState<number>(1);
  const [limit] = useState<number>(31);

  // dados
  const [loading, setLoading] = useState<boolean>(false);
  const [erro, setErro] = useState<string | null>(null);
  const [fontes, setFontes] = useState<Fonte[]>([]);
  const [total, setTotal] = useState<number>(0);

  // estado da ação de recalcular
  const [recalcLoading, setRecalcLoading] = useState<string | null>(null);
  const [recalcError, setRecalcError] = useState<string | null>(null);

  // criação manual de execução/fonte
  const [novoTagVideo, setNovoTagVideo] = useState<string>("");
  const [novoModelo, setNovoModelo] = useState<string>("");
  const [novoDuracao, setNovoDuracao] = useState<string>(""); // em segundos
  const [creating, setCreating] = useState<boolean>(false);
  const [createError, setCreateError] = useState<string | null>(null);

  // exportação de relatório
  const [exporting, setExporting] = useState<boolean>(false);
  const [exportError, setExportError] = useState<string | null>(null);
  const [exportingXlsx, setExportingXlsx] = useState<boolean>(false);

  // === helpers de formato ===
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

  const fmt = (v: number | null, digits = 3): string => {
    if (v === null || v === undefined) return "-";
    if (Number.isInteger(v)) return String(v);
    return v.toFixed(digits);
  };

  // === chamada GET principal ===
  const carregarFontes = async () => {
    if (!token) return;
    setLoading(true);
    setErro(null);

    try {
      const params = new URLSearchParams();
      params.append("page", page.toString());
      params.append("limit", limit.toString());
      if (tagVideoFiltro.trim() !== "")
        params.append("tag_video", tagVideoFiltro.trim());
      if (modeloFiltro.trim() !== "")
        params.append("modelo_utilizado", modeloFiltro.trim());

      const resp = await fetch(
        `http://localhost:8000/fontes?${params.toString()}`,
        {
          method: "GET",
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      );

      if (!resp.ok) {
        const text = await resp.text();
        throw new Error(`Erro ao buscar fontes: ${resp.status} - ${text}`);
      }

      const data: ApiResponse = await resp.json();
      setFontes(data.fontes || []);
      setTotal(data.total || 0);
    } catch (err: any) {
      console.error(err);
      setErro(err.message || "Erro ao carregar fontes");
    } finally {
      setLoading(false);
    }
  };

  // === criação manual de uma fonte/execução sem presenças ===
  const criarFonteManual = async () => {
    if (!token) return;

    if (!novoTagVideo.trim() || !novoModelo.trim()) {
      setCreateError("Informe tag_video e modelo.");
      return;
    }

    setCreating(true);
    setCreateError(null);

    try {
      const payload: any = {
        tag_video: novoTagVideo.trim(),
        modelo_utilizado: novoModelo.trim(),
      };

      if (novoDuracao.trim() !== "") {
        payload.duracao = Number(novoDuracao);
      }

      const resp = await fetch("http://localhost:8000/fontes/manual", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(payload),
      });

      if (!resp.ok) {
        const text = await resp.text();
        throw new Error(`Erro ao criar execução: ${resp.status} - ${text}`);
      }

      // sucesso → limpa formulário e recarrega lista
      setNovoTagVideo("");
      setNovoModelo("");
      setNovoDuracao("");
      await carregarFontes();
    } catch (err: any) {
      console.error(err);
      setCreateError(err.message || "Erro ao criar execução manual");
    } finally {
      setCreating(false);
    }
  };

  // === gerar relatório CSV de todas as fontes atualmente carregadas ===
  const gerarRelatorioCSV = () => {
    try {
      setExporting(true);
      setExportError(null);

      const headers = [
        "tag_video",
        "total_pessoas_gold_standard",
        "modelo_utilizado",
        "duracao",
        "timestamp_inicial",
        "timestamp_final",
        "total_de_frames",
        "tempo_total_processamento",
        "total_faces_analisadas",
        "total_clusters_gerados",
        "quantidade_faces_nao_reconhecidas",
        "true_positives",
        "true_negatives",
        "false_positives",
        "false_negatives",
        "accuracy",
        "precision",
        "recall",
        "f1_score",
        "covering",
        "inter_cluster_distance",
        "intra_cluster_distance",
        "silhouette",
        "homogeneity",
        "completeness",
        "v_measure",
        "ratio_tempo_real",
        "auxiliary_db_size",
      ];

      const safe = (val: any) => {
        if (val === null || val === undefined) return "";
        if (typeof val === "number") {
          if (Number.isInteger(val)) {
            val = String(val);
          } else {
            val = val.toFixed(3);
          }
        } else if (typeof val !== "string") {
          val = String(val);
        }
        let clean = val.replace(/\r?\n|\r/g, " ");
        if (clean.includes(",") || clean.includes(";")) {
          clean = `"${clean.replace(/"/g, '""')}"`;
        }
        return clean;
      };

      const linhas: string[] = [];
      linhas.push(headers.join(","));

      fontes.forEach((f) => {
        const row = [
          f.tag_video,
          f.total_pessoas_gold_standard,
          f.modelo_utilizado,
          f.duracao,
          f.timestamp_inicial,
          f.timestamp_final,
          f.total_de_frames,
          f.tempo_total_processamento,
          f.total_faces_analisadas,
          f.total_clusters_gerados,
          f.quantidade_faces_nao_reconhecidas,
          f.true_positives,
          f.true_negatives,
          f.false_positives,
          f.false_negatives,
          f.accuracy,
          f.precision,
          f.recall,
          f.f1_score,
          f.covering,
          f.inter_cluster_distance,
          f.intra_cluster_distance,
          f.silhouette,
          f.homogeneity,
          f.completeness,
          f.v_measure,
          f.time_to_complete_video_total_time,
          f.auxiliary_db_size,
        ].map(safe);

        linhas.push(row.join(","));
      });

      const csvContent = linhas.join("\n");
      const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });

      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;

      const agora = new Date();
      const yyyy = agora.getFullYear();
      const mm = String(agora.getMonth() + 1).padStart(2, "0");
      const dd = String(agora.getDate()).padStart(2, "0");
      const hh = String(agora.getHours()).padStart(2, "0");
      const mi = String(agora.getMinutes()).padStart(2, "0");
      const ss = String(agora.getSeconds()).padStart(2, "0");

      a.download = `fontes_${yyyy}${mm}${dd}_${hh}${mi}${ss}.csv`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);

      URL.revokeObjectURL(url);
    } catch (err: any) {
      console.error(err);
      setExportError(err.message || "Erro ao gerar relatório");
    } finally {
      setExporting(false);
    }
  };

  // === gerar relatório XLSX de todas as fontes atualmente carregadas ===
  const gerarRelatorioXLSX = async () => {
    try {
      setExportingXlsx(true);
      setExportError(null);
      const xlsx = await import("xlsx");

      const headers = [
        "tag_video",
        "total_pessoas_gold_standard",
        "modelo_utilizado",
        "duracao",
        "timestamp_inicial",
        "timestamp_final",
        "total_de_frames",
        "tempo_total_processamento",
        "total_faces_analisadas",
        "total_clusters_gerados",
        "quantidade_faces_nao_reconhecidas",
        "true_positives",
        "true_negatives",
        "false_positives",
        "false_negatives",
        "accuracy",
        "precision",
        "recall",
        "f1_score",
        "covering",
        "inter_cluster_distance",
        "intra_cluster_distance",
        "silhouette",
        "homogeneity",
        "completeness",
        "v_measure",
        "ratio_tempo_real",
        "auxiliary_db_size",
      ];

      const val = (v: any) => (v === null || v === undefined ? "" : v);

      const rows = fontes.map((f) => [
        val(f.tag_video),
        val(f.total_pessoas_gold_standard),
        val(f.modelo_utilizado),
        val(f.duracao),
        val(f.timestamp_inicial),
        val(f.timestamp_final),
        val(f.total_de_frames),
        val(f.tempo_total_processamento),
        val(f.total_faces_analisadas),
        val(f.total_clusters_gerados),
        val(f.quantidade_faces_nao_reconhecidas),
        val(f.true_positives),
        val(f.true_negatives),
        val(f.false_positives),
        val(f.false_negatives),
        val(f.accuracy),
        val(f.precision),
        val(f.recall),
        val(f.f1_score),
        val(f.covering),
        val(f.inter_cluster_distance),
        val(f.intra_cluster_distance),
        val(f.silhouette),
        val(f.homogeneity),
        val(f.completeness),
        val(f.v_measure),
        val(f.time_to_complete_video_total_time),
        val(f.auxiliary_db_size),
      ]);

      const aoa = [headers, ...rows];
      const ws = xlsx.utils.aoa_to_sheet(aoa);
      const wb = xlsx.utils.book_new();
      xlsx.utils.book_append_sheet(wb, ws, "Fontes");

      const now = new Date();
      const yyyy = now.getFullYear();
      const mm = String(now.getMonth() + 1).padStart(2, "0");
      const dd = String(now.getDate()).padStart(2, "0");
      const hh = String(now.getHours()).padStart(2, "0");
      const mi = String(now.getMinutes()).padStart(2, "0");
      const ss = String(now.getSeconds()).padStart(2, "0");

      xlsx.writeFile(wb, `fontes_${yyyy}${mm}${dd}_${hh}${mi}${ss}.xlsx`);
    } catch (err: any) {
      console.error(err);
      setExportError(err?.message || "Erro ao gerar relatório XLSX");
    } finally {
      setExportingXlsx(false);
    }
  };

  // === PATCH helper genérico para atualizar 1 campo da fonte ===
  const patchFonte = async (
    fonteId: string,
    body: Record<string, any>
  ): Promise<Fonte | null> => {
    if (!token) return null;

    const resp = await fetch(`http://localhost:8000/fontes/${fonteId}`, {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify(body),
    });

    if (!resp.ok) {
      const text = await resp.text();
      throw new Error(`Erro ao atualizar fonte: ${resp.status} - ${text}`);
    }

    const updated = await resp.json();
    const mapped: Fonte = {
      id: updated.id,
      tag_video: updated.tag_video ?? null,
      modelo_utilizado: updated.modelo_utilizado ?? null,
      duracao: updated.duracao ?? null,
      total_pessoas_gold_standard: updated.total_pessoas_gold_standard ?? null,

      timestamp_inicial: updated.timestamp_inicial ?? null,
      timestamp_final: updated.timestamp_final ?? null,

      total_faces_analisadas: updated.total_faces_analisadas ?? null,
      total_clusters_gerados: updated.total_clusters_gerados ?? null,

      total_de_frames: updated.total_de_frames ?? null,
      tempo_total_processamento: updated.tempo_total_processamento ?? null,
      quantidade_faces_nao_reconhecidas:
        updated.quantidade_faces_nao_reconhecidas ?? null,

      true_positives: updated.true_positives ?? null,
      true_negatives: updated.true_negatives ?? null,
      false_positives: updated.false_positives ?? null,
      false_negatives: updated.false_negatives ?? null,

      accuracy: updated.accuracy ?? null,
      precision: updated.precision ?? null,
      recall: updated.recall ?? null,
      f1_score: updated.f1_score ?? null,

      covering: updated.covering ?? null,
      inter_cluster_distance: updated.inter_cluster_distance ?? null,
      intra_cluster_distance: updated.intra_cluster_distance ?? null,
      silhouette: updated.silhouette ?? null,
      homogeneity: updated.homogeneity ?? null,
      completeness: updated.completeness ?? null,
      v_measure: updated.v_measure ?? null,

      time_to_complete_video_total_time:
        updated.time_to_complete_video_total_time ?? null,
      auxiliary_db_size: updated.auxiliary_db_size ?? null,
    };

    return mapped;
  };

  // === Handlers de edição inline ===
  const handleBlurGoldStandard = async (fonte: Fonte, novoValorStr: string) => {
    const novoValorNum = novoValorStr === "" ? null : Number(novoValorStr);
    if (novoValorNum === fonte.total_pessoas_gold_standard) return;

    try {
      const updated = await patchFonte(fonte.id, {
        total_pessoas_gold_standard: novoValorNum,
      });
      if (updated) {
        setFontes((curr) =>
          curr.map((f) => (f.id === fonte.id ? { ...f, ...updated } : f))
        );
      }
    } catch (err: any) {
      console.error(err);
      alert(err.message || "Falha ao atualizar total_pessoas_gold_standard");
    }
  };

  const handleBlurDuracao = async (fonte: Fonte, novoValorStr: string) => {
    const novoValorNum = novoValorStr === "" ? null : Number(novoValorStr);
    if (novoValorNum === fonte.duracao) return;

    try {
      const updated = await patchFonte(fonte.id, { duracao: novoValorNum });
      if (updated) {
        setFontes((curr) =>
          curr.map((f) => (f.id === fonte.id ? { ...f, ...updated } : f))
        );
      }
    } catch (err: any) {
      console.error(err);
      alert(err.message || "Falha ao atualizar duração");
    }
  };

  const handleBlurNaoReconhecidas = async (
    fonte: Fonte,
    novoValorStr: string
  ) => {
    const novoValorNum = novoValorStr === "" ? null : Number(novoValorStr);
    if (novoValorNum === fonte.quantidade_faces_nao_reconhecidas) return;

    try {
      const updated = await patchFonte(fonte.id, {
        quantidade_faces_nao_reconhecidas: novoValorNum,
      });
      if (updated) {
        setFontes((curr) =>
          curr.map((f) => (f.id === fonte.id ? { ...f, ...updated } : f))
        );
      }
    } catch (err: any) {
      console.error(err);
      alert(
        err.message || "Falha ao atualizar quantidade_faces_nao_reconhecidas"
      );
    }
  };

  const handleBlurAuxDbSize = async (fonte: Fonte, novoValorStr: string) => {
    const novoValorNum = novoValorStr === "" ? null : Number(novoValorStr);
    if (novoValorNum === fonte.auxiliary_db_size) return;

    try {
      const updated = await patchFonte(fonte.id, {
        auxiliary_db_size: novoValorNum,
      });
      if (updated) {
        setFontes((curr) =>
          curr.map((f) => (f.id === fonte.id ? { ...f, ...updated } : f))
        );
      }
    } catch (err: any) {
      console.error(err);
      alert(err.message || "Falha ao atualizar auxiliary_db_size");
    }
  };

  // === ação de recalcular métrica agregada ===
  const recalcularFonte = async (id: string) => {
    if (!token) return;

    setRecalcLoading(id);
    setRecalcError(null);

    try {
      const resp = await fetch(
        `http://localhost:8000/fontes/${id}/recalcular`,
        {
          method: "POST",
          headers: { Authorization: `Bearer ${token}` },
        }
      );

      if (!resp.ok) {
        const text = await resp.text();
        throw new Error(`Erro ao recalcular: ${resp.status} - ${text}`);
      }

      await carregarFontes();
    } catch (err: any) {
      console.error(err);
      setRecalcError(err.message || "Erro ao recalcular");
    } finally {
      setRecalcLoading(null);
    }
  };

  // efeito inicial / filtros / paginação
  useEffect(() => {
    carregarFontes();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, tagVideoFiltro, modeloFiltro, token]);

  const totalPaginas = Math.ceil(total / limit) || 1;

  return (
    <div style={{ padding: "20px" }}>
      <h2>Fontes / Execuções</h2>

      {/* Criar execução manual */}
      <div
        style={{
          background: "#e8f0fe",
          border: "1px solid #90caf9",
          borderRadius: "8px",
          padding: "12px",
          marginBottom: "16px",
          display: "flex",
          flexWrap: "wrap",
          gap: "12px",
          alignItems: "flex-end",
        }}
      >
        <div style={{ display: "flex", flexDirection: "column" }}>
          <label style={{ fontWeight: "bold", fontSize: "12px" }}>tag_video *</label>
          <input
            type="text"
            value={novoTagVideo}
            onChange={(e) => setNovoTagVideo(e.target.value)}
            placeholder="ex: aula_2025_03_14_blocoB"
            style={editInputStyleWide}
          />
        </div>

        <div style={{ display: "flex", flexDirection: "column" }}>
          <label style={{ fontWeight: "bold", fontSize: "12px" }}>modelo *</label>
          <input
            type="text"
            value={novoModelo}
            onChange={(e) => setNovoModelo(e.target.value)}
            placeholder="ex: facenet512_v2"
            style={editInputStyleWide}
          />
        </div>

        <div style={{ display: "flex", flexDirection: "column" }}>
          <label style={{ fontWeight: "bold", fontSize: "12px" }}>duração (s)</label>
          <input
            type="number"
            step="0.01"
            value={novoDuracao}
            onChange={(e) => setNovoDuracao(e.target.value)}
            placeholder="ex: 123.45"
            style={editInputStyleNarrow}
          />
        </div>

        <button
          onClick={criarFonteManual}
          disabled={creating}
          style={{
            padding: "6px 10px",
            fontSize: "12px",
            cursor: creating ? "not-allowed" : "pointer",
            backgroundColor: creating ? "#ccc" : "#1976d2",
            border: "none",
            color: "#fff",
            borderRadius: "4px",
            minWidth: "120px",
            height: "32px",
            alignSelf: "flex-end",
          }}
          title="Registrar execução manualmente (caso nenhuma presença tenha sido reconhecida)"
        >
          {creating ? "..." : "Criar Execução"}
        </button>

        {createError && (
          <div
            style={{
              color: "#a00",
              fontSize: "12px",
              fontWeight: 500,
              flexBasis: "100%",
            }}
          >
            {createError}
          </div>
        )}
      </div>

      {/* Filtros */}
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
            placeholder="ex: aula_2025_03_14_blocoB"
            style={{ padding: "6px 8px", minWidth: "220px" }}
          />
        </div>

        <div style={{ display: "flex", flexDirection: "column" }}>
          <label style={{ fontWeight: "bold" }}>Filtrar por modelo:</label>
          <input
            type="text"
            value={modeloFiltro}
            onChange={(e) => {
              setPage(1);
              setModeloFiltro(e.target.value);
            }}
            placeholder="ex: facenet512_v2"
            style={{ padding: "6px 8px", minWidth: "220px" }}
          />
        </div>

        <div style={{ fontSize: "14px", color: "#555" }}>
          <div>Total registros: {total}</div>
          <div>
            Página {page} / {totalPaginas}
          </div>
        </div>
      </div>

      {/* Erros */}
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

      {recalcError && (
        <div
          style={{
            backgroundColor: "#fff4e0",
            border: "1px solid #ffc107",
            padding: "10px",
            marginBottom: "16px",
            borderRadius: "6px",
            color: "#a65e00",
          }}
        >
          {recalcError}
        </div>
      )}

      {/* Ações de exportação */}
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          gap: "12px",
          alignItems: "center",
          marginBottom: "12px",
        }}
      >
        <button
          onClick={gerarRelatorioCSV}
          disabled={exporting || fontes.length === 0}
          style={{
            padding: "6px 10px",
            fontSize: "12px",
            cursor: exporting || fontes.length === 0 ? "not-allowed" : "pointer",
            backgroundColor: exporting || fontes.length === 0 ? "#ccc" : "#1976d2",
            border: "none",
            color: "#fff",
            borderRadius: "4px",
            minWidth: "140px",
            height: "32px",
          }}
          title="Baixar CSV com todas as execuções listadas abaixo"
        >
          {exporting ? "Gerando..." : "Gerar Relatório CSV"}
        </button>

        <button
          onClick={gerarRelatorioXLSX}
          disabled={exportingXlsx || fontes.length === 0}
          style={{
            padding: "6px 10px",
            fontSize: "12px",
            cursor: exportingXlsx || fontes.length === 0 ? "not-allowed" : "pointer",
            backgroundColor: exportingXlsx || fontes.length === 0 ? "#ccc" : "#2e7d32",
            border: "none",
            color: "#fff",
            borderRadius: "4px",
            minWidth: "160px",
            height: "32px",
          }}
          title="Baixar XLSX com todas as execuções listadas abaixo"
        >
          {exportingXlsx ? "Gerando..." : "Gerar Relatório XLSX"}
        </button>

        {exportError && (
          <div style={{ color: "#a00", fontSize: "12px", fontWeight: 500 }}>
            {exportError}
          </div>
        )}
      </div>

      {loading ? (
        <div>Carregando...</div>
      ) : (
        <>
          {/* =================== TABELA 01 - DADOS GERAIS =================== */}
          <h3 style={{ marginTop: 8 }}>Tabela 01 — Dados Gerais</h3>
          <div style={{ overflowX: "auto", marginBottom: 24 }}>
            <table
              style={{
                borderCollapse: "collapse",
                width: "100%",
                minWidth: "1200px",
                fontSize: "13px",
              }}
            >
              <thead>
                <tr style={{ background: "#1976d2", color: "#fff", textAlign: "left" }}>
                  {[
                    "tag_video",
                    "total_pessoas_gold_standard",
                    "modelo",
                    "duração (s)",
                    "inicio",
                    "fim",
                    "total frames",
                    "tempo_total_proc (s)",
                    "ratio_tempo_real",
                    "aux_db_size (MB)",
                    "Ações",
                  ].map((h) => (
                    <th key={h} style={thStyle}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {fontes.length === 0 ? (
                  <tr>
                    <td colSpan={11} style={emptyStyle}>Nenhuma fonte encontrada.</td>
                  </tr>
                ) : (
                  fontes.map((f) => (
                    <tr key={`g-${f.id}`} style={{ background: "#fafafa" }}>
                      <td style={tdStyle}>{f.tag_video || "-"}</td>

                      {/* total_pessoas_gold_standard editável */}
                      <td style={tdStyle}>
                        <input
                          type="number"
                          defaultValue={f.total_pessoas_gold_standard ?? ""}
                          style={editInputStyle}
                          onBlur={(e) => handleBlurGoldStandard(f, e.target.value)}
                        />
                      </td>

                      <td style={tdStyle}>{f.modelo_utilizado || "-"}</td>

                      {/* duracao editável */}
                      <td style={tdStyle}>
                        <input
                          type="number"
                          step="0.01"
                          defaultValue={f.duracao ?? ""}
                          style={editInputStyle}
                          onBlur={(e) => handleBlurDuracao(f, e.target.value)}
                        />
                      </td>

                      <td style={tdStyle}>{formatTimestamp(f.timestamp_inicial)}</td>
                      <td style={tdStyle}>{formatTimestamp(f.timestamp_final)}</td>

                      <td style={tdStyle}>{f.total_de_frames ?? "-"}</td>
                      <td style={tdStyle}>{fmt(f.tempo_total_processamento)}</td>
                      <td style={tdStyle}>{fmt(f.time_to_complete_video_total_time)}</td>

                      {/* aux db size editável */}
                      <td style={tdStyle}>
                        <input
                          type="number"
                          step="0.01"
                          defaultValue={f.auxiliary_db_size ?? ""}
                          style={editInputStyle}
                          onBlur={(e) => handleBlurAuxDbSize(f, e.target.value)}
                        />
                      </td>

                      <td style={tdStyle}>
                        <button
                          onClick={() => recalcularFonte(f.id)}
                          disabled={recalcLoading === f.id}
                          style={{
                            padding: "4px 8px",
                            fontSize: "12px",
                            cursor: recalcLoading === f.id ? "not-allowed" : "pointer",
                            backgroundColor: recalcLoading === f.id ? "#ccc" : "#1976d2",
                            border: "none",
                            color: "#fff",
                            borderRadius: "4px",
                            minWidth: "90px",
                          }}
                          title="Sincronizar dados dessa execução com base no banco atual"
                        >
                          {recalcLoading === f.id ? "..." : "Recalcular"}
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>

          {/* =================== TABELA 02 - MÉTRICAS DE EFICIÊNCIA =================== */}
          <h3>Tabela 02 — Métricas de Eficiência</h3>
          <div style={{ overflowX: "auto", marginBottom: 24 }}>
            <table
              style={{
                borderCollapse: "collapse",
                width: "100%",
                minWidth: "1400px",
                fontSize: "13px",
              }}
            >
              <thead>
                <tr style={{ background: "#1976d2", color: "#fff", textAlign: "left" }}>
                  {[
                    "tag_video",
                    "faces analisadas",
                    "clusters_gerados",
                    "faces_nao_reconhecidas",
                    "TP",
                    "TN",
                    "FP",
                    "FN",
                    "accuracy",
                    "precision",
                    "recall",
                    "f1",
                  ].map((h) => (
                    <th key={h} style={thStyle}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {fontes.length === 0 ? (
                  <tr>
                    <td colSpan={12} style={emptyStyle}>Nenhuma fonte encontrada.</td>
                  </tr>
                ) : (
                  fontes.map((f) => (
                    <tr key={`e-${f.id}`} style={{ background: "#fafafa" }}>
                      <td style={tdStyle}>{f.tag_video || "-"}</td>
                      <td style={tdStyle}>{f.total_faces_analisadas ?? "-"}</td>
                      <td style={tdStyle}>{f.total_clusters_gerados ?? "-"}</td>

                      {/* faces_nao_reconhecidas editável */}
                      <td style={tdStyle}>
                        <input
                          type="number"
                          defaultValue={f.quantidade_faces_nao_reconhecidas ?? ""}
                          style={editInputStyle}
                          onBlur={(e) => handleBlurNaoReconhecidas(f, e.target.value)}
                        />
                      </td>

                      <td style={tdStyle}>{f.true_positives ?? "-"}</td>
                      <td style={tdStyle}>{f.true_negatives ?? "-"}</td>
                      <td style={tdStyle}>{f.false_positives ?? "-"}</td>
                      <td style={tdStyle}>{f.false_negatives ?? "-"}</td>

                      <td style={tdStyle}>{fmt(f.accuracy)}</td>
                      <td style={tdStyle}>{fmt(f.precision)}</td>
                      <td style={tdStyle}>{fmt(f.recall)}</td>
                      <td style={tdStyle}>{fmt(f.f1_score)}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>

          {/* =================== TABELA 03 - MÉTRICAS DE AGRUPAMENTO =================== */}
          <h3>Tabela 03 — Métricas de Agrupamento</h3>
          <div style={{ overflowX: "auto" }}>
            <table
              style={{
                borderCollapse: "collapse",
                width: "100%",
                minWidth: "1200px",
                fontSize: "13px",
              }}
            >
              <thead>
                <tr style={{ background: "#1976d2", color: "#fff", textAlign: "left" }}>
                  {[
                    "covering",
                    "inter_cluster_dist",
                    "intra_cluster_dist",
                    "silhouette",
                    "homogeneity",
                    "completeness",
                    "v_measure",
                  ].map((h) => (
                    <th key={h} style={thStyle}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {fontes.length === 0 ? (
                  <tr>
                    <td colSpan={7} style={emptyStyle}>Nenhuma fonte encontrada.</td>
                  </tr>
                ) : (
                  fontes.map((f) => (
                    <tr key={`c-${f.id}`} style={{ background: "#fafafa" }}>
                      <td style={tdStyle}>{fmt(f.covering)}</td>
                      <td style={tdStyle}>{fmt(f.inter_cluster_distance)}</td>
                      <td style={tdStyle}>{fmt(f.intra_cluster_distance)}</td>
                      <td style={tdStyle}>{fmt(f.silhouette)}</td>
                      <td style={tdStyle}>{fmt(f.homogeneity)}</td>
                      <td style={tdStyle}>{fmt(f.completeness)}</td>
                      <td style={tdStyle}>{fmt(f.v_measure)}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </>
      )}

      {/* paginação simples */}
      <div
        style={{
          marginTop: "16px",
          display: "flex",
          gap: "8px",
          alignItems: "center",
        }}
      >
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

const thStyle: React.CSSProperties = {
  padding: "8px 10px",
  border: "1px solid #145a96",
  fontWeight: "bold",
  fontSize: "12px",
  whiteSpace: "nowrap",
};

const tdStyle: React.CSSProperties = {
  padding: "8px 10px",
  border: "1px solid #ddd",
  verticalAlign: "top",
  fontSize: "12px",
  whiteSpace: "nowrap",
};

const emptyStyle: React.CSSProperties = {
  padding: "16px",
  border: "1px solid #ddd",
  textAlign: "center",
  color: "#666",
};

const editInputStyle: React.CSSProperties = {
  fontSize: "12px",
  padding: "4px 6px",
  minWidth: "70px",
  border: "1px solid #ccc",
  borderRadius: "4px",
};

const editInputStyleWide: React.CSSProperties = {
  fontSize: "12px",
  padding: "6px 8px",
  minWidth: "220px",
  border: "1px solid #90caf9",
  borderRadius: "4px",
};

const editInputStyleNarrow: React.CSSProperties = {
  fontSize: "12px",
  padding: "6px 8px",
  minWidth: "100px",
  border: "1px solid #90caf9",
  borderRadius: "4px",
};

export default FontesDashboard;
