"""
Ingesta CABA - Buenos Aires Compras (BAC)

Baja el CSV anual de compras de la Ciudad (formato OCDS "aplanado",
~130 MB), se queda con los contratos de servicios u obras de 1 año o
más que siguen vigentes (vencen hoy o después) y genera:

  datos/caba_contratos.csv  -> una fila por contrato (evidencia)
  datos/caba_empresas.csv   -> una fila por empresa (CUIT), lista para la planilla
  datos/resumen.json        -> números de la corrida y columnas reales del archivo

Regla de oro del proyecto: solo entran empresas con evidencia de
trabajo continuo (contrato largo y vigente con el Estado).

Nota: el JSON anual de la Ciudad quedó congelado con datos de 2022;
el CSV anual es el que trae el año en curso.
"""

import csv
import io
import json
import os
import re
import sys
import urllib.request
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone

URL = (
    "https://cdn.buenosaires.gob.ar/datosabiertos/datasets/"
    "ministerio-de-economia-y-finanzas/buenos-aires-compras/bac_anual.csv"
)
DURACION_MINIMA_DIAS = 365
ANIOS_SOSPECHOSO = 15
CATEGORIAS = {"services": "Servicios", "works": "Obras"}
SALIDA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "datos")

RE_AWARD = re.compile(r"^awards/(\d+)/(.+)$")
RE_CONTRACT = re.compile(r"^contracts/(\d+)/(.+)$")
RE_PERSONA = re.compile(r"^(suppliers|signatories)/(\d+)/(id|name)$")
RE_PARTY = re.compile(r"^parties/(\d+)/(.+)$")
RE_CUIT = re.compile(r"(\d{2})-?(\d{8})-?(\d)")


def cuit_limpio(x):
    """Deja el CUIT solo con numeros (11 digitos), sin guiones."""
    m = RE_CUIT.search(str(x or ""))
    return "".join(m.groups()) if m else re.sub(r"\D", "", str(x or ""))

csv.field_size_limit(sys.maxsize)


def bajar(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=1500) as r:
        return r.read()


def num(x):
    try:
        return float(str(x).replace(",", "."))
    except (TypeError, ValueError):
        return 0.0


def fecha(s):
    s = (s or "").strip()
    return s[:10] if re.match(r"^\d{4}-\d{2}-\d{2}", s) else ""


def dias_entre(ini, fin):
    try:
        return (date.fromisoformat(fin) - date.fromisoformat(ini)).days
    except ValueError:
        return 0


def agrupar(fila, regex):
    """Junta columnas tipo awards/0/x, awards/1/x en una lista de dicts."""
    grupos = defaultdict(dict)
    for col, val in fila.items():
        if not col or val in (None, ""):
            continue
        m = regex.match(col)
        if m:
            grupos[int(m.group(1))][m.group(2)] = val.strip()
    return [grupos[i] for i in sorted(grupos)]


def personas(d, tipo):
    """Saca CUIT y nombre de suppliers/N/id o signatories/N/id dentro de un award/contract."""
    p = defaultdict(dict)
    for k, v in d.items():
        m = RE_PERSONA.match(k)
        if m and m.group(1) == tipo:
            p[int(m.group(2))][m.group(3)] = v
    return [x for _, x in sorted(p.items()) if x.get("id")]


def main():
    hoy = date.today().isoformat()
    limite_sospechoso = (date.today() + timedelta(days=365 * ANIOS_SOSPECHOSO)).isoformat()

    print("Bajando", URL)
    raw = bajar(URL)
    print(f"Bajados {len(raw)/1048576:.1f} MB")
    texto = raw.decode("utf-8-sig", errors="replace")
    raw = None
    lector = csv.DictReader(io.StringIO(texto))
    columnas = lector.fieldnames or []

    tenders = {}          # clave de proceso -> datos del llamado
    contactos = {}        # CUIT -> datos de contacto publicados por la Ciudad
    muestra_parties = []  # diagnostico: como vienen las partes en el archivo
    campos_parties = defaultdict(int)
    evidencias = []       # contratos/adjudicaciones candidatos
    filas = 0
    por_tag = defaultdict(int)
    anios = defaultdict(int)

    for fila in lector:
        filas += 1
        ocid = (fila.get("ocid") or "").strip()
        tid = (fila.get("tender/id") or "").strip()
        por_tag[(fila.get("tag") or "").strip()] += 1
        anios[fecha(fila.get("date"))[:4] or "sin fecha"] += 1

        if fila.get("tender/mainProcurementCategory"):
            info = {
                "categoria": fila.get("tender/mainProcurementCategory", "").strip(),
                "rubro": (fila.get("tender/additionalProcurementCategories") or "").strip().strip("[]'\" "),
                "organismo": (fila.get("tender/procuringEntity/name") or "").strip(),
                "procedimiento": (fila.get("tender/procurementMethodDetails") or "").strip(),
                "titulo": (fila.get("tender/title") or "").strip(),
            }
            for k in (ocid, tid):
                if k:
                    tenders.setdefault(k, info)

        for pa in agrupar(fila, RE_PARTY):
            for k in pa:
                campos_parties[k] += 1
            if len(muestra_parties) < 8 and pa not in muestra_parties:
                muestra_parties.append(pa)
            cuit = cuit_limpio(pa.get("identifier/id") or pa.get("id"))
            if len(cuit) != 11:
                continue
            c = contactos.setdefault(cuit, {})
            for campo, col in (("contacto_nombre", "contactPoint/name"), ("email", "contactPoint/email"),
                               ("telefono", "contactPoint/telephone"), ("web", "contactPoint/url"),
                               ("direccion", "address/streetAddress"), ("localidad", "address/locality"),
                               ("codigo_postal", "address/postalCode")):
                if pa.get(col) and not c.get(campo):
                    c[campo] = pa[col]

        for aw in agrupar(fila, RE_AWARD):
            ini = fecha(aw.get("contractPeriod/startDate"))
            fin = fecha(aw.get("contractPeriod/endDate"))
            dias = int(num(aw.get("contractPeriod/durationInDays"))) or dias_entre(ini, fin)
            for s in personas(aw, "suppliers"):
                evidencias.append({
                    "claves": (ocid, tid, aw.get("id", "")),
                    "id": aw.get("id", ""), "origen": "adjudicacion",
                    "cuit": cuit_limpio(s["id"]), "razon_social": s.get("name", ""),
                    "objeto": aw.get("title", "") or aw.get("description", ""),
                    "fecha": fecha(aw.get("date")), "inicio": ini, "vencimiento": fin,
                    "dias": dias, "monto": num(aw.get("value/amount")),
                    "moneda": aw.get("value/currency", "ARS"),
                    "link": aw.get("documents/0/url", ""), "ocid": ocid,
                })

        for ct in agrupar(fila, RE_CONTRACT):
            ini = fecha(ct.get("period/startDate"))
            fin = fecha(ct.get("period/endDate"))
            dias = int(num(ct.get("period/durationInDays"))) or dias_entre(ini, fin)
            for s in personas(ct, "signatories"):
                evidencias.append({
                    "claves": (ocid, tid, ct.get("awardID", "")),
                    "id": ct.get("awardID", "") or ct.get("id", ""), "origen": "contrato",
                    "cuit": cuit_limpio(s["id"]), "razon_social": s.get("name", ""),
                    "objeto": ct.get("title", "") or ct.get("description", ""),
                    "fecha": fecha(ct.get("dateSigned")), "inicio": ini, "vencimiento": fin,
                    "dias": dias, "monto": num(ct.get("value/amount")),
                    "moneda": ct.get("value/currency", "ARS"),
                    "link": "", "ocid": ocid,
                })
    texto = None

    contratos = []
    vistos = set()
    sin_categoria = 0
    descartes = defaultdict(int)
    for ev in evidencias:
        info = None
        for k in ev["claves"]:
            if k and k in tenders:
                info = tenders[k]
                break
        cat = (info or {}).get("categoria", "")
        if not info:
            sin_categoria += 1
        if cat and cat not in CATEGORIAS:
            descartes["bienes u otra categoria"] += 1
            continue
        if ev["dias"] < DURACION_MINIMA_DIAS:
            descartes["plazo menor a 1 anio"] += 1
            continue
        if not ev["vencimiento"] or ev["vencimiento"] < hoy:
            descartes["vencido o sin vencimiento"] += 1
            continue
        clave = (ev["ocid"], ev["id"], ev["cuit"])
        if clave in vistos:
            continue
        vistos.add(clave)
        contratos.append({
            "cuit": ev["cuit"],
            "razon_social": ev["razon_social"],
            "categoria": CATEGORIAS.get(cat, "Sin dato"),
            "rubro": (info or {}).get("rubro", ""),
            "objeto": ev["objeto"] or (info or {}).get("titulo", ""),
            "organismo": (info or {}).get("organismo", ""),
            "procedimiento": (info or {}).get("procedimiento", ""),
            "fecha_adjudicacion": ev["fecha"],
            "inicio": ev["inicio"],
            "vencimiento": ev["vencimiento"],
            "duracion_dias": ev["dias"],
            "monto": round(ev["monto"], 2),
            "moneda": ev["moneda"],
            "revisar": "si" if ev["vencimiento"] > limite_sospechoso else "",
            "origen": ev["origen"],
            "proceso": ev["ocid"],
            "link_fuente": ev["link"],
        })
    contratos.sort(key=lambda c: (c["vencimiento"], c["cuit"]))

    empresas = {}
    for c in contratos:
        e = empresas.setdefault(c["cuit"], {
            "cuit": c["cuit"], "razon_social": c["razon_social"],
            "contratos_vigentes": 0, "monto_total": 0.0,
            "proximo_vencimiento": c["vencimiento"], "ultimo_vencimiento": c["vencimiento"],
            "rubros": set(), "organismos": set(), "objetos": set(),
            "ejemplo_objeto": c["objeto"], "link_fuente": c["link_fuente"],
            "contacto_nombre": "", "email": "", "telefono": "", "web": "",
            "direccion": "", "localidad": "", "codigo_postal": "",
            "revisar": "", "fuente": "CABA - Buenos Aires Compras",
            "estado": "detectada", "fecha_alta": hoy,
        })
        e["contratos_vigentes"] += 1
        e["monto_total"] += c["monto"]
        e["proximo_vencimiento"] = min(e["proximo_vencimiento"], c["vencimiento"])
        e["ultimo_vencimiento"] = max(e["ultimo_vencimiento"], c["vencimiento"])
        if c["rubro"]:
            e["rubros"].add(c["rubro"])
        if c["organismo"]:
            e["organismos"].add(c["organismo"])
        if c["objeto"]:
            e["objetos"].add(c["objeto"].strip())
        if c["revisar"]:
            e["revisar"] = "si"
        if not e["link_fuente"] and c["link_fuente"]:
            e["link_fuente"] = c["link_fuente"]

    filas_empresas = []
    for e in empresas.values():
        e["rubros"] = " | ".join(sorted(e["rubros"]))
        e["organismos"] = " | ".join(sorted(e["organismos"]))
        e["objetos"] = " || ".join(sorted(e["objetos"]))[:4000]
        e["monto_total"] = round(e["monto_total"], 2)
        for k, v in contactos.get(e["cuit"], {}).items():
            e[k] = v
        filas_empresas.append(e)
    filas_empresas.sort(key=lambda e: -e["monto_total"])

    os.makedirs(SALIDA, exist_ok=True)
    for nombre, datos in (("caba_contratos.csv", contratos), ("caba_empresas.csv", filas_empresas)):
        with open(os.path.join(SALIDA, nombre), "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(datos[0].keys()) if datos else ["cuit"])
            w.writeheader()
            w.writerows(datos)

    por_rubro = defaultdict(int)
    for e in filas_empresas:
        for r in (e["rubros"] or "Sin rubro").split(" | "):
            por_rubro[r] += 1

    resumen = {
        "corrida": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "fuente": URL,
        "filas_en_archivo": filas,
        "filas_por_etapa": dict(por_tag),
        "filas_por_anio": dict(sorted(anios.items())),
        "procesos_con_datos_de_llamado": len(tenders),
        "adjudicaciones_y_contratos_leidos": len(evidencias),
        "sin_datos_de_llamado": sin_categoria,
        "descartados": dict(descartes),
        "filtro": f"servicios u obras, {DURACION_MINIMA_DIAS} dias o mas, vigente al {hoy}",
        "contratos_que_pasan_el_filtro": len(contratos),
        "empresas_distintas": len(filas_empresas),
        "empresas_con_email": sum(1 for e in filas_empresas if e["email"]),
        "empresas_con_telefono": sum(1 for e in filas_empresas if e["telefono"]),
        "empresas_a_revisar_por_vencimiento_muy_largo": sum(1 for e in filas_empresas if e["revisar"]),
        "empresas_por_rubro": dict(sorted(por_rubro.items(), key=lambda x: -x[1])),
        "top_15_por_monto": [
            {k: e[k] for k in ("razon_social", "cuit", "contratos_vigentes", "monto_total",
                               "proximo_vencimiento", "rubros", "localidad",
                               "email", "telefono")}
            for e in filas_empresas[:15]
        ],
        "parties_campos_con_dato": dict(campos_parties),
        "parties_muestra": muestra_parties,
        "columnas_del_archivo": [c for c in columnas if not re.search(r"/items/[1-9]", c or "")][:300],
    }
    with open(os.path.join(SALIDA, "resumen.json"), "w", encoding="utf-8") as f:
        json.dump(resumen, f, ensure_ascii=False, indent=1)
    print(json.dumps({k: resumen[k] for k in (
        "filas_en_archivo", "adjudicaciones_y_contratos_leidos",
        "contratos_que_pasan_el_filtro", "empresas_distintas")}))
    if not filas_empresas:
        print("ATENCION: ninguna empresa paso el filtro", file=sys.stderr)


if __name__ == "__main__":
    main()
