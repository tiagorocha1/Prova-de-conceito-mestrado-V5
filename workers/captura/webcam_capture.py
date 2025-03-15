import cv2
import asyncio
import io
from datetime import datetime
from minio_utils import save_image_to_minio
from rabbitmq_manager import rabbitmq_manager
import os

# Configuração do intervalo de captura (em segundos)
CAPTURE_INTERVAL = int(os.getenv("CAPTURE_INTERVAL", 1))  # Padrão: 1 segundo

class WebcamCapture:
    """Captura frames da webcam e envia para MinIO + RabbitMQ somente se houver ao menos uma face detectada."""
    
    def __init__(self, camera_index=0):
        self.camera_index = camera_index
        self.running = False
        # Inicializa o classificador Haar Cascade para detecção de faces
        self.face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    
    async def capture_and_upload(self):
        """Captura frames, detecta faces e, se houver, realiza o upload e envia mensagem."""
        cap = cv2.VideoCapture(self.camera_index)

        if not cap.isOpened():
            print(f"❌ Erro: A câmera {self.camera_index} não pôde ser aberta.")
            return

        try:
            while self.running:
                ret, frame = cap.read()
                if not ret:
                    print("❌ Erro ao capturar frame.")
                    continue

                # Converte para escala de cinza para melhorar a detecção
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                faces = self.face_cascade.detectMultiScale(
                    gray,
                    scaleFactor=1.1,
                    minNeighbors=5,
                    minSize=(30, 30)
                )

                if len(faces) > 0:
                    # Se pelo menos uma face for detectada, procede com o upload
                    current_date = datetime.now().strftime("%d-%m-%Y")
                    timestamp = str(int(datetime.now().timestamp() * 1000))
                    
                    object_name = f"{current_date}/{timestamp}.png"
                    minio_path = object_name

                    # Converte o frame para buffer PNG
                    ret_enc, buffer = cv2.imencode(".png", frame)
                    if not ret_enc:
                        print("❌ Erro ao codificar o frame.")
                        continue

                    image_buffer = io.BytesIO(buffer.tobytes())

                    try:
                        # Usa run_in_executor para rodar a função de upload sem bloquear o loop asyncio
                        loop = asyncio.get_running_loop()
                        await loop.run_in_executor(None, save_image_to_minio, image_buffer, object_name)
                        await rabbitmq_manager.send_message(minio_path)
                        print(f"✅ Imagem salva e mensagem enviada: {minio_path}")
                    except Exception as e:
                        print(f"❌ Erro no upload: {e}")
                else:
                    print("Nenhuma face detectada.")

                # Aguarda o intervalo configurado antes de capturar o próximo frame
                await asyncio.sleep(CAPTURE_INTERVAL)

        except KeyboardInterrupt:
            print("⏹️ Interrompido pelo usuário.")

        finally:
            cap.release()
            cv2.destroyAllWindows()
