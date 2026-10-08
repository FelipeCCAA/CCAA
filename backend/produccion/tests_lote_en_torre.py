from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError

from maestros.models import Equipo
from procesos.models import CorridaSecado, EjecucionProceso, EtapaProceso
from recepcion.models import MovimientoSilo

from . import servicios
from .models import Lote
from .servicios import MENSAJE_LOTE_EN_TORRE
from .tests_borrador import BaseBorradorLote


class LoteEnTorreTests(BaseBorradorLote):
    """
    Un lote en torre nace solo desde el puesto de Secado: tomando el
    concentrado que Calidad liberó, no abriéndolo desde el vale. Por los tres
    caminos que abren un lote, el rechazo no deja nada escrito.
    """

    def assertNadaCreado(self):
        self.assertEqual(MovimientoSilo.objects.count(), 0)
        self.assertFalse(EjecucionProceso.objects.filter(equipo=self.equipo).exists())
        self.assertFalse(CorridaSecado.objects.exists())

    def datos_torre(self):
        return {**self.datos_completos(), "equipo": self.equipo.id, "linea": "E1"}

    def test_el_servicio_no_abre_un_lote_en_torre(self):
        with self.assertRaises(ValidationError) as error:
            servicios.abrir_lote_desde_vale(
                vale=self.vale, codigo_lote="TORRE-SRV", fecha=date(2026, 7, 16),
                litros=Decimal("1000"), equipo=self.equipo,
            )

        self.assertEqual(error.exception.message_dict["equipo"], [MENSAJE_LOTE_EN_TORRE])
        self.assertFalse(Lote.objects.filter(codigo_lote="TORRE-SRV").exists())
        self.assertNadaCreado()

    def test_el_servicio_no_abre_un_lote_sin_maquina(self):
        """Sin máquina, el mapa máquina → etapa caía en Secado por defecto."""
        with self.assertRaises(ValidationError) as error:
            servicios.abrir_lote_desde_vale(
                vale=self.vale, codigo_lote="SIN-MAQUINA", fecha=date(2026, 7, 16),
                litros=Decimal("1000"),
            )

        self.assertIn("equipo", error.exception.message_dict)
        self.assertFalse(Lote.objects.filter(codigo_lote="SIN-MAQUINA").exists())
        self.assertNadaCreado()

    def test_confirmar_borrador_en_torre_responde_400_sin_tocar_nada(self):
        borrador = self.crear_borrador(**self.datos_torre())

        respuesta = self.cliente.post(
            f"/api/produccion/lotes/{borrador['id']}/confirmar-borrador/"
        )

        self.assertEqual(respuesta.status_code, 400, respuesta.json())
        self.assertEqual(respuesta.json(), {"equipo": MENSAJE_LOTE_EN_TORRE})
        self.assertEqual(Lote.objects.get(pk=borrador["id"]).estado, Lote.Estado.BORRADOR)
        self.assertNadaCreado()

    def test_el_alta_directa_rechaza_una_torre(self):
        respuesta = self.cliente.post(
            "/api/produccion/lotes/",
            {
                "codigo_lote": "CCAA6197E1-09", "producto": self.polvo.id,
                "vale": self.vale.id, "litros_estandarizados": "1000",
                "fecha": "2026-07-16", "linea": "E1", "equipo": self.equipo.id,
            },
            format="json",
        )

        self.assertEqual(respuesta.status_code, 400, respuesta.data)
        self.assertIn(MENSAJE_LOTE_EN_TORRE, str(respuesta.data["equipo"]))
        self.assertFalse(Lote.objects.filter(codigo_lote="CCAA6197E1-09").exists())
        self.assertNadaCreado()

    def ofrecidos(self):
        respuesta = self.cliente.get("/api/produccion/lotes/opciones-inicio/")
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        return {equipo["id"] for equipo in respuesta.data["equipos"]}

    def test_opciones_inicio_no_ofrece_torres_aunque_la_ruta_empiece_en_secado(self):
        # Control positivo: con la ruta en Envasado la línea sí se ofrece, así
        # que el «no se ofrece» de abajo no es una lista vacía por otra causa.
        self.assertIn(self.linea_envasado.id, self.ofrecidos())

        EtapaProceso.objects.filter(codigo="primera-borrador").update(
            tipo=EtapaProceso.Tipo.SECADO
        )

        respuesta = self.cliente.get("/api/produccion/lotes/opciones-inicio/")

        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        ofrecidos = {equipo["id"] for equipo in respuesta.data["equipos"]}
        self.assertNotIn(self.equipo.id, ofrecidos)
        self.assertNotIn(self.otro_equipo.id, ofrecidos)

    def test_opciones_inicio_no_ofrece_maquinas_que_el_servidor_rechaza(self):
        """
        Una ruta que empieza en Transferencia pide máquinas de carga, y abrir
        un lote desde el vale sobre una de ellas cae en Secado y se rechaza
        (`abre_desde_vale`): ofrecerla es ofrecer un rechazo.
        """
        carga = Equipo.objects.create(
            sucursal=self.sucursal, codigo="carga-borrador", nombre="Punto de carga",
            tipo=Equipo.Tipo.CARGA, sigla="C1",
        )
        EtapaProceso.objects.filter(codigo="primera-borrador").update(
            tipo=EtapaProceso.Tipo.TRANSFERENCIA
        )

        self.assertNotIn(carga.id, self.ofrecidos())
        with self.assertRaises(ValidationError):
            servicios.abrir_lote_desde_vale(
                vale=self.vale, codigo_lote="CARGA-SRV", fecha=date(2026, 7, 16),
                litros=Decimal("1000"), equipo=carga,
            )

    def test_abre_desde_vale_es_la_regla_de_la_guarda(self):
        for tipo in Equipo.Tipo.values:
            with self.subTest(tipo=tipo):
                self.assertEqual(
                    servicios.abre_desde_vale(tipo),
                    servicios.tipo_etapa_de_apertura(Equipo(tipo=tipo)) != EtapaProceso.Tipo.SECADO,
                )
        self.assertEqual(
            {tipo for tipo in Equipo.Tipo.values if servicios.abre_desde_vale(tipo)},
            {Equipo.Tipo.EVAPORADOR, Equipo.Tipo.ENVASADORA, Equipo.Tipo.LINEA},
        )

    def test_una_maquina_que_no_es_torre_no_habla_de_secado(self):
        """
        Una mantequera, una descremadora o un punto de carga no abren desde un
        vale, pero tampoco son una torre: el rechazo dice qué máquina es y no
        manda a Secado.
        """
        for tipo, codigo in (
            (Equipo.Tipo.MANTEQUERA, "mant-vale"),
            (Equipo.Tipo.DESCREMADORA, "desc-vale"),
            (Equipo.Tipo.CARGA, "carga-vale"),
        ):
            equipo = Equipo.objects.create(
                sucursal=self.sucursal, codigo=codigo, nombre=f"Máquina {codigo}", tipo=tipo,
            )
            with self.subTest(tipo=tipo), self.assertRaises(ValidationError) as error:
                servicios.abrir_lote_desde_vale(
                    vale=self.vale, codigo_lote=f"{codigo}-SRV", fecha=date(2026, 7, 16),
                    litros=Decimal("1000"), equipo=equipo,
                )
            mensaje = error.exception.message_dict["equipo"][0]
            self.assertEqual(
                mensaje,
                f"Máquina {codigo} no abre lotes desde un vale: desde un vale abren lote "
                "solo evaporadores, envasadoras y líneas.",
            )
            self.assertNotIn("Secado", mensaje)
        self.assertNadaCreado()
