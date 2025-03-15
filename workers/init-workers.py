import subprocess
import os

# Caminhos para os diretórios dos workers
WORKERS = {
    "captura": "captura/captura.py",
    "deteccao": "deteccao/deteccao.py",
    "reconhecimento": "reconhecimento/reconhecimento.py",
    "banco_de_dados": "banco_de_dados/banco_de_dados.py"
}

# Lista para armazenar os processos em execução
processes = []

try:
    print("🚀 Iniciando todos os workers...")
    for name, path in WORKERS.items():
        if os.path.exists(path):
            print(f"🔹 Iniciando {name}...")
            process = subprocess.Popen(["python", path], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            processes.append((name, process))
        else:
            print(f"❌ Worker {name} não encontrado: {path}")

    print("✅ Todos os workers foram iniciados!")
    
    # Mantém os processos rodando e captura erros
    for name, process in processes:
        stdout, stderr = process.communicate()
        print(f"⚠️ Worker {name} foi encerrado.")
        if stdout:
            print(f"📜 [STDOUT] {name}:\n{stdout}")
        if stderr:
            print(f"❌ [ERRO] {name}:\n{stderr}")

except KeyboardInterrupt:
    print("⏹ Encerrando todos os workers...")
    for name, process in processes:
        process.terminate()
        print(f"🔻 {name} encerrado.")
