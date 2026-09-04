# Flujo de leche descremada

## Objetivo

Explicar cómo la leche descremada producida internamente queda habilitada para Estandarización y continúa por la ruta del producto elegido.

## Diagrama

```mermaid
flowchart LR
    REC[Recepción] --> Q1{Calidad leche}
    Q1 -->|Liberada| SILO[(Silo de origen)]
    SILO --> DES[Descremado]
    DES --> LD[Leche descremada<br/>lote + cantidad]
    DES --> CRE[Crema<br/>rama independiente]
    LD --> TK[(TK descremada)]
    TK --> Q2{Calidad / habilitación}
    Q2 -->|Liberada| EST[Estandarización]
    EST --> PROD{Producto y ruta<br/>seleccionados}
    PROD -->|Ruta de polvo| EVA[Evaporación]
    PROD -->|Otra ruta autorizada| SIG[Siguiente proceso]

    class REC,DES,EST,EVA,SIG process;
    class SILO,TK storage;
    class LD,CRE intermediate;
    class Q1,Q2 quality;
    class PROD decision;
    classDef process fill:#dbeafe,stroke:#2563eb,color:#172554;
    classDef storage fill:#e0f2fe,stroke:#0284c7,color:#0c4a6e;
    classDef intermediate fill:#fef3c7,stroke:#d97706,color:#78350f;
    classDef quality fill:#dcfce7,stroke:#16a34a,color:#14532d;
    classDef decision fill:#f3e8ff,stroke:#9333ea,color:#581c87;
```

## Explicación breve

La leche descremada no es leche en polvo ni un producto terminado: es un material intermedio en litros. Se almacena en su TK, espera su habilitación y luego puede alimentar un vale de Estandarización. Desde ahí continúa según la ruta del producto a fabricar.

## Estados o decisiones importantes

- Descremado reserva capacidad del TK antes de comenzar.
- La salida conserva su propio lote, cantidad, ubicación y ruta.
- Estandarización solo utiliza saldo disponible y liberado.
- React no decide la etapa posterior: la informa la ruta configurada.

## Validación del experto-procesos-lacteos

**CORRECTO CON OBSERVACIONES.** La salida y su acción hacia Estandarización fueron verificadas; falta confirmar en planta los maestros y completar una validación operacional prolongada de esta rama.
