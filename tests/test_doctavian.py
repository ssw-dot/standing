"""Lo unico de Doctavian que se puede probar sin red: la forma de los datos.

Las llamadas HTTP no se prueban aqui a proposito. Lo que si se prueba es lo que
decide como se ve el informe, porque la plantilla no razona: si el programa
manda `hayDudas` mal, la plantilla ensena una seccion vacia o esconde una que
importaba, y eso no lo caza nadie mirando un PDF bonito.
"""
from __future__ import annotations

import unittest
import zipfile
from pathlib import Path

from standing.doctavian import datos_de
from standing.veredicto import Comprobacion, Requisito, Resultado, Veredicto

RAIZ = Path(__file__).resolve().parents[1]


def comp(clave, cumple, motivo="porque si", cita="lo dice el documento"):
    return Comprobacion(Requisito(clave=clave, cita=cita), cumple, motivo)


def res(veredicto, comps, avisos=()):
    return Resultado(veredicto, list(comps), list(avisos))


class Datos(unittest.TestCase):

    def test_elegible_no_lleva_secciones_de_problema(self):
        d = datos_de(res(Veredicto.ELEGIBLE, [comp("pais", True)]),
                     documento="c.pdf", perfil={"pais": "MX"})
        self.assertTrue(d["esElegible"])
        self.assertFalse(d["hayBloqueantes"])
        self.assertFalse(d["hayDudas"])
        self.assertEqual(d["veredicto"], "ELIGIBLE")

    def test_una_duda_no_es_un_bloqueante(self):
        """El fallo entero del proyecto en una linea.

        Si una duda acabara en `bloqueantes`, el informe diria en su titular que
        algo te excluye cuando lo unico que pasa es que el documento callaba.
        """
        d = datos_de(res(Veredicto.NO_SE_PUEDE_SABER,
                         [comp("antiguedad", None)]),
                     documento="c.pdf", perfil={})
        self.assertTrue(d["hayDudas"])
        self.assertFalse(d["hayBloqueantes"])
        self.assertEqual(d["veredicto"], "CANNOT BE DETERMINED")
        self.assertEqual(d["dudas"][0]["estado"], "unclear")

    def test_cada_requisito_lleva_su_cita(self):
        """Sin la cita el informe es una opinion con formato."""
        d = datos_de(res(Veredicto.NO_ELEGIBLE,
                         [comp("pais", False, cita="Only EU applicants.")]),
                     documento="c.pdf", perfil={"pais": "MX"})
        self.assertEqual(d["bloqueantes"][0]["cita"], "Only EU applicants.")
        self.assertTrue(all(r["cita"] for r in d["requisitos"]))

    def test_los_requisitos_van_cumplidos_primero(self):
        """Un informe que abre por lo que falla se lee como un rechazo.

        El orden es cumplidas, bloqueantes, dudas: primero lo que ya esta
        resuelto, y las dudas al final, que es donde alguien tiene que mirar.
        """
        d = datos_de(res(Veredicto.NO_ELEGIBLE,
                         [comp("a", None), comp("b", False), comp("c", True)]),
                     documento="c.pdf", perfil={})
        self.assertEqual([r["clave"] for r in d["requisitos"]],
                         ["c", "b", "a"])

    def test_los_recuentos_no_los_calcula_la_plantilla(self):
        d = datos_de(res(Veredicto.NO_ELEGIBLE,
                         [comp("a", True), comp("b", True), comp("c", False)]),
                     documento="c.pdf", perfil={})
        self.assertEqual(d["totalRequisitos"], 3)
        self.assertEqual(d["totalCumplidas"], 2)

    def test_el_perfil_viaja_como_lista_para_poder_iterarlo(self):
        d = datos_de(res(Veredicto.ELEGIBLE, []),
                     documento="c.pdf", perfil={"pais": "MX", "anos": 4})
        self.assertEqual(d["perfil"],
                         [{"campo": "pais", "valor": "MX"},
                          {"campo": "anos", "valor": "4"}])

    def test_sin_avisos_la_seccion_no_existe(self):
        d = datos_de(res(Veredicto.ELEGIBLE, [], avisos=[]),
                     documento="c.pdf", perfil={})
        self.assertFalse(d["hayAvisos"])
        self.assertEqual(d["avisos"], [])


class Plantilla(unittest.TestCase):
    """La plantilla es un artefacto del repositorio: si no abre, no hay informe."""

    def setUp(self):
        self.docx = RAIZ / "plantilla" / "informe.docx"
        if not self.docx.exists():
            self.skipTest("falta plantilla/informe.docx: "
                          "python plantilla/construir.py")
        self.xml = zipfile.ZipFile(self.docx).read(
            "word/document.xml").decode("utf-8")

    def test_es_un_docx_legible(self):
        import xml.dom.minidom
        xml.dom.minidom.parseString(self.xml)   # lanza si no es XML valido

    def test_itera_los_requisitos(self):
        self.assertIn("mdoc:repeater", self.xml)
        self.assertIn("requisitos", self.xml)

    def test_esconde_lo_que_no_hay(self):
        for bandera in ("hayBloqueantes", "hayDudas", "hayAvisos"):
            self.assertIn(bandera, self.xml)

    def test_todo_campo_de_la_plantilla_existe_en_los_datos(self):
        """El fallo silencioso de cualquier plantilla: un campo que no llega.

        No revienta nada — sale un hueco en el PDF. Asi que las claves de la
        plantilla se comparan contra las que produce `datos_de`.
        """
        import re
        d = datos_de(res(Veredicto.ELEGIBLE, [comp("a", True)]),
                     documento="c.pdf", perfil={"pais": "MX"})
        usados = set(re.findall(r"MERGEFIELD (\w+)", self.xml))
        self.assertTrue(usados)
        self.assertFalse(usados - set(d), f"campos sin datos: {usados - set(d)}")

    def test_toda_variable_de_bucle_sale_de_una_coleccion_declarada(self):
        import re
        bucles = dict(re.findall(
            r'mdoc:repeater value="(\w+)" variable="(\w+)"', self.xml))
        self.assertTrue(bucles, "no se encontro ningun repeater")
        d = datos_de(res(Veredicto.NO_ELEGIBLE, [comp("a", False)]),
                     documento="c.pdf", perfil={"pais": "MX"})
        for coleccion in bucles:
            self.assertIsInstance(d.get(coleccion), list,
                                  f"el repeater itera '{coleccion}', que no es "
                                  f"una lista en los datos")


if __name__ == "__main__":
    unittest.main()
