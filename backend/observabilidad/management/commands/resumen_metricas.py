"""
Convierte el registro de métricas en las respuestas que se necesitan.

Las dos preguntas que contesta son las del síntoma reportado: qué endpoints
cuestan más en total, y cuáles pide la misma pantalla varias veces seguidas.

No decide nada ni optimiza nada: entrega los números para que la decisión se
tome con evidencia. Es la mitad «medir antes» del método.
"""

import json

from django.core.management.base import BaseCommand, CommandError

from observabilidad import dominio


class Command(BaseCommand):
    help = "Resume un registro de métricas: percentiles por ruta y repeticiones."

    def add_arguments(self, parser):
        parser.add_argument(
            "archivo", help="Ruta al .jsonl que escribió el middleware"
        )
        parser.add_argument(
            "--ventana",
            type=float,
            default=5.0,
            help="Segundos dentro de los cuales dos llamadas iguales son repetición",
        )

    def handle(self, *args, **opciones):
        muestras, ilegibles = self._leer(opciones["archivo"])

        if not muestras:
            self.stdout.write(
                self.style.WARNING("El registro no trae muestras.")
            )
            self._avisar_ilegibles(ilegibles)
            return

        self.stdout.write(f"\n{len(muestras)} requests medidos")
        self.stdout.write(
            "Ordenado por tiempo total: un endpoint barato llamado muchas "
            "veces cuesta más que uno caro llamado una.\n"
        )

        self.stdout.write(
            f"{'ruta':<52}{'n':>6}{'p50':>8}{'p95':>8}{'p99':>8}"
            f"{'total':>10}{'SQL':>7}{'msSQL':>8}"
        )

        for fila in dominio.resumir(muestras):
            self.stdout.write(
                f"{fila.ruta[:50]:<52}{fila.llamadas:>6}"
                f"{fila.p50:>8.0f}{fila.p95:>8.0f}{fila.p99:>8.0f}"
                f"{fila.ms_total:>10.0f}{fila.consultas_media:>7.1f}"
                f"{fila.ms_sql_media:>8.1f}"
            )

        repetidas = dominio.repeticiones(muestras, opciones["ventana"])

        self.stdout.write(
            f"\nRepeticiones dentro de {opciones['ventana']:.0f} s "
            f"(mismo usuario, misma ruta):"
        )

        if not repetidas:
            self.stdout.write("  ninguna")

        for ruta, veces in repetidas:
            self.stdout.write(f"  {veces:>3}x  {ruta}")

        self._avisar_ilegibles(ilegibles)

    def _avisar_ilegibles(self, ilegibles):
        if ilegibles:
            self.stdout.write(
                self.style.WARNING(
                    f"\n{ilegibles} línea ilegible(s) omitida(s)."
                )
            )

    def _leer(self, archivo):
        muestras, ilegibles = [], 0

        try:
            f = open(archivo, encoding="utf-8")
        except OSError as error:
            # El error más probable es teclear mal la ruta del registro. Un
            # traceback no lo dice; esto sí.
            raise CommandError(
                f"No se pudo leer el registro {archivo!r}: {error.strerror}."
            ) from error

        with f:
            for linea in f:
                linea = linea.strip()

                if not linea:
                    continue

                try:
                    muestras.append(dominio.Muestra(**json.loads(linea)))
                except (ValueError, TypeError):
                    # El registro se escribe en producción y puede quedar
                    # cortado a mitad de línea. Perder el informe entero por
                    # una línea rota sería perder la medición.
                    ilegibles += 1

        return muestras, ilegibles
