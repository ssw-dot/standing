"""Xano: el registro de lo que decidiste NO pedir.

Este fichero es la tesis del producto llevada a su conclusion.

Standing existe porque los dos errores no cuestan lo mismo: un falso "elegible"
se descubre solo —presentas, te rechazan— y un falso "no elegible" no se
descubre nunca. Pero **¿por que no se descubre nunca?**

Porque nadie guarda registro de aquello a lo que no se presento. Las
candidaturas enviadas dejan rastro: un expediente, un acuse, una carta. Las que
no se enviaron no dejan nada. No hay carpeta de "convocatorias que descarte", y
por eso no hay forma de volver sobre ellas.

El PDF resuelve eso para un cribado. Esto lo resuelve para la organizacion:

    ¿Que convocatorias cribamos este trimestre?
    ¿A cuales decidimos no presentarnos, y con que frase del documento?
    ¿Cuantas quedaron en duda y nadie volvio a mirarlas?

Esa ultima pregunta es la que no se puede hacer hoy en ningun sitio.

## Dos reglas

**Guardar nunca bloquea el veredicto.** Si Xano no responde, el cribado ya se
hizo y el informe ya vale. Se avisa y se sigue: perder el registro es malo,
perder el trabajo por no poder registrarlo es peor.

**Se guarda la evidencia, no solo el veredicto.** Una fila que dijera
`NO_ELEGIBLE` y nada mas no serviria para auditar nada: haria falta volver a
correrlo para saber por que. Se guardan las citas.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone

from .red import cargar_env, json_de, peticion
from .veredicto import Resultado

TABLA = "cribados"


class SinXano(RuntimeError):
    pass


def base_url() -> str:
    """La URL del grupo de API de Xano, del .env.

    No hay valor por defecto a proposito: una URL inventada apuntaria al
    espacio de otra persona, y ahi lo que se escribe no se puede recuperar.
    """
    cargar_env()
    u = os.environ.get("XANO_URL", "").strip().rstrip("/")
    if not u:
        raise SinXano(
            "falta XANO_URL. Se copia del grupo de API en el panel de Xano y "
            "tiene la forma https://x8ab-cdef-1234.n7.xano.io/api:AbCdEf")
    return u


@dataclass(frozen=True)
class Entrada:
    """Una fila del historial. Lo que hace falta para auditar sin re-ejecutar."""

    documento: str
    veredicto: str
    cuando: str
    perfil: dict
    bloqueantes: list[dict]
    dudas: list[dict]
    avisos: list[str]

    def como_json(self) -> dict:
        # Las listas y dicts van serializados: Xano acepta campos de texto sin
        # que haya que declarar un esquema anidado en su panel, y eso hace que
        # la tabla se pueda crear con cuatro clics en vez de veinte.
        return {
            "documento": self.documento,
            "veredicto": self.veredicto,
            "cuando": self.cuando,
            "perfil": json.dumps(self.perfil, ensure_ascii=False),
            "bloqueantes": json.dumps(self.bloqueantes, ensure_ascii=False),
            "dudas": json.dumps(self.dudas, ensure_ascii=False),
            "avisos": json.dumps(self.avisos, ensure_ascii=False),
        }


def _citas(comprobaciones) -> list[dict]:
    """Cada comprobacion, con la frase del documento que la sostiene.

    Sin la cita, una fila del historial dice que pasó pero no por que, y
    entonces auditarla obliga a volver a ejecutar el cribado — que es
    exactamente lo que el historial venia a evitar.
    """
    return [{"requisito": c.requisito.clave,
             "motivo": c.motivo,
             "cita": c.requisito.cita} for c in comprobaciones]


def entrada_de(res: Resultado, *, documento: str, perfil: dict) -> Entrada:
    return Entrada(
        documento=documento,
        veredicto=res.veredicto.value,
        cuando=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        perfil=perfil,
        bloqueantes=_citas(res.bloqueantes),
        dudas=_citas(res.dudosas),
        avisos=list(res.avisos),
    )


def guardar(res: Resultado, *, documento: str, perfil: dict) -> tuple[bool, str]:
    """Guarda un cribado. Devuelve (se_guardo, nota). NUNCA lanza.

    No lanza porque quien llama ya tiene un veredicto valido en la mano. Que el
    registro falle es una perdida; que se pierda el cribado por no poder
    registrarlo seria un error de diseno.
    """
    e = entrada_de(res, documento=documento, perfil=perfil)
    try:
        url = base_url()
    except SinXano as x:
        return False, f"sin historial: {x}"

    try:
        d = json_de(peticion(f"{url}/{TABLA}",
                             datos=json.dumps(e.como_json()).encode(),
                             metodo="POST",
                             cabeceras={"Content-Type": "application/json"}))
    except Exception as x:                     # noqa: BLE001 — ver docstring
        return False, f"no se pudo guardar en el historial: {str(x)[:160]}"
    return True, f"guardado en el historial (id {d.get('id', '?')})"


def listar(limite: int = 50) -> list[dict]:
    """El historial. Aqui SI se lanza: quien lo pide, lo pide para leerlo."""
    url = base_url()
    return json_de(peticion(f"{url}/{TABLA}"))[:limite]


def resumen(filas: list[dict]) -> str:
    """El recuento que hace visible lo invisible."""
    if not filas:
        return "El historial esta vacio."

    cuenta: dict[str, int] = {}
    for f in filas:
        v = str(f.get("veredicto", "?"))
        cuenta[v] = cuenta.get(v, 0) + 1

    lineas = [f"{len(filas)} cribados guardados:"]
    for v in ("ELEGIBLE", "NO_ELEGIBLE", "NO_SE_PUEDE_SABER"):
        if cuenta.get(v):
            lineas.append(f"  {cuenta[v]:>4}  {v}")

    descartadas = cuenta.get("NO_ELEGIBLE", 0)
    dudosas = cuenta.get("NO_SE_PUEDE_SABER", 0)
    if descartadas or dudosas:
        lineas.append("")
        n = descartadas + dudosas
        lineas.append(
            (f"Hay 1 convocatoria a la que no te presentaste. Ese es "
             if n == 1 else
             f"A {n} convocatorias no te presentaste. Ese es ") +
            "el monton que en cualquier otro sitio no existe: las candidaturas "
            "enviadas dejan rastro y las descartadas no, y por eso un 'no "
            "elegible' equivocado no se descubre nunca. Aqui se puede volver "
            "sobre ellas.")
        if dudosas:
            lineas.append(
                f"La que queda en duda espera a una persona."
                if dudosas == 1 else
                f"Las {dudosas} en duda esperan a una persona.")
    return "\n".join(lineas)
