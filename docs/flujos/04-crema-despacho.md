# Crema a despacho directo

## Objetivo

Mostrar cómo la crema comercial sale desde Descremado hacia un despacho a granel sin ingresar a Mantequilla.

## Diagrama

```mermaid
flowchart LR
    REC[Recepción] --> Q1{Calidad leche}
    Q1 -->|Liberada| SILO[(Silo)]
    SILO --> DES[Descremado]
    DES --> CRE[Crema<br/>lote independiente]
    DES --> LD[Leche descremada<br/>ruta separada]
    CRE --> TK[(TK crema)]
    TK --> Q2{Calidad crema}
    Q2 -->|Liberada para despacho| DISP[Crema disponible]
    DISP --> BOR[Despacho borrador]
    BOR --> AUT[Despacho autorizado]
    AUT --> SAL[Salida física del TK]
    SAL --> MOV[Saldo actualizado]

    class REC,DES process;
    class SILO,TK storage;
    class CRE,LD,DISP,BOR,AUT material;
    class Q1,Q2 quality;
    class SAL,MOV destination;
    classDef process fill:#dbeafe,stroke:#2563eb,color:#172554;
    classDef storage fill:#e0f2fe,stroke:#0284c7,color:#0c4a6e;
    classDef material fill:#fef3c7,stroke:#d97706,color:#78350f;
    classDef quality fill:#dcfce7,stroke:#16a34a,color:#14532d;
    classDef destination fill:#f3e8ff,stroke:#9333ea,color:#581c87;
```

## Explicación breve

El operador elige para la crema una ruta de despacho directo. Calidad decide sobre esa salida sin afectar la leche descremada hermana. Una vez autorizado y ejecutado el despacho, el movimiento físico reduce el saldo del TK.

## Estados o decisiones importantes

- Elegir despacho evita que la misma crema aparezca como insumo de Mantequilla.
- La liberación es independiente de la salida de leche descremada.
- El saldo autorizado queda comprometido para impedir doble uso.
- No se crean cajas, pallets ni producto terminado.

## Validación del experto-procesos-lacteos

**CORRECTO CON OBSERVACIONES.** La rama fue verificada por interfaz; los rangos definitivos de crema comercial deben ser confirmados por Calidad.
