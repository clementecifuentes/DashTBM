# -*- coding: utf-8 -*-
"""
Procesa los PDF "Argentina TBM Dealer Analysis" (John Deere) y genera un
dashboard HTML autocontenido listo para publicar en GitHub Pages.

Uso:
    python procesar_tbm.py                 # procesa todos los PDF de ./datos
    python procesar_tbm.py archivo.pdf     # procesa solo ese PDF

Flujo mensual:
    1) copiar el PDF nuevo a ./datos/
    2) python procesar_tbm.py
    3) git add -A && git commit -m "TBM <mes>" && git push
"""

import json
import os
import re
import sys
import unicodedata
from datetime import datetime

import pdfplumber

BASE = os.path.dirname(os.path.abspath(__file__))
DIR_DATOS = os.path.join(BASE, "datos")
HISTORICO = os.path.join(DIR_DATOS, "historico.json")
PLANTILLA = os.path.join(BASE, "plantilla.html")
SALIDA = os.path.join(BASE, "index.html")

MESES = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11,
    "december": 12,
}
MESES_ES = ["", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio",
            "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]

# Categorias esperadas en el reporte estandar TBM.
CAT_TRACTORES = ["<50", "50-70", "70-80", "80-90", "90-100", "100-110",
                 "110-120", "120-130", "130-140", "140-160", "160-180",
                 "180-200", "200-220", "220+"]
CAT_COSECHADORAS = ["Pg 0-5 (<231)", "Pg 6 (231-272)", "Pg 7 (272-320)",
                    "Pg 8+ (320+)"]
TOTALES = ["AOR", "TERRITORIO", "PAIS"]

RE_TITULO = re.compile(r"^(Tractor|Combine)\s+Dealer\s+Analysis\s+([A-Z0-9]+)\s*$", re.I)
RE_NUM = re.compile(r"^\(?-?[\d,]+(?:\.\d+)?\)?%?$")

AVISOS = []


def avisar(msg):
    AVISOS.append(msg)
    print("  [!] " + msg)


def a_numero(txt):
    """'1,765' -> 1765.0 ; '30.8%' -> 30.8 ; '(12)' -> -12.0"""
    t = txt.strip().replace(",", "").replace("%", "")
    neg = t.startswith("(") and t.endswith(")")
    t = t.strip("()")
    try:
        v = float(t)
    except ValueError:
        return None
    return -v if neg else v


def es_numero(txt):
    return bool(RE_NUM.match(txt.strip())) and a_numero(txt) is not None


def agrupar_filas(palabras, tol=2.5):
    """Agrupa palabras por coordenada vertical. Devuelve [(top, [palabras])]."""
    filas = []
    for w in sorted(palabras, key=lambda w: (w["top"], w["x0"])):
        for f in filas:
            if abs(f[0] - w["top"]) <= tol:
                f[1].append(w)
                break
        else:
            filas.append((w["top"], [w]))
    return [(t, sorted(ws, key=lambda w: w["x0"])) for t, ws in
            sorted(filas, key=lambda f: f[0])]


def texto_fila(ws):
    return " ".join(w["text"] for w in ws)


def normalizar(txt):
    txt = unicodedata.normalize("NFKD", txt).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", txt.lower())


def tipo_de_fila(nombre, indice, total):
    n = normalizar(nombre)
    if "marketshare" in n:
        return "share"
    if "industry" in n or "industria" in n:
        return "industria"
    if "competitor" in n:
        return "competidores"
    if indice == 0:
        return "dealer"
    return "marca"


def nombre_es(nombre, tipo, dealer):
    return {
        "dealer": dealer,
        "competidores": "Competidores",
        "industria": "Industria",
        "share": "Market Share",
    }.get(tipo, nombre.strip())


def parsear_bloque(filas, i_titulo, i_fin, dealer):
    """Extrae las filas de datos de un bloque (una tabla del PDF)."""
    bloque = filas[i_titulo + 1:i_fin]

    # 1) Encabezado: la fila que contiene COUNTRY delimita el fin del header.
    top_header = None
    for top, ws in bloque:
        if any(w["text"].upper() == "COUNTRY" for w in ws):
            top_header = top
            break
    if top_header is None:
        return None

    cuerpo = [(t, ws) for t, ws in bloque if t > top_header + 3]
    if not cuerpo:
        return None

    # 2) La fila "Industry" define los centros de columna (siempre completa).
    centros = None
    for top, ws in cuerpo:
        if any(normalizar(w["text"]) == "industry" for w in ws):
            nums = [w for w in ws if es_numero(w["text"])]
            centros = [(w["x0"] + w["x1"]) / 2 for w in nums]
            break
    if not centros:
        return None
    n_col = len(centros)
    x_min = min(centros) - 25

    # 3) Anclas de fila: etiquetas de texto a la izquierda de la primer columna.
    anclas = []  # [top, nombre, {col: valor}]
    for top, ws in cuerpo:
        etiquetas = [w["text"] for w in ws
                     if w["x0"] < x_min and not es_numero(w["text"])]
        if etiquetas:
            anclas.append([top, " ".join(etiquetas), {}])
    if not anclas:
        return None

    # 4) Cada numero se asigna al ancla mas cercana verticalmente y a la
    #    columna mas cercana horizontalmente (tolera filas partidas en dos).
    for top, ws in cuerpo:
        for w in ws:
            if w["x0"] < x_min or not es_numero(w["text"]):
                continue
            ancla = min(anclas, key=lambda a: abs(a[0] - top))
            if abs(ancla[0] - top) > 6:
                continue
            cx = (w["x0"] + w["x1"]) / 2
            col = min(range(n_col), key=lambda c: abs(centros[c] - cx))
            ancla[2][col] = a_numero(w["text"])

    filas_datos = []
    for a in anclas:
        if not a[2]:
            continue  # etiqueta partida (ej. "Sa" en otra linea), se descarta
        vals = [a[2].get(c) for c in range(n_col)]
        filas_datos.append({"nombre_raw": a[1], "valores": vals})

    if not filas_datos:
        return None

    total = len(filas_datos)
    out = []
    for i, f in enumerate(filas_datos):
        tipo = tipo_de_fila(f["nombre_raw"], i, total)
        out.append({
            "nombre": nombre_es(f["nombre_raw"], tipo, dealer),
            "tipo": tipo,
            "valores": f["valores"],
        })
    return {"n_col": n_col, "filas": out}


def columnas_para(segmento, n_col):
    cats = CAT_TRACTORES if segmento == "tractores" else CAT_COSECHADORAS
    n_cat = n_col - len(TOTALES)
    if n_cat != len(cats):
        avisar(f"{segmento}: se esperaban {len(cats)} categorias y el PDF trae "
               f"{n_cat}. Se usan nombres genericos; revisar procesar_tbm.py.")
        cats = [f"Cat {i + 1}" for i in range(n_cat)]
    return cats + TOTALES


def parsear_pdf(ruta):
    print(f"Procesando: {os.path.basename(ruta)}")
    datos = {"segmentos": {}}
    with pdfplumber.open(ruta) as pdf:
        for pagina in pdf.pages:
            palabras = pagina.extract_words()
            filas = agrupar_filas(palabras)
            textos = [texto_fila(ws) for _, ws in filas]

            # Dealer y mes (aparecen en el encabezado de cada pagina)
            for i, t in enumerate(textos):
                if t.startswith("Select a Dealer") and i + 1 < len(textos):
                    cand = textos[i + 1].split("  ")[0]
                    cand = re.sub(r"\s+\d+$", "", cand).strip()
                    if cand:
                        datos.setdefault("dealer", cand)
                m = re.match(r"^([A-Za-z]+)\s+(\d{4})$", t.strip())
                if m and m.group(1).lower() in MESES:
                    datos.setdefault("mes_txt", t.strip())
                    datos.setdefault("mes_num", MESES[m.group(1).lower()])
                    datos.setdefault("anio", int(m.group(2)))

            titulos = [(i, RE_TITULO.match(t)) for i, t in enumerate(textos)]
            titulos = [(i, m) for i, m in titulos if m]
            for k, (i, m) in enumerate(titulos):
                segmento = "tractores" if m.group(1).lower() == "tractor" else "cosechadoras"
                periodo = m.group(2).upper()
                fin = titulos[k + 1][0] if k + 1 < len(titulos) else len(filas)
                b = parsear_bloque(filas, i, fin, datos.get("dealer", "Dealer"))
                if not b:
                    avisar(f"no se pudo leer el bloque {segmento} {periodo}")
                    continue
                seg = datos["segmentos"].setdefault(
                    segmento, {"columnas": columnas_para(segmento, b["n_col"]),
                               "periodos": {}})
                seg["periodos"][periodo] = b["filas"]

    if "mes_num" not in datos:
        raise SystemExit(f"No se encontro el mes en {ruta}")

    datos["clave"] = f"{datos['anio']}-{datos['mes_num']:02d}"
    datos["mes_es"] = f"{MESES_ES[datos['mes_num']]} {datos['anio']}"
    datos["archivo"] = os.path.basename(ruta)
    datos["procesado"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    return datos


def verificar(datos):
    """Industria debe ser la suma de las demas filas en las categorias y el AOR.
    (No aplica a TERRITORIO/PAIS: ahi el reporte no desagrega igual.)"""
    for nombre_seg, seg in datos["segmentos"].items():
        n_chequear = len(seg["columnas"]) - 2  # hasta AOR inclusive
        for periodo, filas in seg["periodos"].items():
            ind = next((f for f in filas if f["tipo"] == "industria"), None)
            partes = [f for f in filas if f["tipo"] in ("dealer", "competidores", "marca")]
            if not ind or len(partes) < 2:
                continue
            for c in range(n_chequear):
                real = ind["valores"][c]
                if real is None:
                    continue
                suma = sum((f["valores"][c] or 0) for f in partes)
                if abs(suma - real) > max(0.6, real * 0.02):
                    avisar(f"{nombre_seg}/{periodo} col {seg['columnas'][c]}: "
                           f"suma de filas={suma:.1f} vs industria={real:.1f}")


def main():
    if not os.path.isdir(DIR_DATOS):
        os.makedirs(DIR_DATOS)

    if len(sys.argv) > 1:
        pdfs = [os.path.abspath(a) for a in sys.argv[1:]]
    else:
        pdfs = sorted(os.path.join(DIR_DATOS, f) for f in os.listdir(DIR_DATOS)
                      if f.lower().endswith(".pdf"))
    if not pdfs:
        raise SystemExit(f"No hay PDF en {DIR_DATOS}")

    historico = {}
    if os.path.exists(HISTORICO):
        with open(HISTORICO, encoding="utf-8") as fh:
            historico = json.load(fh)

    for ruta in pdfs:
        d = parsear_pdf(ruta)
        verificar(d)
        historico[d["clave"]] = d
        print(f"  OK -> {d['mes_es']} | {d['dealer']} | "
              f"segmentos: {', '.join(sorted(d['segmentos']))}")

    historico = dict(sorted(historico.items()))
    with open(HISTORICO, "w", encoding="utf-8") as fh:
        json.dump(historico, fh, ensure_ascii=False, indent=1)

    with open(PLANTILLA, encoding="utf-8") as fh:
        html = fh.read()
    payload = json.dumps({
        "meses": historico,
        "generado": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "avisos": AVISOS,
    }, ensure_ascii=False)
    html = html.replace("/*__DATOS__*/null/*__FIN__*/", payload)
    with open(SALIDA, "w", encoding="utf-8") as fh:
        fh.write(html)

    print(f"\nHistorico: {len(historico)} mes(es) -> {HISTORICO}")
    print(f"Dashboard -> {SALIDA}")
    if AVISOS:
        print(f"\n{len(AVISOS)} aviso(s) durante el procesamiento (ver arriba).")


if __name__ == "__main__":
    main()
