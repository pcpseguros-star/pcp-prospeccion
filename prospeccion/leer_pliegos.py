"""
Lector de pliegos

Baja pliegos en PDF publicados en el Boletin Oficial de la Ciudad, extrae
el texto completo y guarda, para cada uno:
  - el objeto de la contratacion
  - el articulo de seguros completo (y los parrafos que mencionan seguros)

Entrada:  datos/pliegos_fuente.csv  (columnas: base, nota)
          'base' es el nombre del documento sin el sufijo de anexo
          (ej. PE-RES-MSGC-SSASS-550-26); se prueban ANX, ANX-1 ... ANX-9.
Salida:   datos/pliegos/<base>.txt   y   datos/pliegos_resumen.json
"""

import csv
import io
import json
import os
import re
import urllib.request

from pypdf import PdfReader

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATOS = os.path.join(RAIZ, "datos")
CARPETA = os.path.join(DATOS, "pliegos")
URL = "https://documentosboletinoficial.buenosaires.gob.ar/publico/{}.pdf"
SUFIJOS = ["ANX"] + [f"ANX-{i}" for i in range(1, 10)]

RE_ARTICULO = re.compile(r"\n\s*(ART[ÍI]CULO|Art[íi]culo)\s*(N[°º.]?\s*)?\d+[^\n]{0,80}", re.M)
RE_SEGURO_TITULO = re.compile(r"SEGURO", re.I)
PALABRAS = re.compile(r"seguro|p[óo]liza|riesgos del trabajo|\bART\b|responsabilidad civil|"
                      r"accidentes personales|co-?asegurad|asegurador", re.I)


def bajar(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def texto_pdf(datos):
    lector = PdfReader(io.BytesIO(datos))
    return "\n".join((p.extract_text() or "") for p in lector.pages)


def articulos(texto):
    marcas = [m.start() for m in RE_ARTICULO.finditer(texto)] + [len(texto)]
    for a, b in zip(marcas, marcas[1:]):
        yield texto[a:b].strip()


def objeto(texto):
    m = re.search(r"OBJETO[^\n]*\n(.{0,700})", texto, re.I | re.S)
    return re.sub(r"\s+", " ", m.group(1)).strip()[:500] if m else ""


def main():
    os.makedirs(CARPETA, exist_ok=True)
    with open(os.path.join(DATOS, "pliegos_fuente.csv"), encoding="utf-8") as f:
        fuentes = list(csv.DictReader(f))

    resumen = []
    for fu in fuentes:
        base = fu["base"].strip()
        docs = []
        for suf in SUFIJOS:
            nombre = f"{base}-{suf}"
            try:
                datos = bajar(URL.format(nombre))
            except Exception:
                continue
            try:
                txt = texto_pdf(datos)
            except Exception as e:
                docs.append({"documento": nombre, "error": repr(e)[:150]})
                continue
            arts_seguro = [a for a in articulos(txt) if RE_SEGURO_TITULO.search(a.split("\n", 1)[0])]
            parrafos = [re.sub(r"\s+", " ", p).strip() for p in re.split(r"\n\s*\n|(?<=\.)\n", txt)
                        if PALABRAS.search(p)]
            docs.append({
                "documento": nombre, "url": URL.format(nombre), "paginas_texto": len(txt),
                "objeto": objeto(txt), "articulos_seguro": arts_seguro, "parrafos_seguro": parrafos[:60],
            })
        with open(os.path.join(CARPETA, base + ".txt"), "w", encoding="utf-8") as f:
            for d in docs:
                f.write(f"===== {d['documento']}  {d.get('url', '')}\n")
                if d.get("error"):
                    f.write(f"ERROR {d['error']}\n\n")
                    continue
                f.write(f"OBJETO: {d['objeto']}\n\n")
                for a in d["articulos_seguro"]:
                    f.write("--- ARTICULO DE SEGUROS ---\n" + a + "\n\n")
                if not d["articulos_seguro"]:
                    f.write("--- PARRAFOS QUE MENCIONAN SEGUROS ---\n")
                    for p in d["parrafos_seguro"]:
                        f.write("* " + p[:900] + "\n")
                f.write("\n")
        resumen.append({
            "base": base, "nota": fu.get("nota", ""),
            "documentos_encontrados": [d["documento"] for d in docs],
            "con_articulo_de_seguros": [d["documento"] for d in docs if d.get("articulos_seguro")],
        })
        print(base, "->", resumen[-1]["documentos_encontrados"], "| seguros en:", resumen[-1]["con_articulo_de_seguros"])

    with open(os.path.join(DATOS, "pliegos_resumen.json"), "w", encoding="utf-8") as f:
        json.dump(resumen, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
