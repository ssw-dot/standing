"""Standing: ¿puedo presentarme a esto?

    python -m standing convocatoria.pdf --perfil perfil.json --salida informe.pdf

Los cuatro pasos, y cada uno puede fallar de forma distinta:

    1. Nutrient DWS   PDF  -> texto (con OCR si esta escaneado)
    2. Gemini         texto -> requisitos, cada uno con su cita literal
    3. codigo         requisitos + perfil -> veredicto        <- aqui no hay modelo
    4. SerpApi        contexto con enlace para lo que quedo en duda
    5. Foxit          informe -> PDF

El paso 3 es el unico que decide, y es el unico sin red ni modelo.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .agente import extraer_requisitos
from .busqueda import buscar
from .documento import extraer
from .informe import html_a_pdf
from .render import informe_html
from .veredicto import Veredicto, decidir

SALIDA = {Veredicto.ELEGIBLE: 0, Veredicto.NO_ELEGIBLE: 1,
          Veredicto.NO_SE_PUEDE_SABER: 2}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="standing", description=__doc__)
    ap.add_argument("pdf", type=Path)
    ap.add_argument("--perfil", type=Path, required=True,
                    help="JSON con tus datos: pais, tipo_de_entidad, etc.")
    ap.add_argument("--salida", type=Path, default=Path("informe.pdf"))
    ap.add_argument("--sin-ocr", action="store_true",
                    help="ahorra creditos si el PDF ya tiene capa de texto")
    ap.add_argument("--sin-contexto", action="store_true",
                    help="no consultar SerpApi para las dudas")
    ap.add_argument("--texto", action="store_true",
                    help="solo por consola, sin generar PDF")
    a = ap.parse_args(argv)

    if not a.pdf.exists():
        print(f"no existe {a.pdf}", file=sys.stderr)
        return 3
    perfil = json.loads(a.perfil.read_text(encoding="utf-8"))

    print(f"[1/5] leyendo {a.pdf.name}...", flush=True)
    doc = extraer(a.pdf, ocr=not a.sin_ocr)
    if doc.parece_vacio:
        print("      AVISO: apenas se extrajo texto. Puede ser un PDF "
              "escaneado sin OCR, o una portada.", file=sys.stderr)

    print("[2/5] localizando requisitos...", flush=True)
    reqs, avisos = extraer_requisitos(doc.texto)
    print(f"      {len(reqs)} requisitos con cita verificada")

    remite = any(a.startswith("este documento remite") for a in avisos)
    if remite:
        print("      AVISO: el documento remite sus reglas a otro documento",
              flush=True)

    print("[3/5] comparando contra tu perfil...", flush=True)
    res = decidir(reqs, perfil, remite=remite)
    res.avisos.extend(avisos)
    if doc.parece_vacio:
        res.avisos.append(
            "del documento se extrajeron menos de 200 caracteres. Si estaba "
            "escaneado, los requisitos reales pueden no haberse leido: este "
            "veredicto podria basarse en un documento vacio.")

    contexto = {}
    if res.dudosas and not a.sin_contexto:
        print(f"[4/5] buscando contexto para {len(res.dudosas)} dudas...",
              flush=True)
        for c in res.dudosas[:3]:      # tope: 250 busquedas al mes en el plan gratis
            try:
                contexto[c.requisito.clave] = buscar(
                    f"{c.requisito.cita[:110]} eligibility", n=2)
            except Exception as e:
                res.avisos.append(f"sin contexto para '{c.requisito.clave}': {e}")

    print(f"\n  {res.veredicto.value}\n")
    for c in res.comprobaciones:
        marca = {True: "si ", False: "NO ", None: " ? "}[c.cumple]
        print(f"  [{marca}] {c.requisito.clave}: {c.motivo}")
    for w in res.avisos:
        print(f"  aviso: {w}")

    if not a.texto:
        print(f"\n[5/5] generando {a.salida}...", flush=True)
        html_a_pdf(informe_html(res, fuente=a.pdf.name, perfil=perfil,
                                contexto=contexto), a.salida)
        print(f"      {a.salida} ({a.salida.stat().st_size // 1024} KB)")

    return SALIDA[res.veredicto]


if __name__ == "__main__":
    raise SystemExit(main())
