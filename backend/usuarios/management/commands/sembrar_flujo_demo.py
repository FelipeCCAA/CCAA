"""
Un día de planta completo, de la leche cruda al lote analizado.

Sirve para mirar la aplicación con datos que se sostienen entre sí: el silo tiene
lo que las recepciones metieron, el vale movió esos litros, y el lote consumió
del silo que el vale llenó. Un sembrado que inventa cada tabla por separado se
ve bien en cada pantalla y no cuadra en ninguna cuenta.

**Pasa por los servicios de dominio, no por escrituras sueltas.** La
estandarización llama a `transferir`, `iniciar_agitacion`, `registrar_muestra` y
`decidir`; el veredicto de la recepción lo calcula `recepcion.dominio`. Si una
regla cambia, este sembrado falla — que es exactamente lo que se quiere de él.

La única concesión es el reloj: los treinta minutos de agitación se retrasan
escribiendo `agitacion_desde` hacia atrás. La alternativa era esperar media hora
o saltarse la regla, y saltársela dejaría un vale liberado contra una muestra
que el sistema no habría aceptado.

El producto es el que **tiene especificación vigente**, para que el análisis del
lote se pueda contrastar contra algo. Sin eso el expediente diría «sin
especificación» y el sembrado no mostraría lo que se quiere mostrar.
"""

from datetime import date, time, timedelta
from decimal import Decimal
import uuid

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from estandarizacion import servicios
from estandarizacion.dominio import Leche, calcular_mezcla
from estandarizacion.models import ValeEstandarizacion
from maestros.models import Especificacion, Silo, Vehiculo
from produccion.dominio import generar_codigo_lote
from produccion.models import Analisis, Lote
from recepcion import dominio as dominio_recepcion
from recepcion.models import MovimientoSilo, Recepcion
from usuarios.models import Sucursal


# Controles de una leche que entra conforme. Son los que el dominio exige para
# dar la recepción por analizada; con uno menos queda pendiente y no se libera.
CONTROLES_CONFORMES = {
    "temperatura": 4.0,
    "acidez": 0.15,
    "ph": 6.7,
    "crioscopia": -0.520,
    "delvo": "Negativo",
    "inhibidores": "Negativo",
    "organoleptico": "Conforme",
}

# Composición de la leche que se recibe y de la descremada del TK. De aquí sale
# la mezcla, y el RC objetivo se elige para que el vale salga liberado.
ENTERA = Leche(cantidad=27000.0, grasa=3.60, sng=8.60)
DESCREMADA = Leche(cantidad=10000.0, grasa=0.05, sng=8.90)


class Command(BaseCommand):
    help = "Siembra un flujo completo: recepción → estandarización → lote analizado."

    def add_arguments(self, parser):
        parser.add_argument(
            "--aplicar",
            action="store_true",
            help="Escribe de verdad. Sin esto simula y revierte.",
        )
        parser.add_argument(
            "--fecha",
            default=None,
            help="Día de la corrida, ISO. Por omisión, hoy.",
        )

    def handle(self, *args, **opciones):
        self.fecha = (
            date.fromisoformat(opciones["fecha"]) if opciones["fecha"] else date.today()
        )
        aplicar = opciones["aplicar"]

        with transaction.atomic():
            resumen = self._sembrar()

            if not aplicar:
                transaction.set_rollback(True)

        for linea in resumen:
            self.stdout.write(linea)

        if aplicar:
            self.stdout.write(self.style.SUCCESS("Sembrado."))
        else:
            self.stdout.write(
                self.style.WARNING(
                    "Simulación: nada se guardó. Repite con --aplicar.\n"
                    "Se recorrio el mismo camino y se revirtio, en vez de "
                    "calcular aparte lo que habria pasado."
                )
            )

    # ------------------------------------------------------------------ pasos

    def _sembrar(self):
        contexto = self._contexto()
        lineas = ["", "=== 1. Recepcion de leche cruda ==="]

        recepciones = self._recepcionar(contexto)
        for recepcion in recepciones:
            lineas.append(
                f"  modulo {recepcion.modulo}: {recepcion.litros} L -> "
                f"{recepcion.silo.codigo} ({recepcion.get_estado_display()})"
            )

        lineas += ["", "=== 2. Estandarizacion ==="]
        vale, evaluacion = self._estandarizar(contexto)
        lineas += [
            f"  vale {vale.codigo}: {vale.volumen} L de RC objetivo {vale.rc_objetivo}",
            f"    entera {vale.litros_entera} L de {vale.silo_entera.codigo}",
            f"    descremada {vale.litros_descremada} L de {vale.silo_descremada.codigo}",
            f"    -> {vale.silo_destino.codigo}",
            f"    muestra: grasa {vale.grasa_real} / SNG {vale.sng_real} "
            f"= RC {vale.rc_real:.4f}",
            f"    {vale.get_estado_display().upper()} — {evaluacion.motivo}",
        ]

        lineas += ["", "=== 3. Lote y analisis de calidad ==="]
        lote, analisis, veredicto = self._producir(contexto, vale)
        lineas += [
            f"  lote {lote.codigo_lote} | {lote.producto.nombre}",
            f"    {lote.kg_producidos} kg desde {vale.volumen} L de "
            f"{vale.silo_destino.codigo}",
            f"    especificacion v{analisis.especificacion.version}: "
            + ", ".join(
                f"{k} {v['min']}-{v['max']}"
                for k, v in analisis.especificacion.rangos.items()
            ),
            "    medido: "
            + ", ".join(f"{k} {v}" for k, v in analisis.valores.items()),
            f"    veredicto: {veredicto}",
        ]

        return lineas

    def _contexto(self):
        especificacion = (
            Especificacion.objects.select_related("producto")
            .filter(vigente_desde__lte=self.fecha)
            .order_by("-vigente_desde")
            .first()
        )

        if especificacion is None:
            raise CommandError(
                "No hay ninguna especificación vigente: sin ella el análisis del "
                "lote no se puede contrastar y el sembrado no mostraría nada."
            )

        sucursal = Sucursal.objects.filter(activa=True).first()
        operador = User.objects.filter(is_active=True).order_by("pk").first()
        vehiculo = Vehiculo.objects.filter(activo=True).first()

        silos = list(Silo.objects.filter(activo=True, tipo=Silo.Tipo.SILO).order_by("pk"))
        tanques = list(Silo.objects.filter(activo=True, tipo=Silo.Tipo.TK_LD).order_by("pk"))

        if len(silos) < 2 or not tanques:
            raise CommandError(
                "Hacen falta al menos dos silos de leche y un TK de descremada."
            )

        return {
            "especificacion": especificacion,
            "producto": especificacion.producto,
            "sucursal": sucursal,
            "operador": operador,
            "vehiculo": vehiculo,
            "silo_recepcion": silos[0],
            "silo_destino": silos[1],
            "tanque": tanques[0],
        }

    def _recepcionar(self, contexto):
        """Un camión de dos módulos, hasta dejar la leche en el silo."""
        llegada = uuid.uuid4()
        creadas = []

        for numero, litros in ((1, Decimal("14000.00")), (2, Decimal("13000.00"))):
            recepcion = Recepcion.objects.create(
                sucursal=contexto["sucursal"],
                llegada_id=llegada,
                fecha=self.fecha,
                hora=time(6, 30),
                guia=f"G-{self.fecha:%Y%m%d}-01",
                vehiculo=contexto["vehiculo"],
                modulo=f"M{numero}",
                procedencia="Nestlé",
                tipo_leche="Entera",
                litros=litros,
                operador=contexto["operador"],
                turno="A",
                estado=Recepcion.Estado.REGISTRADA,
            )

            # Muestra, y decisión de Calidad calculada por el dominio: el estado
            # no se escribe a mano, se deduce de lo medido.
            recepcion.codigo_muestra = f"M-{self.fecha:%Y%m%d}-{numero:02d}"
            recepcion.muestreado_por = contexto["operador"]
            recepcion.muestreado_en = timezone.now()
            recepcion.controles = dict(CONTROLES_CONFORMES)

            evaluacion = dominio_recepcion.evaluar_recepcion(recepcion.controles)

            if not evaluacion.liberable:
                raise CommandError(
                    f"Los controles del sembrado no liberan: {evaluacion.motivos}"
                )

            recepcion.estado = Recepcion.Estado.LIBERADA
            recepcion.calidad_por = contexto["operador"]
            recepcion.calidad_en = timezone.now()
            recepcion.silo = contexto["silo_recepcion"]
            recepcion.silo_asignado_por = contexto["operador"]
            recepcion.silo_asignado_en = timezone.now()
            recepcion.save()

            MovimientoSilo.objects.create(
                silo=recepcion.silo,
                tipo=MovimientoSilo.Tipo.INGRESO,
                litros=recepcion.litros,
                fecha_hora=timezone.now(),
                origen_tipo=MovimientoSilo.OrigenTipo.RECEPCION,
                origen_id=recepcion.id,
            )

            recepcion.estado = Recepcion.Estado.DESCARGADA
            recepcion.save(update_fields=["estado"])
            creadas.append(recepcion)

        # El TK de descremada se carga como ajuste: el descremado todavía no
        # está modelado, y fingir una recepción de leche descremada sería
        # inventarse un camión que nunca llegó.
        MovimientoSilo.objects.create(
            silo=contexto["tanque"],
            tipo=MovimientoSilo.Tipo.INGRESO,
            litros=Decimal("10000.00"),
            fecha_hora=timezone.now(),
            origen_tipo=MovimientoSilo.OrigenTipo.AJUSTE,
            motivo="Carga inicial de leche descremada para la demostración.",
        )

        return creadas

    def _estandarizar(self, contexto):
        volumen = 20000.0
        rc_objetivo = 0.4000

        mezcla = calcular_mezcla(
            entera=ENTERA,
            descremada=DESCREMADA,
            rc_objetivo=rc_objetivo,
            volumen=volumen,
        )

        # El vale no lleva sucursal propia: la hereda de sus silos.
        vale = ValeEstandarizacion.objects.create(
            codigo=f"VE-{self.fecha:%Y%m%d}-01",
            fecha=self.fecha,
            producto=contexto["producto"],
            rc_objetivo=Decimal(str(rc_objetivo)),
            volumen=Decimal(str(volumen)),
            silo_entera=contexto["silo_recepcion"],
            silo_descremada=contexto["tanque"],
            silo_destino=contexto["silo_destino"],
            entera_grasa=Decimal(str(ENTERA.grasa)),
            entera_sng=Decimal(str(ENTERA.sng)),
            descremada_grasa=Decimal(str(DESCREMADA.grasa)),
            descremada_sng=Decimal(str(DESCREMADA.sng)),
            litros_entera=Decimal(str(round(mezcla.entera, 2))),
            litros_descremada=Decimal(str(round(mezcla.descremada, 2))),
            estado=ValeEstandarizacion.Estado.CALCULADO,
            responsable=contexto["operador"],
        )

        servicios.transferir(vale_id=vale.pk, usuario=contexto["operador"])
        servicios.iniciar_agitacion(vale_id=vale.pk)

        # Los treinta minutos, hacia atrás. Es la única regla que este sembrado
        # no puede cumplir esperando, y se retrasa el reloj en vez de saltarse
        # la comprobación: así el vale queda liberado contra una muestra que el
        # sistema sí habría aceptado.
        ValeEstandarizacion.objects.filter(pk=vale.pk).update(
            agitacion_desde=timezone.now() - timedelta(minutes=35)
        )

        # La mezcla salió como se calculó: la muestra confirma el RC objetivo.
        servicios.registrar_muestra(
            vale_id=vale.pk,
            grasa=Decimal(str(round(mezcla.grasa_esperada, 2))),
            sng=Decimal(str(round(mezcla.sng_esperado, 2))),
        )

        vale, evaluacion = servicios.decidir(
            vale_id=vale.pk, usuario=contexto["operador"]
        )

        if vale.estado != ValeEstandarizacion.Estado.LIBERADO:
            raise CommandError(
                f"El vale del sembrado no quedó liberado: {evaluacion.motivo}"
            )

        return vale, evaluacion

    def _producir(self, contexto, vale):
        producto = contexto["producto"]
        codigo = generar_codigo_lote(
            fecha=self.fecha, sku=producto.codigo, correlativo=1
        )

        lote = Lote.objects.create(
            sucursal=contexto["sucursal"],
            codigo_lote=codigo,
            producto=producto,
            fecha=self.fecha,
            linea="E1",
            turno="A",
            hora_inicio=time(8, 0),
            estado=Lote.Estado.EN_PROCESO,
        )

        # La leche sale del silo que llenó el vale: es lo que hace que el saldo
        # cuadre con lo que la pantalla de silos muestra.
        MovimientoSilo.objects.create(
            silo=vale.silo_destino,
            tipo=MovimientoSilo.Tipo.SALIDA,
            litros=vale.volumen,
            fecha_hora=timezone.now(),
            origen_tipo=MovimientoSilo.OrigenTipo.LOTE,
            origen_id=lote.id,
            motivo=f"Asignación de leche al lote {lote.codigo_lote}",
        )

        # Rendimiento aproximado de leche a polvo: unos 8,5 kg por cada 100 L.
        lote.kg_producidos = (vale.volumen * Decimal("0.085")).quantize(Decimal("0.01"))
        lote.bultos = int(lote.kg_producidos / 25)
        lote.hora_termino = time(16, 0)
        lote.estado = Lote.Estado.PRODUCIDO
        lote.save()

        especificacion = contexto["especificacion"]

        # Valores dentro de rango: el sembrado muestra un lote conforme. Para
        # ver el camino contrario basta editarlos desde la pantalla de Calidad.
        valores = {
            clave: round((rango["min"] + rango["max"]) / 2, 2)
            for clave, rango in especificacion.rangos.items()
        }

        analisis = Analisis.objects.create(
            lote=lote,
            fecha=self.fecha,
            muestra=f"{lote.codigo_lote}-A1",
            valores=valores,
            especificacion=especificacion,
        )

        veredicto = self._veredicto(valores, especificacion)

        return lote, analisis, veredicto

    @staticmethod
    def _veredicto(valores, especificacion):
        fuera = [
            clave
            for clave, rango in especificacion.rangos.items()
            if not (rango["min"] <= valores.get(clave, 0) <= rango["max"])
        ]

        return "CONFORME" if not fuera else f"fuera de rango: {', '.join(fuera)}"
