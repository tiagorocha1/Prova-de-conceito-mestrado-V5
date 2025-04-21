import pandas as pd
from pymongo import MongoClient
import os
from dotenv import load_dotenv

# Carrega variáveis do .env (se existir)
load_dotenv()

# Conexão com MongoDB
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "seu_banco")

client = MongoClient(MONGO_URI)
db = client[MONGO_DB_NAME]

# Carregar as coleções
presencas_cursor = db.presencas.find()
frames_cursor = db.frames.find()

# Converter para DataFrames
df_presencas = pd.DataFrame(list(presencas_cursor))
df_frames = pd.DataFrame(list(frames_cursor))

print("✅ Dados carregados com sucesso!")
print(f"Total de registros de presença: {len(df_presencas)}")
print(f"Total de frames: {len(df_frames)}\n")

# -----------------------------
# ANÁLISES
# -----------------------------

print("🔍 Estatísticas sobre tempo de processamento total:")
print(df_presencas["tempo_processamento_total"].describe(), "\n")

print("⏱ Tempo médio de detecção e reconhecimento:")
print(df_presencas[["tempo_deteccao", "tempo_reconhecimento"]].mean(), "\n")

print("🧍 Faces por pessoa (mín, máx, média):")
faces_por_pessoa = df_presencas["pessoa"].value_counts()
print(faces_por_pessoa.describe(), "\n")

print("👥 Total de pessoas distintas reconhecidas:")
print(df_presencas["pessoa"].nunique(), "\n")

print("📸 Percentual de frames vazios (total_faces_detectadas == 0):")
df_frames["percent_vazios"] = df_frames["total_faces_detectadas"] == 0
percent_vazios = df_frames["percent_vazios"].mean() * 100
print(f"{percent_vazios:.2f}%\n")

print("🧾 Quantidade de presenças por frame:")
df_frames["qtd_presencas"] = df_frames["lista_presencas"].apply(lambda x: len(x) if isinstance(x, list) else 0)
print(df_frames["qtd_presencas"].describe(), "\n")

print("📊 Eficiência de reconhecimento (reconhecidas / detectadas):")
df_frames["eficiencia_reconhecimento"] = df_frames.apply(
    lambda row: row["total_faces_reconhecidas"] / row["total_faces_detectadas"]
    if row["total_faces_detectadas"] > 0 else 0, axis=1
)
print(df_frames["eficiencia_reconhecimento"].describe(), "\n")

print("📦 Estimativa de tempo em fila:")
df_presencas["tempo_fila"] = df_presencas["tempo_processamento_total"] - (
    df_presencas["tempo_captura_frame"] + df_presencas["tempo_deteccao"] + df_presencas["tempo_reconhecimento"]
)
print(df_presencas["tempo_fila"].describe(), "\n")
