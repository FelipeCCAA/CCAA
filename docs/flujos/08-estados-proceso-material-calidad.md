# Estados de proceso, equipo, material y Calidad

## Objetivo

Evitar que un mismo estado se utilice para describir cuatro situaciones operacionales diferentes.

## Diagrama

```mermaid
flowchart LR
    CIERRE[Cierre físico de corrida] --> PROC[PROCESO<br/>Terminado]
    CIERRE --> EQ[EQUIPO<br/>Disponible]
    CIERRE --> TIPO[TIPO DE MATERIAL<br/>Materia prima / intermedio / terminado]
    TIPO --> CAL[ESTADO DE CALIDAD<br/>Pendiente]
    CAL -->|Resultado conforme| LIB[ESTADO DE CALIDAD<br/>Liberado]
    CAL -->|Resultado no conforme| RECH[ESTADO DE CALIDAD<br/>Rechazado / bloqueado]
    LIB --> SIG[Siguiente etapa]
    RECH --> DISP[Disposición definida<br/>por Calidad]

    class CIERRE,PROC process;
    class EQ equipment;
    class TIPO material;
    class CAL quality;
    class LIB approved;
    class RECH blocked;
    class SIG,DISP destination;
    classDef process fill:#dbeafe,stroke:#2563eb,color:#172554;
    classDef equipment fill:#e0f2fe,stroke:#0284c7,color:#0c4a6e;
    classDef material fill:#fef3c7,stroke:#d97706,color:#78350f;
    classDef quality fill:#fef9c3,stroke:#ca8a04,color:#713f12;
    classDef approved fill:#dcfce7,stroke:#16a34a,color:#14532d;
    classDef blocked fill:#fee2e2,stroke:#dc2626,color:#7f1d1d;
    classDef destination fill:#f3e8ff,stroke:#9333ea,color:#581c87;
```

## Explicación breve

Cerrar una corrida indica que la transformación física terminó. El equipo puede quedar disponible inmediatamente, aunque el material siga retenido. El tipo del material no cambia porque Calidad lo rechace: solamente cambia su estado de Calidad y su disposición permitida.

## Estados o decisiones importantes

- Estado del proceso: qué ocurrió con la corrida.
- Estado del equipo: si puede recibir otro trabajo.
- Tipo de material: materia prima/insumo, intermedio, terminado, coproducto, rework o merma según corresponda.
- Estado de Calidad: pendiente, liberado, rechazado o bloqueado.
- Ejemplo: `Material intermedio` + `Calidad pendiente`.

## Validación del experto-procesos-lacteos

**CORRECTO.** Esta separación coincide con Secado, Descremado, Mantequilla y las liberaciones intermedias implementadas.
