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

Una sola página:

0. **Una ficha arriba de todo**, del segmento que esté elegido en el
   interruptor Tractores / Cosechadoras, el mismo que manda en las tablas.
   Compara el año fiscal en curso contra el anterior, en **AOR y en País**,
   para tres filas: industria, Cetomaq y market share. Sale directo de las
   tablas FYTD y LFYTD del informe elegido, así que cambia con el selector de
   informe y con el de segmento.

1. **Tablas del informe** — FYTD y LFYTD tal cual salen del PDF, sin nada
   calculado encima. El interruptor de segmento manda también en la ficha de
   arriba. Click en el encabezado de una columna para resaltarla en las dos
   tablas a la vez.
2. **Evolución mensual por tipo de máquina** — una línea por cada tipo de las
   tablas (14 bandas de potencia, 4 clases de cosechadora), todas en el mismo
   gráfico. **Segmento y medida aceptan las dos opciones a la vez**: se pueden
   ver tractores y cosechadoras juntos, e industria y Cetomaq juntos, hasta 36
   líneas. El color sigue al tipo de máquina y el trazo a la medida —llena la
   industria, punteada Cetomaq— así los dos ejes de elección no se pisan. Nunca
   se pueden apagar las dos opciones de un mismo grupo: siempre queda una. La leyenda de abajo apaga y prende cada una. Al pasar el mouse se
   aísla la línea más cercana y el resto se atenúa. Filtro de rango
   (desde / hasta), de segmento y de medida (industria o dealer). Debajo se
   El resumen de todo eso sube a las fichas de arriba.
3. **Proyección sobre el gráfico** — tres interruptores encima del gráfico de
   ventas:
   - *Decretos*: línea vertical con un punto amarillo en el mes de cada decreto;
     el tooltip dice cuál es y qué cambió.
   - *Retenciones*: cinta arriba del área de dibujo con la alícuota de soja
     vigente en cada tramo (33% → 26% → 33% → 26% → 24%).
   - *Dólar oficial*: tira debajo del eje, alineada mes a mes, con su propia
     escala. Es la cotización del **Banco Nación**, tipo vendedor, promediada
     dentro del mes.

   La cinta y la tira comparten el eje de meses con las ventas pero **no** el eje
   vertical. Dibujar el dólar como una línea más dentro del mismo plano sería un
   gráfico de doble eje: se pueden hacer coincidir dos curvas cualesquiera
   moviendo las escalas, y ahí la "correlación" la dibuja uno, no los datos.
4. **Tasas e indicadores** — un botón abre una ventana flotante, que se arrastra
   por su encabezado y se cierra con la × o con Escape. Adentro: el indicador
   elegido en grande con las marcas de cada decreto de retenciones, y abajo una
   grilla con todos los indicadores en miniatura y su último valor. Toma el
   mismo rango de meses que el gráfico de ventas y se actualiza cuando lo
   cambiás, pero cada indicador conserva su propia escala.

### Por qué una rampa y no 18 colores

Las bandas de potencia son una escala **ordenada**, no categorías sueltas. Cada
segmento usa entonces una rampa de un solo tono, de claro (máquina chica) a
oscuro (máquina grande): azul para tractores, naranja para cosechadoras. Con 18
colores distintos nadie distingue una línea de otra; con la rampa se lee de una
que las líneas oscuras son los tractores grandes. El verde y el amarillo quedan
para la identidad de la página, nunca para los datos, así no se confunde la
marca con una serie.

Un mes puede dar **negativo**: el reporte reasigna unidades entre AOR de un
informe al siguiente, así que el FYTD del AOR a veces baja. Cuando un extremo
del rango es cero o negativo el Δ % se muestra como `—`, porque no es
interpretable.

El rango de meses del gráfico arranca por defecto en el **año fiscal en curso**.

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
La página muestra la variación tal como la informa el reporte. Tener presente
al leerla que en jul-2026 los tractores del AOR caen −18,2% contra el LFYTD
recalculado, pero solo −2,9% contra el dato de FY25 publicado en su momento:
buena parte de esa caída es reasignación de unidades al AOR, no mercado.

## Indicadores de contexto

`indicadores.py` baja de la **API pública del BCRA** (Estadísticas Monetarias
v4.0, sin clave ni registro) y mensualiza:

| serie | id BCRA | qué es |
|---|---|---|
| BADLAR privados | 7 | costo de fondeo mayorista, % TNA |
| TAMAR privados | 44 | plazo fijo mayorista, % TNA |
| Adelantos en cta. cte. | 13 | capital de trabajo, % TNA |
| Soja y maíz | FRED/FMI | precio internacional mensual, US$/t |
| Préstamos prendarios | 113 | stock, la línea con la que se financia maquinaria |
| Préstamos por documentos | 111 | stock |
| Tipo de cambio mayorista | 5 | $/US$ (A3500, se usa para pasar los stocks a dólares) |
| Dólar oficial Banco Nación | argentinadatos | $/US$, tipo vendedor, cierre del mes — el que se muestra |

En la página se muestran solo **retenciones y tipo de cambio**; el resto igual
se baja y queda guardado en `datos/indicadores.json`, así volver a mostrar una
serie es agregar su clave a la lista `MOSTRAR` de `indicadores.py` y nada más.

El dólar se muestra como **último valor de cada mes** (el cierre), y el gráfico
termina donde termina el último informe TBM. Por eso el valor del borde no
coincide con el del diario de hoy: jul-2026 cerró en 1.510 y sep-2026 va en
1.535. Tanto la tira como la ventana dicen de qué mes es
cada número, y la ventana avisa hasta dónde llega la serie.

El BCRA **no** publica una serie de Banco Nación: su minorista (id 4) es un
promedio de bancos. El oficial de BNA sale de `api.argentinadatos.com`, que
tiene la historia diaria desde 2011 sin clave. Contra el mayorista corre entre
1,3% y 1,8% arriba en los últimos meses.

Los precios de granos salen de FRED (series del FMI, sin clave): son precios
internacionales del golfo de EEUU, **no** la pizarra de Rosario, que no está
publicada en ninguna API. De ahí se deriva el precio neto de retenciones.

Las tasas se promedian dentro del mes; los stocks y el dólar se toman al cierre. Los stocks
además se pasan a dólares: en pesos nominales, con la inflación del período, la
serie no se puede comparar consigo misma.

Los **derechos de exportación** no salen de ninguna API: están curados a mano en
`datos/eventos.json`, con decreto, fecha, alícuotas y fuente para cada cambio
(38/2025, 439/2025, 526/2025, 682/2025, 877/2025, 423/2026). Cada uno lleva el
**mes en que rige**, que no siempre es el de publicación: el 526/2025 salió el
31/7 y rige desde el 1/8, así que julio-2025 todavía pagó 33%. El 0% de
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
