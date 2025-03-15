import tkinter as tk
from tkinter import ttk, messagebox
import cv2
import asyncio
from threading import Thread
from datetime import datetime
import io
import os
from PIL import Image, ImageTk

# Importa as funções e objetos de integração com o MinIO e RabbitMQ
from minio_utils import save_image_to_minio
from rabbitmq_manager import rabbitmq_manager

# Intervalo de captura (em segundos)
CAPTURE_INTERVAL = int(os.getenv("CAPTURE_INTERVAL", 1))

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

if __name__ == "__main__":
    root = tk.Tk()
    app = WebcamApp(root)
    root.mainloop()
import tkinter as tk
from tkinter import ttk, messagebox
import cv2
import asyncio
from threading import Thread
from datetime import datetime
import io
import os
from PIL import Image, ImageTk

# Importa as funções e objetos de integração com o MinIO e RabbitMQ
from minio_utils import save_image_to_minio
from rabbitmq_manager import rabbitmq_manager

# Intervalo de captura (em segundos)
CAPTURE_INTERVAL = int(os.getenv("CAPTURE_INTERVAL", 1))

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

if __name__ == "__main__":
    root = tk.Tk()
    app = WebcamApp(root)
    root.mainloop()
