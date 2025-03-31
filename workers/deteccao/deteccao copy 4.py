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
MIN_FACE_WIDTH = 90
MIN_FACE_HEIGHT = 90

# Conectar ao MinIO
minio_client = Minio(
    MINIO_ENDPOINT,
    access_key=MINIO_ACCESS_KEY,
    secret_key=MINIO_SECRET_KEY,
    secure=False  # Defina como True se estiver usando HTTPS
)

# Conectar ao RabbitMQ
connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST))
channel = connection.channel()
channel.queue_declare(queue=RABBITMQ_QUEUE, durable=True)  # Fila de entrada
channel.queue_declare(queue='deteccoes', durable=True)  # Fila de saída corrigida
"""
def is_frontal_face(detection, angle_threshold=25):
   
    Verifica se a face é frontal com base na inclinação dos olhos.
    
    Calcula o ângulo entre a linha que une os olhos e a horizontal e o normaliza
    para o intervalo [0, 90]. Se o ângulo for menor ou igual ao limiar (em graus),
    a face é considerada frontal.
 
    facial_area = detection.get("facial_area") or detection.get("region")
    if not facial_area:
        return False
    left_eye = facial_area.get("left_eye")
    right_eye = facial_area.get("right_eye")
    if not left_eye or not right_eye:
        return False

    dx = right_eye[0] - left_eye[0]
    dy = right_eye[1] - left_eye[1]
    angle = math.degrees(math.atan2(dy, dx))
    # Normaliza o ângulo para obter o menor ângulo em relação à horizontal
    angle = abs(angle) % 180
    if angle > 90:
        angle = 180 - angle
    print(f"Ângulo entre os olhos (normalizado): {angle:.2f}°")
    return angle <= angle_threshold
   """

def is_frontal_face(detection, angle_threshold=25, symmetry_threshold=0.5):
    """
    Verifica se a face é frontal com base na inclinação dos olhos e na simetria
    dos olhos em relação à caixa facial.
    
    Critérios:
      - O ângulo entre os olhos e a horizontal (roll) deve ser menor ou igual a 'angle_threshold' graus.
      - Os olhos devem estar aproximadamente simétricos dentro da caixa da face. Para isso,
        calculamos a distância proporcional do olho mais à esquerda em relação à borda esquerda
        e do olho mais à direita em relação à borda direita. Se a diferença dessas proporções
        for maior que 'symmetry_threshold', a face é considerada lateralizada.
    
    Parâmetros:
      detection: dicionário com as informações da detecção (deve conter 'facial_area' ou 'region')
      angle_threshold: limiar para o ângulo (em graus)
      symmetry_threshold: limiar para a diferença na simetria dos olhos (valor entre 0 e 1)
      
    Retorna:
      True se a face for considerada frontal; False caso contrário.
    """
    facial_area = detection.get("facial_area") or detection.get("region")
    if not facial_area:
        return False

    left_eye = facial_area.get("left_eye")
    right_eye = facial_area.get("right_eye")
    if not left_eye or not right_eye:
        return False

    # Cálculo do ângulo (roll)
    dx = right_eye[0] - left_eye[0]
    dy = right_eye[1] - left_eye[1]
    angle = math.degrees(math.atan2(dy, dx))
    angle = abs(angle) % 180
    if angle > 90:
        angle = 180 - angle

    if angle > angle_threshold:
        print(f"Ângulo {angle:.2f}° acima do limiar de {angle_threshold}°")
        return False

    # Verificação da simetria dos olhos na caixa facial
    face_x = facial_area.get("x")
    face_w = facial_area.get("w")
    if face_x is None or face_w is None:
        # Se não houver informações da caixa, confia apenas no ângulo
        return True

    # Determina qual dos olhos está à esquerda, baseado na coordenada x
    if left_eye[0] < right_eye[0]:
        eye_left, eye_right = left_eye, right_eye
    else:
        eye_left, eye_right = right_eye, left_eye

    # Calcula a razão da distância do olho esquerdo à borda esquerda e do olho direito à borda direita
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
    Imprime os landmarks da face detectada, se presentes.
    
    Parâmetros:
      - detection: objeto que se espera ser um dicionário contendo a chave "facial_area".
      - index: índice da detecção (para identificação no log).
    """
    if isinstance(detection, dict):
        facial_area = detection.get("facial_area", {})
        print(f"Face {index + 1}:")
        print(f"  Left Eye: {facial_area.get('left_eye', 'N/A')}")
        print(f"  Right Eye: {facial_area.get('right_eye', 'N/A')}")
        print(f"  Nose: {facial_area.get('nose', 'N/A')}")
        print(f"  Mouth Left: {facial_area.get('mouth_left', 'N/A')}")
        print(f"  Mouth Right: {facial_area.get('mouth_right', 'N/A')}")
        print("-" * 40)
    else:
        print(f"Face {index + 1} não possui dados estruturados de landmarks: {detection}")

def filtros(index, detection):
    """
    Verifica se a face deve ser ignorada, 
    seja por ser muito pequena ou por não possuir os landmarks dos dois olhos.
    
    Retorna True se a face deve ser ignorada e False caso contrário.
    """
    # Obter a região facial
    facial_area = detection.get("facial_area") or detection.get("region")
    if facial_area is None:
        print(f"❌ Região da face não encontrada na detecção {index}. Ignorando...")
        return True

    w = facial_area.get("w", 0)
    h = facial_area.get("h", 0)

    # Filtrar por tamanho mínimo
    if w < MIN_FACE_WIDTH or h < MIN_FACE_HEIGHT:
        print(f"⚠️ Face {index} ignorada por ser muito pequena (w={w}, h={h})")
        return True

    # Verificar se os landmarks dos dois olhos estão presentes
    if not (facial_area.get("left_eye") and facial_area.get("right_eye")):
        print(f"⚠️ Face {index} ignorada por falta dos landmarks dos dois olhos.")
        return True
    
    # Verificar se a face é frontal
    if not is_frontal_face(detection):
       print(f"⚠️ Face {index} ignorada por não ser frontal.")
       return True

    return False

def process_image(image_bytes, image_name):
    """
    Realiza a detecção de faces e salva as imagens das faces.
    Retorna uma lista com os caminhos das faces detectadas.
    """
    faces_detectadas = []

    # Ler imagem a partir de bytes
    img_array = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)

    # Verificação se a imagem foi carregada corretamente
    if img is None:
        print(f"❌ Erro ao carregar a imagem: {image_name}")
        return []

    # Detectar faces usando DeepFace com RetinaFace e extrair as faces
    try:
        detections = DeepFace.extract_faces(img_path=img, 
                                            detector_backend='retinaface',
                                            enforce_detection=False,
                                            anti_spoofing = True  )
    except Exception as e:
        print(f"❌ Erro ao detectar faces: {e}")
        return []

    # Verificar se alguma face foi detectada
    if len(detections) == 0:
        print(f"❌ Nenhuma face detectada em {image_name}")
        return []

    # Criar pasta do dia
    today = datetime.now().strftime("%d-%m-%Y")
    save_folder = os.path.join(OUTPUT_FOLDER_DETECTIONS, today)
    os.makedirs(save_folder, exist_ok=True)

    # Processar faces detectadas
    for i, detection in enumerate(detections):
        # Imprimir os landmarks da face
        print_landmarks(detection,i)

        # A extração correta da face e da região está na chave "face" e "facial_area" (ou "region")
        facial_area = detection.get("facial_area") or detection.get("region")
        if facial_area is None:
            print(f"❌ Região da face não encontrada na detecção {i} de {image_name}")
            continue

        x, y, w, h = facial_area["x"], facial_area["y"], facial_area["w"], facial_area["h"]

        # Utilizar a função filtros para ignorar faces indesejadas
        if filtros(i, detection):
            continue

        face_img = img[y:y+h, x:x+w]

        # Verificar se a face foi extraída corretamente
        if face_img is None or face_img.size == 0:
            print(f"❌ Erro ao extrair a face {i} de {image_name}")
            continue

        # Nome do arquivo da face
        timestamp = datetime.now().strftime("%H%M%S%f")
        face_filename = f"face_{timestamp}.png"
        face_path = os.path.join(save_folder, face_filename)

        # Converter a imagem da face para bytes
        _, face_img_bytes = cv2.imencode('.png', face_img)
        face_img_bytes = BytesIO(face_img_bytes)

        # Criar caminho correto para MinIO
        minio_object_path = f"{today}/{face_filename}".replace("\\", "/")

        try:
            # Enviar para o MinIO
            face_img_bytes_value = face_img_bytes.getvalue()
            minio_client.put_object(DETECCOES_BUCKET, minio_object_path, BytesIO(face_img_bytes_value), len(face_img_bytes_value), content_type="image/png")
            print(f"✅ Face salva no MinIO: {minio_object_path}")

            # Adicionar caminho salvo na lista
            faces_detectadas.append(minio_object_path)

        except S3Error as e:
            print(f"❌ Erro ao salvar {face_path} no MinIO: {e}")

    return faces_detectadas

def callback(ch, method, properties, body):
    """
    Função chamada quando uma mensagem é recebida do RabbitMQ.
    """
    try:
        # Decodificar JSON corretamente
        received_message = json.loads(body.decode())
        minio_path = received_message["minio_path"]
        
        date_capture = received_message["data_captura_frame"]
        time_capture = received_message["hora_captura_frame"]

        print(f"📩 Recebida mensagem: {minio_path}")

        # Recuperar a imagem do MinIO
        response = minio_client.get_object(FRAME_BUCKET, minio_path)
        image_bytes = response.read()

        # Processar a imagem para detectar faces
        detected_faces = process_image(image_bytes, os.path.basename(minio_path))

        # Enviar mensagens para a fila de deteccoes com os caminhos das faces
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

# Consumir mensagens do RabbitMQ
channel.basic_consume(queue=RABBITMQ_QUEUE, on_message_callback=callback)

print("📡 Aguardando mensagens. Para sair, pressione CTRL+C")
channel.start_consuming()
