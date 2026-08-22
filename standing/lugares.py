"""Resolver nombres de pais a un codigo, y saber cuando NO se puede.

La funcion importante no es la que resuelve: es la que admite que no sabe.

"MX" y "Mexico" son el mismo pais y compararlos como cadenas da que no. Ese
fallo excluye a alguien que si podia presentarse, y no deja rastro. Pero el
arreglo ingenuo —un diccionario grande— trae uno peor: "Quebec" se parece a
"Canada" y no es un pais. Si el mapa adivina, el veredicto se vuelve una
opinion disfrazada de dato.

Por eso `resolver` devuelve `None` cuando no esta segura, y el veredicto trata
ese `None` como duda y no como exclusion.
"""
from __future__ import annotations

# Solo lo que se puede afirmar. Ampliar la tabla es seguro; adivinar no.
_PAISES = {
    "mexico": "MX", "mx": "MX", "mex": "MX", "estados unidos mexicanos": "MX",
    "united states": "US", "usa": "US", "us": "US", "u s a": "US",
    "united states of america": "US", "estados unidos": "US",
    "canada": "CA", "ca": "CA", "can": "CA",
    "colombia": "CO", "co": "CO", "col": "CO",
    "argentina": "AR", "ar": "AR", "arg": "AR",
    "brasil": "BR", "brazil": "BR", "br": "BR", "bra": "BR",
    "chile": "CL", "cl": "CL", "chl": "CL",
    "peru": "PE", "pe": "PE", "per": "PE",
    "espana": "ES", "spain": "ES", "es": "ES", "esp": "ES",
    "france": "FR", "francia": "FR", "fr": "FR", "fra": "FR",
    "germany": "DE", "alemania": "DE", "de": "DE", "deu": "DE", "ger": "DE",
    "united kingdom": "GB", "uk": "GB", "gb": "GB", "gbr": "GB",
    "great britain": "GB", "reino unido": "GB",
    "india": "IN", "in": "IN", "ind": "IN",
    "japan": "JP", "japon": "JP", "jp": "JP", "jpn": "JP",
    "guatemala": "GT", "gt": "GT", "honduras": "HN", "hn": "HN",
    "costa rica": "CR", "cr": "CR", "panama": "PA", "pa": "PA",
    "ecuador": "EC", "ec": "EC", "bolivia": "BO", "bo": "BO",
    "uruguay": "UY", "uy": "UY", "paraguay": "PY", "py": "PY",
    "venezuela": "VE", "ve": "VE", "cuba": "CU", "cu": "CU",
    "republica dominicana": "DO", "dominican republic": "DO", "do": "DO",
    "puerto rico": "PR", "pr": "PR", "el salvador": "SV", "sv": "SV",
    "nicaragua": "NI", "ni": "NI", "portugal": "PT", "pt": "PT",
    "italy": "IT", "italia": "IT", "it": "IT", "ita": "IT",
    "netherlands": "NL", "nl": "NL", "nld": "NL",
    "australia": "AU", "au": "AU", "aus": "AU",
    "nigeria": "NG", "ng": "NG", "kenya": "KE", "ke": "KE",
    "south africa": "ZA", "za": "ZA", "sudafrica": "ZA",
}

# Lo que parece pais y no lo es. Sin esta lista, "Quebec" acabaria en "CA" por
# parecido y el veredicto seria una adivinanza con cara de dato.
_NO_SON_PAISES = {
    "quebec", "ontario", "california", "texas", "new york", "florida",
    "catalunya", "cataluna", "catalonia", "euskadi", "pais vasco",
    "scotland", "escocia", "wales", "gales", "england", "inglaterra",
    "bavaria", "baviera", "jalisco", "nuevo leon", "yucatan", "chiapas",
    "cdmx", "ciudad de mexico", "mexico city", "distrito federal",
    "europe", "europa", "latam", "latinoamerica", "latin america",
    "north america", "norteamerica", "africa", "asia", "eu",
    "union europea", "european union", "worldwide", "global", "any country",
}


def resolver(nombre: str) -> str | None:
    """Codigo de dos letras, o None cuando no se puede afirmar.

    Sin quitar plurales, y esa linea es una correccion: quitarlos convierte
    "United States" en "united state" y el pais deja de existir. Los nombres de
    pais son nombres propios; la regla del plural, que arregla
    "organisations"/"organisation", aqui rompe. La misma normalizacion no vale
    para las dos cosas.
    """
    from .veredicto import normalizar
    n = normalizar(nombre, plural=False)
    if not n:
        return None
    if n in _NO_SON_PAISES:
        return None
    return _PAISES.get(n)


def es_region(nombre: str) -> bool:
    """¿Es algo que suena a sitio pero no es un pais concreto?

    Se separa de `resolver` porque las dos respuestas son distintas: "Quebec"
    es un sitio que no sabemos mapear, y "asdfgh" es que el modelo se equivoco.
    Al informe le importa la diferencia; al veredicto no, las dos son duda.
    """
    from .veredicto import normalizar
    return normalizar(nombre, plural=False) in _NO_SON_PAISES
