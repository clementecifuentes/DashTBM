# -*- coding: utf-8 -*-
"""Baja indicadores publicos y los deja mensualizados en datos/indicadores.json.

Fuentes, todas publicas y sin clave:
  * Tasas y credito: API del BCRA (Estadisticas Monetarias v4.0),
    https://api.bcra.gob.ar/estadisticas/v4.0/monetarias
  * Dolar oficial (Banco Nacion): https://api.argentinadatos.com, historia
    diaria desde 2011, sin clave. El BCRA no publica una serie propia de BNA:
    su minorista (id 4) es un promedio de bancos, no el mostrador del Nacion.
  * Precios de granos: series mensuales del FMI publicadas por la Reserva
    Federal de St. Louis, https://fred.stlouisfed.org (endpoint CSV abierto).
    OJO: son precios internacionales (golfo de EEUU), NO la pizarra de Rosario.
    La pizarra no esta publicada en ninguna API: vive en planillas de MAGyP.

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
FRED = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=%s"
DOLAR = "https://api.argentinadatos.com/v1/cotizaciones/dolares/oficial"

# id FRED -> (clave, etiqueta, unidad)
GRANOS = {
    "PSOYBUSDM":   ("soja",  "Soja, precio internacional",  "US$/t"),
    "PMAIZMTUSDM": ("maiz",  "Maíz, precio internacional",  "US$/t"),
}

# Que se muestra en la pagina. El resto igual se baja y queda en el JSON, asi
# volver a mostrar una serie es agregar su clave a esta lista y nada mas.
MOSTRAR = ["retenciones", "oficial"]

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


def bajar_fred(id_serie):
    # FRED corta la conexion con una UA propia; con UA de navegador responde
    # en menos de un segundo.
    req = urllib.request.Request(FRED % id_serie, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Accept": "text/csv,*/*"})
    with urllib.request.urlopen(req, context=CTX, timeout=40) as r:
        crudo = r.read().decode("utf-8", "replace")
    out = {}
    for linea in crudo.splitlines()[1:]:
        partes = linea.split(",")
        if len(partes) < 2:
            continue
        fecha, valor = partes[0].strip(), partes[1].strip()
        if valor in ("", "."):
            continue
        try:
            out[fecha[:7]] = float(valor)
        except ValueError:
            pass
    return out


def bajar_dolar_oficial():
    """Cotizacion del Banco Nacion, promedio mensual del tipo vendedor."""
    req = urllib.request.Request(DOLAR, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Accept": "application/json"})
    with urllib.request.urlopen(req, context=CTX, timeout=40) as r:
        datos = json.load(r)
    return [(d["fecha"], float(d["venta"])) for d in datos
            if d.get("fecha") and d.get("venta") is not None
            and d["fecha"] >= DESDE]


def alicuotas_por_mes(eventos, meses):
    """Alicuota de cada grano vigente al cierre de cada mes, segun los decretos."""
    cambios = sorted((e for e in eventos
                      if not e.get("solo_evento") and e.get("alicuotas")),
                     key=lambda e: e.get("mes") or e["fecha"][:7])
    out = {}
    for m in meses:
        actual = {"soja": 33.0, "maiz": 12.0, "trigo": 12.0}   # vigentes antes del periodo
        for e in cambios:
            if (e.get("mes") or e["fecha"][:7]) <= m:
                actual.update(e["alicuotas"])
        out[m] = actual
    return out


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


def eventos_cargados(base):
    return os.path.exists(os.path.join(base, "datos", "eventos.json"))


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

    try:
        series["oficial"] = mensualizar(bajar_dolar_oficial(), "promedio")
        meta["oficial"] = {"etiqueta": "Dólar oficial Banco Nación (venta)",
                           "unidad": "$/US$", "fuente": "api.argentinadatos.com",
                           "modo": "promedio"}
        ms = sorted(series["oficial"])
        print("  OK %-11s %s .. %s  (%d meses, Banco Nación)"
              % ("oficial", ms[0], ms[-1], len(ms)))
    except Exception as e:
        print("  [!] oficial: %s" % e)

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

    for id_serie, (clave, etiqueta, unidad) in GRANOS.items():
        try:
            series[clave] = {m: v for m, v in bajar_fred(id_serie).items()
                             if m >= DESDE[:7]}
        except Exception as e:
            print("  [!] %s (%s): %s" % (clave, id_serie, e))
            continue
        meta[clave] = {"etiqueta": etiqueta, "unidad": unidad,
                       "id_fred": id_serie, "modo": "mensual"}
        ms = sorted(series[clave])
        print("  OK %-11s %s .. %s  (%d meses, FRED/FMI)" % (clave, ms[0], ms[-1], len(ms)))

    # Precio que le queda al productor: internacional menos el derecho de
    # exportacion vigente. Es una aproximacion: ignora fletes y gastos
    # comerciales, pero aisla el efecto de los decretos.
    if eventos_cargados(BASE):
        eventos_tmp = json.load(open(os.path.join(BASE, "datos", "eventos.json"),
                                     encoding="utf-8"))
        for grano in ("soja", "maiz"):
            if grano not in series:
                continue
            alic = alicuotas_por_mes(eventos_tmp, sorted(series[grano]))
            nueva = grano + "_neto"
            series[nueva] = {m: v * (1 - alic[m][grano] / 100.0)
                             for m, v in series[grano].items()}
            meta[nueva] = {"etiqueta": meta[grano]["etiqueta"].split(",")[0]
                           + " neto de retenciones (aprox.)",
                           "unidad": "US$/t", "modo": "derivado"}
            print("  OK %-11s derivado de %s y las alicuotas" % (nueva, grano))

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
                   "mostrar": MOSTRAR,
                   "fuente": "BCRA, Banco Nación (vía argentinadatos) y FMI vía FRED",
                   "bajado": datetime.now().strftime("%Y-%m-%d %H:%M")},
                  fh, ensure_ascii=False, indent=1)
    print("\n-> %s" % SALIDA)
    print("Ahora corré: python procesar_tbm.py   (para regenerar index.html)")


if __name__ == "__main__":
    main()
