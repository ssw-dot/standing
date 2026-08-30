"""Extraccion local de texto: el plan B cuando Nutrient no responde.

Existe por una razon concreta y comprobada: con la clave sin creditos, este
programa moria con una traza de Python en el primer paso. Un jurado que lo
ejecute —y el reto dice que lo ejecutan— veria eso y nada mas. Un fallo de
cuota no es un fallo del proyecto, pero se lee igual.

## Por que esto NO sustituye a Nutrient

Este modulo es exactamente la libreria local que el README senala como
peligrosa. Lee la capa de texto de un PDF y punto: **ante un PDF escaneado
devuelve cadena vacia**, que es el peor fallo posible aqui, porque "no dice
nada" y "no se pudo leer" acaban siendo la misma cosa.

Por eso el respaldo **avisa en voz alta y el aviso viaja hasta el informe**. La
diferencia con la libreria local del README no es tecnica, es que aqui el
sistema sabe que esta usando el plan B y lo dice. Un respaldo silencioso seria
peor que no tenerlo.

## Alcance, medido y no prometido

Sin dependencias: `zlib` y expresiones regulares sobre los flujos de contenido.
Cubre PDFs con capa de texto, compresion Flate y cadenas literales `(...) Tj`.

**Lo que NO cubre, comprobado contra `ejemplos/convocatoria.pdf`:** ese PDF usa
fuentes CID incrustadas, asi que su texto va como identificadores de glifo en
cadenas hexadecimales y solo se vuelve legible aplicando el `ToUnicode` CMap del
propio documento. Este respaldo no lo hace, y por eso ahi devuelve **cadena
vacia**. Tampoco hay OCR.

Eso no lo convierte en inutil, pero si define para que sirve: **es una red que
evita la traza de Python, no un sustituto de Nutrient.** Cuando no puede leer,
devuelve poco o nada, `parece_vacio` lo detecta, el aviso llega al informe y el
veredicto acaba en NO_SE_PUEDE_SABER — que es justo la respuesta correcta
cuando no se ha podido leer el documento.
"""
from __future__ import annotations

import re
import zlib
from pathlib import Path

# Operadores de texto de PDF: `(...) Tj` para una cadena y `[...] TJ` para un
# array con ajustes de kerning entre trozos.
RE_FLUJO = re.compile(rb"stream\r?\n(.*?)\r?\nendstream", re.S)
RE_TJ = re.compile(rb"\((?:\\.|[^\\()])*\)\s*Tj", re.S)
RE_TJ_ARRAY = re.compile(rb"\[(.*?)\]\s*TJ", re.S)
RE_CADENA = re.compile(rb"\((?:\\.|[^\\()])*\)", re.S)
RE_SALTO = re.compile(rb"\b(?:T\*|TD|Td|TL)\b")

ESCAPES = {b"\\n": b"\n", b"\\r": b"\r", b"\\t": b"\t", b"\\b": b"\b",
           b"\\f": b"\f", b"\\(": b"(", b"\\)": b")", b"\\\\": b"\\"}


def _sin_escapes(s: bytes) -> bytes:
    for k, v in ESCAPES.items():
        s = s.replace(k, v)
    # \\ddd octal
    return re.sub(rb"\\([0-7]{1,3})",
                  lambda m: bytes([int(m.group(1), 8) & 0xFF]), s)


def _cadena(bruto: bytes) -> str:
    return _sin_escapes(bruto[1:-1]).decode("latin-1", "replace")


def _texto_de_flujo(datos: bytes) -> str:
    """Saca el texto de un flujo de contenido ya descomprimido."""
    trozos: list[str] = []
    # Se recorre en orden de aparicion para no perder el orden de lectura: un
    # PDF puede alternar Tj sueltos y arrays TJ dentro del mismo parrafo.
    for m in re.finditer(rb"\((?:\\.|[^\\()])*\)\s*Tj|\[(?:.*?)\]\s*TJ|\bT\*",
                         datos, re.S):
        t = m.group(0)
        if t.endswith(b"T*"):
            trozos.append("\n")
        elif t.endswith(b"Tj"):
            trozos.append(_cadena(RE_CADENA.search(t).group(0)))
        else:
            trozos.append("".join(_cadena(c)
                                  for c in RE_CADENA.findall(t)))
    return "".join(trozos)


def texto_local(pdf: Path) -> str:
    """Todo el texto que se pueda sacar del PDF sin salir a la red."""
    crudo = pdf.read_bytes()
    partes: list[str] = []
    for m in RE_FLUJO.finditer(crudo):
        datos = m.group(1)
        try:
            datos = zlib.decompress(datos)
        except zlib.error:
            # Sin comprimir, o con un filtro que no manejamos. Se intenta igual:
            # un flujo de imagen simplemente no producira texto.
            pass
        try:
            partes.append(_texto_de_flujo(datos))
        except Exception:                          # noqa: BLE001
            # Un flujo ilegible no puede tumbar la extraccion entera: el resto
            # del documento puede ser perfectamente legible.
            continue
    texto = "\n".join(p for p in partes if p.strip())
    # Los PDFs suelen partir las lineas en trozos por kerning; se recomponen los
    # espacios multiples para que el modelo no vea palabras cortadas.
    return re.sub(r"[ \t]{2,}", " ", texto).strip()
