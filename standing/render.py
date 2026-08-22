"""El informe en HTML. Foxit lo convierte a PDF.

Regla de diseno: **la cita del documento pesa mas que el veredicto.** El
veredicto es una palabra; la cita es la prueba. Si alguien solo mira el titular
y no lee las citas, el informe ha fallado aunque el titular sea correcto.
"""
from __future__ import annotations

import html
from datetime import date

from .busqueda import Hallazgo
from .veredicto import Resultado, Veredicto

COLOR = {Veredicto.ELEGIBLE: ("#0b6b3a", "#e8f6ee"),
         Veredicto.NO_ELEGIBLE: ("#8a1c1c", "#fdecec"),
         Veredicto.NO_SE_PUEDE_SABER: ("#7a4b00", "#fff6e5")}

TITULO = {Veredicto.ELEGIBLE: "Cumples los requisitos que el documento enuncia",
          Veredicto.NO_ELEGIBLE: "Hay un requisito que no cumples",
          Veredicto.NO_SE_PUEDE_SABER: "No se puede decidir con este documento"}

BAJADA = {
    Veredicto.ELEGIBLE:
        "Todo requisito que el documento enuncia se ha podido comprobar y lo "
        "cumples. Esto no es una promesa de que te lo concedan: es que nada de "
        "lo escrito te deja fuera.",
    Veredicto.NO_ELEGIBLE:
        "Al menos un requisito te excluye de forma clara. Abajo esta la frase "
        "exacta del documento que lo dice, para que puedas comprobarla.",
    Veredicto.NO_SE_PUEDE_SABER:
        "Ningun requisito te excluye, pero hay condiciones que este documento "
        "no permite evaluar. La decision es tuya, y abajo esta exactamente que "
        "falta por saber.",
}

CSS = """
body{font:15px/1.65 -apple-system,Segoe UI,Roboto,sans-serif;color:#1a1a1a;
 margin:0;padding:40px 46px;max-width:760px}
h1{font-size:15px;letter-spacing:.14em;text-transform:uppercase;color:#666;
 margin:0 0 26px;font-weight:600}
.v{border-left:5px solid;padding:18px 22px;border-radius:4px;margin-bottom:8px}
.v b{display:block;font-size:21px;margin-bottom:7px}
.v p{margin:0;font-size:14px}
h2{font-size:12px;letter-spacing:.1em;text-transform:uppercase;color:#777;
 margin:32px 0 12px;border-bottom:1px solid #e3e3e3;padding-bottom:6px}
.r{margin-bottom:20px;padding-left:15px;border-left:3px solid #ddd}
.r.no{border-left-color:#8a1c1c}
.r.duda{border-left-color:#c98a00}
.r.si{border-left-color:#0b6b3a}
.k{font-weight:600;font-size:14px}
.m{font-size:13px;color:#555;margin:3px 0 8px}
blockquote{margin:0;padding:9px 14px;background:#f6f6f4;border-radius:3px;
 font-size:13px;color:#333;font-style:italic}
.ctx{font-size:12.5px;color:#555;margin:6px 0}
.ctx a{color:#26e;text-decoration:none}
footer{margin-top:36px;padding-top:14px;border-top:1px solid #e3e3e3;
 font-size:11.5px;color:#888}
"""


def _e(s: str) -> str:
    return html.escape(str(s))


def informe_html(res: Resultado, *, fuente: str, perfil: dict,
                 contexto: dict[str, list[Hallazgo]] | None = None) -> str:
    color, fondo = COLOR[res.veredicto]
    p = [f"<style>{CSS}</style>",
         "<h1>Standing &middot; cribado de elegibilidad</h1>",
         f'<div class="v" style="border-color:{color};background:{fondo}">'
         f'<b style="color:{color}">{_e(TITULO[res.veredicto])}</b>'
         f'<p>{_e(BAJADA[res.veredicto])}</p></div>',
         f'<p class="m">Documento: <b>{_e(fuente)}</b> &middot; '
         f'{date.today():%d/%m/%Y}</p>']

    orden = [("no", res.bloqueantes, "Lo que te deja fuera"),
             ("duda", res.dudosas, "Lo que no se puede saber"),
             ("si", [c for c in res.comprobaciones if c.cumple is True],
              "Lo que si cumples")]
    for clase, grupo, titulo in orden:
        if not grupo:
            continue
        p.append(f"<h2>{_e(titulo)}</h2>")
        for c in grupo:
            p.append(f'<div class="r {clase}"><div class="k">'
                     f'{_e(c.requisito.clave.replace("_", " "))}</div>'
                     f'<div class="m">{_e(c.motivo)}</div>'
                     f"<blockquote>&ldquo;{_e(c.requisito.cita)}&rdquo;"
                     f"</blockquote>")
            for h in (contexto or {}).get(c.requisito.clave, []):
                p.append(f'<div class="ctx">&rarr; {_e(h.titulo)} '
                         f'<a href="{_e(h.enlace)}">{_e(h.enlace[:64])}</a></div>')
            p.append("</div>")

    if res.avisos:
        p.append("<h2>Avisos</h2>")
        for a in res.avisos:
            p.append(f'<div class="m">&bull; {_e(a)}</div>')

    p.append("<h2>Perfil usado</h2>")
    p.append('<div class="m">' + " &middot; ".join(
        f"<b>{_e(k)}</b>: {_e(v)}" for k, v in perfil.items()) + "</div>")

    p.append("<footer>El veredicto lo decide codigo determinista comparando el "
             "perfil contra los requisitos; el modelo solo localiza y copia las "
             "frases. Toda cita se verifica contra el texto original: si no "
             "aparece, el requisito se descarta y se dice en Avisos.<br>"
             "Texto extraido con Nutrient DWS &middot; contexto con SerpApi "
             "&middot; PDF generado con Foxit PDF Services.</footer>")
    return "<html><meta charset='utf-8'><body>" + "".join(p) + "</body></html>"
