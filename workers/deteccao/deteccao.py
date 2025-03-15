import os
import pika
import dlib
import cv2
import json
from datetime import datetime
from minio import Minio
from minio.error import S3Error
from dotenv import load_dotenv

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

# Detector de faces do dlib
detector = dlib.get_frontal_face_detector()

def process_image(image_path, image_name):
    """
    Realiza a detecção de faces e salva as imagens das faces.
    Retorna uma lista com os caminhos das faces detectadas.
    """
    faces_detectadas = []

    # Ler imagem
    img = cv2.imread(image_path)

    # 🔹 Verificação se a imagem foi carregada corretamente
    if img is None:
        print(f"❌ Erro ao carregar a imagem: {image_path}")
        return []

    # Converter para escala de cinza
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Detectar faces
    faces = detector(gray)

    # 🔹 Verificar se alguma face foi detectada
    if len(faces) == 0:
        print(f"❌ Nenhuma face detectada em {image_path}")
        return []

    # Criar pasta do dia
    today = datetime.now().strftime("%d-%m-%Y")
    save_folder = os.path.join(OUTPUT_FOLDER_DETECTIONS, today)
    os.makedirs(save_folder, exist_ok=True)

    # Processar faces detectadas
    for i, face in enumerate(faces):
        x, y, w, h = face.left(), face.top(), face.width(), face.height()

        # 🔹 Verificação se as coordenadas da face são válidas
        if x < 0 or y < 0 or w <= 0 or h <= 0:
            print(f"❌ Coordenadas inválidas para a face detectada em {image_path}: ({x}, {y}, {w}, {h})")
            continue  # Ignora essa face e passa para a próxima

        # 🔹 Garantir que os índices estão dentro dos limites da imagem
        y1, y2 = max(0, y), min(img.shape[0], y + h)
        x1, x2 = max(0, x), min(img.shape[1], x + w)

        # Recortar a região da face
        face_img = img[y1:y2, x1:x2]

        # 🔹 Verificação se o recorte resultou em uma imagem válida
        if face_img.size == 0:
            print(f"❌ Recorte inválido para face em {image_path}, ignorando...")
            continue

        # Nome do arquivo da face
        timestamp = datetime.now().strftime("%H%M%S%f")
        face_filename = f"face_{timestamp}.png"
        face_path = os.path.join(save_folder, face_filename)

        # Salvar face localmente
        cv2.imwrite(face_path, face_img)

        # Criar caminho correto para MinIO
        minio_object_path = f"{today}/{face_filename}".replace("\\", "/")

        try:
            # Enviar para o MinIO
            minio_client.fput_object(DETECCOES_BUCKET, minio_object_path, face_path)
            print(f"✅ Face salva no MinIO: {minio_object_path}")

            # Remover a face local após upload
            os.remove(face_path)

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
        
        date_capture= received_message["data_captura_frame"]
        time_capture= received_message["hora_captura_frame"]

        print(f"📩 Recebida mensagem: {minio_path}")

        # Recuperar a imagem do MinIO
        data = minio_client.get_object(FRAME_BUCKET, minio_path)
        image_path = os.path.join("temp", os.path.basename(minio_path))

        # Criar diretório temp se não existir
        os.makedirs("temp", exist_ok=True)

        # Salvar a imagem temporariamente
        with open(image_path, 'wb') as file_data:
            for d in data.stream(32 * 1024):
                file_data.write(d)

        # Processar a imagem para detectar faces
        detected_faces = process_image(image_path, os.path.basename(minio_path))

        # Enviar mensagens para a fila de deteccoes com os caminhos das faces
        for face_path in detected_faces:
            message_json = json.dumps({"minio_path": face_path,
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

        # Remover imagem temporária
        os.remove(image_path)

    except json.JSONDecodeError:
        print(f"❌ Erro ao decodificar JSON: {body}")
    
    except S3Error as e:
        print(f"❌ Erro ao recuperar {minio_path} do MinIO: {e}")
    
    ch.basic_ack(delivery_tag=method.delivery_tag)

# Consumir mensagens do RabbitMQ
channel.basic_consume(queue=RABBITMQ_QUEUE, on_message_callback=callback)

print("📡 Aguardando mensagens. Para sair, pressione CTRL+C")
channel.start_consuming()
