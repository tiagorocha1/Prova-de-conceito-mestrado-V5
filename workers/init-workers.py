import subprocess
import os

# Caminhos para os diretórios dos workers
WORKERS = {
    "captura": "workers/captura/captura.py",
    "deteccao": "workers/deteccao/deteccao.py",
    "reconhecimento": "workers/reconhecimento/reconhecimento.py",
    "banco_de_dados": "workers/banco_de_dados/banco_de_dados.py"
}

# Lista para armazenar os processos em execução
processes = []

try:
    print("🚀 Iniciando todos os workers...")
    for name, path in WORKERS.items():
        if os.path.exists(path):
            print(f"🔹 Iniciando {name}...")
            process = subprocess.Popen(["python", path], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            processes.append((name, process))
        else:
            print(f"❌ Worker {name} não encontrado: {path}")

    print("✅ Todos os workers foram iniciados!")
    
    # Mantém os processos rodando
    for name, process in processes:
        process.wait()
        print(f"⚠️ Worker {name} foi encerrado.")

except KeyboardInterrupt:
    print("⏹ Encerrando todos os workers...")
    for name, process in processes:
        process.terminate()
        print(f"🔻 {name} encerrado.")
