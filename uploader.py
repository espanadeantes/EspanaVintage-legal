"""
Sube a TikTok el siguiente video pendiente en la cola, vía Content Posting API.

Uso: python3 uploader.py
Pensado para ser invocado periodicamente por un scheduler (cron/launchd),
ver schedule_setup.sh. Cada ejecucion publica como maximo un video.
"""
import os
import shutil
import time
from pathlib import Path

import requests
import yaml
from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")

with open(BASE_DIR / "config.yaml") as f:
    CONFIG = yaml.safe_load(f)

CLIENT_KEY = os.environ["TIKTOK_CLIENT_KEY"]
ACCESS_TOKEN = os.environ.get("TIKTOK_ACCESS_TOKEN")

PENDIENTES = BASE_DIR / CONFIG["carpeta_pendientes"]
PUBLICADOS = BASE_DIR / CONFIG["carpeta_publicados"]
LOG_PATH = BASE_DIR / "publicaciones.log"


def _siguiente_video():
    candidatos = sorted(
        p for p in PENDIENTES.iterdir()
        if p.suffix.lower() in CONFIG["extensiones_validas"]
    )
    return candidatos[0] if candidatos else None


def _caption_para(video_path: Path) -> str:
    txt_path = video_path.with_suffix(".txt")
    if txt_path.exists():
        return txt_path.read_text(encoding="utf-8").strip()
    return CONFIG["caption_por_defecto"]


def _log(mensaje: str):
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - {mensaje}\n")
    print(mensaje)


def _init_publish(video_path: Path, caption: str) -> dict:
    size_bytes = video_path.stat().st_size
    payload = {
        "post_info": {
            "title": caption,
            "privacy_level": "PUBLIC_TO_EVERYONE",
            "disable_duet": False,
            "disable_comment": False,
            "disable_stitch": False,
        },
        "source_info": {
            "source": "FILE_UPLOAD",
            "video_size": size_bytes,
            "chunk_size": size_bytes,
            "total_chunk_count": 1,
        },
    }
    endpoint = (
        "https://open.tiktokapis.com/v2/post/publish/video/init/"
        if CONFIG["modo_publicacion"] == "DIRECT_POST"
        else "https://open.tiktokapis.com/v2/post/publish/inbox/video/init/"
    )
    resp = requests.post(
        endpoint,
        headers={
            "Authorization": f"Bearer {ACCESS_TOKEN}",
            "Content-Type": "application/json; charset=UTF-8",
        },
        json=payload,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("error", {}).get("code") not in (None, "ok"):
        raise RuntimeError(f"Error iniciando publicacion: {data}")
    return data["data"]


def _subir_video(upload_url: str, video_path: Path):
    size_bytes = video_path.stat().st_size
    with open(video_path, "rb") as f:
        resp = requests.put(
            upload_url,
            headers={
                "Content-Type": "video/mp4",
                "Content-Range": f"bytes 0-{size_bytes - 1}/{size_bytes}",
            },
            data=f,
        )
    resp.raise_for_status()


def publicar_siguiente():
    if not ACCESS_TOKEN:
        _log("No hay TIKTOK_ACCESS_TOKEN en .env. Ejecuta primero auth_setup.py")
        return

    video_path = _siguiente_video()
    if video_path is None:
        _log("No hay videos pendientes en la cola.")
        return

    caption = _caption_para(video_path)
    _log(f"Publicando: {video_path.name}")

    init_data = _init_publish(video_path, caption)
    _subir_video(init_data["upload_url"], video_path)

    PUBLICADOS.mkdir(exist_ok=True)
    shutil.move(str(video_path), PUBLICADOS / video_path.name)
    txt_path = video_path.with_suffix(".txt")
    if txt_path.exists():
        shutil.move(str(txt_path), PUBLICADOS / txt_path.name)

    _log(f"Publicado correctamente: {video_path.name} (publish_id={init_data.get('publish_id')})")


if __name__ == "__main__":
    publicar_siguiente()
