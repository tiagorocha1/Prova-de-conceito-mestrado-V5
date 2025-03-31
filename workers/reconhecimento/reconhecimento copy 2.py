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
channel.queue_declare(queue="reconhecimentos", durable=True)  # 🔹 Fila de saída

# -------------------------------
# Função de Processamento
# -------------------------------
def generate_embedding(image: Image.Image):
    """Gera o embedding facial usando DeepFace."""
    try:
        # Converter a imagem para numpy array
        image_np = np.array(image)
        
        # Gerar embedding diretamente da imagem em numpy array
        embeddings = DeepFace.represent(img_path=image_np, model_name=MODEL_NAME, enforce_detection=False)
        return embeddings[0]['embedding'] if embeddings else None
    except Exception as e:
        logger.error(f"❌ Erro ao gerar embedding: {e}")
        return None
    
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
    #existing_paths = pessoas.find_one({"uuid": uuid}).get("image_paths", [])
    #existing_hashes = {get_image_hash(minio_client.get_object(BUCKET_RECONHECIMENTO, path).read()) for path in existing_paths}

    #if get_image_hash(image_bytes.getvalue()) not in existing_hashes:
    try:
        minio_client.put_object(
            BUCKET_RECONHECIMENTO, minio_path, image_bytes, len(image_bytes.getvalue()), content_type="image/png"
        )
        logger.info(f"✅ Imagem salva no MinIO: {minio_path}")
        return minio_path
    except S3Error as e:
        logger.error(f"❌ Erro ao salvar no MinIO: {e}")
        return None
    #else:
    #    logger.info("Imagem já existente, não será reenviada para MinIO.")
    #    return None
    
# -------------------------------
# Processamento da Face com Embeddings
# -------------------------------

def process_face(image: Image.Image) -> dict:
    """Processa a imagem da face e realiza o reconhecimento."""
    start_time = datetime.now().timestamp()

    logger.info(f"Iniciando processamento da face em {start_time}")

    # 📌 Salvar a imagem temporariamente no disco antes de comparar
    #temp_file = os.path.join(TEMP_DIR, f"temp_input_{uuid.uuid4()}.png")
    #image.save(temp_file)
    
    new_embedding = generate_embedding(image)

    if new_embedding is None:
        logger.error("❌ Falha ao gerar o embedding da face.")
    #    os.remove(temp_file)
        return {"error": "Falha na geração do embedding"}

    # 📌 Busca apenas pessoas com imagens cadastradas
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

        for stored_embedding  in stored_embeddings:
            try:
                result = DeepFace.verify(
                    img1_path=new_embedding,
                    img2_path=stored_embedding,
                    enforce_detection=False,
                    model_name=MODEL_NAME
                )

                #if result.get("verified") is True:
                if result["distance"] < SIMILARITY_THRESHOLD:
                    match_count += 1
                    logger.info(f"Match {match_count} encontrado para UUID: {person_uuid}")
                    # Se a pessoa possuir menos de 3 imagens, consideramos o primeiro match suficiente
                    # Caso contrário, esperamos até que haja mais de 3 matchs
                    if (match_count / total_imagens) >= 0.2:
                        match_found = True
                        matched_uuid = person_uuid
                        logger.info(f"✅ Face reconhecida - UUID: {matched_uuid}")
                        break  # Sai do loop dos embeddings para essa pessoa
            except Exception as e:
                logger.error(f"❌ Erro ao verificar com {new_embedding}: {e}")

        if match_found:
            break

    # 📌 Se não houver correspondência, criar um novo usuário
    if not match_found:
        matched_uuid = str(uuid.uuid4())
        pessoas.insert_one({
            "uuid": matched_uuid,
            "image_paths": [],
            "embeddings": [],
            "tags": [matched_uuid]
        })
        logger.info(f"🆕 Nova face cadastrada - UUID: {matched_uuid}")

    # 📌 Enviar a imagem para MinIO e salvar no banco de dados
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

    # 📌 Obter a primeira foto como `primary_photo`
    pessoa = pessoas.find_one({"uuid": matched_uuid})
    primary_photo = pessoa["image_paths"][0] if pessoa and pessoa.get("image_paths") else None

    # Capturar tempo de término do processamento
    finish_time = datetime.now().timestamp()
    processing_time_ms = finish_time - start_time
    
    

    # 📌 Remover arquivos temporários
    #os.remove(temp_file)
    #if os.path.exists(stored_temp_path):
    #    os.remove(stored_temp_path)

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
        response = minio_client.get_object(BUCKET_DETECCOES, minio_path)
        image = Image.open(BytesIO(response.read()))
        
        # Tempos
        inicio_processamento = msg.get("inicio_processamento")
        tempo_captura_frame = msg.get("tempo_captura_frame")   
        tempo_deteccao = msg.get("tempo_deteccao")
        data_captura_frame = msg.get("data_captura_frame")
        timestamp = msg.get("timestamp")

        #Tag
        tag_video = msg.get("tag_video")

        # Capturar tempo de início do processamento
        start_time = datetime.now()

        # Processar reconhecimento facial
        result = process_face(image)

        # Capturar tempo de término do processamento
        #finish_time = datetime.now()
        #processing_time_ms = int((finish_time - start_time).total_seconds() * 1000)

        # Criar mensagem de saída com todas as informações
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
            "tags": result["tags"],
            "timestamp": timestamp,
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
        #os.remove(temp_face_path)

        ch.basic_ack(delivery_tag=method.delivery_tag)

    except Exception as e:
        logger.error(f"❌ Erro no processamento: {e}")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

# Iniciar consumidor
channel.basic_consume(queue=QUEUE_NAME, on_message_callback=callback)
print("🎯 Aguardando mensagens...")
channel.start_consuming()
