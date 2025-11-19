#!/usr/bin/env python3
# analisar_presenca.py

import os
from pymongo import MongoClient
import pandas as pd
import matplotlib.pyplot as plt

# ----------------------------
# Configurações de conexão
# ----------------------------
MONGO_URI   = os.getenv('MONGO_URI',   'mongodb://localhost:27017')
DB_NAME     = os.getenv('DB_NAME',     'seu_banco')
COLLECTION  = os.getenv('COLLECTION',  'presenca')

# ----------------------------
# Conectar ao MongoDB e carregar dados
# ----------------------------
client     = MongoClient(MONGO_URI)
db         = client[DB_NAME]
collection = db[COLLECTION]

docs = list(collection.find())
if not docs:
    raise ValueError("Coleção vazia ou consulta sem resultados.")

df = pd.DataFrame(docs)

# ----------------------------
# Conversão de datas e timestamps
# ----------------------------
# Converte colunas de timestamp (segundos) em datetime
for col in ['timestamp_inicial','timestamp_final','inicio_processamento','fim_processamento','timestamp']:
    df[col] = pd.to_datetime(df[col], unit='s')

# Converte data de captura (string) em datetime
df['data_captura_frame'] = pd.to_datetime(df['data_captura_frame'], format='%d-%m-%Y')

# Ordena e define índice temporal
df = df.sort_values('timestamp_inicial').set_index('timestamp_inicial')

# ----------------------------
# 1. Estatísticas descritivas
# ----------------------------
print("\n=== Estatísticas Descritivas ===")
print(df[['tempo_processamento_total',
          'tempo_captura_frame',
          'tempo_deteccao',
          'tempo_reconhecimento']].describe())

# ----------------------------
# 2. Agrupamentos
# ----------------------------
print("\n=== Agrupamento por Câmera (tag_video) ===")
group_tag = df.groupby('tag_video')['tempo_processamento_total'] \
              .agg(['mean','median','max','count'])
print(group_tag)

print("\n=== Frequência de Registros por Pessoa ===")
freq_pessoa = df.groupby('pessoa').size().sort_values(ascending=False)
print(freq_pessoa)

# ----------------------------
# 3. Séries Temporais (resample)
# ----------------------------
print("\n=== Registros por Dia ===")
daily_counts = df.resample('D').size()
print(daily_counts)

print("\n=== Tempo Médio de Processamento por Hora ===")
hourly_mean = df.resample('H')['tempo_processamento_total'].mean()
print(hourly_mean)

# ----------------------------
# 4. Visualizações básicas
# ----------------------------
# Histograma do tempo total
plt.figure()
df['tempo_processamento_total'].hist(bins=50)
plt.title('Histograma de Tempo Total de Processamento')
plt.xlabel('Tempo (s)')
plt.ylabel('Frequência')
plt.show()

# Boxplot de tempo de detecção por tag_video
plt.figure()
df.boxplot(column='tempo_deteccao', by='tag_video')
plt.title('Boxplot: Tempo de Detecção por Câmera')
plt.suptitle('')
plt.xlabel('tag_video')
plt.ylabel('tempo_deteccao (s)')
plt.show()

# Rolling mean (janela = 30 registros)
plt.figure()
df['tempo_processamento_total'].rolling(window=30).mean() \
   .plot(title='Média Móvel (janela=30) do Tempo Total')
plt.ylabel('Tempo (s)')
plt.show()

# ----------------------------
# 5. Correlações
# ----------------------------
print("\n=== Matriz de Correlação ===")
corr = df[['tempo_captura_frame',
           'tempo_deteccao',
           'tempo_reconhecimento',
           'tempo_fila_real']].corr()
print(corr)

# ----------------------------
# 6. Identificação de Outliers
# ----------------------------
mean_tot = df['tempo_processamento_total'].mean()
std_tot  = df['tempo_processamento_total'].std()
limiar   = mean_tot + 3 * std_tot

outliers = df[df['tempo_processamento_total'] > limiar]
print(f"\n=== Outliers (tempo > {limiar:.2f}s) ===")
print(outliers[['tempo_processamento_total','tag_video','pessoa']])

# ----------------------------
# Fim do script
# ----------------------------
print("\nAnálise concluída.")
