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
import concurrent.futures
from pymongo import MongoClient, ReturnDocument

# Carregar variáveis de ambiente
load_dotenv()

# Configurações
RABBITMQ_HOST = os.getenv('RABBITMQ_HOST')
RABBITMQ_QUEUE = os.getenv('RABBITMQ_QUEUE')
MINIO_ENDPOINT = os.getenv('MINIO_ENDPOINT')
MINIO_ACCESS_KEY = os.getenv('MINIO_ACCESS_KEY')
MINIO_SECRET_KEY = os.getenv('MINIO_SECRET_KEY')
FRAME_BUCKET = os.getenv('FRAME_BUCKET')  # Bucket de origem das imagens
DETECCOES_BUCKET = os.getenv('DETECCOES_BUCKET')  # Bucket onde as faces serão armazenadas
OUTPUT_FOLDER_DETECTIONS = os.getenv('OUTPUT_FOLDER_DETECTIONS')
MIN_FACE_WIDTH = 130
MIN_FACE_HEIGHT = 130
MONGO_URI = os.getenv('MONGO_URI')
MONGO_DB_NAME = os.getenv('MONGO_DB_NAME')

# Conectar ao MinIO
minio_client = Minio(
    MINIO_ENDPOINT,
    access_key=MINIO_ACCESS_KEY,
    secret_key=MINIO_SECRET_KEY,
    secure=False  # Defina como True se estiver usando HTTPS
)

# Conexão com MongoDB
client = MongoClient(MONGO_URI)
db = client[MONGO_DB_NAME]
frames = db["frames"]
counters = db["counters"]
# Criar bucket se não existir
if not minio_client.bucket_exists(DETECCOES_BUCKET):
    minio_client.make_bucket(DETECCOES_BUCKET)

# 🔢 Função para obter número sequencial por tag_video
def get_next_sequence_value(tag_video: str) -> int:
    counter = counters.find_one_and_update(
        {"_id": tag_video},
        {"$inc": {"sequence_value": 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER
    )
    return counter["sequence_value"]

def salvar_frame_sem_faces(frame_uuid: str, tag_video: str, duracao: str = None, fps: str = None):
    """
    Salva no MongoDB um documento representando um frame sem faces detectadas.
    """
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


def is_frontal_face(facial_area, angle_threshold=25, symmetry_threshold=0.5):
    """
    Verifica se a face é frontal com base na inclinação e simetria dos olhos.

    Parâmetros:
      facial_area: dicionário com informações da face (deve conter 'left_eye', 'right_eye', 'x' e 'w')
      angle_threshold: limiar para o ângulo (em graus)
      symmetry_threshold: limiar para a diferença de simetria dos olhos

    Retorna:
      True se a face for frontal; False caso contrário.
    """
    left_eye = facial_area.get("left_eye")
    right_eye = facial_area.get("right_eye")
    if not left_eye or not right_eye:
        return False

    # Cálculo do ângulo (roll)
    dx = right_eye[0] - left_eye[0]
    dy = right_eye[1] - left_eye[1]
    angle = abs(math.degrees(math.atan2(dy, dx))) % 180
    if angle > 90:
        angle = 180 - angle

    if angle > angle_threshold:
        print(f"Ângulo {angle:.2f}° acima do limiar de {angle_threshold}°")
        return False

    # Verificação de simetria (caso a caixa facial esteja disponível)
    face_x = facial_area.get("x")
    face_w = facial_area.get("w")
    if face_x is not None and face_w is not None:
        # Determina qual olho é o esquerdo
        if left_eye[0] < right_eye[0]:
            eye_left, eye_right = left_eye, right_eye
        else:
            eye_left, eye_right = right_eye, left_eye

        left_ratio = (eye_left[0] - face_x) / face_w
        right_ratio = ((face_x + face_w) - eye_right[0]) / face_w
        symmetry_diff = abs(left_ratio - right_ratio)
        print(f"Left ratio: {left_ratio:.2f}, Right ratio: {right_ratio:.2f}, Diferença: {symmetry_diff:.2f}")

        if symmetry_diff > symmetry_threshold:
            print(f"Simetria fora do limiar de {symmetry_threshold}")
            return False

    return True

def print_landmarks(detection, index):
    """
    Imprime os landmarks da face detectada.
    """
    if isinstance(detection, dict):
        facial_area = detection.get("facial_area") or detection.get("region", {})
        print(f"Face {index + 1}:")
        print(f"  Left Eye: {facial_area.get('left_eye', 'N/A')}")
        print(f"  Right Eye: {facial_area.get('right_eye', 'N/A')}")
        print(f"  Nose: {facial_area.get('nose', 'N/A')}")
        print(f"  Mouth Left: {facial_area.get('mouth_left', 'N/A')}")
        print(f"  Mouth Right: {facial_area.get('mouth_right', 'N/A')}")
        print("-" * 40)
    else:
        print(f"Face {index + 1} não possui dados estruturados de landmarks: {detection}")

def filtros(index, facial_area):
    """
    Verifica se a face deve ser ignorada, seja por tamanho ou pela ausência dos landmarks essenciais.
    
    Retorna True se a face deve ser ignorada e False caso contrário.
    """
    w = facial_area.get("w", 0)
    h = facial_area.get("h", 0)

    if w < MIN_FACE_WIDTH or h < MIN_FACE_HEIGHT:
        print(f"⚠️ Face {index} ignorada por ser muito pequena (w={w}, h={h})")
        return True


    if not (facial_area.get("left_eye") and facial_area.get("right_eye")):
        print(f"⚠️ Face {index} ignorada por falta dos landmarks dos dois olhos.")
        return True
    
    #if not is_frontal_face(facial_area):
    #   print(f"⚠️ Face {index} ignorada por não ser frontal.")
    #   return True

    return False


def process_face(i, detection, img, today, save_folder, image_name):
    """
    Processa uma única face: filtra, extrai a face, codifica a imagem e envia para o MinIO.
    Retorna o caminho salvo no MinIO ou None, caso ocorra algum erro.
    """
    # Imprime os landmarks da face
    #print_landmarks(detection, i)

    facial_area = detection.get("facial_area") or detection.get("region")
    if not facial_area:
        print(f"❌ Região da face não encontrada na detecção {i} de {image_name}")
        return None

    if filtros(i, facial_area):
        return None

    x, y, w, h = facial_area["x"], facial_area["y"], facial_area["w"], facial_area["h"]
    face_img = img[y:y+h, x:x+w]
    if face_img is None or face_img.size == 0:
        print(f"❌ Erro ao extrair a face {i} de {image_name}")
        return None

    timestamp = datetime.now().strftime("%H%M%S%f")
    face_filename = f"face_{timestamp}.png"
    face_path = os.path.join(save_folder, face_filename)

    success, encoded_img = cv2.imencode('.png', face_img)
    if not success:
        print(f"❌ Erro ao codificar a face {i} de {image_name}")
        return None

    face_bytes = encoded_img.tobytes()
    minio_object_path = f"{today}/{face_filename}".replace("\\", "/")

    try:
        minio_client.put_object(
            DETECCOES_BUCKET, 
            minio_object_path, 
            BytesIO(face_bytes), 
            len(face_bytes), 
            content_type="image/png"
        )
        print(f"✅ Face salva no MinIO: {minio_object_path}")
        return minio_object_path
    except S3Error as e:
        print(f"❌ Erro ao salvar {face_path} no MinIO: {e}")
        return None

def process_image(image_bytes, image_name):
    """
    Realiza a detecção de faces, processa cada face em paralelo e salva as imagens no MinIO.
    Retorna uma lista com os caminhos das faces detectadas.
    """
    faces_detectadas = []
    
    # Carregar imagem a partir dos bytes
    img_array = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
    if img is None:
        print(f"❌ Erro ao carregar a imagem: {image_name}")
        return faces_detectadas

    try:
        start_time = datetime.now().timestamp()
        detections = DeepFace.extract_faces(
            img_path=img, 
            detector_backend='centerface', # 'opencv', 'retinaface', 'mtcnn', 'ssd', 'dlib', 'mediapipe', 'yolov8', 'yolov11n', 'yolov11s', 'yolov11m','centerface' or 'skip' (default is opencv)
            enforce_detection=False,
            anti_spoofing=True
        )
        #print(detections)
        elapsed_time = datetime.now().timestamp() - start_time
        print(f"⏱ Tempo de detecção de faces: {elapsed_time * 1000:.2f} ms")
    except Exception as e:
        print(f"❌ Erro ao detectar faces: {e}")
        return faces_detectadas

    if not detections:
        print(f"❌ Nenhuma face detectada em {image_name}")
        return faces_detectadas

    # Cria a pasta com a data atual para organização
    today = datetime.now().strftime("%d-%m-%Y")
    save_folder = os.path.join(OUTPUT_FOLDER_DETECTIONS, today)
    os.makedirs(save_folder, exist_ok=True)

    # Processa cada face em paralelo
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = [
            executor.submit(process_face, i, detection, img, today, save_folder, image_name)
            for i, detection in enumerate(detections)
        ]
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            if result:
                faces_detectadas.append(result)

    return faces_detectadas


def callback(ch, method, properties, body):
    """
    Processa a mensagem recebida do RabbitMQ.
    """
    start_time = datetime.now().timestamp()
    try:

        received_message = json.loads(body.decode())
        minio_path = received_message["minio_path"]
        inicio_processamento = received_message["inicio_processamento"]
        tempo_captura_frame = received_message["tempo_captura_frame"]
        data_captura_frame = received_message["data_captura_frame"]
        tag_video = received_message["tag_video"]
        timestamp = received_message["timestamp"]
        frame_uuid = received_message["frame_uuid"]
        fps = received_message["fps"]
        duracao = received_message["duracao"]
        fim_captura = received_message.get("fim_captura")
        inicio_deteccao = datetime.now().timestamp()
        tempo_espera_captura_deteccao = inicio_deteccao - float(fim_captura or inicio_deteccao)



        print(f"📩 Recebida mensagem: {minio_path}")

        response = minio_client.get_object(FRAME_BUCKET, minio_path)
        image_bytes = response.read()

        detected_faces = process_image(image_bytes, os.path.basename(minio_path))

        if not detected_faces:
            salvar_frame_sem_faces(frame_uuid, tag_video, duracao, fps)
            ch.basic_ack(delivery_tag=method.delivery_tag)
            return

        tempo_deteccao = datetime.now().timestamp() - start_time
        for face_path in detected_faces:
            message_json = json.dumps({
                "data_captura_frame": data_captura_frame,
                "minio_path": face_path,
                "inicio_processamento": inicio_processamento,
                "tempo_captura_frame": tempo_captura_frame,
                "tempo_deteccao": tempo_deteccao,
                "tag_video": tag_video,
                "timestamp": timestamp,
                "frame_uuid": frame_uuid,
                "frame_total_faces": len(detected_faces),
                "fps": fps,
                "duracao": duracao,
                "tempo_espera_captura_deteccao": tempo_espera_captura_deteccao,
                "inicio_deteccao": inicio_deteccao,
                "fim_deteccao": datetime.now().timestamp(),

            })
            channel.basic_publish(
                exchange='',
                routing_key='deteccoes',
                body=message_json,
                properties=pika.BasicProperties(
                    delivery_mode=2  # Garante persistência da mensagem
                )
            )
            print(f"✅ Enviada mensagem para 'deteccoes': {message_json}")

    except json.JSONDecodeError:
        print(f"❌ Erro ao decodificar JSON: {body}")
    except S3Error as e:
        print(f"❌ Erro ao recuperar {minio_path} do MinIO: {e}")

    
  
    
    ch.basic_ack(delivery_tag=method.delivery_tag)

def main():
    """
    Função principal: configura o RabbitMQ e inicia o consumo de mensagens.
    """
    global channel  # Necessário para uso no callback
    connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST))
    channel = connection.channel()
    channel.queue_declare(queue=RABBITMQ_QUEUE, durable=True)
    channel.queue_declare(queue='deteccoes', durable=True)

    channel.basic_consume(queue=RABBITMQ_QUEUE, on_message_callback=callback)
    print("📡 Aguardando mensagens. Para sair, pressione CTRL+C")
    channel.start_consuming()

if __name__ == '__main__':
    main()