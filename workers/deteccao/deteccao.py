# silenciar logs do TensorFlow/absl
import os
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
import logging
logging.getLogger('absl').setLevel(logging.ERROR)

# imports principais
import time
import json
from datetime import datetime
from io import BytesIO

import cv2
import numpy as np
import pika
import mediapipe as mp
from dotenv import load_dotenv
from minio import Minio
from minio.error import S3Error
from pymongo import MongoClient, ReturnDocument

# resto do seu script…


# ----------------------------------------
# Carrega variáveis de ambiente
# ----------------------------------------
load_dotenv()

RABBITMQ_HOST            = os.getenv('RABBITMQ_HOST')
RABBITMQ_QUEUE           = os.getenv('RABBITMQ_QUEUE')
MINIO_ENDPOINT           = os.getenv('MINIO_ENDPOINT')
MINIO_ACCESS_KEY         = os.getenv('MINIO_ACCESS_KEY')
MINIO_SECRET_KEY         = os.getenv('MINIO_SECRET_KEY')
FRAME_BUCKET             = os.getenv('FRAME_BUCKET')
DETECCOES_BUCKET         = os.getenv('DETECCOES_BUCKET')
OUTPUT_FOLDER_DETECTIONS = os.getenv('OUTPUT_FOLDER_DETECTIONS')
MONGO_URI                = os.getenv('MONGO_URI')
MONGO_DB_NAME            = os.getenv('MONGO_DB_NAME')

MIN_DETECTION_CONFIDENCE = 0.5   # confiança mínima MediaPipe
MIN_FACE_WIDTH           = 60    # px
MIN_FACE_HEIGHT          = 60    # px

# ----------------------------------------
# Inicializa MediaPipe FaceDetection
# ----------------------------------------
mp_face_detector = mp.solutions.face_detection.FaceDetection(
    model_selection=1,
    min_detection_confidence=MIN_DETECTION_CONFIDENCE
)

# ----------------------------------------
# Conexões externas
# ----------------------------------------
minio_client = Minio(
    MINIO_ENDPOINT,
    access_key=MINIO_ACCESS_KEY,
    secret_key=MINIO_SECRET_KEY,
    secure=False
)
mongo_client = MongoClient(MONGO_URI)
db           = mongo_client[MONGO_DB_NAME]
frames       = db["frames"]
counters     = db["counters"]

# Garante que o bucket de detecções exista
if not minio_client.bucket_exists(DETECCOES_BUCKET):
    minio_client.make_bucket(DETECCOES_BUCKET)

# ----------------------------------------
# Helpers MongoDB
# ----------------------------------------
def get_next_sequence_value(tag_video: str) -> int:
    counter = counters.find_one_and_update(
        {"_id": tag_video},
        {"$inc": {"sequence_value": 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER
    )
    return counter["sequence_value"]

def salvar_frame_sem_faces(frame_uuid: str, tag_video: str, duracao: float = None, fps: float = None):
    numero_frame = get_next_sequence_value(tag_video)
    novo_frame = {
        "uuid": frame_uuid,
        "total_faces_detectadas": 0,
        "total_faces_reconhecidas": 0,
        "tag_video": tag_video,
        "lista_presencas": [],
        "duracao": duracao,
        "fps": fps,
        "numero_frame": numero_frame
    }
    frames.insert_one(novo_frame)
    print(f"🗃️ Frame sem faces salvo no MongoDB: {novo_frame}")

# ----------------------------------------
# Filtro de tamanhos e landmarks
# ----------------------------------------
def filtros(index: int, facial_area: dict) -> bool:
    w, h = facial_area.get("w", 0), facial_area.get("h", 0)
    if w < MIN_FACE_WIDTH or h < MIN_FACE_HEIGHT:
        print(f"⚠️ Face {index} ignorada por ser muito pequena (w={w}, h={h})")
        return True
    if not (facial_area.get("left_eye") and facial_area.get("right_eye")):
        print(f"⚠️ Face {index} ignorada por falta dos landmarks dos dois olhos.")
        return True
    return False

# ----------------------------------------
# Processa e envia cada face para o MinIO
# ----------------------------------------
def process_face(i: int, detection: dict, img, today: str, save_folder: str, image_name: str):
    facial_area = detection["facial_area"]
    if filtros(i, facial_area):
        return None

    x, y, w, h = facial_area["x"], facial_area["y"], facial_area["w"], facial_area["h"]
    face_img = img[y:y+h, x:x+w]
    if face_img.size == 0:
        print(f"❌ Crop vazio para face {i} em {image_name}")
        return None

    _, encoded = cv2.imencode('.png', face_img)
    face_bytes = encoded.tobytes()
    timestamp  = datetime.now().strftime("%H%M%S%f")
    filename   = f"face_{timestamp}.png"
    object_path = f"{today}/{filename}".replace("\\", "/")

    try:
        minio_client.put_object(
            DETECCOES_BUCKET,
            object_path,
            BytesIO(face_bytes),
            len(face_bytes),
            content_type="image/png"
        )
        print(f"✅ Face salva no MinIO: {object_path}")
        return object_path
    except S3Error as e:
        print(f"❌ Erro ao salvar no MinIO: {e}")
        return None

# ----------------------------------------
# Executa detecção MediaPipe + paraleliza cortes
# ----------------------------------------
def process_image(image_bytes: bytes, image_name: str):
    faces_paths = []
    arr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        print(f"❌ Erro ao carregar a imagem: {image_name}")
        return faces_paths

    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    start = time.time()
    results = mp_face_detector.process(rgb)
    detection_time = time.time() - start
    print(f"⏱ Tempo de detecção: {detection_time*1000:.2f} ms")

    if not results.detections:
        print(f"🚫 Sem faces em {image_name}")
        return faces_paths

    today       = datetime.now().strftime("%d-%m-%Y")
    save_folder = os.path.join(OUTPUT_FOLDER_DETECTIONS, today)
    os.makedirs(save_folder, exist_ok=True)

    h, w = img.shape[:2]
    detections = []
    for det in results.detections:
        rel_bb = det.location_data.relative_bounding_box
        x1 = max(0, int(rel_bb.xmin * w))
        y1 = max(0, int(rel_bb.ymin * h))
        bw = min(int(rel_bb.width * w), w - x1)
        bh = min(int(rel_bb.height * h), h - y1)

        kp = det.location_data.relative_keypoints
        re, le = kp[0], kp[1]
        right_eye = (int(re.x * w), int(re.y * h))
        left_eye  = (int(le.x * w), int(le.y * h))

        facial_area = {
            "x": x1, "y": y1, "w": bw, "h": bh,
            "right_eye": right_eye, "left_eye": left_eye
        }
        detections.append({"facial_area": facial_area})

    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor() as exe:
        futures = [
            exe.submit(process_face, i, det, img, today, save_folder, image_name)
            for i, det in enumerate(detections)
        ]
        for fut in concurrent.futures.as_completed(futures):
            path = fut.result()
            if path:
                faces_paths.append(path)

    return faces_paths

# ----------------------------------------
# Callback RabbitMQ — sempre ack no finally
# ----------------------------------------
def callback(ch, method, properties, body):
    try:
        msg = json.loads(body.decode())
        resp = minio_client.get_object(FRAME_BUCKET, msg["minio_path"])
        img_bytes = resp.read()

        detected = process_image(img_bytes, os.path.basename(msg["minio_path"]))
        if not detected:
            salvar_frame_sem_faces(
                msg["frame_uuid"],
                msg["tag_video"],
                msg.get("duracao"),
                msg.get("fps")
            )
        else:
            tempo_deteccao = datetime.now().timestamp() - float(msg["inicio_processamento"])
            for face_path in detected:
                out_msg = {
                    "data_captura_frame":      msg["data_captura_frame"],
                    "minio_path":              face_path,
                    "inicio_processamento":    msg["inicio_processamento"],
                    "tempo_captura_frame":     msg["tempo_captura_frame"],
                    "tempo_deteccao":          tempo_deteccao,
                    "tag_video":               msg["tag_video"],
                    "timestamp":               msg["timestamp"],
                    "frame_uuid":              msg["frame_uuid"],
                    "frame_total_faces":       len(detected),
                    "fps":                     msg.get("fps"),
                    "duracao":                 msg.get("duracao"),
                    "tempo_espera_captura_deteccao":
                        datetime.now().timestamp() - float(msg.get("fim_captura", msg["inicio_processamento"])),
                    "inicio_deteccao": datetime.now().timestamp(),
                    "fim_deteccao":    datetime.now().timestamp(),
                }
                channel.basic_publish(
                    exchange='',
                    routing_key='deteccoes',
                    body=json.dumps(out_msg),
                    properties=pika.BasicProperties(delivery_mode=2)
                )
                print(f"✅ Enviada detecção: {out_msg}")

    except Exception as e:
        print(f"❌ Erro no callback: {e}")
    finally:
        # ack único e garantido
        ch.basic_ack(delivery_tag=method.delivery_tag)

# ----------------------------------------
# Inicialização do consumer
# ----------------------------------------
def main():
    global channel
    conn = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST))
    channel = conn.channel()
    channel.queue_declare(queue=RABBITMQ_QUEUE, durable=True)
    channel.queue_declare(queue='deteccoes', durable=True)
    channel.basic_consume(queue=RABBITMQ_QUEUE, on_message_callback=callback)
    print("📡 Aguardando mensagens...")
    channel.start_consuming()

if __name__ == "__main__":
    main()
