# PCP – Prospección de empresas con trabajo continuo

Motor de detección de empresas proveedoras del Estado con contratos largos y vigentes, para PCP Asesores de Seguros.

## Qué hace

Los días 1 y 16 de cada mes, una tarea automática de GitHub:

1. Baja el archivo anual de compras de la Ciudad de Buenos Aires (Buenos Aires Compras, formato OCDS).
2. Se queda con los contratos de **servicios u obras** de **365 días o más** que **siguen vigentes**.
3. Guarda los resultados en la carpeta `datos/`.

Después, un escenario de Make lee `datos/caba_empresas.csv` y lo carga en la planilla como empresas en estado **detectada**.

## Archivos de salida

| Archivo | Contenido |
|---|---|
| `datos/caba_empresas.csv` | Una fila por empresa (CUIT): contratos vigentes, monto total, próximo vencimiento, rubros, organismos |
| `datos/caba_contratos.csv` | Una fila por contrato: objeto, organismo, plazo, vencimiento, monto y link al pliego |
| `datos/resumen.json` | Números de la corrida, para controlar que todo salió bien |

## Correr a mano

En la pestaña **Actions** → **Ingesta CABA** → **Run workflow**.

## Fuente

Datos abiertos del Gobierno de la Ciudad de Buenos Aires, licencia CC BY 2.5 AR:
https://data.buenosaires.gob.ar/dataset/buenos-aires-compras
