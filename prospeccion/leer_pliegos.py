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
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.read()


def texto_pdf(datos):
    lector = PdfReader(io.BytesIO(datos))
    return "\n".join((p.extract_text() or "") for p in lector.pages)


def articulos(texto):
    marcas = [m.start() for m in RE_ARTICULO.finditer(texto)] + [len(texto)]
    for a, b in zip(marcas, marcas[1:]):
        yield texto[a:b].strip()


def secciones_seguro(texto):
    """Busca encabezados SEGUROS en el texto normalizado y devuelve los tramos con mas contenido."""
    plano = re.sub(r"\s+", " ", texto)
    tramos = []
    for m in re.finditer(r"SEGUROS|Seguros\.", plano):
        ini = max(0, m.start() - 120)
        fin_busca = re.search(r"(ART[ÍI]CULO|Art[íi]culo)\s*(N[°º.]?\s*)?\d+", plano[m.end() + 300:])
        fin = m.end() + 300 + (fin_busca.start() if fin_busca else 12000)
        fin = min(fin, m.end() + 16000)
        tramo = plano[ini:fin]
        peso = len(re.findall(r"p[óo]liza|asegurad|ART\b|responsabilidad civil|accidentes", tramo, re.I))
        if peso >= 3:
            tramos.append((peso, ini, tramo))
    tramos.sort(reverse=True)
    elegidos = []
    for peso, ini, tramo in tramos:
        if all(abs(ini - e[0]) > 1500 for e in elegidos):
            elegidos.append((ini, tramo))
        if len(elegidos) == 2:
            break
    return [t for _, t in sorted(elegidos)]


def objeto(texto):
    plano = re.sub(r"\s+", " ", texto)
    candidatos = [plano[m.end():m.end() + 450] for m in re.finditer(r"OBJETO", plano, re.I)]
    candidatos = [c for c in candidatos if not re.search(r"\d\s+(Art[íi]culo|ART[ÍI]CULO)", c[:200])]
    return candidatos[0].strip() if candidatos else ""


def main():
    os.makedirs(CARPETA, exist_ok=True)
    with open(os.path.join(DATOS, "pliegos_fuente.csv"), encoding="utf-8") as f:
        fuentes = list(csv.DictReader(f))

    resumen = []
    for fu in fuentes:
        base = fu["base"].strip()
        docs = []
        fallos_seguidos = 0
        for suf in SUFIJOS:
            if fallos_seguidos >= 2 and suf != "ANX-1":
                break  # no hay mas anexos
            nombre = f"{base}-{suf}"
            try:
                datos = bajar(URL.format(nombre))
                fallos_seguidos = 0
            except Exception:
                fallos_seguidos += 1
                continue
            try:
                txt = texto_pdf(datos)
            except Exception as e:
                docs.append({"documento": nombre, "error": repr(e)[:150]})
                continue
            arts_seguro = secciones_seguro(txt)
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
        print(base, "->", resumen[-1]["documentos_encontrados"], "| seguros en:", resumen[-1]["con_articulo_de_seguros"], flush=True)

    with open(os.path.join(DATOS, "pliegos_resumen.json"), "w", encoding="utf-8") as f:
        json.dump(resumen, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
