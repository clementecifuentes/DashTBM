# Dashboard TBM — Cetomaq

Publica las tablas **FYTD** y **LFYTD** del reporte mensual *Argentina TBM
Dealer Analysis* (John Deere) — tractores y cosechadoras — con la variación de
la industria a nivel AOR, Territorio y País, y la evolución mes a mes por
categoría.

**https://clementecifuentes.github.io/DashTBM/**

## Actualización mensual

1. Copiar el PDF nuevo a `datos/`
2. `python indicadores.py` — baja tasas y crédito del BCRA (opcional pero
   recomendado: deja el contexto al día)
3. `python procesar_tbm.py`
4. `git add -A && git commit -m "TBM <mes>" && git push`

El paso 3 lee todos los PDF de `datos/`, acumula cada mes en
`datos/historico.json` y regenera `index.html`, que es autocontenido.

## Qué muestra

Una sola página, en dos bloques:

1. **Tablas del informe** — FYTD y LFYTD tal cual salen del PDF, sin nada
   calculado encima. Selector de segmento arriba; click en el encabezado de una
   columna para resaltarla en las dos tablas a la vez.
2. **Evolución mensual** — unidades de cada mes (no acumuladas), con filtro de
   rango (desde / hasta) y de variables, combinables entre tractores y
   cosechadoras. Debajo del gráfico se calcula la variación entre los meses y
   las variables elegidos: valor inicial, final, Δ en unidades, Δ %, total del
   rango y promedio mensual. El contexto de tasas y retenciones queda plegado.

Un mes puede dar **negativo**: el reporte reasigna unidades entre AOR de un
informe al siguiente, así que el FYTD del AOR a veces baja. Cuando un extremo
del rango es cero o negativo el Δ % se muestra como `—`, porque no es
interpretable.

## Cómo se leen los números

- **FYTD**: acumulado del año fiscal en curso. **El año fiscal arranca en
  noviembre** (verificado: el FYTD se resetea de 229,6 en oct-2025 a 10,8 en
  nov-2025).
- **LFYTD**: mismo período del año fiscal anterior.
- Las **unidades mensuales** del gráfico se derivan restando el FYTD de un
  informe menos el del anterior. En noviembre el FYTD ya es el mes.
- El dealer opera dentro de su AOR: sus unidades se repiten en AOR, Territorio
  y País; lo que cambia es contra qué universo se mide el share.

### El AOR del año anterior se recalcula

Comparando cada LFYTD contra el FYTD del mismo mes publicado un año antes:

| | dealer | industria AOR | industria País |
|---|---|---|---|
| coincide | **siempre, exacto** | no | sí |
| desvío | 0% | **+7% a +23%** | 0,0% |

Las unidades propias del dealer y los totales nacionales quedan firmes; lo que
se recalcula hacia arriba con los meses es la **asignación de unidades al AOR**.
Por eso el dashboard muestra, junto a la variación que informa el reporte, la
comparación contra el dato del año anterior **tal como estaba publicado en su
momento**: en jul-2026 los tractores del AOR pasan de −18,2% a −2,9%.

## Indicadores de contexto

`indicadores.py` baja de la **API pública del BCRA** (Estadísticas Monetarias
v4.0, sin clave ni registro) y mensualiza:

| serie | id BCRA | qué es |
|---|---|---|
| BADLAR privados | 7 | costo de fondeo mayorista, % TNA |
| TAMAR privados | 44 | plazo fijo mayorista, % TNA |
| Adelantos en cta. cte. | 13 | capital de trabajo, % TNA |
| Préstamos prendarios | 113 | stock, la línea con la que se financia maquinaria |
| Préstamos por documentos | 111 | stock |
| Tipo de cambio mayorista | 5 | $/US$ |

Las tasas se promedian dentro del mes; los stocks se toman al cierre. Los stocks
además se pasan a dólares: en pesos nominales, con la inflación del período, la
serie no se puede comparar consigo misma.

Los **derechos de exportación** no salen de ninguna API: están curados a mano en
`datos/eventos.json`, con decreto, fecha, alícuotas y fuente para cada cambio
(38/2025, 439/2025, 526/2025, 682/2025, 877/2025, 423/2026). El 0% de
septiembre de 2025 duró dos días hábiles hasta agotar el cupo de US$ 7.000
millones, así que va marcado como evento y no como nivel mensual.

El panel usa **eje y propio** y comparte solo el eje x con el gráfico de
unidades. Superponer dos escalas en un mismo dibujo es la forma clásica de
fabricar correlaciones que no están en los datos.

## Informes escaneados

Feb-2026 y Jun-2026 llegaron con el texto convertido a curvas (sin capa de
texto). Están transcriptos a mano en `datos/manual/transcribir.py`, que valida
cada cifra contra dos condiciones independientes antes de generar el JSON:
Industria = suma de las filas, y Market Share = dealer / industria. Si llega
otro informe así, se agrega ahí siguiendo el mismo formato.

## Archivos

| Archivo | Qué es |
|---|---|
| `procesar_tbm.py` | Lee los PDF, valida y genera el HTML |
| `indicadores.py` | Baja tasas y crédito del BCRA |
| `datos/eventos.json` | Cambios de retenciones, curados con fuente |
| `datos/indicadores.json` | **Generado.** Series mensualizadas |
| `plantilla.html` | Diseño del dashboard (editar acá, no en `index.html`) |
| `index.html` | **Generado.** Autocontenido, es lo que se publica |
| `datos/historico.json` | Datos acumulados de todos los meses |
| `datos/manual/` | Transcripción de los informes sin capa de texto |
| `datos/*.pdf` | Reportes originales (no se suben al repo) |

## Validaciones automáticas

`procesar_tbm.py` avisa por consola y en la propia página si:

- en alguna categoría o en el AOR la fila *Industria* no es la suma de las demás
  (tolerancia 2%);
- no puede interpretar el encabezado de una columna;
- faltan meses en la serie.

El formato del reporte no es fijo: **omite las columnas que están en cero** (en
nov-2024 la tabla LFYTD de cosechadoras trae 2 categorías en vez de 4) y los
límites de clase se movieron con los años (`Pg7 272 < 319` en 2024,
`Pg7 272<320` en 2026). Por eso el encabezado de cada tabla se lee de verdad y
se normaliza a una clave canónica, en lugar de asumir columnas fijas.

## Requisitos

```bash
pip install pdfplumber
```
