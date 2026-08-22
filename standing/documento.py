"""Nutrient DWS: de un PDF al texto que hay dentro, con OCR si hace falta.

Por que Nutrient y no una libreria local: una convocatoria escaneada es un PDF
sin capa de texto, y una libreria local devuelve cadena vacia sin avisar. Eso
seria el peor fallo posible aqui — un documento ilegible produciria "no se
encontro ningun requisito", que este sistema traduce a NO_SE_PUEDE_SABER. Con
OCR de por medio, la diferencia entre "no dice nada" y "no se pudo leer" deja de
ser invisible.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .red import cargar_env, clave, json_de, multipart, peticion

BASE = "https://api.nutrient.io"


@dataclass
class Extraido:
    texto: str
    paginas: int
    con_ocr: bool

    @property
    def parece_vacio(self) -> bool:
        """Menos de 200 caracteres en un PDF de convocatoria es sospechoso.

        No se lanza excepcion: se marca. Un documento casi vacio puede ser real
        (una pagina de portada) y decidir por el usuario que su fichero no vale
        es el mismo error que decidir que no es elegible.
        """
        return len(self.texto.strip()) < 200


def extraer(pdf: Path, *, ocr: bool = True) -> Extraido:
    """PDF -> texto. Salida `json-content`, que es la que devuelve texto plano.

    Comprobado contra la API: `plain-text` y `text` no existen como tipos de
    salida y devuelven 400 con `failingPaths`. `json-content` con `plainText`
    si, y ademas trae el texto separado por paginas, asi que el numero de
    paginas es un dato leido y no una cuenta de saltos de pagina.
    """
    cargar_env()
    instrucciones = {"parts": [{"file": "documento"}],
                     "output": {"type": "json-content", "plainText": True}}
    if ocr:
        instrucciones["parts"][0]["actions"] = [{"type": "ocr",
                                                 "language": "english"}]

    cuerpo, tipo = multipart(
        {"instructions": json.dumps(instrucciones)},
        {"documento": (pdf.name, pdf.read_bytes(), "application/pdf")})

    d = json_de(peticion(f"{BASE}/build", datos=cuerpo, metodo="POST", cabeceras={
        "Authorization": f"Bearer {clave('NUTRIENT_KEY')}", "Content-Type": tipo}))
    paginas = d.get("pages") or []
    texto = (chr(10) * 2).join(p.get("plainText", "") for p in paginas)
    return Extraido(texto=texto, paginas=len(paginas), con_ocr=ocr)


def creditos() -> dict:
    """Cuantos creditos quedan. El plan gratis trae 50 y cada extraccion gasta.

    Se mira antes de una tanda: quedarse a cero a mitad deja informes que
    parecen completos y no lo son.
    """
    cargar_env()
    return json_de(peticion(f"{BASE}/account/info", cabeceras={
        "Authorization": f"Bearer {clave('NUTRIENT_KEY')}"}))
