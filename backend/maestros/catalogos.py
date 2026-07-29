"""
Catálogos compartidos del proceso productivo.

Traducidos de `prototipo/js/modelo/esquema.js` (CATALOGOS). Viven aquí, y no
repetidos en cada modelo, porque los usan varias apps: `produccion` evalúa los
análisis contra ellos y `maestros` define los rangos de las especificaciones.
"""

# Parámetros fisicoquímicos que se miden en un análisis y sobre los que una
# especificación declara rangos. La clave es la que se usa dentro de los campos
# JSON `Especificacion.rangos` y `Analisis.valores`.
PARAMETROS = {
    "humedad":     {"etiqueta": "Humedad",           "unidad": "%"},
    "mg":          {"etiqueta": "Materia grasa",     "unidad": "%"},
    "sng":         {"etiqueta": "Sólidos no grasos", "unidad": "%"},
    "st":          {"etiqueta": "Sólidos totales",   "unidad": "%"},
    "acidez":      {"etiqueta": "Acidez",            "unidad": "°D"},
    "ph":          {"etiqueta": "pH",                "unidad": ""},
    "temperatura": {"etiqueta": "Temperatura",       "unidad": "°C"},
    "pesoEsp":     {"etiqueta": "Peso específico",   "unidad": "g/mL"},
    "proteina":    {"etiqueta": "Proteína",          "unidad": "%"},
}

CLAVES_PARAMETROS = set(PARAMETROS)
