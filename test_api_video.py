#!/usr/bin/env python3
"""
Script de teste da API LingBot-Map com suporte a vídeo.

Uso:
  python test_api_video.py --video /caminho/para/video.mp4
  python test_api_video.py --video video.mp4 --fps 5 --mode windowed
  python test_api_video.py --video video.mp4 --first-k 50   # primeiros 50 frames
  python test_api_video.py --video video.mp4 --diagnose     # diagnóstico extra
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

import urllib.request
import urllib.parse
import urllib.error

BASE_URL = "http://localhost:8000"


def api_get(path: str) -> dict:
    url = f"{BASE_URL}{path}"
    with urllib.request.urlopen(url, timeout=30) as resp:
        return json.loads(resp.read())


def api_post_multipart(path: str, fields: dict, files: list) -> dict:
    """Envia POST multipart/form-data com suporte a arquivos grandes."""
    boundary = "----LingBotVideoBoundary7MA4YWxkTrZu0gW"
    body_parts = []

    for name, value in fields.items():
        body_parts.append(
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="{name}"\r\n\r\n'
            f"{value}\r\n"
        )

    file_data_parts = []
    for field_name, file_path, content_type in files:
        filename = Path(file_path).name
        file_size = Path(file_path).stat().st_size
        print(f"  Lendo arquivo: {filename} ({file_size / 1024 / 1024:.1f} MB)...")
        with open(file_path, "rb") as f:
            data = f.read()
        header = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="{field_name}"; filename="{filename}"\r\n'
            f"Content-Type: {content_type}\r\n\r\n"
        ).encode()
        file_data_parts.append(header + data + b"\r\n")
        print(f"  Arquivo lido ({len(data) / 1024 / 1024:.1f} MB na memória)")

    body = "".join(body_parts).encode() + b"".join(file_data_parts) + f"--{boundary}--\r\n".encode()

    print(f"  Enviando request ({len(body) / 1024 / 1024:.1f} MB total)...")
    req = urllib.request.Request(
        f"{BASE_URL}{path}",
        data=body,
        method="POST",
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    with urllib.request.urlopen(req, timeout=300) as resp:
        return json.loads(resp.read())


def download_file(url: str, dest: Path) -> None:
    with urllib.request.urlopen(url, timeout=300) as resp:
        dest.write_bytes(resp.read())


def progress_bar(progress: int, width: int = 40) -> str:
    filled = int(width * progress / 100)
    bar = "█" * filled + "░" * (width - filled)
    return f"[{bar}] {progress:3d}%"


def get_video_content_type(path: str) -> str:
    ext = Path(path).suffix.lower()
    mapping = {
        ".mp4": "video/mp4",
        ".avi": "video/x-msvideo",
        ".mov": "video/quicktime",
        ".mkv": "video/x-matroska",
        ".webm": "video/webm",
    }
    return mapping.get(ext, "video/mp4")


def main():
    parser = argparse.ArgumentParser(description="Testa a API LingBot-Map com vídeo")
    parser.add_argument("--api-url", default="http://localhost:8000", help="URL base da API")
    parser.add_argument("--video", required=True, help="Caminho para o arquivo de vídeo")
    parser.add_argument("--mode", default="streaming", choices=["streaming", "windowed"],
                        help="Modo de inferência (padrão: streaming)")
    parser.add_argument("--fps", type=int, default=5,
                        help="FPS para extração de frames do vídeo (padrão: 5)")
    parser.add_argument("--first-k", type=int, default=None,
                        help="Usar apenas os primeiros K frames extraídos")
    parser.add_argument("--window-size", type=int, default=64,
                        help="Tamanho da janela para modo windowed (padrão: 64)")
    parser.add_argument("--conf-threshold", type=float, default=50.0,
                        help="Limiar de confiança em %% (padrão: 50.0)")
    parser.add_argument("--mask-sky", action="store_true",
                        help="Mascarar céu (cenas externas)")
    parser.add_argument("--offload-to-cpu", action="store_true", default=True,
                        help="Offload resultados para CPU (recomendado, padrão: ativado)")
    parser.add_argument("--output", default="resultado_video.glb", help="Arquivo GLB de saída")
    parser.add_argument("--no-download", action="store_true", help="Não baixar o GLB ao finalizar")
    parser.add_argument("--diagnose", action="store_true",
                        help="Mostrar informações completas do job ao finalizar")
    args = parser.parse_args()

    global BASE_URL
    BASE_URL = args.api_url.rstrip("/")

    # ── Verificar arquivo de vídeo ─────────────────────────────────────────
    video_path = Path(args.video)
    if not video_path.exists():
        print(f"ERRO: Arquivo de vídeo não encontrado: {video_path}")
        sys.exit(1)

    video_size_mb = video_path.stat().st_size / 1024 / 1024
    print(f"Vídeo: {video_path.name} ({video_size_mb:.1f} MB)")

    # ── Verificar saúde da API ─────────────────────────────────────────────
    print("\nVerificando API...")
    try:
        health = api_get("/api/health")
    except Exception as e:
        print(f"  ERRO: Não foi possível conectar à API em {BASE_URL}")
        print(f"  Detalhes: {e}")
        sys.exit(1)

    status_icon = "✓" if health["status"] == "ok" else "✗"
    model_icon = "✓" if health["model_loaded"] else "✗"
    gpu_info = health.get("gpu", {})
    gpu_text = gpu_info.get("name", "CPU") if gpu_info.get("available") else "CPU (sem GPU)"

    print(f"  {status_icon} API: {health['status']}")
    print(f"  {model_icon} Modelo: {'carregado' if health['model_loaded'] else 'NÃO carregado'}")
    print(f"  ⚙ Dispositivo: {gpu_text}")

    if not health["model_loaded"]:
        print("\nAguarde o modelo terminar de carregar e tente novamente.")
        sys.exit(1)

    # ── Criar job com vídeo ────────────────────────────────────────────────
    content_type = get_video_content_type(str(video_path))
    print(f"\nCriando job (modo={args.mode}, fps={args.fps}, content-type={content_type})...")

    fields = {
        "mode": args.mode,
        "fps": str(args.fps),
        "conf_threshold": str(args.conf_threshold),
        "mask_sky": "true" if args.mask_sky else "false",
        "offload_to_cpu": "true" if args.offload_to_cpu else "false",
        "window_size": str(args.window_size),
    }
    if args.first_k is not None:
        fields["first_k"] = str(args.first_k)

    files = [("files", str(video_path), content_type)]

    try:
        job = api_post_multipart("/api/jobs", fields=fields, files=files)
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"  ERRO HTTP {e.code}: {body}")
        sys.exit(1)
    except Exception as e:
        print(f"  ERRO ao criar job: {e}")
        sys.exit(1)

    job_id = job["id"]
    print(f"  ✓ Job criado: {job_id}")

    # ── Monitorar progresso ────────────────────────────────────────────────
    print(f"\nMonitorando progresso (pode demorar vários minutos)...")
    print(f"  Vídeo grande? Use --fps 2 ou --first-k 30 para testar mais rápido.")
    start_time = time.time()
    last_status = None
    last_progress = -1

    while True:
        try:
            info = api_get(f"/api/jobs/{job_id}")
        except Exception as e:
            print(f"\n  Erro ao obter status: {e}")
            time.sleep(3)
            continue

        status = info["status"]
        progress = info.get("progress", 0)
        message = info.get("message", "")
        elapsed = time.time() - start_time

        # Mostrar mudanças de status sempre
        if status != last_status or abs(progress - last_progress) >= 5:
            bar = progress_bar(progress)
            print(f"\r  {bar}  {message[:40]:<40}  {elapsed:5.0f}s", end="", flush=True)
            last_status = status
            last_progress = progress

        if status == "completed":
            print(f"\n  ✓ Concluído em {elapsed:.0f}s")
            break
        elif status == "failed":
            error = info.get("error", "erro desconhecido")
            print(f"\n  ✗ FALHOU!")
            print(f"\n  Mensagem: {message}")
            print(f"\n  Erro completo:\n{error}")
            sys.exit(1)

        time.sleep(2)

    # ── Diagnóstico extra ──────────────────────────────────────────────────
    if args.diagnose:
        try:
            full_info = api_get(f"/api/jobs/{job_id}")
            print(f"\nInformações completas do job:")
            for k, v in full_info.items():
                if k != "error":
                    print(f"  {k}: {v}")
        except Exception as e:
            print(f"  Erro ao obter diagnóstico: {e}")

    # ── Baixar resultado ───────────────────────────────────────────────────
    if not args.no_download:
        output_path = Path(args.output)
        glb_url = f"{BASE_URL}/api/jobs/{job_id}/result"
        print(f"\nBaixando resultado GLB de {glb_url}...")
        try:
            download_file(glb_url, output_path)
            size_mb = output_path.stat().st_size / 1024 / 1024
            if size_mb < 0.001:
                print(f"  ⚠ AVISO: arquivo GLB muito pequeno ({size_mb:.3f} MB) - pode estar corrompido")
            else:
                print(f"  ✓ Salvo em: {output_path}  ({size_mb:.1f} MB)")
        except urllib.error.HTTPError as e:
            body = e.read().decode()
            print(f"  ERRO HTTP {e.code} ao baixar GLB: {body}")
            sys.exit(1)
        except Exception as e:
            print(f"  ERRO ao baixar GLB: {e}")
            sys.exit(1)
    else:
        print(f"\nResultado disponível em: {BASE_URL}/api/jobs/{job_id}/result")

    print(f"\nJob concluído! Visualize em http://localhost:3000")
    print(f"Ou abra '{args.output}' no https://gltf-viewer.donmccurdy.com/")


if __name__ == "__main__":
    main()
