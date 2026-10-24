"""
Enriquecimiento de contactos

Para cada empresa de datos/caba_empresas.csv que todavia no fue buscada:
  1. Busca su web oficial con Tavily (razon social + Argentina).
  2. Entra a la web y a sus paginas de contacto y extrae mails y telefonos.
     Si la web no deja leerse, usa la lectura de paginas de Tavily.
  3. Guarda el resultado en datos/contactos.csv (una fila por CUIT).

Cada empresa se busca una sola vez: las corridas siguientes solo
procesan CUIT nuevos. Para volver a buscar una, borrar su fila del CSV.

Uso:  TAVILY_API_KEY=... python prospeccion/enriquecer.py --limite 10
"""

import argparse
import csv
import html
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import date

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATOS = os.path.join(RAIZ, "datos")
ENTRADA = os.path.join(DATOS, "caba_empresas.csv")
SALIDA = os.path.join(DATOS, "contactos.csv")
RESUMEN = os.path.join(DATOS, "resumen_enriquecimiento.json")

CAMPOS = ["cuit", "razon_social", "web", "email", "telefono", "otros_emails",
          "otros_telefonos", "confianza_web", "como_se_leyo", "fecha_busqueda"]

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

# Sitios que nunca son la web oficial de una empresa
NO_OFICIALES = (
    "linkedin.", "facebook.", "instagram.", "twitter.", "x.com", "youtube.", "tiktok.",
    "wikipedia.", "gob.ar", "gov.ar", "boletinoficial", "cuitonline", "dateas", "cuit.",
    "paginasamarillas", "guiaempresas", "empresite", "cylex", "infoisinfo", "opencorporates",
    "mercadolibre", "computrabajo", "bumeran", "zonajobs", "glassdoor", "indeed", "bnamericas",
    "dnb.com", "emis.com", "infobae", "clarin", "lanacion", "pagina12", "perfil.com",
    "ambito", "iprofesional", "buenosairescompras", "argentina.gob", "afip", "arca.gob",
    "google.", "waze.", "tripadvisor", "yelp", "kompass", "cronista", "telam", "foursquare",
    "sitioempresas", "cuitargentina", "argentinacuit", "infocuit", "tusfacturas", "nosis",
    "veraz", "infocif", "datoscuit", "cuitarg", "guiatelefonica", "rubros.com",
)

PALABRAS_SOCIETARIAS = {
    "sa", "s", "a", "srl", "sas", "sociedad", "anonima", "responsabilidad", "limitada", "de",
    "del", "la", "las", "los", "el", "y", "e", "cia", "compania", "comercial", "industrial",
    "saic", "saci", "sacif", "sacifi", "sca", "ute", "ut", "union", "transitoria", "empresas",
    "argentina", "hijos", "i", "c", "f", "sh",
}

RE_EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
RE_TEL = re.compile(
    r"(?:\+?54[\s\-.]?)?(?:\(?0?\d{2,4}\)?[\s\-.]?)?(?:15[\s\-.]?)?\d{3,4}[\s\-.]?\d{4}")
RE_LINK = re.compile(r"""href=["']([^"'#]+)["']""", re.I)


def sin_acentos(s):
    tabla = str.maketrans("áéíóúüñÁÉÍÓÚÜÑ", "aeiouunAEIOUUN")
    return s.translate(tabla)


def palabras_clave(razon):
    t = re.sub(r"[^a-z0-9 ]", " ", sin_acentos(razon.lower()))
    return [p for p in t.split() if p not in PALABRAS_SOCIETARIAS and len(p) >= 3]


def nombre_para_buscar(razon):
    t = re.sub(r"\b(S\.?\s?A\.?(\s?[ICF]\.?)*|S\.?R\.?L\.?|S\.?A\.?S\.?|SOCIEDAD ANONIMA|"
               r"SOCIEDAD DE RESPONSABILIDAD LIMITADA|UNION TRANSITORIA( DE EMPRESAS)?|U\.?T\.?E?\.?)\b",
               " ", razon, flags=re.I)
    return re.sub(r"\s+", " ", t).strip(" -.,") or razon


def dominio(url):
    try:
        d = urllib.parse.urlparse(url).netloc.lower()
    except ValueError:
        return ""
    return d[4:] if d.startswith("www.") else d


def es_oficial_posible(url):
    d = dominio(url)
    return bool(d) and not any(x in d for x in NO_OFICIALES)


def confianza(url, claves):
    d = re.sub(r"[^a-z0-9]", "", dominio(url).split(".")[0])
    if not claves:
        return "baja"
    pegadas = "".join(claves)
    if any(c in d for c in claves if len(c) >= 4) or (pegadas and pegadas[:8] in d):
        return "alta"
    if any(c[:4] in d for c in claves if len(c) >= 4):
        return "media"
    return "baja"


class Tavily:
    def __init__(self, clave):
        self.clave = clave
        self.creditos = 0

    def _post(self, ruta, cuerpo):
        req = urllib.request.Request(
            "https://api.tavily.com/" + ruta,
            data=json.dumps(cuerpo).encode(),
            headers={"Content-Type": "application/json", "Authorization": "Bearer " + self.clave},
        )
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())

    def buscar(self, consulta):
        self.creditos += 1
        return self._post("search", {
            "query": consulta, "search_depth": "basic", "max_results": 8,
            "topic": "general", "country": "argentina", "include_answer": False,
        }).get("results", [])

    def leer(self, urls):
        self.creditos += max(1, (len(urls) + 4) // 5)
        res = self._post("extract", {"urls": urls, "extract_depth": "basic"})
        return [r.get("raw_content") or "" for r in res.get("results", [])]


def bajar_pagina(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "es-AR,es"})
    with urllib.request.urlopen(req, timeout=20) as r:
        tipo = r.headers.get("Content-Type", "")
        if "html" not in tipo and "text" not in tipo:
            return ""
        return r.read(2_000_000).decode("utf-8", errors="replace")


def links_de_contacto(base, pagina):
    vistos = []
    for href in RE_LINK.findall(pagina):
        h = html.unescape(href).strip()
        if h.lower().startswith(("mailto:", "tel:", "javascript:")):
            continue
        if re.search(r"contact|nosotros|empresa|quienes|about|ubicaci", h, re.I):
            u = urllib.parse.urljoin(base, h)
            if dominio(u) == dominio(base) and u not in vistos:
                vistos.append(u)
    return vistos[:3]


def emails_de(texto, dom):
    texto = html.unescape(texto)
    mails = set(m.lower().strip(".") for m in RE_EMAIL.findall(texto))
    for m in re.findall(r"mailto:([^\"'?>\s]+)", texto, re.I):
        mails.add(urllib.parse.unquote(m).lower().strip("."))
    buenos = []
    for m in mails:
        if re.search(r"\.(png|jpe?g|gif|svg|webp|css|js)$", m):
            continue
        if any(x in m for x in ("example.", "sentry", "wixpress", "noreply", "no-reply",
                                "domain.", "email.com", "tuempresa", "sudominio", "@2x")):
            continue
        buenos.append(m)
    propios = [m for m in buenos if dom and m.split("@")[1].endswith(dom)]
    otros = [m for m in buenos if m not in propios]
    orden = lambda m: (0 if re.match(r"(info|contacto|ventas|comercial|administracion|admin)@", m) else 1, m)
    return sorted(propios, key=orden) + sorted(otros, key=orden)


def tel_valido(t):
    d = re.sub(r"\D", "", t or "")
    if len(d) < 8 or len(d) > 13:
        return False
    if len(d) == 8 and re.fullmatch(r"(19|20)\d{6}", d):
        return False  # parece una fecha
    if len(d) == 11 and d[0] in "23":
        return False  # parece un CUIT
    if len(set(d)) <= 2 or re.search(r"0{4,}", d) or d.startswith("00"):
        return False  # relleno tipo 00000057
    if any(x in d for x in ("1234567", "2345678", "3456789", "9876543")):
        return False  # relleno tipo 1234567890
    return True


def telefonos_de(texto):
    texto = html.unescape(texto)
    cand = [urllib.parse.unquote(t) for t in re.findall(r"tel:([^\"'>\s]+)", texto, re.I)]
    sin_tags = re.sub(r"<[^>]+>", " ", texto)
    sin_tags = re.sub(r"\b\d{2}-\d{8}-\d\b", " ", sin_tags)  # saca CUITs
    cand += RE_TEL.findall(sin_tags)
    vistos, salida = set(), []
    for t in cand:
        d = re.sub(r"\D", "", t)
        if not tel_valido(t):
            continue
        clave = d[-8:]
        if clave in vistos:
            continue
        vistos.add(clave)
        salida.append(re.sub(r"\s+", " ", t.strip()))
    return salida


def procesar(empresa, tav):
    razon = empresa["razon_social"]
    claves = palabras_clave(razon)
    fila = {k: "" for k in CAMPOS}
    fila.update(cuit=empresa["cuit"], razon_social=razon, fecha_busqueda=date.today().isoformat())

    resultados = tav.buscar(f'"{nombre_para_buscar(razon)}" empresa Argentina contacto')
    candidatas = [r for r in resultados if es_oficial_posible(r.get("url", ""))]
    if not candidatas:
        fila["como_se_leyo"] = "sin web encontrada"
        return fila
    orden = {"alta": 0, "media": 1, "baja": 2}
    candidatas.sort(key=lambda r: orden[confianza(r["url"], claves)])
    elegida = candidatas[0]["url"]
    nivel = confianza(elegida, claves)
    p = urllib.parse.urlparse(elegida)
    home = f"{p.scheme or 'https'}://{p.netloc}/"
    fila["web"] = home
    fila["confianza_web"] = nivel
    dom = dominio(home)

    textos, como = [], []
    try:
        portada = bajar_pagina(home)
        textos.append(portada)
        for u in links_de_contacto(home, portada):
            try:
                textos.append(bajar_pagina(u))
            except Exception:
                pass
        como.append("web directa")
    except Exception:
        pass
    if not textos or not emails_de(" ".join(textos), dom):
        try:
            urls = [home, urllib.parse.urljoin(home, "contacto"), urllib.parse.urljoin(home, "contact")]
            textos += tav.leer(urls)
            como.append("lectura Tavily")
        except Exception:
            pass
    textos.append(" ".join(r.get("content", "") for r in resultados if dominio(r.get("url", "")) == dom))

    junto = "\n".join(textos)
    mails = emails_de(junto, dom)
    tels = telefonos_de(junto)
    fila["email"] = mails[0] if mails else ""
    fila["otros_emails"] = " | ".join(mails[1:4])
    fila["telefono"] = tels[0] if tels else ""
    fila["otros_telefonos"] = " | ".join(tels[1:3])
    fila["como_se_leyo"] = " + ".join(como) or "no se pudo leer la web"
    return fila


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limite", type=int, default=0, help="maximo de empresas a buscar (0 = todas)")
    args = ap.parse_args()

    clave = os.environ.get("TAVILY_API_KEY", "").strip()
    if not clave:
        sys.exit("Falta el secreto TAVILY_API_KEY")
    tav = Tavily(clave)

    hechas = {}
    if os.path.exists(SALIDA):
        with open(SALIDA, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                tels = [t for t in [r.get("telefono", "")] + (r.get("otros_telefonos") or "").split(" | ") if tel_valido(t)]
                r["telefono"] = tels[0] if tels else ""
                r["otros_telefonos"] = " | ".join(tels[1:3])
                hechas[r["cuit"]] = r
    with open(ENTRADA, encoding="utf-8") as f:
        empresas = [e for e in csv.DictReader(f) if e["cuit"] not in hechas]
    if args.limite:
        empresas = empresas[: args.limite]
    print(f"Ya buscadas: {len(hechas)}. A buscar ahora: {len(empresas)}")

    nuevas = []
    for i, e in enumerate(empresas, 1):
        try:
            fila = procesar(e, tav)
        except Exception as ex:
            print(f"  error con {e['razon_social']}: {ex!r}")
            if "401" in repr(ex) or "403" in repr(ex) or "432" in repr(ex):
                print("La clave de Tavily fue rechazada o se agotaron los creditos. Corto aca.")
                break
            continue
        nuevas.append(fila)
        hechas[fila["cuit"]] = fila
        print(f"{i:>3}. {e['razon_social'][:45]:<45} {fila['web'] or '-':<35} "
              f"{fila['email'] or '-':<30} {fila['telefono'] or '-'}")
        time.sleep(0.5)

    os.makedirs(DATOS, exist_ok=True)
    with open(SALIDA, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS)
        w.writeheader()
        w.writerows(sorted(hechas.values(), key=lambda r: r["cuit"]))

    resumen = {
        "fecha": date.today().isoformat(),
        "buscadas_en_esta_corrida": len(nuevas),
        "con_web": sum(1 for r in nuevas if r["web"]),
        "web_confianza_alta": sum(1 for r in nuevas if r["confianza_web"] == "alta"),
        "con_email": sum(1 for r in nuevas if r["email"]),
        "con_telefono": sum(1 for r in nuevas if r["telefono"]),
        "creditos_tavily_usados": tav.creditos,
        "total_en_base": len(hechas),
        "detalle": [{k: r[k] for k in ("razon_social", "web", "confianza_web", "email", "telefono", "como_se_leyo")}
                    for r in nuevas[:30]],
    }
    with open(RESUMEN, "w", encoding="utf-8") as f:
        json.dump(resumen, f, ensure_ascii=False, indent=1)
    print(json.dumps({k: v for k, v in resumen.items() if k != "detalle"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
