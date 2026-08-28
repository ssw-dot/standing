"""El historial. Sin red: se sustituye la peticion.

Lo que se fija aqui es una asimetria de diseno: **guardar nunca puede tumbar un
veredicto**. Quien llama ya tiene un cribado valido en la mano; que el registro
falle es una perdida, que se pierda el trabajo por no poder registrarlo seria un
error de diseno.
"""
import json
import unittest
from unittest import mock

from standing import historial as H
from standing.veredicto import Requisito, Veredicto, decidir

PERFIL = {"pais": "MX", "tipo": "nonprofit"}
URL = "https://x8ab-cdef-1234.n7.xano.io/api:AbCdEf"


def resultado(veredicto="no_elegible"):
    if veredicto == "elegible":
        return decidir([Requisito("pais", "Open to Mexico.", ("Mexico",),
                                  "lugar")], {"pais": "MX"})
    if veredicto == "duda":
        return decidir([Requisito("x", "Requirements apply.", ())], {"x": "y"})
    return decidir([Requisito("pais", "Open to Germany only.", ("Germany",),
                              "lugar")], {"pais": "MX"})


class TestGuardarNuncaTumbaNada(unittest.TestCase):
    def test_sin_xano_devuelve_falso_pero_no_lanza(self):
        with mock.patch.dict("os.environ", {"XANO_URL": ""}, clear=False):
            with mock.patch.object(H, "base_url",
                                   side_effect=H.SinXano("falta XANO_URL")):
                ok, nota = H.guardar(resultado(), documento="c.pdf", perfil=PERFIL)
        self.assertFalse(ok)
        self.assertIn("sin historial", nota)

    def test_si_la_red_falla_tampoco_lanza(self):
        # El cribado ya se hizo y el informe ya vale.
        with mock.patch.object(H, "base_url", return_value=URL):
            with mock.patch.object(H, "peticion",
                                   side_effect=RuntimeError("HTTP 500")):
                ok, nota = H.guardar(resultado(), documento="c.pdf", perfil=PERFIL)
        self.assertFalse(ok)
        self.assertIn("no se pudo guardar", nota)

    def test_cuando_va_bien_lo_dice(self):
        with mock.patch.object(H, "base_url", return_value=URL):
            with mock.patch.object(H, "peticion",
                                   return_value=b'{"id": 7}'):
                ok, nota = H.guardar(resultado(), documento="c.pdf", perfil=PERFIL)
        self.assertTrue(ok)
        self.assertIn("7", nota)


class TestQueSeGuarda(unittest.TestCase):
    def test_guarda_la_cita_no_solo_el_veredicto(self):
        # Una fila que dijera NO_ELEGIBLE y nada mas obligaria a re-ejecutar el
        # cribado para saber por que — que es justo lo que el historial evita.
        e = H.entrada_de(resultado(), documento="c.pdf", perfil=PERFIL)
        bloq = json.loads(e.como_json()["bloqueantes"])
        self.assertEqual(len(bloq), 1)
        self.assertIn("Germany", bloq[0]["cita"])
        self.assertTrue(bloq[0]["motivo"])

    def test_guarda_el_perfil_usado(self):
        # Sin el perfil, la fila no se puede reinterpretar: el mismo documento
        # da otro veredicto con otro solicitante.
        e = H.entrada_de(resultado(), documento="c.pdf", perfil=PERFIL)
        self.assertEqual(json.loads(e.como_json()["perfil"]), PERFIL)

    def test_las_dudas_van_aparte_de_los_bloqueantes(self):
        e = H.entrada_de(resultado("duda"), documento="c.pdf", perfil=PERFIL)
        self.assertEqual(json.loads(e.como_json()["bloqueantes"]), [])
        self.assertEqual(len(json.loads(e.como_json()["dudas"])), 1)

    def test_todo_va_serializado_a_texto(self):
        # Asi la tabla de Xano se crea con campos de texto y cuatro clics, en
        # vez de declarar un esquema anidado a mano.
        d = H.entrada_de(resultado(), documento="c.pdf", perfil=PERFIL).como_json()
        for k in ("perfil", "bloqueantes", "dudas", "avisos"):
            self.assertIsInstance(d[k], str, k)

    def test_la_fecha_es_utc_y_legible(self):
        e = H.entrada_de(resultado(), documento="c.pdf", perfil=PERFIL)
        self.assertIn("+00:00", e.cuando)


class TestResumen(unittest.TestCase):
    def test_historial_vacio(self):
        self.assertIn("vacio", H.resumen([]))

    def test_cuenta_por_veredicto(self):
        filas = [{"veredicto": "ELEGIBLE"}, {"veredicto": "NO_ELEGIBLE"},
                 {"veredicto": "NO_ELEGIBLE"}, {"veredicto": "NO_SE_PUEDE_SABER"}]
        t = H.resumen(filas)
        self.assertIn("4 cribados", t)
        self.assertIn("NO_ELEGIBLE", t)

    def test_nombra_el_monton_invisible(self):
        # Es la frase que justifica que esta integracion exista.
        filas = [{"veredicto": "NO_ELEGIBLE"}, {"veredicto": "NO_SE_PUEDE_SABER"}]
        t = H.resumen(filas)
        self.assertIn("no te presentaste", t)
        self.assertIn("2 convocatorias", t)

    def test_si_todo_es_elegible_no_inventa_un_monton(self):
        # Un aviso que sale siempre deja de leerse.
        t = H.resumen([{"veredicto": "ELEGIBLE"}, {"veredicto": "ELEGIBLE"}])
        self.assertNotIn("no te presentaste", t)

    def test_senala_las_dudas_como_lo_que_espera_a_una_persona(self):
        t = H.resumen([{"veredicto": "NO_SE_PUEDE_SABER"}])
        self.assertIn("una persona", t)


class TestUrl(unittest.TestCase):
    def test_sin_url_lanza_con_instrucciones(self):
        with mock.patch.dict("os.environ", {"XANO_URL": ""}, clear=False):
            try:
                H.base_url()
            except H.SinXano as e:
                texto = str(e)
        self.assertIn("xano.io", texto)

    def test_quita_la_barra_final(self):
        with mock.patch.dict("os.environ", {"XANO_URL": URL + "/"}, clear=False):
            self.assertEqual(H.base_url(), URL)


if __name__ == "__main__":
    unittest.main()
