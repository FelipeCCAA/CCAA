# Descremado como subproceso

## Objetivo

Destacar que una corrida de Descremado transforma una entrada en dos materiales trazables y operacionalmente independientes.

## Diagrama

```mermaid
flowchart TB
    L[Leche liberada<br/>silo + litros + composición] --> SUG[Sugerencia de balance]
    SUG --> CONF{Operador revisa,<br/>ajusta y confirma}
    CONF --> RES[Reservar origen,<br/>TK crema y TK descremada]
    RES --> DES[DESCREMADO]

    DES --> CRE[CREMA]
    DES --> LD[LECHE DESCREMADA]

    CRE --> DC[Identidad propia:<br/>lote + cantidad + TK<br/>Calidad + ruta + destino]
    LD --> DD[Identidad propia:<br/>lote + cantidad + TK<br/>Calidad + ruta + destino]

    DC --> QC{Calidad crema}
    QC -->|Ruta autorizada| MAN[Mantequilla]
    QC -->|Ruta autorizada| DSP[Despacho]
    QC -.->|Solo si existe esa ruta| ESTC[Estandarización]

    DD --> QD{Calidad descremada}
    QD -->|Liberada| ESTD[Estandarización]

    class SUG,RES,DES,MAN,DSP,ESTC,ESTD process;
    class L,CRE,LD,DC,DD material;
    class CONF decision;
    class QC,QD quality;
    classDef process fill:#dbeafe,stroke:#2563eb,color:#172554;
    classDef material fill:#fef3c7,stroke:#d97706,color:#78350f;
    classDef decision fill:#f3e8ff,stroke:#9333ea,color:#581c87;
    classDef quality fill:#dcfce7,stroke:#16a34a,color:#14532d;
```

## Explicación breve

CCAA calcula una sugerencia, pero el operador mantiene la decisión y debe confirmarla. Al cerrar, la corrida genera crema y leche descremada con registros separados. La decisión de Calidad o destino de una rama no cambia automáticamente la otra.

## Estados o decisiones importantes

- La sugerencia no inicia la corrida por sí sola.
- Las tres ubicaciones se reservan para evitar sobreasignación.
- Ambas salidas tienen lote, saldo, TK, Calidad, ruta y destino propios.
- Crema hacia Estandarización solo corresponde si existe una ruta autorizada.

## Validación del experto-procesos-lacteos

**CORRECTO CON OBSERVACIONES.** La bifurcación y sus liberaciones independientes son correctas; los parámetros definitivos de la descremadora siguen sujetos a validación de planta.
