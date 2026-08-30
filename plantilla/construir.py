#!/usr/bin/env python3
"""Escribe `informe.docx`: la plantilla que Doctavian compone.

Se genera con codigo y no se sube un DOCX hecho a mano por dos razones. La
primera es que un binario en el repositorio no se puede revisar: un `diff` de un
DOCX no dice nada, y aqui la plantilla **es** la logica de presentacion. La
segunda es que asi el fichero se puede volver a construir identico, que es lo
unico que permite cambiarlo sin miedo.

No hace falta python-docx. Un DOCX es un ZIP con tres XML dentro, y escribirlos
a mano cuesta menos que arrastrar una dependencia que solo se usaria aqui.

    python plantilla/construir.py

## Que hay dentro

Los elementos `mdoc:` son la parte que importa, porque son lo que hace que este
documento decida cosas en vez de limitarse a recibirlas:

    <mdoc:repeater value="requisitos" variable="req">   itera los requisitos
    <mdoc:paragraph hidden="...">                        oculta una seccion entera
    #req.cita#                                           el campo del elemento actual

Un requisito no cumplido y una duda **no se ven igual y no estan en el mismo
sitio**, y eso lo decide la plantilla, no el programa que la rellena.

## Lo que aun no esta verificado

La sintaxis de campo fuera de los bucles se escribe como MERGEFIELD de Word,
que es lo que inserta su complemento. Dentro de un repeater la documentacion es
explicita —almohadillas alrededor de la variable— y esa parte si esta
confirmada por escrito:

> *"The hash # symbol is used. You must place # before and after any Variable
> referenced inside Tables and Repeaters."*

Por eso los campos pasan todos por `campo()` y `en_bucle()`: cuando la primera
generacion real diga cual de las dos formas quiere fuera del bucle, se cambia
en una funcion y no en cuarenta sitios.
"""
from __future__ import annotations

import zipfile
from pathlib import Path

AQUI = Path(__file__).resolve().parent

NS = ('xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"')


def esc(t: str) -> str:
    return (t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def campo(nombre: str) -> str:
    """Un campo de combinacion de Word: lo que inserta su complemento."""
    return (
        '<w:r><w:fldChar w:fldCharType="begin"/></w:r>'
        f'<w:r><w:instrText xml:space="preserve"> MERGEFIELD {esc(nombre)} '
        '</w:instrText></w:r>'
        '<w:r><w:fldChar w:fldCharType="separate"/></w:r>'
        f'<w:r><w:t>«{esc(nombre)}»</w:t></w:r>'
        '<w:r><w:fldChar w:fldCharType="end"/></w:r>')


def en_bucle(variable: str, campo_: str) -> str:
    """Una variable del repeater: almohadilla delante y detras."""
    return f'<w:r><w:t xml:space="preserve">#{variable}.{campo_}#</w:t></w:r>'


def texto(t: str, *, negrita=False, tam=None, color=None,
          espacio_antes=0) -> str:
    props = ""
    if negrita:
        props += "<w:b/>"
    if tam:
        props += f'<w:sz w:val="{tam * 2}"/><w:szCs w:val="{tam * 2}"/>'
    if color:
        props += f'<w:color w:val="{color}"/>'
    rpr = f"<w:rPr>{props}</w:rPr>" if props else ""
    ppr = (f'<w:pPr><w:spacing w:before="{espacio_antes * 20}"/></w:pPr>'
           if espacio_antes else "")
    return (f"<w:p>{ppr}<w:r>{rpr}<w:t xml:space=\"preserve\">{esc(t)}"
            f"</w:t></w:r></w:p>")


def crudo(*trozos: str, espacio_antes=0) -> str:
    """Un parrafo compuesto de trozos ya formados (campos, textos, variables)."""
    ppr = (f'<w:pPr><w:spacing w:before="{espacio_antes * 20}"/></w:pPr>'
           if espacio_antes else "")
    return f"<w:p>{ppr}{''.join(trozos)}</w:p>"


def marca(t: str) -> str:
    """Un elemento mdoc, que en el DOCX es texto plano y en la salida no existe."""
    return texto(t)


def cuerpo() -> str:
    p = []

    p.append(texto("Standing", negrita=True, tam=26))
    p.append(texto("Eligibility screening report", tam=11, color="666666"))

    p.append(crudo('<w:r><w:t xml:space="preserve">Document: </w:t></w:r>'
                   + campo("documento"), espacio_antes=12))
    p.append(crudo('<w:r><w:rPr><w:b/><w:sz w:val="36"/></w:rPr>'
                   '<w:t xml:space="preserve">Verdict: </w:t></w:r>'
                   + campo("veredicto"), espacio_antes=10))

    # Las tres frases que explican el veredicto. Solo se ve una, y cual se ve lo
    # decide la plantilla: el programa entrega tres banderas y se desentiende.
    p.append(marca('<mdoc:paragraph hidden="#!esElegible#">'))
    p.append(texto("You meet every requirement this document states. Anything "
                   "it leaves unsaid is not a bar to applying.", tam=11))
    p.append(marca("</mdoc:paragraph>"))

    p.append(marca('<mdoc:paragraph hidden="#!esNoElegible#">'))
    p.append(texto("This document excludes you, and the sentence that does it "
                   "is quoted below. Read it before you accept it.", tam=11))
    p.append(marca("</mdoc:paragraph>"))

    p.append(marca('<mdoc:paragraph hidden="#!esDuda#">'))
    p.append(texto("The document does not say. That is not a rejection — it is "
                   "a question for a person, and the open points are listed "
                   "below.", tam=11))
    p.append(marca("</mdoc:paragraph>"))

    p.append(crudo('<w:r><w:rPr><w:b/></w:rPr><w:t xml:space="preserve">'
                   'Requirements found: </w:t></w:r>' + campo("totalRequisitos")
                   + '<w:r><w:t xml:space="preserve">   ·   met: </w:t></w:r>'
                   + campo("totalCumplidas"), espacio_antes=14))

    # El bucle. Cada requisito sale con la frase del documento que lo dice: sin
    # la cita el informe es una opinion, y con ella es una comprobacion.
    p.append(texto("Requirement by requirement", negrita=True, tam=14,
                   espacio_antes=16))
    p.append(marca('<mdoc:repeater value="requisitos" variable="req">'))
    p.append(crudo('<w:r><w:rPr><w:b/></w:rPr>'
                   + f'<w:t xml:space="preserve">#req.clave#</w:t></w:r>'
                   '<w:r><w:t xml:space="preserve">  —  </w:t></w:r>'
                   '<w:r><w:t xml:space="preserve">#req.estado#</w:t></w:r>',
                   espacio_antes=8))
    p.append(crudo('<w:r><w:rPr><w:i/></w:rPr>'
                   '<w:t xml:space="preserve">"#req.cita#"</w:t></w:r>'))
    p.append(crudo('<w:r><w:t xml:space="preserve">#req.motivo#</w:t></w:r>'))
    p.append(marca("</mdoc:repeater>"))

    # Las dos secciones que desaparecen. Un informe con un titulo "Blocking"
    # seguido de nada dice que el programa no supo que no habia nada; que la
    # seccion no exista dice que no habia nada.
    p.append(marca('<mdoc:paragraph hidden="#!hayBloqueantes#">'))
    p.append(texto("What blocks you", negrita=True, tam=14, espacio_antes=16))
    p.append(marca('<mdoc:repeater value="bloqueantes" variable="b">'))
    p.append(crudo('<w:r><w:rPr><w:b/></w:rPr>'
                   '<w:t xml:space="preserve">#b.clave#: </w:t></w:r>'
                   '<w:r><w:t xml:space="preserve">#b.motivo#</w:t></w:r>'))
    p.append(crudo('<w:r><w:rPr><w:i/></w:rPr>'
                   '<w:t xml:space="preserve">"#b.cita#"</w:t></w:r>'))
    p.append(marca("</mdoc:repeater>"))
    p.append(marca("</mdoc:paragraph>"))

    p.append(marca('<mdoc:paragraph hidden="#!hayDudas#">'))
    p.append(texto("What the document does not settle", negrita=True, tam=14,
                   espacio_antes=16))
    p.append(texto("None of these excludes you. Each one is a place where the "
                   "document is silent and a person has to decide.", tam=10,
                   color="666666"))
    p.append(marca('<mdoc:repeater value="dudas" variable="d">'))
    p.append(crudo('<w:r><w:rPr><w:b/></w:rPr>'
                   '<w:t xml:space="preserve">#d.clave#: </w:t></w:r>'
                   '<w:r><w:t xml:space="preserve">#d.motivo#</w:t></w:r>'))
    p.append(crudo('<w:r><w:rPr><w:i/></w:rPr>'
                   '<w:t xml:space="preserve">"#d.cita#"</w:t></w:r>'))
    p.append(marca("</mdoc:repeater>"))
    p.append(marca("</mdoc:paragraph>"))

    p.append(marca('<mdoc:paragraph hidden="#!hayAvisos#">'))
    p.append(texto("Warnings", negrita=True, tam=14, espacio_antes=16))
    p.append(marca('<mdoc:repeater value="avisos" variable="a">'))
    p.append(crudo('<w:r><w:t xml:space="preserve">· #a.texto#</w:t></w:r>'))
    p.append(marca("</mdoc:repeater>"))
    p.append(marca("</mdoc:paragraph>"))

    p.append(texto("The profile screened", negrita=True, tam=14,
                   espacio_antes=16))
    p.append(marca('<mdoc:repeater value="perfil" variable="c">'))
    p.append(crudo('<w:r><w:t xml:space="preserve">#c.campo#: #c.valor#'
                   "</w:t></w:r>"))
    p.append(marca("</mdoc:repeater>"))

    p.append(texto("A verdict of CANNOT BE DETERMINED is not a failure of this "
                   "report. It is the report refusing to invent a sentence the "
                   "document never wrote.", tam=9, color="666666",
                   espacio_antes=20))

    # La documentacion avisa de que un mdoc:paragraph al final del documento sin
    # un parrafo vacio detras puede reventar la generacion. Es barato hacerle
    # caso.
    p.append(texto(""))
    return "".join(p)


def escribir(destino: Path) -> Path:
    doc = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
           f"<w:document {NS}><w:body>{cuerpo()}"
           '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/>'
           '<w:pgMar w:top="1134" w:right="1134" w:bottom="1134" '
           'w:left="1134"/></w:sectPr></w:body></w:document>')

    tipos = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
             '<Types xmlns="http://schemas.openxmlformats.org/package/2006/'
             'content-types">'
             '<Default Extension="rels" ContentType="application/vnd.openxml'
             'formats-package.relationships+xml"/>'
             '<Default Extension="xml" ContentType="application/xml"/>'
             '<Override PartName="/word/document.xml" ContentType="application/'
             'vnd.openxmlformats-officedocument.wordprocessingml.document.main'
             '+xml"/></Types>')

    rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/'
            '2006/relationships"><Relationship Id="rId1" Type="http://schemas.'
            'openxmlformats.org/officeDocument/2006/relationships/officeDocument'
            '" Target="word/document.xml"/></Relationships>')

    destino.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", tipos)
        z.writestr("_rels/.rels", rels)
        z.writestr("word/document.xml", doc)
    return destino


if __name__ == "__main__":
    r = escribir(AQUI / "informe.docx")
    print(f"OK  {r}  ·  {r.stat().st_size} bytes")
