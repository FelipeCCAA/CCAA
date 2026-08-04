"""
Captura de cambios por señales de Django.

Por señales y no desde las vistas: así queda cubierto todo lo que escribe en
la base —la API, el admin, un script, el shell— y no solo los caminos que
alguien se acordó de instrumentar. Una auditoría con agujeros conocidos no
sirve de mucho.

Los dos lados del diff se leen **de la base**: el antes en `pre_save` y el
después en `post_save`. Cuesta dos consultas por escritura; a escala de planta
no se nota, y a cambio todo lo que dice la auditoría es lo que la base
realmente guardó, en el mismo formato. Comparar la base contra el objeto en
memoria haría figurar como cambiados campos que solo cambiaron de tipo.
"""

from django.apps import apps
from django.core.exceptions import ObjectDoesNotExist
from django.db.models.signals import (
    post_delete,
    post_save,
    pre_delete,
    pre_save,
)
from django.dispatch import receiver

from .contexto import actor_actual


#: Etiquetas de app cuyos modelos se auditan. Fuera quedan las tablas de
#: infraestructura de Django: sesiones, permisos, tokens y el propio
#: `LogEntry`, que son ruido y no decisiones de nadie.
APPS_AUDITADAS = {
    "maestros",
    "produccion",
    "recepcion",
    "calidad",
    "inocuidad",
    "planificacion",
    "usuarios",
    "inventario",
    "procesos",
    "mantenimiento",
}

#: Campos que nunca se registran, aunque cambien.
CAMPOS_EXCLUIDOS = {"password", "last_login"}

#: Guarda la instantánea previa hasta que `post_save`/`post_delete` la use.
#: Se indexa por `id(instancia)` porque el objeto todavía puede no tener pk.
_PENDIENTES: dict[int, dict] = {}


def se_audita(modelo) -> bool:
    if modelo._meta.app_label not in APPS_AUDITADAS:
        return False

    # Un modelo puede excluirse declarando `auditar = False` en su Meta.
    return getattr(modelo._meta, "auditar", True)


def _valor(instancia, campo):
    """
    El valor de un campo, en algo que quepa en JSON.

    Las claves foráneas se leen por su `_id` para no disparar una consulta por
    campo: el objetivo es registrar qué cambió, no describir el grafo entero.
    """
    if campo.is_relation:
        valor = getattr(instancia, f"{campo.name}_id", None)
    else:
        valor = getattr(instancia, campo.name, None)

    if valor is None or isinstance(valor, (bool, int, float, str)):
        return valor

    if isinstance(valor, (dict, list)):
        return valor

    return str(valor)


def _instantanea(instancia) -> dict:
    """
    Los campos del objeto y sus valores.

    Sin la clave primaria: no cambia nunca y ya viaja en `objeto_id`, así que
    en un alta solo sería ruido repetido.
    """
    return {
        campo.name: _valor(instancia, campo)
        for campo in instancia._meta.concrete_fields
        if campo.name not in CAMPOS_EXCLUIDOS and not campo.primary_key
    }


def _instantanea_guardada(modelo, pk) -> dict | None:
    """
    La instantánea leída **de la base**, no del objeto en memoria.

    Los dos lados del diff tienen que venir de la misma fuente. Asignar
    `lote.kg_producidos = 1200` deja un `int` en memoria mientras la columna
    guarda `Decimal('1200.00')`; comparando memoria contra base, ese campo
    figuraría como cambiado cada vez que se toca aunque el valor sea el mismo,
    y el registro mostraría `['1000.00', 1200]` — dos formas del mismo número
    que un auditor tiene que interpretar.

    Cuesta una consulta más por escritura. A escala de planta no se nota, y a
    cambio todo lo que dice la auditoría es lo que la base realmente guardó.
    """
    try:
        return _instantanea(modelo._base_manager.get(pk=pk))
    except ObjectDoesNotExist:
        return None


def _diferencias(antes: dict, despues: dict) -> dict:
    return {
        campo: [antes.get(campo), despues.get(campo)]
        for campo in despues
        if antes.get(campo) != despues.get(campo)
    }


@receiver(pre_save)
def _antes_de_guardar(sender, instance, **kwargs):
    if not se_audita(sender):
        return

    if instance.pk is None:
        _PENDIENTES[id(instance)] = {}
        return

    anterior = _instantanea_guardada(sender, instance.pk)

    # Un save() con pk asignada sobre una fila que no existe: es un alta.
    _PENDIENTES[id(instance)] = anterior if anterior is not None else {}


@receiver(post_save)
def _al_guardar(sender, instance, created, **kwargs):
    if not se_audita(sender):
        return

    antes = _PENDIENTES.pop(id(instance), None)

    if antes is None:
        # `post_save` sin su `pre_save`: pasa con `bulk_create` y con
        # `loaddata`. No se inventa un diff.
        antes = {}

    # También de la base: es lo que quedó guardado, incluidos los valores que
    # el propio modelo derive en `save()` —como el SKU del producto—.
    despues = _instantanea_guardada(sender, instance.pk) or _instantanea(instance)

    # Un alta se guarda con la MISMA forma que una modificación: el valor
    # anterior es `None` porque no había nada. Guardarla como un diccionario
    # plano de valores obligaría a cada consumidor a distinguir las dos formas
    # —y el que no lo haga, revienta: fue exactamente lo que tumbó la pantalla
    # de auditoría al intentar desestructurar un número como par.
    cambios = (
        {campo: [None, valor] for campo, valor in despues.items()}
        if created
        else _diferencias(antes, despues)
    )

    # Un save() que no cambió nada no es un hecho que registrar.
    if not created and not cambios:
        return

    _escribir(
        instance,
        "creacion" if created else "modificacion",
        cambios,
    )


@receiver(pre_delete)
def _antes_de_borrar(sender, instance, **kwargs):
    """La fila todavía existe: es la última oportunidad de leerla."""
    if not se_audita(sender):
        return

    _PENDIENTES[id(instance)] = _instantanea_guardada(sender, instance.pk) or {}


@receiver(post_delete)
def _al_borrar(sender, instance, **kwargs):
    if not se_audita(sender):
        return

    # En un borrado el «después» no existe: se guarda lo que había, que es lo
    # único que queda para reconstruir qué se perdió.
    habia = _PENDIENTES.pop(id(instance), None) or _instantanea(instance)

    _escribir(instance, "borrado", {c: [v, None] for c, v in habia.items()})


def _escribir(instancia, accion, cambios):
    Registro = apps.get_model("auditoria", "RegistroAuditoria")
    actor = actor_actual()

    usuario = actor.usuario

    # El middleware entrega un envoltorio que resuelve el usuario tarde,
    # porque DRF autentica dentro de la vista.
    if hasattr(usuario, "resolver"):
        usuario = usuario.resolver()

    meta = instancia._meta

    Registro.objects.create(
        usuario=usuario,
        usuario_nombre=getattr(usuario, "username", "") or "",
        accion=accion,
        modelo=f"{meta.app_label}.{meta.object_name}",
        etiqueta_modelo=str(meta.verbose_name),
        objeto_id=str(instancia.pk),
        objeto_desc=str(instancia)[:300],
        cambios=cambios,
        ip=actor.ip,
        origen=actor.origen,
    )
