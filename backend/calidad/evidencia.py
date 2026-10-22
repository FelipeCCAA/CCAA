"""Escritura atómica de fuentes de Calidad, compartida por API y admin.

No bloquea hojas, pallets ni raíces adicionales al invalidar. El lector toma
las fuentes antes de leer la aprobación; así no invierte fuente → aprobación.
"""

from django.db import DEFAULT_DB_ALIAS, connections, models, transaction


# Un lector compartido permite firmar lotes diferentes simultáneamente. Solo
# cambios de maestros/registro periódico requieren exclusividad: también cubre
# altas nuevas que un FOR UPDATE sobre filas existentes no podría proteger.
CATALOGO_LOCK = (17219, 101)


def bloquear_catalogo(*, escritura=False, using=DEFAULT_DB_ALIAS):
    conexion = connections[using]
    if conexion.vendor != "postgresql":
        return  # El check calidad.E001 impide operar sin bloqueo de filas.
    funcion = "pg_advisory_xact_lock" if escritura else "pg_advisory_xact_lock_shared"
    with conexion.cursor() as cursor:
        cursor.execute(f"SELECT {funcion}(%s, %s)", CATALOGO_LOCK)


class EvidenciaCalidadMixin(models.Model):
    """Incluye invalidación y auditoría dentro del mismo commit del dato."""

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        from .vigencia import campos_evidencia, invalidar_por_cambio, preparar_escritura

        using = kwargs.get("using") or self._state.db or DEFAULT_DB_ALIAS
        campos = campos_evidencia(self._meta.label)
        with transaction.atomic(using=using):
            anterior = None
            if self.pk is not None:
                anterior = type(self)._base_manager.using(using).filter(pk=self.pk).values(*campos).first()
            preparar_escritura(self, anterior, using=using)
            if anterior is not None:
                # El antes debe ser el valor reemplazado, no uno leído antes
                # de esperar a otro escritor. Sin releer bajo lock, A→B→A
                # podría parecer un no-op y conservar una firma de B.
                actual = type(self)._base_manager.using(using).select_for_update().filter(pk=self.pk).values(*campos).get()
                for campo in ("lote_id", "control_id", "monitoreo_id", "ejecucion_id", "salida_origen_id"):
                    if campo in anterior and anterior[campo] != actual[campo]:
                        from django.core.exceptions import ValidationError

                        raise ValidationError("La evidencia cambió mientras se guardaba. Vuelve a cargarla antes de corregirla.")
                anterior = actual
            resultado = super().save(*args, **kwargs)
            despues = type(self)._base_manager.using(using).filter(pk=self.pk).values(*campos).get()
            if anterior != despues:
                invalidar_por_cambio(self, anterior, despues, using=using)
            return resultado


class FirmaCalidadMixin(models.Model):
    """La firma anterior se conserva; su versión determina la vigencia."""

    firma_id = models.UUIDField(null=True, blank=True, editable=False)
    version_evidencia = models.PositiveIntegerField(default=0, editable=False)
    version_firmada = models.PositiveIntegerField(null=True, blank=True, editable=False)
    evidencia_firmada = models.JSONField(default=dict, blank=True, editable=False)

    class Meta:
        abstract = True

    @property
    def firma_vigente(self):
        estados = getattr(self, "ESTADOS_LIBERADO", (self.Estado.LIBERADO,))
        return bool(
            self.estado in estados and self.firma_id and self.evidencia_firmada
            and self.version_firmada == self.version_evidencia
        )

    def save(self, *args, **kwargs):
        from django.core.exceptions import ValidationError

        if self.pk is not None:
            campo = "lote_id" if self._meta.model_name == "liberacion" else "salida_id"
            sujeto = type(self)._base_manager.filter(pk=self.pk).values_list(campo, flat=True).first()
            if sujeto is not None and sujeto != getattr(self, campo):
                raise ValidationError({campo.removesuffix("_id"): "La aprobación pertenece al mismo material durante toda su historia."})
        return super().save(*args, **kwargs)
