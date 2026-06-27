"""
Autorización OAuth de un solo uso contra la cuenta de TikTok @EspanaVintage.

Ejecutar una vez: python3 auth_setup.py
Abrirá el navegador, pides login/autorización con tu cuenta de TikTok,
y el script guarda el access_token y refresh_token en .env automáticamente.

Requiere que en TikTok for Developers -> Login Kit hayas registrado
el redirect URI: http://localhost:8920/callback
"""
import http.server
import os
import secrets
import urllib.parse
import webbrowser

import requests
from dotenv import dotenv_values, load_dotenv

REDIRECT_URI = "http://localhost:8920/callback"
SCOPES = "user.info.basic,video.publish"
ENV_PATH = os.path.join(os.path.dirname(__file__), ".env")

load_dotenv(ENV_PATH)
CLIENT_KEY = os.environ["TIKTOK_CLIENT_KEY"]
CLIENT_SECRET = os.environ["TIKTOK_CLIENT_SECRET"]

_state = secrets.token_urlsafe(16)
_received_code = {}


class _CallbackHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        if params.get("state", [""])[0] != _state:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"Estado invalido, intenta de nuevo.")
            return
        _received_code["code"] = params.get("code", [None])[0]
        self.send_response(200)
        self.end_headers()
        self.wfile.write("Autorizacion completada, puedes cerrar esta pestana.".encode())

    def log_message(self, format, *args):
        pass


def _update_env(updates: dict):
    values = dotenv_values(ENV_PATH)
    values.update(updates)
    with open(ENV_PATH, "w") as f:
        for key, value in values.items():
            f.write(f"{key}={value or ''}\n")


def main():
    auth_url = "https://www.tiktok.com/v2/auth/authorize/?" + urllib.parse.urlencode({
        "client_key": CLIENT_KEY,
        "scope": SCOPES,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "state": _state,
    })

    print("Abriendo navegador para autorizar la app contra tu cuenta de TikTok...")
    webbrowser.open(auth_url)

    server = http.server.HTTPServer(("localhost", 8920), _CallbackHandler)
    while "code" not in _received_code:
        server.handle_request()
    server.server_close()

    code = _received_code["code"]
    if not code:
        print("No se recibio codigo de autorizacion. Revisa el redirect URI configurado en TikTok.")
        return

    token_resp = requests.post(
        "https://open.tiktokapis.com/v2/oauth/token/",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={
            "client_key": CLIENT_KEY,
            "client_secret": CLIENT_SECRET,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": REDIRECT_URI,
        },
    )
    token_resp.raise_for_status()
    data = token_resp.json()

    if "access_token" not in data:
        print("Error al obtener el token:", data)
        return

    _update_env({
        "TIKTOK_ACCESS_TOKEN": data["access_token"],
        "TIKTOK_REFRESH_TOKEN": data["refresh_token"],
    })
    print("Listo. access_token y refresh_token guardados en .env")


if __name__ == "__main__":
    main()
