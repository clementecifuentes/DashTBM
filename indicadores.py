# -*- coding: utf-8 -*-
"""Baja indicadores publicos y los deja mensualizados en datos/indicadores.json.

Fuente de tasas y credito: API publica del BCRA (Estadisticas Monetarias v4.0),
https://api.bcra.gob.ar/estadisticas/v4.0/monetarias  -- sin clave ni registro.

Uso:
    python indicadores.py            # baja todo y reescribe datos/indicadores.json

Los derechos de exportacion NO salen de una API: estan curados a mano en
datos/eventos.json, con decreto y fuente para cada cambio.
"""

import json
import os
import ssl
import urllib.request
from collections import defaultdict
from datetime import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
SALIDA = os.path.join(BASE, "datos", "indicadores.json")
API = "https://api.bcra.gob.ar/estadisticas/v4.0/monetarias/%d?desde=%s&hasta=%s&limit=3000"

DESDE = "2024-10-01"   # un mes antes del primer informe TBM
HASTA = datetime.now().strftime("%Y-%m-%d")

# id BCRA -> (clave, etiqueta, unidad, como agregar el mes)
SERIES = {
    7:   ("badlar",     "BADLAR bancos privados",             "% TNA",  "promedio"),
    44:  ("tamar",      "TAMAR bancos privados",              "% TNA",  "promedio"),
    13:  ("adelantos",  "Adelantos en cuenta corriente",      "% TNA",  "promedio"),
    113: ("prendarios", "Préstamos prendarios al sector privado", "M$", "cierre"),
    111: ("documentos", "Préstamos por documentos al sector privado", "M$", "cierre"),
    5:   ("tc",         "Tipo de cambio mayorista",           "$/US$",  "promedio"),
}

# El BCRA usa un certificado que a veces no valida en Windows; la respuesta es
# publica y no lleva credenciales, asi que se acepta sin verificar la cadena.
CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE


def bajar(id_var):
    req = urllib.request.Request(API % (id_var, DESDE, HASTA),
                                 headers={"User-Agent": "DashTBM/1.0"})
    with urllib.request.urlopen(req, context=CTX, timeout=40) as r:
        d = json.load(r)
    det = d["results"][0]["detalle"]
    return [(x["fecha"], float(x["valor"])) for x in det]


def mensualizar(datos, modo):
    por_mes = defaultdict(list)
    for fecha, valor in datos:
        por_mes[fecha[:7]].append((fecha, valor))
    out = {}
    for mes, vs in por_mes.items():
        vs.sort()
        out[mes] = (sum(v for _, v in vs) / len(vs) if modo == "promedio"
                    else vs[-1][1])
    return out


def main():
    series, meta = {}, {}
    for id_var, (clave, etiqueta, unidad, modo) in SERIES.items():
        try:
            crudo = bajar(id_var)
        except Exception as e:
            print("  [!] %s (id %d): %s" % (clave, id_var, e))
            continue
        series[clave] = mensualizar(crudo, modo)
        meta[clave] = {"etiqueta": etiqueta, "unidad": unidad,
                       "id_bcra": id_var, "modo": modo}
        ms = sorted(series[clave])
        print("  OK %-11s %s .. %s  (%d meses, %d datos diarios)"
              % (clave, ms[0], ms[-1], len(ms), len(crudo)))

    # Stock de credito pasado a dolares: en pesos nominales, 21 meses de
    # inflacion hacen que la serie no se pueda comparar consigo misma.
    if "tc" in series:
        for orig, nueva in (("prendarios", "prendarios_usd"),
                            ("documentos", "documentos_usd")):
            if orig not in series:
                continue
            series[nueva] = {m: round(v / series["tc"][m], 1)
                             for m, v in series[orig].items() if m in series["tc"]}
            meta[nueva] = {"etiqueta": meta[orig]["etiqueta"] + " (en dólares)",
                           "unidad": "MUS$", "id_bcra": meta[orig]["id_bcra"],
                           "modo": meta[orig]["modo"]}
            print("  OK %-11s derivado de %s / tc" % (nueva, orig))

    for clave in series:
        series[clave] = {m: round(v, 2) for m, v in sorted(series[clave].items())}

    eventos = []
    ruta_ev = os.path.join(BASE, "datos", "eventos.json")
    if os.path.exists(ruta_ev):
        with open(ruta_ev, encoding="utf-8") as fh:
            eventos = json.load(fh)
        print("  OK %-11s %d eventos curados" % ("eventos", len(eventos)))

    with open(SALIDA, "w", encoding="utf-8") as fh:
        json.dump({"series": series, "meta": meta, "eventos": eventos,
                   "fuente": "BCRA, Estadísticas Monetarias v4.0 (API pública)",
                   "bajado": datetime.now().strftime("%Y-%m-%d %H:%M")},
                  fh, ensure_ascii=False, indent=1)
    print("\n-> %s" % SALIDA)
    print("Ahora corré: python procesar_tbm.py   (para regenerar index.html)")


if __name__ == "__main__":
    main()
