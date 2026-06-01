#!/usr/bin/env python3
"""
Script de teste da API LingBot-Map.

Uso:
  python test_api.py                          # usa example/loop (20 imagens)
  python test_api.py --dataset courthouse     # outro dataset
  python test_api.py --images-dir /caminho    # diretório customizado
  python test_api.py --max-images 10          # limitar quantidade de imagens
  python test_api.py --mode windowed          # modo janela deslizante
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


def api_post_multipart(path: str, fields: dict, files: list[tuple]) -> dict:
    """Envia POST multipart/form-data sem dependências externas."""
    boundary = "----LingBotTestBoundary7MA4YWxkTrZu0gW"
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
        with open(file_path, "rb") as f:
            data = f.read()
        header = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="{field_name}"; filename="{filename}"\r\n'
            f"Content-Type: {content_type}\r\n\r\n"
        ).encode()
        file_data_parts.append(header + data + b"\r\n")

    body = "".join(body_parts).encode() + b"".join(file_data_parts) + f"--{boundary}--\r\n".encode()

    req = urllib.request.Request(
        f"{BASE_URL}{path}",
        data=body,
        method="POST",
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read())


def download_file(url: str, dest: Path) -> None:
    with urllib.request.urlopen(url, timeout=120) as resp:
        dest.write_bytes(resp.read())


def progress_bar(progress: int, width: int = 40) -> str:
    filled = int(width * progress / 100)
    bar = "█" * filled + "░" * (width - filled)
    return f"[{bar}] {progress:3d}%"


def main():
    parser = argparse.ArgumentParser(description="Testa a API LingBot-Map")
    parser.add_argument("--api-url", default="http://localhost:8000", help="URL base da API")
    parser.add_argument("--dataset", default="loop", choices=["courthouse", "loop", "oxford", "university"],
                        help="Dataset de exemplo a usar (padrão: loop)")
    parser.add_argument("--images-dir", help="Diretório customizado com imagens (sobrepõe --dataset)")
    parser.add_argument("--max-images", type=int, default=20,
                        help="Máximo de imagens a enviar (padrão: 20)")
    parser.add_argument("--mode", default="streaming", choices=["streaming", "windowed"],
                        help="Modo de inferência (padrão: streaming)")
    parser.add_argument("--output", default="resultado.glb", help="Arquivo GLB de saída")
    parser.add_argument("--no-download", action="store_true", help="Não baixar o GLB ao finalizar")
    args = parser.parse_args()

    global BASE_URL
    BASE_URL = args.api_url.rstrip("/")

    # ── Verificar saúde da API ─────────────────────────────────────────────
    print("Verificando API...")
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

    # ── Selecionar imagens ─────────────────────────────────────────────────
    workspace = Path(__file__).parent
    if args.images_dir:
        images_dir = Path(args.images_dir)
    else:
        images_dir = workspace / "example" / args.dataset

    if not images_dir.exists():
        print(f"\nDiretório não encontrado: {images_dir}")
        sys.exit(1)

    image_extensions = {".jpg", ".jpeg", ".png", ".webp"}
    all_images = sorted(
        p for p in images_dir.iterdir()
        if p.suffix.lower() in image_extensions
    )

    if not all_images:
        print(f"\nNenhuma imagem encontrada em: {images_dir}")
        sys.exit(1)

    images = all_images[: args.max_images]
    print(f"\nImagens: {len(images)}/{len(all_images)} de '{images_dir.name}'")
    for img in images[:3]:
        print(f"  • {img.name}")
    if len(images) > 3:
        print(f"  ... e mais {len(images) - 3}")

    # ── Criar job ──────────────────────────────────────────────────────────
    print(f"\nCriando job (modo={args.mode})...")
    files = [("files", str(img), "image/png") for img in images]
    fields = {"mode": args.mode}

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
    print(f"\nMonitorando progresso...")
    start_time = time.time()
    last_msg = ""

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

        bar = progress_bar(progress)
        line = f"\r  {bar}  {message[:35]:<35}  {elapsed:5.0f}s"
        print(line, end="", flush=True)

        if status == "completed":
            print(f"\n  ✓ Concluído em {elapsed:.0f}s")
            break
        elif status == "failed":
            error = info.get("error", "erro desconhecido")
            print(f"\n  ✗ FALHOU: {error}")
            sys.exit(1)

        time.sleep(2)

    # ── Baixar resultado ───────────────────────────────────────────────────
    if not args.no_download:
        output_path = Path(args.output)
        glb_url = f"{BASE_URL}/api/jobs/{job_id}/result"
        print(f"\nBaixando resultado GLB...")
        try:
            download_file(glb_url, output_path)
            size_mb = output_path.stat().st_size / 1024 / 1024
            print(f"  ✓ Salvo em: {output_path}  ({size_mb:.1f} MB)")
        except Exception as e:
            print(f"  ERRO ao baixar GLB: {e}")
            sys.exit(1)
    else:
        print(f"\nResultado disponível em: {BASE_URL}/api/jobs/{job_id}/result")

    print(f"\nJob concluído! Visualize o resultado em http://localhost:3000")
    print(f"Ou abra '{args.output}' no https://gltf-viewer.donmccurdy.com/")


if __name__ == "__main__":
    main()
