import tkinter as tk
from tkinter import ttk, messagebox, filedialog
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

# ----------------------------
# Carregar Variáveis de Ambiente
# ----------------------------
load_dotenv()

# Configuração do MinIO
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY")
BUCKET_NAME = os.getenv("MINIO_BUCKET")

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

# ----------------------------
# Configurações de Captura
# ----------------------------
WEBCAM_FPS = 20  # Taxa de frames por segundo para a webcam
VIDEO_FPS = 20   # Taxa de frames por segundo para arquivos de vídeo
CAPTURE_INTERVAL = 3  # Intervalo de captura em segundos

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

        # Dropdown para seleção da fonte (webcam ou arquivo de vídeo)
        self.source_label = tk.Label(root, text="Selecione a Fonte:")
        self.source_label.pack(pady=10)

        self.source_var = tk.StringVar()
        self.source_dropdown = ttk.Combobox(root, textvariable=self.source_var, values=["Webcam", "Arquivo de Vídeo"])
        self.source_dropdown.pack()
        self.source_dropdown.current(0)

        # Dropdown para seleção da webcam
        self.camera_label = tk.Label(root, text="Selecione a Webcam:")
        self.camera_label.pack(pady=10)

        self.camera_var = tk.StringVar()
        self.camera_dropdown = ttk.Combobox(root, textvariable=self.camera_var, values=self.cameras)
        self.camera_dropdown.pack()
        if self.cameras:
            self.camera_dropdown.current(0)

        # Botão para selecionar arquivo de vídeo
        self.video_button = tk.Button(root, text="Selecionar Arquivo de Vídeo", command=self.select_video_file)
        self.video_button.pack(pady=10)

        # NOVO: Campo de entrada para Tag Video
        self.video_tag_label = tk.Label(root, text="Tag Video:")
        self.video_tag_label.pack(pady=10)
        self.video_tag_entry = tk.Entry(root)
        self.video_tag_entry.pack()

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
        self.video_file = None

        # Cria um loop asyncio para tarefas assíncronas
        self.loop = asyncio.new_event_loop()
        self.thread = Thread(target=self.run_asyncio_loop, daemon=True)
        self.thread.start()

        self.last_capture_time = datetime.now()

    def get_available_cameras(self):
        """Descobre quais webcams estão disponíveis no sistema."""
        available_cameras = []
        for i in range(5):
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                available_cameras.append(f"Camera {i}")
                cap.release()
        return available_cameras if available_cameras else []

    def select_video_file(self):
        """Abre um diálogo para selecionar um arquivo de vídeo."""
        self.video_file = filedialog.askopenfilename(filetypes=[("Arquivos de Vídeo", "*.mp4;*.avi;*.mov")])
        if self.video_file:
            self.source_var.set("Arquivo de Vídeo")

    def start_capture(self):
        """Inicia a captura e exibição do vídeo da webcam ou arquivo de vídeo."""
        source = self.source_var.get()
        if source == "Webcam":
            if not self.cameras:
                messagebox.showerror("Erro", "Nenhuma câmera encontrada!")
                return

            camera_index = int(self.camera_var.get().split()[-1])
            self.cap = cv2.VideoCapture(camera_index)
            if not self.cap.isOpened():
                messagebox.showerror("Erro", f"A câmera {camera_index} não pôde ser aberta.")
                return

            # Definir a taxa de quadros para a webcam
            self.fps = WEBCAM_FPS
            self.frame_interval = int(1000 / self.fps)

        elif source == "Arquivo de Vídeo":
            if not self.video_file:
                messagebox.showerror("Erro", "Nenhum arquivo de vídeo selecionado!")
                return

            self.cap = cv2.VideoCapture(self.video_file)
            if not self.cap.isOpened():
                messagebox.showerror("Erro", f"O arquivo de vídeo {self.video_file} não pôde ser aberto.")
                return

            # Obter a taxa de quadros do vídeo
            self.fps = self.cap.get(cv2.CAP_PROP_FPS) or VIDEO_FPS
            self.frame_interval = int(1000 / self.fps)

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
        """Atualiza o preview da webcam ou arquivo de vídeo e agenda o envio do frame."""
        if self.running and self.cap:
            ret, frame = self.cap.read()
            if not ret:
                self.stop_capture()  # Para a captura se o vídeo chegou ao fim
                return

            # Converte o frame de BGR para RGB e exibe no widget
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            im = Image.fromarray(frame_rgb)
            imgtk = ImageTk.PhotoImage(image=im)
            self.preview_label.imgtk = imgtk  # Mantém referência para evitar garbage collection
            #self.preview_label.config(image=imgtk)

            # Verifica se o intervalo de captura foi atingido
            current_time = datetime.now()
            if (current_time - self.last_capture_time).total_seconds() >= CAPTURE_INTERVAL:
                self.last_capture_time = current_time
                # Processa o frame de forma assíncrona (salva no MinIO e envia mensagem)
                asyncio.run_coroutine_threadsafe(self.upload_frame(frame), self.loop)

            # Agenda a próxima atualização com base na taxa de quadros do vídeo
            self.root.after(100, self.update_frame)

    async def upload_frame(self, frame):
        # Marca o início do processamento
        inicio_processamento = datetime.now().timestamp()

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
            # Marca o fim do processamento e calcula o tempo total (em milissegundos)
            fim_processamento = datetime.now().timestamp()
            tempo_captura_frame = fim_processamento - inicio_processamento
            # Obtém o valor da tag de vídeo informado na interface
            tag_video = self.video_tag_entry.get()
            # Envia a mensagem para o RabbitMQ com o valor da tag video incluso
            await rabbitmq_manager.send_message(minio_path, inicio_processamento, tempo_captura_frame, tag_video)
            print(f"✅ Imagem salva e mensagem enviada: {minio_path}")
        except Exception as e:
            print(f"❌ Erro no upload: {e}")

    def run_asyncio_loop(self):
        """Executa o loop asyncio em uma thread separada."""
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

class RabbitMQManager:
    """Gerencia a conexão com RabbitMQ, garantindo que não seja fechada prematuramente."""

    def __init__(self):
        self.connection = None
        self.channel = None
        self.loop = asyncio.get_event_loop()

    async def connect(self):
        """Mantém uma conexão aberta e persistente com o RabbitMQ."""
        if self.connection is None or self.connection.is_closed:
            self.connection = await aio_pika.connect_robust("amqp://guest:guest@localhost:5672/")
            self.channel = await self.connection.channel()
            await self.channel.declare_exchange("direct_exchange", aio_pika.ExchangeType.DIRECT, durable=True)
            await self.channel.declare_queue("frame", durable=True)
            print("✅ Conectado ao RabbitMQ e canal configurado!")

    async def send_message(self, minio_path: str, inicio_processamento: int, tempo_captura_frame: int, tag_video: str):
        """Envia a mensagem garantindo que a conexão esteja ativa e inclui a tag video."""
        await self.connect()

        try:
            message_body = json.dumps({
                "minio_path": minio_path,
                "inicio_processamento": inicio_processamento,
                "tempo_captura_frame": tempo_captura_frame,
                "data_captura_frame": datetime.now().strftime("%d-%m-%Y"),
                "tag_video": tag_video,
                "timestamp": datetime.now().timestamp()
            })
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
