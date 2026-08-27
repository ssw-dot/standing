"""Lo que se fija aqui es una asimetria, no un comportamiento.

Los dos errores posibles no cuestan lo mismo. Un falso ELEGIBLE se descubre
solo: presentas, te rechazan. Un falso NO_ELEGIBLE no se descubre nunca —la
persona no se presenta, no hay carta, no hay nada que revisar—, y por eso casi
todos los tests de este fichero comprueban lo mismo desde angulos distintos:
**que la duda no se convierta en exclusion.**
"""
import unittest

from standing.lugares import es_region, resolver
from standing.veredicto import (Requisito, Veredicto, coincide, decidir,
                                normalizar)


def req(clave, valores=(), cita="El documento lo dice aqui.", tipo="texto"):
    return Requisito(clave, cita, tuple(valores), tipo)


class TestNormalizar(unittest.TestCase):
    def test_quita_acentos_y_mayusculas(self):
        self.assertEqual(normalizar("MÉXICO"), "mexico")

    def test_quita_plural(self):
        self.assertEqual(normalizar("organisations"), "organisation")

    def test_no_destroza_palabras_cortas(self):
        # "us" no puede convertirse en "u" por acabar en s.
        self.assertEqual(normalizar("us"), "us")

    def test_quita_puntuacion(self):
        self.assertEqual(normalizar("non-profit, inc."), "non profit inc")


class TestCoincide(unittest.TestCase):
    def test_el_fallo_de_la_biblioteca(self):
        # Un cribado dijo NO ELEGIBLE a una biblioteca porque el documento
        # decia "nonprofit organisations" y el perfil decia "nonprofit". Le
        # dijimos que no pidiera un fondo escrito para ella.
        self.assertTrue(coincide("nonprofit", ("nonprofit organisations",)))

    def test_al_reves_tambien(self):
        self.assertTrue(coincide("nonprofit organisation", ("nonprofit",)))

    def test_no_encaja_lo_que_no_encaja(self):
        self.assertFalse(coincide("empresa privada", ("nonprofit",)))

    def test_vacio_no_encaja_con_nada(self):
        self.assertFalse(coincide("", ("nonprofit",)))
        self.assertFalse(coincide("nonprofit", ("",)))


class TestRequisitoExigeCita(unittest.TestCase):
    def test_sin_cita_no_se_construye(self):
        # La cita es la unica prueba de que el requisito estaba en el
        # documento y no lo invento el modelo.
        with self.assertRaises(ValueError):
            Requisito("pais", "   ", ("MX",))

    def test_sin_clave_no_se_construye(self):
        with self.assertRaises(ValueError):
            Requisito("", "cita", ("MX",))


class TestLaDudaNoExcluye(unittest.TestCase):
    """El corazon del asunto."""

    def test_perfil_sin_el_dato_es_duda(self):
        r = decidir([req("facturacion", ("menos de 1M",))], {"pais": "MX"})
        self.assertIs(r.veredicto, Veredicto.NO_SE_PUEDE_SABER)

    def test_requisito_sin_valores_es_duda(self):
        # El documento enuncia "debe cumplir requisitos de tamano" pero no dice
        # cuales. Eso no autoriza ni excluye.
        r = decidir([req("tamano")], {"tamano": "12 empleados"})
        self.assertIs(r.veredicto, Veredicto.NO_SE_PUEDE_SABER)

    def test_valor_vacio_en_el_perfil_es_duda(self):
        r = decidir([req("pais", ("MX",))], {"pais": ""})
        self.assertIs(r.veredicto, Veredicto.NO_SE_PUEDE_SABER)

    def test_lista_vacia_en_el_perfil_es_duda(self):
        r = decidir([req("pais", ("MX",))], {"pais": []})
        self.assertIs(r.veredicto, Veredicto.NO_SE_PUEDE_SABER)

    def test_sin_requisitos_no_es_elegible(self):
        # Que no se haya podido leer el documento no es una autorizacion.
        r = decidir([], {"pais": "MX"})
        self.assertIs(r.veredicto, Veredicto.NO_SE_PUEDE_SABER)
        self.assertTrue(r.avisos)

    def test_el_aviso_distingue_las_dos_causas(self):
        r = decidir([], {})
        texto = " ".join(r.avisos)
        # "no hay requisitos" y "no se pudo leer" son cosas distintas y el
        # informe no puede fingir que sabe cual de las dos fue.
        self.assertIn("distintas", texto)


class TestCadenasNoSonListas(unittest.TestCase):
    def test_una_cadena_es_un_valor(self):
        # Iterar "MX" y comparar "M" y "X" contra los admitidos da un
        # no-elegible silencioso. Es el fallo mas caro que hemos tenido: un
        # cribado que debia excluir, absolvia.
        r = decidir([req("pais", ("Mexico",), tipo="lugar")], {"pais": "MX"})
        self.assertIs(r.veredicto, Veredicto.ELEGIBLE)

    def test_una_lista_si_se_itera(self):
        r = decidir([req("pais", ("Colombia",), tipo="lugar")],
                    {"pais": ["MX", "CO"]})
        self.assertIs(r.veredicto, Veredicto.ELEGIBLE)


class TestLugares(unittest.TestCase):
    def test_codigo_y_nombre_son_lo_mismo(self):
        for a, b in [("MX", "Mexico"), ("mex", "MÉXICO"), ("us", "United States")]:
            self.assertEqual(resolver(a), resolver(b), f"{a} vs {b}")

    def test_una_region_no_se_resuelve_a_pais(self):
        # Quebec se parece a Canada y no es un pais. Si el mapa adivina, el
        # veredicto se vuelve una opinion con cara de dato.
        self.assertIsNone(resolver("Quebec"))
        self.assertTrue(es_region("Quebec"))

    def test_cdmx_no_es_un_pais(self):
        self.assertIsNone(resolver("CDMX"))

    def test_un_disparate_no_es_region(self):
        # "asdfgh" y "Quebec" son las dos None, pero por motivos distintos.
        self.assertIsNone(resolver("asdfgh"))
        self.assertFalse(es_region("asdfgh"))

    def test_region_admitida_es_duda_no_exclusion(self):
        r = decidir([req("pais", ("Europe",), tipo="lugar")], {"pais": "MX"})
        self.assertIs(r.veredicto, Veredicto.NO_SE_PUEDE_SABER)

    def test_pais_del_perfil_irreconocible_es_duda(self):
        r = decidir([req("pais", ("Mexico",), tipo="lugar")], {"pais": "Wakanda"})
        self.assertIs(r.veredicto, Veredicto.NO_SE_PUEDE_SABER)

    def test_exclusion_clara_si_se_excluye(self):
        # No excluir por duda no puede volverse no excluir nunca.
        r = decidir([req("pais", ("Germany", "France"), tipo="lugar")],
                    {"pais": "MX"})
        self.assertIs(r.veredicto, Veredicto.NO_ELEGIBLE)


class TestPrecedencia(unittest.TestCase):
    def test_un_incumplimiento_manda_sobre_una_duda(self):
        # Si el documento dice "solo Alemania" y el perfil dice Mexico, da
        # igual que otro requisito este en duda.
        r = decidir([req("pais", ("Germany",), tipo="lugar"),
                     req("facturacion", ("menos de 1M",))],
                    {"pais": "MX"})
        self.assertIs(r.veredicto, Veredicto.NO_ELEGIBLE)
        self.assertEqual(len(r.bloqueantes), 1)
        self.assertEqual(len(r.dudosas), 1)

    def test_todo_cumplido_es_elegible(self):
        r = decidir([req("pais", ("Mexico",), tipo="lugar"),
                     req("tipo", ("nonprofit organisations",))],
                    {"pais": "MX", "tipo": "nonprofit"})
        self.assertIs(r.veredicto, Veredicto.ELEGIBLE)
        self.assertEqual(r.dudosas, [])

    def test_toda_comprobacion_lleva_motivo(self):
        # Un veredicto sin motivo no se puede discutir, y este producto se
        # vende justo por poder discutirlo.
        r = decidir([req("pais", ("Mexico",), tipo="lugar"),
                     req("x", ("y",))], {"pais": "MX"})
        for c in r.comprobaciones:
            self.assertTrue(c.motivo.strip())
            self.assertTrue(c.requisito.cita.strip())


if __name__ == "__main__":
    unittest.main()


class TestUmbrales(unittest.TestCase):
    """Escrita despues de que el sistema entero fallara en una convocatoria real.

        requisito: "must have been operating for at least two years"
        perfil:    "4 years"
        veredicto: NO_ELEGIBLE

    Cuatro anos cumple al menos dos. El comparador de texto trataba la
    condicion como si fuera un valor admitido de una lista.
    """

    def test_el_fallo_de_los_cuatro_anos(self):
        r = decidir([req("antiguedad", ("at least two years",))],
                    {"antiguedad": "4 years"})
        self.assertIs(r.veredicto, Veredicto.ELEGIBLE)

    def test_por_debajo_del_minimo_si_excluye(self):
        r = decidir([req("antiguedad", ("at least two years",))],
                    {"antiguedad": "1 year"})
        self.assertIs(r.veredicto, Veredicto.NO_ELEGIBLE)

    def test_numeros_con_letra(self):
        from standing.cantidades import leer_umbral
        u = leer_umbral("un minimo de tres empleados")
        self.assertEqual((u.operador, u.valor, u.unidad), (">=", 3.0, "personas"))

    def test_no_more_than_no_se_lee_como_more_than(self):
        # "no more than" contiene "more than". Leerlo al reves convierte un
        # techo en un suelo, y entonces una empresa pequena queda excluida por
        # no ser bastante grande.
        from standing.cantidades import leer_umbral
        self.assertEqual(leer_umbral("no more than 20 employees").operador, "<=")
        self.assertEqual(leer_umbral("more than 20 employees").operador, ">=")

    def test_maximo_se_compara_bien(self):
        r = decidir([req("tamano", ("no more than 20 employees",))],
                    {"tamano": "12 employees"})
        self.assertIs(r.veredicto, Veredicto.ELEGIBLE)
        r = decidir([req("tamano", ("no more than 20 employees",))],
                    {"tamano": "30 employees"})
        self.assertIs(r.veredicto, Veredicto.NO_ELEGIBLE)

    def test_unidades_distintas_es_duda(self):
        # Comparar anos contra empleados y responder que no cumple seria
        # inventarse una conclusion con forma de calculo.
        r = decidir([req("x", ("minimum of 3 employees",))], {"x": "4 years"})
        self.assertIs(r.veredicto, Veredicto.NO_SE_PUEDE_SABER)

    def test_sin_cantidad_en_el_perfil_es_duda(self):
        r = decidir([req("antiguedad", ("at least two years",))],
                    {"antiguedad": "recien fundada"})
        self.assertIs(r.veredicto, Veredicto.NO_SE_PUEDE_SABER)

    def test_una_enumeracion_de_verdad_sigue_yendo_por_texto(self):
        # El detector de umbrales no puede tragarse los casos normales.
        r = decidir([req("tipo", ("nonprofit organisations", "cooperative"))],
                    {"tipo": "nonprofit"})
        self.assertIs(r.veredicto, Veredicto.ELEGIBLE)

    def test_un_ano_exacto_cumple_al_menos_un_ano(self):
        # El borde. ">=" incluye el propio valor.
        r = decidir([req("a", ("at least one year",))], {"a": "1 year"})
        self.assertIs(r.veredicto, Veredicto.ELEGIBLE)


class TestRemision(unittest.TestCase):
    """Escrita despues de correr el sistema contra una convocatoria real de
    Horizon Europe.

    El documento dice, con esas palabras, que sus reglas de elegibilidad estan
    en otro fichero. Y aun asi el sistema saco un NO_ELEGIBLE de un parentesis
    suelto. Todo parecia correcto —habia cita, habia comparacion, habia
    motivo— salvo que la fuente no era la fuente.
    """

    def test_un_documento_que_remite_no_excluye(self):
        r = decidir([req("pais", ("Germany",), tipo="lugar")],
                    {"pais": "MX"}, remite=True)
        self.assertIs(r.veredicto, Veredicto.NO_SE_PUEDE_SABER)

    def test_y_lo_explica(self):
        r = decidir([req("pais", ("Germany",), tipo="lugar")],
                    {"pais": "MX"}, remite=True)
        self.assertTrue(any("remite" in a for a in r.avisos))

    def test_el_incumplimiento_sigue_visible(self):
        # Se degrada el veredicto, no se esconde la comprobacion: quien lea el
        # informe tiene que ver que ese requisito no encajaba.
        r = decidir([req("pais", ("Germany",), tipo="lugar")],
                    {"pais": "MX"}, remite=True)
        self.assertEqual(len(r.bloqueantes), 1)

    def test_elegible_no_se_degrada(self):
        # "Cumples lo que este documento pide" sigue siendo cierto aunque haya
        # mas reglas en otro sitio, y equivocarse por ahi se descubre solo.
        r = decidir([req("pais", ("Mexico",), tipo="lugar")],
                    {"pais": "MX"}, remite=True)
        self.assertIs(r.veredicto, Veredicto.ELEGIBLE)

    def test_sin_remision_todo_igual(self):
        r = decidir([req("pais", ("Germany",), tipo="lugar")], {"pais": "MX"})
        self.assertIs(r.veredicto, Veredicto.NO_ELEGIBLE)


class TestDeteccionDeRemision(unittest.TestCase):
    def test_detecta_la_frase_de_horizon(self):
        from standing.agente import detectar_remision
        t = ("In addition to the work programme parts mentioned above, the "
             "General Annexes to this work programme set out the general "
             "conditions applying to the calls of the work programme such as "
             "eligibility rules; details on how to submit an application.")
        self.assertTrue(detectar_remision(t))

    def test_no_se_dispara_con_cualquier_anexo(self):
        # "El TRL se define en los anexos generales" menciona un anexo y no
        # remite ninguna regla. Si todo remite, nada remite y el aviso pierde
        # su valor.
        from standing.agente import detectar_remision
        t = ("The definition of Technology Readiness Levels is available in "
             "the General Annexes to this work programme.")
        self.assertEqual(detectar_remision(t), [])

    def test_tambien_en_espanol(self):
        from standing.agente import detectar_remision
        t = ("Los requisitos de participacion se detallan en las bases "
             "reguladoras publicadas junto a esta convocatoria.")
        self.assertTrue(detectar_remision(t))


class TestElUmbralEnLaCita(unittest.TestCase):
    """El fallo de los cuatro anos, entrando por otra puerta.

    Corriendo el sistema tres veces sobre la MISMA convocatoria salieron dos
    veredictos distintos: ELEGIBLE una vez y NO_ELEGIBLE dos. No era
    indeterminismo del veredicto — era que el modelo unas veces devuelve
    `["at least two years"]` y otras `["2 years"]`. Sin las palabras del
    umbral, la condicion pasa por una enumeracion y el comparador de texto
    excluye a quien cumple de sobra.

    La deteccion no puede depender de que el modelo conserve una frase. La
    cita si es fiable: **se verifica contra el documento**, asi que es texto
    real y no la parafrasis de nadie.
    """

    CITA = "Organisations must have been operating for at least two years."

    def test_aunque_el_modelo_se_coma_las_palabras_del_umbral(self):
        r = decidir([Requisito("antiguedad", self.CITA, ("2 years",))],
                    {"antiguedad": "4 years"})
        self.assertIs(r.veredicto, Veredicto.ELEGIBLE)

    def test_y_sigue_funcionando_cuando_si_las_trae(self):
        r = decidir([Requisito("antiguedad", self.CITA, ("at least two years",))],
                    {"antiguedad": "4 years"})
        self.assertIs(r.veredicto, Veredicto.ELEGIBLE)

    def test_no_sobrecorrige_quien_no_cumple_sigue_fuera(self):
        # Lo facil seria dejar de excluir nunca. Eso convierte la herramienta
        # en una que siempre dice que si, que es igual de inutil.
        r = decidir([Requisito("antiguedad", self.CITA, ("2 years",))],
                    {"antiguedad": "1 year"})
        self.assertIs(r.veredicto, Veredicto.NO_ELEGIBLE)

    def test_los_tres_veredictos_son_estables_entre_llamadas(self):
        # Mismo requisito, diez veces: la parte determinista tiene que dar
        # siempre lo mismo. Es lo que se vende al comprador.
        req = Requisito("antiguedad", self.CITA, ("2 years",))
        vistos = {decidir([req], {"antiguedad": "4 years"}).veredicto
                  for _ in range(10)}
        self.assertEqual(len(vistos), 1)


class TestNoExcluirPorTextoSiSonCantidades(unittest.TestCase):
    """La red que cierra la clase, no la instancia.

    Si los dos lados son cantidades de la misma magnitud, comparar TEXTO no
    puede decidir: "4 years" y "2 years" no dicen lo mismo y aun asi uno cumple
    de sobra. Excluir ahi es exactamente el falso NO_ELEGIBLE que este sistema
    existe para no dar.
    """

    def test_dos_cantidades_sin_umbral_legible_van_a_duda(self):
        # Sin nada en la cita de donde sacar el umbral.
        r = decidir([Requisito("empleados", "Staffing requirements apply.",
                               ("20 employees",))],
                    {"empleados": "12 employees"})
        self.assertIs(r.veredicto, Veredicto.NO_SE_PUEDE_SABER)

    def test_numeros_pelados_tambien(self):
        r = decidir([Requisito("x", "A number is required.", ("50",))],
                    {"x": "80"})
        self.assertIs(r.veredicto, Veredicto.NO_SE_PUEDE_SABER)

    def test_una_coincidencia_de_texto_sigue_valiendo(self):
        # La red va DESPUES del encaje positivo: no puede romper lo que ya
        # funcionaba.
        r = decidir([Requisito("x", "cita", ("20 employees",))],
                    {"x": "20 employees"})
        self.assertIs(r.veredicto, Veredicto.ELEGIBLE)

    def test_lo_que_no_son_cantidades_se_sigue_excluyendo(self):
        # La red no puede tragarse los casos normales: si el documento pide
        # "nonprofit" y el perfil dice "empresa privada", eso es un no.
        r = decidir([Requisito("tipo", "Open to nonprofits.", ("nonprofit",))],
                    {"tipo": "empresa privada"})
        self.assertIs(r.veredicto, Veredicto.NO_ELEGIBLE)

    def test_unidades_distintas_no_activan_la_red(self):
        # "4 years" contra "3 employees" no son la misma magnitud. Ya iban a
        # duda por otro camino; lo que importa es que no se rompa.
        r = decidir([Requisito("x", "Requirements apply.", ("3 employees",))],
                    {"x": "4 years"})
        self.assertIn(r.veredicto,
                      (Veredicto.NO_SE_PUEDE_SABER, Veredicto.NO_ELEGIBLE))
