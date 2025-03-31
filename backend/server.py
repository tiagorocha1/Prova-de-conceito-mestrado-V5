import datetime
from bson import ObjectId
from fastapi import FastAPI, Body, HTTPException, Depends
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
from typing import List, Optional
from datetime import datetime, timedelta
from minio import Minio
import logging
from io import BytesIO
from dotenv import load_dotenv
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from typing import Optional
from passlib.context import CryptContext


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
      - o somatório de todos os campos "tempo_processamento_total" na variável "tempo_processamento_fonte",
      - o total de pessoas distintas no campo "pessoa" na variável "total_de_pessoas".
    As imagens são acessadas via presigned URLs (válidas por 10 minutos).
    """
    try:
        skip = (page - 1) * limit

        # Monta o filtro de consulta
        query = {}
        if tag_video:
            query["tag_video"] = tag_video
        if data_captura_frame:
            # Converte de YYYY-MM-DD (valor vindo do frontend) para DD-MM-YYYY (formato do banco)
            data_formatada = datetime.strptime(data_captura_frame, "%Y-%m-%d").strftime("%d-%m-%Y")
            query["data_captura_frame"] = data_formatada

        # Pipeline de agregação para somar o tempo_processamento_total de todos os documentos filtrados
        agg_pipeline = [
            {"$match": query},
            {"$group": {"_id": None, "total_tempo": {"$sum": {"$toDouble": "$tempo_processamento_total"}}}}
        ]
        agg_result = list(presencas.aggregate(agg_pipeline))
        if agg_result:
            tempo_processamento_fonte = agg_result[0].get("total_tempo", 0)
        else:
            tempo_processamento_fonte = 0

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
            })

        total = presencas.count_documents(query)
        return JSONResponse({
            "presencas": results,
            "total": total,
            "tempo_processamento_fonte": tempo_processamento_fonte,
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
        "hashed_password": get_password_hash("teste")
    }
    users.insert_one(admin_data)
    return JSONResponse({"message": "Usuário admin criado com sucesso."}, status_code=201)

# To run:
# python -m uvicorn server:app --reload --host 0.0.0.0 --port 8000


