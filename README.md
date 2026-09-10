# Dashboard TBM — Cetomaq

Publica en la web las tablas **FYTD** y **LFYTD** del reporte mensual
*Argentina TBM Dealer Analysis* (John Deere), para tractores y cosechadoras,
con la variación de la industria a nivel **AOR**, **Territorio** y **País**.

## Actualización mensual (3 pasos)

1. Copiar el PDF nuevo a `datos/`
2. Ejecutar:

   ```bash
   python procesar_tbm.py
   ```

3. Publicar:

   ```bash
   git add -A && git commit -m "TBM <mes>" && git push
   ```

El paso 2 lee **todos** los PDF de `datos/`, acumula cada mes en
`datos/historico.json` y regenera `index.html`. Con más de un mes cargado
aparece un selector de mes arriba a la derecha.

Si el reporte cambia de formato (categorías nuevas, otra cantidad de columnas),
el script avisa por consola y el dashboard muestra los avisos en pantalla en
lugar de publicar datos mal alineados.

## Archivos

| Archivo | Qué es |
|---|---|
| `procesar_tbm.py` | Lee el PDF, valida y genera el HTML |
| `plantilla.html` | Diseño del dashboard (editar acá, no en `index.html`) |
| `index.html` | **Generado.** Autocontenido, es lo que se publica |
| `datos/historico.json` | Datos acumulados de todos los meses procesados |
| `datos/*.pdf` | Reportes originales (no se suben al repo) |

## Cómo se leen los números

- **FYTD**: acumulado del año fiscal en curso hasta el mes del reporte.
- **LFYTD**: mismo período del año fiscal anterior.
- Los decimales de la industria vienen del propio reporte (prorrateo de zonas).
- El dealer opera dentro de su AOR: sus unidades se repiten en AOR, Territorio
  y País; lo que cambia es contra qué universo se calcula el market share.
- La variación de market share se expresa en puntos porcentuales (pp).

## Validaciones del script

Antes de publicar, `procesar_tbm.py` verifica que en cada categoría y en el AOR
la fila *Industria* sea igual a la suma de las demás filas. Cualquier desvío
mayor al 2% se reporta como aviso.

## Requisitos

```bash
pip install pdfplumber
```
