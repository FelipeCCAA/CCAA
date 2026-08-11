"""
Levanta el bloqueo por intentos de acceso.

El límite del login existía sin forma de levantarlo: la única salida era abrir
una shell de Django dentro del contenedor y borrar una clave de caché a mano.
Eso no se le puede pedir al turno de noche cuando el jefe de planta no puede
entrar.

    python manage.py desbloquear_login --listar
    python manage.py desbloquear_login --usuario jperez
    python manage.py desbloquear_login --ip 190.44.12.7

**`--listar` no escanea la caché.** Deduce a quién mirar desde los intentos de
acceso recientes y luego consulta el contador de cada uno. Escanear claves solo
funciona con algunos backends —con Redis, Django ni siquiera expone la
operación— y un diagnóstico que deja de funcionar al cambiar de caché es un
diagnóstico que falla el día que más se necesita.
"""

from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from usuarios.models import IntentoAcceso
from usuarios.throttling import (
    LoginIPThrottle,
    LoginUsuarioThrottle,
    clave_de_ip,
    clave_de_usuario,
    desbloquear,
    estado_del_limite,
    normalizar,
)


#: Hasta dónde mirar atrás para saber a quién preguntar. La ventana del límite
#: es de una hora; dos dan margen para un reloj corrido sin traer ruido viejo.
HORAS_A_REVISAR = 2


class Command(BaseCommand):
    help = "Levanta el bloqueo del login por usuario o por dirección."

    def add_arguments(self, parser):
        parser.add_argument("--usuario", help="Nombre de la cuenta a desbloquear.")
        parser.add_argument("--ip", help="Dirección a desbloquear.")
        parser.add_argument(
            "--listar",
            action="store_true",
            help="Muestra quién está bloqueado ahora, sin cambiar nada.",
        )

    def handle(self, *args, **opciones):
        if opciones["listar"]:
            return self._listar()

        if not opciones["usuario"] and not opciones["ip"]:
            raise CommandError(
                "Indica --usuario, --ip o --listar.\n"
                "  Ejemplo: manage.py desbloquear_login --usuario jperez"
            )

        if opciones["usuario"]:
            self._soltar(
                clave_de_usuario(opciones["usuario"]),
                f"la cuenta «{normalizar(opciones['usuario'])}»",
            )

        if opciones["ip"]:
            self._soltar(
                clave_de_ip(opciones["ip"]),
                f"la dirección {opciones['ip'].strip()}",
            )

    def _soltar(self, clave, descripcion):
        if desbloquear(clave):
            self.stdout.write(self.style.SUCCESS(f"Desbloqueada {descripcion}."))
        else:
            # No es un error: puede que ya hubiera caducado sola. Decirlo evita
            # que alguien siga buscando un bloqueo que no existe.
            self.stdout.write(f"{descripcion.capitalize()} no estaba bloqueada.")

    def _listar(self):
        desde = timezone.now() - timedelta(hours=HORAS_A_REVISAR)
        recientes = IntentoAcceso.objects.filter(fecha_hora__gte=desde)

        candidatos = [
            (clave_de_usuario(nombre), f"usuario {normalizar(nombre)}", LoginUsuarioThrottle())
            for nombre in sorted({i.usuario for i in recientes if i.usuario})
        ] + [
            (clave_de_ip(ip), f"dirección {ip}", LoginIPThrottle())
            for ip in sorted({i.ip for i in recientes if i.ip})
        ]

        filas = [
            (descripcion, estado_del_limite(clave, throttle))
            for clave, descripcion, throttle in candidatos
        ]
        bloqueados = [(d, e) for d, e in filas if e["bloqueado"]]

        if not filas:
            self.stdout.write(
                f"Sin intentos de acceso en las últimas {HORAS_A_REVISAR} horas."
            )
            return

        for descripcion, estado in sorted(filas, key=lambda f: -f[1]["usados"]):
            marca = (
                self.style.ERROR("BLOQUEADO")
                if estado["bloqueado"]
                else self.style.SUCCESS("libre    ")
            )
            espera = (
                f" · se libera un hueco en {estado['libre_en'] // 60} min"
                if estado["bloqueado"]
                else ""
            )
            self.stdout.write(
                f"  {marca}  {descripcion:<40} "
                f"{estado['usados']}/{estado['limite']}{espera}"
            )

        if bloqueados:
            self.stdout.write("")
            self.stdout.write(
                "Para levantar uno: manage.py desbloquear_login --usuario <nombre>"
            )
