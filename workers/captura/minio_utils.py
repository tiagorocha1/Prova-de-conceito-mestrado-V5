import io
from minio import Minio
import os
from dotenv import load_dotenv

# ----------------------------
# Carregar Variáveis de Ambiente
# ----------------------------
load_dotenv()

# Configuração do MinIO
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY")
BUCKET_NAME = os.getenv("MINIO_BUCKET")

# Configuração do MinIO
minio_client = Minio(
    MINIO_ENDPOINT,
    access_key=MINIO_ACCESS_KEY,
    secret_key=MINIO_SECRET_KEY,
    secure=False
)

bucket_name = "frame"

# Criar bucket se não existir
if not minio_client.bucket_exists(bucket_name):
    minio_client.make_bucket(bucket_name)

def save_image_to_minio(image_buffer: io.BytesIO, object_name: str):
    """Salva uma imagem no MinIO dentro da subpasta do dia corrente (DD-MM-AAAA)."""
    file_size = image_buffer.getbuffer().nbytes

    try:
        minio_client.put_object(
            bucket_name,
            object_name,
            data=image_buffer,
            length=file_size,
            content_type="image/png"
        )
        print(f"✅ Imagem salva no MinIO: {object_name}")

    except Exception as e:
        print(f"❌ Erro ao salvar no MinIO: {e}")
