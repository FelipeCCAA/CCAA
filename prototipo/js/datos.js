/* ============================================================
   Capa de datos — Gestión Productiva Planta CCAA (leche en polvo y crema)
   Datos semilla tomados de los archivos reales de la planta.
   Funciona con file:// (sin servidor). Persiste en localStorage.
   ============================================================ */
const CLAVE_ALMACEN = "gpl_ccaa_v1";

const DATOS_SEMILLA = {
  "produccion": [
    {
      "semana": 20,
      "anio": 2026,
      "fecha": "2026-05-14",
      "producto": "Crema 42% CCAA",
      "mandante": "CCAA",
      "oc": 4581469467,
      "gd": 1253,
      "kg": 8180.0,
      "bolsas": "N/A",
      "destino": "Los Angeles",
      "op": null,
      "lote": "CCAA6133",
      "humedad": null,
      "mg": 42.7,
      "sng": 5.16,
      "st": 47.86,
      "acidez": 11.1,
      "ph": 6.7,
      "temperatura": 5.0,
      "pesoEsp": null,
      "proteina": null,
      "vencimiento": null,
      "linea": "",
      "horaInicio": "",
      "horaTermino": "",
      "observacion": "",
      "resultadoCalidad": "Conforme"
    },
    {
      "semana": 20,
      "anio": 2026,
      "fecha": "2026-05-14",
      "producto": "P. Semidescremado ST 45% CCAA",
      "mandante": "CCAA",
      "oc": 4581469422,
      "gd": 1258,
      "kg": 26120.0,
      "bolsas": "N/A",
      "destino": "Los Angeles",
      "op": null,
      "lote": "CCAA6134N",
      "humedad": null,
      "mg": 1.81,
      "sng": 9.44,
      "st": 11.25,
      "acidez": 24.7,
      "ph": 6.37,
      "temperatura": 8.0,
      "pesoEsp": null,
      "proteina": null,
      "vencimiento": null,
      "linea": "",
      "horaInicio": "",
      "horaTermino": "",
      "observacion": "",
      "resultadoCalidad": "Sin especificación"
    },
    {
      "semana": 20,
      "anio": 2026,
      "fecha": "2026-05-15",
      "producto": "LEP NESTLÉ",
      "mandante": "Nestlé",
      "oc": null,
      "gd": null,
      "kg": 13625.0,
      "bolsas": 545,
      "destino": "",
      "op": null,
      "lote": "",
      "humedad": null,
      "mg": null,
      "sng": null,
      "st": null,
      "acidez": null,
      "ph": null,
      "temperatura": null,
      "pesoEsp": null,
      "proteina": null,
      "vencimiento": null,
      "linea": "",
      "horaInicio": "",
      "horaTermino": "",
      "observacion": "",
      "resultadoCalidad": "Sin especificación"
    },
    {
      "semana": 20,
      "anio": 2026,
      "fecha": "2026-05-15",
      "producto": "Rwk NESTLÉ",
      "mandante": "Nestlé",
      "oc": null,
      "gd": null,
      "kg": 100.0,
      "bolsas": null,
      "destino": "",
      "op": null,
      "lote": "",
      "humedad": null,
      "mg": null,
      "sng": null,
      "st": null,
      "acidez": null,
      "ph": null,
      "temperatura": null,
      "pesoEsp": null,
      "proteina": null,
      "vencimiento": null,
      "linea": "",
      "horaInicio": "",
      "horaTermino": "",
      "observacion": "",
      "resultadoCalidad": "Sin especificación"
    },
    {
      "semana": 20,
      "anio": 2026,
      "fecha": "2026-05-16",
      "producto": "Crema 42% CCAA",
      "mandante": "CCAA",
      "oc": 4581469467,
      "gd": 1270,
      "kg": 19160.0,
      "bolsas": "N/A",
      "destino": "Surlat",
      "op": null,
      "lote": "CCAA6135",
      "humedad": null,
      "mg": 42.0,
      "sng": 5.22,
      "st": 47.22,
      "acidez": 11.2,
      "ph": 6.37,
      "temperatura": 5.0,
      "pesoEsp": null,
      "proteina": null,
      "vencimiento": null,
      "linea": "",
      "horaInicio": "",
      "horaTermino": "",
      "observacion": "",
      "resultadoCalidad": "No conforme"
    },
    {
      "semana": 20,
      "anio": 2026,
      "fecha": "2026-05-16",
      "producto": "P. Semidescremado ST 45% CCAA",
      "mandante": "CCAA",
      "oc": 4581469422,
      "gd": 1267,
      "kg": 28200.0,
      "bolsas": "N/A",
      "destino": "Los Angeles",
      "op": null,
      "lote": "CCAA6135N",
      "humedad": null,
      "mg": 2.03,
      "sng": 9.2,
      "st": 11.23,
      "acidez": 24.0,
      "ph": 6.34,
      "temperatura": 7.5,
      "pesoEsp": null,
      "proteina": null,
      "vencimiento": null,
      "linea": "",
      "horaInicio": "",
      "horaTermino": "",
      "observacion": "",
      "resultadoCalidad": "Sin especificación"
    },
    {
      "semana": 20,
      "anio": 2026,
      "fecha": "2026-05-16",
      "producto": "P. Semidescremado ST 45% CCAA",
      "mandante": "CCAA",
      "oc": 4581469422,
      "gd": 1268,
      "kg": 28950.0,
      "bolsas": "N/A",
      "destino": "Los Angeles",
      "op": null,
      "lote": "CCAA6135N",
      "humedad": null,
      "mg": 2.05,
      "sng": 9.2,
      "st": 11.25,
      "acidez": 25.0,
      "ph": 6.25,
      "temperatura": 7.0,
      "pesoEsp": null,
      "proteina": null,
      "vencimiento": null,
      "linea": "",
      "horaInicio": "",
      "horaTermino": "",
      "observacion": "",
      "resultadoCalidad": "Sin especificación"
    },
    {
      "semana": 20,
      "anio": 2026,
      "fecha": "2026-05-16",
      "producto": "P. Semidescremado ST 45% CCAA",
      "mandante": "CCAA",
      "oc": 4581469422,
      "gd": 1273,
      "kg": 26520.0,
      "bolsas": "N/A",
      "destino": "Los Angeles",
      "op": null,
      "lote": "CCAA6136N",
      "humedad": null,
      "mg": 2.05,
      "sng": 9.2,
      "st": 11.25,
      "acidez": 24.5,
      "ph": 6.35,
      "temperatura": 7.0,
      "pesoEsp": null,
      "proteina": null,
      "vencimiento": null,
      "linea": "",
      "horaInicio": "",
      "horaTermino": "",
      "observacion": "",
      "resultadoCalidad": "Sin especificación"
    },
    {
      "semana": 21,
      "anio": 2026,
      "fecha": "2026-05-18",
      "producto": "P. Entero ST 48%",
      "mandante": "CCAA",
      "oc": 4581365906,
      "gd": 1279,
      "kg": 25950.0,
      "bolsas": null,
      "destino": "Los Angeles",
      "op": null,
      "lote": "CCAA6138N",
      "humedad": null,
      "mg": 4.12,
      "sng": 7.8,
      "st": 47.68,
      "acidez": 21.0,
      "ph": 6.39,
      "temperatura": 7.0,
      "pesoEsp": null,
      "proteina": null,
      "vencimiento": null,
      "linea": "",
      "horaInicio": "",
      "horaTermino": "",
      "observacion": "",
      "resultadoCalidad": "No conforme"
    },
    {
      "semana": 21,
      "anio": 2026,
      "fecha": "2026-05-18",
      "producto": "P. Semidescremado ST 45% CCAA",
      "mandante": "CCAA",
      "oc": 4581469422,
      "gd": 1275,
      "kg": 25920.0,
      "bolsas": null,
      "destino": "Los Angeles",
      "op": null,
      "lote": "CCAA6138N",
      "humedad": null,
      "mg": 2.07,
      "sng": 9.33,
      "st": 45.6,
      "acidez": 25.0,
      "ph": 6.37,
      "temperatura": 7.0,
      "pesoEsp": null,
      "proteina": null,
      "vencimiento": null,
      "linea": "",
      "horaInicio": "",
      "horaTermino": "",
      "observacion": "",
      "resultadoCalidad": "Sin especificación"
    },
    {
      "semana": 21,
      "anio": 2026,
      "fecha": "2026-05-19",
      "producto": "Crema 42% CCAA",
      "mandante": "CCAA",
      "oc": 4581469467,
      "gd": 1281,
      "kg": 5400.0,
      "bolsas": null,
      "destino": "Macul",
      "op": null,
      "lote": "CCAA6139",
      "humedad": null,
      "mg": 43.67,
      "sng": 5.07,
      "st": 48.74,
      "acidez": 12.0,
      "ph": 6.68,
      "temperatura": 5.0,
      "pesoEsp": null,
      "proteina": null,
      "vencimiento": null,
      "linea": "",
      "horaInicio": "",
      "horaTermino": "",
      "observacion": "",
      "resultadoCalidad": "Conforme"
    },
    {
      "semana": 21,
      "anio": 2026,
      "fecha": "2026-05-19",
      "producto": "P. Entero ST 48%",
      "mandante": "CCAA",
      "oc": 4581365906,
      "gd": 1288,
      "kg": 25980.0,
      "bolsas": null,
      "destino": "Los Angeles",
      "op": null,
      "lote": "CCAA6139N",
      "humedad": null,
      "mg": 3.15,
      "sng": 8.38,
      "st": 46.12,
      "acidez": 20.5,
      "ph": 6.35,
      "temperatura": 7.0,
      "pesoEsp": null,
      "proteina": null,
      "vencimiento": null,
      "linea": "",
      "horaInicio": "",
      "horaTermino": "",
      "observacion": "",
      "resultadoCalidad": "No conforme"
    },
    {
      "semana": 21,
      "anio": 2026,
      "fecha": "2026-05-19",
      "producto": "Crema 42% CCAA",
      "mandante": "CCAA",
      "oc": 4581469467,
      "gd": 1287,
      "kg": 9390.0,
      "bolsas": null,
      "destino": "Los Angeles",
      "op": null,
      "lote": "CCAA6139",
      "humedad": null,
      "mg": 43.4,
      "sng": 5.09,
      "st": 48.49,
      "acidez": 11.3,
      "ph": 6.69,
      "temperatura": 5.0,
      "pesoEsp": null,
      "proteina": null,
      "vencimiento": null,
      "linea": "",
      "horaInicio": "",
      "horaTermino": "",
      "observacion": "",
      "resultadoCalidad": "Conforme"
    },
    {
      "semana": 21,
      "anio": 2026,
      "fecha": "2026-05-20",
      "producto": "Crema 42% CCAA",
      "mandante": "CCAA",
      "oc": 4581469467,
      "gd": 1291,
      "kg": 7910.0,
      "bolsas": null,
      "destino": "Los Angeles",
      "op": null,
      "lote": "CCAA6140",
      "humedad": null,
      "mg": 41.16,
      "sng": 5.3,
      "st": 46.46,
      "acidez": 11.3,
      "ph": 6.69,
      "temperatura": 5.0,
      "pesoEsp": null,
      "proteina": null,
      "vencimiento": null,
      "linea": "",
      "horaInicio": "",
      "horaTermino": "",
      "observacion": "",
      "resultadoCalidad": "Conforme"
    },
    {
      "semana": 21,
      "anio": 2026,
      "fecha": "2026-05-20",
      "producto": "P. Semidescremado ST 45% CCAA",
      "mandante": "CCAA",
      "oc": 4581469422,
      "gd": 1289,
      "kg": 26090.0,
      "bolsas": null,
      "destino": "Los Angeles",
      "op": null,
      "lote": "CCAA6139N",
      "humedad": null,
      "mg": 1.9,
      "sng": 9.51,
      "st": 45.64,
      "acidez": 24.5,
      "ph": 6.27,
      "temperatura": 7.0,
      "pesoEsp": null,
      "proteina": null,
      "vencimiento": null,
      "linea": "",
      "horaInicio": "",
      "horaTermino": "",
      "observacion": "",
      "resultadoCalidad": "Sin especificación"
    },
    {
      "semana": 21,
      "anio": 2026,
      "fecha": "2026-05-20",
      "producto": "P. Semidescremado ST 45% CCAA",
      "mandante": "CCAA",
      "oc": 4581469422,
      "gd": 1294,
      "kg": 27490.0,
      "bolsas": null,
      "destino": "Los Angeles",
      "op": null,
      "lote": "CCAA6140N",
      "humedad": null,
      "mg": 1.97,
      "sng": 9.25,
      "st": 44.88,
      "acidez": 22.4,
      "ph": 6.33,
      "temperatura": 7.0,
      "pesoEsp": null,
      "proteina": null,
      "vencimiento": null,
      "linea": "",
      "horaInicio": "",
      "horaTermino": "",
      "observacion": "",
      "resultadoCalidad": "Sin especificación"
    },
    {
      "semana": 21,
      "anio": 2026,
      "fecha": "2026-05-20",
      "producto": "P. Entero ST 48%",
      "mandante": "CCAA",
      "oc": 4581365906,
      "gd": 1295,
      "kg": 24390.0,
      "bolsas": null,
      "destino": "Los Angeles",
      "op": null,
      "lote": "CCAA6140N",
      "humedad": null,
      "mg": 3.89,
      "sng": 7.96,
      "st": 47.4,
      "acidez": 20.6,
      "ph": 6.32,
      "temperatura": 7.0,
      "pesoEsp": null,
      "proteina": null,
      "vencimiento": null,
      "linea": "",
      "horaInicio": "",
      "horaTermino": "",
      "observacion": "",
      "resultadoCalidad": "No conforme"
    },
    {
      "semana": 21,
      "anio": 2026,
      "fecha": "2026-05-20",
      "producto": "Leche estandarizada - Lácteos Nebe",
      "mandante": "Lácteos Nebe",
      "oc": null,
      "gd": 1293,
      "kg": 27410.0,
      "bolsas": null,
      "destino": "Loncoche",
      "op": null,
      "lote": "CCAA6141",
      "humedad": null,
      "mg": 4.06,
      "sng": 9.13,
      "st": 13.19,
      "acidez": 15.5,
      "ph": 6.74,
      "temperatura": 6.0,
      "pesoEsp": null,
      "proteina": null,
      "vencimiento": null,
      "linea": "",
      "horaInicio": "",
      "horaTermino": "",
      "observacion": "",
      "resultadoCalidad": "Sin especificación"
    },
    {
      "semana": 21,
      "anio": 2026,
      "fecha": "2026-05-22",
      "producto": "P. Semidescremado ST 45% CCAA",
      "mandante": "CCAA",
      "oc": 4581469422,
      "gd": null,
      "kg": null,
      "bolsas": null,
      "destino": "",
      "op": null,
      "lote": "",
      "humedad": null,
      "mg": null,
      "sng": null,
      "st": null,
      "acidez": null,
      "ph": null,
      "temperatura": null,
      "pesoEsp": null,
      "proteina": null,
      "vencimiento": null,
      "linea": "",
      "horaInicio": "",
      "horaTermino": "",
      "observacion": "",
      "resultadoCalidad": "Sin especificación"
    },
    {
      "semana": 21,
      "anio": 2026,
      "fecha": "2026-05-22",
      "producto": "Leche estandarizada - Lácteos Nebe",
      "mandante": "Lácteos Nebe",
      "oc": null,
      "gd": 1297,
      "kg": 27060.0,
      "bolsas": null,
      "destino": "Loncoche",
      "op": null,
      "lote": "CCAA6142",
      "humedad": null,
      "mg": 4.61,
      "sng": 9.15,
      "st": 13.76,
      "acidez": 15.5,
      "ph": 6.69,
      "temperatura": 6.2,
      "pesoEsp": null,
      "proteina": null,
      "vencimiento": null,
      "linea": "",
      "horaInicio": "",
      "horaTermino": "",
      "observacion": "",
      "resultadoCalidad": "Sin especificación"
    },
    {
      "semana": 21,
      "anio": 2026,
      "fecha": "2026-05-22",
      "producto": "P. Entero ST 48%",
      "mandante": "CCAA",
      "oc": 4581365906,
      "gd": null,
      "kg": null,
      "bolsas": null,
      "destino": "",
      "op": null,
      "lote": "",
      "humedad": null,
      "mg": null,
      "sng": null,
      "st": null,
      "acidez": null,
      "ph": null,
      "temperatura": null,
      "pesoEsp": null,
      "proteina": null,
      "vencimiento": null,
      "linea": "",
      "horaInicio": "",
      "horaTermino": "",
      "observacion": "",
      "resultadoCalidad": "Sin control"
    },
    {
      "semana": 21,
      "anio": 2026,
      "fecha": "2026-05-23",
      "producto": "Crema 42% CCAA",
      "mandante": "CCAA",
      "oc": 4581469467,
      "gd": null,
      "kg": null,
      "bolsas": null,
      "destino": "",
      "op": null,
      "lote": "",
      "humedad": null,
      "mg": null,
      "sng": null,
      "st": null,
      "acidez": null,
      "ph": null,
      "temperatura": null,
      "pesoEsp": null,
      "proteina": null,
      "vencimiento": null,
      "linea": "",
      "horaInicio": "",
      "horaTermino": "",
      "observacion": "",
      "resultadoCalidad": "Sin control"
    },
    {
      "semana": 21,
      "anio": 2026,
      "fecha": "2026-05-23",
      "producto": "P. Semidescremado ST 45% CCAA",
      "mandante": "CCAA",
      "oc": 4581469422,
      "gd": null,
      "kg": null,
      "bolsas": null,
      "destino": "",
      "op": null,
      "lote": "",
      "humedad": null,
      "mg": null,
      "sng": null,
      "st": null,
      "acidez": null,
      "ph": null,
      "temperatura": null,
      "pesoEsp": null,
      "proteina": null,
      "vencimiento": null,
      "linea": "",
      "horaInicio": "",
      "horaTermino": "",
      "observacion": "",
      "resultadoCalidad": "Sin especificación"
    },
    {
      "semana": 21,
      "anio": 2026,
      "fecha": "2026-05-23",
      "producto": "P. Entero ST 48%",
      "mandante": "CCAA",
      "oc": 4581365906,
      "gd": null,
      "kg": null,
      "bolsas": null,
      "destino": "",
      "op": null,
      "lote": "",
      "humedad": null,
      "mg": null,
      "sng": null,
      "st": null,
      "acidez": null,
      "ph": null,
      "temperatura": null,
      "pesoEsp": null,
      "proteina": null,
      "vencimiento": null,
      "linea": "",
      "horaInicio": "",
      "horaTermino": "",
      "observacion": "",
      "resultadoCalidad": "Sin control"
    }
  ],
  "recepcion": [
    {
      "id": "REC-260504-01",
      "fecha": "2026-05-04",
      "silo": "SILO 1",
      "procedencia": "Nestlé",
      "tipoLeche": "Entera",
      "litros": 56488,
      "camion": "BKSX97",
      "operador": "Cristian Navarro",
      "turno": "A",
      "temperatura": 4.2,
      "acidez": 15.5,
      "ph": 6.7,
      "delvoTest": "Negativo",
      "inhibidores": "Negativo",
      "crioscopia": -0.52,
      "destino": "Descremación",
      "estado": "Liberada"
    },
    {
      "id": "REC-260504-02",
      "fecha": "2026-05-04",
      "silo": "SILO 3",
      "procedencia": "Nestlé",
      "tipoLeche": "Entera",
      "litros": 119668,
      "camion": "HKRC88",
      "operador": "Francisco Ruiz",
      "turno": "A",
      "temperatura": 4.0,
      "acidez": 16.0,
      "ph": 6.68,
      "delvoTest": "Negativo",
      "inhibidores": "Negativo",
      "crioscopia": -0.515,
      "destino": "RC 0,422",
      "estado": "Liberada"
    },
    {
      "id": "REC-260504-03",
      "fecha": "2026-05-04",
      "silo": "TK LD 2",
      "procedencia": "P Unión",
      "tipoLeche": "Descremada",
      "litros": 111496,
      "camion": "JFTP68",
      "operador": "John Aguilar",
      "turno": "B",
      "temperatura": 5.1,
      "acidez": 16.8,
      "ph": 6.61,
      "delvoTest": "Negativo",
      "inhibidores": "Negativo",
      "crioscopia": -0.512,
      "destino": "RC 0,201",
      "estado": "Liberada"
    },
    {
      "id": "REC-260504-04",
      "fecha": "2026-05-04",
      "silo": "SILO 2",
      "procedencia": "Nestlé",
      "tipoLeche": "Entera",
      "litros": 24740,
      "camion": "BGVV31",
      "operador": "Nelson Werner",
      "turno": "C",
      "temperatura": 6.3,
      "acidez": 18.5,
      "ph": 6.45,
      "delvoTest": "Negativo",
      "inhibidores": "Positivo",
      "crioscopia": -0.505,
      "destino": "Retenida",
      "estado": "Retenida"
    }
  ],
  "liberaciones": [
    {
      "id": "LIB-6134",
      "lote": "CCAA6134N",
      "producto": "P. Semidescremado ST 45% CCAA",
      "fecha": "2026-05-14",
      "especialista": "Camila Rauque",
      "estado": "Liberado",
      "checklist": [
        {
          "documento": "CCAA.REC.FORM.002.01 Planilla de Instructivo",
          "completado": true
        },
        {
          "documento": "Formularios de control de proceso (PCC)",
          "completado": true
        },
        {
          "documento": "Checklist de cuerpos extraños evaporadores",
          "completado": true
        },
        {
          "documento": "Hoja de pulverización E1 y E2",
          "completado": true
        },
        {
          "documento": "Disco de uperización",
          "completado": true
        },
        {
          "documento": "Inspección preoperativa E1 y E2",
          "completado": true
        },
        {
          "documento": "Conexión de tierra E1 - E2",
          "completado": true
        },
        {
          "documento": "Formulario fisicoquímicos E1 y E2",
          "completado": true
        },
        {
          "documento": "Formulario de filtros de limpieza",
          "completado": true
        },
        {
          "documento": "Monitoreo de PPRO E1 y E2",
          "completado": true
        },
        {
          "documento": "Monitoreo de PPRO Rovemas 3 y 4",
          "completado": true
        },
        {
          "documento": "Checklist cuerpos extraños Rovema 3 y 4",
          "completado": true
        },
        {
          "documento": "Seguimiento FEFO",
          "completado": true
        },
        {
          "documento": "Monitoreo PPRO Detector de metales",
          "completado": true
        },
        {
          "documento": "Control de consumo de materiales",
          "completado": true
        },
        {
          "documento": "Control de hermeticidad y peso neto",
          "completado": true
        },
        {
          "documento": "Registro de evaluación sensorial",
          "completado": true
        },
        {
          "documento": "Informe de laboratorio externo",
          "completado": true
        },
        {
          "documento": "CCAA.Calidad.FORM.016.02 Certificado de Análisis",
          "completado": true
        }
      ]
    },
    {
      "id": "LIB-6133",
      "lote": "CCAA6133",
      "producto": "Crema 42% CCAA",
      "fecha": "2026-05-14",
      "especialista": "Juan Calderón",
      "estado": "Liberado",
      "checklist": [
        {
          "documento": "CCAA.REC.FORM.002.01 Planilla de Instructivo",
          "completado": true
        },
        {
          "documento": "Formularios de control de proceso (PCC)",
          "completado": true
        },
        {
          "documento": "Checklist de cuerpos extraños evaporadores",
          "completado": true
        },
        {
          "documento": "Hoja de pulverización E1 y E2",
          "completado": true
        },
        {
          "documento": "Disco de uperización",
          "completado": true
        },
        {
          "documento": "Inspección preoperativa E1 y E2",
          "completado": true
        },
        {
          "documento": "Conexión de tierra E1 - E2",
          "completado": true
        },
        {
          "documento": "Formulario fisicoquímicos E1 y E2",
          "completado": true
        },
        {
          "documento": "Formulario de filtros de limpieza",
          "completado": true
        },
        {
          "documento": "Monitoreo de PPRO E1 y E2",
          "completado": true
        },
        {
          "documento": "Monitoreo de PPRO Rovemas 3 y 4",
          "completado": true
        },
        {
          "documento": "Checklist cuerpos extraños Rovema 3 y 4",
          "completado": true
        },
        {
          "documento": "Seguimiento FEFO",
          "completado": true
        },
        {
          "documento": "Monitoreo PPRO Detector de metales",
          "completado": true
        },
        {
          "documento": "Control de consumo de materiales",
          "completado": true
        },
        {
          "documento": "Control de hermeticidad y peso neto",
          "completado": true
        },
        {
          "documento": "Registro de evaluación sensorial",
          "completado": true
        },
        {
          "documento": "Informe de laboratorio externo",
          "completado": true
        },
        {
          "documento": "CCAA.Calidad.FORM.016.02 Certificado de Análisis",
          "completado": true
        }
      ]
    },
    {
      "id": "LIB-6140",
      "lote": "CCAA6140N",
      "producto": "P. Entero ST 48%",
      "fecha": "2026-05-22",
      "especialista": "Camila Rauque",
      "estado": "En revisión",
      "checklist": [
        {
          "documento": "CCAA.REC.FORM.002.01 Planilla de Instructivo",
          "completado": true
        },
        {
          "documento": "Formularios de control de proceso (PCC)",
          "completado": true
        },
        {
          "documento": "Checklist de cuerpos extraños evaporadores",
          "completado": true
        },
        {
          "documento": "Hoja de pulverización E1 y E2",
          "completado": true
        },
        {
          "documento": "Disco de uperización",
          "completado": true
        },
        {
          "documento": "Inspección preoperativa E1 y E2",
          "completado": true
        },
        {
          "documento": "Conexión de tierra E1 - E2",
          "completado": true
        },
        {
          "documento": "Formulario fisicoquímicos E1 y E2",
          "completado": true
        },
        {
          "documento": "Formulario de filtros de limpieza",
          "completado": true
        },
        {
          "documento": "Monitoreo de PPRO E1 y E2",
          "completado": true
        },
        {
          "documento": "Monitoreo de PPRO Rovemas 3 y 4",
          "completado": true
        },
        {
          "documento": "Checklist cuerpos extraños Rovema 3 y 4",
          "completado": true
        },
        {
          "documento": "Seguimiento FEFO",
          "completado": true
        },
        {
          "documento": "Monitoreo PPRO Detector de metales",
          "completado": true
        },
        {
          "documento": "Control de consumo de materiales",
          "completado": false
        },
        {
          "documento": "Control de hermeticidad y peso neto",
          "completado": false
        },
        {
          "documento": "Registro de evaluación sensorial",
          "completado": false
        },
        {
          "documento": "Informe de laboratorio externo",
          "completado": false
        },
        {
          "documento": "CCAA.Calidad.FORM.016.02 Certificado de Análisis",
          "completado": false
        }
      ]
    },
    {
      "id": "LIB-6142",
      "lote": "CCAA6142",
      "producto": "Crema 42% CCAA",
      "fecha": "2026-05-23",
      "especialista": "Juan Calderón",
      "estado": "Pendiente",
      "checklist": [
        {
          "documento": "CCAA.REC.FORM.002.01 Planilla de Instructivo",
          "completado": true
        },
        {
          "documento": "Formularios de control de proceso (PCC)",
          "completado": true
        },
        {
          "documento": "Checklist de cuerpos extraños evaporadores",
          "completado": true
        },
        {
          "documento": "Hoja de pulverización E1 y E2",
          "completado": true
        },
        {
          "documento": "Disco de uperización",
          "completado": true
        },
        {
          "documento": "Inspección preoperativa E1 y E2",
          "completado": true
        },
        {
          "documento": "Conexión de tierra E1 - E2",
          "completado": false
        },
        {
          "documento": "Formulario fisicoquímicos E1 y E2",
          "completado": false
        },
        {
          "documento": "Formulario de filtros de limpieza",
          "completado": false
        },
        {
          "documento": "Monitoreo de PPRO E1 y E2",
          "completado": false
        },
        {
          "documento": "Monitoreo de PPRO Rovemas 3 y 4",
          "completado": false
        },
        {
          "documento": "Checklist cuerpos extraños Rovema 3 y 4",
          "completado": false
        },
        {
          "documento": "Seguimiento FEFO",
          "completado": false
        },
        {
          "documento": "Monitoreo PPRO Detector de metales",
          "completado": false
        },
        {
          "documento": "Control de consumo de materiales",
          "completado": false
        },
        {
          "documento": "Control de hermeticidad y peso neto",
          "completado": false
        },
        {
          "documento": "Registro de evaluación sensorial",
          "completado": false
        },
        {
          "documento": "Informe de laboratorio externo",
          "completado": false
        },
        {
          "documento": "CCAA.Calidad.FORM.016.02 Certificado de Análisis",
          "completado": false
        }
      ]
    }
  ],
  "maestros": [
    {
      "vehiculo": 6017041,
      "placa": "BKSX97",
      "transportista": "Luis Alejandro Flores Borquez",
      "tipo": "Camión",
      "capacidad": 16000.0,
      "choferAM": "",
      "choferPM": ""
    },
    {
      "vehiculo": 6017042,
      "placa": "JFTP68",
      "transportista": "Luis Alejandro Flores Borquez",
      "tipo": "Camión",
      "capacidad": 15000.0,
      "choferAM": "",
      "choferPM": ""
    },
    {
      "vehiculo": 6017043,
      "placa": "HKRC88",
      "transportista": "Renato Teobaldo Kahler González",
      "tipo": "Camión",
      "capacidad": 15500.0,
      "choferAM": "",
      "choferPM": ""
    },
    {
      "vehiculo": 6017044,
      "placa": "HYBS56",
      "transportista": "Renato Teobaldo Kahler González",
      "tipo": "Camión",
      "capacidad": 15500.0,
      "choferAM": "",
      "choferPM": ""
    },
    {
      "vehiculo": 6017045,
      "placa": "FWHF70",
      "transportista": "Luis Alejandro Flores Borquez",
      "tipo": "Camión",
      "capacidad": 17500.0,
      "choferAM": "",
      "choferPM": ""
    },
    {
      "vehiculo": 6017046,
      "placa": "HRWD18",
      "transportista": "Transportes Arnold y Cia Ltda",
      "tipo": "Camión",
      "capacidad": 15500.0,
      "choferAM": "",
      "choferPM": ""
    },
    {
      "vehiculo": 6017047,
      "placa": "WR8456",
      "transportista": "Gilberto Mas Becker",
      "tipo": "Camión",
      "capacidad": 14500.0,
      "choferAM": "",
      "choferPM": ""
    },
    {
      "vehiculo": 6017048,
      "placa": "",
      "transportista": "Nestle",
      "tipo": "Camión",
      "capacidad": 20000.0,
      "choferAM": "",
      "choferPM": ""
    },
    {
      "vehiculo": 6017050,
      "placa": "BKSX 96",
      "transportista": "Luis Alejandro Flores Borquez",
      "tipo": "Camión",
      "capacidad": 14000.0,
      "choferAM": "",
      "choferPM": ""
    },
    {
      "vehiculo": 6017051,
      "placa": "FYPG55",
      "transportista": "Transportes Arnold y Cia Ltda",
      "tipo": "Camión",
      "capacidad": 20000.0,
      "choferAM": "",
      "choferPM": ""
    },
    {
      "vehiculo": 6017052,
      "placa": "JWZW68",
      "transportista": "Transportes Arnold y Cia Ltda",
      "tipo": "Camión",
      "capacidad": 15500.0,
      "choferAM": "",
      "choferPM": ""
    },
    {
      "vehiculo": 6017053,
      "placa": "CCHC33",
      "transportista": "Gilberto Mas Becker",
      "tipo": "Camión",
      "capacidad": 15200.0,
      "choferAM": "",
      "choferPM": ""
    },
    {
      "vehiculo": 6017054,
      "placa": "BZFF89",
      "transportista": "Luis Alejandro Flores Borquez",
      "tipo": "Camión",
      "capacidad": 14800.0,
      "choferAM": "",
      "choferPM": ""
    },
    {
      "vehiculo": 6017055,
      "placa": "DJXP99",
      "transportista": "Luis Alejandro Flores Borquez",
      "tipo": "Camión",
      "capacidad": 18500.0,
      "choferAM": "",
      "choferPM": ""
    },
    {
      "vehiculo": 6017057,
      "placa": "PCKD24",
      "transportista": "Renato Teobaldo Kahler González",
      "tipo": "Camión",
      "capacidad": 16300.0,
      "choferAM": "",
      "choferPM": ""
    },
    {
      "vehiculo": 6017058,
      "placa": "BDDW77",
      "transportista": "Luis Alejandro Flores Borquez",
      "tipo": "Camión",
      "capacidad": 15000.0,
      "choferAM": "",
      "choferPM": ""
    },
    {
      "vehiculo": 6017059,
      "placa": "FYLY76",
      "transportista": "Renato Teobaldo Kahler González",
      "tipo": "Camión",
      "capacidad": 17000.0,
      "choferAM": "",
      "choferPM": ""
    },
    {
      "vehiculo": 6017060,
      "placa": "CWFT95",
      "transportista": "Guido Bernardo Triviño Aguila",
      "tipo": "Camión",
      "capacidad": 14400.0,
      "choferAM": "",
      "choferPM": ""
    }
  ],
  "catalogos": {
    "productos": [
      "Crema 42% CCAA",
      "LEP NESTLÉ",
      "Leche estandarizada - Lácteos Nebe",
      "P. Entero ST 48%",
      "P. Semidescremado ST 45% CCAA",
      "Rwk NESTLÉ"
    ],
    "mandantes": [
      "Nestlé",
      "Colun",
      "CCAA",
      "Surlat",
      "Lácteos Nebe"
    ],
    "lineas": [
      "E1",
      "E2"
    ],
    "destinos": [
      "Los Angeles",
      "Stock",
      "Nestlé",
      "Surlat",
      "Colun",
      "Macul",
      "Chilolac"
    ],
    "silos": [
      "SILO 1",
      "SILO 2",
      "SILO 3",
      "SILO 4",
      "SILO 5",
      "SILO 6",
      "SILO 7",
      "SILO 8",
      "TK LD 1",
      "TK LD 2",
      "TK LD 3",
      "TK LD 4",
      "TK LD 5",
      "TK LD 6",
      "TK CREMA 1",
      "TK CREMA 2",
      "TK CREMA 3",
      "TK CREMA 4",
      "TK CREMA 5"
    ],
    "procedencias": [
      "Nestlé",
      "P Unión"
    ],
    "operadores": [
      "Cristian Navarro",
      "Francisco Ruiz",
      "John Aguilar",
      "Nelson Werner",
      "Simon Navarro",
      "Araceli Catalan",
      "Daniel Rivera",
      "Fredy Salamanca",
      "Gabriela Huenchur",
      "Jorge Veliz",
      "José Almonacid",
      "Jose Andrade",
      "Luis Almonacid",
      "Luis Vargas",
      "Magdiel Ojeda",
      "Norberto Werner",
      "Pedro Hernández",
      "Sebastian Farias"
    ],
    "turnos": [
      "A",
      "B",
      "C"
    ],
    "especificaciones": {
      "P. Entero ST 48%": {
        "humedad": [
          0,
          4.0
        ],
        "mg": [
          26,
          30
        ],
        "st": [
          47,
          49
        ],
        "acidez": [
          13,
          16
        ],
        "ph": [
          6.5,
          6.9
        ]
      },
      "P. Semidescremado ST 45%": {
        "humedad": [
          0,
          4.0
        ],
        "mg": [
          10,
          16
        ],
        "st": [
          44,
          46
        ],
        "acidez": [
          13,
          16
        ],
        "ph": [
          6.5,
          6.9
        ]
      },
      "Crema 42% NESTLÉ": {
        "humedad": [
          0,
          60
        ],
        "mg": [
          40,
          44
        ],
        "acidez": [
          9,
          14
        ],
        "ph": [
          6.4,
          6.9
        ],
        "temperatura": [
          0,
          8
        ]
      },
      "Crema 42% CCAA": {
        "humedad": [
          0,
          60
        ],
        "mg": [
          40,
          44
        ],
        "acidez": [
          9,
          14
        ],
        "ph": [
          6.4,
          6.9
        ],
        "temperatura": [
          0,
          8
        ]
      }
    },
    "documentosLiberacion": [
      "CCAA.REC.FORM.002.01 Planilla de Instructivo",
      "Formularios de control de proceso (PCC)",
      "Checklist de cuerpos extraños evaporadores",
      "Hoja de pulverización E1 y E2",
      "Disco de uperización",
      "Inspección preoperativa E1 y E2",
      "Conexión de tierra E1 - E2",
      "Formulario fisicoquímicos E1 y E2",
      "Formulario de filtros de limpieza",
      "Monitoreo de PPRO E1 y E2",
      "Monitoreo de PPRO Rovemas 3 y 4",
      "Checklist cuerpos extraños Rovema 3 y 4",
      "Seguimiento FEFO",
      "Monitoreo PPRO Detector de metales",
      "Control de consumo de materiales",
      "Control de hermeticidad y peso neto",
      "Registro de evaluación sensorial",
      "Informe de laboratorio externo",
      "CCAA.Calidad.FORM.016.02 Certificado de Análisis"
    ]
  }
};

let DB = null;
function clonar(o){ return JSON.parse(JSON.stringify(o)); }
const COLECCIONES = ["produccion","recepcion","liberaciones","maestros"];

function cargarDatos(){
  try{
    const g = localStorage.getItem(CLAVE_ALMACEN);
    if(g){
      DB = JSON.parse(g);
      for(const k of COLECCIONES) if(!Array.isArray(DB[k])) DB[k]=clonar(DATOS_SEMILLA[k]);
      if(!DB.catalogos) DB.catalogos = clonar(DATOS_SEMILLA.catalogos);
      return DB;
    }
  }catch(e){ console.warn("Sin almacenamiento local, uso semilla.", e); }
  DB = clonar(DATOS_SEMILLA);
  return DB;
}
function obtenerDatos(){ if(!DB) cargarDatos(); return DB; }
function guardarDatos(){
  try{ localStorage.setItem(CLAVE_ALMACEN, JSON.stringify(DB)); return true; }
  catch(e){ console.warn("No se pudo guardar.", e); return false; }
}
function restablecerDatos(){ DB = clonar(DATOS_SEMILLA); guardarDatos(); return DB; }

function exportarJSON(nombre){
  const blob = new Blob([JSON.stringify(DB,null,2)], {type:"application/json"});
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href=url; a.download=nombre||"gestion-productiva-ccaa.json";
  document.body.appendChild(a); a.click(); document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
function importarJSON(archivo){
  return new Promise((res,rej)=>{
    const fr=new FileReader();
    fr.onload=()=>{
      try{
        const d=JSON.parse(fr.result); let ch=[];
        for(const k of COLECCIONES) if(Array.isArray(d[k])){ DB[k]=d[k]; ch.push(k); }
        if(d.catalogos) DB.catalogos=d.catalogos;
        if(!ch.length){ rej(new Error("El archivo no contiene colecciones reconocidas.")); return; }
        guardarDatos(); res({colecciones:ch});
      }catch(e){ rej(new Error("JSON inválido: "+e.message)); }
    };
    fr.onerror=()=>rej(new Error("No se pudo leer el archivo."));
    fr.readAsText(archivo);
  });
}
