import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, Optional

import aio_pika
from dotenv import load_dotenv
from pymongo import MongoClient, ReturnDocument
from pymongo.collection import Collection
from pymongo.results import InsertOneResult


# =========================
# Configuração inicial
# =========================

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME")
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST")
QUEUE_NAME_BD = os.getenv("QUEUE_NAME_BD")
MODEL_NAME = os.getenv("MODEL_NAME", "desconhecido")  # versão/modelo do reconhecimento
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("banco_de_dados")

# =========================
# Conexão com MongoDB
# =========================
client = MongoClient(MONGO_URI)
db = client[MONGO_DB_NAME]
presencas: Collection = db["presencas"]
frames: Collection = db["frames"]
counters: Collection = db["counters"]
fontes: Collection = db["fonte"]  # nova coleção


# =========================
# Repositório: Sequência por tag_video
# =========================

def get_next_sequence_value(tag_video: str) -> int:
    """
    Retorna o próximo número sequencial para um determinado tag_video.
    Usado para definir o numero_frame de forma incremental por vídeo.
    """
    counter = counters.find_one_and_update(
        {"_id": tag_video},
        {"$inc": {"sequence_value": 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER
    )
    return counter["sequence_value"]


# =========================
# Repositório: Fonte
# =========================

def get_or_create_fonte(
    tag_video: str,
    timestamp_atual: float,
    modelo_utilizado: str,
    duracao: Any,
) -> Dict[str, Any]:
    
    """
    Busca a fonte correspondente ao tag_video (e modelo).
    Se não existir, cria uma nova fonte inicializada com valores padrão.

    Retorna o documento completo da fonte (inclui _id).
    """
    # Podemos decidir se a chave lógica é só tag_video
    # ou (tag_video + modelo_utilizado). Aqui vou usar os dois,
    # o que permite reprocessar um mesmo vídeo com modelos diferentes.
    filtro = {
        "tag_video": tag_video,
        "modelo_utilizado": modelo_utilizado
    }

    fonte_doc = fontes.find_one(filtro)
    if fonte_doc:
        return fonte_doc

    # Criar nova fonte com todos os campos que definimos conceitualmente
    # Campos de métricas começam zerados/nulos e serão preenchidos/atualizados pela API externa
    nova_fonte = {
        # Identificação do experimento
        "tag_video": tag_video,
        "timestamp_inicial": timestamp_atual,
        "timestamp_final": timestamp_atual,
        "modelo_utilizado": modelo_utilizado,
        "total_faces_analisadas": 0,
        "total_clusters_gerados": 0,

        "total_de_frames": 0,
        "tempo_total_processamento": 0.0,
        "quantidade_faces_nao_reconhecidas": 0,

        # Métricas de classificação
        "true_positives": 0,
        "true_negatives": 0,
        "false_positives": 0,
        "false_negatives": 0,
        "accuracy": None,
        "precision": None,
        "recall": None,
        "f1_score": None,

        # Métricas de clusterização
        "covering": None,
        "inter_cluster_distance": None,
        "intra_cluster_distance": None,
        "silhouette": None,
        "homogeneity": None,
        "completeness": None,
        "v_measure": None,

        # Métricas de desempenho
        "time_to_complete_video_total_time": None,
        "auxiliary_db_size": None,

        "total_pessoas_gold_standard": None,

        "duracao":  duracao,      

    }

    insert_result: InsertOneResult = fontes.insert_one(nova_fonte)
    nova_fonte["_id"] = insert_result.inserted_id
    return nova_fonte


def atualizar_timestamp_final_fonte(fonte_id, novo_timestamp_final: float) -> None:
    """
    Atualiza continuamente o timestamp_final da fonte para refletir
    o frame mais recente processado.

    Observação:
    No futuro, essa atualização pode migrar para a API externa que consolida métricas.
    Por enquanto, mantemos aqui para garantir consistência temporal mínima.
    """
    fontes.update_one(
        {"_id": fonte_id},
        {"$set": {"timestamp_final": novo_timestamp_final}}
    )


# =========================
# Builders (montam os documentos para inserção)
# =========================

def montar_presence_doc(
    msg: Dict[str, Any],
    fim_processamento: float,
    tempo_fila_real: float,
    fonte_id
) -> Dict[str, Any]:
    """
    Constrói o documento de presença pronto para inserção em 'presencas'.
    Não faz inserção, só monta.
    """
    inicio_proc = msg["inicio_processamento"]

    return {
        "timestamp_inicial": inicio_proc,
        "timestamp_final": fim_processamento,

        "data_captura_frame": msg["data_captura_frame"],
        "inicio_processamento": inicio_proc,
        "fim_processamento": fim_processamento,

        "tempo_processamento_total": fim_processamento - inicio_proc,
        "tempo_captura_frame": msg["tempo_captura_frame"],
        "tempo_deteccao": msg["tempo_deteccao"],
        "tempo_reconhecimento": msg["tempo_reconhecimento"],

        "pessoa": msg.get("uuid"),
        "foto_captura": msg["reconhecimento_path"],
        "tags": msg.get("tags", []),

        "tag_video": msg.get("tag_video"),
        "timestamp": msg.get("timestamp"),

        "tempo_espera_captura_deteccao": msg.get("tempo_espera_captura_deteccao"),
        "tempo_espera_deteccao_reconhecimento": msg.get("tempo_espera_deteccao_reconhecimento"),
        "tempo_fila_real": tempo_fila_real,

        "similarity_value": msg.get("similarity_value"),

        # relacionamento explícito
        "fonte_id": fonte_id,

        "confusionCategory": "N/A",
    }


def montar_novo_frame_doc(
    msg: Dict[str, Any],
    presenca_id,
    frame_total_faces: int,
    numero_frame: int,
    fonte_id
) -> Dict[str, Any]:
    """
    Monta o documento inicial de um frame que ainda não existe.
    """
    return {
        "uuid": msg["frame_uuid"],

        "total_faces_detectadas": frame_total_faces,
        "total_faces_reconhecidas": 1,

        "tag_video": msg.get("tag_video"),
        "fps": msg.get("fps"),
        "duracao": msg["duracao"],
        "numero_frame": numero_frame,

        "lista_presencas": [presenca_id],

        # relacionamento explícito
        "fonte_id": fonte_id,
    }


# =========================
# Repositórios: persistência em Mongo
# =========================

def inserir_presenca(presence_doc: Dict[str, Any]):
    """
    Insere o documento de presença em 'presencas' e retorna o _id.
    """
    result = presencas.insert_one(presence_doc)
    return result.inserted_id


def atualizar_ou_criar_frame(
    frame_uuid: str,
    tag_video: str,
    frame_total_faces: int,
    presenca_id,
    fps: Optional[Any],
    duracao: Any,
    fonte_id,
):
    """
    Atualiza um frame existente com a nova presença
    OU cria um novo frame se ele ainda não existir.
    """
    frame_doc = frames.find_one({"uuid": frame_uuid})

    if frame_doc:
        # Atualiza frame existente
        frames.update_one(
            {"uuid": frame_uuid},
            {
                "$inc": {"total_faces_reconhecidas": 1},
                "$push": {"lista_presencas": presenca_id},
                # garante que a relação com 'fonte' é conhecida
                "$set": {"fonte_id": fonte_id}
            }
        )
        return

    # Criar novo frame
    numero_frame = get_next_sequence_value(tag_video)

    novo_frame = {
        "uuid": frame_uuid,
        "total_faces_detectadas": frame_total_faces,
        "total_faces_reconhecidas": 1,
        "tag_video": tag_video,
        "lista_presencas": [presenca_id],
        "fps": fps,
        "duracao": duracao,
        "numero_frame": numero_frame,
        "fonte_id": fonte_id,
    }

    frames.insert_one(novo_frame)


# =========================
# Orquestrador principal (consumer)
# =========================

async def registrar_presenca(message: aio_pika.IncomingMessage):
    """
    Lê mensagem da fila, registra presença, garante frame e vincula
    tudo a uma 'fonte'. Mantém logs e captura falhas.
    """
    async with message.process():
        try:
            msg = json.loads(message.body.decode())
            logger.info(f"📦 Mensagem recebida: {msg}")

            # --- cálculo de tempos imediatos
            fim_processamento = datetime.now().timestamp()

            espera_captura_deteccao = float(msg.get("tempo_espera_captura_deteccao", 0))
            espera_deteccao_reconhecimento = float(msg.get("tempo_espera_deteccao_reconhecimento", 0))
            tempo_fila_real = espera_captura_deteccao + espera_deteccao_reconhecimento

            frame_total_faces = msg["frame_total_faces"]
            frame_uuid = msg["frame_uuid"]
            fps = msg.get("fps")
            duracao = msg["duracao"]
            tag_video = msg.get("tag_video")
            
            # --- garantir/obter fonte
            fonte_doc = get_or_create_fonte(
                tag_video=tag_video,
                timestamp_atual=fim_processamento,
                modelo_utilizado=MODEL_NAME,
                duracao=duracao
            )
            fonte_id = fonte_doc["_id"]

            # Atualiza timestamp_final dessa fonte pro frame mais recente
            atualizar_timestamp_final_fonte(fonte_id, fim_processamento)

            # --- montar presence_doc incluindo referência à fonte
            presence_doc = montar_presence_doc(
                msg=msg,
                fim_processamento=fim_processamento,
                tempo_fila_real=tempo_fila_real,
                fonte_id=fonte_id
            )

            # --- inserir presença e recuperar ID
            presenca_id = inserir_presenca(presence_doc)

            # --- atualizar ou criar frame associado
            atualizar_ou_criar_frame(
                frame_uuid=frame_uuid,
                tag_video=tag_video,
                frame_total_faces=frame_total_faces,
                presenca_id=presenca_id,
                fps=fps,
                duracao=duracao,
                fonte_id=fonte_id,
            )

            logger.info(
                f"✅ Presença salva para pessoa={presence_doc.get('pessoa')} "
                f"em {presence_doc['tempo_processamento_total']:.2f}s "
                f"(fonte_id={fonte_id})"
            )

        except Exception as e:
            # Log detalhado pra facilitar debug
            logger.exception(f"❌ Erro ao registrar presença: {e}")


# =========================
# Main loop (RabbitMQ consumer)
# =========================

async def main():
    connection = await aio_pika.connect_robust(f"amqp://{RABBITMQ_HOST}/")
    channel = await connection.channel()
    await channel.set_qos(prefetch_count=10)

    queue = await channel.declare_queue(QUEUE_NAME_BD, durable=True)

    logger.info("🎯 Aguardando mensagens de reconhecimento para registrar presença...")
    await queue.consume(registrar_presenca)

    # Mantém a aplicação viva
    await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
