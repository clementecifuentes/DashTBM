# -*- coding: utf-8 -*-
"""Genera una conclusion corta por cada filtro de la tabla y la deja cacheada.

El dashboard es un HTML estatico servido por GitHub Pages: no hay nada corriendo
del lado del servidor cuando alguien lo mira. Asi que la conclusion se escribe
ACA, al generar la pagina, y queda embebida en index.html. Ventajas sobre
llamar al modelo desde el navegador:

  - la API key no sale de esta maquina (el repo es publico);
  - el panel aparece instantaneo, sin esperar una respuesta;
  - la pagina sigue funcionando sin conexion.

El filtro de la tabla es mes x segmento: 22 x 2 = 44 combinaciones, y cada mes
se agregan 2. Por eso el cache va por hash del resumen: si el resumen de una
combinacion no cambio, se reusa el texto guardado y no se vuelve a llamar. En un
mes normal eso son 2 llamadas, no 44.

Al modelo NO se le manda la tabla: se le manda el resumen que arma resumen(),
en JSON, con los totales, la variacion interanual y el top 3 de bandas de
potencia.

Uso:
    python conclusiones.py              # genera lo que falte o haya cambiado
    python conclusiones.py --todo       # ignora el cache y regenera las 44
    python conclusiones.py --modelo X   # usa otro modelo

Necesita la variable de entorno ANTHROPIC_API_KEY. Si no esta, avisa y no toca
nada: procesar_tbm.py sigue funcionando con las conclusiones que ya haya.
"""

import hashlib
import json
import os
import sys
from datetime import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
HISTORICO = os.path.join(BASE, "datos", "historico.json")
INDICADORES = os.path.join(BASE, "datos", "indicadores.json")
SALIDA = os.path.join(BASE, "datos", "conclusiones.json")

MODELO = "claude-sonnet-5"
MAX_TOKENS = 300

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

    Es lo unico que ve el modelo. Tiene que ser estable: si cambia un byte,
    el cache se invalida y se vuelve a llamar.
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
            "bandas_con_ventas": len([b for b in bandas(t, "industria")]),
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
        r["bandas_fytd"] = {
            "top3_concesionario": bd[:3],
            "top3_industria_aor": bi[:3],
        }
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


def main():
    todo = "--todo" in sys.argv
    modelo = MODELO
    if "--modelo" in sys.argv:
        modelo = sys.argv[sys.argv.index("--modelo") + 1]

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

    pendientes = []
    for clave in sorted(historico):
        for seg in ("tractores", "cosechadoras"):
            r = resumen(historico, ind, clave, seg)
            if r is None:
                continue          # el informe no trae ese segmento ese mes
            k, f = clave + "|" + seg, firma(r)
            if cache.get(k, {}).get("firma") == f:
                continue          # el resumen no cambio: se reusa el texto
            pendientes.append((k, r, f))

    print("%d combinaciones en el historico, %d para generar"
          % (len(cache) + len(pendientes), len(pendientes)))
    if not pendientes:
        print("Nada cambio, el cache esta al dia.")
        return

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
            fallidas += 1
            # Se conserva lo que hubiera de antes: un fallo de red no tiene por
            # que dejar el panel vacio.
            print("  [!] %-24s %s" % (k, e))
            continue
        cache[k] = {"firma": f, "texto": texto, "modelo": modelo,
                    "generado": datetime.now().strftime("%Y-%m-%d %H:%M")}
        hechas += 1
        print("  OK %-24s %d caracteres" % (k, len(texto)))

    with open(SALIDA, "w", encoding="utf-8") as fh:
        json.dump({"conclusiones": dict(sorted(cache.items())),
                   "modelo": modelo,
                   "generado": datetime.now().strftime("%Y-%m-%d %H:%M")},
                  fh, ensure_ascii=False, indent=1)
    print("\n%d generadas, %d con error -> %s" % (hechas, fallidas, SALIDA))
    print("Ahora corre: python procesar_tbm.py   (para regenerar index.html)")


if __name__ == "__main__":
    main()
