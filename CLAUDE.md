# Contexto del proyecto

Dashboard del informe **Argentina TBM Dealer Analysis** que John Deere le manda
a Cetomaq (Ceres Tolvas) todos los meses. Publica las cuatro tablas del informe
—Tractores y Cosechadoras, cada una en FYTD y LFYTD— **tal cual salen del PDF**,
más un gráfico de evolución mensual y un panel de retenciones y tipo de cambio.

Se publica por GitHub Pages en la raíz de `main`: lo que se ve es `index.html`.

## Lo que llega cada mes

Un único PDF nuevo. Todo el resto del trabajo es mecánico:

```bash
python indicadores.py      # dólar y retenciones al día
python procesar_tbm.py     # relee todos los PDF y regenera index.html
```

Eso es todo. **El panel de conclusión no entra en el flujo mensual**: se calcula
en el navegador sobre lo que ya está embebido, así que se actualiza solo con el
mes nuevo. No hay que correr nada para eso.

`conclusiones.py` y `datos/conclusiones.json` quedaron del diseño anterior, con
una conclusión redactada a mano por mes × segmento. **Ya no se embeben en la
página** y están desactualizados a propósito: son la base del panel en vivo que
quedó pendiente para cuando haya cuenta de API. Si alguna vez se retoman, el
script vuelca en `_pendientes.json` los resúmenes que faltan y los textos se
cargan con `python conclusiones.py --cargar <archivo>`.

`procesar_tbm.py` sin argumentos relee todo `datos/*.pdf`. Con un archivo suelto
como argumento procesa solo ese y lo **mezcla** con el histórico existente, no
arranca de cero.

Antes del push hay que mirar los números, no solo que el script termine bien:
el informe nuevo tiene que entrar sin avisos y el mes anterior no tiene que
haberse movido.

## Convenciones

- Los commits van a nombre de Clemente, con mensaje en castellano y **sin líneas
  de coautoría ni menciones de herramientas al pie**. Esto no es negociable: el
  repo es público y la lista de contribuidores tiene que quedar limpia.
- El diseño se edita en `plantilla.html`. `index.html` es **generado**: cualquier
  cambio hecho ahí se pierde en el próximo procesamiento.
- `estable.html` es una copia congelada que sirve de referencia. No se regenera.
- Arriba de todo va el bloque **"Peso en la red John Deere"** (`pintarRed`), en
  verde sólido para que se lea como titular. Es un dato **derivado**, no sale
  del informe: `JD = industria − marca − competidores`, y el resto de la red es
  eso menos el concesionario. En el AOR da cero (es el único concesionario JD
  de su zona), por eso solo se muestran Territorio y País. Siempre tiene que
  decir que es derivado.
- El panel de conclusión va **a la derecha de la ficha** y se calcula en el
  navegador (`puntosFicha`), con los números que `cifras()` ya computó para el
  cuadro. Nunca recalcular por separado: si los dos hicieran la cuenta por su
  lado podrían mostrar cifras distintas. Máximo 4 puntos.
- Nunca mostrarle al que visita la página un cartel pidiendo correr un script,
  ni meter ese tipo de faltante en `avisar()`: los avisos se publican.
- No agregar indicadores, tarjetas ni secciones que no estén pedidas. La página
  ya se rediseñó dos veces por estar sobrecargada de datos.

## Cosas del informe que no son obvias

- **El año fiscal de Deere arranca en noviembre.** El FYTD se resetea ahí
  (oct-2025 cerró en 229,6 y nov-2025 arrancó en 10,8).
- **Las columnas cambian de un informe a otro.** El reporte omite las categorías
  que están en cero y los límites de clase se movieron con los años, así que el
  encabezado de cada tabla se lee de verdad y se normaliza a una clave canónica.
- **En el AOR la suma cierra: dealer + marca + competidores = industria.** Eso
  es lo que permite despejar John Deere, y significa que `Competitors` son
  todas las marcas que no son JD ni la marca listada (Pauny, que solo aparece
  en tractores). En Territorio y País la suma NO cierra, y el faltante es el
  resto de la red JD. Si Deere alguna vez dejara una marca afuera de
  `Competitors`, el número derivado se iría sin que nada falle: por eso
  `verificar_red()` exige que la red despejada no sea negativa ni menor que el
  propio concesionario.
- **Las unidades del dealer nunca se recalculan; las de la industria sí.** El AOR
  de la industria de FY25 quedó reexpresado para arriba entre un 7% y un 23%
  respecto de lo que se había publicado en su momento. El País no se toca (0,0%).
  Por eso las comparaciones interanuales van contra el dato reexpresado, y la
  diferencia contra el dato original está aclarada donde corresponde.
- **Feb-2026 y jun-2026 vinieron con el texto convertido a curvas** y están
  transcriptos a mano en `datos/manual/`. Si llega otro así, se agrega ahí.

## Efectos visuales

Cualquier animación tiene que dejar el estado final visible **sin** depender de
JavaScript ni de `animation-fill-mode`. Una versión anterior arrancaba en
`opacity: 0` y dejó la página entera en blanco cuando el script no llegó a
correr.

## Verificar antes de dar algo por hecho

Para comprobar que un elemento se puede tocar de verdad hay que usar
`elementFromPoint` o un click real. `dispatchEvent` saltea el hit-testing y da
falsos positivos: así se dio por arreglado un tooltip de decretos que en
realidad estaba tapado por otro elemento.
