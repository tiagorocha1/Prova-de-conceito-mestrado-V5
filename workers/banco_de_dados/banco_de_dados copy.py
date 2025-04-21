import pika
import json
import logging
from pymongo import MongoClient
from dotenv import load_dotenv
import os
from datetime import datetime

# Carregar variáveis de ambiente
load_dotenv()

MONGO_URI = os.getenv('MONGO_URI')
MONGO_DB_NAME = os.getenv('MONGO_DB_NAME')
MODEL_NAME = os.getenv('MODEL_NAME')

# Conexão ao RabbitMQ
RABBITMQ_HOST = os.getenv('RABBITMQ_HOST')
QUEUE_NAME_BD = os.getenv('QUEUE_NAME_BD')

# Configuração de logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Conexão ao MongoDB
client = MongoClient(MONGO_URI)
db = client[MONGO_DB_NAME]
presencas = db["presencas"]

connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST))
channel = connection.channel()
channel.queue_declare(queue=QUEUE_NAME_BD, durable=True)

def registrar_presenca(ch, method, properties, body):
    try:
        msg = json.loads(body)

        fim_processamento = datetime.now().timestamp()
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
            "pessoa": msg["uuid"],
            "foto_captura": msg["reconhecimento_path"],
            "tags": msg.get("tags", []),
            "tag_video": msg.get("tag_video"),
            "timestamp": msg.get("timestamp"),
        }

        # Inserir no MongoDB
        presencas.insert_one(presence_doc)
        logger.info(f"✅ Registro de presença salvo: {presence_doc}")

        # Confirmação da mensagem processada com sucesso
        ch.basic_ack(delivery_tag=method.delivery_tag)

    except Exception as e:
        logger.error(f"❌ Erro ao registrar presença: {e}")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

# Iniciar consumidor
channel.basic_consume(queue=QUEUE_NAME_BD, on_message_callback=registrar_presenca)
logger.info("🎯 Aguardando mensagens de reconhecimento para registrar presença...")
channel.start_consuming()
