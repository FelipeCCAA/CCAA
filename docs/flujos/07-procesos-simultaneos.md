# Procesos simultáneos

## Objetivo

Mostrar que CCAA administra varias corridas al mismo tiempo y bloquea solo el recurso físico en conflicto.

## Diagrama

```mermaid
flowchart TB
    TURNO[Turno productivo simultáneo]
    TURNO --> E1[Estandarización<br/>Lote EST-101<br/>Silo/TK A]
    TURNO --> D1[Descremado<br/>Lote DES-202<br/>Descremadora]
    TURNO --> M1[Mantequilla<br/>Lote MAN-303<br/>Línea mantequilla]
    TURNO --> V1[Evaporación A<br/>Lote EVA-404<br/>Evaporador 2]
    TURNO --> S1[Secado<br/>Lote SEC-505<br/>Torre 1]

    E1 --> OK1[Continúa]
    D1 --> OK2[Continúa]
    M1 --> OK3[Continúa]
    V1 --> OC[Evaporador 2<br/>OCUPADO]
    S1 --> OK5[Continúa]

    V2[Evaporación B<br/>Lote EVA-606] --> INT{Solicita<br/>Evaporador 2}
    INT -->|Ya ocupado por EVA-404| BLOQ[BLOQUEADA<br/>No se inicia]
    BLOQ -.-> NOTA[Los otros procesos<br/>no se detienen]

    class TURNO note;
    class E1,D1,M1,V1,S1,V2 process;
    class OK1,OK2,OK3,OK5 available;
    class OC occupied;
    class INT decision;
    class BLOQ blocked;
    class NOTA note;
    classDef process fill:#dbeafe,stroke:#2563eb,color:#172554;
    classDef available fill:#dcfce7,stroke:#16a34a,color:#14532d;
    classDef occupied fill:#ffedd5,stroke:#ea580c,color:#7c2d12;
    classDef blocked fill:#fee2e2,stroke:#dc2626,color:#7f1d1d;
    classDef decision fill:#fef3c7,stroke:#d97706,color:#78350f;
    classDef note fill:#f8fafc,stroke:#64748b,color:#1e293b;
```

## Explicación breve

Cada corrida mantiene su lote, material, equipo, almacenamiento y estado. Los procesos con recursos distintos pueden avanzar en paralelo. Si otra corrida intenta usar el mismo equipo, CCAA rechaza solamente ese inicio y conserva las demás operaciones.

## Estados o decisiones importantes

- `En preparación` reserva el equipo.
- `En ejecución`, `Pausada` y `Bloqueada` mantienen la ocupación.
- `Pendiente de control` no ocupa físicamente el equipo.
- Silos y TK también reservan saldo o capacidad durante operaciones largas.

## Validación del experto-procesos-lacteos

**CORRECTO.** La simultaneidad con equipos distintos y el rechazo de una colisión fueron comprobados mediante pruebas transaccionales.
