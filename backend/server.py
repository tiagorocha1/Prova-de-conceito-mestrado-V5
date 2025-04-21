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
import matplotlib.pyplot as plt


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


