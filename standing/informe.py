"""Foxit PDF Services: del veredicto a un PDF que se puede archivar.

Por que el informe es un PDF y no una pantalla: si alguien decide no presentarse
a una convocatoria, la razon tiene que sobrevivir a la sesion. Un PDF con las
citas del documento es algo que se le puede ensenar a un jefe, adjuntar a un
expediente o releer en seis meses. Una respuesta en un chat, no.

El flujo de Foxit son cuatro pasos y ninguno es opcional:
    subir HTML -> pedir conversion -> esperar la tarea -> descargar
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from .red import cargar_env, clave, json_de, multipart, peticion

BASE = "https://na1.fusion.foxit.com/pdf-services"
ESPERA = (1, 1, 2, 3, 5, 8, 13, 21)      # segundos entre sondeos


def _cabeceras() -> dict[str, str]:
    cargar_env()
    return {"client_id": clave("FOXIT_CLIENT_ID"),
            "client_secret": clave("FOXIT_CLIENT_SECRET")}


def subir(nombre: str, contenido: bytes, tipo: str) -> str:
    cuerpo, ctipo = multipart({}, {"file": (nombre, contenido, tipo)})
    d = json_de(peticion(f"{BASE}/api/documents/upload", datos=cuerpo,
                         metodo="POST",
                         cabeceras={**_cabeceras(), "Content-Type": ctipo}))
    return d["documentId"]


def _esperar(task_id: str) -> str:
    """Sondea la tarea hasta que termina. Devuelve el id del documento
    resultante.

    Con espera creciente y no fija: un PDF de dos paginas tarda un segundo y uno
    de doscientas tarda medio minuto. Sondear cada segundo durante medio minuto
    gasta cuota para nada.
    """
    for pausa in ESPERA:
        d = json_de(peticion(f"{BASE}/api/tasks/{task_id}",
                             cabeceras=_cabeceras()))
        estado = (d.get("status") or "").upper()
        if estado in ("COMPLETED", "SUCCESS", "DONE"):
            return d.get("resultDocumentId") or d.get("documentId")
        if estado in ("FAILED", "ERROR"):
            raise RuntimeError(f"Foxit fallo la tarea: {d}")
        time.sleep(pausa)
    raise TimeoutError(f"la tarea {task_id} no termino en {sum(ESPERA)} s")


def descargar(document_id: str) -> bytes:
    return peticion(f"{BASE}/api/documents/{document_id}/download",
                    cabeceras=_cabeceras())


def html_a_pdf(html: str, destino: Path) -> Path:
    doc = subir("informe.html", html.encode("utf-8"), "text/html")
    d = json_de(peticion(
        f"{BASE}/api/documents/create/pdf-from-html",
        datos=json.dumps({"documentId": doc}).encode(), metodo="POST",
        cabeceras={**_cabeceras(), "Content-Type": "application/json"}))
    destino.write_bytes(descargar(_esperar(d["taskId"])))
    return destino
