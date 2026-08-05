# Sistema CCAA — Análisis integral de procesos de fábrica y propuesta técnica

**Fecha:** 2026-08-05  
**Versión:** 1.0 — Documento maestro consolidado  
**Estado:** En construcción; faltan documentos adicionales y validación final con responsables de planta.

---

# 1. Rol profesional solicitado

Actúa como un **arquitecto de software, diseñador UX/UI y desarrollador full stack profesional**, con experiencia en:

- Python.
- Django.
- Django REST Framework.
- React.
- TypeScript.
- PostgreSQL.
- Redis.
- Celery.
- Celery Beat.
- Docker.
- BPMN.
- Sistemas industriales.
- Trazabilidad de alimentos.
- Gestión de calidad e inocuidad.
- Automatización de procesos.
- Diseño de interfaces profesionales.
- Optimización de rendimiento.
- Arquitectura de sistemas escalables.

Tu objetivo es analizar el sistema CCAA, comprender cómo trabaja la fábrica, organizar sus procesos, eliminar redundancias, detectar dependencias entre áreas y proponer una solución digital profesional, intuitiva, trazable y escalable.

El análisis debe considerar:

1. Procesos físicos de fábrica.
2. Formularios y registros utilizados.
3. Reglas de negocio.
4. Estados y aprobaciones.
5. Comunicación entre áreas.
6. Trazabilidad de lotes.
7. Aseos, CIP, COP y verificaciones.
8. Calidad e inocuidad.
9. Inventario y materiales.
10. Usuarios, roles y permisos.
11. Arquitectura backend.
12. Arquitectura frontend.
13. Base de datos.
14. Automatizaciones.
15. Rendimiento.
16. Auditoría.
17. Reportes e indicadores.
18. Preparación para producción.

No se debe copiar cada Excel como una pantalla independiente. Los documentos deben analizarse para extraer:

- Campos.
- Reglas.
- responsables.
- Frecuencias.
- Validaciones.
- Estados.
- Relaciones.
- Evidencias.
- Firmas.
- Trazabilidad.

El sistema debe digitalizar el proceso, no solamente replicar formularios antiguos.

---

# 2. Objetivo general del sistema CCAA

CCAA debe administrar el ciclo productivo completo de una planta láctea:

```text
PLANIFICACIÓN
      │
      ▼
RECOLECCIÓN
      │
      ▼
RECEPCIÓN Y ANÁLISIS
      │
      ▼
DESCARGA EN SILOS
      │
      ▼
TRAZABILIDAD Y ADMINISTRACIÓN DE SILOS
      │
      ▼
DESCREMACIÓN Y ESTANDARIZACIÓN
      │
      ▼
CONDENSACIÓN
      │
      ▼
PRECONDENSADO
      │
      ├── DESPACHO EXTERNO
      │
      └── SECADO
              │
              ▼
        LECHE EN POLVO
              │
              ▼
            ENVASE
              │
              ▼
           CALIDAD
              │
              ▼
          LIBERACIÓN
              │
              ▼
            BODEGA
              │
              ▼
           DESPACHO
```

Rama paralela:

```text
DESCREMACIÓN
      │
      ▼
    CREMA
      │
      ├── ESTANDARIZACIÓN DE CREMA
      ├── DESPACHO EXTERNO
      └── MANTEQUILLA
              │
              ▼
        CÁMARA CLIMATIZADA
              │
              ▼
           LIBERACIÓN
              │
              ▼
           DESPACHO
```

Procesos transversales:

```text
CALIDAD
TRAZABILIDAD
ASEOS
MANTENIMIENTO
INVENTARIO
PLANIFICACIÓN
SEGURIDAD
AUDITORÍA
```

---

# 3. Principio central del sistema

La unidad principal de control no debe ser solamente el formulario.

La estructura central debe ser:

```text
ORDEN DE PRODUCCIÓN
      +
LOTE
      +
ETAPA
      +
PRODUCTO
      +
EQUIPO
      +
MATERIAS PRIMAS
      +
CONTROLES
      +
FORMULARIOS
      +
ASEOS
      +
TRAZABILIDAD
      +
APROBACIONES
```

Una orden debe avanzar por estados controlados:

```text
BORRADOR
→ PLANIFICADA
→ APROBADA
→ EN PREPARACIÓN
→ EN PRODUCCIÓN
→ ESPERANDO CALIDAD
→ LIBERADA
→ CERRADA
```

Estados alternativos:

```text
RETENIDA
BLOQUEADA
CANCELADA
NO CONFORME
EN REPROCESO
EN INVESTIGACIÓN
```

---

# 4. Recolección de leche en predios

## 4.1 Flujo operacional

```text
PROGRAMACIÓN DE RECOLECCIÓN
        │
        ▼
ASIGNAR CONDUCTOR, CAMIÓN, CARRO, MÓDULOS Y RUTA
        │
        ▼
LLEGADA AL PREDIO
        │
        ├── Identificar proveedor
        ├── Identificar predio
        ├── Identificar sala
        ├── Revisar estanque
        └── Verificar leche disponible
        │
        ▼
AGITACIÓN DE LA LECHE
        │
        ▼
MEDICIÓN Y CONTROL
        │
        ├── Litros
        ├── Temperatura
        ├── Prueba de alcohol
        ├── Evaluación visual
        └── Observaciones
        │
        ▼
¿PRUEBA DE ALCOHOL CONFORME?
     ┌──────────┴──────────┐
     │                     │
    SÍ                    NO
     │                     │
     ▼                     ▼
TOMAR MUESTRA       NO CARGAR LA LECHE
     │                     │
     ▼                     ├── Tomar muestra
CARGAR MÓDULO              ├── Registrar desviación
     │                     └── Informar responsable
     ▼
EMITIR VOUCHER
     │
     ▼
TRANSPORTAR A FÁBRICA
```

## 4.2 Documentos asociados

- `CCAA.OPE.POE.001.02 – Control de Proveedores LF`.
- `CCAA.OPE.POE.002.01 – Manual Operacional para recolección y transporte de leche fresca en camiones prediales`.
- `CCAA.OPE.POE.003.01 – Toma de muestra de Leche fresca`.
- `CCAA.OPE.ESP.001.01 – Plan Monitor Calidad e Inocuidad LF 2026`.

## 4.3 Formulario digital recomendado

```text
Código de recolección
Fecha y hora
Empresa
Proveedor
Predio
Sala
Conductor
Camión
Carro
Tipo de módulo
Módulo
Estanque
Litros
Temperatura
Resultado prueba de alcohol
Muestra tomada
Observaciones
Geolocalización opcional
Firma o identificación del responsable
Estado de sincronización
```

---

# 5. Recepción industrial de leche fresca

## 5.1 Registro de llegada

```text
CAMIÓN LLEGA A FÁBRICA
        │
        ▼
REGISTRAR INGRESO
        │
        ├── Fecha
        ├── Hora
        ├── Patente
        ├── Conductor
        ├── Ruta
        ├── Camión
        ├── Carro
        └── Módulos
        │
        ▼
IDENTIFICAR CARGAS
        │
        ├── Módulo
        ├── Proveedores
        ├── Litros declarados
        ├── Temperatura
        └── Código de recolección
        │
        ▼
ESTADO: ESPERANDO MUESTREO
```

## 5.2 Formulario consolidado de recepción

Las hojas históricas como `Descarga Camiones`, `Base DATOS`, `Litros-kilos`, `Diferencia`, `Imprimir1` e `Imprimir2` no deben convertirse en formularios separados.

Formulario recomendado:

```text
Identificación de recepción
Fecha y hora de llegada
Código de recolección
Patente del camión
Patente del carro
Conductor
Ruta
Módulos transportados
Litros declarados por módulo
Litros calculados
Kilos recibidos
Diferencias
Estado
Observaciones
```

---

# 6. Muestreo y análisis de recepción

## 6.1 Flujo de análisis

```text
MUESTRA POR MÓDULO
        │
        ▼
TEMPERATURA
        │
        ▼
EVALUACIÓN SENSORIAL
        │
        ├── Materias extrañas
        ├── Sangre
        ├── Pus
        └── Aroma
        │
        ▼
ANÁLISIS DE ANTIBIÓTICOS
        │
        ├── Betalactámicos
        ├── Tetraciclinas
        └── Sulfamidas
        │
        ▼
PRUEBA DE ALCOHOL
        │
        ▼
pH Y ACIDEZ
        │
        ▼
CRIOSCOPÍA
        │
        ▼
COMPOSICIÓN
        │
        ├── Materia grasa
        ├── Sólidos no grasos
        ├── Proteína
        ├── Densidad
        └── Sólidos totales
        │
        ▼
DECISIÓN DE CALIDAD
```

## 6.2 Formularios asociados

- `CCAA.Calidad.FORM.009.01 – PAC Antibióticos`.
- `CCAA.Calidad.FORM.007.01 – PAC Crioscopio`.
- `CCAA.Calidad.FORM.004.01 – PAC pH-metro`.
- `CCAA.Calidad.FORM.033.01 – PAC Balanza Analítica Recepción`.
- `CCAA.Calidad.FORM.010.01 – PAC Refrigerador`.
- `CCAA.Calidad.FORM.042.01 – Monitoreo Temperatura Área de Recepción`.
- `CCAA.Calidad.FORM.019.01 – Formulario Sensorial`.
- `CCAA.Calidad.FORM.017.01 – Formulario Test Sniff`.
- `CCAA.Calidad.FORM.029.01 – Producto No Conforme Proveedores`.
- `CCAA.Calidad.FORM.025.01 – TNC`.

## 6.3 Reglas importantes

### Temperatura

```text
Temperatura objetivo en predio: aproximadamente 4 °C
Temperatura máxima esperada en recepción: 8 °C
```

```text
¿TEMPERATURA ≤ 8 °C?
     ├── SÍ → Continuar análisis
     └── NO → Retener, informar y evaluar
```

### Antibióticos

```text
RESULTADO POSITIVO
        │
        ▼
REPETIR ANÁLISIS
        │
        ▼
¿SE CONFIRMA?
     ├── NO → Continuar
     └── SÍ
          ├── Bloquear camión
          ├── No descargar
          ├── Identificar proveedor
          ├── Bloquear módulos asociados
          ├── Informar Operaciones
          ├── Informar Calidad
          └── Abrir no conformidad
```

### Crioscopía

```text
Resultado mayor o igual a -0,512 °C
→ posible presencia de agua
→ repetir análisis
→ revisar pool
→ identificar origen
→ informar Calidad
```

---

# 7. Autorización y descarga

## 7.1 Flujo

```text
ANÁLISIS COMPLETOS
        │
        ▼
CONSOLIDAR RESULTADOS
        │
        ▼
¿TODOS CONFORMES?
     ┌────────────┴────────────┐
     │                         │
    SÍ                        NO
     │                         │
     ▼                         ▼
APROBAR MÓDULO            RETENER MÓDULO
     │                         │
     ▼                         ├── Repetir análisis
ASIGNAR SILO                  ├── Evaluar desviación
     │                         ├── Bloquear proveedor
     ▼                         └── Definir disposición
AUTORIZAR DESCARGA
     │
     ▼
DESCARGAR
```

## 7.2 Estados recomendados

```text
REGISTRADO
→ ESPERANDO MUESTREO
→ EN ANÁLISIS
→ ANÁLISIS COMPLETADO
→ APROBADO PARA DESCARGA
→ DESCARGANDO
→ DESCARGADO
```

Ruta alternativa:

```text
EN ANÁLISIS
→ RETENIDO
→ REANÁLISIS
→ RECHAZADO
→ BLOQUEADO
→ DESTINO DEFINIDO
```

## 7.3 Regla técnica

No se debe permitir registrar una descarga si el módulo no está en estado:

```text
APROBADO PARA DESCARGA
```

---

# 8. Administración y trazabilidad de silos

## 8.1 Flujo

```text
DESCARGA EN SILO
        │
        ▼
CREAR MOVIMIENTO DE INGRESO
        │
        ├── Camión
        ├── Módulo
        ├── Proveedores
        ├── Cantidad
        ├── Fecha
        └── Hora
        │
        ▼
ACTUALIZAR COMPOSICIÓN
        │
        ├── pH
        ├── Acidez
        ├── Grasa
        ├── SNG
        ├── Proteína
        ├── Temperatura
        └── Densidad
        │
        ▼
ACTUALIZAR ESTADO DEL SILO
        │
        ├── Disponible
        ├── En llenado
        ├── En agitación
        ├── Esperando muestra
        ├── Liberado
        ├── Reservado
        ├── Alimentando línea
        ├── Vacío
        └── En CIP
        │
        ▼
ASIGNAR DESTINO
        │
        ├── Descremación
        ├── Estandarización
        ├── Condensación
        ├── Despacho
        └── Retención
```

## 8.2 Formulario oficial relacionado

- `CCAA.REC.FORM.005.01 – Aviso de Estandarización / Trazabilidad de Leche en Silos`.

## 8.3 Datos mínimos

```text
Número de vale
Fecha
Tipo de leche
Silo
Parte
Camiones de origen
Litros ingresados
Procedencia
Destino
Ingresos
Salidas
Saldo
pH
Acidez
Grasa
SNG
Proteína
Temperatura
Densidad
Inicio de llenado
Hora de muestra
Operador
```

---

# 9. Descremación

## 9.1 Flujo general

```text
LECHE FRESCA
      │
      ▼
DESCREMADORA
      │
      ├── CREMA
      └── LECHE DESCREMADA
```

## 9.2 Preparación

```text
ORDEN DE DESCREMACIÓN
        │
        ▼
VERIFICAR SILO DE ORIGEN
        │
        ▼
VERIFICAR CAPACIDAD DE DESTINO
        │
        ├── Estanque de crema
        └── Estanque de descremada
        │
        ▼
CAMBIAR CODOS A PRODUCCIÓN
        │
        ▼
CONECTAR LÍNEAS
        │
        ▼
ABRIR ENFRIAMIENTO Y AIRE
        │
        ▼
CONFIGURAR VÁLVULAS
        │
        ▼
INSPECCIÓN PREOPERATIVA
```

## 9.3 Arranque

```text
ARRANCAR DESCREMADORA
        │
        ▼
ALCANZAR 1.395 RPM
        │
        ▼
¿RPM CORRECTAS?
     ├── SÍ → Continuar
     └── NO
          ├── Quitar alarma
          ├── Reintentar
          └── Informar Mantenimiento
```

## 9.4 Control operacional

```text
CONTROL CADA HORA
        │
        ├── Descremadora
        ├── Pasteurizador
        ├── Bombas
        ├── Válvulas
        ├── Conexiones
        ├── Caudalímetros
        ├── Temperaturas
        ├── Fugas
        └── Obstrucciones
```

Reglas:

```text
Leche descremada:
materia grasa objetivo ≤ 0,1 %

Crema para despacho:
materia grasa objetivo entre 42 % y 43 %
```

---

# 10. Estandarización y relación RC

## 10.1 Fórmula conceptual

```text
RC = % materia grasa / % sólidos no grasos
```

## 10.2 Flujo de cálculo

```text
PROGRAMA DE PRODUCCIÓN
        │
        ▼
SELECCIONAR PRODUCTO
        │
        ├── RC 0,201
        ├── RC 0,422
        ├── Entero
        ├── Semidescremado
        └── Otro
        │
        ▼
CONSULTAR LECHE ENTERA
        │
        ├── Cantidad
        ├── Grasa
        └── SNG
        │
        ▼
CONSULTAR DESCREMADA
        │
        ├── Cantidad
        ├── Grasa
        └── SNG
        │
        ▼
CALCULAR
        │
        ├── Leche entera requerida
        ├── Leche a descremar
        ├── Descremada a agregar
        ├── Crema esperada
        └── Producto final esperado
        │
        ▼
GENERAR HOJA RC
```

## 10.3 Ejecución

```text
VALE APROBADO
        │
        ▼
SELECCIONAR SILO Y TK
        │
        ▼
CONECTAR CIRCUITO
        │
        ▼
TRANSFERIR
        │
        ▼
REGISTRAR CANTIDAD REAL
        │
        ▼
AGITAR 30 MINUTOS
        │
        ▼
TOMAR MUESTRA
        │
        ▼
ANALIZAR
        │
        ├── Grasa
        ├── SNG
        ├── Proteína
        ├── Densidad
        ├── pH
        └── Acidez
        │
        ▼
CALCULAR RC REAL
```

## 10.4 Decisión

```text
¿RC REAL CUMPLE?
     ├── SÍ
     │    ├── Liberar silo
     │    └── Avisar a Condensación
     │
     └── NO
          ├── Calcular corrección
          ├── Agregar leche entera o descremada
          ├── Reagitar
          └── Reanalizar
```

---

# 11. Entrega a Condensación

```text
SILO ESTANDARIZADO Y LIBERADO
        │
        ▼
PUBLICAR DISPONIBILIDAD
        │
        ├── Vale
        ├── Producto
        ├── Silo
        ├── Cantidad
        ├── RC
        ├── Grasa
        ├── SNG
        ├── Proteína
        ├── pH
        ├── Acidez
        ├── Temperatura
        └── Trazabilidad
        │
        ▼
CONDENSACIÓN SELECCIONA EVAPORADOR
        │
        ├── Scheffer 2
        ├── Scheffer 3
        └── VEB
        │
        ▼
RESERVAR SILO
        │
        ▼
INICIAR CONSUMO
```

---

# 12. Condensación

## 12.1 Preparación

```text
ORDEN DE PRODUCCIÓN
        │
        ▼
IDENTIFICAR PRODUCTO
        │
        ├── RC 0,201
        ├── RC 0,422
        ├── Leche entera en polvo
        ├── MSK
        └── Otro
        │
        ▼
SELECCIONAR EVAPORADOR
        │
        ├── Scheffer 2
        ├── Scheffer 3
        └── VEB
        │
        ▼
CHECKLIST DE CONDICIONES
        │
        ▼
HABILITAR O BLOQUEAR INICIO
```

## 12.2 Formularios de preparación

- `CCAA.Cond.FORM.005.01 – Check list CE Scheffers 2`.
- `CCAA.Cond.FORM.014.01 – Checklist CE Scheffer 3`.
- `CCAA.Cond.FORM.016.01 – Checklist CE VEB`.
- `CCAA.Cond.FORM.022.01 – Checklist Inspección Agitadores, Silos y Estanques Condensación`.

## 12.3 Proceso

```text
ALIMENTAR DESDE SILO
        │
        ▼
UPERIZACIÓN / TRATAMIENTO TÉRMICO
        │
        ▼
CONTROL PCC
        │
        ▼
EVAPORACIÓN
        │
        ▼
CONTROL DE PROCESO
        │
        ├── Flujo
        ├── Densidad
        ├── Temperaturas
        ├── Vacío
        ├── Presión
        ├── Sólidos totales
        ├── Materia grasa
        └── Acidez
        │
        ▼
ENFRIAMIENTO
        │
        ▼
ESTANQUE DE PRECONDENSADO
        │
        ▼
CONTROL DE CALIDAD
        │
        ▼
LIBERAR O BLOQUEAR
```

## 12.4 Formularios Scheffer 2

- `CCAA.Cond.FORM.001.05 – Control de Proceso Scheffer 2 RC 0,201`.
- `CCAA.Cond.FORM.006.06 – Control de Proceso Scheffer 2 RC 0,422`.
- `CCAA.Cond.FORM.009.05 – Control de Proceso Scheffer 2 Leche en Polvo`.
- `CCAA.Cond.FORM.021.01 – Control de Proceso Scheffer 2 MSK`.

## 12.5 Formularios Scheffer 3

- `CCAA.Cond.FORM.015.04 – Control de Proceso Scheffer 3 RC 0,201`.
- `CCAA.Cond.FORM.007.06 – Control de Proceso Scheffer 3 RC 0,422`.
- `CCAA.Cond.FORM.013.05 – Control de Proceso Scheffer 3 Leche Entera en Polvo`.

## 12.6 Formularios VEB

- `CCAA.Cond.FORM.012.04 – Control de Proceso VEB RC 0,201`.
- `CCAA.Cond.FORM.011.05 – Control de Proceso VEB RC 0,422`.
- `CCAA.Cond.FORM.010.04 – Control de Proceso VEB Leche Entera en Polvo`.
- `CCAA.Cond.FORM.020.01 – Control de Proceso VEB MSK`.

---

# 13. Secado

## 13.1 Preparación

```text
PROGRAMA DE PRODUCCIÓN
        │
        ▼
SELECCIONAR EGRON 1 O EGRON 2
        │
        ▼
VERIFICAR PRECONDENSADO
        │
        ▼
INSPECCIÓN PREOPERATIVA
        │
        ├── Torre limpia
        ├── Torre armada
        ├── Fluid bed limpio
        ├── Toberas y cribas
        ├── Filtros
        ├── Tecles
        ├── Conexión a tierra
        └── Ausencia de cuerpos extraños
        │
        ▼
HABILITAR O CORREGIR
```

## 13.2 Formularios

- `CCAA.SEC.FORM.003.01 – Inspección Preoperativa Egron 1 y 2`.
- `CCAA.SEC.FORM.008.01 – Condiciones Básicas de Tecles Torre Secado`.
- `CCAA.SEC.FORM.016.01 – Conexión a Tierra Egron 1`.
- `CCAA.SEC.FORM.041.01 – Conexión a Tierra Egron 2`.
- `CCAA.Sec.FORM.042.01 – Checklist Materiales de Vidrio`.
- `CCAA.SEC.FORM.020.01 – Filtros de Limpieza de Producto`.
- `CCAA.SEC.FORM.018 – Registro de Ingreso a Torre de Secado`.

## 13.3 Pulverización

```text
TORRE HABILITADA
        │
        ▼
RECIBIR PRECONDENSADO
        │
        ▼
PULVERIZAR
        │
        ▼
SECAR
        │
        ▼
POSTSECAR
        │
        ▼
ENFRIAR
        │
        ▼
TAMIZAR
        │
        ▼
TRANSFERIR A SILO DE POLVO
```

### Formularios de pulverización

- `CCAA.Sec.FORM.025.01 – Hoja de Pulverización Egron 1`.
- `CCAA.Sec.FORM.026.01 – Hoja de Pulverización Egron 2`.
- `CCAA.Sec.FORM.047.01 – Hoja de Pulverización Egron 1 y 2 MSK`.

### Controles

- `CCAA.SEC.FORM.013.01 – Controles Ayudante Secado Durante Proceso`.
- `CCAA.SEC.FORM.015.01 – Medición Sobrepresión Torre de Secado`.
- `CCAA.SEC.FORM.022.01 – Monitoreo PPRO Egron 1 y 2`.
- `CCAA.SEC.FORM.012.01 – Cuerpos Extraños Fluid Bed Egron 1`.
- `CCAA.Sec.FORM.021.01 – Dosificación de Lecitina`.
- `CCAA.Sec.FORM.011.01 – Control de Consumos de Materiales`.

## 13.4 Calidad de polvo

- `CCAA.SEC.FORM.001.03 – Análisis Fisicoquímico Egron 1 y 2`.
- `CCAA.Sec.FORM.019.03 – Formulario de Análisis Egron 1 y 2 LEP 27 %`.
- `CCAA.Sec.FORM.046.01 – Análisis Fisicoquímico Egron 1 y 2 MSK`.
- `CCAA.Calidad.FORM.033.02 – Plan de Autocontrol de Balanza Secado`.

---

# 14. Envase

## 14.1 Preparación

```text
LOTE LIBERADO DESDE SECADO
        │
        ▼
SELECCIONAR ROVEMA 3 O 4
        │
        ▼
VERIFICAR MATERIAL DE ENVASE
        │
        ▼
DESARMAR, ASEAR Y ARMAR
        │
        ▼
INSPECCIÓN OPERATIVA
        │
        ▼
HABILITAR EQUIPO
```

## 14.2 Formularios

- `CCAA.Sec.FORM.024.01 – Inspección Operativa Rovema 3 y 4`.
- `CCAA.SEC.FORM.004.01 – Desarme, Aseo y Armado Rovema 3 y 4`.
- `CCAA.SEC.FORM.007.02 – Checklist Cuerpos Extraños Rovema 3 y 4`.

## 14.3 Proceso

```text
ALIMENTAR PRODUCTO
        │
        ▼
FORMAR Y LLENAR BOLSA
        │
        ▼
CONTROLAR PESO
        │
        ▼
CONTROLAR HERMETICIDAD
        │
        ▼
CONTROLAR ROCE METÁLICO
        │
        ▼
DETECTOR DE METALES
        │
        ▼
CODIFICAR
        │
        ▼
FORMAR PALLET
        │
        ▼
PRODUCTO TERMINADO
```

### Formularios

- `CCAA.ENV.FORM.004.01 – Control de Hermeticidad y Peso Neto`.
- `CCAA.ENV.FORM.003.03 – PPRO Detector de Metales Rovema 3`.
- `CCAA.ENV.FORM.001.03 – PPRO Detector de Metales Rovema 4`.
- `CCAA.SEC.FORM.005.01 – Monitoreo PPRO Rovema 3 y Rovema 4`.

---

# 15. Mantequilla

## 15.1 Flujo

```text
CREMA LIBERADA
        │
        ▼
PASTEURIZAR
        │
        ▼
ACONDICIONAR
        │
        ▼
ECM-800
        │
        ├── Batido
        ├── Separación de suero
        ├── Formación de grano
        ├── Amasado
        └── Ajuste de humedad
        │
        ▼
ENVASAR
        │
        ▼
CÁMARA CLIMATIZADA
        │
        ▼
CONTROL DE CALIDAD
        │
        ▼
LIBERACIÓN
```

## 15.2 Formularios

- `CCAA.Calidad.FORM.005.01 – Estándar Visual Rutinas de Entrada Mantequilla`.
- `CCAA.MAN.FORM.009.01 – Control de Proceso Pasteurización`.
- `CCAA.MAN.FORM.001.02 – Control de Temperatura Cámara Climatizada`.
- `CCAA.MAN.DOC.001.01 – Estándar Medición Humedad en Mantequilla`.
- `CCAA.MAN.FORM.002.01 – CIP Crema Mantequilla`.

---

# 16. Calidad, dossier y liberación

## 16.1 Flujo

```text
CREAR LOTE
        │
        ▼
ABRIR DOSSIER
        │
        ▼
INCORPORAR REGISTROS
        │
        ├── Materia prima
        ├── Silos
        ├── Estandarización
        ├── Condensación
        ├── PCC
        ├── Secado
        ├── Análisis
        ├── Envase
        ├── PPRO
        ├── Materiales
        ├── Aseos críticos
        ├── Rework
        └── No conformidades
        │
        ▼
¿DOSSIER COMPLETO?
     ├── NO → Mantener bloqueado
     └── SÍ
          │
          ▼
     ¿RESULTADOS CONFORMES?
          ├── SÍ → Liberar
          └── NO
               ├── Reprocesar
               ├── Reclasificar
               ├── Concesión autorizada
               └── Destruir
```

## 16.2 Formularios

- `CCAA.Calidad.FORM.023.03 – Portada de Dossier`.
- `CCAA.Calidad.FORM.023.04 – Portada de Dossier Semielaborado`.
- `CCAA.Calidad.FORM.025.01 – TNC`.
- `CCAA.Calidad.FORM.029.01 – Producto No Conforme Proveedores`.
- `CCAA.Calidad.FORM.024 – Evaluación de Materias Primas`.

---

# 17. Rework y descarte

## 17.1 Rework

```text
GENERAR REWORK
        │
        ▼
IDENTIFICAR ORIGEN
        │
        ▼
PESAR
        │
        ▼
ASIGNAR LOTE
        │
        ▼
ROTULAR
        │
        ▼
ALMACENAR SEGREGADO
        │
        ▼
CALIDAD EVALÚA
        │
        ▼
¿APTO?
     ├── SÍ
     │    ├── Liberar
     │    ├── Asignar FEFO
     │    ├── Vincular a orden
     │    └── Registrar consumo
     │
     └── NO
          └── Convertir en descarte
```

## 17.2 Formularios

- `CCAA.Sec.FORM.017.02 – Entrega Manual de Reproceso`.
- `CCAA.SEC.FORM.017.01 – Planilla de Entrega Manual de Reproceso`.
- `CCAA.SEC.FORM.023.01 – Seguimiento FEFO`.
- `CCAA.SEC.FORM.014.01 – Registro de Polvo a Destrucción`.
- `CCAA.Sec.FORM.041.01 – Entrega Manual de Polvo de Descarte`.
- `CCAA.Fab.POE.001.01 – Manejo del Rework`.

---

# 18. Aseos y habilitación

Los aseos no deben mezclarse con el flujo principal, pero deben relacionarse con equipos, líneas y áreas.

## 18.1 Modelo general

```text
FIN DE PRODUCCIÓN
        │
        ▼
EQUIPO PENDIENTE DE ASEO
        │
        ▼
SELECCIONAR PROGRAMA
        │
        ├── CIP
        ├── COP
        ├── Aseo manual
        └── Aseo general
        │
        ▼
EJECUTAR
        │
        ├── Tiempo
        ├── Temperatura
        ├── Concentración
        ├── Flujo
        └── Enjuague
        │
        ▼
VERIFICAR
        │
        ▼
¿CONFORME?
     ├── SÍ → Liberar equipo
     └── NO → Repetir aseo
```

## 18.2 Aseos de Condensación

- `CCAA.COND.FORM.003.02 – Aseos Generales Condensación`.
- `CCAA.Cond.FORM.018.01 – CIP Línea de Silos hacia Condensación`.
- `CCAA.Cond.FORM.019.01 – Aseos Generales VEB`.
- `CCAA.Cond.FORM.017.01 – Limpieza de Pretiles`.
- `CCAA.Cond.FORM.008.01 – Limpieza y Preparación de Vortex`.
- `CCAA.Cond.FORM.004.01 – Carbonato y Concentración de Soda`.
- `Formato validación CIP`.

## 18.3 Aseos de Secado

- `CCAA.SEC.FORM.009.01 – Aseos Generales Torre Secado`.
- `CCAA.SEC.FORM.029.01 – Aseos Interiores Torre Egron 1`.
- `CCAA.SEC.FORM.030.01 – Aseos Interiores Torre Egron 2`.
- `CCAA.SEC.FORM.031.01 – Aseos Exteriores Torre Egron 1`.
- `CCAA.SEC.FORM.032.01 – Aseos Exteriores Torre Egron 2`.
- `CCAA.SEC.FORM.038.01 – Aseos Exteriores Aéreos Torre`.
- `CCAA.Sec.FORM.043.01 – Registro de Aseos Salas de Secado`.
- `CCAA.SEC.FORM.033.01 – Limpieza y Desinfección de Drenajes Egron 1 y 2`.
- `CCAA.SEC.FORM.037.01 – Control de Limpieza de Aspiradoras`.
- `CCAA.Sec.FORM.044.01 – Lavado y Desinfección de Tobera y Criba`.
- `CCAA.Sec.FORM.045.01 – Lavado y Secado de Materiales Área Secado`.

## 18.4 Aseos generales de Calidad

- `CCAA.Calidad.FORM.044.01 – Aseos Generales Laboratorio`.
- `CCAA.Calidad.FORM.001.02 – Aseos Generales Oficinas`.
- `CCAA.Calidad.FORM.002.02 – Aseos de Baños`.
- `CCAA.Calidad.FORM.014.01 – Limpieza Bodega SUSPEL`.
- `CCAA.Calidad.FORM.015.01 – Limpieza Bodega RESPEL`.

## 18.5 Regla de bloqueo

```text
ASEO CRÍTICO RECHAZADO
        │
        ▼
EQUIPO NO HABILITADO
        │
        ▼
NO SE PUEDE INICIAR PRODUCCIÓN
```

Los aseos de baños, oficinas y áreas comunes se gestionan mediante programa maestro, pero no se vinculan directamente con un lote salvo que exista un riesgo de inocuidad.

---

# 19. Inventario y materiales

El inventario debe administrar:

- Materias primas.
- Materiales de envase.
- Bolsas.
- Pita.
- Scrotch.
- Químicos.
- Materiales de limpieza.
- Repuestos.
- Rework.
- Producto intermedio.
- Producto terminado.

Estados recomendados:

```text
RECIBIDO
→ CUARENTENA
→ EN EVALUACIÓN
→ LIBERADO
→ RESERVADO
→ ENTREGADO A PRODUCCIÓN
→ CONSUMIDO
```

Alternativas:

```text
RECHAZADO
BLOQUEADO
DEVUELTO
VENCIDO
DAÑADO
```

Algunos materiales requieren aprobación de Calidad y otros no. Esto debe configurarse por producto:

```text
requiere_aprobacion_calidad = true / false
```

---

# 20. Roles y permisos

## 20.1 Roles principales

- Administrador general.
- Administrador de área.
- Planificación.
- Operaciones.
- Conductor.
- Recepción.
- Laboratorio.
- Fabricación.
- Condensación.
- Secado.
- Envase.
- Mantequilla.
- Calidad.
- Bodega.
- Despacho.
- Mantenimiento.
- Auditor.
- Visualizador.

## 20.2 Regla de administración

Un administrador de Producción no debe administrar necesariamente usuarios de Recepción.

Modelo recomendado:

```text
USUARIO
  │
  ├── ÁREA
  ├── ROL
  ├── PERMISOS
  ├── TURNOS
  └── PLANTA
```

Permisos por acción:

```text
ver
crear
editar
aprobar
rechazar
bloquear
liberar
cerrar
anular
exportar
administrar usuarios
```

---

# 21. Arquitectura técnica recomendada

## 21.1 Backend

```text
Python
└── Django
    ├── Django REST Framework
    ├── PostgreSQL
    ├── Redis
    ├── Celery
    ├── Celery Beat
    ├── WebSockets opcionales
    └── Auditoría
```

Responsabilidades:

- Reglas de negocio.
- API REST.
- Estados.
- Validaciones.
- Permisos.
- Trazabilidad.
- Integridad transaccional.
- Reportes.
- Automatizaciones.
- Auditoría.

## 21.2 Frontend

```text
TypeScript
└── React
    ├── React Router
    ├── TanStack Query
    ├── Formularios tipados
    ├── Componentes reutilizables
    ├── Tablas profesionales
    ├── Dashboards
    └── Diseño responsive
```

Responsabilidades:

- Interfaz por área.
- Formularios dinámicos.
- Validación inmediata.
- Visualización de estados.
- Alertas.
- Flujos guiados.
- Paneles.
- Trazabilidad visual.

## 21.3 Base de datos

PostgreSQL debe ser la fuente central de verdad.

Entidades principales:

```text
usuarios
areas
roles
permisos
proveedores
predios
salas
conductores
camiones
carros
modulos
estanques
recolecciones
cargas
recepciones
muestras
analisis
silos
movimientos_silo
ordenes_produccion
lotes
productos
formulas
equipos
lineas
procesos
etapas
controles
formularios
respuestas
aprobaciones
aseos
programas_cip
materiales
inventario
movimientos_inventario
rework
no_conformidades
dossiers
despachos
auditoria
```

---

# 22. Redis, Celery y Celery Beat

## Redis

Se recomienda para:

- Caché.
- Sesiones.
- Colas de Celery.
- Bloqueos distribuidos.
- Datos temporales.
- Optimización de consultas repetidas.

## Celery

Se recomienda para tareas en segundo plano:

- Generación de reportes.
- Creación de PDF.
- Envío de correos.
- Actualización de indicadores.
- Procesamiento de archivos.
- Cierre automático.
- Alertas.
- Sincronizaciones.

## Celery Beat

Se recomienda para tareas programadas:

- Revisar controles vencidos.
- Enviar recordatorios.
- Crear tareas periódicas.
- Verificar equipos pendientes.
- Detectar lotes sin liberar.
- Revisar inventario mínimo.
- Ejecutar reportes diarios.
- Programar aseos.

Redis, Celery y Celery Beat también pueden utilizarse en servidor local mientras los servicios estén levantados.

---

# 23. Dockerización

Servicios recomendados:

```text
frontend
backend
postgres
redis
celery_worker
celery_beat
nginx
```

Ejemplo conceptual:

```text
Docker Compose
├── React
├── Django API
├── PostgreSQL
├── Redis
├── Celery Worker
├── Celery Beat
└── Nginx
```

Beneficios:

- Entornos reproducibles.
- Configuración uniforme.
- Facilita desarrollo local.
- Facilita despliegue.
- Permite separar servicios.
- Simplifica mantenimiento.

---

# 24. Diseño UX/UI recomendado

La interfaz debe ser:

- Profesional.
- Limpia.
- Intuitiva.
- Adaptable.
- Rápida.
- Coherente.
- Accesible.
- Orientada a tareas.
- Diferenciada por área.

## 24.1 Estructura visual

```text
Barra lateral
├── Inicio
├── Mi área
├── Órdenes
├── Procesos
├── Controles
├── Calidad
├── Inventario
├── Aseos
├── Reportes
└── Administración
```

## 24.2 Pantallas por proceso

Cada pantalla debería mostrar:

```text
Encabezado
├── Orden
├── Lote
├── Producto
├── Equipo
├── Estado
└── Responsable

Contenido
├── Flujo de etapas
├── Formularios pendientes
├── Controles
├── Observaciones
├── Adjuntos
└── Historial

Panel lateral
├── Alertas
├── Bloqueos
├── Calidad
├── Aseo
└── Próxima acción
```

---

# 25. Reglas de negocio esenciales

1. No descargar leche sin aprobación de Calidad.
2. No utilizar un silo bloqueado.
3. No iniciar producción con equipo sin aseo aprobado.
4. No cerrar una etapa con controles obligatorios pendientes.
5. No liberar un lote con dossier incompleto.
6. No consumir material en cuarentena.
7. No agregar rework sin autorización.
8. No modificar registros aprobados sin generar una nueva versión.
9. Toda corrección debe dejar auditoría.
10. Los documentos obsoletos no deben generar tareas.
11. Un lote debe mantener trazabilidad hacia atrás y hacia adelante.
12. Una falla crítica de inocuidad debe bloquear el lote.
13. Los estados deben cambiar mediante acciones controladas.
14. Las aprobaciones deben registrar usuario, fecha y hora.
15. Un equipo no puede estar produciendo y en CIP simultáneamente.

---

# 26. Trazabilidad completa

## Hacia atrás

```text
LOTE TERMINADO
    │
    ├── Pallets
    ├── Bolsas
    ├── Rovema
    ├── Silo de polvo
    ├── Torre Egron
    ├── Precondensado
    ├── Evaporador
    ├── Vale de estandarización
    ├── Silos de leche fresca
    ├── Camiones
    ├── Módulos
    └── Proveedores
```

## Hacia adelante

```text
PROVEEDOR
    │
    ▼
RECOLECCIÓN
    │
    ▼
MÓDULO
    │
    ▼
SILO
    │
    ▼
ESTANDARIZACIÓN
    │
    ▼
PRECONDENSADO
    │
    ▼
LECHE EN POLVO
    │
    ▼
LOTE ENVASADO
    │
    ▼
PALLET
    │
    ▼
CLIENTE
```

---

# 27. Formularios digitales consolidados

No se recomienda crear una pantalla por cada archivo.

Formularios principales:

## Recolección

1. Recolección.
2. Cargas por módulo.
3. Voucher.
4. Muestra.

## Recepción

5. Recepción de camión.
6. Muestreo por módulo.
7. Control de leche fresca.
8. Desviación.
9. Descarga.
10. Movimiento de silo.

## Fabricación

11. Orden de descremación.
12. Control de descremación.
13. Hoja de RC.
14. Vale de estandarización.
15. Transferencia.
16. Análisis de silo.
17. Entrega de turno.

## Condensación

18. Checklist del equipo.
19. Control de proceso.
20. Control PCC.
21. Transferencia de precondensado.
22. Despacho de precondensado.

## Secado

23. Inspección preoperativa.
24. Hoja de pulverización.
25. Controles de proceso.
26. Análisis fisicoquímico.
27. Rework.
28. Descarte.

## Envase

29. Inspección de Rovema.
30. Peso y hermeticidad.
31. Detector de metales.
32. Cuerpos extraños.
33. Pallet terminado.

## Calidad

34. Evaluación de materia prima.
35. No conformidad.
36. Revisión de dossier.
37. Liberación.
38. Concesión.

## Aseos

39. Ejecución CIP.
40. Ejecución COP.
41. Aseo manual.
42. Inspección preoperativa.
43. Validación.
44. Aseos generales.

---

# 28. Fases recomendadas de implementación

## Fase 1 — Base maestra

- Usuarios.
- Roles.
- Áreas.
- Productos.
- Equipos.
- Silos.
- Estanques.
- Proveedores.
- Camiones.
- Módulos.
- Formularios.
- Auditoría.

## Fase 2 — Recolección y recepción

- Recolección.
- Voucher.
- Recepción.
- Muestras.
- Análisis.
- Descarga.
- Silos.

## Fase 3 — Fabricación

- Descremación.
- Crema.
- Leche descremada.
- Hoja RC.
- Estandarización.
- Transferencias.

## Fase 4 — Condensación

- Órdenes.
- Checklists.
- PCC.
- Controles.
- Precondensado.

## Fase 5 — Secado y envase

- Torres.
- Pulverización.
- Análisis.
- Rovemas.
- Detector de metales.
- Pallets.

## Fase 6 — Calidad y dossier

- No conformidades.
- Dossier.
- Liberación.
- Trazabilidad completa.

## Fase 7 — Inventario, aseos y mantenimiento

- MRP.
- EOQ.
- Materiales.
- CIP/COP.
- Programas de limpieza.
- Equipos.
- Mantenimiento.

## Fase 8 — Optimización

- Redis.
- Celery.
- Celery Beat.
- Reportes.
- Dashboards.
- Alertas.
- Integraciones.
- Docker.
- Producción.

---

# 29. Prompt profesional para analizar el sistema

```text
Actúa como arquitecto de software, diseñador UX/UI y desarrollador full stack senior especializado en Python, Django, Django REST Framework, React, TypeScript, PostgreSQL, Redis, Celery, Celery Beat, Docker y sistemas industriales.

Analiza completamente el sistema CCAA y su código fuente. Comprende los módulos existentes, los flujos de negocio, los modelos de datos, los endpoints, las rutas del frontend, los permisos, las validaciones, las consultas, las tareas en segundo plano y la experiencia de usuario.

Utiliza como referencia el documento de procesos de fábrica proporcionado. Relaciona cada módulo del sistema con los procesos reales de Recolección, Recepción, Calidad, Silos, Descremación, Estandarización, Condensación, Secado, Envase, Mantequilla, Inventario, Aseos, Mantenimiento, Dossier, Liberación y Despacho.

Objetivos:

1. Revisar la arquitectura actual.
2. Detectar errores, redundancias y acoplamientos.
3. Identificar procesos incompletos o mal modelados.
4. Proponer una arquitectura modular y escalable.
5. Revisar los modelos de PostgreSQL.
6. Revisar relaciones, índices y restricciones.
7. Revisar endpoints de Django REST Framework.
8. Revisar rutas, componentes y estado de React.
9. Implementar TypeScript estricto.
10. Diseñar interfaces profesionales e intuitivas.
11. Reducir formularios duplicados.
12. Implementar formularios dinámicos por producto, equipo y proceso.
13. Implementar estados, aprobaciones y bloqueos.
14. Implementar trazabilidad hacia atrás y hacia adelante.
15. Implementar auditoría completa.
16. Implementar permisos por área y acción.
17. Integrar Redis para caché y colas.
18. Integrar Celery para tareas de segundo plano.
19. Integrar Celery Beat para tareas programadas.
20. Preparar Docker Compose para desarrollo y producción.
21. Optimizar consultas y rendimiento.
22. Crear pruebas automáticas.
23. Mejorar la seguridad.
24. Preparar documentación técnica.
25. Crear un plan de migración gradual.

No copies los formularios antiguos literalmente. Extrae sus campos, reglas y responsabilidades. Consolida los formularios repetidos y crea componentes reutilizables.

La unidad central del sistema debe ser:

Orden de producción + lote + etapa + equipo + controles + materiales + trazabilidad + aprobaciones.

Entrega el análisis en este orden:

1. Resumen ejecutivo.
2. Arquitectura actual.
3. Problemas encontrados.
4. Mapa de módulos.
5. Flujo completo.
6. Modelo de datos propuesto.
7. Backend propuesto.
8. Frontend propuesto.
9. API propuesta.
10. Redis y Celery.
11. Seguridad.
12. Rendimiento.
13. UX/UI.
14. Plan de implementación.
15. Riesgos.
16. Prioridades.
17. Código o cambios recomendados.
```

---

# 30. Conclusión

El sistema CCAA debe representar cómo funciona realmente la fábrica y no solamente almacenar planillas.

La lógica central es:

```text
La producción avanza por etapas físicas.

Calidad, aseos, inventario, mantenimiento y trazabilidad
acompañan transversalmente cada lote.

Cada movimiento debe quedar relacionado con:
producto, lote, equipo, origen, destino, responsable,
fecha, hora, estado y evidencia.
```

La arquitectura recomendada es:

```text
Frontend:
React + TypeScript

Backend:
Python + Django + Django REST Framework

Base de datos:
PostgreSQL

Tareas y caché:
Redis + Celery + Celery Beat

Infraestructura:
Docker + Nginx
```

El sistema debe ser:

- Profesional.
- Intuitivo.
- Modular.
- Escalable.
- Seguro.
- Auditable.
- Trazable.
- Configurable.
- Orientado a procesos.
- Preparado para producción.
