"""SerpApi: comprobar fuera lo que el documento no dice dentro.

Para que sirve de verdad. Una convocatoria dice "abierto a organizaciones sin
animo de lucro registradas en el pais del solicitante" y no dice cuales son. El
modelo, si le preguntas, se inventa una respuesta plausible. Buscarlo devuelve
enlaces reales que se pueden citar, o no devuelve nada — y no devolver nada es
una respuesta valida que el modelo nunca da.

Regla que gobierna este fichero: **un resultado de busqueda no decide un
veredicto.** Aporta contexto con enlace para que lo juzgue una persona. Lo que
decide es el documento.
"""
from __future__ import annotations

import urllib.parse
from dataclasses import dataclass

from .red import cargar_env, clave, json_de, peticion


@dataclass(frozen=True)
class Hallazgo:
    titulo: str
    fragmento: str
    enlace: str


def buscar(consulta: str, *, n: int = 4) -> list[Hallazgo]:
    cargar_env()
    q = urllib.parse.urlencode({"q": consulta, "num": n, "engine": "google",
                                "api_key": clave("SERPAPI_KEY")})
    d = json_de(peticion(f"https://serpapi.com/search.json?{q}"))
    return [Hallazgo(r.get("title", ""), r.get("snippet", ""), r.get("link", ""))
            for r in d.get("organic_results", [])[:n]]


def saldo() -> dict:
    """Cuantas busquedas quedan. 250 al mes en el plan gratis.

    Se consulta antes de una tanda: quedarse sin cuota a mitad de un cribado
    deja un informe a medias que parece completo.
    """
    cargar_env()
    q = urllib.parse.urlencode({"api_key": clave("SERPAPI_KEY")})
    return json_de(peticion(f"https://serpapi.com/account.json?{q}"))
