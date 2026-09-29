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

Notas de formato (verificadas sobre 21 informes, nov-2024 a jul-2026):
  - El reporte OMITE las columnas de categorias que estan en cero, asi que la
    cantidad de columnas cambia de un informe a otro y hasta entre tablas del
    mismo informe. Por eso el encabezado se lee de verdad, no se asume.
  - Los limites de las clases se movieron con los anios (Pg7 "272 < 319" en
    2024 y "272<320" en 2026). Se normalizan a una clave canonica (Pg7) para
    que la serie mensual sea continua, pero se conserva el texto original
    del PDF para mostrar las tablas tal cual.
  - El anio fiscal arranca en NOVIEMBRE: el FYTD se resetea ahi.
  - Algunos PDF llegan con el texto convertido a curvas: cada letra es un
    dibujo y no queda nada que extraer. No son escaneos de papel, pesan unas
    siete veces mas que los normales. Esos se transcriben aparte, en
    datos/manual/<clave>.json, con el mismo formato que genera este script.
"""

import glob
import json
import os
import re
import sys
import unicodedata
from datetime import datetime

import pdfplumber

BASE = os.path.dirname(os.path.abspath(__file__))
DIR_DATOS = os.path.join(BASE, "datos")
DIR_MANUAL = os.path.join(DIR_DATOS, "manual")
HISTORICO = os.path.join(DIR_DATOS, "historico.json")
INDICADORES = os.path.join(DIR_DATOS, "indicadores.json")
PLANTILLA = os.path.join(BASE, "plantilla.html")
SALIDA = os.path.join(BASE, "index.html")

MES_INICIO_FY = 11  # el anio fiscal arranca en noviembre

MESES = {"january": 1, "february": 2, "march": 3, "april": 4, "may": 5,
         "june": 6, "july": 7, "august": 8, "september": 9, "october": 10,
         "november": 11, "december": 12}
MESES_ES = ["", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio",
            "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
MESES_COR = ["", "Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul",
             "Ago", "Sep", "Oct", "Nov", "Dic"]

TOTALES = ["AOR", "TERRITORIO", "PAIS"]
ET_TOTALES = {"AOR": "AOR", "TERRITORIO": "TERRITORY", "PAIS": "COUNTRY"}

RE_TITULO = re.compile(r"^(Tractor|Combine)\s+Dealer\s+Analysis\s+([A-Z0-9]+)\s*$", re.I)
RE_NUM = re.compile(r"^\(?-?[\d,]+(?:\.\d+)?\)?%?$")

AVISOS = []


def avisar(msg):
    if msg not in AVISOS:
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


def normalizar(txt):
    txt = unicodedata.normalize("NFKD", txt).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", txt.lower())


def agrupar_filas(palabras, tol=2.5):
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


# ---------------------------------------------------------------- encabezados

def canonizar(segmento, crudo, anterior):
    """Texto del encabezado -> (clave canonica, etiqueta a mostrar).

    `anterior` es la clave de la columna previa, necesaria para la ultima
    banda abierta ("220 & Over"), cuyo texto el PDF dibuja superpuesto y sale
    ilegible de la extraccion."""
    txt = crudo.strip()
    plano = normalizar(txt)

    for clave, et in ET_TOTALES.items():
        if normalizar(et) in plano:
            return clave, et

    if segmento == "cosechadoras":
        m = re.search(r"pg\s*(\d+(?:-\d+)?\s*\+?)", txt, re.I)
        if m:
            return "Pg" + re.sub(r"\s+", "", m.group(1)), txt
        return None, txt

    # Tractores: bandas de HP
    abierta = "over" in plano or "&" in txt
    nums = [int(n) for n in re.findall(r"\d+", txt)]
    if txt.startswith("<") and len(nums) == 1:
        return "<%d" % nums[0], "<%d" % nums[0]
    if abierta or not nums:
        # ultima banda: se deduce del limite superior de la columna anterior
        base = None
        if anterior and "-" in anterior:
            base = anterior.split("-")[1]
        if base:
            return base + "+", base + " & Over"
        return None, txt
    if len(nums) >= 2:
        a, b = nums[0], nums[1]
        if b > a:
            return "%d-%d" % (a, b), "%d <%d" % (a, b)
    return None, txt


def parsear_bloque(filas, i_titulo, i_fin, segmento, dealer):
    bloque = filas[i_titulo + 1:i_fin]

    top_header = None
    for top, ws in bloque:
        if any(w["text"].upper() == "COUNTRY" for w in ws):
            top_header = top
            break
    if top_header is None:
        return None

    cuerpo = [(t, ws) for t, ws in bloque if t > top_header + 3]
    cabeza = [(t, ws) for t, ws in bloque if t <= top_header + 3]
    if not cuerpo:
        return None

    # La fila Industria define los centros de columna (siempre viene completa).
    centros = None
    for top, ws in cuerpo:
        if any(normalizar(w["text"]) == "industry" for w in ws):
            nums = [w for w in ws if es_numero(w["text"])]
            centros = [(w["x0"] + w["x1"]) / 2 for w in nums]
            break
    if not centros:
        return None
    n_col = len(centros)
    # Frontera entre la columna de etiquetas y la primera de datos: media
    # separacion entre columnas. Se compara contra el CENTRO de la palabra,
    # no contra su borde, porque "MarketShare" y "30.8%" se solapan en x.
    paso = (centros[1] - centros[0]) if n_col > 1 else 60.0
    x_min = centros[0] - paso / 2

    def centro(w):
        return (w["x0"] + w["x1"]) / 2

    def es_dato(w):
        return centro(w) >= x_min

    def col_de(w):
        cx = centro(w)
        return min(range(n_col), key=lambda c: abs(centros[c] - cx))

    # --- Encabezado real de esta tabla -------------------------------------
    crudos = ["" for _ in range(n_col)]
    for top, ws in cabeza:
        for w in ws:
            if not es_dato(w):
                continue  # "Name", el nombre del dealer, etc.
            c = col_de(w)
            crudos[c] = (crudos[c] + " " + w["text"]).strip()

    columnas, etiquetas = [], []
    for i, crudo in enumerate(crudos):
        clave, et = canonizar(segmento, crudo, columnas[-1] if columnas else None)
        if clave is None:
            clave = "col%d" % (i + 1)
            avisar("%s: no pude interpretar el encabezado '%s' (columna %d)"
                   % (segmento, crudo[:30], i + 1))
        columnas.append(clave)
        etiquetas.append(et)

    # --- Filas de datos -----------------------------------------------------
    anclas = []
    for top, ws in cuerpo:
        etq = [w["text"] for w in ws
               if not es_dato(w) and not es_numero(w["text"])]
        if etq:
            anclas.append([top, " ".join(etq), {}, {}])
    if not anclas:
        return None

    for top, ws in cuerpo:
        for w in ws:
            if not es_dato(w) or not es_numero(w["text"]):
                continue
            ancla = min(anclas, key=lambda a: abs(a[0] - top))
            if abs(ancla[0] - top) > 6:
                continue
            c = col_de(w)
            ancla[2][c] = a_numero(w["text"])
            ancla[3][c] = w["text"]   # texto tal cual lo imprime el PDF

    datos = [a for a in anclas if a[2]]
    if not datos:
        return None

    # El nombre largo del dealer puede partirse en dos renglones y arrastrar
    # parte de sus numeros al segundo ("Rural Ceres Dealer 0.0 0.0 4.0 0.0" /
    # "S.A. 4.0 4.0 4"). Eso creaba una fila fantasma y dejaba al dealer sin
    # AOR, Territorio y Pais. Si dos filas seguidas llenan columnas que la otra
    # tiene vacias, son la misma fila partida: se unen.
    unidas = [datos[0]]
    for a in datos[1:]:
        prev = unidas[-1]
        comunes = set(prev[2]) & set(a[2])
        if not comunes and (len(prev[2]) + len(a[2])) <= n_col:
            prev[1] = (prev[1] + " " + a[1]).strip()
            prev[2].update(a[2])
            prev[3].update(a[3])
        else:
            unidas.append(a)
    datos = unidas

    out = []
    for i, a in enumerate(datos):
        n = normalizar(a[1])
        if "marketshare" in n:
            tipo, nombre = "share", "Market Share"
        elif "industry" in n:
            tipo, nombre = "industria", "Industry"
        elif "competitor" in n:
            tipo, nombre = "competidores", "Competitors"
        elif i == 0:
            tipo, nombre = "dealer", dealer
        else:
            tipo, nombre = "marca", a[1].strip()
        out.append({"nombre": nombre, "tipo": tipo,
                    "valores": [a[2].get(c) for c in range(n_col)],
                    "textos": [a[3].get(c, "") for c in range(n_col)]})
    return {"columnas": columnas, "etiquetas": etiquetas, "filas": out}


def parsear_pdf(ruta):
    print("Procesando: " + os.path.basename(ruta))
    datos = {"segmentos": {}}
    with pdfplumber.open(ruta) as pdf:
        for pagina in pdf.pages:
            filas = agrupar_filas(pagina.extract_words())
            textos = [" ".join(w["text"] for w in ws) for _, ws in filas]

            for i, t in enumerate(textos):
                m = re.search(r"\b([A-Za-z]+)\s+(\d{4})\b", t)
                if m and m.group(1).lower() in MESES and "mes_num" not in datos:
                    datos["mes_num"] = MESES[m.group(1).lower()]
                    datos["anio"] = int(m.group(2))
                if t.startswith("Select a Dealer") and i + 1 < len(textos):
                    cand = re.sub(r"\s*\d+\s*$", "", textos[i + 1])
                    cand = re.sub(r"\b[A-Za-z]+\s+\d{4}\b", "", cand).strip()
                    if cand and "dealer" not in datos:
                        datos["dealer"] = cand

            titulos = [(i, RE_TITULO.match(t)) for i, t in enumerate(textos)]
            titulos = [(i, m) for i, m in titulos if m]
            for k, (i, m) in enumerate(titulos):
                segmento = ("tractores" if m.group(1).lower() == "tractor"
                            else "cosechadoras")
                periodo = m.group(2).upper()
                if periodo not in ("FYTD", "LFYTD"):
                    continue  # solo interesan estas dos tablas
                fin = titulos[k + 1][0] if k + 1 < len(titulos) else len(filas)
                b = parsear_bloque(filas, i, fin, segmento,
                                   datos.get("dealer", "Dealer"))
                if not b:
                    avisar("no pude leer el bloque %s %s de %s"
                           % (segmento, periodo, os.path.basename(ruta)))
                    continue
                datos["segmentos"].setdefault(segmento, {})[periodo] = b

    if "mes_num" not in datos:
        raise SystemExit("No se encontro el mes en " + ruta)

    datos["clave"] = "%d-%02d" % (datos["anio"], datos["mes_num"])
    datos["mes_es"] = "%s %d" % (MESES_ES[datos["mes_num"]], datos["anio"])
    datos["mes_cor"] = "%s %s" % (MESES_COR[datos["mes_num"]],
                                  str(datos["anio"])[2:])
    datos["fy"] = "FY%s" % str(datos["anio"] + (1 if datos["mes_num"] >= MES_INICIO_FY else 0))[2:]
    datos["archivo"] = os.path.basename(ruta)
    datos["procesado"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    return datos


# ------------------------------------------------------------- verificaciones

def verificar(d):
    """Industria = suma de las demas filas, en cada categoria y en el AOR.
    (No aplica a TERRITORIO/PAIS: ahi el reporte no desagrega igual.)"""
    for nom_seg, seg in d["segmentos"].items():
        for periodo, tabla in seg.items():
            cols = tabla["columnas"]
            ind = next((f for f in tabla["filas"] if f["tipo"] == "industria"), None)
            partes = [f for f in tabla["filas"]
                      if f["tipo"] in ("dealer", "competidores", "marca")]
            if not ind or len(partes) < 2:
                continue
            for c, clave in enumerate(cols):
                if clave in ("TERRITORIO", "PAIS"):
                    continue
                real = ind["valores"][c]
                if real is None:
                    continue
                suma = sum((f["valores"][c] or 0) for f in partes)
                if abs(suma - real) > max(0.6, real * 0.02):
                    avisar("%s %s/%s col %s: suma=%.1f vs industria=%.1f"
                           % (d["clave"], nom_seg, periodo, clave, suma, real))


def verificar_cruzado(historico):
    """Controles que solo se pueden hacer con varios meses cargados.

    Son los dos que en la practica detectan errores de lectura, porque no
    dependen de que las cuentas cierren dentro de una misma tabla:

      1. El LFYTD de un mes tiene que coincidir con el FYTD del mismo mes del
         anio anterior, en las unidades propias del dealer. Esas no se
         recalculan nunca, asi que cualquier diferencia es un error de lectura.
         (La industria si se recalcula: ahi la diferencia es normal.)
      2. El FYTD del dealer es acumulado y no puede bajar dentro del mismo anio
         fiscal. Este control es solo para el dealer a proposito: la industria
         SI baja a veces, porque Deere reasigna unidades entre AOR de un informe
         al otro (por ejemplo cosechadoras AOR FY26: 22,3 en junio, 19,6 en
         julio y 21,3 en agosto). Eso es una correccion de Deere, no un error de
         lectura, y avisar por cada una taparia los avisos que si importan.
    """
    def tabla(cl, seg, per):
        return historico.get(cl, {}).get("segmentos", {}).get(seg, {}).get(per)

    def val(t, tipo, col):
        if not t or col not in t["columnas"]:
            return None
        f = next((f for f in t["filas"] if f["tipo"] == tipo), None)
        return f["valores"][t["columnas"].index(col)] if f else None

    def pares(ta, tb):
        """Columnas presentes en las dos tablas, para poder compararlas."""
        return [c for c in ta["columnas"] if c in tb["columnas"]] if ta and tb else []

    claves = sorted(historico)
    for cl in claves:
        antes = "%d-%s" % (int(cl[:4]) - 1, cl[5:])
        for seg in ("tractores", "cosechadoras"):
            ta, tb = tabla(cl, seg, "LFYTD"), tabla(antes, seg, "FYTD")
            for col in pares(ta, tb):
                a, b = val(ta, "dealer", col), val(tb, "dealer", col)
                if a is not None and b is not None and abs(a - b) > 0.05:
                    avisar("%s %s %s: el LFYTD del dealer da %.1f y el FYTD de "
                           "%s daba %.1f" % (cl, seg, col, a, antes, b))

    for i, cl in enumerate(claves[1:], 1):
        prev = claves[i - 1]
        if historico[cl].get("fy") != historico[prev].get("fy"):
            continue          # arranca otro anio fiscal, el FYTD se resetea
        for seg in ("tractores", "cosechadoras"):
            ta, tb = tabla(prev, seg, "FYTD"), tabla(cl, seg, "FYTD")
            for col in pares(ta, tb):
                a, b = val(ta, "dealer", col), val(tb, "dealer", col)
                if a is not None and b is not None and b < a - 0.05:
                    avisar("%s %s %s: el FYTD del dealer baja de %.1f a %.1f "
                           "dentro del mismo anio fiscal" % (cl, seg, col, a, b))


def serie_mensual(historico):
    """FYTD es acumulado: las unidades del mes son la diferencia con el mes
    anterior del mismo anio fiscal (y en noviembre, el FYTD mismo)."""
    claves = sorted(historico)
    series = {}
    for seg in ("tractores", "cosechadoras"):
        # Recorre en orden ascendente y pisa la etiqueta, asi queda la del
        # informe mas nuevo (los limites de clase se movieron con los anios).
        etiquetas = {}
        for cl in claves:
            tabla = historico[cl]["segmentos"].get(seg, {}).get("FYTD")
            if tabla:
                for k, et in zip(tabla["columnas"], tabla["etiquetas"]):
                    if k not in TOTALES:
                        etiquetas[k] = et
        cats = [{"key": k, "label": et} for k, et in etiquetas.items()]
        cats.sort(key=lambda c: orden_cat(seg, c["key"]))
        puntos = []

        for i, cl in enumerate(claves):
            mes = historico[cl]
            tabla = mes["segmentos"].get(seg, {}).get("FYTD")
            if not tabla:
                continue
            anterior = None
            if mes["mes_num"] != MES_INICIO_FY:
                prev = "%d-%02d" % ((mes["anio"] - 1, 12) if mes["mes_num"] == 1
                                    else (mes["anio"], mes["mes_num"] - 1))
                if prev in historico:
                    anterior = historico[prev]["segmentos"].get(seg, {}).get("FYTD")
                    if anterior and historico[prev]["fy"] != mes["fy"]:
                        anterior = None

            punto = {"clave": cl, "mes": mes["mes_cor"], "fy": mes["fy"],
                     "derivado": mes["mes_num"] != MES_INICIO_FY,
                     "completo": mes["mes_num"] == MES_INICIO_FY or anterior is not None}
            for tipo in ("dealer", "industria"):
                vals = {}
                for c in cats + [{"key": t} for t in TOTALES]:
                    a = valor(tabla, tipo, c["key"])
                    if a is None:
                        continue
                    if mes["mes_num"] == MES_INICIO_FY:
                        vals[c["key"]] = round(a, 1)
                    elif anterior is not None:
                        b = valor(anterior, tipo, c["key"]) or 0.0
                        vals[c["key"]] = round(a - b, 1)
                punto[tipo] = vals
            if punto["completo"]:
                puntos.append(punto)
        series[seg] = {"categorias": cats, "puntos": puntos}
    return series


def orden_cat(seg, clave):
    if seg == "cosechadoras":
        m = re.search(r"\d+", clave)
        return int(m.group()) if m else 99
    if clave.startswith("<"):
        return -1
    m = re.match(r"(\d+)", clave)
    return int(m.group(1)) if m else 9999


def valor(tabla, tipo, clave):
    f = next((f for f in tabla["filas"] if f["tipo"] == tipo), None)
    if not f or clave not in tabla["columnas"]:
        return None
    return f["valores"][tabla["columnas"].index(clave)]


# ---------------------------------------------------------------------- main

def main():
    if len(sys.argv) > 1:
        pdfs = [os.path.abspath(a) for a in sys.argv[1:]]
    else:
        vistos, pdfs = set(), []
        for r in sorted(glob.glob(os.path.join(DIR_DATOS, "*.pdf")) +
                        glob.glob(os.path.join(DIR_DATOS, "*.PDF"))):
            if r.lower() not in vistos:
                vistos.add(r.lower())
                pdfs.append(r)

    # Si se pasan archivos sueltos hay que MEZCLAR con lo que ya esta cargado:
    # arrancar de cero borraria el resto del historico.
    historico = {}
    if len(sys.argv) > 1 and os.path.exists(HISTORICO):
        with open(HISTORICO, encoding="utf-8") as fh:
            historico = json.load(fh)
        print("Partiendo del historico existente (%d meses)" % len(historico))
    sin_texto = []
    for ruta in pdfs:
        try:
            d = parsear_pdf(ruta)
        except SystemExit as e:
            sin_texto.append(os.path.basename(ruta))
            print("  [!] sin capa de texto, el texto vino convertido a curvas: %s"
                  % os.path.basename(ruta))
            continue
        verificar(d)
        historico[d["clave"]] = d
        print("  OK -> %s | %s | %s" % (d["mes_es"], d["dealer"], d["fy"]))

    # Meses transcriptos a mano (PDF sin capa de texto)
    for ruta in sorted(glob.glob(os.path.join(DIR_MANUAL, "*.json"))):
        with open(ruta, encoding="utf-8") as fh:
            d = json.load(fh)
        verificar(d)
        historico[d["clave"]] = d
        print("  OK -> %s | %s | transcripcion manual" % (d["mes_es"], d["dealer"]))

    if not historico:
        raise SystemExit("No se pudo procesar ningun informe")

    historico = dict(sorted(historico.items()))
    verificar_cruzado(historico)
    faltan = huecos(historico)
    if faltan:
        avisar("faltan meses en la serie: " + ", ".join(faltan))

    with open(HISTORICO, "w", encoding="utf-8") as fh:
        json.dump(historico, fh, ensure_ascii=False, indent=1)

    indicadores = None
    if os.path.exists(INDICADORES):
        with open(INDICADORES, encoding="utf-8") as fh:
            indicadores = json.load(fh)
    else:
        avisar("no hay datos/indicadores.json; correr indicadores.py")

    # datos/conclusiones.json ya no se embebe: la conclusion que muestra la
    # pagina se calcula en el navegador sobre el periodo de la ficha, que puede
    # ser cualquier rango. El archivo queda igual, con las 44 redactadas por
    # mes x segmento, porque es la base del panel en vivo que quedo pendiente.
    payload = {
        "meses": historico,
        "series": serie_mensual(historico),
        "indicadores": indicadores,
        "generado": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "avisos": AVISOS,
    }
    with open(PLANTILLA, encoding="utf-8") as fh:
        html = fh.read()
    html = html.replace("/*__DATOS__*/null/*__FIN__*/",
                        json.dumps(payload, ensure_ascii=False))
    with open(SALIDA, "w", encoding="utf-8") as fh:
        fh.write(html)

    print("\nHistorico: %d meses (%s a %s)" % (
        len(historico), min(historico), max(historico)))
    print("Dashboard -> " + SALIDA)
    if sin_texto:
        print("\nPDF sin texto extraible, pendientes de transcribir a datos/manual/:")
        for e in sin_texto:
            print("  - " + e)
    if AVISOS:
        print("\n%d aviso(s)." % len(AVISOS))


def huecos(historico):
    claves = sorted(historico)
    falta = []
    if not claves:
        return falta
    a, m = [int(x) for x in claves[0].split("-")]
    fin = claves[-1]
    while True:
        cl = "%d-%02d" % (a, m)
        if cl == fin:
            break
        m += 1
        if m == 13:
            a, m = a + 1, 1
        cl = "%d-%02d" % (a, m)
        if cl not in historico:
            falta.append(cl)
    return falta


if __name__ == "__main__":
    main()
