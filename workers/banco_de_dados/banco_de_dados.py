import asyncio
import json
import logging
from pymongo import MongoClient, ReturnDocument
from dotenv import load_dotenv
import os
from datetime import datetime
import aio_pika


# Carregar variáveis de ambiente
load_dotenv()

MONGO_URI = os.getenv('MONGO_URI')
MONGO_DB_NAME = os.getenv('MONGO_DB_NAME')
RABBITMQ_HOST = os.getenv('RABBITMQ_HOST')
QUEUE_NAME_BD = os.getenv('QUEUE_NAME_BD')

# Configuração de logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("banco_de_dados")

# Conexão com MongoDB
client = MongoClient(MONGO_URI)
db = client[MONGO_DB_NAME]
presencas = db["presencas"]
frames = db["frames"]

counters = db["counters"]


# 🔢 Função para obter número sequencial por tag_video
def get_next_sequence_value(tag_video: str) -> int:
    counter = counters.find_one_and_update(
        {"_id": tag_video},
        {"$inc": {"sequence_value": 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER
    )
    return counter["sequence_value"]


async def registrar_presenca(message: aio_pika.IncomingMessage):

    
    async with message.process():
        try:
            msg = json.loads(message.body.decode())

            logger.info(f"📦 Mensagem recebida: {msg}")

            fim_processamento = datetime.now().timestamp()
            frame_total_faces = msg["frame_total_faces"]
            frame_uuid = msg["frame_uuid"]
            fps = msg.get("fps")
            duracao = msg["duracao"]
            tag_video = msg.get("tag_video")
            espera_captura_deteccao = float(msg.get("tempo_espera_captura_deteccao", 0))
            espera_deteccao_reconhecimento = float(msg.get("tempo_espera_deteccao_reconhecimento", 0))
            tempo_fila_real = espera_captura_deteccao + espera_deteccao_reconhecimento

            presence_doc = {
                "timestamp_inicial": msg["inicio_processamento"],
                "timestamp_final": fim_processamento,
                "data_captura_frame": msg["data_captura_frame"],
                "inicio_processamento": msg["inicio_processamento"],
                "fim_processamento": fim_processamento,
                "tempo_processamento_total": fim_processamento - msg["inicio_processamento"],
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
            }

            result = presencas.insert_one(presence_doc)

            presenca_id = result.inserted_id

            # Verificar se já existe o frame
            frame_doc = frames.find_one({"uuid": frame_uuid})

            if frame_doc:
                # Atualizar frame existente
                frames.update_one(
                    {"uuid": frame_uuid},
                    {
                        "$inc": {"total_faces_reconhecidas": 1},
                        "$push": {"lista_presencas": presenca_id},

                    }
                )
            else:
                # Criar novo frame
                # Obter número sequencial por tag_video
                numero_frame = get_next_sequence_value(tag_video)
                novo_frame = {
                    "uuid": frame_uuid,
                    "total_faces_detectadas": frame_total_faces,
                    "total_faces_reconhecidas": 1,
                    "tag_video": msg.get("tag_video"),
                    "lista_presencas": [presenca_id],
                    "fps": fps,
                    "duracao": duracao,
                    "numero_frame": numero_frame
                }
                frames.insert_one(novo_frame)


            logger.info(f"✅ Registro salvo: {presence_doc['pessoa']}, total: {presence_doc['tempo_processamento_total']:.2f}s")
        except Exception as e:
            logger.error(f"❌ Erro ao registrar presença: {e}")

async def main():
    connection = await aio_pika.connect_robust(f"amqp://{RABBITMQ_HOST}/")
    channel = await connection.channel()
    await channel.set_qos(prefetch_count=10)

    queue = await channel.declare_queue(QUEUE_NAME_BD, durable=True)

    logger.info("🎯 Aguardando mensagens de reconhecimento para registrar presença...")
    await queue.consume(registrar_presenca)

    # Mantém a aplicação rodando
    await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
