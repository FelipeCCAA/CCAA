"""Maestros ficticios para OP-09; ejecutar sólo con manage_isolated.py shell.

No crea recepciones, vales ni lotes operacionales. Los rangos que faltan los
aportan los preparadores E2E existentes. La única especificación aquí es la
de polvo terminado, con los valores documentados en el spec visual.
"""

from datetime import date
from decimal import Decimal

from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import ImproperlyConfigured
from django.db import transaction

from maestros.models import (
    Equipo, Especificacion, FormatoEnvasado, Mandante, Producto, Silo,
    Vehiculo,
)
from procesos.models import EtapaProceso, Proceso, RutaProducto
from usuarios.areas import usuarios_del_area
from usuarios.models import PerfilUsuario, Rol, Sucursal


def _solo_op09():
    base = settings.DATABASES["default"]
    if not (
        settings.DJANGO_ENV == "test"
        and base.get("ENGINE") == "django.db.backends.postgresql"
        and base.get("NAME") == "op09_circuito"
        and base.get("HOST") == "127.0.0.1"
        and str(base.get("PORT")) == "55449"
    ):
        raise ImproperlyConfigured("Seed OP-09: destino distinto del clúster aislado.")


def _producto(mandante, nombre, **atributos):
    producto, creado = Producto.objects.get_or_create(
        mandante=mandante, nombre=nombre, defaults={**atributos, "activo": True},
    )
    if not creado and any(getattr(producto, clave) != valor for clave, valor in atributos.items()):
        raise ImproperlyConfigured(f"Producto E2E incompatible: {nombre}")
    return producto


def _ruta(planta, producto, codigo, etapas, destino):
    proceso, _ = Proceso.objects.get_or_create(
        codigo=codigo, version=1,
        defaults={"nombre": codigo.replace("ruta-", "").title(), "activo": True},
    )
    if not proceso.activo:
        raise ImproperlyConfigured(f"Ruta E2E inactiva: {codigo}")
    for orden, clave, nombre, tipo in etapas:
        EtapaProceso.objects.get_or_create(
            proceso=proceso, codigo=clave,
            defaults={"nombre": nombre, "tipo": tipo, "orden": orden,
                      "requiere_calidad": True, "activa": True},
        )
    ruta, _ = RutaProducto.objects.get_or_create(
        sucursal=planta, producto=producto, proceso=proceso,
        defaults={"prioridad": 1, "destino_final": destino,
                  "destino": "Fixture OP-09 aislado", "activa": True},
    )
    if not ruta.activa or ruta.destino_final != destino:
        raise ImproperlyConfigured(f"Destino E2E incompatible: {producto.nombre}")


@transaction.atomic
def seed():
    _solo_op09()
    # usuarios.0008 ya crea TENANT-TEST/INTERNA con DJANGO_ENV=test. Todos los
    # perfiles y maestros previos de este clúster pertenecen a esa planta.
    plantas = list(Sucursal.objects.filter(activa=True).select_related("empresa"))
    if len(plantas) != 1 or plantas[0].codigo != "INTERNA" or plantas[0].empresa.rut != "TENANT-TEST":
        raise ImproperlyConfigured("OP-09 requiere la planta aislada TENANT-TEST/INTERNA.")
    planta = plantas[0]
    empresa = planta.empresa

    # El E2E de recepción debe elegir a una persona responsable del muestreo.
    # No necesita iniciar sesión: la cuenta no tiene contraseña utilizable.
    if not usuarios_del_area(PerfilUsuario.Area.RECEPCION).exists():
        responsable, creado = User.objects.get_or_create(
            username="op09_recepcion", defaults={"is_active": True},
        )
        if creado:
            responsable.set_unusable_password()
            responsable.save(update_fields=["password"])
        PerfilUsuario.objects.update_or_create(
            usuario=responsable,
            defaults={"empresa": empresa, "sucursal": planta,
                      "alcance": PerfilUsuario.Alcance.SUCURSAL,
                      "rol": Rol.RECEPCION, "area": PerfilUsuario.Area.RECEPCION,
                      "cargo": "Responsable ficticio de muestras OP09"},
        )

    propio, _ = Mandante.objects.get_or_create(
        empresa=empresa, codigo_cliente=Mandante.Cliente.NO_DEFINIDO,
        defaults={"nombre": "CCAA FICTICIA OP09", "activo": True},
    )
    tercero, _ = Mandante.objects.get_or_create(
        empresa=empresa, codigo_cliente=Mandante.Cliente.NESTLE,
        defaults={"nombre": "Mandante ficticio NE OP09", "activo": True},
    )
    comunes = {"naturaleza_comercial": Producto.NaturalezaComercial.PRODUCTO_PROPIO,
               "mercado": Producto.Mercado.LOCAL}
    polvo = _producto(
        propio, "Leche entera en polvo", **comunes,
        categoria=Producto.Categoria.LECHE_POLVO, tipo=Producto.TipoProducto.ENTERA,
        formato=Producto.Formato.SACO_25KG, familia=Producto.Familia.POLVO,
        naturaleza=Producto.Naturaleza.TERMINADO, unidad_base=Producto.Unidad.KG,
    )
    precondensado = _producto(
        tercero, "Precondensado Entero NE Granel",
        naturaleza_comercial=Producto.NaturalezaComercial.SERVICIO_TERCEROS,
        mercado=Producto.Mercado.LOCAL, categoria=Producto.Categoria.PRECONDENSADO,
        tipo=Producto.TipoProducto.ENTERA, formato=Producto.Formato.GRANEL,
        familia=Producto.Familia.LIQUIDO,
        naturaleza=Producto.Naturaleza.INTERMEDIO, unidad_base=Producto.Unidad.L,
    )
    _producto(
        propio, "Crema fresca 42% Granel CA", **comunes,
        categoria=Producto.Categoria.CREMA, tipo=Producto.TipoProducto.ENTERA,
        formato=Producto.Formato.GRANEL, familia=Producto.Familia.CREMA,
        naturaleza=Producto.Naturaleza.INTERMEDIO, unidad_base=Producto.Unidad.KG,
    )
    mantequilla = _producto(
        propio, "Mantequilla S-sal 20kg", **comunes,
        categoria=Producto.Categoria.MANTEQUILLA,
        tipo=Producto.TipoProducto.SIN_SAL, formato=Producto.Formato.CAJA_20KG,
        familia=Producto.Familia.OTRO,
        naturaleza=Producto.Naturaleza.TERMINADO, unidad_base=Producto.Unidad.KG,
    )

    # Capacidades exclusivamente ficticias: dos fuentes para el circuito,
    # una reserva y los TK que nombran las pruebas de descremado.
    estanques = (
        ("Silo 3", Silo.Tipo.SILO, "60000"),
        ("Silo 4", Silo.Tipo.SILO, "60000"),
        ("Silo 5", Silo.Tipo.SILO, "60000"),
        ("Tk02", Silo.Tipo.TK_LD, "20000"),
        ("OP09-PRE-BASE", Silo.Tipo.SILO, "60000"),
        ("Tk03", Silo.Tipo.TK_LD, "20000"),
        ("TkC2", Silo.Tipo.TK_CREMA, "10000"),
        ("TkC3", Silo.Tipo.TK_CREMA, "10000"),
    )
    for codigo, tipo, capacidad in estanques:
        silo, _ = Silo.objects.get_or_create(
            sucursal=planta, codigo=codigo,
            defaults={"tipo": tipo, "capacidad_l": Decimal(capacidad),
                      "estado": Silo.Estado.DISPONIBLE, "activo": True},
        )
        if silo.tipo != tipo or not silo.activo:
            raise ImproperlyConfigured(f"Estanque E2E incompatible: {codigo}")
    Vehiculo.objects.get_or_create(
        placa="QAOP09", defaults={"sucursal": planta, "numero": "OP09",
                                  "tipo": "Camión ficticio", "capacidad_l": Decimal("30000"),
                                  "transportista": "Transportista ficticio OP09",
                                  "chofer_am": "Chofer ficticio", "activo": True},
    )

    # Equipos/siglas y formatos replican los datos sembrados por migraciones
    # 0010, 0017, 0031 y 0037; no representan capacidad industrial nueva.
    equipos = (
        ("scheffers2", "Evaporador Scheffers 2", Equipo.Tipo.EVAPORADOR, "S2", True, False),
        ("e1", "Torre de secado Egron 1", Equipo.Tipo.TORRE, "E1", False, True),
        ("rovema3", "Envasadora Rovema 3", Equipo.Tipo.ENVASADORA, "R3", False, False),
        ("linea_mantequilla", "Línea de mantequilla", Equipo.Tipo.LINEA, "LM", False, True),
    )
    por_codigo = {}
    for codigo, nombre, tipo, sigla, leche, materiales in equipos:
        equipo, _ = Equipo.objects.get_or_create(
            sucursal=planta, codigo=codigo,
            defaults={"nombre": nombre, "tipo": tipo, "sigla": sigla,
                      "consume_leche": leche, "consume_materiales": materiales,
                      "activo": True},
        )
        if equipo.tipo != tipo or not equipo.activo:
            raise ImproperlyConfigured(f"Equipo E2E incompatible: {codigo}")
        por_codigo[codigo] = equipo

    polvo_etapas = (
        (1, "estandarizacion", "Estandarización", EtapaProceso.Tipo.ESTANDARIZACION),
        (2, "evaporacion", "Evaporación", EtapaProceso.Tipo.EVAPORACION),
        (3, "secado", "Secado", EtapaProceso.Tipo.SECADO),
        (4, "envasado", "Envasado", EtapaProceso.Tipo.ENVASADO),
    )
    _ruta(planta, polvo, "ruta-polvo", polvo_etapas,
          RutaProducto.DestinoFinal.ENVASADO)
    _ruta(planta, precondensado, "ruta-precondensado", polvo_etapas[:2],
          RutaProducto.DestinoFinal.DESPACHO_DIRECTO)
    _ruta(planta, mantequilla, "ruta-mantequilla", (
        (1, "mantequilla", "Elaboración de mantequilla", EtapaProceso.Tipo.MANTEQUILLA),
        (2, "envasado", "Envasado en cajas", EtapaProceso.Tipo.ENVASADO),
    ), RutaProducto.DestinoFinal.ENVASADO)

    for producto, codigo, nombre, kg, maximo, equipo in (
        (polvo, "saco-25kg", "Saco 25 kg", "25", 20, "rovema3"),
        (mantequilla, "caja-20kg", "Caja 20 kg", "20", 25, "linea_mantequilla"),
    ):
        formato, _ = FormatoEnvasado.objects.get_or_create(
            producto=producto, codigo=codigo,
            defaults={"nombre": nombre, "kg_neto": Decimal(kg),
                      "unidades_maximas_pallet": maximo, "activo": True},
        )
        formato.equipos.add(por_codigo[equipo])

    # Valores declarados por flujo-polvo-continuacion.spec.ts (MG 26–28,
    # humedad 2–4); sólo para datos ficticios de esta ejecución.
    Especificacion.objects.get_or_create(
        producto=polvo, tipo_analisis=Especificacion.TipoAnalisis.LOTE, version=1,
        defaults={"vigente_desde": date.today(),
                  "rangos": {
                      "mg": {"min": 26, "max": 28, "obligatorio": True},
                      "humedad": {"min": 2, "max": 4, "obligatorio": True},
                  },
                  "fuente": "Fixture ficticio OP-09; rangos del E2E de polvo, no operacionales."},
    )
    print("OP09 maestros ficticios: polvo, precondensado, crema, mantequilla, silos, equipos y rutas.")
    print("Luego: configurar_maestro_inicial --aplicar; preparar_circuito_polvo --aplicar.")
    print("Después, preparadores de precondensado/descremado/mantequilla/suero según familia.")


seed()
