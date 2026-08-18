import uuid
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from maestros.models import Silo
from usuarios.models import PerfilUsuario, Rol

from .models import MovimientoSilo


class MovimientosSiloOperacionalesTests(TestCase):
    def setUp(self):
        self.usuario = User.objects.create_user(username="recepcion-silos", password="x")
        PerfilUsuario.objects.create(usuario=self.usuario, rol=Rol.RECEPCION)
        self.cliente = APIClient()
        self.cliente.credentials(
            HTTP_AUTHORIZATION=f"Token {Token.objects.create(user=self.usuario).key}"
        )
        self.origen = Silo.objects.create(
            codigo="ORIGEN", tipo=Silo.Tipo.SILO, capacidad_l=1000
        )
        self.destino = Silo.objects.create(
            codigo="DESTINO", tipo=Silo.Tipo.SILO, capacidad_l=600
        )
        MovimientoSilo.objects.create(
            silo=self.origen, tipo=MovimientoSilo.Tipo.INGRESO,
            litros=Decimal("800"), fecha_hora=timezone.now(),
        )

    def transferir(self, clave, litros="300"):
        return self.cliente.post(
            "/api/recepcion/movimientos/transferir/",
            {
                "silo_origen": self.origen.pk,
                "silo_destino": self.destino.pk,
                "litros": litros,
                "operacion_id": str(clave),
            },
            format="json",
        )

    def test_transferencia_crea_dos_asientos_y_conserva_saldos(self):
        respuesta = self.transferir(uuid.uuid4())

        self.assertEqual(respuesta.status_code, 201)
        self.assertEqual(MovimientoSilo.objects.count(), 3)
        self.assertEqual(
            sum(
                -m.litros if m.tipo == MovimientoSilo.Tipo.SALIDA else m.litros
                for m in self.origen.movimientos.all()
            ),
            Decimal("500"),
        )
        self.assertEqual(self.destino.movimientos.get().litros, Decimal("300"))

    def test_reintento_con_misma_clave_no_duplica_transferencia(self):
        clave = uuid.uuid4()
        self.assertEqual(self.transferir(clave).status_code, 201)
        self.assertEqual(self.transferir(clave).status_code, 201)
        self.assertEqual(MovimientoSilo.objects.filter(operacion_id=clave).count(), 2)

    def test_no_consume_silo_bloqueado_por_calidad(self):
        self.origen.estado = Silo.Estado.BLOQUEADO_CALIDAD
        self.origen.save(update_fields=["estado"])

        respuesta = self.transferir(uuid.uuid4())

        self.assertEqual(respuesta.status_code, 400)
        self.assertEqual(MovimientoSilo.objects.count(), 1)

    def test_no_permita_saldo_negativo_ni_sobrecapacidad(self):
        self.assertEqual(self.transferir(uuid.uuid4(), "900").status_code, 400)
        MovimientoSilo.objects.create(
            silo=self.destino, tipo=MovimientoSilo.Tipo.INGRESO,
            litros=Decimal("500"), fecha_hora=timezone.now(),
        )
        self.assertEqual(self.transferir(uuid.uuid4(), "200").status_code, 400)

    def test_movimiento_confirmado_no_se_edita_ni_elimina(self):
        movimiento = self.origen.movimientos.first()
        ruta = f"/api/recepcion/movimientos/{movimiento.pk}/"

        self.assertEqual(self.cliente.patch(ruta, {"litros": "1"}).status_code, 405)
        self.assertEqual(self.cliente.delete(ruta).status_code, 405)
