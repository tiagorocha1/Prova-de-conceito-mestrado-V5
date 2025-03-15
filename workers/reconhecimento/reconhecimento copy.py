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
from minio.error import S3Error
from dotenv import load_dotenv

# -------------------------------
# Configurações
# -------------------------------

# Carregar variáveis de ambiente
load_dotenv()

TEMP_DIR = os.getenv("TEMP_DIR")
os.makedirs(TEMP_DIR, exist_ok=True)

# Configuração de logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuração de variáveis de ambiente
TEMP_DIR = os.getenv("TEMP_DIR")

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
SIMILARITY_THRESHOLD = 0.6


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
channel.queue_declare(queue="reconhecimentos", durable=True)  # 🔹 Fila de saída

# -------------------------------
# Função de Processamento
# -------------------------------
def generate_embedding(image_path):
    """Gera o embedding facial usando DeepFace."""
    try:
        embeddings = DeepFace.represent(img_path=image_path, model_name=MODEL_NAME)
        return embeddings[0]['embedding'] if embeddings else None
    except Exception as e:
        logger.error(f"❌ Erro ao gerar embedding: {e}")
        return None
    
def is_similar_embedding(new_embedding, existing_embeddings, threshold=SIMILARITY_THRESHOLD):
    """Verifica se o embedding gerado é similar a algum dos embeddings armazenados."""
    for existing_embedding in existing_embeddings:
        distance = np.linalg.norm(np.array(new_embedding) - np.array(existing_embedding))
        if distance < threshold:
            return True
    return False
    
def get_image_hash(image_bytes):
    """Calcula o hash MD5 de uma imagem."""
    return hashlib.md5(image_bytes).hexdigest()

def upload_image_to_minio(image: Image.Image, uuid: str) -> str:
    """Salva a imagem no MinIO e retorna seu caminho."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S%f")
    image_filename = f"face_{timestamp}.png"
    minio_path = f"{uuid}/{image_filename}"

    # Converter a imagem para bytes
    image_bytes = BytesIO()
    image.save(image_bytes, format="PNG")
    image_bytes.seek(0)

    # Verificar hash antes de fazer upload
    existing_paths = pessoas.find_one({"uuid": uuid}).get("image_paths", [])
    existing_hashes = {get_image_hash(minio_client.get_object(BUCKET_RECONHECIMENTO, path).read()) for path in existing_paths}

    if get_image_hash(image_bytes.getvalue()) not in existing_hashes:
        try:
            minio_client.put_object(
                BUCKET_RECONHECIMENTO, minio_path, image_bytes, len(image_bytes.getvalue()), content_type="image/png"
            )
            logger.info(f"✅ Imagem salva no MinIO: {minio_path}")
            return minio_path
        except S3Error as e:
            logger.error(f"❌ Erro ao salvar no MinIO: {e}")
            return None
    else:
        logger.info("Imagem já existente, não será reenviada para MinIO.")
        return None

def process_face(image: Image.Image, start_time: datetime = None) -> dict:
    """Processa a imagem da face e realiza o reconhecimento."""
    
    if start_time is None:
        start_time = datetime.now()

    logger.info(f"Iniciando processamento da face em {start_time}")

    # 📌 Salvar a imagem temporariamente no disco antes de comparar
    temp_file = os.path.join(TEMP_DIR, f"temp_input_{uuid.uuid4()}.png")
    image.save(temp_file)
    
    #new_embedding = generate_embedding(temp_file)

    # 📌 Busca apenas pessoas com imagens cadastradas
    known_people = list(pessoas.find({
                        "image_paths": {"$exists": True, "$ne": []},
                        "face_embedding": {"$exists": True, "$ne": None, "$ne": []}
                    }))

    match_found = False
    matched_uuid = None

    for pessoa in known_people:
        person_uuid = pessoa["uuid"]
        image_paths = pessoa.get("image_paths", [])

        for stored_image_path in image_paths:
            try:
                # 📌 Baixar imagem do MinIO para comparação
                stored_temp_path = os.path.join(TEMP_DIR, os.path.basename(stored_image_path))
                minio_client.fget_object(BUCKET_RECONHECIMENTO, stored_image_path, stored_temp_path)

                # 📌 Usar caminho do arquivo real no DeepFace
                result = DeepFace.verify(
                    img1_path=temp_file,
                    img2_path=stored_temp_path,
                    enforce_detection=False,
                    model_name=MODEL_NAME
                )

                if result.get("verified") is True:
                    match_found = True
                    matched_uuid = person_uuid
                    logger.info(f"✅ Face reconhecida - UUID: {matched_uuid}")
                    break
            except Exception as e:
                logger.error(f"❌ Erro ao verificar com {stored_image_path}: {e}")

        if match_found:
            break

    # 📌 Se não houver correspondência, criar um novo usuário
    if not match_found:
        matched_uuid = str(uuid.uuid4())
        pessoas.insert_one({
            "uuid": matched_uuid,
            "image_paths": [],
            "embeddings": [],
            "tags": []
        })
        logger.info(f"🆕 Nova face cadastrada - UUID: {matched_uuid}")

    # 📌 Enviar a imagem para MinIO e salvar no banco de dados
    minio_path = upload_image_to_minio(image, matched_uuid)
    if minio_path:
        pessoas.update_one(
            {"uuid": matched_uuid},
            {"$push": {"image_paths": minio_path}}
        )

    # 📌 Obter a primeira foto como `primary_photo`
    pessoa = pessoas.find_one({"uuid": matched_uuid})
    primary_photo = pessoa["image_paths"][0] if pessoa and pessoa.get("image_paths") else None

    # Capturar tempo de término do processamento
    finish_time = datetime.now()
    processing_time_ms = int((finish_time - start_time).total_seconds() * 1000)
    
    embedding = generate_embedding(temp_file)
    if embedding:
        pessoas.update_one(
            {"uuid": matched_uuid},
            {"$push": {"embeddings": embedding}}
        )
        logger.info("✅ Embedding atualizado no MongoDB")

    # 📌 Remover arquivos temporários
    os.remove(temp_file)
    if os.path.exists(stored_temp_path):
        os.remove(stored_temp_path)

    return {
        "uuid": matched_uuid,
        "tags": pessoa.get("tags", []),
        "primary_photo": primary_photo,
        "reconhecimento_path": minio_path,
        "inicio": start_time.strftime("%Y-%m-%d %H:%M:%S.%f"),
        "fim": finish_time.strftime("%Y-%m-%d %H:%M:%S.%f"),
        "tempo_processamento": processing_time_ms
    }



# -------------------------------
# Consumidor de Mensagens
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
        temp_face_path = os.path.join(TEMP_DIR, os.path.basename(minio_path))
        minio_client.fget_object(BUCKET_DETECCOES, minio_path, temp_face_path)
        
        # Dados da captura do frame
        data_captura = msg.get("data_captura_frame")
        hora_captura = msg.get("hora_captura_frame")

        # Capturar tempo de início do processamento
        start_time = datetime.now()
        
        # Abrir imagem
        image = Image.open(temp_face_path)

        # Processar reconhecimento facial
        result = process_face(image, start_time=start_time)

        # Capturar tempo de término do processamento
        finish_time = datetime.now()
        processing_time_ms = int((finish_time - start_time).total_seconds() * 1000)

        # Criar mensagem de saída com todas as informações
        output_msg = json.dumps({
            "reconhecimento_path": result["reconhecimento_path"],
            "uuid": result["uuid"],
            "tags": result["tags"],
            "data_captura_frame": data_captura,
            "hora_captura_frame": hora_captura,
            "inicio": result["inicio"],
            "fim": result["fim"],
            "tempo_processamento": result["tempo_processamento"]
        })

        # Enviar para RabbitMQ
        channel.basic_publish(
            exchange="",
            routing_key="reconhecimentos",
            body=output_msg,
            properties=pika.BasicProperties(delivery_mode=2),
        )
        logger.info(f"✅ Reconhecimento enviado para fila 'reconhecimentos': {output_msg}")

        # Remover arquivo temporário
        os.remove(temp_face_path)

        ch.basic_ack(delivery_tag=method.delivery_tag)

    except Exception as e:
        logger.error(f"❌ Erro no processamento: {e}")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

# Iniciar consumidor
channel.basic_consume(queue=QUEUE_NAME, on_message_callback=callback)
print("🎯 Aguardando mensagens...")
channel.start_consuming()
