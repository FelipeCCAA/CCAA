import uuid
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from calidad.models import LiberacionProceso
from maestros.models import (
    Equipo, Especificacion, Mandante, Producto, Receta, RecetaComponente,
)
from procesos.models import EjecucionProceso, EtapaProceso, Proceso, SalidaProceso
from inventario.models import (
    Bodega, Existencia, ExistenciaProductoTerminado, Insumo, LoteInventario,
    MovimientoInventario, MovimientoProductoTerminado, Ubicacion,
)
from inventario.servicios import consumir_receta_produccion, registrar_entrada
from usuarios.models import Empresa, PerfilUsuario, Rol, Sucursal

from .models import Analisis, Lote, PalletProducto, RegistroEnvase
from .servicios import registrar_envasado
from .serializers import RegistroEnvaseSerializer


class EnvasePalletTests(TestCase):
    def setUp(self):
        empresa = Empresa.objects.create(rut="ENV-1", nombre="Empresa envase")
        self.planta = Sucursal.objects.create(
            empresa=empresa, codigo="ENV", nombre="Planta envase"
        )
        self.usuario = User.objects.create_user("operador-envase")
        PerfilUsuario.objects.create(
            usuario=self.usuario, empresa=empresa, sucursal=self.planta,
            rol=Rol.PRODUCCION, area=PerfilUsuario.Area.ENVASE,
        )
        mandante = Mandante.objects.create(
            empresa=empresa, nombre="Mandante envase", codigo_cliente="env"
        )
        self.producto = Producto.objects.create(
            mandante=mandante, nombre="Leche en polvo", unidad_base="kg"
        )
        self.lote = Lote.objects.create(
            sucursal=self.planta, codigo_lote="L-ENV-1", producto=self.producto,
            fecha=date(2026, 8, 17), estado=Lote.Estado.PRODUCIDO,
            kg_producidos=Decimal("1000"),
        )
        self.envasadora = Equipo.objects.create(
            sucursal=self.planta, codigo="rovema-test", nombre="Rovema test",
            tipo=Equipo.Tipo.ENVASADORA,
        )

    def registrar(self, *, clave=None, pallets=None):
        inicio = timezone.now() - timedelta(hours=1)
        return registrar_envasado(
            lote_id=self.lote.pk, equipo=self.envasadora, formato_kg="25",
            inicio=inicio, termino=timezone.now(), usuario=self.usuario,
            operacion_id=clave,
            pallets=pallets or [
                {"codigo": "PAL-001", "unidades": 20, "kg_neto": "500"},
                {"codigo": "PAL-002", "unidades": 20, "kg_neto": "500"},
            ],
        )

    def test_registra_envase_y_pallets_sobre_el_mismo_lote(self):
        registro = self.registrar()

        self.assertEqual(registro.lote, self.lote)
        self.assertEqual(registro.unidades, 40)
        self.assertEqual(registro.kg_envasados, Decimal("1000"))
        self.assertEqual(registro.pallets.count(), 2)
        self.assertTrue(all(
            pallet.estado == PalletProducto.Estado.PENDIENTE_CALIDAD
            for pallet in registro.pallets.all()
        ))
        existencias = ExistenciaProductoTerminado.objects.filter(
            pallet__envase=registro, activo=True,
        )
        self.assertEqual(existencias.count(), 2)
        self.assertTrue(all(
            existencia.ubicacion.tipo == Ubicacion.Tipo.CUARENTENA
            for existencia in existencias.select_related("ubicacion")
        ))
        self.assertEqual(MovimientoProductoTerminado.objects.count(), 2)
        datos = RegistroEnvaseSerializer(registro).data
        self.assertIn("operador_nombre", datos)
        self.assertTrue(datos["inicio"])

    def test_clave_idempotente_no_duplica_pallets(self):
        clave = uuid.uuid4()
        primero = self.registrar(clave=clave)
        segundo = self.registrar(clave=clave)

        self.assertEqual(primero.pk, segundo.pk)
        self.assertEqual(RegistroEnvase.objects.count(), 1)
        self.assertEqual(PalletProducto.objects.count(), 2)
        self.assertEqual(ExistenciaProductoTerminado.objects.count(), 2)
        self.assertEqual(MovimientoProductoTerminado.objects.count(), 2)

    def test_no_permite_envasar_mas_de_lo_producido(self):
        with self.assertRaises(ValidationError):
            self.registrar(pallets=[
                {"codigo": "PAL-EXCESO", "unidades": 41, "kg_neto": "1025"}
            ])

        self.assertEqual(RegistroEnvase.objects.count(), 0)
        self.assertEqual(PalletProducto.objects.count(), 0)

    def test_un_producto_intermedio_no_aparece_como_producto_envasable(self):
        self.producto.naturaleza = Producto.Naturaleza.INTERMEDIO
        self.producto.save(update_fields=["naturaleza"])

        with self.assertRaises(ValidationError):
            self.registrar(pallets=[
                {"codigo": "PAL-INTERMEDIO", "unidades": 20, "kg_neto": "500"}
            ])

        self.assertEqual(RegistroEnvase.objects.count(), 0)

    def test_mantequilla_exige_liberacion_intermedia_antes_de_envasar(self):
        proceso = Proceso.objects.create(codigo="ruta-mant-env", nombre="Mantequilla")
        etapa = EtapaProceso.objects.create(
            proceso=proceso, codigo="batido", nombre="Batido",
            tipo=EtapaProceso.Tipo.MANTEQUILLA, orden=1, requiere_calidad=True,
        )
        ejecucion = EjecucionProceso.objects.create(
            codigo="EJ-MANT-ENV", etapa=etapa, sucursal=self.planta,
            estado=EjecucionProceso.Estado.PENDIENTE_CONTROL,
        )
        salida = SalidaProceso.objects.create(
            ejecucion=ejecucion, lote=self.lote,
            naturaleza=SalidaProceso.Naturaleza.PRINCIPAL,
            clasificacion=SalidaProceso.Clasificacion.GRANEL,
            destino=SalidaProceso.Destino.ENVASADO,
            cantidad=Decimal("1000"), unidad="kg",
        )
        decision = LiberacionProceso.objects.create(salida=salida)

        with self.assertRaisesMessage(ValidationError, "pendiente de aprobación"):
            self.registrar()

        especificacion = Especificacion.objects.create(
            producto=self.producto, version=1, vigente_desde=date(2026, 1, 1),
            rangos={"humedad": {"min": 0, "max": 5, "obligatorio": True}},
        )
        analisis = Analisis.objects.create(
            lote=self.lote, fecha=date(2026, 8, 17),
            valores={"humedad": 3}, especificacion=especificacion,
        )
        decision.estado = LiberacionProceso.Estado.LIBERADO
        decision.analisis_lote = analisis
        decision.decidida_por = self.usuario
        decision.decidida_en = timezone.now()
        decision.full_clean()
        decision.save()

        registro = self.registrar()
        self.assertEqual(registro.lote, self.lote)

    def test_simulacion_pallet_25kg_consume_envases_y_respeta_500kg(self):
        """20 sacos + 1 pallet físico producen exactamente un pallet de 500 kg."""
        bolsa = Insumo.objects.create(
            empresa=self.planta.empresa, codigo="ENV-SACO-25", nombre="Saco 25 kg",
            categoria=Insumo.Categoria.EMPAQUE, area=PerfilUsuario.Area.ENVASE,
            unidad=Insumo.Unidad.UN, requiere_calidad=False,
        )
        base = Insumo.objects.create(
            empresa=self.planta.empresa, codigo="ENV-PALLET-500", nombre="Pallet base 500 kg",
            categoria=Insumo.Categoria.EMPAQUE, area=PerfilUsuario.Area.ENVASE,
            unidad=Insumo.Unidad.UN, requiere_calidad=False,
        )
        receta = Receta.objects.create(
            producto=self.producto, version=1, cantidad_base=Decimal("500"),
            vigente_desde=date(2026, 1, 1), fuente="Simulación pallet 25 kg",
        )
        RecetaComponente.objects.create(
            receta=receta, insumo=bolsa, cantidad=Decimal("20"), unidad="un",
        )
        RecetaComponente.objects.create(
            receta=receta, insumo=base, cantidad=Decimal("1"), unidad="un",
        )
        bodega = Bodega.objects.create(
            sucursal=self.planta, codigo="B-ENV", nombre="Envases",
            area=PerfilUsuario.Area.BODEGA,
        )
        disponible = Ubicacion.objects.create(
            bodega=bodega, codigo="ENV-DISP", tipo=Ubicacion.Tipo.DISPONIBLE,
        )
        for insumo, cantidad in ((bolsa, 20), (base, 1)):
            lote_material = LoteInventario.objects.create(
                sucursal=self.planta, insumo=insumo, codigo=f"SIM-{insumo.codigo}",
                estado_calidad=LoteInventario.EstadoCalidad.NO_REQUIERE,
            )
            registrar_entrada(
                lote=lote_material, ubicacion=disponible, cantidad=cantidad,
                usuario=self.usuario, documento_tipo="simulacion", documento_id=insumo.pk,
            )

        self.lote.kg_producidos = Decimal("500")
        self.lote.save(update_fields=["kg_producidos"])
        consumo, movimientos = consumir_receta_produccion(
            lote_produccion=self.lote, usuario=self.usuario,
        )
        registro = self.registrar(pallets=[
            {"codigo": "PAL-SIM-25KG", "unidades": 20, "kg_neto": "500"}
        ])

        pallet = registro.pallets.get()
        self.assertEqual((pallet.unidades, pallet.kg_neto), (20, Decimal("500")))
        self.assertEqual(consumo.kg_base, Decimal("500"))
        self.assertEqual(
            sorted(m.cantidad for m in movimientos), [Decimal("1.000"), Decimal("20.000")]
        )
        self.assertTrue(all(e.cantidad_fisica == 0 for e in Existencia.objects.all()))
        self.assertEqual(MovimientoInventario.objects.filter(tipo="consumo").count(), 2)
