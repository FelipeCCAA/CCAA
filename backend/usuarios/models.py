from django.db import models
from django.contrib.auth.models import User

from .tenancy import empresa_predeterminada_pruebas, sucursal_predeterminada_pruebas


class IntentoAcceso(models.Model):
    """
    Cada intento de iniciar sesión, exitoso o no.

    Antes no quedaba rastro de ninguno: un ataque de fuerza bruta contra la API
    era indistinguible de un turno normal, y después de un incidente no había
    forma de responder «desde dónde y contra qué cuenta». `auditoria` no cubre
    esto porque captura escrituras de modelos, y un login fallido no escribe
    nada.

    **El nombre de usuario se guarda como texto, no como clave foránea**: la
    mitad de los intentos de un ataque son contra cuentas que no existen, y son
    justamente los que más dicen. Con una FK, esos se perderían.

    **Sin empresa ni sucursal, a diferencia del resto del sistema.** El login
    ocurre *antes* de saber quién llama: exigirle un tenant obligaría a
    resolverlo desde un nombre de usuario que puede no existir, y dejaría fuera
    del registro justo los intentos que más importa ver.

    Nunca se guarda la contraseña, ni siquiera de un intento fallido: un
    tecleo de una contraseña válida en el campo equivocado terminaría en la
    base en claro.
    """

    usuario = models.CharField("Usuario declarado", max_length=150)
    ip = models.GenericIPAddressField("Dirección", null=True, blank=True)
    exito = models.BooleanField("Correcto", default=False)
    motivo = models.CharField("Motivo del rechazo", max_length=60, blank=True)
    fecha_hora = models.DateTimeField("Fecha y hora", auto_now_add=True)

    class Meta:
        verbose_name = "Intento de acceso"
        verbose_name_plural = "Intentos de acceso"
        ordering = ["-fecha_hora"]
        indexes = [
            # Las dos preguntas que se le hacen a esta tabla: «qué pasó con
            # esta cuenta» y «qué está haciendo esta dirección».
            models.Index(fields=["usuario", "-fecha_hora"]),
            models.Index(fields=["ip", "-fecha_hora"]),
        ]

    def __str__(self):
        return f"{self.usuario} · {'ok' if self.exito else self.motivo}"


class Empresa(models.Model):
    rut = models.CharField(max_length=20, unique=True)
    nombre = models.CharField(max_length=160)
    activa = models.BooleanField(default=True)

    class Meta:
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class Sucursal(models.Model):
    empresa = models.ForeignKey(Empresa, on_delete=models.PROTECT, related_name="sucursales")
    codigo = models.CharField(max_length=30)
    nombre = models.CharField(max_length=140)
    direccion = models.CharField(max_length=250, blank=True)
    activa = models.BooleanField(default=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["empresa", "codigo"], name="sucursal_codigo_unico_empresa")]
        ordering = ["empresa", "nombre"]

    def __str__(self):
        return f"{self.empresa} · {self.nombre}"


class Rol(models.TextChoices):
    """
    Los roles del proceso, tal como los define el prototipo
    (prototipo/js/modelo/esquema.js, CATALOGOS.roles).

    No son categorías administrativas: cada uno corresponde a quién hace qué
    en planta, y de ahí sale la regla central del sistema — solo Calidad y
    Administración autorizan la liberación de un lote.

    **`OPERARIO` es un comodín y no dice dónde trabaja nadie.** En CCAA la misma
    persona opera en Recepción y en Fabricación, así que el rol dejó de servir
    para deducir el área: para eso está `PerfilUsuario.area` y sus áreas
    adicionales. Un operario sin área asignada no escribe en ninguna parte, y
    eso es lo correcto — el permiso lo da el área, no la etiqueta.
    """

    RECEPCION = "recepcion", "Recepción"
    PRODUCCION = "produccion", "Producción"
    CALIDAD = "calidad", "Calidad"
    OPERARIO = "operario", "Operario"
    ADMIN = "admin", "Administrador"
    LECTURA = "lectura", "Solo lectura"


# Quiénes pueden autorizar una liberación (MODELO_DATOS.md §1).
ROLES_AUTORIZADORES = (Rol.CALIDAD, Rol.ADMIN)

# Los roles que **sí** nombran un área, para los perfiles antiguos que se
# cargaron sin ella. Es el respaldo que ya aplicaba `rol_de`, escrito una vez.
# `operario`, `admin` y `lectura` no aparecen: no dicen dónde trabaja nadie, y
# tratarlos como si lo dijeran repartiría avisos de Recepción a toda la planta.
AREAS_QUE_NOMBRA_EL_ROL: dict[str, tuple[str, ...]] = {
    Rol.RECEPCION: ("recepcion",),
    Rol.CALIDAD: ("calidad",),
    Rol.PRODUCCION: ("condensacion", "secado", "envase"),
}


class PerfilUsuario(models.Model):

    class Alcance(models.TextChoices):
        SUCURSAL = "sucursal", "Sucursal"
        EMPRESA = "empresa", "Toda la empresa"

    class Nivel(models.TextChoices):
        ADMIN = "admin", "Administrador de área"
        TRABAJADOR = "trabajador", "Trabajador"

    class Area(models.TextChoices):
        ASEO = "aseo", "Aseo y saneamiento"
        RECEPCION = "recepcion", "Recepción"
        CONDENSACION = "condensacion", "Condensación"
        SECADO = "secado", "Secado"
        ENVASE = "envase", "Envase"
        CALIDAD = "calidad", "Calidad"
        BODEGA = "bodega", "Bodega"
        COMPRAS = "compras", "Compras"
        DESPACHO = "despacho", "Despacho"
        MANTENIMIENTO = "mantenimiento", "Mantenimiento"
        ADMINISTRACION = "administracion", "Administración general"

    usuario = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="perfil"
    )

    cargo = models.CharField(
        max_length=100,
        blank=True
    )

    area = models.CharField(max_length=30, choices=Area.choices, blank=True)

    turno = models.CharField(
        max_length=50,
        blank=True
    )

    rol = models.CharField(
        max_length=20,
        choices=Rol.choices,
        default=Rol.LECTURA
    )

    empresa = models.ForeignKey(
        Empresa,
        on_delete=models.PROTECT,
        related_name="perfiles",
        default=empresa_predeterminada_pruebas,
    )

    sucursal = models.ForeignKey(
        Sucursal,
        on_delete=models.PROTECT,
        related_name="perfiles",
        null=True,
        blank=True,
        default=sucursal_predeterminada_pruebas,
    )

    alcance = models.CharField(
        max_length=10,
        choices=Alcance.choices,
        default=Alcance.SUCURSAL,
    )

    nivel = models.CharField(
        max_length=20,
        choices=Nivel.choices,
        default=Nivel.TRABAJADOR,
    )

    class Meta:
        verbose_name = "Perfil de usuario"
        verbose_name_plural = "Perfiles de usuario"
        permissions = [
            ("produccion_orden_crear", "Puede crear órdenes de producción"),
            ("produccion_orden_editar", "Puede editar órdenes de producción"),
            ("produccion_lote_cerrar", "Puede cerrar lotes de producción"),
            ("produccion_lote_anular", "Puede anular lotes de producción"),
            ("secado_proceso_iniciar", "Puede iniciar procesos de secado"),
            ("secado_proceso_cerrar", "Puede cerrar procesos de secado"),
            ("calidad_lote_liberar", "Puede liberar lotes por Calidad"),
            ("calidad_lote_bloquear", "Puede bloquear lotes por Calidad"),
            ("inventario_transferir", "Puede transferir inventario"),
            ("inventario_ajustar", "Puede solicitar ajustes de inventario"),
            ("despacho_crear", "Puede crear solicitudes de despacho"),
            ("despacho_autorizar", "Puede autorizar despachos"),
            ("auditoria_exportar", "Puede exportar registros de auditoría"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(alcance="sucursal", sucursal__isnull=False)
                    | models.Q(alcance="empresa", sucursal__isnull=True)
                ),
                name="perfil_scope_coherente",
            )
        ]

    def __str__(self):
        return self.usuario.username

    @property
    def es_admin_de_area(self):
        return self.nivel == self.Nivel.ADMIN

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)
        es_staff = self.usuario.is_superuser or self.es_admin_de_area
        if self.usuario.is_staff != es_staff:
            User.objects.filter(pk=self.usuario_id).update(is_staff=es_staff)
            self.usuario.is_staff = es_staff

    def clean(self):
        from django.core.exceptions import ValidationError

        super().clean()
        if not self.empresa_id:
            raise ValidationError({"empresa": "La empresa es obligatoria."})
        if self.alcance == self.Alcance.SUCURSAL and not self.sucursal_id:
            raise ValidationError({"sucursal": "El alcance de sucursal exige una sucursal."})
        if self.alcance == self.Alcance.EMPRESA and self.sucursal_id:
            raise ValidationError({"sucursal": "El alcance de empresa no lleva una sucursal."})
        if self.sucursal_id and self.sucursal.empresa_id != self.empresa_id:
            raise ValidationError({"sucursal": "La sucursal no pertenece a la empresa seleccionada."})
        if self.alcance == self.Alcance.EMPRESA and not (
            self.area == self.Area.ADMINISTRACION and self.es_admin_de_area
        ):
            raise ValidationError(
                {"alcance": "Solo Administración general puede abarcar toda la empresa."}
            )


class AreaDePerfil(models.Model):
    """
    Un área más en la que trabaja esta persona.

    En CCAA **una persona desempeña más de una función en más de un área**: el
    mismo operario puede estar en Recepción por la mañana y en Fabricación por
    la tarde. Un solo campo `area` no puede decir eso, y quien lo consulta —a
    quién avisar de que llegó leche, a quién ofrecer como responsable— acaba
    dejando fuera a media planta.

    `PerfilUsuario.area` sigue siendo el **área principal**, y es la única que
    hoy concede permisos (`rol_de` y las clases con `areas_escritura`). Estas
    son las adicionales: suman presencia, **no permisos**. Que un operario de
    Recepción que también trabaja en Bodega pueda escribir en Bodega es una
    decisión de quién responde por cada área, no un efecto colateral de
    apuntarlo aquí.
    """

    perfil = models.ForeignKey(
        PerfilUsuario,
        on_delete=models.CASCADE,
        related_name="areas_adicionales",
        verbose_name="Perfil",
    )

    area = models.CharField("Área", max_length=30, choices=PerfilUsuario.Area.choices)

    class Meta:
        verbose_name = "Área adicional"
        verbose_name_plural = "Áreas adicionales"
        constraints = [
            models.UniqueConstraint(
                fields=["perfil", "area"], name="area_adicional_unica_por_perfil"
            )
        ]

    def __str__(self):
        return f"{self.perfil.usuario.username} · {self.get_area_display()}"

    def clean(self):
        from django.core.exceptions import ValidationError

        super().clean()
        if self.area and self.area == self.perfil.area:
            raise ValidationError({
                "area": "Esa ya es el área principal del perfil; no hace falta repetirla."
            })


def rol_de(usuario) -> str | None:
    """
    Rol efectivo de un usuario.

    Un superusuario de Django es administrador aunque no tenga perfil: es
    quien creó la instalación con `createsuperuser`, y dejarlo sin permisos
    lo encerraría fuera de su propio sistema.

    Un usuario normal sin perfil no tiene rol, y por tanto no escribe nada.
    """
    if usuario is None or not usuario.is_authenticated:
        return None

    if usuario.is_superuser:
        return Rol.ADMIN

    perfil = getattr(usuario, "perfil", None)

    if not perfil:
        return None

    # El área determina el permiso operativo. Un administrador de Secado
    # administra su personal, pero no se convierte por eso en administrador
    # global de maestros o de otras áreas.
    por_area = {
        PerfilUsuario.Area.RECEPCION: Rol.RECEPCION,
        PerfilUsuario.Area.CONDENSACION: Rol.PRODUCCION,
        PerfilUsuario.Area.SECADO: Rol.PRODUCCION,
        PerfilUsuario.Area.ENVASE: Rol.PRODUCCION,
        PerfilUsuario.Area.CALIDAD: Rol.CALIDAD,
    }
    if perfil.area == PerfilUsuario.Area.ADMINISTRACION:
        return Rol.ADMIN
    return por_area.get(perfil.area, perfil.rol)
