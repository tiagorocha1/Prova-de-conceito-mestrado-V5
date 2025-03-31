import os
import math
import pika
import cv2
import json
from datetime import datetime
from minio import Minio
from minio.error import S3Error
from dotenv import load_dotenv
import numpy as np
from io import BytesIO
from deepface import DeepFace
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Carregar variáveis de ambiente
load_dotenv()

# Configurações
RABBITMQ_HOST = os.getenv('RABBITMQ_HOST')
RABBITMQ_QUEUE = os.getenv('RABBITMQ_QUEUE')
MINIO_ENDPOINT = os.getenv('MINIO_ENDPOINT')
MINIO_ACCESS_KEY = os.getenv('MINIO_ACCESS_KEY')
MINIO_SECRET_KEY = os.getenv('MINIO_SECRET_KEY')
FRAME_BUCKET = os.getenv('FRAME_BUCKET')         # Bucket de origem das imagens
DETECCOES_BUCKET = os.getenv('DETECCOES_BUCKET')   # Bucket onde as faces serão armazenadas
OUTPUT_FOLDER_DETECTIONS = os.getenv('OUTPUT_FOLDER_DETECTIONS')
MIN_FACE_WIDTH = 90
MIN_FACE_HEIGHT = 90

# Cache para a pasta de salvamento (evita recriação desnecessária)
CURRENT_DATE = None
SAVE_FOLDER = None

def get_save_folder():
    global CURRENT_DATE, SAVE_FOLDER
    today = datetime.now().strftime("%d-%m-%Y")
    if today != CURRENT_DATE:
        CURRENT_DATE = today
        SAVE_FOLDER = os.path.join(OUTPUT_FOLDER_DETECTIONS, today)
        os.makedirs(SAVE_FOLDER, exist_ok=True)
    return SAVE_FOLDER

# Conectar ao MinIO
minio_client = Minio(
    MINIO_ENDPOINT,
    access_key=MINIO_ACCESS_KEY,
    secret_key=MINIO_SECRET_KEY,
    secure=False  # Altere para True se usar HTTPS
)

# Conectar ao RabbitMQ
connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST))
channel = connection.channel()
channel.queue_declare(queue=RABBITMQ_QUEUE, durable=True)  # Fila de entrada
channel.queue_declare(queue='deteccoes', durable=True)       # Fila de saída
channel.basic_qos(prefetch_count=1)  # Limita o número de mensagens não reconhecidas

def is_frontal_face(detection, angle_threshold=25, symmetry_threshold=0.5):
    """
    Verifica se a face é frontal, considerando o ângulo entre os olhos e a simetria em relação à caixa facial.
    """
    facial_area = detection.get("facial_area") or detection.get("region")
    if not facial_area:
        return False

    left_eye = facial_area.get("left_eye")
    right_eye = facial_area.get("right_eye")
    if not left_eye or not right_eye:
        return False

    dx = right_eye[0] - left_eye[0]
    dy = right_eye[1] - left_eye[1]
    angle = abs(math.degrees(math.atan2(dy, dx))) % 180
    if angle > 90:
        angle = 180 - angle
    if angle > angle_threshold:
        logger.debug(f"Ângulo {angle:.2f}° acima do limiar de {angle_threshold}°")
        return False

    face_x = facial_area.get("x")
    face_w = facial_area.get("w")
    if face_x is None or face_w is None:
        return True

    # Determinar qual olho está à esquerda
    if left_eye[0] < right_eye[0]:
        eye_left, eye_right = left_eye, right_eye
    else:
        eye_left, eye_right = right_eye, left_eye

    left_ratio = (eye_left[0] - face_x) / face_w
    right_ratio = ((face_x + face_w) - eye_right[0]) / face_w

    symmetry_diff = abs(left_ratio - right_ratio)
    logger.debug(f"Left ratio: {left_ratio:.2f}, Right ratio: {right_ratio:.2f}, Diferença: {symmetry_diff:.2f}")

    if symmetry_diff > symmetry_threshold:
        logger.debug(f"Simetria fora do limiar de {symmetry_threshold}")
        return False

    return True

def print_landmarks(detection, index):
    """
    Imprime os landmarks (pontos de referência) da face detectada (usando logging.debug).
    """
    if isinstance(detection, dict):
        facial_area = detection.get("facial_area", {})
        logger.debug(f"Face {index + 1}:")
        logger.debug(f"  Left Eye: {facial_area.get('left_eye', 'N/A')}")
        logger.debug(f"  Right Eye: {facial_area.get('right_eye', 'N/A')}")
        logger.debug(f"  Nose: {facial_area.get('nose', 'N/A')}")
        logger.debug(f"  Mouth Left: {facial_area.get('mouth_left', 'N/A')}")
        logger.debug(f"  Mouth Right: {facial_area.get('mouth_right', 'N/A')}")
        logger.debug("-" * 40)
    else:
        logger.debug(f"Face {index + 1} sem dados estruturados de landmarks.")

def filtros(index, detection):
    """
    Verifica se a face deve ser ignorada:
      - Se a região facial não estiver presente
      - Se a face for muito pequena
      - Se faltar os landmarks dos dois olhos
      - Se a face não for frontal
    Retorna True se a face deve ser ignorada.
    """
    facial_area = detection.get("facial_area") or detection.get("region")
    if facial_area is None:
        logger.info(f"Região da face não encontrada na detecção {index}. Ignorando...")
        return True

    w = facial_area.get("w", 0)
    h = facial_area.get("h", 0)

    if w < MIN_FACE_WIDTH or h < MIN_FACE_HEIGHT:
        logger.info(f"Face {index} ignorada por ser muito pequena (w={w}, h={h})")
        return True

    if not (facial_area.get("left_eye") and facial_area.get("right_eye")):
        logger.info(f"Face {index} ignorada por falta dos landmarks dos dois olhos.")
        return True
    
    if not is_frontal_face(detection):
       logger.info(f"Face {index} ignorada por não ser frontal.")
       return True

    return False

def process_image(image_bytes, image_name):
    """
    Realiza a detecção de faces e salva as imagens das faces detectadas no MinIO.
    Retorna uma lista com os caminhos (paths) das faces salvas.
    """
    faces_detectadas = []

    # Converter bytes para imagem
    img_array = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
    if img is None:
        logger.error(f"Erro ao carregar a imagem: {image_name}")
        return []

    # Detecção de faces (o DeepFace já pode cachear modelos após a primeira chamada)
    try:
        detections = DeepFace.extract_faces(
            img_path=img, 
            detector_backend='retinaface',
            enforce_detection=False,
            anti_spoofing=True
        )
    except Exception as e:
        logger.error(f"Erro ao detectar faces: {e}")
        return []

    if not detections:
        logger.error(f"Nenhuma face detectada em {image_name}")
        return []

    save_folder = get_save_folder()

    for i, detection in enumerate(detections):
        print_landmarks(detection, i)
        facial_area = detection.get("facial_area") or detection.get("region")
        if facial_area is None:
            logger.error(f"Região da face não encontrada na detecção {i} de {image_name}")
            continue

        x, y, w, h = facial_area["x"], facial_area["y"], facial_area["w"], facial_area["h"]

        if filtros(i, detection):
            continue

        face_img = img[y:y+h, x:x+w]
        if face_img is None or face_img.size == 0:
            logger.error(f"Erro ao extrair a face {i} de {image_name}")
            continue

        timestamp = datetime.now().strftime("%H%M%S%f")
        face_filename = f"face_{timestamp}.png"
        face_path = os.path.join(save_folder, face_filename)

        # Codificar imagem para PNG
        success, face_img_bytes = cv2.imencode('.png', face_img)
        if not success:
            logger.error(f"Erro ao codificar a face {i} de {image_name}")
            continue
        face_img_bytes = BytesIO(face_img_bytes.tobytes())

        # Definir o caminho do objeto no MinIO
        minio_object_path = f"{CURRENT_DATE}/{face_filename}".replace("\\", "/")

        try:
            face_img_bytes_value = face_img_bytes.getvalue()
            minio_client.put_object(
                DETECCOES_BUCKET,
                minio_object_path,
                BytesIO(face_img_bytes_value),
                len(face_img_bytes_value),
                content_type="image/png"
            )
            logger.info(f"Face salva no MinIO: {minio_object_path}")
            faces_detectadas.append(minio_object_path)
        except S3Error as e:
            logger.error(f"Erro ao salvar {face_path} no MinIO: {e}")

    return faces_detectadas

def callback(ch, method, properties, body):
    """
    Função chamada ao receber mensagem do RabbitMQ. Processa a imagem e publica os resultados.
    """
    try:
        received_message = json.loads(body.decode())
        minio_path = received_message["minio_path"]
        date_capture = received_message["data_captura_frame"]
        time_capture = received_message["hora_captura_frame"]

        logger.info(f"Recebida mensagem: {minio_path}")

        response = minio_client.get_object(FRAME_BUCKET, minio_path)
        image_bytes = response.read()

        detected_faces = process_image(image_bytes, os.path.basename(minio_path))

        for face_path in detected_faces:
            message_json = json.dumps({
                "minio_path": face_path,
                "data_captura_frame": date_capture,
                "hora_captura_frame": time_capture
            })
            channel.basic_publish(
                exchange='',
                routing_key='deteccoes',
                body=message_json,
                properties=pika.BasicProperties(delivery_mode=2)
            )
            logger.info(f"Enviada mensagem para 'deteccoes': {message_json}")

    except json.JSONDecodeError:
        logger.error(f"Erro ao decodificar JSON: {body}")
    except S3Error as e:
        logger.error(f"Erro ao recuperar {minio_path} do MinIO: {e}")

    ch.basic_ack(delivery_tag=method.delivery_tag)

# Iniciar consumo das mensagens
channel.basic_consume(queue=RABBITMQ_QUEUE, on_message_callback=callback)
logger.info("Aguardando mensagens. Para sair, pressione CTRL+C")
channel.start_consuming()
