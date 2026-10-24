"""
Plantillas HTML de los mails de prospeccion (identidad PCP: azul #1F3B57, naranja #C46A2D).

Dos modelos:
  A: su contrato le exige seguros (pliego de la Ciudad como respaldo)
  B: le vende bienes al Estado (coberturas del Banco de Coberturas de PCP)

El logo va como imagen embebida (cid / adjunto inline). El boton principal abre un mail de
respuesta a admin@pcpasesoresdeseguros.ar con el asunto ya cargado.
"""

import html
import urllib.parse

AZUL = "#1F3B57"
NARANJA = "#C46A2D"
GRIS = "#5B6670"
FONDO = "#F4F6F8"
MAIL_PCP = "admin@pcpasesoresdeseguros.ar"
WEB = "https://pcpasesoresdeseguros.ar/"


def e(t):
    return html.escape(str(t or ""), quote=True)


def mailto(asunto):
    return f"mailto:{MAIL_PCP}?subject={urllib.parse.quote(asunto)}"


def _base(preheader, titulo, cuerpo_html, cta_texto, cta_asunto, razon, logo_src):
    baja = mailto(f"BAJA - {razon}")
    return f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(titulo)}</title></head>
<body style="margin:0;padding:0;background:{FONDO};">
<div style="display:none;max-height:0;overflow:hidden;opacity:0;">{e(preheader)}</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{FONDO};">
<tr><td align="center" style="padding:24px 12px;">
<table role="presentation" width="600" cellpadding="0" cellspacing="0" style="width:100%;max-width:600px;background:#ffffff;border-radius:10px;overflow:hidden;font-family:Arial,Helvetica,sans-serif;">
  <tr><td style="background:{AZUL};padding:20px 28px;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>
      <td width="58" style="vertical-align:middle;"><img src="{logo_src}" alt="PCP" width="44" height="58" style="display:block;width:44px;height:58px;border:0;border-radius:6px;"></td>
      <td style="vertical-align:middle;padding-left:12px;color:#ffffff;font-size:18px;line-height:22px;font-weight:bold;">PCP Asesores de Seguros<br><span style="font-size:12px;font-weight:normal;color:#D6DEE6;">Tu seguro de confianza, con asesoramiento real</span></td>
    </tr></table>
  </td></tr>
  <tr><td style="height:4px;background:{NARANJA};font-size:0;line-height:0;">&nbsp;</td></tr>
  <tr><td style="padding:28px 28px 8px 28px;color:#1d2731;font-size:15px;line-height:23px;">
    <p style="margin:0 0 6px 0;font-size:20px;line-height:26px;color:{AZUL};font-weight:bold;">{e(titulo)}</p>
    {cuerpo_html}
  </td></tr>
  <tr><td align="center" style="padding:8px 28px 26px 28px;">
    <table role="presentation" cellpadding="0" cellspacing="0"><tr>
      <td style="background:{NARANJA};border-radius:6px;">
        <a href="{mailto(cta_asunto)}" style="display:inline-block;padding:14px 26px;color:#ffffff;font-size:15px;font-weight:bold;text-decoration:none;font-family:Arial,Helvetica,sans-serif;">{e(cta_texto)}</a>
      </td></tr></table>
    <p style="margin:12px 0 0 0;font-size:13px;color:{GRIS};">O respondan este mail, o escriban por WhatsApp al 11 2307-8263.</p>
  </td></tr>
  <tr><td style="padding:18px 28px;border-top:1px solid #E3E7EB;color:{GRIS};font-size:13px;line-height:19px;">
    <strong style="color:{AZUL};">Leandro Ezequiel Vázquez</strong><br>
    Productor Asesor de Seguros · Matrícula SSN N° 94.236<br>
    PCP Asesores de Seguros · Mitre 3723, Of. 3, Gral. San Martín<br>
    <a href="{WEB}" style="color:{NARANJA};text-decoration:none;">pcpasesoresdeseguros.ar</a> · {MAIL_PCP} · 11 2307-8263
  </td></tr>
  <tr><td style="padding:12px 28px 20px 28px;background:{FONDO};color:#8A949C;font-size:11px;line-height:16px;">
    Les escribimos porque {e(razon)} figura como proveedora de la Ciudad de Buenos Aires en los datos públicos de Buenos Aires Compras.
    Si no desean recibir más mensajes, <a href="{baja}" style="color:#8A949C;">respondan BAJA</a> y no volveremos a escribirles.
  </td></tr>
</table>
</td></tr></table>
</body></html>"""


def _intro():
    return (f'<p style="margin:14px 0;">Hola, ¿cómo están?</p>'
            f'<p style="margin:0 0 14px 0;">Soy Leandro Vázquez, productor asesor de seguros (matrícula SSN 94.236), '
            f'de PCP Asesores de Seguros.</p>')


def _cierre_reenvio():
    return ('<p style="margin:0 0 14px 0;">Si los seguros los maneja otra persona, ¿me ayudan a hacerle llegar este mail?</p>')


def modelo_a(d, logo_src):
    """d: razon, organismo, objeto, vencimiento (DD/MM/AAAA), tipo, seguros (lista), extra_requisitos"""
    items = "".join(f'<li style="margin:0 0 6px 0;">{e(s)}</li>' for s in d["seguros"])
    cuerpo = (
        _intro()
        + f'<p style="margin:0 0 14px 0;">Vi que <strong>{e(d["razon"])}</strong> tiene vigente el contrato de '
          f'<em>{e(d["objeto"])}</em> con <strong>{e(d["organismo"])}</strong>, hasta el <strong>{e(d["vencimiento"])}</strong>.</p>'
        + f'<p style="margin:0 0 8px 0;">En los pliegos de la Ciudad para {e(d["tipo"])} se exige mantener durante todo el contrato:</p>'
        + f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:0 0 16px 0;"><tr>'
          f'<td style="background:#FBF3EC;border-left:4px solid {NARANJA};padding:12px 16px;border-radius:4px;">'
          f'<ul style="margin:0;padding-left:18px;color:#1d2731;">{items}</ul></td></tr></table>'
        + f'<p style="margin:0 0 14px 0;">{e(d["extra_requisitos"])}</p>'
        + '<p style="margin:0 0 14px 0;">Les propongo una <strong>revisión sin cargo</strong>: comparamos sus pólizas actuales '
          'con lo que pide el pliego y, si para la próxima renovación hay una opción que cumpla igual y les convenga más, se la presento.</p>'
        + _cierre_reenvio()
    )
    asunto = f'Las pólizas de su contrato con {d["organismo"]}'
    htmlb = _base(f'Revisión sin cargo de las pólizas que exige su contrato con {d["organismo"]}.',
                  "Las pólizas que exige su contrato", cuerpo, "Quiero la revisión sin cargo",
                  f'Revisión de pólizas - {d["razon"]}', d["razon"], logo_src)
    return asunto, htmlb


def modelo_b(d, logo_src):
    """d: razon, organismo, objeto, coberturas: lista de (nombre, descripcion, ojo_opcional)"""
    bloques = ""
    for nombre, desc, ojo in d["coberturas"]:
        ojo_html = (f'<br><span style="color:{NARANJA};font-weight:bold;">Ojo:</span> {e(ojo)}' if ojo else "")
        bloques += (f'<tr><td style="background:#F1F4F7;border-left:4px solid {AZUL};padding:12px 16px;border-radius:4px;">'
                    f'<strong style="color:{AZUL};">{e(nombre)}</strong><br>{e(desc)}{ojo_html}</td></tr>'
                    f'<tr><td style="height:10px;font-size:0;line-height:0;">&nbsp;</td></tr>')
    cuerpo = (
        _intro()
        + f'<p style="margin:0 0 14px 0;">Vi que <strong>{e(d["razon"])}</strong> provee <em>{e(d["objeto"])}</em> a '
          f'<strong>{e(d["organismo"])}</strong>. Cuando una empresa abastece al Estado de forma continua, hay riesgos que el '
          f'contrato no pide cubrir pero que afectan directo al negocio. Por ejemplo:</p>'
        + f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:0 0 6px 0;">{bloques}</table>'
        + '<p style="margin:0 0 14px 0;">Si les sirve, reviso <strong>sin cargo</strong> cómo están cubiertos hoy y les digo '
          'si hay algo que conviene ajustar.</p>'
        + _cierre_reenvio()
    )
    asunto = f'{d["razon"]}: lo que su contrato con la Ciudad no cubre'
    htmlb = _base(f'Riesgos que su contrato con {d["organismo"]} no cubre, y cómo resolverlos.',
                  "Lo que su contrato no cubre", cuerpo, "Quiero que lo revisemos",
                  f'Revisión de coberturas - {d["razon"]}', d["razon"], logo_src)
    return asunto, htmlb
