"""Consenso entre lecturas. Sin red: se sustituye la llamada al modelo.

Escrito despues de que la MISMA convocatoria diera tres veredictos distintos en
cuatro ejecuciones. Temperatura 0 reduce la varianza de Gemini pero no la
elimina, y un cribado que contesta distinto en dos ejecuciones no se puede
defender ante nadie — que es exactamente lo que este producto vende.
"""
import json
import unittest
from unittest import mock

from standing import agente


def respuestas(*lecturas):
    """Un _llamar falso que devuelve cada lectura por turno, ciclicamente."""
    it = iter(lecturas)

    def falso(texto):
        nonlocal it
        try:
            return json.dumps(next(it))
        except StopIteration:
            it = iter(lecturas)
            return json.dumps(next(it))

    return falso


R_PAIS = {"clave": "pais", "cita": "Applicants must be based in Mexico.",
          "valores": ["Mexico"], "tipo": "lugar"}
R_TIPO = {"clave": "tipo", "cita": "Open to nonprofits.",
          "valores": ["nonprofit"], "tipo": "texto"}
R_RARO = {"clave": "plazo", "cita": "Deadline: 30 November 2026.",
          "valores": [], "tipo": "texto"}

DOC = ("Applicants must be based in Mexico. Open to nonprofits. "
       "Deadline: 30 November 2026.")


class TestConsenso(unittest.TestCase):
    def test_lo_que_sale_siempre_se_queda(self):
        with mock.patch.object(agente, "_llamar",
                               respuestas([R_PAIS, R_TIPO])):
            reqs, _ = agente.extraer_requisitos(DOC)
        self.assertEqual({r.clave for r in reqs}, {"pais", "tipo"})

    def test_lo_que_sale_una_sola_vez_se_descarta(self):
        # R_RARO aparece en 1 de 3 lecturas: es ruido del muestreo, no un
        # requisito que el documento enuncie.
        with mock.patch.object(agente, "_llamar", respuestas(
                [R_PAIS, R_TIPO, R_RARO], [R_PAIS, R_TIPO], [R_PAIS, R_TIPO])):
            reqs, avisos = agente.extraer_requisitos(DOC)
        self.assertEqual({r.clave for r in reqs}, {"pais", "tipo"})
        self.assertTrue(any("inestables" in a for a in avisos))

    def test_dos_de_tres_bastan(self):
        with mock.patch.object(agente, "_llamar", respuestas(
                [R_PAIS, R_TIPO], [R_PAIS, R_TIPO], [R_PAIS])):
            reqs, _ = agente.extraer_requisitos(DOC)
        self.assertEqual({r.clave for r in reqs}, {"pais", "tipo"})

    def test_agrupa_por_cita_aunque_cambie_la_clave(self):
        # El modelo se inventa la clave y puede llamarla distinto entre
        # lecturas. La cita es texto copiado del documento: esa no cambia.
        otra = dict(R_PAIS, clave="pais_de_residencia")
        with mock.patch.object(agente, "_llamar",
                               respuestas([R_PAIS], [otra], [R_PAIS])):
            reqs, _ = agente.extraer_requisitos(DOC)
        self.assertEqual(len(reqs), 1)

    def test_se_queda_con_la_version_que_mas_valores_trae(self):
        # Un requisito con lista de valores dice mas que uno vacio. Quedarse
        # con el vacio perderia informacion que si se llego a leer.
        pobre = dict(R_PAIS, valores=[])
        rico = dict(R_PAIS, valores=["Mexico", "Colombia"])
        with mock.patch.object(agente, "_llamar",
                               respuestas([pobre], [rico], [pobre])):
            reqs, _ = agente.extraer_requisitos(DOC)
        self.assertEqual(len(reqs[0].valores), 2)

    def test_es_estable_entre_ejecuciones(self):
        # Lo que se vende: la misma entrada da la misma salida.
        entrada = ([R_PAIS, R_TIPO, R_RARO], [R_PAIS, R_TIPO], [R_PAIS, R_TIPO])
        salidas = set()
        for _ in range(5):
            with mock.patch.object(agente, "_llamar", respuestas(*entrada)):
                reqs, _ = agente.extraer_requisitos(DOC)
            salidas.add(tuple(sorted(r.clave for r in reqs)))
        self.assertEqual(len(salidas), 1)

    def test_si_ninguna_lectura_sale_lo_dice(self):
        def revienta(texto):
            raise RuntimeError("ningun modelo respondio")

        with mock.patch.object(agente, "_llamar", revienta):
            reqs, avisos = agente.extraer_requisitos(DOC)
        self.assertEqual(reqs, [])
        self.assertTrue(any("no se pudo leer" in a for a in avisos))

    def test_una_cita_inventada_sigue_cayendo(self):
        # El consenso no puede saltarse la verificacion de la cita: tres
        # lecturas de acuerdo en algo que no esta en el documento siguen siendo
        # tres invenciones.
        falso = {"clave": "x", "cita": "This sentence is not in the document.",
                 "valores": ["y"], "tipo": "texto"}
        with mock.patch.object(agente, "_llamar", respuestas([falso])):
            reqs, avisos = agente.extraer_requisitos(DOC)
        self.assertEqual(reqs, [])
        self.assertTrue(any("no aparece en el documento" in a for a in avisos))


if __name__ == "__main__":
    unittest.main()
