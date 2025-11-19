import datetime
from bson import ObjectId
from fastapi import FastAPI, Body, HTTPException, Depends
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional
from deepface import DeepFace
import uuid
import os
import base64
import io
from PIL import Image
from pymongo import MongoClient
import shutil
from typing import List, Optional
from datetime import datetime, timedelta
from minio import Minio
import logging
from io import BytesIO
from dotenv import load_dotenv
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from passlib.context import CryptContext
import matplotlib.pyplot as plt
import math
from sklearn.metrics import silhouette_score, homogeneity_score, completeness_score, v_measure_score
import numpy as np
import time




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

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES"))

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
users = db["users"]
frames = db["frames"]
fontes = db["fonte"]

class PresencaUpdate(BaseModel):
    confusionCategory: Optional[str] = None  # "TP", "TN", "FP", "FN", etc.
    gold_standard: Optional[str] = None      # rótulo verdadeiro / ID real



class FonteUpdate(BaseModel):
    # Todos opcionais porque PATCH = atualização parcial

    # Identificação / execução
    tag_video: Optional[str] = None
    timestamp_inicial: Optional[float] = None
    timestamp_final: Optional[float] = None
    modelo_utilizado: Optional[str] = None

    total_faces_analisadas: Optional[int] = None
    total_clusters_gerados: Optional[int] = None

    # contadores operacionais globais do experimento
    total_de_frames: Optional[int] = None
    tempo_total_processamento: Optional[float] = None
    quantidade_faces_nao_reconhecidas: Optional[int] = None

    # Métricas de classificação
    true_positives: Optional[int] = None
    true_negatives: Optional[int] = None
    false_positives: Optional[int] = None
    false_negatives: Optional[int] = None
    accuracy: Optional[float] = None
    precision: Optional[float] = None
    recall: Optional[float] = None
    f1_score: Optional[float] = None

    # Métricas de clusterização
    covering: Optional[float] = None
    inter_cluster_distance: Optional[float] = None
    intra_cluster_distance: Optional[float] = None
    silhouette: Optional[float] = None
    homogeneity: Optional[float] = None
    completeness: Optional[float] = None
    v_measure: Optional[float] = None

    # Métricas de desempenho
    time_to_complete_video_total_time: Optional[float] = None
    auxiliary_db_size: Optional[float] = None

    # Extras adicionados
    total_pessoas_gold_standard: Optional[int] = None  
    duracao: Optional[float] = None  



# ----------------------------
# Helper de serialização
# ----------------------------

def serialize_presenca(doc: dict) -> dict:
    if not doc:
        return None

    foto_captura = doc.get("foto_captura")
    foto_url = get_presigned_url(foto_captura) if foto_captura else None

    return {
        "id": str(doc.get("_id")),
        "uuid": doc.get("pessoa"),
        "tempo_processamento_total": doc.get("tempo_processamento_total"),
        "tempo_captura_frame": doc.get("tempo_captura_frame"),
        "tempo_deteccao": doc.get("tempo_deteccao"),
        "tempo_reconhecimento": doc.get("tempo_reconhecimento"),
        "foto_captura": foto_url,
        "tag_video": doc.get("tag_video"),
        "tags": doc.get("tags", []),
        "data_captura_frame": doc.get("data_captura_frame"),
        "timestamp_inicial": doc.get("timestamp_inicial"),
        "timestamp_final": doc.get("timestamp_final"),
        "tempo_fila": doc.get("tempo_fila_real"),
        "similarity_value": doc.get("similarity_value"),
        "confusionCategory": doc.get("confusionCategory")
    }


def serialize_fonte(doc: dict) -> dict:
    """
    Converte um documento cru do MongoDB em um dicionário pronto para resposta JSON.
    """
    if not doc:
        return None

    return {
        "id": str(doc.get("_id")),

        # Identificação do experimento
        "tag_video": doc.get("tag_video"),
        "timestamp_inicial": doc.get("timestamp_inicial"),
        "timestamp_final": doc.get("timestamp_final"),
        "modelo_utilizado": doc.get("modelo_utilizado"),

        # Contagem geral
        "total_faces_analisadas": doc.get("total_faces_analisadas"),
        "total_clusters_gerados": doc.get("total_clusters_gerados"),

        # 👇 Novos campos operacionais
        "total_de_frames": doc.get("total_de_frames"),
        "tempo_total_processamento": doc.get("tempo_total_processamento"),
        "quantidade_faces_nao_reconhecidas": doc.get("quantidade_faces_nao_reconhecidas"),

        # Métricas de classificação
        "true_positives": doc.get("true_positives"),
        "true_negatives": doc.get("true_negatives"),
        "false_positives": doc.get("false_positives"),
        "false_negatives": doc.get("false_negatives"),
        "accuracy": doc.get("accuracy"),
        "precision": doc.get("precision"),
        "recall": doc.get("recall"),
        "f1_score": doc.get("f1_score"),

        # Métricas de clusterização
        "covering": doc.get("covering"),
        "inter_cluster_distance": doc.get("inter_cluster_distance"),
        "intra_cluster_distance": doc.get("intra_cluster_distance"),
        "silhouette": doc.get("silhouette"),
        "homogeneity": doc.get("homogeneity"),
        "completeness": doc.get("completeness"),
        "v_measure": doc.get("v_measure"),

        # Métricas de desempenho
        "time_to_complete_video_total_time": doc.get("time_to_complete_video_total_time"),
        "auxiliary_db_size": doc.get("auxiliary_db_size"),

        "total_pessoas_gold_standard": doc.get("total_pessoas_gold_standard"),
        #tempo do video em segundos
        "duracao": doc.get("duracao"),
    }


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

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

class User(BaseModel):
    username: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    disabled: Optional[bool] = None

class UserInDB(User):
    hashed_password: str

# ----------------------------
# Funções de Autenticação
# ----------------------------
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception
    user = users.find_one({"username": token_data.username})
    if user is None:
        raise credentials_exception
    return UserInDB(**user)

async def get_current_active_user(current_user: User = Depends(get_current_user)):
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

# ----------------------------
# Grafico de Presença
# ----------------------------

def gerar_graficos_para_tag(tag_video: str, dados: list[dict], pasta_saida="static/plots"):
    if not os.path.exists(pasta_saida):
        os.makedirs(pasta_saida)

    numeros = [d["numero_frame"] for d in dados]
    detectados = [d["total_faces_detectadas"] for d in dados]
    reconhecidos = [d["total_faces_reconhecidas"] for d in dados]

    # Gráfico 1 - Detecção
    plt.figure()
    plt.plot(numeros, detectados, marker="o")
    plt.title(f"Detecções - {tag_video}")
    plt.xlabel("Número do Frame")
    plt.ylabel("Pessoas Detectadas")
    plt.grid(True)
    path_detectados = os.path.join(pasta_saida, f"{tag_video}_detectados.png")
    plt.savefig(path_detectados)
    plt.close()

    # Gráfico 2 - Reconhecimento
    plt.figure()
    plt.plot(numeros, reconhecidos, marker="o", color="green")
    plt.title(f"Reconhecimentos - {tag_video}")
    plt.xlabel("Número do Frame")
    plt.ylabel("Pessoas Reconhecidas")
    plt.grid(True)
    path_reconhecidos = os.path.join(pasta_saida, f"{tag_video}_reconhecidos.png")
    plt.savefig(path_reconhecidos)
    plt.close()

    # Retorna os caminhos relativos
    return f"/static/plots/{tag_video}_detectados.png", f"/static/plots/{tag_video}_reconhecidos.png"

# ----------------------------
# Endpoints de Autenticação
# ----------------------------
@app.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    user = users.find_one({"username": form_data.username})
    if not user or not verify_password(form_data.password, user["hashed_password"]):
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user["username"]}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/users/", response_model=User)
async def create_user(user: UserInDB):
    user.hashed_password = get_password_hash(user.hashed_password)
    users.insert_one(user.dict())
    return user

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
# Endpoints Protegidos
# ----------------------------

@app.get("/pessoas", dependencies=[Depends(get_current_active_user)])
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

@app.get("/pessoas/{uuid}", dependencies=[Depends(get_current_active_user)])
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



@app.get("/pessoas/{uuid}/photos", dependencies=[Depends(get_current_active_user)])
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

@app.get("/pessoas/{uuid}/photo", dependencies=[Depends(get_current_active_user)])
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

@app.delete("/pessoas/{uuid}", dependencies=[Depends(get_current_active_user)])
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

@app.post("/pessoas/{uuid}/tags", dependencies=[Depends(get_current_active_user)])
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

@app.delete("/pessoas/{uuid}/tags", dependencies=[Depends(get_current_active_user)])
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

@app.get("/pessoas/{uuid}/photos/count", dependencies=[Depends(get_current_active_user)])
async def count_photos(uuid: str):
    try:
        pessoa = pessoas.find_one({"uuid": uuid})
        if not pessoa:
            raise HTTPException(status_code=404, detail="Pessoa não encontrada")
        count = len(pessoa.get("image_paths", []))
        return JSONResponse({"uuid": uuid, "photo_count": count}, status_code=200)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.delete("/presencas/{id}", dependencies=[Depends(get_current_active_user)])
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
    


from datetime import datetime
from fastapi.responses import JSONResponse

@app.get("/presencas", dependencies=[Depends(get_current_active_user)])
async def list_presencas(
    page: int = 1,
    limit: int = 10,
    tag_video: Optional[str] = None,
    data_captura_frame: Optional[str] = None
):
    """
    Retorna uma lista paginada de registros de presença.
    Se os parâmetros "tag_video" ou "data_captura_frame" forem informados,
    filtra os registros pelo valor especificado.

    Além disso, retorna:
      - o somatório de tempo_captura_frame + tempo_deteccao + tempo_reconhecimento de todos os documentos como "tempo_processamento",
      - o somatório de tempo_fila_real (registrado) como "tempo_fila",
      - o total de pessoas distintas como "total_de_pessoas".
    """
    try:
        skip = (page - 1) * limit

        # Monta o filtro de consulta
        query = {}
        if tag_video:
            query["tag_video"] = tag_video
        if data_captura_frame:
            data_formatada = datetime.strptime(data_captura_frame, "%Y-%m-%d").strftime("%d-%m-%Y")
            query["data_captura_frame"] = data_formatada

        # Obtem os documentos filtrados para cálculo personalizado
        documentos = list(presencas.find(query))

        tempo_processamento = 0.0
        tempo_fila = 0.0

        for doc in documentos:
            captura = float(doc.get("tempo_captura_frame", 0))
            deteccao = float(doc.get("tempo_deteccao", 0))
            reconhecimento = float(doc.get("tempo_reconhecimento", 0))
            tempo_fila_real = float(doc.get("tempo_fila_real", 0))

            processamento = captura + deteccao + reconhecimento

            tempo_processamento += processamento
            tempo_fila += tempo_fila_real

        # Calcula o total de pessoas distintas
        distinct_personas = presencas.distinct("pessoa", query)
        total_de_pessoas = len(distinct_personas)

        # Busca os registros paginados
        cursor = presencas.find(query).sort([("inicio_processamento", -1)]).skip(skip).limit(limit)
        results = []
        for p in cursor:
            foto_captura = p.get("foto_captura")
            foto_url = get_presigned_url(foto_captura) if foto_captura else None

            results.append({
                "id": str(p["_id"]),
                "uuid": p.get("pessoa"),
                "tempo_processamento_total": p.get("tempo_processamento_total"),
                "tempo_captura_frame": p.get("tempo_captura_frame"),
                "tempo_deteccao": p.get("tempo_deteccao"),
                "tempo_reconhecimento": p.get("tempo_reconhecimento"),
                "foto_captura": foto_url,
                "tag_video": p.get("tag_video"),
                "tags": p.get("tags", []),
                "data_captura_frame": p.get("data_captura_frame"),
                "timestamp_inicial": p.get("timestamp_inicial"),
                "timestamp_final": p.get("timestamp_final"),
                "tempo_fila": p.get("tempo_fila_real"),
                "similarity_value": p.get("similarity_value"),
                "confusionCategory": p.get("confusionCategory"),
                "gold_standard": p.get("gold_standard"),
                
            })

        total = presencas.count_documents(query)

        return JSONResponse({
            "presencas": results,
            "total": total,
            "tempo_processamento": tempo_processamento,
            "tempo_fila": tempo_fila,
            "total_de_pessoas": total_de_pessoas
        }, status_code=200)

    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)






@app.get("/presentes", dependencies=[Depends(get_current_active_user)])
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
    
@app.get("/frames/estatisticas", dependencies=[Depends(get_current_active_user)])
async def estatisticas_frames(tag_video: str):
    """
    Retorna estatísticas sobre os frames com base na tag de vídeo fornecida.
    """
    try:
        query = {"tag_video": tag_video}

        # Total de frames com a tag
        total_frames = frames.count_documents(query)

        # Frame com menor quantidade de pessoas detectadas
        menor_frame = frames.find({"total_faces_detectadas": {"$gte": 1}}).sort("total_faces_detectadas", 1).limit(1)
        menor_qtd = None
        menor_uuid = None
        doc = next(menor_frame, None)
        if doc:
            menor_qtd = doc["total_faces_detectadas"]
            menor_uuid = doc["uuid"]

        # Frame com maior quantidade de pessoas detectadas
        maior_frame = frames.find({"total_faces_detectadas": {"$gte": 1}}).sort("total_faces_detectadas", -1).limit(1)
        maior_qtd = None
        maior_uuid = None
        doc = next(maior_frame, None)
        if doc:
            maior_qtd = doc["total_faces_detectadas"]
            maior_uuid = doc["uuid"]

        # Quantidade de frames com 0 pessoas detectadas
        frames_sem_pessoas = frames.count_documents({**query, "total_faces_detectadas": 0})

        return JSONResponse({
            "tag_video": tag_video,
            "total_frames": total_frames,
            "menor_qtd_faces_detectadas": menor_qtd,
            "uuid_menor_qtd": menor_uuid,
            "maior_qtd_faces_detectadas": maior_qtd,
            "uuid_maior_qtd": maior_uuid,
            "frames_sem_pessoas": frames_sem_pessoas
        }, status_code=200)

    except Exception as e:
        logger.error(f"Erro ao calcular estatísticas dos frames: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)
    
@app.get("/frames/agrupamentos", dependencies=[Depends(get_current_active_user)])
async def listar_agrupamentos_por_tag_video():
    """
    Retorna uma lista com informações agregadas por tag_video,
    incluindo total_pessoas, fps, duracao e gráficos de detecção e reconhecimento.
    """
    try:
        tags = frames.distinct("tag_video")
        resultados = []

        for tag_video in tags:
            query = {"tag_video": tag_video}

            total_frames = frames.count_documents(query)
            frames_sem_pessoas = frames.count_documents({**query, "total_faces_detectadas": 0})

            # Frame de exemplo para extrair fps e duracao
            frame_amostra = frames.find_one(query)
            fps = frame_amostra.get("fps") if frame_amostra else None
            duracao = frame_amostra.get("duracao") if frame_amostra else None

            # Pessoas distintas com presença ligada à tag_video
            pessoas_unicas = presencas.distinct("pessoa", {"tag_video": tag_video})
            total_pessoas = len(pessoas_unicas)

            # Frame com menor qtd de pessoas detectadas
            menor_doc = frames.find({**query, "total_faces_detectadas": {"$gte": 1}})\
                              .sort("total_faces_detectadas", 1).limit(1)
            menor_qtd, menor_uuid = None, None
            for doc in menor_doc:
                menor_qtd = doc["total_faces_detectadas"]
                menor_uuid = doc["uuid"]

            # Frame com maior qtd de pessoas detectadas
            maior_doc = frames.find({**query, "total_faces_detectadas": {"$gte": 1}})\
                              .sort("total_faces_detectadas", -1).limit(1)
            maior_qtd, maior_uuid = None, None
            for doc in maior_doc:
                maior_qtd = doc["total_faces_detectadas"]
                maior_uuid = doc["uuid"]

            # Buscar frames ordenados para gerar gráficos
            frames_ordenados = list(frames.find(query).sort("numero_frame", 1))

            # Gerar gráficos e obter paths relativos
            grafico_detectados, grafico_reconhecidos = gerar_graficos_para_tag(tag_video, frames_ordenados)

            resultados.append({
                "tag_video": tag_video,
                "total_frames": total_frames,
                "frames_sem_pessoas": frames_sem_pessoas,
                "menor_qtd_faces_detectadas": menor_qtd,
                "uuid_menor_qtd": menor_uuid,
                "maior_qtd_faces_detectadas": maior_qtd,
                "uuid_maior_qtd": maior_uuid,
                "total_pessoas": total_pessoas,
                "fps": fps,
                "duracao": duracao,
                "grafico_detectados": grafico_detectados,
                "grafico_reconhecidos": grafico_reconhecidos
            })

        return JSONResponse(resultados, status_code=200)

    except Exception as e:
        logger.error(f"Erro ao agrupar por tag_video: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/fontes", dependencies=[Depends(get_current_active_user)])
async def list_fontes(
    page: int = 1,
    limit: int = 10,
    tag_video: Optional[str] = None,
    modelo_utilizado: Optional[str] = None,
):
    """
    Lista fontes (execuções/experimentos) com paginação.
    Permite filtrar por tag_video e/ou modelo_utilizado.

    Isso vai ser útil para o dashboard comparar execuções
    e também pra você auditar como o sistema está performando.
    """
    try:
        query = {}
        if tag_video:
            query["tag_video"] = tag_video
        if modelo_utilizado:
            query["modelo_utilizado"] = modelo_utilizado

        skip = (page - 1) * limit
        total = fontes.count_documents(query)

        cursor = fontes.find(query)\
                       .sort("timestamp_inicial", -1)\
                       .skip(skip)\
                       .limit(limit)

        resultados = [serialize_fonte(doc) for doc in cursor]

        return JSONResponse({
            "fontes": resultados,
            "total": total,
            "page": page,
            "limit": limit
        }, status_code=200)

    except Exception as e:
        logger.error(f"Erro ao listar fontes: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/fontes/{id}", dependencies=[Depends(get_current_active_user)])
async def get_fonte(id: str):
    """
    Retorna uma única fonte pelo ID.
    Isso serve pra exibir a visão detalhada do experimento.
    """
    try:
        try:
            oid = ObjectId(id)
        except:
            raise HTTPException(status_code=400, detail="ID inválido")

        fonte_doc = fontes.find_one({"_id": oid})
        if not fonte_doc:
            raise HTTPException(status_code=404, detail="Fonte não encontrada")

        return JSONResponse(serialize_fonte(fonte_doc), status_code=200)

    except HTTPException:
        # deixa o FastAPI lidar com o HTTPException
        raise
    except Exception as e:
        logger.error(f"Erro ao buscar fonte {id}: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)
    
def _calc_covering(fonte_doc: dict, fonte_oid: ObjectId) -> float:
    """
    covering = (pessoas distintas rotuladas no gold_standard nessa fonte)
               / (total_pessoas_gold_standard declarado na fonte)

    Interpretação:
      - 1.0  => cobrimos todo mundo que deveria estar no vídeo
      - 0.5  => só metade das pessoas esperadas apareceu rotulada
      - 0.0  => ninguém do gold_standard apareceu identificado
    """
    total_gs_esperado = fonte_doc.get("total_pessoas_gold_standard")

    # Se não tem referência de quantas pessoas deveriam existir,
    # não dá pra calcular cobertura de forma honesta.
    if not total_gs_esperado or total_gs_esperado <= 0:
        return 0.0

    # pega todas as presenças dessa fonte que tenham um gold_standard definido
    docs = presencas.find(
        {
            "fonte_id": fonte_oid,
            "gold_standard": {"$exists": True, "$ne": None, "$ne": ""},
        },
        {"gold_standard": 1}
    )

    # extrai valores únicos de gold_standard
    pessoas_rotuladas = set()
    for d in docs:
        gs = d.get("gold_standard")
        if gs is not None and gs != "":
            pessoas_rotuladas.add(gs)

    pessoas_cobertas = len(pessoas_rotuladas)

    covering = pessoas_cobertas / float(total_gs_esperado)

    # só por segurança, clamp em [0,1]
    if covering < 0.0:
        covering = 0.0
    if covering > 1.0:
        covering = 1.0

    return covering



@app.patch("/fontes/{id}", dependencies=[Depends(get_current_active_user)])
async def update_fonte(id: str, fonte_update: FonteUpdate):
    """
    Atualiza parcialmente uma fonte.
    Essa rota é chamada pelo pipeline para:
      - atualizar timestamp_final (sempre que chega frame novo),
      - acumular total_faces_analisadas / total_clusters_gerados,
      - preencher métricas de classificação (precision, recall, etc.),
      - preencher métricas de clusterização (silhouette, v_measure, etc.),
      - preencher métricas de desempenho (time_to_complete_video_total_time, etc.).

    Exemplo de payload para fechar a execução:
    {
        "timestamp_final": 1730000000.0,
        "total_faces_analisadas": 482,
        "precision": 0.91,
        "recall": 0.88,
        "f1_score": 0.895,
        "time_to_complete_video_total_time": 0.82,
        "auxiliary_db_size": 134.7
    }
    """
    try:
        try:
            oid = ObjectId(id)
        except:
            raise HTTPException(status_code=400, detail="ID inválido")

        # só manda pro banco os campos realmente informados
        update_data = {k: v for k, v in fonte_update.dict().items() if v is not None}
        if not update_data:
            raise HTTPException(status_code=400, detail="Nada para atualizar")

        result = fontes.update_one({"_id": oid}, {"$set": update_data})

        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Fonte não encontrada")

        # buscar de volta após atualização
        fonte_doc = fontes.find_one({"_id": oid})

        return JSONResponse(serialize_fonte(fonte_doc), status_code=200)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao atualizar fonte {id}: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


# -------------------------------------------------
# Helpers internos para cálculo / acesso
# -------------------------------------------------

def _get_fonte_or_404(fonte_id_str: str):
    """
    Converte string em ObjectId, busca a fonte e retorna (oid, fonte_doc).
    Lança HTTPException se algo der errado.
    """
    try:
        oid = ObjectId(fonte_id_str)
    except:
        raise HTTPException(status_code=400, detail="ID inválido")

    fonte_doc = fontes.find_one({"_id": oid})
    if not fonte_doc:
        raise HTTPException(status_code=404, detail="Fonte não encontrada")

    return oid, fonte_doc


def _calc_tempo_total_processamento(fonte_doc: dict) -> float:
    """
    Calcula (timestamp_final - timestamp_inicial) da fonte.
    Se não houver timestamps ou se der negativo, retorna 0.0.
    """
    ts_ini = fonte_doc.get("timestamp_inicial")
    ts_fim = fonte_doc.get("timestamp_final")

    if ts_ini is not None and ts_fim is not None:
        dur = float(ts_fim) - float(ts_ini)
        if dur < 0:
            dur = 0.0
        return dur
    return 0.0


def _calc_frames_stats(fonte_oid: ObjectId, tag_video_da_fonte: str) -> dict:
    """
    Calcula totais de frames relacionados à fonte:
      - total_de_frames =
          frames_com_faces (frames que já têm fonte_id)
        + frames_sem_faces (frames do mesmo tag_video sem fonte_id)
    Retorna dict:
      {
        "total_de_frames": int
      }
    """
    filtro_fonte = {"fonte_id": fonte_oid}

    frames_com_faces = frames.count_documents(filtro_fonte)

    filtro_sem_faces = {
        "tag_video": tag_video_da_fonte,
        "fonte_id": {"$exists": False},
    }
    frames_sem_faces = frames.count_documents(filtro_sem_faces)

    total_de_frames = frames_com_faces + frames_sem_faces

    return {
        "total_de_frames": total_de_frames
    }


def _calc_faces_clusters_stats(fonte_oid: ObjectId, tag_video_da_fonte: str) -> dict:
    """
    Calcula:
      - total_faces_analisadas = presenças com essa fonte_id
      - total_clusters_gerados = pessoas dessa tag_video (cada pessoa = cluster)
    Retorna dict:
      {
        "total_faces_analisadas": int,
        "total_clusters_gerados": int
      }
    """
    total_faces_analisadas = presencas.count_documents({"fonte_id": fonte_oid})

    pessoas_docs = list(pessoas.find({"tag_video": tag_video_da_fonte}))
    total_clusters_gerados = len(pessoas_docs)

    return {
        "total_faces_analisadas": total_faces_analisadas,
        "total_clusters_gerados": total_clusters_gerados,
        "pessoas_docs": pessoas_docs,  # vamos reutilizar para inter_cluster_distance
    }


def _calc_confusion_metrics(fonte_oid: ObjectId, pessoas_nao_cobertas: int) -> dict:
    """
    Lê confusionCategory dos docs de presencas ligados à fonte e computa:
      TP, TN, FP, FN, accuracy, precision, recall, f1_score

    Retorna dict:
      {
        "TP": int, "TN": int, "FP": int, "FN": int,
        "accuracy": float,
        "precision": float,
        "recall": float,
        "f1_score": float
      }
    """
    TP = presencas.count_documents({"fonte_id": fonte_oid, "confusionCategory": "TP"})
    TN = presencas.count_documents({"fonte_id": fonte_oid, "confusionCategory": "TN"})
    FP = presencas.count_documents({"fonte_id": fonte_oid, "confusionCategory": "FP"})
    FN = pessoas_nao_cobertas  # presenças que deveriam ter ocorrido, mas não ocorreram

    total_all = TP + TN + FP + FN

    if total_all > 0:
        accuracy = (TP + TN) / total_all
    else:
        accuracy = 0.0

    if (TP + FP) > 0:
        precision = TP / (TP + FP)
    else:
        precision = 0.0

    if (TP + FN) > 0:
        recall = TP / (TP + FN)
    else:
        recall = 0.0

    if (precision + recall) > 0:
        f1_score = 2 * (precision * recall) / (precision + recall)
    else:
        f1_score = 0.0

    return {
        "TP": TP,
        "TN": TN,
        "FP": FP,
        "FN": FN,
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "f1_score": f1_score,
    }

def _calc_centroid(embs: list[list[float]]) -> list[float] | None:
    """
    Calcula o centróide (média coordenada-a-coordenada) de uma lista de embeddings
    de uma pessoa. Ignora embeddings vazios/dimensionados errado.
    Retorna o vetor centróide ou None se não conseguir.
    """
    if not embs:
        return None

    dim = len(embs[0])
    if dim == 0:
        return None

    # Verifica se há ao menos um embedding válido com esse dim
    valid_embs = [e for e in embs if isinstance(e, list) and len(e) == dim]
    if not valid_embs:
        return None

    centroid = []
    for k in range(dim):
        soma_k = 0.0
        for e in valid_embs:
            soma_k += float(e[k])
        centroid.append(soma_k / len(valid_embs))

    return centroid


def _euclidean_distance(a: list[float], b: list[float]) -> float:
    """
    Distância euclidiana padrão entre dois vetores de mesma dimensão.
    """
    dist_sq = 0.0
    for i in range(len(a)):
        diff = a[i] - b[i]
        dist_sq += diff * diff
    return math.sqrt(dist_sq)


def _calc_inter_cluster_distance(pessoas_docs: list[dict]) -> float:
    """
    inter_cluster_distance:
      - Para cada pessoa (cluster), calcula um centróide.
      - Mede a distância euclidiana entre todos os pares de centróides.
      - Retorna a média dessas distâncias.
      - Se houver menos de 2 centróides válidos, retorna 0.0.
    """
    centroids: list[list[float]] = []

    for pessoa_doc in pessoas_docs:
        embs = pessoa_doc.get("embeddings", [])
        centroid = _calc_centroid(embs)
        if centroid is not None:
            centroids.append(centroid)

    if len(centroids) < 2:
        return 0.0

    soma_dist = 0.0
    pares = 0
    for i in range(len(centroids)):
        for j in range(i + 1, len(centroids)):
            soma_dist += _euclidean_distance(centroids[i], centroids[j])
            pares += 1

    if pares == 0:
        return 0.0

    return soma_dist / pares


def _calc_intra_cluster_distance(pessoas_docs: list[dict]) -> float:
    """
    intra_cluster_distance:
      - Para cada pessoa:
          - calcula o centróide dessa pessoa
          - calcula a distância euclidiana de cada embedding dessa pessoa até o centróide
          - tira a média dessas distâncias -> "dispersão" daquele cluster
      - Depois tira a média dessas dispersões entre todas as pessoas que tinham embeddings válidos.

      Interpretação:
        * menor = clusters mais coesos (bom).
    """
    dispersoes_por_pessoa: list[float] = []

    for pessoa_doc in pessoas_docs:
        embs = pessoa_doc.get("embeddings", [])
        if not embs:
            continue

        centroid = _calc_centroid(embs)
        if centroid is None:
            continue

        # filtra embeddings válidos (mesmo dim do centróide)
        dim = len(centroid)
        valid_embs = [e for e in embs if isinstance(e, list) and len(e) == dim]
        if not valid_embs:
            continue

        # distâncias de cada embedding até o centróide
        distancias = []
        for e in valid_embs:
            distancias.append(_euclidean_distance(e, centroid))

        if distancias:
            media_cluster = sum(distancias) / len(distancias)
            dispersoes_por_pessoa.append(media_cluster)

    if not dispersoes_por_pessoa:
        return 0.0

    # média entre todas as pessoas
    return sum(dispersoes_por_pessoa) / len(dispersoes_por_pessoa)

def _calc_silhouette_score(pessoas_docs):
    # Coleta todos os embeddings e rótulos correspondentes
    X = []
    labels = []
    for idx, pessoa in enumerate(pessoas_docs):
        for emb in pessoa.get("embeddings", []):
            X.append(emb)
            labels.append(idx)  # cluster ID da pessoa

    if len(set(labels)) < 2:
        return None  # Silhouette não é definido para apenas 1 cluster

    X = np.array(X, dtype=np.float32)
    labels = np.array(labels)

    try:
        score = silhouette_score(X, labels, metric="euclidean")
        return float(score)
    except Exception as e:
        print("Erro ao calcular silhouette:", e)
        return None
    
def _calc_cluster_label_metrics(fonte_oid: ObjectId) -> dict:
    """
    Usa as presenças desta fonte para calcular:
      - homogeneity
      - completeness
      - v_measure

    Precisamos que cada presença tenha:
      - gold_standard  (classe verdadeira / ID real)
      - pessoa         (cluster atribuído pelo sistema)

    Retorna:
      {
        "homogeneity": float,
        "completeness": float,
        "v_measure": float
      }

    Se não houver dados suficientes (ex: só um rótulo único ou só um cluster),
    retorna 0.0 para todos.
    """

    # buscar todas as presenças dessa fonte
    docs = list(presencas.find({"fonte_id": fonte_oid}))

    true_labels = []
    pred_labels = []

    for d in docs:
        gs = d.get("gold_standard")
        cluster_id = d.get("pessoa")
        # só usamos se os dois existem
        if gs is None or cluster_id is None:
            continue
        true_labels.append(gs)
        pred_labels.append(cluster_id)

    # precisamos ter pelo menos 2 classes/2 clusters para métricas fazerem sentido
    # condições mínimas:
    # - pelo menos dois clusters diferentes previstos
    # - pelo menos dois rótulos verdadeiros diferentes
    if len(true_labels) < 2:
        return {
            "homogeneity": 0.0,
            "completeness": 0.0,
            "v_measure": 0.0
        }

    if len(set(pred_labels)) < 2 or len(set(true_labels)) < 2:
        # se só tem 1 cluster ou só 1 classe verdadeira,
        # homogeneity/completeness/v_measure acabam degeneradas.
        # Você PODE ainda calcular, mas normalmente escolhemos devolver 0.0
        # pra sinalizar "não tem diversidade suficiente".
        try:
            h = homogeneity_score(true_labels, pred_labels)
            c = completeness_score(true_labels, pred_labels)
            v = v_measure_score(true_labels, pred_labels)
        except Exception:
            h = c = v = 0.0

        return {
            "homogeneity": float(h),
            "completeness": float(c),
            "v_measure": float(v),
        }

    # caso geral normal
    h = homogeneity_score(true_labels, pred_labels)
    c = completeness_score(true_labels, pred_labels)
    v = v_measure_score(true_labels, pred_labels)

    return {
        "homogeneity": float(h),
        "completeness": float(c),
        "v_measure": float(v),
    }

def _calc_faces_nao_reconhecidas(fonte_doc: dict, fonte_oid: ObjectId) -> int:
    """
    Calcula quantas pessoas esperadas (total_pessoas_gold_standard)
    NÃO apareceram nenhuma vez nas presenças dessa fonte.

    Regra:
      pessoas_cobertas = número de gold_standard distintos presentes em presencas dessa fonte
      resultado = total_pessoas_gold_standard - pessoas_cobertas (min 0)
    """
    total_esperado = fonte_doc.get("total_pessoas_gold_standard")

    # se não tiver anotado ainda, não conseguimos calcular
    if total_esperado is None:
        return 0

    # pega todos os gold_standard dessa fonte
    distinct_gold = presencas.distinct(
        "gold_standard",
        {"fonte_id": fonte_oid, "gold_standard": {"$exists": True, "$ne": None, "$ne": ""}}
    )
    pessoas_cobertas = len(distinct_gold)

    faltantes = total_esperado - pessoas_cobertas
    if faltantes < 0:
        faltantes = 0

    return faltantes

def _calc_ratio_tempo_real(fonte_doc: dict) -> Optional[float]:
    """
    Calcula o quão 'tempo real' foi a execução:
      ratio_tempo_real = tempo_total_processamento / duracao

    Retorna None se faltar algum dado.
    """
    duracao = fonte_doc.get("duracao")
    tempo_total_proc = fonte_doc.get("tempo_total_processamento")

    if not duracao or duracao <= 0 or tempo_total_proc is None:
        return None

    ratio = tempo_total_proc / float(duracao)
    return round(ratio, 3)



# -------------------------------------------------
# Rota principal de recalcular
# -------------------------------------------------
@app.post("/fontes/{id}/recalcular", dependencies=[Depends(get_current_active_user)])
async def recalcular_fonte(id: str):
    """
    Recalcula e persiste métricas agregadas da execução ('fonte').

    Métricas calculadas:
      - total_de_frames
      - total_faces_analisadas
      - total_clusters_gerados
      - tempo_total_processamento

      - true_positives / true_negatives / false_positives / false_negatives
      - accuracy / precision / recall / f1_score

      - inter_cluster_distance / intra_cluster_distance
      - silhouette
      - homogeneity / completeness / v_measure
    """
    try:
        # 1. carrega fonte
        oid, fonte_doc = _get_fonte_or_404(id)
        tag_video_da_fonte = fonte_doc.get("tag_video")

        # 2. duração da execução
        tempo_total_processamento = _calc_tempo_total_processamento(fonte_doc)
        time_to_complete_video_total_time = _calc_ratio_tempo_real({
                                "duracao": fonte_doc.get("duracao"),
                                "tempo_total_processamento": tempo_total_processamento
                            })

        # 3. frames
        frames_stats = _calc_frames_stats(oid, tag_video_da_fonte)
        total_de_frames = frames_stats["total_de_frames"]

        # 4. faces & clusters
        faces_clusters_stats = _calc_faces_clusters_stats(oid, tag_video_da_fonte)
        total_faces_analisadas = faces_clusters_stats["total_faces_analisadas"]
        total_clusters_gerados = faces_clusters_stats["total_clusters_gerados"]
        pessoas_docs = faces_clusters_stats["pessoas_docs"]

        # 5. métricas de cobertura
        pessoas_nao_cobertas = _calc_faces_nao_reconhecidas(fonte_doc, oid)

        # 6. classificação (confusion matrix + métricas derivadas)
        confusion_stats = _calc_confusion_metrics(oid, pessoas_nao_cobertas)
        TP = confusion_stats["TP"]
        TN = confusion_stats["TN"]
        FP = confusion_stats["FP"]
        FN = confusion_stats["FN"]

        accuracy = confusion_stats["accuracy"]
        precision = confusion_stats["precision"]
        recall = confusion_stats["recall"]
        f1_score = confusion_stats["f1_score"]

        # 7. clusterização geométrica (sem rótulo verdadeiro)
        inter_cluster_distance = _calc_inter_cluster_distance(pessoas_docs)
        intra_cluster_distance = _calc_intra_cluster_distance(pessoas_docs)
        silhouette = _calc_silhouette_score(pessoas_docs)

        # 8. métricas supervisionadas de clusterização (usam gold_standard)
        label_metrics = _calc_cluster_label_metrics(oid)
        homogeneity = label_metrics["homogeneity"]
        completeness = label_metrics["completeness"]
        v_measure = label_metrics["v_measure"]

       

        # 9. métrica de covering
        covering = _calc_covering(fonte_doc, oid)

        # 10. montar update final
        update_data = {
            # operacionais
            "total_de_frames": total_de_frames,
            "total_faces_analisadas": total_faces_analisadas,
            "total_clusters_gerados": total_clusters_gerados,
            "tempo_total_processamento": tempo_total_processamento,
            "time_to_complete_video_total_time": time_to_complete_video_total_time,

            # classificação
            "true_positives": TP,
            "true_negatives": TN,
            "false_positives": FP,
            "false_negatives": FN,
            "accuracy": accuracy,
            "precision": precision,
            "recall": recall,
            "f1_score": f1_score,

            # clusterização geométrica
            "inter_cluster_distance": inter_cluster_distance,
            "intra_cluster_distance": intra_cluster_distance,
            "silhouette": silhouette,

            # clusterização supervisionada (gold standard)
            "homogeneity": homogeneity,
            "completeness": completeness,
            "v_measure": v_measure,

            # Métricas de cobertura
             "quantidade_faces_nao_reconhecidas": pessoas_nao_cobertas,

            # cobertura
            "covering": covering, 
        }

        result = fontes.update_one({"_id": oid}, {"$set": update_data})
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Fonte não encontrada ao atualizar")

        # 9. retornar a versão atualizada
        fonte_atualizada = fontes.find_one({"_id": oid})
        return JSONResponse(serialize_fonte(fonte_atualizada), status_code=200)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao recalcular fonte %s: %s", id, e)
        return JSONResponse({"error": str(e)}, status_code=500)


@app.patch("/presencas/{id}", dependencies=[Depends(get_current_active_user)])
async def atualizar_presenca(id: str, payload: PresencaUpdate):
    """
    Atualiza campos manuais de um registro de presença:
      - confusionCategory (TP/TN/FP/FN)
      - gold_standard (identidade real no gold standard)
    """
    try:
        try:
            oid = ObjectId(id)
        except:
            raise HTTPException(status_code=400, detail="ID inválido")

        update_fields = {}
        if payload.confusionCategory is not None:
            update_fields["confusionCategory"] = payload.confusionCategory
        if payload.gold_standard is not None:
            update_fields["gold_standard"] = payload.gold_standard

        if not update_fields:
            raise HTTPException(status_code=400, detail="Nada para atualizar")

        result = presencas.update_one(
            {"_id": oid},
            {"$set": update_fields}
        )

        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Presença não encontrada")

        # retornar o doc atualizado
        doc = presencas.find_one({"_id": oid})
        # gerar URL assinada pra foto (igual você faz em /presencas GET)
        foto_captura = doc.get("foto_captura")
        foto_url = get_presigned_url(foto_captura) if foto_captura else None

        return JSONResponse({
            "id": str(doc["_id"]),
            "uuid": doc.get("pessoa"),
            "tempo_processamento_total": doc.get("tempo_processamento_total"),
            "tag_video": doc.get("tag_video"),
            "confusionCategory": doc.get("confusionCategory"),
            "gold_standard": doc.get("gold_standard"),
            "foto_captura": foto_url,
        }, status_code=200)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao atualizar presença %s: %s", id, e)
        return JSONResponse({"error": str(e)}, status_code=500)


class FonteManualCreate(BaseModel):
    tag_video: str
    modelo_utilizado: str
    duracao: Optional[float] = None  # em segundos, pode vir null
    total_pessoas_gold_standard: Optional[int] = None  # opcional no cadastro inicial

@app.post("/fontes/manual", dependencies=[Depends(get_current_active_user)])
async def criar_fonte_manual(fonte_input: FonteManualCreate):
    """
    Cria manualmente uma fonte (execução) mesmo que não exista nenhuma presença registrada.
    Só cria se ainda não existir uma fonte com (tag_video, modelo_utilizado).

    Essa rota é útil pra registrar execuções "vazias":
    - vídeos onde ninguém foi reconhecido
    - execuções de teste
    - cenários onde queremos monitorar tempo/duração mesmo sem match
    """
    try:
        # verifica se já existe
        existente = fontes.find_one({
            "tag_video": fonte_input.tag_video,
            "modelo_utilizado": fonte_input.modelo_utilizado
        })
        if existente:
            # já existe, só retorna ela serializada
            return JSONResponse(serialize_fonte(existente), status_code=200)

        agora = time.time()  # epoch seconds float

        nova_fonte = {
            # Identificação / metadata básica
            "tag_video": fonte_input.tag_video,
            "modelo_utilizado": fonte_input.modelo_utilizado,
            "duracao": fonte_input.duracao,
            "total_pessoas_gold_standard": fonte_input.total_pessoas_gold_standard,

            # timestamps
            "timestamp_inicial": agora,
            "timestamp_final": agora,

            # contadores operacionais
            "total_faces_analisadas": 0,
            "total_clusters_gerados": 0,
            "total_de_frames": 0,
            "tempo_total_processamento": 0.0,

            # este campo pode ser calculado depois,
            # mas aqui iniciamos em 0 (nenhuma face reconhecida)
            "quantidade_faces_nao_reconhecidas": 0,

            # métricas de classificação
            "true_positives": 0,
            "true_negatives": 0,
            "false_positives": 0,
            "false_negatives": 0,
            "accuracy": None,
            "precision": None,
            "recall": None,
            "f1_score": None,

            # métricas de clusterização geométrica
            "covering": None,
            "inter_cluster_distance": None,
            "intra_cluster_distance": None,
            "silhouette": None,

            # métricas de clusterização supervisionada
            "homogeneity": None,
            "completeness": None,
            "v_measure": None,

            # métricas de desempenho
            # ratio_tempo_real (duracao / tempo_total_proc) já vive aqui
            "time_to_complete_video_total_time": None,

            # tamanho do banco auxiliar
            "auxiliary_db_size": None,
        }

        insert_result = fontes.insert_one(nova_fonte)
        nova_fonte["_id"] = insert_result.inserted_id

        return JSONResponse(serialize_fonte(nova_fonte), status_code=201)

    except Exception as e:
        logger.error(f"Erro ao criar fonte manual: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


from math import ceil
from fastapi import Query

@app.get("/clusters", dependencies=[Depends(get_current_active_user)])
async def listar_clusters_por_tag_video(
    tag_video: str = Query(..., min_length=1),
    page: int = Query(1, ge=1),
    limit: int = Query(24, ge=1, le=200),
    sort: str = Query("last_seen_desc"),
):
    """
    Lista clusters (pessoas) de uma determinada tag_video,
    agrupando presenças por 'pessoa' e mostrando métricas básicas.

    Cada cluster corresponde a uma 'pessoa' detectada no vídeo.
    """

    try:
        # Escolhe critério de ordenação
        sort_stage = {
            "last_seen_desc": {"$sort": {"last_seen": -1}},
            "count_desc": {"$sort": {"qtd_presencas": -1}},
            "first_seen_asc": {"$sort": {"first_seen": 1}},
        }.get(sort, {"$sort": {"last_seen": -1}})

        skip = (page - 1) * limit

        pipeline = [
            {"$match": {"tag_video": tag_video}},
            {
                "$group": {
                    "_id": "$pessoa",
                    "qtd_presencas": {"$sum": 1},
                    "first_seen": {"$min": "$timestamp_inicial"},
                    "last_seen": {"$max": "$timestamp_final"},
                    "gold_standards": {"$addToSet": "$gold_standard"},
                    "tp": {
                        "$sum": {"$cond": [{"$eq": ["$confusionCategory", "TP"]}, 1, 0]}
                    },
                    "tn": {
                        "$sum": {"$cond": [{"$eq": ["$confusionCategory", "TN"]}, 1, 0]}
                    },
                    "fp": {
                        "$sum": {"$cond": [{"$eq": ["$confusionCategory", "FP"]}, 1, 0]}
                    },
                    "fn": {
                        "$sum": {"$cond": [{"$eq": ["$confusionCategory", "FN"]}, 1, 0]}
                    },
                }
            },
            {
                "$lookup": {
                    "from": "pessoas",
                    "localField": "_id",
                    "foreignField": "uuid",
                    "as": "pessoa_doc",
                }
            },
            {
                "$project": {
                    "_id": 0,
                    "pessoa": {"$ifNull": ["$_id", ""]},
                    "qtd_presencas": 1,
                    "first_seen": 1,
                    "last_seen": 1,
                    "gold_standards": 1,
                    "confusion_breakdown": {
                        "TP": "$tp",
                        "TN": "$tn",
                        "FP": "$fp",
                        "FN": "$fn",
                    },
                    "tag_video": tag_video,
                    "last_appearance": {
                        "$ifNull": [
                            {"$arrayElemAt": ["$pessoa_doc.last_appearance", 0]},
                            None,
                        ]
                    },
                    "all_images": {
                        "$slice": [
                            {"$ifNull": [{"$arrayElemAt": ["$pessoa_doc.image_paths", 0]}, []]},
                            8,
                        ]
                    },
                }
            },
            {
                "$addFields": {
                    "thumb": {
                        "$cond": [
                            {"$gt": [{"$size": "$all_images"}, 0]},
                            {"$arrayElemAt": ["$all_images", 0]},
                            None,
                        ]
                    }
                }
            },
            sort_stage,
            {
                "$facet": {
                    "data": [{"$skip": skip}, {"$limit": limit}],
                    "meta": [{"$count": "total"}],
                }
            },
        ]

        result = list(presencas.aggregate(pipeline))
        if not result:
            return JSONResponse(
                {"clusters": [], "total": 0, "page": page, "pages": 0, "limit": limit},
                status_code=200,
            )

        data = result[0].get("data", [])
        meta = result[0].get("meta", [])
        total = meta[0]["total"] if meta else 0
        pages = ceil(total / limit) if total else 0

        # monta URLs assinadas
        for c in data:
            if c.get("thumb"):
                c["thumb_url"] = get_presigned_url(c["thumb"])

        return JSONResponse(
            {"clusters": data, "total": total, "page": page, "pages": pages, "limit": limit},
            status_code=200,
        )

    except Exception as e:
        logger.error(f"Erro ao listar clusters para tag_video {tag_video}: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/create_admin")
async def create_admin():
    # Verifica se o usuário admin já existe
    existing_admin = users.find_one({"username": "admin"})
    if existing_admin:
        return JSONResponse({"message": "O usuário admin já foi criado."}, status_code=400)
    
    # Cria o usuário admin com a senha especificada
    admin_data = {
        "username": "admin",
        "email": None,
        "full_name": "Admin",
        "disabled": False,
        "hashed_password": get_password_hash("admin")
    }
    users.insert_one(admin_data)
    return JSONResponse({"message": "Usuário admin criado com sucesso."}, status_code=201)

# To run:
# python -m uvicorn server:app --reload --host 0.0.0.0 --port 8000


