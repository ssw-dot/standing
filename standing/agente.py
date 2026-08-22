"""La capa del modelo. Su trabajo es leer y citar, no decidir.

El modelo NO devuelve un veredicto. Devuelve requisitos, y cada uno con la
frase literal del documento que lo dice. Comparar esos requisitos contra el
perfil lo hace `veredicto.py`, que es aritmetica y no alucina.

La division no es estetica. A un modelo al que le preguntas "¿es elegible?" le
estas pidiendo una conclusion, y produce una conclusion siempre — incluso
cuando el documento no da para tanto. Pedirle en cambio "copiame la frase donde
lo dice" tiene una propiedad util: **cuando no existe la frase, no hay nada que
copiar**, y eso se detecta.

Por eso todo requisito sin cita se descarta antes del veredicto: la cita se
verifica contra el texto original, y si no aparece, el requisito se lo invento.
"""
from __future__ import annotations

import json
import os
import re

from .red import cargar_env, clave, json_de, peticion
from .veredicto import Requisito

# Cadena de respaldo, no un modelo fijo. Medido el 2026-08-21 con una clave
# nueva y la misma peticion minima:
#
#   gemini-flash-latest        cuelga 25 s sin responder
#   gemini-2.5-flash           404 "no longer available to new users"
#   gemini-flash-lite-latest   200 en 0,9 s
#   gemma-4-31b-it             200 en 5,1 s
#
# Fijar uno solo significa que el dia que el jurado lo ejecute, si ese esta
# caido, el proyecto no arranca y parece que no funciona. Un alias flotante
# tampoco basta: el que colgo ERA el alias flotante.
MODELOS = [m for m in os.environ.get("STANDING_MODELOS", "").split(",") if m] or [
    "gemini-flash-lite-latest",
    "gemma-4-31b-it",
    "gemini-flash-latest",
]
TIEMPO = int(os.environ.get("STANDING_TIEMPO", "45"))

INSTRUCCION = """You extract eligibility requirements from a call for
proposals, grant, tender or funding document.

Return ONLY a JSON array. Each element:
  {"clave": "<short snake_case key>",
   "cita": "<VERBATIM sentence from the document stating this requirement>",
   "valores": ["<each accepted value>"],
   "tipo": "lugar" | "texto"}

Rules that matter more than completeness:
- "cita" MUST be copied character-for-character from the document. Never
  paraphrase, never translate, never tidy it up. It is checked against the
  source and dropped if it is not found.
- "valores" lists what the document ACCEPTS, not what it rejects.
- Use "tipo": "lugar" only for countries, regions or territories.
- If the document states a requirement but does not say which values qualify,
  return it with an empty "valores" list. Do not guess the values.
- If you find no requirements, return []. An empty array is a valid answer and
  a better one than an invented requirement.

Common keys: pais, tipo_de_entidad, tamano, sector, edad, antiguedad,
facturacion, plazo."""


def _llamar(texto: str) -> str:
    """Prueba los modelos por orden y devuelve el primero que responda.

    Los fallos se acumulan y se relanzan juntos si ninguno funciona: saber que
    uno dio 404 y otro se colgo es lo que permite arreglarlo. Un mensaje de
    "no se pudo contactar al modelo" no dice nada.
    """
    cargar_env()
    fallos = []
    for modelo in MODELOS:
        try:
            return _llamar_a(modelo, texto)
        except Exception as e:
            fallos.append(f"{modelo}: {type(e).__name__} {str(e)[:120]}")
    raise RuntimeError("ningun modelo respondio:" + "".join(chr(10) + "  " + f for f in fallos))


def _llamar_a(modelo: str, texto: str) -> str:
    url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
           f"{modelo}:generateContent?key={clave('GOOGLE_API_KEY')}")
    cuerpo = json.dumps({
        "systemInstruction": {"parts": [{"text": INSTRUCCION}]},
        "contents": [{"parts": [{"text": texto[:120_000]}]}],
        # temperatura 0: la misma convocatoria tiene que dar el mismo cribado
        # dos veces. Un veredicto que cambia entre ejecuciones no se puede
        # defender ante nadie.
        "generationConfig": {"temperature": 0, "responseMimeType": "application/json"},
    }).encode()
    d = json_de(peticion(url, datos=cuerpo, metodo="POST", tiempo=TIEMPO,
                         cabeceras={"Content-Type": "application/json"}))
    try:
        return d["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError):
        raise RuntimeError(f"el modelo no devolvio texto: {str(d)[:300]}") from None


def _normalizar_espacios(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()


# Frases con las que un documento dice "las reglas estan en otro sitio". Salio
# de una convocatoria real de Horizon Europe, cuyo texto dice que "the General
# Annexes to this work programme set out the general conditions applying to the
# calls... such as eligibility rules".
#
# Sin esto, el sistema devolvia "no se encontro ningun requisito", que es cierto
# y es inutil: esconde el unico dato accionable del documento, que es DONDE
# estan las reglas. Un documento que remite no es un documento sin reglas.
REMISIONES = (
    "general annexes", "annex to this", "annexes to this", "set out in annex",
    "as set out in the general", "detailed in annex", "see annex",
    "conditions applying to the calls", "eligibility rules are set out",
    "en el anexo", "en las bases", "bases reguladoras", "vease el anexo",
    "conforme a las bases", "segun las bases generales",
)


def detectar_remision(texto: str) -> list[str]:
    """Frases donde el documento delega sus reglas en otro documento.

    Devuelve las frases completas, no solo la coincidencia: al usuario le sirve
    saber a que anexo tiene que ir, no que exista uno.
    """
    import re
    frases = re.split(r"(?<=[.;])\s+", re.sub(r"\s+", " ", texto))
    fuera = []
    for f in frases:
        bajo = f.lower()
        # Ademas de la frase de remision, la oracion tiene que hablar de
        # elegibilidad o condiciones. Sin este segundo filtro entraba cualquier
        # mencion de un anexo —"the TRL definition is available in the General
        # Annexes"— y el aviso perdia todo su valor: si todo remite, nada
        # remite.
        habla_de_reglas = any(w in bajo for w in (
            "eligib", "condition", "requirement", "criteri", "rules",
            "elegib", "requisito", "condicion", "bases"))
        if (any(r in bajo for r in REMISIONES) and habla_de_reglas
                and len(f) < 400):
            fuera.append(f.strip())
    # Sin duplicados, conservando el orden en que aparecen en el documento.
    vistas, unicas = set(), []
    for f in fuera:
        if f not in vistas:
            vistas.add(f)
            unicas.append(f)
    return unicas[:4]


def _trozos(texto: str, tam: int = 18_000, solape: int = 1_500):
    """Parte el texto en trozos que se solapan.

    Existe porque un documento de 88.000 caracteres, dado entero, se lee por
    encima: el modelo devolvio CERO requisitos de una convocatoria que tenia al
    menos dos, uno de ellos geografico. Con trozos mas pequenos los encuentra.

    El solape no es adorno: un requisito partido justo por el corte se perderia
    en los dos trozos a la vez, y ese es el fallo que nadie ve porque no da
    error.
    """
    if len(texto) <= tam:
        return [texto]
    trozos, i = [], 0
    while i < len(texto):
        trozos.append(texto[i:i + tam])
        i += tam - solape
    return trozos


def extraer_requisitos(texto: str) -> tuple[list[Requisito], list[str]]:
    """Devuelve (requisitos con cita verificada, avisos).

    La verificacion de la cita es el control anti-invencion. Un requisito cuya
    frase no aparece en el documento no entra al veredicto: se reporta aparte,
    para que se vea que el modelo se lo saco de la manga en vez de que
    desaparezca en silencio.
    """
    trozos = _trozos(texto)
    datos, avisos_previos = [], []
    for n, trozo in enumerate(trozos, 1):
        bruto = _llamar(trozo)
        try:
            parcial = json.loads(bruto)
        except json.JSONDecodeError:
            avisos_previos.append(
                f"el trozo {n} de {len(trozos)} no devolvio JSON valido: "
                f"{bruto[:120]}")
            continue
        if isinstance(parcial, list):
            datos.extend(parcial)
        else:
            avisos_previos.append(
                f"el trozo {n} devolvio {type(parcial).__name__}, no una lista")

    plano = _normalizar_espacios(texto)
    reqs, avisos = [], list(avisos_previos)
    vistos = set()
    for d in datos:
        if not isinstance(d, dict):
            continue
        cita = str(d.get("cita", "")).strip()
        clave_ = str(d.get("clave", "")).strip()
        if not clave_ or not cita:
            avisos.append(f"descartado un requisito sin clave o sin cita: {d}")
            continue
        if _normalizar_espacios(cita) not in plano:
            avisos.append(
                f"descartado '{clave_}': la cita no aparece en el documento. "
                f"El modelo la reformulo o se la invento: \"{cita[:90]}\"")
            continue
        valores = d.get("valores") or []
        if isinstance(valores, str):
            valores = [valores]
        # Los trozos se solapan, asi que un requisito que caiga en la zona
        # comun sale dos veces. Se deduplica por la cita, que es lo unico
        # estable: la clave la elige el modelo y puede variar entre llamadas.
        firma = _normalizar_espacios(cita)
        if firma in vistos:
            continue
        vistos.add(firma)
        reqs.append(Requisito(clave_, cita,
                              tuple(str(v).strip() for v in valores if str(v).strip()),
                              "lugar" if d.get("tipo") == "lugar" else "texto"))

    for frase in detectar_remision(texto):
        avisos.append(f"este documento remite sus reglas a otro sitio: \"{frase}\"")

    return reqs, avisos
