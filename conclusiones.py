# -*- coding: utf-8 -*-
"""Conclusiones del panel: una por cada filtro de la tabla (mes x segmento).

El dashboard es un HTML estatico servido por GitHub Pages: no hay nada corriendo
del lado del servidor cuando alguien lo mira. Asi que la conclusion se escribe
ACA, al generar la pagina, y queda embebida en index.html.

Por defecto NO llama a ninguna API y no necesita ninguna clave. El flujo normal
es que Clemente pase el PDF del mes y la conclusion se escriba en esa misma
conversacion:

    python conclusiones.py --pendientes     # vuelca los resumenes que faltan
    ... se escriben los textos en un JSON {"2026-08|tractores": "..."} ...
    python conclusiones.py --cargar textos.json

El cache va por hash del resumen: si el resumen de una combinacion no cambio,
el texto guardado sigue valiendo y esa combinacion no vuelve a aparecer. En un
mes normal son 2 conclusiones nuevas, no 44.

Queda tambien un modo que llama a la API de Anthropic, apagado por defecto:

    python conclusiones.py --api            # necesita ANTHROPIC_API_KEY

No hace falta para el uso normal. Esta por si algun dia se arma el panel en
vivo: un Worker que guarde la clave del lado del servidor y al que la pagina le
pida la conclusion, que es la unica forma de que refleje tambien los filtros del
grafico. La clave nunca se escribe a disco, solo se lee del entorno.

Otros usos:
    python conclusiones.py --todo           # ignora el cache, rehace las 44
    python conclusiones.py --api --modelo X # otro modelo
"""

import hashlib
import json
import os
import re
import sys
from datetime import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
HISTORICO = os.path.join(BASE, "datos", "historico.json")
INDICADORES = os.path.join(BASE, "datos", "indicadores.json")
SALIDA = os.path.join(BASE, "datos", "conclusiones.json")
PENDIENTES = os.path.join(BASE, "_pendientes.json")   # _*.json esta en .gitignore

MODELO = "claude-sonnet-5"
MAX_TOKENS = 300
MAX_ORACIONES = 5

SEG_ES = {"tractores": "Tractores", "cosechadoras": "Cosechadoras"}

SISTEMA = (
    "Sos analista comercial de un concesionario John Deere en Argentina. "
    "Escribis conclusiones para el tablero interno que mira la gerencia.\n"
    "Reglas:\n"
    "- Maximo 5 oraciones, en espanol rioplatense, tono sobrio y directo.\n"
    "- Usa SOLO los numeros del resumen que te pasan. No inventes datos, "
    "no estimes, no agregues contexto de mercado que no este en el resumen.\n"
    "- Destaca lo mas relevante: la variacion interanual, el peso del "
    "concesionario en su zona y donde se concentran las unidades.\n"
    "- 'AOR' es la zona de influencia del concesionario. FYTD es el acumulado "
    "del anio fiscal en curso y LFYTD el del anio anterior al mismo mes, asi "
    "que comparar uno con otro ES la variacion interanual.\n"
    "- Nada de titulos, vinetas ni encabezados: solo el parrafo.\n"
    "- No repitas el nombre del mes y el segmento en la primera oracion, ya "
    "estan en pantalla."
)


def fila(tabla, tipo):
    if not tabla:
        return None
    return next((f for f in tabla["filas"] if f["tipo"] == tipo), None)


def val(tabla, tipo, col):
    f = fila(tabla, tipo)
    if not f or col not in tabla["columnas"]:
        return None
    return f["valores"][tabla["columnas"].index(col)]


def variacion(act, ant):
    """Variacion porcentual, o None cuando no se puede calcular."""
    if act is None or ant is None or not ant:
        return None
    return round((act - ant) / ant * 100.0, 1)


def bandas(tabla, tipo):
    """Unidades por banda de potencia, sin los tres totales."""
    if not tabla:
        return []
    f = fila(tabla, tipo)
    if not f:
        return []
    out = []
    for i, col in enumerate(tabla["columnas"]):
        if col in ("AOR", "TERRITORIO", "PAIS"):
            continue
        v = f["valores"][i]
        if v:
            out.append({"banda": tabla["etiquetas"][i], "unidades": v})
    return sorted(out, key=lambda x: -x["unidades"])


def indicadores_del_mes(ind, clave):
    """Retenciones de soja y dolar oficial vigentes al cierre del mes."""
    if not ind:
        return None
    out = {}
    of = (ind.get("series") or {}).get("oficial") or {}
    if clave in of:
        out["dolar_oficial_cierre"] = of[clave]
    vig = None
    for e in ind.get("eventos") or []:
        if e.get("solo_evento") or not e.get("alicuotas"):
            continue
        if (e.get("mes") or e["fecha"][:7]) <= clave:
            vig = e
    if vig:
        out["retenciones_soja_pc"] = vig["alicuotas"].get("soja")
        out["ultimo_decreto"] = vig["titulo"]
    return out or None


def resumen(historico, ind, clave, seg):
    """Resumen compacto de una combinacion mes x segmento.

    Es lo unico que se mira para escribir la conclusion. Tiene que ser estable:
    si cambia un byte, el cache se invalida y esa combinacion vuelve a pedirse.
    """
    mes = historico[clave]
    segm = mes["segmentos"].get(seg) or {}
    fy, lfy = segm.get("FYTD"), segm.get("LFYTD")
    if not fy and not lfy:
        return None

    r = {
        "mes": mes["mes_es"],
        "segmento": SEG_ES[seg],
        "anio_fiscal": mes["fy"],
        "concesionario": mes["dealer"],
    }

    for per, t in (("FYTD", fy), ("LFYTD", lfy)):
        if not t:
            continue
        r[per] = {
            "dealer_aor": val(t, "dealer", "AOR"),
            "industria_aor": val(t, "industria", "AOR"),
            "share_aor_pc": val(t, "share", "AOR"),
            "industria_pais": val(t, "industria", "PAIS"),
            "share_pais_pc": val(t, "share", "PAIS"),
            "bandas_con_ventas": len(bandas(t, "industria")),
            "bandas_en_el_informe": len([c for c in t["columnas"]
                                         if c not in ("AOR", "TERRITORIO", "PAIS")]),
        }

    if fy and lfy:
        r["variacion_interanual_pc"] = {
            "dealer_aor": variacion(val(fy, "dealer", "AOR"),
                                    val(lfy, "dealer", "AOR")),
            "industria_aor": variacion(val(fy, "industria", "AOR"),
                                       val(lfy, "industria", "AOR")),
            "industria_pais": variacion(val(fy, "industria", "PAIS"),
                                        val(lfy, "industria", "PAIS")),
        }

    if fy:
        bd, bi = bandas(fy, "dealer"), bandas(fy, "industria")
        r["bandas_fytd"] = {"top3_concesionario": bd[:3],
                            "top3_industria_aor": bi[:3]}
        if bi:
            us = [b["unidades"] for b in bi]
            r["bandas_fytd"]["industria_aor_min_max_promedio"] = [
                min(us), max(us), round(sum(us) / len(us), 1)]

    imes = indicadores_del_mes(ind, clave)
    if imes:
        r["contexto"] = imes
    return r


def firma(r):
    return hashlib.sha256(json.dumps(r, sort_keys=True, ensure_ascii=False)
                          .encode("utf-8")).hexdigest()[:16]


def oraciones(t):
    # Los puntos de un numero (1.031, 3.937) no terminan una oracion.
    t = re.sub(r"(?<=\d)\.(?=\d)", "", t)
    return len([x for x in t.replace("!", ".").replace("?", ".").split(".")
                if x.strip()])


def cargar_textos(cache, pendientes, ruta):
    """Mete los textos escritos a mano, con la firma del resumen que los origino."""
    with open(ruta, encoding="utf-8") as fh:
        textos = json.load(fh)
    porclave = {k: f for k, _, f in pendientes}
    puestos, rechazados = 0, 0
    for k, texto in textos.items():
        texto = (texto or "").strip()
        if k not in porclave:
            print("  [!] %-26s no estaba pendiente, se ignora" % k)
            rechazados += 1
            continue
        if not texto:
            print("  [!] %-26s texto vacio" % k)
            rechazados += 1
            continue
        n = oraciones(texto)
        if n > MAX_ORACIONES:
            print("  [!] %-26s %d oraciones, el maximo es %d"
                  % (k, n, MAX_ORACIONES))
            rechazados += 1
            continue
        cache[k] = {"firma": porclave[k], "texto": texto,
                    "modelo": "redaccion propia",
                    "generado": datetime.now().strftime("%Y-%m-%d %H:%M")}
        puestos += 1
        print("  OK %-26s %d oraciones, %d caracteres" % (k, n, len(texto)))
    faltan = [k for k, _, _ in pendientes if k not in textos]
    if faltan:
        print("\n  Siguen sin conclusion: " + ", ".join(faltan[:8])
              + (" y %d mas" % (len(faltan) - 8) if len(faltan) > 8 else ""))
    return puestos, rechazados


def pedir(cliente, modelo, r):
    msg = cliente.messages.create(
        model=modelo,
        max_tokens=MAX_TOKENS,
        system=SISTEMA,
        messages=[{"role": "user", "content":
                   "Resumen de los datos filtrados:\n\n"
                   + json.dumps(r, ensure_ascii=False, indent=1)
                   + "\n\nEscribi la conclusion."}],
    )
    return " ".join(b.text for b in msg.content if b.type == "text").strip()


def por_api(cache, pendientes, modelo):
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("\n[!] No esta definida ANTHROPIC_API_KEY, no se genera nada.")
        print("    Las conclusiones que ya estaban siguen publicandose.")
        print("    En PowerShell:  $env:ANTHROPIC_API_KEY = 'sk-ant-...'")
        raise SystemExit(1)
    try:
        import anthropic
    except ImportError:
        raise SystemExit("Falta el SDK: pip install anthropic")
    cliente = anthropic.Anthropic()
    hechas, fallidas = 0, 0
    for k, r, f in pendientes:
        try:
            texto = pedir(cliente, modelo, r)
        except Exception as e:
            # Se conserva lo que hubiera de antes: un fallo de red no tiene por
            # que dejar el panel vacio.
            fallidas += 1
            print("  [!] %-26s %s" % (k, e))
            continue
        cache[k] = {"firma": f, "texto": texto, "modelo": modelo,
                    "generado": datetime.now().strftime("%Y-%m-%d %H:%M")}
        hechas += 1
        print("  OK %-26s %d caracteres" % (k, len(texto)))
    return hechas, fallidas


def guardar(cache):
    with open(SALIDA, "w", encoding="utf-8") as fh:
        json.dump({"conclusiones": dict(sorted(cache.items())),
                   "generado": datetime.now().strftime("%Y-%m-%d %H:%M")},
                  fh, ensure_ascii=False, indent=1)
    print("-> %s (%d conclusiones)" % (SALIDA, len(cache)))
    print("Ahora corre: python procesar_tbm.py   (para regenerar index.html)")


def main():
    args = sys.argv[1:]
    todo = "--todo" in args
    modelo = args[args.index("--modelo") + 1] if "--modelo" in args else MODELO

    if not os.path.exists(HISTORICO):
        raise SystemExit("Falta datos/historico.json: corre primero procesar_tbm.py")
    with open(HISTORICO, encoding="utf-8") as fh:
        historico = json.load(fh)
    ind = None
    if os.path.exists(INDICADORES):
        with open(INDICADORES, encoding="utf-8") as fh:
            ind = json.load(fh)

    cache = {}
    if os.path.exists(SALIDA) and not todo:
        with open(SALIDA, encoding="utf-8") as fh:
            cache = json.load(fh).get("conclusiones", {})

    total, pendientes = 0, []
    for clave in sorted(historico):
        for seg in ("tractores", "cosechadoras"):
            r = resumen(historico, ind, clave, seg)
            if r is None:
                continue          # el informe no trae ese segmento ese mes
            total += 1
            k, f = clave + "|" + seg, firma(r)
            if cache.get(k, {}).get("firma") == f:
                continue          # el resumen no cambio: el texto sigue valiendo
            pendientes.append((k, r, f))

    print("%d combinaciones, %d sin conclusion al dia" % (total, len(pendientes)))

    if "--cargar" in args:
        puestos, rechazados = cargar_textos(
            cache, pendientes, args[args.index("--cargar") + 1])
        print("\n%d cargadas, %d rechazadas" % (puestos, rechazados))
        guardar(cache)
        return

    if not pendientes:
        print("Nada cambio, el cache esta al dia.")
        return

    if "--api" in args:
        hechas, fallidas = por_api(cache, pendientes, modelo)
        print("\n%d generadas, %d con error" % (hechas, fallidas))
        guardar(cache)
        return

    # Modo por defecto: volcar los resumenes para escribir los textos a mano.
    with open(PENDIENTES, "w", encoding="utf-8") as fh:
        json.dump({k: {"firma": f, "resumen": r} for k, r, f in pendientes},
                  fh, ensure_ascii=False, indent=1)
    print("\n-> %s" % PENDIENTES)
    print('Escribi los textos en un JSON {"clave|segmento": "texto"} y corre:')
    print("    python conclusiones.py --cargar <ese archivo>")


if __name__ == "__main__":
    main()
