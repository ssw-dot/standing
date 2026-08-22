#!/usr/bin/env python3
"""Los tres veredictos, sin red y sin credenciales.

    python demo.py

Existe para que cualquiera —un jurado, sobre todo— pueda ver que hace esto en
diez segundos sin dar de alta cuatro cuentas. Lo que se ejecuta aqui es el
mismo `decidir()` que usa el sistema completo; lo unico que falta es de donde
salen los requisitos, que en el sistema real los saca un modelo del PDF.
"""
from __future__ import annotations

import sys

from standing.veredicto import Requisito, Veredicto, decidir

VERDE, ROJO, AMBAR, GRIS, FIN = (
    "\033[92m", "\033[91m", "\033[93m", "\033[90m", "\033[0m")
COLOR = {Veredicto.ELEGIBLE: VERDE, Veredicto.NO_ELEGIBLE: ROJO,
         Veredicto.NO_SE_PUEDE_SABER: AMBAR}
MARCA = {True: f"{VERDE}si {FIN}", False: f"{ROJO}NO {FIN}",
         None: f"{AMBAR} ? {FIN}"}

CASOS = [
    ("Encaja aunque el documento lo diga con mas palabras",
     [Requisito("tipo_de_entidad",
                "Open to nonprofit organisations.",
                ("nonprofit organisations",)),
      Requisito("pais",
                "Applicants must be based in Mexico, Colombia or Peru.",
                ("Mexico", "Colombia", "Peru"), "lugar"),
      Requisito("antiguedad",
                "Organisations must have been operating for at least two years.",
                ("at least two years",))],
     {"tipo_de_entidad": "nonprofit", "pais": "MX", "antiguedad": "4 years"}),

    ("Un incumplimiento claro sigue siendo un no",
     [Requisito("pais",
                "This call is open to organisations based in Germany or France.",
                ("Germany", "France"), "lugar")],
     {"pais": "MX"}),

    ("Una region no es un pais: no se adivina",
     [Requisito("pais",
                "Applicants must be established in Europe.",
                ("Europe",), "lugar")],
     {"pais": "MX"}),

    ("El documento pide algo y no dice cuanto",
     [Requisito("gobernanza",
                "Applicants must comply with our governance standards.",
                ())],
     {"gobernanza": "consejo de cinco miembros"}),

    ("Anos contra empleados no son comparables",
     [Requisito("tamano",
                "Organisations must employ a minimum of three people.",
                ("minimum of three people",))],
     {"tamano": "4 years"}),

    ("Un documento ilegible no autoriza nada",
     [], {"pais": "MX"}),
]


def main() -> int:
    print()
    for titulo, reqs, perfil in CASOS:
        r = decidir(reqs, perfil)
        c = COLOR[r.veredicto]
        print(f"  {GRIS}{titulo}{FIN}")
        print(f"  {c}{r.veredicto.value}{FIN}")
        for comp in r.comprobaciones:
            print(f"    [{MARCA[comp.cumple]}] {comp.requisito.clave}: "
                  f"{comp.motivo}")
            print(f"          {GRIS}\"{comp.requisito.cita}\"{FIN}")
        for a in r.avisos:
            print(f"    {GRIS}aviso: {a}{FIN}")
        print()

    print(f"  {GRIS}Cuatro de los seis casos son dudas, no rechazos. Esa es la"
          f" diferencia.{FIN}")
    print(f"  {GRIS}Un falso 'no elegible' no deja rastro: la persona no se"
          f" presenta y nadie se entera.{FIN}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
