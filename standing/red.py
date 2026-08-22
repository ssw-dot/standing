"""Un solo sitio donde vive todo lo que sale a la red.

Aqui esta el manejo de credenciales, el User-Agent y los errores. Los clientes
de cada API lo usan; nadie mas abre un socket.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
import uuid
from pathlib import Path

# Foxit sirve tras Cloudflare y devuelve 403 "error code: 1010" a cualquier
# peticion sin User-Agent de navegador. Medido: la misma peticion con y sin el
# da 403 y 200. No es opcional aunque no lo diga la documentacion.
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0 Safari/537.36")

RAIZ = Path(__file__).resolve().parents[1]


class SinClave(RuntimeError):
    pass


def cargar_env(ruta: Path | None = None) -> None:
    for linea in (ruta or RAIZ / ".env").read_text(encoding="utf-8").splitlines():
        if "=" in linea and not linea.lstrip().startswith("#"):
            k, _, v = linea.partition("=")
            v = v.strip().strip('"').strip("'")
            if v:
                os.environ.setdefault(k.strip(), v)


def clave(nombre: str) -> str:
    v = os.environ.get(nombre, "").strip()
    if not v:
        raise SinClave(
            f"falta {nombre}. Ponla en {RAIZ / '.env'} y no en el codigo.")
    return v


def peticion(url: str, *, datos: bytes | None = None,
             cabeceras: dict[str, str] | None = None,
             metodo: str | None = None, tiempo: int = 90) -> bytes:
    h = {"User-Agent": UA, **(cabeceras or {})}
    r = urllib.request.Request(url, data=datos, headers=h, method=metodo)
    try:
        with urllib.request.urlopen(r, timeout=tiempo) as resp:
            return resp.read()
    except urllib.error.HTTPError as e:
        # El cuerpo del error es donde estan los motivos utiles; sin el, un 400
        # es indistinguible de otro y se depura a ciegas.
        detalle = e.read()[:600].decode("utf-8", "replace")
        raise RuntimeError(f"HTTP {e.code} en {url}: {detalle}") from None


def multipart(campos: dict[str, str], ficheros: dict[str, tuple[str, bytes, str]]
              ) -> tuple[bytes, str]:
    lim = uuid.uuid4().hex
    partes = []
    for k, v in campos.items():
        partes.append(f"--{lim}\r\nContent-Disposition: form-data; "
                      f"name=\"{k}\"\r\n\r\n{v}\r\n".encode())
    for k, (nombre, contenido, tipo) in ficheros.items():
        partes.append(f"--{lim}\r\nContent-Disposition: form-data; name=\"{k}\";"
                      f" filename=\"{nombre}\"\r\nContent-Type: {tipo}\r\n\r\n"
                      .encode() + contenido + b"\r\n")
    partes.append(f"--{lim}--\r\n".encode())
    return b"".join(partes), f"multipart/form-data; boundary={lim}"


def json_de(bruto: bytes) -> dict:
    return json.loads(bruto.decode("utf-8", "replace"))
