"""
Ingesta CABA - Buenos Aires Compras (BAC)

Baja el archivo anual de compras de la Ciudad (formato OCDS, ~80 MB),
se queda con los contratos de servicios u obras de 1 año o más que
siguen vigentes (vencen hoy o después) y genera:

  datos/caba_contratos.csv  -> una fila por contrato (evidencia)
  datos/caba_empresas.csv   -> una fila por empresa (CUIT), lista para la planilla
  datos/resumen.json        -> números de la corrida, para controlar

Regla de oro del proyecto: solo entran empresas con evidencia de
trabajo continuo (contrato largo y vigente con el Estado).
"""

import csv
import json
import os
import sys
import urllib.request
from collections import defaultdict
from datetime import date, datetime, timezone

URL = (
    "https://cdn.buenosaires.gob.ar/datosabiertos/datasets/"
    "ministerio-de-economia-y-finanzas/buenos-aires-compras/bac_anual.json"
)
DURACION_MINIMA_DIAS = 365
CATEGORIAS = {"services", "works"}
SALIDA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "datos")


def bajar(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=900) as r:
        return r.read()


def num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


def fecha(s):
    return (s or "")[:10]


def main():
    hoy = date.today().isoformat()
    print("Bajando", URL)
    raw = bajar(URL)
    print(f"Bajados {len(raw)/1048576:.1f} MB")
    paquete = json.loads(raw)
    raw = None
    releases = paquete.get("releases", [])
    print("Procesos:", len(releases))

    contratos = []
    vistos = set()
    anios = defaultdict(int)
    for rel in releases:
        tender = rel.get("tender") or {}
        categoria = tender.get("mainProcurementCategory") or ""
        rubro = ", ".join(c.strip() for c in (tender.get("additionalProcurementCategories") or []))
        organismo = ((tender.get("procuringEntity") or {}).get("name") or "").strip()
        metodo = (tender.get("procurementMethodDetails") or "").strip()
        for aw in rel.get("awards") or []:
            anios[fecha(aw.get("date"))[:4]] += 1
            periodo = aw.get("contractPeriod") or {}
            dias = int(num(periodo.get("durationInDays")))
            vence = fecha(periodo.get("endDate"))
            if categoria not in CATEGORIAS or dias < DURACION_MINIMA_DIAS:
                continue
            if not vence or vence < hoy:
                continue
            link = ""
            for d in aw.get("documents") or []:
                if d.get("url"):
                    link = d["url"]
                    break
            for sup in aw.get("suppliers") or []:
                cuit = (sup.get("id") or "").strip()
                clave = (rel.get("ocid"), aw.get("id"), cuit)
                if not cuit or clave in vistos:
                    continue
                vistos.add(clave)
                contratos.append({
                    "cuit": cuit,
                    "razon_social": (sup.get("name") or "").strip(),
                    "categoria": "Servicios" if categoria == "services" else "Obras",
                    "rubro": rubro,
                    "objeto": (aw.get("title") or tender.get("title") or "").strip(),
                    "organismo": organismo,
                    "procedimiento": metodo,
                    "fecha_adjudicacion": fecha(aw.get("date")),
                    "inicio": fecha(periodo.get("startDate")),
                    "vencimiento": vence,
                    "duracion_dias": dias,
                    "monto": round(num((aw.get("value") or {}).get("amount")), 2),
                    "moneda": (aw.get("value") or {}).get("currency") or "ARS",
                    "proceso": rel.get("ocid") or "",
                    "link_fuente": link,
                })

    contratos.sort(key=lambda c: (c["vencimiento"], c["cuit"]))

    empresas = {}
    for c in contratos:
        e = empresas.setdefault(c["cuit"], {
            "cuit": c["cuit"],
            "razon_social": c["razon_social"],
            "contratos_vigentes": 0,
            "monto_total": 0.0,
            "proximo_vencimiento": c["vencimiento"],
            "ultimo_vencimiento": c["vencimiento"],
            "rubros": set(),
            "organismos": set(),
            "ejemplo_objeto": c["objeto"],
            "link_fuente": c["link_fuente"],
            "fuente": "CABA - Buenos Aires Compras",
            "estado": "detectada",
            "fecha_alta": hoy,
        })
        e["contratos_vigentes"] += 1
        e["monto_total"] += c["monto"]
        e["proximo_vencimiento"] = min(e["proximo_vencimiento"], c["vencimiento"])
        e["ultimo_vencimiento"] = max(e["ultimo_vencimiento"], c["vencimiento"])
        if c["rubro"]:
            e["rubros"].add(c["rubro"])
        if c["organismo"]:
            e["organismos"].add(c["organismo"])

    filas_empresas = []
    for e in empresas.values():
        e["rubros"] = " | ".join(sorted(e["rubros"]))
        e["organismos"] = " | ".join(sorted(e["organismos"]))
        e["monto_total"] = round(e["monto_total"], 2)
        filas_empresas.append(e)
    filas_empresas.sort(key=lambda e: -e["monto_total"])

    os.makedirs(SALIDA, exist_ok=True)
    with open(os.path.join(SALIDA, "caba_contratos.csv"), "w", newline="", encoding="utf-8") as f:
        campos = list(contratos[0].keys()) if contratos else ["cuit"]
        w = csv.DictWriter(f, fieldnames=campos)
        w.writeheader()
        w.writerows(contratos)
    with open(os.path.join(SALIDA, "caba_empresas.csv"), "w", newline="", encoding="utf-8") as f:
        campos = list(filas_empresas[0].keys()) if filas_empresas else ["cuit"]
        w = csv.DictWriter(f, fieldnames=campos)
        w.writeheader()
        w.writerows(filas_empresas)

    por_rubro = defaultdict(int)
    for e in filas_empresas:
        for r in (e["rubros"] or "Sin rubro").split(" | "):
            por_rubro[r] += 1

    resumen = {
        "corrida": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "fuente": URL,
        "publicado_por_la_ciudad": paquete.get("publishedDate"),
        "procesos_en_archivo": len(releases),
        "adjudicaciones_por_anio": dict(sorted(anios.items())),
        "filtro": f"servicios u obras, contrato de {DURACION_MINIMA_DIAS} dias o mas, vigente al {hoy}",
        "contratos_que_pasan_el_filtro": len(contratos),
        "empresas_distintas": len(filas_empresas),
        "empresas_por_rubro": dict(sorted(por_rubro.items(), key=lambda x: -x[1])),
        "top_10_por_monto": [
            {k: e[k] for k in ("razon_social", "cuit", "contratos_vigentes", "monto_total", "proximo_vencimiento", "rubros")}
            for e in filas_empresas[:10]
        ],
    }
    with open(os.path.join(SALIDA, "resumen.json"), "w", encoding="utf-8") as f:
        json.dump(resumen, f, ensure_ascii=False, indent=1)
    print(json.dumps({k: resumen[k] for k in ("contratos_que_pasan_el_filtro", "empresas_distintas")}))
    if not filas_empresas:
        print("ATENCION: ninguna empresa paso el filtro", file=sys.stderr)


if __name__ == "__main__":
    main()
