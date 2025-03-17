import datetime
from bson import ObjectId
from fastapi import FastAPI, Body, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from deepface import DeepFace
import uuid
import os
import base64
import io
from PIL import Image
from pymongo import MongoClient
import shutil
from typing import List
from datetime import datetime
from minio import Minio
import logging
from io import BytesIO
from dotenv import load_dotenv


# ----------------------------
# Carregar Variáveis de Ambiente
# ----------------------------
load_dotenv()

# Configurações do MinIO
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY")
MINIO_BUCKET = os.getenv("MINIO_BUCKET")

MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME")

# ----------------------------
# Configuração de Logs
# ----------------------------

logger = logging.getLogger("server")
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

#bucket_name = "reconhecimento"

# ----------------------------
# Conexão com MongoDB
# ----------------------------
client = MongoClient(MONGO_URI)
db = client[MONGO_DB_NAME]
pessoas = db["pessoas"]
presencas = db["presencas"]

# ----------------------------
# Configuração do MinIO
# ----------------------------
minio_client = Minio(
    MINIO_ENDPOINT,
    access_key=MINIO_ACCESS_KEY,
    secret_key=MINIO_SECRET_KEY,
    secure=False
)

# ----------------------------
# Directorio Temporario
# ----------------------------
IMAGES_DIR = os.getenv("IMAGES_DIR")
os.makedirs(IMAGES_DIR, exist_ok=True)


# ----------------------------
# FastAPI App and Middleware
# ----------------------------
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve the images directory as static files
app.mount("/static", StaticFiles(directory=IMAGES_DIR), name="static")

# ----------------------------
# Pydantic Models
# ----------------------------
class ImagePayload(BaseModel):
    image: str  # Base64-encoded image

class TagPayload(BaseModel):
    tag: str

class FaceItem(BaseModel):
    image: str  # Base64 da imagem
    timestamp: int  # Timestamp enviado pelo frontend (em milissegundos)

class BatchImagePayload(BaseModel):
    images: List[FaceItem]

# ----------------------------
# Função para obter a URL da imagem no MinIO
# ----------------------------
from datetime import timedelta

import os
from datetime import timedelta

def get_presigned_url(object_name: str, expiration: int = 600) -> str:
    """
    Gera uma URL assinada (presigned URL) para acessar um arquivo no MinIO.
    A URL expira após `expiration` segundos (padrão: 10 minutos).
    """
    try:
        # Normaliza o caminho para usar '/'
        normalized_path = object_name.replace("\\", "/")

        # Remove prefixos desnecessários como 'data/faces/'
        if normalized_path.startswith("data/faces/"):
            normalized_path = normalized_path[len("data/faces/"):]

        url = minio_client.presigned_get_object(
            MINIO_BUCKET, 
            normalized_path, 
            expires=timedelta(seconds=expiration)  # Converte para timedelta
        )
        return url
    except Exception as e:
        logger.error(f"Erro ao gerar presigned URL: {e}")
        return None

# ----------------------------
# Endpoints
# ----------------------------

@app.get("/pessoas")
async def list_pessoas(page: int = 1, limit: int = 10):
    """
    Retorna uma lista paginada de pessoas com seus UUIDs e tags (sem fotos).
    """
    try:
        total = pessoas.count_documents({})
        skip = (page - 1) * limit
        cursor = pessoas.find({}).skip(skip).limit(limit)
        result = []
        for p in cursor:
            result.append({
                "uuid": p["uuid"],
                "tags": p.get("tags", [])
            })
        return JSONResponse({"pessoas": result, "total": total}, status_code=200)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/pessoas/{uuid}")
async def get_pessoa(uuid: str):
    """
    Retorna os detalhes de uma pessoa, incluindo UUID, tags e a URL assinada da foto principal no MinIO.
    """
    try:
        pessoa = pessoas.find_one({"uuid": uuid})
        if not pessoa:
            raise HTTPException(status_code=404, detail="Pessoa não encontrada")

        primary_photo = get_presigned_url(pessoa["image_paths"][0]) if pessoa.get("image_paths") else None

        return JSONResponse({
            "uuid": pessoa["uuid"],
            "tags": pessoa.get("tags", []),
            "primary_photo": primary_photo
        }, status_code=200)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)



@app.get("/pessoas/{uuid}/photos")
async def list_photos(uuid: str):
    """
    Retorna as URLs de todas as fotos de uma pessoa armazenadas no MinIO.
    """
    try:
        pessoa = pessoas.find_one({"uuid": uuid})
        if not pessoa:
            raise HTTPException(status_code=404, detail="Pessoa não encontrada")

        image_paths = pessoa.get("image_paths", [])
        image_urls = [get_presigned_url(path) for path in image_paths]

        return JSONResponse({"uuid": uuid, "image_urls": image_urls}, status_code=200)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/pessoas/{uuid}/photo")
async def get_primary_photo(uuid: str):
    """
    Retorna a URL da foto principal (primeira foto) de uma pessoa armazenada no MinIO.
    """
    try:
        pessoa = pessoas.find_one({"uuid": uuid})
        if not pessoa:
            raise HTTPException(status_code=404, detail="Pessoa não encontrada")

        image_paths = pessoa.get("image_paths", [])
        if not image_paths:
            raise HTTPException(status_code=404, detail="Nenhuma foto encontrada")

        primary_photo = get_presigned_url(image_paths[0])

        return JSONResponse({"uuid": uuid, "primary_photo": primary_photo}, status_code=200)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.delete("/pessoas/{uuid}")
async def delete_pessoa(uuid: str):
    """
    Exclui uma pessoa com o UUID fornecido e remove suas imagens do MinIO.
    """
    try:
        pessoa = pessoas.find_one({"uuid": uuid})
        if not pessoa:
            raise HTTPException(status_code=404, detail="Pessoa não encontrada")

        # Deletar imagens do MinIO
        for image_path in pessoa.get("image_paths", []):
            minio_client.remove_object(MINIO_BUCKET, image_path)

        # Deletar do banco de dados
        pessoas.delete_one({"uuid": uuid})

        return JSONResponse({"message": "Pessoa deletada com sucesso"}, status_code=200)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post("/pessoas/{uuid}/tags")
async def add_tag(uuid: str, payload: TagPayload):
    """
    Adiciona uma tag à pessoa com o UUID fornecido.
    """
    try:
        tag = payload.tag.strip()
        if not tag:
            raise HTTPException(status_code=400, detail="Tag inválida")
        result = pessoas.update_one(
            {"uuid": uuid},
            {"$push": {"tags": tag}}
        )
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Pessoa não encontrada")
        pessoa = pessoas.find_one({"uuid": uuid})
        primary_photo = None
        if pessoa.get("image_paths"):
            primary_photo = f"http://localhost:8000/static/{os.path.relpath(pessoa['image_paths'][0], IMAGES_DIR).replace(os.path.sep, '/')}"
        return JSONResponse({
            "message": "Tag adicionada com sucesso",
            "uuid": pessoa["uuid"],
            "tags": pessoa.get("tags", []),
            "primary_photo": primary_photo
        }, status_code=200)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.delete("/pessoas/{uuid}/tags")
async def remove_tag(uuid: str, payload: TagPayload):
    """
    Remove uma tag da pessoa com o UUID fornecido.
    """
    try:
        tag = payload.tag.strip()
        if not tag:
            raise HTTPException(status_code=400, detail="Tag inválida")
        result = pessoas.update_one(
            {"uuid": uuid},
            {"$pull": {"tags": tag}}
        )
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Pessoa não encontrada")
        pessoa = pessoas.find_one({"uuid": uuid})
        return JSONResponse({
            "message": "Tag removida com sucesso",
            "uuid": pessoa["uuid"],
            "tags": pessoa.get("tags", [])
        }, status_code=200)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/pessoas/{uuid}/photos/count")
async def count_photos(uuid: str):
    try:
        pessoa = pessoas.find_one({"uuid": uuid})
        if not pessoa:
            raise HTTPException(status_code=404, detail="Pessoa não encontrada")
        count = len(pessoa.get("image_paths", []))
        return JSONResponse({"uuid": uuid, "photo_count": count}, status_code=200)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.delete("/presencas/{id}")
async def delete_presenca(id: str):
    """
    Exclui o registro de presença com o _id fornecido.
    """
    try:
        result = presencas.delete_one({"_id": ObjectId(id)})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Presença não encontrada")
        return JSONResponse({"message": "Presença deletada com sucesso"}, status_code=200)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
    
@app.get("/presencas")
async def list_presencas(date: str = None, page: int = 1, limit: int = 10):
    """
    Retorna uma lista paginada de registros de presença filtrados pela data.
    As imagens são acessadas via presigned URLs (válidas por 10 minutos).
    """
    try:
        if not date:
            date = datetime.now().strftime("%Y-%m-%d")
        skip = (page - 1) * limit

        cursor = presencas.find({"data_captura_frame": date}).sort([("data_captura_frame", -1), ("hora_captura_frame", -1)]).skip(skip).limit(limit)
        results = []
        for p in cursor:
            foto_captura = p.get("foto_captura")
            foto_url = get_presigned_url(foto_captura) if foto_captura else None

            results.append({
                "id": str(p["_id"]),
                "uuid": p.get("pessoa"),
                "data_captura_frame": p.get("data_captura_frame"),
                "hora_captura_frame": p.get("hora_captura_frame"),
                "foto_captura": foto_url,  # URL válida por 10 min
                "tags": p.get("tags", []),
                "inicio": p.get("inicio"),
                "fim": p.get("fim"),
                "tempo_processamento": p.get("tempo_processamento")
            })

        total = presencas.count_documents({"data_captura_frame": date})
        return JSONResponse({"presencas": results, "total": total, "date": date}, status_code=200)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
@app.get("/presentes")
async def list_presentes(date: str, min_presencas: int):
    """
    Retorna uma lista de pessoas presentes na data especificada com pelo menos `min_presencas` registros de presença.
    """
    try:
        logger.info(f"Buscando presentes para a data: {date} com mínimo de presenças: {min_presencas}")

        # Filtrar presenças pela data e agrupar por pessoa
        pipeline = [
            {"$match": {"data_captura_frame": date}},
            {"$group": {"_id": "$pessoa", "count": {"$sum": 1}}},
            {"$match": {"count": {"$gte": min_presencas}}},
            {"$sort": {"count": -1}}  # Ordenar de forma decrescente pela quantidade de presenças
        ]
        presencas_agrupadas = list(presencas.aggregate(pipeline))
        logger.info(f"Presenças agrupadas: {presencas_agrupadas}")

        # Obter UUIDs das pessoas que atendem ao critério
        uuids = [p["_id"] for p in presencas_agrupadas]
        logger.info(f"UUIDs das pessoas que atendem ao critério: {uuids}")

        # Obter detalhes das pessoas
        pessoas_detalhes = pessoas.find({"uuid": {"$in": uuids}})
        result = []
        for pessoa in pessoas_detalhes:
            primary_photo = get_presigned_url(pessoa["image_paths"][0]) if pessoa.get("image_paths") else None
            presencas_count = next((p["count"] for p in presencas_agrupadas if p["_id"] == pessoa["uuid"]), 0)
            result.append({
                "uuid": pessoa["uuid"],
                "primary_photo": primary_photo,
                "tags": pessoa.get("tags", []),
                "presencas_count": presencas_count
            })
        logger.info(f"Detalhes das pessoas: {result}")

        return JSONResponse({"pessoas": result}, status_code=200)
    except Exception as e:
        logger.error(f"Erro ao buscar presentes: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

# To run:
# python -m uvicorn server:app --reload --host 0.0.0.0 --port 8000


