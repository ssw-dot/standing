"""Doctavian: el informe deja de vivir en el codigo y pasa a vivir en la plantilla.

Standing ya sabia escribir un PDF. Foxit convierte a PDF lo que este programa ha
compuesto: el orden de las secciones, que se ensena cuando no hay bloqueantes,
como se ve una duda. Toda esa forma esta escrita en Python. Cambiarla es tocar
codigo, y quien necesita cambiarla —quien redacta informes de cribado para una
fundacion o un ayuntamiento— no toca codigo.

Doctavian invierte eso. La plantilla es un DOCX con elementos que **iteran sobre
los requisitos, ocultan secciones enteras segun el veredicto y calculan
recuentos** por si mismos. La logica de presentacion vive en un documento de
Word que se abre y se edita. Este modulo solo entrega datos limpios y recoge el
PDF.

    plantilla.docx  +  {datos}  ->  informe.pdf

Y esa es la frase honesta de donde Doctavian hace el trabajo de verdad: no
convierte un PDF que ya estaba compuesto, **compone**. Las tres cosas que aqui
cambian de sitio son el bucle sobre los requisitos, la seccion de bloqueantes
que desaparece cuando no hay ninguno, y el bloque de dudas que solo existe si
el documento callaba.

## Autenticacion

Dos cabeceras, y las dos hacen falta:

  * `x-api-key`  — identifica el area de API (Documents). Es fija.
  * `Authorization: Bearer …` — identifica *a quien llama*, y sale de un inicio
    de sesion OAuth con cuenta de Microsoft o Google.

El token caduca. No es un descuido de este modulo: es como funciona su OAuth, y
por eso el token se lee del `.env` en cada llamada y nunca se cachea en disco.
Medido el 2026-08-28: con la ruta sin `/v1` la API responde
`Unauthorized ApiKeyNotFound` aunque la clave sea correcta — el prefijo de
version forma parte de la identidad de la clave, no es decoracion.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from .red import cargar_env, json_de, multipart, peticion
from .veredicto import Resultado

BASE_POR_DEFECTO = "https://demo.api.doctavian.com/v1"

# Contenedores de Storage. La documentacion los nombra al describir la descarga
# y avisa de que no valida el valor como enum cerrado: uno desconocido no da un
# error claro, da FILE_DOWNLOAD_FAILED. Por eso son constantes y no cadenas
# sueltas repartidas por el fichero.
TIPO_PLANTILLA = "document-template"
TIPO_DATOS = "document-data"
TIPO_SALIDA = os.environ.get("DOCTAVIAN_TIPO_SALIDA", "document-input")


class SinDoctavian(RuntimeError):
    pass


def _base() -> str:
    cargar_env()
    return os.environ.get("DOCTAVIAN_URL", BASE_POR_DEFECTO).rstrip("/")


def _cabeceras(extra: dict[str, str] | None = None) -> dict[str, str]:
    cargar_env()
    clave = os.environ.get("DOCTAVIAN_KEY", "").strip()
    token = os.environ.get("DOCTAVIAN_TOKEN", "").strip()
    if not clave:
        raise SinDoctavian(
            "falta DOCTAVIAN_KEY. Es la clave del area Documents, del portal.")
    if not token:
        raise SinDoctavian(
            "falta DOCTAVIAN_TOKEN. Es un bearer de OAuth y caduca: se copia "
            "del portal (API Keys) cada vez, y va en .env, nunca en el codigo.")
    return {"x-api-key": clave, "Authorization": f"Bearer {token}",
            **(extra or {})}


def _id_subido(bruto: bytes) -> str:
    """El id de Storage de una subida, o un error que dice que devolvieron.

    Sin este mensaje, un cambio en la forma de la respuesta se manifiesta como
    un KeyError sin contexto tres llamadas mas abajo.
    """
    d = json_de(bruto)
    try:
        return d["result"]["data"]["files"][0]["id"]
    except (KeyError, IndexError, TypeError):
        raise SinDoctavian(
            f"respuesta de subida inesperada: {json.dumps(d)[:300]}") from None


def subir_plantilla(docx: Path) -> str:
    cuerpo, tipo = multipart({}, {"file": (docx.name, docx.read_bytes(),
                                           "application/vnd.openxmlformats-"
                                           "officedocument.wordprocessingml."
                                           "document")})
    return _id_subido(peticion(
        f"{_base()}/documents/template/upload", datos=cuerpo, metodo="POST",
        cabeceras=_cabeceras({"Content-Type": tipo,
                              "X-Storage-Type": TIPO_PLANTILLA})))


def subir_datos(datos: dict) -> str:
    crudo = json.dumps(datos, ensure_ascii=False).encode("utf-8")
    cuerpo, tipo = multipart({}, {"file": ("datos.json", crudo,
                                           "application/json")})
    return _id_subido(peticion(
        f"{_base()}/documents/data/upload", datos=cuerpo, metodo="POST",
        cabeceras=_cabeceras({"Content-Type": tipo,
                              "X-Storage-Type": TIPO_DATOS})))


def generar(plantilla: str, datos: str, *, nombre: str = "standing-report",
            zona: str = "(GMT-06:00) Central Standard Time (America/Mexico_City)",
            locale: str = "en_US_POSIX") -> str:
    """Compone el documento y devuelve el id del PDF en Storage."""
    cuerpo = {
        "template": {"urn": plantilla, "fileFormat": "docx",
                     "loadMethod": "Storage"},
        "data": {"urn": datos, "loadMethod": "Storage"},
        "document": {"name": nombre, "fileFormat": "pdf",
                     "deliveryMethod": "Storage",
                     "timezone": zona, "locale": locale},
    }
    d = json_de(peticion(
        f"{_base()}/documents/document/generate",
        datos=json.dumps(cuerpo).encode("utf-8"), metodo="POST",
        cabeceras=_cabeceras({"Content-Type": "application/json"})))
    try:
        return d["result"]["data"]["document"]["urn"]
    except (KeyError, TypeError):
        raise SinDoctavian(
            f"respuesta de generacion inesperada: {json.dumps(d)[:300]}"
        ) from None


def descargar(urn: str, tipo: str = TIPO_SALIDA) -> bytes:
    return peticion(f"{_base()}/documents/document/{urn}/download",
                    cabeceras=_cabeceras({"X-Storage-Type": tipo}))


# ------------------------------------------------------------------ los datos

ETIQUETA = {"ELEGIBLE": "ELIGIBLE",
            "NO_ELEGIBLE": "NOT ELIGIBLE",
            "NO_SE_PUEDE_SABER": "CANNOT BE DETERMINED"}


def _fila(c) -> dict:
    return {"clave": c.requisito.clave,
            "cita": c.requisito.cita,
            "motivo": c.motivo,
            "estado": {True: "meets", False: "fails", None: "unclear"}[c.cumple]}


def datos_de(res: Resultado, *, documento: str, perfil: dict) -> dict:
    """Lo que consume la plantilla.

    Las banderas `hay…` van explicitas y no se dejan deducir de una lista vacia.
    Una plantilla que decide si ensena una seccion contando elementos es una
    plantilla que hay que leer entera para saber que hara; una que pregunta
    `hayBloqueantes` dice lo que hace en la propia palabra. Y el que la edite
    despues no sera programador.
    """
    bloq = [_fila(c) for c in res.bloqueantes]
    dudas = [_fila(c) for c in res.dudosas]
    cumplidas = [_fila(c) for c in res.comprobaciones if c.cumple is True]
    return {
        "documento": documento,
        "veredicto": ETIQUETA.get(res.veredicto.value, res.veredicto.value),
        "esElegible": res.veredicto.value == "ELEGIBLE",
        "esNoElegible": res.veredicto.value == "NO_ELEGIBLE",
        "esDuda": res.veredicto.value == "NO_SE_PUEDE_SABER",
        "perfil": [{"campo": k, "valor": str(v)} for k, v in perfil.items()],
        "requisitos": cumplidas + bloq + dudas,
        "bloqueantes": bloq,
        "dudas": dudas,
        "avisos": [{"texto": a} for a in res.avisos],
        "hayBloqueantes": bool(bloq),
        "hayDudas": bool(dudas),
        "hayAvisos": bool(res.avisos),
        "totalRequisitos": len(res.comprobaciones),
        "totalCumplidas": len(cumplidas),
    }


def informe(res: Resultado, *, documento: str, perfil: dict, plantilla: Path,
            salida: Path) -> Path:
    """Sube plantilla y datos, compone, y deja el PDF en `salida`."""
    p = subir_plantilla(plantilla)
    d = subir_datos(datos_de(res, documento=documento, perfil=perfil))
    salida.write_bytes(descargar(generar(p, d, nombre=salida.stem)))
    return salida
