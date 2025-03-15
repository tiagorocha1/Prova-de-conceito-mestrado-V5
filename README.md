# Reconhecimento Facial - API Backend, Frontend e Workers

## 📌 Descrição

Este é um sistema de reconhecimento facial desenvolvido com FastAPI no backend, React no frontend e workers assíncronos para captura e processamento de imagens. Ele gerencia o armazenamento de imagens, identifica pessoas, registra presenças e fornece uma interface web para interação.

## 🛠 Tecnologias Utilizadas

### Backend:

- **FastAPI** - Framework para desenvolvimento de APIs em Python
- **MongoDB** - Banco de dados NoSQL para armazenamento de registros
- **MinIO** - Armazenamento de objetos para imagens
- **DeepFace** - Biblioteca de reconhecimento facial
- **Pydantic** - Validação de modelos de dados
- **Uvicorn** - Servidor ASGI para rodar a API

### Frontend:

- **React** - Biblioteca para construção de interfaces
- **React Router** - Gerenciamento de rotas
- **Styled Components** - Estilização do frontend

### Workers:

- **OpenCV** - Captura e processamento de imagens
- **RabbitMQ** - Mensageria para comunicação entre componentes
- **Tkinter** - Interface gráfica para seleção de câmeras
- **aio\_pika** - Conexão assíncrona com RabbitMQ
- **Dlib** - Detecção de faces
- **Pika** - Comunicação com RabbitMQ
- **DeepFace** - Reconhecimento facial baseado em aprendizado profundo
- **PyMongo** - Interface com banco de dados MongoDB

## 🚀 Instalação e Configuração

### 1️⃣ Requisitos

- Python 3.8+
- Node.js e npm/yarn instalados
- MongoDB rodando em `localhost:27017`
- MinIO rodando em `localhost:9000`
- RabbitMQ rodando em `localhost:5672`

### 2️⃣ Instalando dependências

#### Backend:

```sh
pip install -r requirements.txt
```

#### Frontend:

```sh
cd frontend
npm install
```

#### Workers:

```sh
cd workers
pip install -r requirements.txt
```

### 3️⃣ Criar o arquivo `.env`
Antes de rodar o projeto, crie um arquivo `.env` com base no `.env.example`. Você pode fazer isso executando:

```sh
cp workers/.env.example workers/.env
```

Em seguida, edite o arquivo `.env` e preencha as credenciais corretas, como `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`, `MONGO_URI`, entre outras.

### 4️⃣ Verifique se o `.env` está no `.gitignore`
O arquivo `.env` **não deve ser versionado no Git**, pois contém credenciais sensíveis. Certifique-se de que ele está listado no `.gitignore`:

```
workers/.env
```

### 5️⃣ Executando a API

Para iniciar a API, utilize:

```sh
uvicorn server:app --reload --host 0.0.0.0 --port 8000
```

A API ficará acessível em `http://localhost:8000`.

### 6️⃣ Executando o Frontend

Para rodar o frontend React:

```sh
cd frontend
npm start
```

O frontend estará acessível em `http://localhost:3000`.

### 7️⃣ Executando os Workers

Os workers são responsáveis por capturar e processar imagens enviadas ao MinIO e encaminhar mensagens para o RabbitMQ.

Para iniciar todos os workers de uma só vez, utilize:

```sh
cd workers
bash init-workers.py
```

Ou execute manualmente:

```sh
cd workers/captura && python captura.py
cd workers/deteccao && python deteccao.py
cd workers/reconhecimento && python reconhecimento.py
cd workers/banco_de_dados && python banco_de_dados.py
```

## 🌍 Endpoints Principais

### 📂 Pessoas

- `GET /pessoas` - Lista pessoas cadastradas
- `GET /pessoas/{uuid}` - Obtém detalhes de uma pessoa
- `DELETE /pessoas/{uuid}` - Remove uma pessoa e suas imagens
- `POST /pessoas/{uuid}/tags` - Adiciona uma tag a uma pessoa
- `DELETE /pessoas/{uuid}/tags` - Remove uma tag de uma pessoa

### 📸 Fotos

- `GET /pessoas/{uuid}/photos` - Lista URLs das fotos de uma pessoa
- `GET /pessoas/{uuid}/photo` - Obtém a URL da foto principal
- `GET /pessoas/{uuid}/photos/count` - Obtém a quantidade de fotos armazenadas

### 📝 Presenças

- `GET /presencas` - Lista presenças registradas
- `DELETE /presencas/{id}` - Remove um registro de presença

## 🖥️ Interface Web (Frontend)

O frontend é uma aplicação React que permite visualizar as pessoas cadastradas, suas fotos e os registros de presença.

### 🌟 Funcionalidades

- **Visualização de presenças** - Página para listar presenças registradas, com fotos capturadas.
- **Gerenciamento de pessoas** - Adicionar e remover tags das pessoas.
- **Visualização de fotos** - Listagem e remoção de fotos associadas a cada pessoa.
- **Navegação amigável** - Interface responsiva e intuitiva.

## ⚙️ Workers (Processamento de Imagens)

Os workers são serviços que capturam, processam e enviam imagens ao MinIO, além de gerenciar a comunicação via RabbitMQ.

### 🌟 Funcionalidades dos Workers

- **Captura de imagens da webcam** - Utilizando OpenCV.
- **Armazenamento de imagens no MinIO** - Envio das imagens capturadas para um bucket específico.
- **Mensageria via RabbitMQ** - Comunicação entre a captura e o backend para reconhecimento facial.
- **Interface gráfica para seleção de câmeras** - Utilizando Tkinter.
- **Detecção de Faces** - Utilizando Dlib para processar imagens recebidas e identificar rostos.
- **Reconhecimento Facial** - Utilizando DeepFace para comparar imagens e identificar pessoas.
- **Registro de Presença** - Armazena os dados de reconhecimento no MongoDB.
- **Envio de Imagens Processadas para o MinIO** - Armazenamento das imagens de rostos detectados.
- **Envio de Mensagens para o RabbitMQ** - Comunicação entre os workers para processar imagens capturadas.

## 📜 Licença

Este projeto está sob a licença MIT. Para mais detalhes, consulte o arquivo `LICENSE`.

