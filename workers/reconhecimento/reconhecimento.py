from io import BytesIO
import os
import json
import uuid
import pika
import cv2
import numpy as np
from PIL import Image
from datetime import datetime
from pymongo import MongoClient
from minio import Minio
from deepface import DeepFace
from minio.error import S3Error
import hashlib
import logging
from dotenv import load_dotenv
from concurrent.futures import ProcessPoolExecutor
from multiprocessing import freeze_support

# -------------------------------
# Configurações
# -------------------------------
load_dotenv()

TEMP_DIR = os.getenv("TEMP_DIR")
os.makedirs(TEMP_DIR, exist_ok=True)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BUCKET_RECONHECIMENTO = os.getenv("BUCKET_RECONHECIMENTO")
BUCKET_DETECCOES = os.getenv("BUCKET_DETECCOES")
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY")
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST")
QUEUE_NAME = os.getenv("QUEUE_NAME")
MONGO_URI = os.getenv('MONGO_URI')
MONGO_DB_NAME = os.getenv('MONGO_DB_NAME')
MODEL_NAME = os.getenv('MODEL_NAME')
SIMILARITY_THRESHOLD = 0.30

print(MODEL_NAME)

# Conexão ao MongoDB
client = MongoClient(MONGO_URI)
db = client[MONGO_DB_NAME]
pessoas = db["pessoas"]
presencas = db["presencas"]

# Conexão ao MinIO
minio_client = Minio(
    MINIO_ENDPOINT,
    access_key=MINIO_ACCESS_KEY,
    secret_key=MINIO_SECRET_KEY,
    secure=False
)

# Conexão ao RabbitMQ
connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST))
channel = connection.channel()
channel.queue_declare(queue=QUEUE_NAME, durable=True)
channel.queue_declare(queue="reconhecimentos", durable=True)  # Fila de saída

# Executor global (será inicializado na função main)
executor = None

# -------------------------------
# Funções Auxiliares
# -------------------------------
def generate_embedding(image: Image.Image):
    """Gera o embedding facial usando DeepFace."""
    try:
        image_np = np.array(image)
        embeddings = DeepFace.represent(img_path=image_np, model_name=MODEL_NAME, enforce_detection=False)
        return embeddings[0]['embedding'] if embeddings else None
    except Exception as e:
        logger.error(f"❌ Erro ao gerar embedding: {e}")
        return None

def get_image_hash(image_bytes):
    """Calcula o hash MD5 de uma imagem."""
    return hashlib.md5(image_bytes).hexdigest()

def upload_image_to_minio(image: Image.Image, uuid_str: str) -> str:
    """Salva a imagem no MinIO e retorna seu caminho."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S%f")
    image_filename = f"face_{timestamp}.png"
    minio_path = f"{uuid_str}/{image_filename}"

    image_bytes = BytesIO()
    image.save(image_bytes, format="PNG")
    image_bytes.seek(0)

    try:
        minio_client.put_object(
            BUCKET_RECONHECIMENTO,
            minio_path,
            image_bytes,
            len(image_bytes.getvalue()),
            content_type="image/png"
        )
        logger.info(f"✅ Imagem salva no MinIO: {minio_path}")
        return minio_path
    except S3Error as e:
        logger.error(f"❌ Erro ao salvar no MinIO: {e}")
        return None

# -------------------------------
# Processamento da Face com Embeddings
# -------------------------------
def process_face(image: Image.Image) -> dict:
    """Processa a imagem da face e realiza o reconhecimento."""
    start_time = datetime.now().timestamp()
    logger.info(f"Iniciando processamento da face em {start_time}")

    new_embedding = generate_embedding(image)
    if new_embedding is None:
        logger.error("❌ Falha ao gerar o embedding da face.")
        return {"error": "Falha na geração do embedding"}

    # Busca pessoas já cadastradas com imagens e embeddings
    known_people = list(pessoas.find({
        "image_paths": {"$exists": True, "$ne": []},
        "embeddings": {"$exists": True, "$ne": None, "$ne": []}
    }))

    match_found = False
    matched_uuid = None

    for pessoa in known_people:
        person_uuid = pessoa["uuid"]
        stored_embeddings = pessoa.get("embeddings", [])
        total_imagens = len(stored_embeddings)
        match_count = 0

        for stored_embedding in stored_embeddings:
            try:
                result = DeepFace.verify(
                    img1_path=new_embedding,
                    img2_path=stored_embedding,
                    enforce_detection=False,
                    model_name=MODEL_NAME
                )
                if result["distance"] < SIMILARITY_THRESHOLD:
                    match_count += 1
                    logger.info(f"Match {match_count} encontrado para UUID: {person_uuid}")
                    if (match_count / total_imagens) >= 0.2:
                        match_found = True
                        matched_uuid = person_uuid
                        logger.info(f"✅ Face reconhecida - UUID: {matched_uuid}")
                        break
            except Exception as e:
                logger.error(f"❌ Erro ao verificar embedding: {e}")

        if match_found:
            break

    # Se não houver correspondência, cria um novo usuário
    if not match_found:
        matched_uuid = str(uuid.uuid4())
        pessoas.insert_one({
            "uuid": matched_uuid,
            "image_paths": [],
            "embeddings": [],
            "tags": [matched_uuid]
        })
        logger.info(f"🆕 Nova face cadastrada - UUID: {matched_uuid}")

    # Envia a imagem para o MinIO e atualiza o MongoDB
    minio_path = upload_image_to_minio(image, matched_uuid)
    if minio_path:
        pessoas.update_one(
            {"uuid": matched_uuid},
            {"$push": {"image_paths": minio_path}}
        )
        logger.info("✅ Imagem atualizada no MongoDB")

    embedding = generate_embedding(image)
    if embedding:
        pessoas.update_one(
            {"uuid": matched_uuid},
            {"$push": {"embeddings": embedding}}
        )
        logger.info("✅ Embedding atualizado no MongoDB")

    pessoa = pessoas.find_one({"uuid": matched_uuid})
    primary_photo = pessoa["image_paths"][0] if pessoa and pessoa.get("image_paths") else None

    finish_time = datetime.now().timestamp()
    processing_time_ms = finish_time - start_time

    return {
        "uuid": matched_uuid,
        "tags": pessoa.get("tags", []),
        "primary_photo": primary_photo,
        "reconhecimento_path": minio_path,
        "inicio": start_time,
        "fim": finish_time,
        "tempo_processamento": processing_time_ms
    }

# -------------------------------
# Consumidor de Mensagens com Paralelismo
# -------------------------------
def callback(ch, method, properties, body):
    try:
        msg = json.loads(body)
        minio_path = msg.get("minio_path")
        if not minio_path:
            logger.error("❌ Mensagem inválida, ignorando...")
            ch.basic_ack(delivery_tag=method.delivery_tag)
            return

        logger.info(f"📩 Processando: {minio_path}")

        # Baixar imagem do MinIO
        response = minio_client.get_object(BUCKET_DETECCOES, minio_path)
        image = Image.open(BytesIO(response.read()))

        # Recupera outros dados da mensagem
        inicio_processamento = msg.get("inicio_processamento")
        tempo_captura_frame = msg.get("tempo_captura_frame")
        tempo_deteccao = msg.get("tempo_deteccao")
        data_captura_frame = msg.get("data_captura_frame")
        timestamp = msg.get("timestamp")
        tag_video = msg.get("tag_video")

        # Envia o processamento da face para o pool de processos
        future = executor.submit(process_face, image)
        result = future.result()

        # Cria a mensagem de saída com os dados processados
        output_msg = json.dumps({
            "data_captura_frame": data_captura_frame,
            "reconhecimento_path": result["reconhecimento_path"],
            "uuid": result["uuid"],
            "tags": result["tags"],
            "inicio_processamento": inicio_processamento,
            "tempo_captura_frame": tempo_captura_frame,
            "tempo_deteccao": tempo_deteccao,
            "tempo_reconhecimento": result["tempo_processamento"],
            "tag_video": tag_video,
            "timestamp": timestamp,
        })

        # Envia para a fila "reconhecimentos"
        channel.basic_publish(
            exchange="",
            routing_key="reconhecimentos",
            body=output_msg,
            properties=pika.BasicProperties(delivery_mode=2),
        )
        logger.info(f"✅ Reconhecimento enviado para fila 'reconhecimentos': {output_msg}")

        ch.basic_ack(delivery_tag=method.delivery_tag)

    except Exception as e:
        logger.error(f"❌ Erro no processamento: {e}")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

# -------------------------------
# Função Principal
# -------------------------------
def main():
    global executor
    executor = ProcessPoolExecutor(max_workers=4)
    channel.basic_consume(queue=QUEUE_NAME, on_message_callback=callback)
    print("🎯 Aguardando mensagens...")
    channel.start_consuming()

if __name__ == '__main__':
    freeze_support()  # Necessário para Windows ou sistemas que usem spawn
    main()
