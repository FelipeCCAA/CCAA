from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from maestros.models import Equipo, Mandante, Producto
from produccion.models import Lote
from usuarios.models import Empresa, PerfilUsuario, Rol, Sucursal

from .models import EjecucionProceso, EntradaProceso, EtapaProceso, Proceso


class PermisosOperacionalesPorEtapaTests(TestCase):
    def setUp(self):
        self.empresa = Empresa.objects.create(rut="77.100.200-3", nombre="Permisos proceso")
        self.sucursal = Sucursal.objects.create(
            empresa=self.empresa, codigo="PER", nombre="Planta permisos"
        )
        mandante = Mandante.objects.create(
            empresa=self.empresa, codigo_cliente="PER", nombre="CCAA"
        )
        self.producto = Producto.objects.create(
            mandante=mandante, nombre="Polvo para permisos",
            familia=Producto.Familia.POLVO,
        )
        self.lote_origen = Lote.objects.create(
            sucursal=self.sucursal, codigo_lote="PER-ORIGEN",
            producto=self.producto, fecha=date(2026, 9, 2),
        )
        self.lote_salida = Lote.objects.create(
            sucursal=self.sucursal, codigo_lote="PER-SALIDA",
            producto=self.producto, fecha=date(2026, 9, 2),
        )
        proceso = Proceso.objects.create(codigo="permisos", nombre="Permisos")
        self.etapa_condensacion = EtapaProceso.objects.create(
            proceso=proceso, codigo="cond", nombre="Condensar",
            tipo=EtapaProceso.Tipo.CONDENSACION, orden=1,
        )
        self.etapa_secado = EtapaProceso.objects.create(
            proceso=proceso, codigo="sec", nombre="Secar",
            tipo=EtapaProceso.Tipo.SECADO, orden=2,
        )
        self.etapa_descremacion = EtapaProceso.objects.create(
            proceso=proceso, codigo="des", nombre="Descremar",
            tipo=EtapaProceso.Tipo.DESCREMACION, orden=3,
        )
        self.evaporador = Equipo.objects.create(
            sucursal=self.sucursal, codigo="EV-PER", nombre="Evaporador",
            tipo=Equipo.Tipo.EVAPORADOR,
        )
        self.torre = Equipo.objects.create(
            sucursal=self.sucursal, codigo="TO-PER", nombre="Torre",
            tipo=Equipo.Tipo.TORRE,
        )
        self.descremadora = Equipo.objects.create(
            sucursal=self.sucursal, codigo="DE-PER", nombre="Descremadora",
            tipo=Equipo.Tipo.DESCREMADORA,
        )
        self.condensacion = self._usuario("condensacion", PerfilUsuario.Area.CONDENSACION)
        self.secado = self._usuario("secado", PerfilUsuario.Area.SECADO)
        self.calidad = self._usuario("calidad", PerfilUsuario.Area.CALIDAD, Rol.CALIDAD)

    def _usuario(self, nombre, area, rol=Rol.PRODUCCION):
        usuario = User.objects.create_user(nombre)
        PerfilUsuario.objects.create(
            usuario=usuario, empresa=self.empresa, sucursal=self.sucursal,
            area=area, rol=rol,
        )
        return usuario

    @staticmethod
    def _cliente(usuario):
        cliente = APIClient()
        cliente.force_authenticate(usuario)
        return cliente

    def _crear_ejecucion(self, usuario, codigo, etapa, equipo):
        return self._cliente(usuario).post(
            "/api/procesos/ejecuciones/",
            {"codigo": codigo, "etapa": etapa.pk, "equipo": equipo.pk},
            format="json",
        )

    def test_alta_generica_solo_conserva_descremacion_y_su_area(self):
        self.assertEqual(
            self._crear_ejecucion(
                self.secado, "EJ-SEC-PER", self.etapa_secado, self.torre
            ).status_code,
            405,
        )
        self.assertEqual(
            self._crear_ejecucion(
                self.secado, "EJ-DES-NO", self.etapa_descremacion,
                self.descremadora,
            ).status_code,
            403,
        )
        self.assertEqual(
            self._crear_ejecucion(
                self.condensacion, "EJ-DES-PER", self.etapa_descremacion,
                self.descremadora,
            ).status_code,
            201,
        )
        self.assertEqual(
            self._crear_ejecucion(
                self.condensacion, "EJ-SEC-NO", self.etapa_secado, self.torre
            ).status_code,
            403,
        )

    def test_calidad_puede_consultar_pero_no_operar(self):
        cliente = self._cliente(self.calidad)

        self.assertEqual(cliente.get("/api/procesos/ejecuciones/").status_code, 200)
        self.assertEqual(
            cliente.post(
                "/api/procesos/ejecuciones/",
                {"codigo": "EJ-CAL-NO", "etapa": self.etapa_secado.pk,
                 "equipo": self.torre.pk},
                format="json",
            ).status_code,
            403,
        )

    def test_permiso_de_detalle_protege_la_etapa(self):
        ejecucion = EjecucionProceso.objects.create(
            sucursal=self.sucursal, codigo="EJ-SEC-DET",
            etapa=self.etapa_secado, equipo=self.torre, responsable=self.secado,
        )

        denegada = self._cliente(self.condensacion).patch(
            f"/api/procesos/ejecuciones/{ejecucion.pk}/",
            {"observaciones": "No corresponde"}, format="json",
        )
        permitida = self._cliente(self.secado).patch(
            f"/api/procesos/ejecuciones/{ejecucion.pk}/",
            {"observaciones": "Control del turno"}, format="json",
        )

        self.assertEqual(denegada.status_code, 403)
        self.assertEqual(permitida.status_code, 200, permitida.data)

    def test_salida_explicita_respeta_permiso_y_balance(self):
        ejecucion = EjecucionProceso.objects.create(
            sucursal=self.sucursal, codigo="EJ-SEC-SAL",
            etapa=self.etapa_secado, equipo=self.torre, responsable=self.secado,
        )
        EntradaProceso.objects.create(
            ejecucion=ejecucion, lote=self.lote_origen, cantidad=100, unidad="kg"
        )
        datos = {
            "lote": self.lote_salida.pk, "cantidad": "100", "unidad": "kg",
            "naturaleza": "principal",
        }

        denegada = self._cliente(self.condensacion).post(
            f"/api/procesos/ejecuciones/{ejecucion.pk}/registrar-salida/",
            datos, format="json",
        )
        permitida = self._cliente(self.secado).post(
            f"/api/procesos/ejecuciones/{ejecucion.pk}/registrar-salida/",
            datos, format="json",
        )

        self.assertEqual(denegada.status_code, 403)
        self.assertEqual(permitida.status_code, 201, permitida.data)

    def test_rework_explicito_exige_area_y_autorizacion(self):
        from calidad.models import Liberacion

        Liberacion.objects.create(
            lote=self.lote_origen, estado=Liberacion.Estado.LIBERADO
        )
        ejecucion = EjecucionProceso.objects.create(
            sucursal=self.sucursal, codigo="EJ-SEC-RW",
            etapa=self.etapa_secado, equipo=self.torre, responsable=self.secado,
        )
        datos = {
            "lote": self.lote_origen.pk, "cantidad": "25",
            "motivo": "Rework aprobado para mezcla controlada",
        }

        denegada = self._cliente(self.condensacion).post(
            f"/api/procesos/ejecuciones/{ejecucion.pk}/incorporar-rework/",
            datos, format="json",
        )
        permitida = self._cliente(self.secado).post(
            f"/api/procesos/ejecuciones/{ejecucion.pk}/incorporar-rework/",
            datos, format="json",
        )

        self.assertEqual(denegada.status_code, 403)
        self.assertEqual(permitida.status_code, 201, permitida.data)
        self.assertEqual(
            EntradaProceso.objects.get(ejecucion=ejecucion).tipo,
            EntradaProceso.Tipo.REPROCESO,
        )

    def test_altas_crudas_especializadas_quedan_cerradas(self):
        cliente = self._cliente(self.condensacion)

        self.assertEqual(cliente.post("/api/procesos/condensaciones/", {}).status_code, 405)
        self.assertEqual(cliente.post("/api/procesos/mantequillas/", {}).status_code, 405)
