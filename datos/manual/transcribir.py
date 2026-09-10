# -*- coding: utf-8 -*-
"""Transcripcion de los informes TBM que llegaron sin capa de texto.

Febrero 2026 y Junio 2026 vinieron con el texto convertido a curvas, asi que
pdfplumber no puede leerlos. Los numeros de abajo se transcribieron leyendo el
PDF renderizado a 300 dpi, y se validan solos: 'comprobar()' exige que en cada
categoria y en el AOR la Industria sea igual a la suma de las filas, y que el
Market Share coincida con dealer/industria. Si alguna cifra estuviera mal
tipeada, casi con seguridad rompe alguna de las dos condiciones.

Genera datos/manual/<clave>.json, que procesar_tbm.py levanta como un mes mas.

    python datos/manual/transcribir.py
"""

import json
import os

BASE = os.path.dirname(os.path.abspath(__file__))

COL_T = ["<50", "50-70", "70-80", "80-90", "90-100", "100-110", "110-120",
         "120-130", "130-140", "140-160", "160-180", "180-200", "200-220",
         "220+", "AOR", "TERRITORIO", "PAIS"]
ET_T = ["<50", "50 <70", "70 <80", "80 <90", "90 <100", "100 <110", "110 <120",
        "120 <130", "130 <140", "140 <160", "160 <180", "180 <200", "200 <220",
        "220 & Over", "AOR", "TERRITORY", "COUNTRY"]
COL_C = ["Pg0-5", "Pg6", "Pg7", "Pg8+", "AOR", "TERRITORIO", "PAIS"]
ET_C = ["Pg0-5 0 < 231", "Pg6 231 < 272", "Pg7 272<320", "Pg8+ 320 & Over",
        "AOR", "TERRITORY", "COUNTRY"]

DEALER = "Cetomaq24 Sa"

# --------------------------------------------------------------- transcripcion
# Cada tabla: filas en el mismo orden que el PDF.
MESES = {
    "2026-02": {
        "mes_num": 2, "anio": 2026, "mes_es": "Febrero 2026", "mes_cor": "Feb 26",
        "fy": "FY26",
        "archivo": "Argentina TBM Dealer Analysis - Febrero 2026.pdf",
        "tractores": {
            "FYTD": [
                ("dealer", [0.0, 0.0, 0.0, 0.0, 2.0, 0.0, 1.0, 0.0, 1.0, 1.0, 2.0, 2.0, 0.0, 3.0, 12.0, 12.0, 12.0]),
                ("marca", [0.7, 1.0, 2.1, 2.5, 1.0, 1.1, 0.4, 0.4, 0.4, 0.3, 0.1, 0.3, 0.2, 0.7, 11.0, 80.1, 240.0]),
                ("competidores", [0.0, 0.0, 0.4, 2.1, 1.4, 0.8, 1.4, 0.8, 2.2, 2.1, 2.0, 3.0, 2.2, 5.3, 23.7, 216.3, 633.0]),
                ("industria", [0.7, 1.0, 2.5, 4.5, 4.4, 1.9, 2.8, 1.1, 3.6, 3.4, 4.1, 5.3, 2.4, 9.0, 46.7, 441.4, 1309.0]),
                ("share", [0.0, 0.0, 0.0, 0.0, 45.4, 0.0, 35.4, 0.0, 28.0, 29.3, 49.4, 37.9, 0.0, 33.3, 25.7, 2.7, 0.9]),
            ],
            "LFYTD": [
                ("dealer", [4.0, 1.0, 0.0, 0.0, 2.0, 3.0, 0.0, 1.0, 1.0, 3.0, 1.0, 1.0, 4.0, 3.0, 24.0, 24.0, 24.0]),
                ("marca", [1.0, 1.1, 2.5, 3.4, 1.6, 1.5, 0.8, 0.5, 0.6, 0.5, 0.1, 0.5, 0.3, 1.1, 15.5, 156.0, 530.0]),
                ("competidores", [0.1, 1.0, 1.0, 2.9, 1.7, 1.6, 0.5, 0.9, 3.5, 1.4, 1.0, 3.8, 1.6, 4.8, 25.9, 266.9, 781.0]),
                ("industria", [5.2, 3.2, 3.6, 6.3, 5.3, 6.1, 1.3, 2.4, 5.1, 4.9, 2.2, 5.3, 5.8, 8.9, 65.3, 613.9, 1970.0]),
                ("share", [77.5, 31.7, 0.0, 0.0, 38.0, 49.6, 0.0, 41.9, 19.6, 60.8, 46.2, 18.8, 68.8, 33.8, 36.7, 3.9, 1.2]),
            ],
        },
        "cosechadoras": {
            "FYTD": [
                ("dealer", [0.0, 0.0, 1.0, 1.0, 2.0, 2.0, 2.0]),
                ("competidores", [1.2, 0.5, 3.4, 2.0, 7.0, 51.1, 150.0]),
                ("industria", [1.2, 0.5, 4.4, 3.0, 9.0, 80.1, 245.0]),
                ("share", [0.0, 0.0, 22.8, 33.9, 22.2, 2.5, 0.8]),
            ],
            "LFYTD": [
                ("dealer", [0.0, 0.0, 4.0, 0.0, 4.0, 4.0, 4.0]),
                ("competidores", [1.0, 1.0, 2.1, 0.5, 4.7, 42.7, 129.0]),
                ("industria", [1.0, 1.0, 6.1, 0.5, 8.7, 67.7, 212.0]),
                ("share", [0.0, 0.0, 65.8, 0.0, 46.1, 5.9, 1.9]),
            ],
        },
    },
    "2026-06": {
        "mes_num": 6, "anio": 2026, "mes_es": "Junio 2026", "mes_cor": "Jun 26",
        "fy": "FY26",
        "archivo": "Argentina TBM Dealer Analysis - Cetomaq Junio 2026.pdf",
        "tractores": {
            "FYTD": [
                ("dealer", [1.0, 0.0, 3.0, 0.0, 7.0, 0.0, 2.0, 1.0, 2.0, 5.0, 3.0, 4.0, 6.0, 15.0, 49.0, 49.0, 49.0]),
                ("marca", [1.0, 1.3, 2.9, 3.4, 1.4, 1.6, 0.6, 0.5, 0.5, 0.5, 0.2, 0.4, 0.2, 1.0, 15.5, 106.4, 335.0]),
                ("competidores", [1.3, 0.3, 2.5, 2.9, 3.0, 2.3, 3.9, 1.3, 6.1, 5.3, 4.3, 8.8, 4.9, 18.7, 65.7, 512.6, 1632.0]),
                ("industria", [3.3, 1.6, 8.4, 6.2, 11.3, 3.9, 6.5, 2.8, 8.6, 10.8, 7.5, 13.3, 11.2, 34.7, 130.1, 981.0, 3222.0]),
                ("share", [30.1, 0.0, 35.7, 0.0, 61.7, 0.0, 30.9, 35.2, 23.2, 46.2, 40.3, 30.2, 53.8, 43.2, 37.7, 5.0, 1.5]),
            ],
            "LFYTD": [
                ("dealer", [5.0, 2.0, 2.0, 0.0, 8.0, 6.0, 1.0, 2.0, 4.0, 5.0, 3.0, 1.0, 7.0, 13.0, 59.0, 59.0, 59.0]),
                ("marca", [2.1, 2.5, 5.5, 7.5, 3.5, 2.9, 1.5, 1.0, 1.3, 1.2, 0.3, 1.3, 0.6, 2.6, 33.9, 280.0, 930.0]),
                ("competidores", [0.1, 2.2, 2.7, 5.6, 4.2, 4.6, 2.1, 2.6, 7.8, 3.0, 3.1, 9.0, 3.6, 12.4, 62.9, 589.0, 1859.0]),
                ("industria", [7.3, 6.7, 10.3, 13.1, 15.6, 13.4, 4.6, 5.6, 13.1, 9.2, 6.4, 11.3, 11.2, 27.9, 155.9, 1299.0, 4395.0]),
                ("share", [68.8, 29.7, 19.5, 0.0, 51.2, 44.6, 21.7, 35.5, 30.5, 54.5, 46.6, 8.9, 62.5, 46.5, 37.9, 4.5, 1.3]),
            ],
        },
        "cosechadoras": {
            "FYTD": [
                ("dealer", [1.0, 1.0, 4.0, 1.0, 7.0, 7.0, 7.0]),
                ("competidores", [2.2, 2.5, 7.3, 3.4, 15.3, 108.9, 326.0]),
                ("industria", [3.2, 3.5, 11.3, 4.4, 22.3, 172.9, 579.0]),
                ("share", [31.2, 28.8, 35.5, 22.8, 31.3, 4.0, 1.2]),
            ],
            "LFYTD": [
                ("dealer", [1.0, 2.0, 9.0, 2.0, 14.0, 14.0, 14.0]),
                ("competidores", [2.2, 2.3, 6.2, 1.6, 12.4, 99.2, 305.0]),
                ("industria", [3.2, 4.3, 15.2, 3.6, 26.4, 160.2, 543.0]),
                ("share", [31.2, 46.1, 59.1, 56.2, 53.1, 8.7, 2.6]),
            ],
        },
    },
}

NOMBRES = {"dealer": DEALER, "marca": "Pauny", "competidores": "Competitors",
           "industria": "Industry", "share": "Market Share"}


def texto(valor, tipo, columna):
    """Reproduce como imprime el numero el PDF: la columna COUNTRY va entera
    y con separador de miles; el resto con un decimal; el share con %."""
    if tipo == "share":
        return "%.1f%%" % valor
    if columna == "PAIS":
        return "{:,.0f}".format(valor)
    return "%.1f" % valor


def comprobar(clave, seg, periodo, cols, filas):
    """Industria = suma de filas, y share = dealer/industria."""
    d = {t: v for t, v in filas}
    ind = d["industria"]
    partes = [v for t, v in filas if t in ("dealer", "marca", "competidores")]
    errores = []
    for i, c in enumerate(cols):
        if c in ("TERRITORIO", "PAIS"):
            continue
        suma = sum(p[i] for p in partes)
        if abs(suma - ind[i]) > max(0.6, ind[i] * 0.02):
            errores.append("%s: suma %.1f != industria %.1f" % (c, suma, ind[i]))
        if ind[i]:
            esp = d["dealer"][i] / ind[i] * 100
            if abs(esp - d["share"][i]) > 1.5:
                errores.append("%s: share %.1f%% != dealer/ind %.1f%%"
                               % (c, d["share"][i], esp))
    for e in errores:
        print("  [!] %s %s/%s %s" % (clave, seg, periodo, e))
    return not errores


def main():
    ok = True
    for clave, m in sorted(MESES.items()):
        d = {
            "clave": clave, "mes_num": m["mes_num"], "anio": m["anio"],
            "mes_es": m["mes_es"], "mes_cor": m["mes_cor"], "fy": m["fy"],
            "dealer": DEALER, "archivo": m["archivo"],
            "fuente": "transcripcion manual (PDF sin capa de texto)",
            "procesado": "transcripcion manual",
            "segmentos": {},
        }
        for seg, cols, ets in (("tractores", COL_T, ET_T),
                               ("cosechadoras", COL_C, ET_C)):
            d["segmentos"][seg] = {}
            for periodo, filas in m[seg].items():
                if not comprobar(clave, seg, periodo, cols, filas):
                    ok = False
                d["segmentos"][seg][periodo] = {
                    "columnas": cols, "etiquetas": ets,
                    "filas": [{"nombre": NOMBRES[t], "tipo": t, "valores": v,
                               "textos": [texto(x, t, c) for x, c in zip(v, cols)]}
                              for t, v in filas],
                }
        ruta = os.path.join(BASE, clave + ".json")
        with open(ruta, "w", encoding="utf-8") as fh:
            json.dump(d, fh, ensure_ascii=False, indent=1)
        print("escrito %s" % ruta)
    print("verificacion: " + ("OK" if ok else "CON ERRORES"))


if __name__ == "__main__":
    main()
