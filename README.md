# Reconhecimento Facial - API Backend, Frontend e Workers

## 📌 Descrição
Este é um sistema completo de reconhecimento facial com registro de presenças, utilizando arquitetura baseada em microserviços com comunicação assíncrona. Inclui backend (FastAPI), frontend (React), workers para captura/detecção/reconhecimento e armazenamento distribuído (MinIO).

## 🗂 Estrutura de Diretórios
```
📁 backend/        → Código da API FastAPI
📁 frontend/       → Aplicativo React (interface)
📁 workers/        → Scripts para captura, detecção e reconhecimento facial
```

## 🛠 Tecnologias Utilizadas

### Backend
- **FastAPI** - API REST em Python
- **MongoDB** - Banco de dados NoSQL
- **MinIO** - Armazenamento de imagens (S3-like)
- **Uvicorn** - Servidor ASGI para FastAPI
- **Python-Jose** - JWT para autenticação
- **Passlib (argon2)** - Hash de senhas seguro

### Frontend
- **React 19** - Interface responsiva
- **React Router DOM** - Navegação SPA
- **Styled Components** - Estilização
- **MediaPipe** - Captura e rastreamento facial em tempo real

### Workers
- **OpenCV** - Captura de webcam e leitura de vídeos
- **DeepFace** - Embeddings e reconhecimento facial
- **Tkinter** - Interface de seleção de fonte
- **aio_pika / pika** - Integração com RabbitMQ
- **MinIO SDK** - Upload/download de imagens
- **PyMongo** - Interação com MongoDB

### ⚠️ Dependência adicional para Windows

A biblioteca `dlib`, utilizada para detecção facial, **requer a instalação do Microsoft C++ Build Tools** no Windows. Sem essa dependência, a instalação do pacote falhará.

#### 🔧 Como instalar:

1. Acesse: [https://visualstudio.microsoft.com/visual-cpp-build-tools/](https://visualstudio.microsoft.com/visual-cpp-build-tools/)
2. Baixe e execute o instalador dos **Build Tools for Visual Studio**
3. Durante a instalação, selecione:
   - ✅ **Desenvolvimento com C++ (C++ build tools)**
   - ✅ **Windows 10 SDK** (ou superior)

> 💡 Essa etapa é necessária apenas para usuários Windows. Em sistemas baseados em Unix (Linux/Mac), os pacotes de compilação do sistema costumam ser suficientes.

## 🚀 Instalação e Configuração

### 1. Requisitos
- Python 3.8+
- Node.js e npm/yarn
- MongoDB em `localhost:27017`
- MinIO em `localhost:9000`
- RabbitMQ em `localhost:5672`

### 2. Instalando dependências
#### Backend
```bash
pip install -r requirements.txt
```

#### Frontend
```bash
cd frontend
npm install
```

#### Workers
```bash
cd workers
pip install -r requirements.txt
```

### 3. Arquivo `.env`
Copie e edite o `.env`:
```bash
cp workers/.env.example workers/.env
```

Inclua chaves como:
- `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`
- `MONGO_URI`
- `RABBITMQ_HOST`

Certifique-se de que `.env` está no `.gitignore`.

### 4. Executando a API
```bash
uvicorn server:app --reload --host 0.0.0.0 --port 8000
```

### 5. Executando o Frontend
```bash
cd frontend
npm install
npm start
```

### 6. Executando os Workers
```bash
cd workers/captura && python captura.py
cd workers/deteccao && python deteccao.py
cd workers/reconhecimento && python reconhecimento.py
cd workers/banco_de_dados && python banco_de_dados.py
```

## 🌐 Principais Endpoints

### Pessoas
- `GET /pessoas` - Lista de pessoas cadastradas
- `GET /pessoas/{uuid}` - Detalhes com URL da foto principal
- `GET /pessoas/{uuid}/photos` - Lista de fotos (URLs assinadas)
- `DELETE /pessoas/{uuid}` - Remove pessoa e suas imagens
- `POST /pessoas/{uuid}/tags` - Adiciona tag
- `DELETE /pessoas/{uuid}/tags` - Remove tag

### Fotos
- `GET /pessoas/{uuid}/photo` - Foto principal
- `GET /pessoas/{uuid}/photos/count` - Contador de fotos

### Presenças
- `GET /presencas` - Lista de presenças com filtros
- `DELETE /presencas/{id}` - Remove uma presença

### Presentes
- `GET /presentes?date=dd-MM-yyyy&min_presencas=N`

### Admin
- `GET /create_admin` - Cria usuário admin (admin/admin)

## 💻 Interface Web

### Funcionalidades
- Visualização de presenças com filtros e imagens
- Listagem de pessoas e suas fotos
- Adição e remoção de tags
- Modal para visualizar fotos
- Identifica presentes por data

## ⚙️ Funcionalidades dos Workers

- 📸 Captura de imagens (webcam/vídeo)
- 💾 Armazenamento no MinIO
- 📡 Envio de mensagens via RabbitMQ
- 🧠 Detecção de faces com filtros (frontalidade, tamanho)
- 🧬 Geração e comparação de embeddings com DeepFace
- 🧾 Registro de presenças no MongoDB

## 🔐 Autenticação e Segurança
- JWT com expiração configurável
- Hash seguro de senhas com Argon2
- Endpoints protegidos por dependências do FastAPI

## 📜 Testes

### Backend
```bash
pytest
```

### Frontend
```bash
npm test
```

## 📜 Licença
Este projeto está sob a licença MIT. Consulte o arquivo `LICENSE` para detalhes.

---

Caso queira gerar um PDF desta documentação ou publicar no GitHub Pages, entre em contato com o mantenedor do projeto.

