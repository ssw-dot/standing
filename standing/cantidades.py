"""Umbrales: "al menos dos anos" no es una opcion, es una condicion.

Este fichero existe por un fallo concreto, encontrado ejecutando el sistema
entero contra una convocatoria real:

    requisito: "Organisations must have been operating for at least two years"
    perfil:    "4 years"
    veredicto: NO_ELEGIBLE   <- mal

Cuatro anos cumple "al menos dos". El comparador de texto no podia saberlo
porque estaba tratando "at least two years" como si fuera un valor admitido de
una lista, y "4 years" no es esa cadena. Es el error caro: un falso
NO_ELEGIBLE, el que hace que alguien no se presente y no se entere nunca.

## La regla que se saca de ahi

**Una frase con umbral no es una enumeracion.** Cuando los valores admitidos
son una condicion y no un conjunto —"al menos", "no mas de", "minimo"—, no se
puede excluir por no coincidir, porque no hay nada con lo que coincidir.

Asi que aqui hay dos salidas, no tres:

- Se puede leer el umbral y el numero  ->  se compara de verdad
- No se puede leer alguno de los dos   ->  duda, nunca exclusion
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# Numeros escritos con letra: aparecen en convocatorias mas de lo que uno
# espera ("at least two years", "un minimo de tres empleados").
PALABRAS = {
    "zero": 0, "cero": 0, "one": 1, "un": 1, "uno": 1, "una": 1,
    "two": 2, "dos": 2, "three": 3, "tres": 3, "four": 4, "cuatro": 4,
    "five": 5, "cinco": 5, "six": 6, "seis": 6, "seven": 7, "siete": 7,
    "eight": 8, "ocho": 8, "nine": 9, "nueve": 9, "ten": 10, "diez": 10,
    "eleven": 11, "once": 11, "twelve": 12, "doce": 12,
    "fifteen": 15, "quince": 15, "twenty": 20, "veinte": 20,
    "fifty": 50, "cincuenta": 50, "hundred": 100, "cien": 100,
}

# Cada patron mapea a un operador. El orden importa: "no more than" contiene
# "more than", asi que las formas negativas van primero o se leen al reves y el
# umbral se invierte — que es como un "maximo de 5" se convierte en "minimo 5".
MINIMO = ("at least", "minimum of", "minimum", "no fewer than", "not less than",
          "or more", "al menos", "un minimo de", "minimo de", "minimo",
          "no menos de", "o mas", "mas de", "over", "more than", "at minimum")
MAXIMO = ("no more than", "not more than", "at most", "maximum of", "maximum",
          "no greater than", "up to", "fewer than", "less than", "under",
          "no mas de", "un maximo de", "maximo de", "maximo", "hasta",
          "menos de", "o menos", "or less")

# Unidades que se pueden comparar entre si. Comparar anos con empleados es un
# error, y callarselo seria peor que no comparar.
UNIDADES = {
    "year": "anos", "years": "anos", "yr": "anos", "yrs": "anos",
    "ano": "anos", "anos": "anos", "año": "anos", "años": "anos",
    "month": "meses", "months": "meses", "mes": "meses", "meses": "meses",
    "employee": "personas", "employees": "personas", "staff": "personas",
    "empleado": "personas", "empleados": "personas", "persona": "personas",
    "personas": "personas", "people": "personas", "member": "personas",
    "members": "personas", "miembro": "personas", "miembros": "personas",
    "usd": "dinero", "eur": "dinero", "mxn": "dinero", "dollar": "dinero",
    "dollars": "dinero", "euro": "dinero", "euros": "dinero",
    "peso": "dinero", "pesos": "dinero",
}


@dataclass(frozen=True)
class Umbral:
    operador: str          # ">=" | "<="
    valor: float
    unidad: str | None


@dataclass(frozen=True)
class Medida:
    valor: float
    unidad: str | None


# "un", "una", "uno" son articulo mucho mas a menudo que numero. En "un minimo
# de tres empleados" el numero es tres, y leer "un" da 1: un umbral de tres
# empleados se queda en uno y deja pasar a quien no cumple.
AMBIGUAS = {"un", "uno", "una", "one"}


def _numero(texto: str) -> float | None:
    """El numero de la frase. Mandan los digitos; las palabras ambiguas van
    las ultimas.

    Se recorre por posicion en la frase y no por orden del diccionario: en
    "minimo de tres" hay que leer "tres" aunque "diez" estuviera antes en la
    tabla.
    """
    t = texto.lower().replace(",", "")
    m = re.search(r"\d+(?:\.\d+)?", t)
    if m:
        return float(m.group())

    encontradas = [p for p in re.findall(r"[a-zñáéíóú]+", t) if p in PALABRAS]
    for palabra in encontradas:
        if palabra not in AMBIGUAS:
            return float(PALABRAS[palabra])
    return float(PALABRAS[encontradas[0]]) if encontradas else None


def _unidad(texto: str) -> str | None:
    t = re.sub(r"[^a-zñáéíóú ]", " ", texto.lower())
    for p in t.split():
        if p in UNIDADES:
            return UNIDADES[p]
    return None


def leer_umbral(texto: str) -> Umbral | None:
    """"at least two years" -> Umbral(">=", 2, "anos"). None si no hay umbral.

    Devolver None no es un fallo: significa que la frase es una enumeracion y
    no una condicion, y entonces le toca al comparador de texto.
    """
    t = " " + re.sub(r"[^a-z0-9ñáéíóú ]", " ", texto.lower()) + " "
    t = re.sub(r"\s+", " ", t)

    # Las formas de maximo se buscan primero: varias contienen una de minimo
    # dentro ("no more than" contiene "more than"), y leerlo al reves convierte
    # un techo en un suelo.
    op = None
    for frase in MAXIMO:
        if f" {frase} " in t:
            op = "<="
            break
    if op is None:
        for frase in MINIMO:
            if f" {frase} " in t:
                op = ">="
                break
    if op is None:
        return None

    n = _numero(texto)
    if n is None:
        return None
    return Umbral(op, n, _unidad(texto))


def leer_medida(texto: str) -> Medida | None:
    n = _numero(texto)
    return None if n is None else Medida(n, _unidad(texto))


def cumple(umbral: Umbral, medida: Medida) -> tuple[bool | None, str]:
    """Devuelve (cumple, motivo). `None` = no se puede comparar.

    Unidades distintas dan None y no False. Comparar "4 anos" contra "minimo 3
    empleados" y responder que no cumple seria inventarse una conclusion con la
    forma de un calculo.
    """
    if umbral.unidad and medida.unidad and umbral.unidad != medida.unidad:
        return None, (f"el documento habla de {umbral.unidad} y tu perfil de "
                      f"{medida.unidad}: no son comparables")

    signo = "al menos" if umbral.operador == ">=" else "como mucho"
    unidad = umbral.unidad or medida.unidad or ""
    ok = (medida.valor >= umbral.valor if umbral.operador == ">="
          else medida.valor <= umbral.valor)
    return ok, (f"{medida.valor:g} {unidad} contra {signo} "
                f"{umbral.valor:g} {unidad}".replace("  ", " ").strip())
