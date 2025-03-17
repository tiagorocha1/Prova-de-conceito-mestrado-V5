import tkinter as tk
from tkinter import ttk, messagebox
import cv2
import asyncio
from threading import Thread
from datetime import datetime
import io
import os
from PIL import Image, ImageTk
from minio import Minio
from dotenv import load_dotenv
import json
import aio_pika
from datetime import datetime


# ----------------------------
# Carregar Variáveis de Ambiente
# ----------------------------
load_dotenv()

# Intervalo de captura (em segundos)
CAPTURE_INTERVAL = int(os.getenv("CAPTURE_INTERVAL", 1))

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


class WebcamApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Captura de Webcam")
        self.root.geometry("800x600")

        # Lista de webcams disponíveis
        self.cameras = self.get_available_cameras()

        # Dropdown para seleção da webcam
        self.camera_label = tk.Label(root, text="Selecione a Webcam:")
        self.camera_label.pack(pady=10)

        self.camera_var = tk.StringVar()
        self.camera_dropdown = ttk.Combobox(root, textvariable=self.camera_var, values=self.cameras)
        self.camera_dropdown.pack()
        if self.cameras:
            self.camera_dropdown.current(0)

        # Botões para iniciar e parar a captura
        self.start_button = tk.Button(root, text="Iniciar Captura", command=self.start_capture, bg="green", fg="white")
        self.start_button.pack(pady=20)

        self.stop_button = tk.Button(root, text="Parar Captura", command=self.stop_capture, bg="red", fg="white")
        self.stop_button.pack()
        self.stop_button.config(state=tk.DISABLED)

        # Label para exibir o preview da webcam
        self.preview_label = tk.Label(root)
        self.preview_label.pack(pady=10)

        self.cap = None  # Instância do VideoCapture
        self.running = False

        # Cria um loop asyncio para tarefas assíncronas
        self.loop = asyncio.new_event_loop()
        self.thread = Thread(target=self.run_asyncio_loop, daemon=True)
        self.thread.start()

    def get_available_cameras(self):
        """Descobre quais webcams estão disponíveis no sistema."""
        available_cameras = []
        for i in range(5):
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                available_cameras.append(f"Camera {i}")
                cap.release()
        return available_cameras if available_cameras else []

    def start_capture(self):
        """Inicia a captura e exibição do vídeo da webcam."""
        if not self.cameras:
            messagebox.showerror("Erro", "Nenhuma câmera encontrada!")
            return

        camera_index = int(self.camera_var.get().split()[-1])
        self.cap = cv2.VideoCapture(camera_index)
        if not self.cap.isOpened():
            messagebox.showerror("Erro", f"A câmera {camera_index} não pôde ser aberta.")
            return

        self.running = True
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        # Inicia o loop de atualização do preview
        self.update_frame()

    def stop_capture(self):
        """Para a captura e limpa o preview."""
        self.running = False
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        if self.cap:
            self.cap.release()
            self.cap = None
        self.preview_label.config(image='')

    def update_frame(self):
        """Atualiza o preview da webcam e agenda o envio do frame."""
        if self.running and self.cap:
            ret, frame = self.cap.read()
            if ret:
                # Converte o frame de BGR para RGB e exibe no widget
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                im = Image.fromarray(frame_rgb)
                imgtk = ImageTk.PhotoImage(image=im)
                self.preview_label.imgtk = imgtk  # Mantém referência para evitar garbage collection
                self.preview_label.config(image=imgtk)

                # Processa o frame de forma assíncrona (salva no MinIO e envia mensagem)
                asyncio.run_coroutine_threadsafe(self.upload_frame(frame), self.loop)
            # Agenda a próxima atualização após o intervalo definido
            self.root.after(CAPTURE_INTERVAL * 1000, self.update_frame)

    async def upload_frame(self, frame):
        current_date = datetime.now().strftime("%d-%m-%Y")
        timestamp = str(int(datetime.now().timestamp() * 1000))
        object_name = f"{current_date}/{timestamp}.png"
        minio_path = object_name

        # Codifica o frame em PNG
        ret, buffer = cv2.imencode(".png", frame)
        if not ret:
            print("❌ Erro ao codificar frame.")
            return
        image_buffer = io.BytesIO(buffer.tobytes())

        try:
            # Utiliza run_in_executor para executar a função em uma thread separada
            await self.loop.run_in_executor(None, save_image_to_minio, image_buffer, object_name)
            await rabbitmq_manager.send_message(minio_path)
            print(f"✅ Imagem salva e mensagem enviada: {minio_path}")
        except Exception as e:
            print(f"❌ Erro no upload: {e}")


    def run_asyncio_loop(self):
        """Executa o loop asyncio em uma thread separada."""
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

class RabbitMQManager:
    """ Gerencia a conexão com RabbitMQ, garantindo que não seja fechada prematuramente. """

    def __init__(self):
        self.connection = None
        self.channel = None
        self.loop = asyncio.get_event_loop()

    async def connect(self):
        """ Mantém uma conexão aberta e persistente com o RabbitMQ """
        if self.connection is None or self.connection.is_closed:
            self.connection = await aio_pika.connect_robust("amqp://guest:guest@localhost:5672/")
            self.channel = await self.connection.channel()
            await self.channel.declare_exchange("direct_exchange", aio_pika.ExchangeType.DIRECT, durable=True)
            await self.channel.declare_queue("frame", durable=True)
            print("✅ Conectado ao RabbitMQ e canal configurado!")

    async def send_message(self, minio_path: str):
        """ Envia a mensagem garantindo que a conexão esteja ativa """
        await self.connect()

        try:
            timestamp = datetime.now()
            message_body = json.dumps({"minio_path": minio_path,
                                       "data_captura_frame": timestamp.strftime("%Y-%m-%d"),
                                       "hora_captura_frame": timestamp.strftime("%H:%M:%S.%f")})
            message = aio_pika.Message(
                body=message_body.encode("utf-8"),
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT
            )

            await self.channel.default_exchange.publish(message, routing_key="frame")
            print(f"✅ Mensagem enviada com sucesso: {message_body}")

        except Exception as e:
            print(f"❌ Erro ao enviar mensagem: {e}")

rabbitmq_manager = RabbitMQManager()

if __name__ == "__main__":
    root = tk.Tk()
    app = WebcamApp(root)
    root.mainloop()


