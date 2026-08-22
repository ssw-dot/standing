"""El veredicto lo decide codigo determinista. El modelo solo lee y cita.

Esa division es todo el diseno. Un modelo al que le preguntas "¿es elegible?"
contesta que si o que no, siempre, porque contestar es lo que hace. Aqui el
modelo tiene un trabajo mas pequeno y mucho mas fiable: **encontrar los
requisitos y copiar la frase que los dice.** Comparar el perfil contra esos
requisitos es aritmetica, y la aritmetica no alucina.

## Los tres veredictos, y por que el tercero es el producto

    ELEGIBLE · NO_ELEGIBLE · NO_SE_PUEDE_SABER

Cualquier herramienta da los dos primeros. El tercero es el que hace falta,
porque los dos errores no cuestan lo mismo:

- Un **falso ELEGIBLE** se descubre solo: presentas, te rechazan, perdiste una
  tarde.
- Un **falso NO_ELEGIBLE** no se descubre nunca. La persona no se presenta, no
  hay carta de rechazo, no hay nada que revisar. Se pierde el dinero y no queda
  rastro de que se perdio.

Por eso la regla que ordena el fichero: **ante la duda, nunca hacia la
exclusion.** Si un requisito no se puede evaluar con lo que hay escrito, no
excluye: se marca y se devuelve la decision a la persona.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Veredicto(str, Enum):
    ELEGIBLE = "ELEGIBLE"
    NO_ELEGIBLE = "NO_ELEGIBLE"
    NO_SE_PUEDE_SABER = "NO_SE_PUEDE_SABER"


@dataclass(frozen=True)
class Requisito:
    """Una condicion sacada del documento, con la frase que la dice.

    `cita` no es un adorno para el informe: es la unica prueba de que el
    requisito estaba en el documento y no lo invento el modelo. Un requisito sin
    cita se descarta antes de llegar al veredicto.
    """
    clave: str
    cita: str
    valores: tuple[str, ...] = ()
    tipo: str = "texto"          # "texto" | "lugar"

    def __post_init__(self):
        if not self.clave.strip():
            raise ValueError("requisito sin clave")
        if not self.cita.strip():
            raise ValueError(f"requisito '{self.clave}' sin cita del documento")


@dataclass(frozen=True)
class Comprobacion:
    requisito: Requisito
    cumple: bool | None          # None = no se puede saber con lo que hay
    motivo: str


@dataclass
class Resultado:
    veredicto: Veredicto
    comprobaciones: list[Comprobacion] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)

    @property
    def bloqueantes(self) -> list[Comprobacion]:
        return [c for c in self.comprobaciones if c.cumple is False]

    @property
    def dudosas(self) -> list[Comprobacion]:
        return [c for c in self.comprobaciones if c.cumple is None]


def normalizar(texto: str, plural: bool = True) -> str:
    """Minusculas, sin acentos, sin plural, sin puntuacion de sobra.

    Existe por un fallo concreto: un cribado dijo NO ELEGIBLE a una biblioteca
    porque el documento decia "nonprofit organisations" y el perfil decia
    "nonprofit". Comparar cadenas crudas le dijo a una biblioteca que no pidiera
    un fondo escrito para bibliotecas.
    """
    import unicodedata
    t = unicodedata.normalize("NFKD", texto.strip().lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = "".join(c if c.isalnum() or c.isspace() else " " for c in t)
    if not plural:
        return " ".join(t.split())
    palabras = []
    for p in t.split():
        # Plural ingles y espanol, en ese orden: "organisations" -> "organisation"
        for suf in ("es", "s"):
            if len(p) > 4 and p.endswith(suf):
                p = p[: -len(suf)]
                break
        palabras.append(p)
    return " ".join(palabras)


def coincide(valor: str, admitidos: tuple[str, ...]) -> bool:
    """¿El valor del perfil encaja con alguno de los admitidos?

    Encaja tambien cuando uno contiene al otro, ya normalizados: "nonprofit"
    contra "nonprofit organisation" es la misma cosa dicha con mas palabras.
    """
    v = normalizar(valor)
    if not v:
        return False
    for a in admitidos:
        n = normalizar(a)
        if not n:
            continue
        if v == n or v in n.split() or n in v.split():
            return True
        if f" {v} " in f" {n} " or f" {n} " in f" {v} ":
            return True
    return False


def comprobar(req: Requisito, perfil: dict[str, object]) -> Comprobacion:
    """Compara UN requisito contra el perfil. Sin modelo, sin red."""
    if req.clave not in perfil:
        return Comprobacion(req, None,
                            f"el perfil no dice nada sobre '{req.clave}'")
    if not req.valores:
        return Comprobacion(req, None,
                            "el documento enuncia el requisito pero no dice "
                            "que valores acepta")

    bruto = perfil[req.clave]
    # Una cadena es UN valor, no una lista de letras. Iterar "MX" y comparar
    # "M" y "X" contra los admitidos da un no-elegible silencioso, y es el fallo
    # mas caro que hemos tenido: un cribado que deberia excluir, absolvia.
    valores = list(bruto) if isinstance(bruto, (list, tuple, set)) else [bruto]
    valores = [str(v) for v in valores if str(v).strip()]
    if not valores:
        return Comprobacion(req, None, f"'{req.clave}' esta vacio en el perfil")

    if req.tipo == "lugar":
        return _comprobar_lugar(req, valores)

    # Un umbral se detecta por su forma, no por lo que diga el modelo. Si el
    # documento dice "at least two years", eso no es una lista de valores
    # admitidos y compararlo como texto solo puede dar un no-elegible falso.
    # Este control va ANTES del comparador de texto para que ese camino no se
    # pueda tomar por accidente.
    umbral = _umbral_de(req.valores)
    if umbral is not None:
        return _comprobar_cantidad(req, valores, umbral)

    encajan = [v for v in valores if coincide(v, req.valores)]
    if encajan:
        return Comprobacion(req, True,
                            f"'{encajan[0]}' encaja con {list(req.valores)}")
    return Comprobacion(req, False,
                        f"{valores} no encaja con ninguno de {list(req.valores)}")


def _comprobar_lugar(req: Requisito, valores: list[str]) -> Comprobacion:
    """Lugares por codigo, y lo que no se resuelve NO excluye.

    "MX" y "Mexico" son el mismo pais; compararlos como texto da que no y
    excluye a quien si podia presentarse. Pero si el documento dice "Europe" o
    "Quebec", el mapa no puede afirmar nada — y entonces la respuesta correcta
    es no saber, nunca excluir. Un lugar sin resolver que se tratara como
    incumplimiento convertiria cada laguna del mapa en un rechazo.
    """
    from .lugares import es_region, resolver

    admitidos, sin_resolver = set(), []
    for a in req.valores:
        c = resolver(a)
        (admitidos.add(c) if c else sin_resolver.append(a))

    mios = [(v, resolver(v)) for v in valores]

    for v, c in mios:
        if c and c in admitidos:
            return Comprobacion(req, True, f"'{v}' ({c}) esta en la lista")

    if sin_resolver:
        que = ", ".join(f"'{x}'" for x in sin_resolver)
        como = " ".join(f"{x} es una region o territorio, no un pais;"
                        for x in sin_resolver if es_region(x))
        return Comprobacion(req, None,
                            f"el documento admite {que} y no se puede afirmar "
                            f"si incluye {valores}. {como}".strip())

    if any(c is None for _, c in mios):
        crudos = [v for v, c in mios if c is None]
        return Comprobacion(req, None,
                            f"no se reconoce {crudos} como pais; no se excluye "
                            f"por no saber")

    return Comprobacion(req, False,
                        f"{[c for _, c in mios]} no esta entre "
                        f"{sorted(admitidos)}")


def decidir(requisitos: list[Requisito], perfil: dict[str, object],
            *, remite: bool = False) -> Resultado:
    """El veredicto entero.

    Orden de precedencia, y no es arbitrario:

    1. Sin requisitos -> NO_SE_PUEDE_SABER. Que no se haya podido leer el
       documento no es una autorizacion para presentarse.
    2. Algun requisito incumplido -> NO_ELEGIBLE. Un incumplimiento claro manda
       sobre cualquier duda: si el documento dice "solo Alemania" y el perfil
       dice Mexico, da igual lo demas.
    3. Alguna duda -> NO_SE_PUEDE_SABER, con las dudas listadas.
    4. Todo comprobado y cumplido -> ELEGIBLE.
    """
    res = Resultado(Veredicto.NO_SE_PUEDE_SABER)

    validos = []
    for r in requisitos:
        if not r.cita.strip():
            res.avisos.append(f"descartado '{r.clave}': sin cita del documento")
            continue
        validos.append(r)

    if not validos:
        res.avisos.append(
            "no se extrajo ningun requisito con cita. Puede que el documento no "
            "los enuncie, o que no se haya podido leer: son cosas distintas y "
            "esto no distingue entre ellas.")
        return res

    res.comprobaciones = [comprobar(r, perfil) for r in validos]

    if res.bloqueantes:
        res.veredicto = Veredicto.NO_ELEGIBLE
    elif res.dudosas:
        res.veredicto = Veredicto.NO_SE_PUEDE_SABER
    else:
        res.veredicto = Veredicto.ELEGIBLE

    # Un documento que remite sus reglas a otro no puede excluir a nadie.
    #
    # Salio de una convocatoria real de Horizon Europe. Su texto dice que "the
    # General Annexes... set out the general conditions... such as eligibility
    # rules", y aun asi el sistema saco un NO_ELEGIBLE de un parentesis suelto
    # que enumeraba a quien se le pedia un plan de igualdad. Un parentesis no es
    # la lista de quien puede presentarse, y sobre todo: las reglas de verdad
    # estaban en un documento que nadie habia leido.
    #
    # Excluir a partir de un documento que se declara incompleto es la peor
    # version del fallo que este sistema existe para evitar, porque ademas
    # parece fundada: hay una cita, hay una comparacion, hay un motivo. Todo
    # correcto salvo que la fuente no era la fuente.
    #
    # ELEGIBLE no se toca: un "cumples lo que este documento pide" sigue siendo
    # cierto, y el que se equivoca por ahi lo descubre al presentarse.
    if remite and res.veredicto is Veredicto.NO_ELEGIBLE:
        res.veredicto = Veredicto.NO_SE_PUEDE_SABER
        res.avisos.append(
            "habia un requisito incumplido, pero este documento remite sus "
            "reglas de elegibilidad a otro. No se excluye a nadie con un "
            "documento que se declara incompleto: hay que leer el anexo al que "
            "remite antes de decidir.")
    return res


def _umbral_de(valores: tuple[str, ...]):
    """El primer umbral que se lea entre los valores admitidos, o None."""
    from .cantidades import leer_umbral
    for v in valores:
        u = leer_umbral(v)
        if u is not None:
            return u
    return None


def _comprobar_cantidad(req: Requisito, valores: list[str], umbral
                        ) -> Comprobacion:
    """Compara contra un umbral. Lo que no se pueda leer es duda.

    Aqui no se excluye nunca por no entender. Si el perfil dice "cuatro anos y
    medio" y el lector de numeros no lo saca, la respuesta es que no se sabe —
    no que incumple. Excluir por un fallo del parser seria convertir una
    limitacion nuestra en un rechazo suyo.
    """
    from .cantidades import cumple, leer_medida

    for v in valores:
        m = leer_medida(v)
        if m is None:
            continue
        ok, motivo = cumple(umbral, m)
        if ok is None:
            return Comprobacion(req, None, motivo)
        return Comprobacion(req, ok, motivo)

    return Comprobacion(req, None,
                        f"el documento pide un minimo o maximo y en tu perfil "
                        f"{valores} no se encuentra ninguna cantidad que "
                        f"comparar")
