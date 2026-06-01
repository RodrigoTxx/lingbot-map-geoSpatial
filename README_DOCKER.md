# Docker + Frontend — Guia de Uso

## Arquitetura

```
┌─────────────────────────────────────────────────┐
│                   Browser                       │
│            React + Three.js (port 3000)         │
└──────────────┬────────────────────────┬──────────┘
               │ HTTP/REST              │ WebSocket
               ▼                        ▼
┌─────────────────────────────────────────────────┐
│            Nginx (port 3000)                    │
│   /api/* → proxy → backend:8000                 │
└──────────────────────┬──────────────────────────┘
                       │
               ┌───────▼────────┐
               │ FastAPI (8000) │  ← GPU container
               │  + Worker      │
               └───────┬────────┘
                       │
               ┌───────▼────────┐
               │   /models/     │  ← volume montado
               │ lingbot-map-   │
               │   long.pt      │
               └────────────────┘
```

## Pré-requisitos

- Docker ≥ 24 com **NVIDIA Container Toolkit**
- Driver NVIDIA compatível com CUDA 12.8
- Checkpoint do modelo (`.pt`) em `./models/`

### Verificar NVIDIA Container Toolkit

```bash
docker run --rm --gpus all nvidia/cuda:12.8.0-base-ubuntu22.04 nvidia-smi
```

## Setup rápido

**1. Baixar o modelo**

```bash
mkdir models
# Hugging Face
huggingface-cli download robbyant/lingbot-map lingbot-map-long.pt \
    --local-dir models/

# OU ModelScope
pip install modelscope
python -c "
from modelscope import snapshot_download
snapshot_download('Robbyant/lingbot-map', local_dir='models/')
"
```

**2. Build e inicializar**

```bash
docker compose up --build
```

O primeiro build leva ~10–15 min (download de PyTorch + FlashInfer JIT).  
Reconstruções posteriores usam cache.

**3. Acessar**

| Interface | URL |
|---|---|
| **Frontend** | http://localhost:3000 |
| **API Docs** | http://localhost:8000/docs |
| **Health** | http://localhost:8000/api/health |

## Uso do Frontend

1. Arraste imagens (`.jpg`, `.png`) ou um vídeo (`.mp4`, `.avi`, etc.) na área de upload
2. Configure parâmetros (modo, FPS, sky mask…)
3. Clique em **"Reconstruir em 3D"**
4. Acompanhe o progresso na lista de jobs
5. Quando concluído, clique no job para visualizar a nuvem de pontos 3D interativa
6. Use **"Baixar GLB"** para exportar o arquivo

## API REST

### Criar job via `curl`

```bash
# Upload de imagens
curl -X POST http://localhost:8000/api/jobs \
  -F "files=@img1.jpg" \
  -F "files=@img2.jpg" \
  -F "mode=streaming" \
  -F "mask_sky=false"

# Upload de vídeo
curl -X POST http://localhost:8000/api/jobs \
  -F "files=@video.mp4" \
  -F "mode=windowed" \
  -F "window_size=128" \
  -F "keyframe_interval=5" \
  -F "fps=10"
```

### Parâmetros disponíveis

| Parâmetro | Padrão | Descrição |
|---|---|---|
| `mode` | `streaming` | `streaming` ou `windowed` (sequências longas) |
| `keyframe_interval` | auto | Manter 1 a cada N frames no KV cache |
| `window_size` | 64 | Tamanho da janela (modo windowed) |
| `camera_num_iterations` | 4 | Iterações de refinamento da câmera (1 = mais rápido) |
| `mask_sky` | false | Mascarar pontos de céu (cenas externas) |
| `conf_threshold` | 50 | Percentil de filtragem de confiança |
| `fps` | 10 | FPS para extração de frames de vídeo |
| `offload_to_cpu` | true | Offload para CPU (economiza VRAM) |

### Monitorar progresso

```bash
# HTTP polling
curl http://localhost:8000/api/jobs/<JOB_ID>

# WebSocket (via wscat)
wscat -c ws://localhost:8000/api/jobs/<JOB_ID>/ws
```

### Baixar resultado

```bash
curl -o resultado.glb http://localhost:8000/api/jobs/<JOB_ID>/result
```

## Variáveis de ambiente (backend)

| Variável | Padrão | Descrição |
|---|---|---|
| `MODEL_PATH` | `/models/lingbot-map-long.pt` | Caminho do checkpoint |
| `UPLOAD_BASE` | `/data/uploads` | Diretório de uploads |
| `CORS_ORIGINS` | `*` | Origens CORS permitidas (produção: domínio específico) |
| `USE_SDPA` | `false` | Usar PyTorch SDPA em vez de FlashInfer |

## Desenvolvimento sem Docker

```bash
# Backend
pip install fastapi "uvicorn[standard]" python-multipart
MODEL_PATH=/path/to/lingbot-map-long.pt uvicorn api.main:app --reload --port 8000

# Frontend (em outro terminal)
cd frontend
npm install
npm run dev   # http://localhost:5173 (proxy → localhost:8000)
```

## Solução de problemas

**GPU não detectada:**
```bash
# Verificar suporte a GPU no Docker
docker info | grep -i runtime
# Deve mostrar: Runtimes: nvidia runc
```

**VRAM insuficiente:**
- Use `offload_to_cpu=true` (padrão)
- Aumente `keyframe_interval` (ex.: 4 ou 8)
- Reduza `camera_num_iterations` para 1

**Modelo não carregado:**
```bash
curl http://localhost:8000/api/health
# "model_loaded": true indica sucesso
```
