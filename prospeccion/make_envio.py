# Codigo del modulo "Run code" del escenario de Make "Prospeccion - Envio de mails".
# Elige hasta {limite} empresas para contactar hoy y arma el mail HTML de cada una.
# Entradas: planilla (Empresas!A2:AF), reglas_rubro ('Reglas por rubro'!A2:B),
#           banco (Banco!D2:G del Banco de Carruseles Coberturas), modo ('borrador' o 'envio'), limite.
import json, re, html, urllib.parse
from datetime import datetime, timedelta, timezone


def lista(x):
    if x is None:
        return []
    if isinstance(x, (bytes, bytearray)):
        x = x.decode('utf-8', 'ignore')
    if isinstance(x, str):
        x = x.strip()
        if not x:
            return []
        try:
            x = json.loads(x)
        except Exception:
            return []
    if isinstance(x, dict):
        x = x.get('values') or []
    return x if isinstance(x, list) else []


def celda(fila, i):
    return str(fila[i]).strip() if len(fila) > i and fila[i] is not None else ''


def e(t):
    return html.escape(str(t or ''), quote=True)


MINUSCULAS = {'de', 'del', 'la', 'las', 'los', 'el', 'y', 'e', 'a', 'en', 'para', 'por', 'con'}
SIGLAS = {'s.a.', 's.a', 's.r.l', 'sa', 'srl', 's.r.l.', 'sas', 's.a.s.', 'ute', 'ut', 'saic', 'sacifi', 'saicfi', 'sacif', 'sh'}


def nombre_propio(t):
    t = (t or '').strip()
    if not t or t != t.upper():
        return t
    out = []
    for i, p in enumerate(t.lower().split()):
        if p in SIGLAS:
            out.append(p.upper())
        elif i > 0 and p in MINUSCULAS:
            out.append(p)
        else:
            out.append(p[:1].upper() + p[1:])
    return ' '.join(out)


def objeto_texto(t):
    t = re.sub(r'\s+', ' ', (t or '').strip()).strip(' .-')
    t = re.sub(r'^(servicio|serv\.?)\s+(de|para|del)?\s*', '', t, flags=re.I)
    if t and t == t.upper():
        t = t.lower()
    return (t[:1].lower() + t[1:]) if t else 'provisión de bienes y servicios'


def fecha_ar(iso):
    m = re.match(r'(\d{4})-(\d{2})-(\d{2})', iso or '')
    return f'{m.group(3)}/{m.group(2)}/{m.group(1)}' if m else iso


RE_MAIL = re.compile(r'^[^@\s]+@[^@\s]+\.[a-z]{2,}$', re.I)
RELLENO = re.compile(r'ejemplo|example|misitio|tudominio|sudominio|domain\.|sentry|wixpress|noreply|no-reply', re.I)

AZUL, NARANJA, GRIS, FONDO = '#1F3B57', '#C46A2D', '#5B6670', '#F4F6F8'
MAIL_PCP = 'admin@pcpasesoresdeseguros.ar'
LOGO = 'https://raw.githubusercontent.com/pcpseguros-star/pcp-prospeccion/main/marca/logo_mail.png'


def mailto(asunto):
    return f'mailto:{MAIL_PCP}?subject={urllib.parse.quote(asunto)}'


def base(preheader, titulo, cuerpo, cta_texto, cta_asunto, razon):
    return f'''<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{e(titulo)}</title></head>
<body style="margin:0;padding:0;background:{FONDO};">
<div style="display:none;max-height:0;overflow:hidden;opacity:0;">{e(preheader)}</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{FONDO};"><tr><td align="center" style="padding:24px 12px;">
<table role="presentation" width="600" cellpadding="0" cellspacing="0" style="width:100%;max-width:600px;background:#ffffff;border-radius:10px;overflow:hidden;font-family:Arial,Helvetica,sans-serif;">
<tr><td style="background:{AZUL};padding:20px 28px;"><table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>
<td width="58" style="vertical-align:middle;"><img src="{LOGO}" alt="PCP" width="44" height="58" style="display:block;width:44px;height:58px;border:0;border-radius:6px;"></td>
<td style="vertical-align:middle;padding-left:12px;color:#ffffff;font-size:18px;line-height:22px;font-weight:bold;">PCP Asesores de Seguros<br><span style="font-size:12px;font-weight:normal;color:#D6DEE6;">Tu seguro de confianza, con asesoramiento real</span></td>
</tr></table></td></tr>
<tr><td style="height:4px;background:{NARANJA};font-size:0;line-height:0;">&nbsp;</td></tr>
<tr><td style="padding:28px 28px 8px 28px;color:#1d2731;font-size:15px;line-height:23px;">
<p style="margin:0 0 6px 0;font-size:20px;line-height:26px;color:{AZUL};font-weight:bold;">{e(titulo)}</p>{cuerpo}</td></tr>
<tr><td align="center" style="padding:8px 28px 26px 28px;"><table role="presentation" cellpadding="0" cellspacing="0"><tr><td style="background:{NARANJA};border-radius:6px;">
<a href="{mailto(cta_asunto)}" style="display:inline-block;padding:14px 26px;color:#ffffff;font-size:15px;font-weight:bold;text-decoration:none;font-family:Arial,Helvetica,sans-serif;">{e(cta_texto)}</a></td></tr></table>
<p style="margin:12px 0 0 0;font-size:13px;color:{GRIS};">O respondan este mail, o escriban por WhatsApp al 11 2307-8263.</p></td></tr>
<tr><td style="padding:18px 28px;border-top:1px solid #E3E7EB;color:{GRIS};font-size:13px;line-height:19px;">
<strong style="color:{AZUL};">Leandro Ezequiel Vázquez</strong><br>Productor Asesor de Seguros · Matrícula SSN N° 94.236<br>PCP Asesores de Seguros · Mitre 3723, Of. 3, Gral. San Martín<br>
<a href="https://pcpasesoresdeseguros.ar/" style="color:{NARANJA};text-decoration:none;">pcpasesoresdeseguros.ar</a> · {MAIL_PCP} · 11 2307-8263</td></tr>
<tr><td style="padding:12px 28px 20px 28px;background:{FONDO};color:#8A949C;font-size:11px;line-height:16px;">
Les escribimos porque {e(razon)} figura como proveedora de la Ciudad de Buenos Aires en los datos públicos de Buenos Aires Compras.
Si no desean recibir más mensajes, <a href="{mailto('BAJA - ' + razon)}" style="color:#8A949C;">respondan BAJA</a> y no volveremos a escribirles.</td></tr>
</table></td></tr></table></body></html>'''


INTRO = ('<p style="margin:14px 0;">Hola, ¿cómo están?</p><p style="margin:0 0 14px 0;">Soy Leandro Vázquez, productor asesor '
         'de seguros (matrícula SSN 94.236), de PCP Asesores de Seguros.</p>')
REENVIO = '<p style="margin:0 0 14px 0;">Si los seguros los maneja otra persona, ¿me ayudan a hacerle llegar este mail?</p>'
FIRMA_TXT = ('\n\nLeandro Ezequiel Vázquez\nProductor Asesor de Seguros · Matrícula SSN N° 94.236\nPCP Asesores de Seguros · '
             f'{MAIL_PCP} · 11 2307-8263\n\nSi no desean recibir más mensajes, respondan BAJA y no volveremos a escribirles.')


def mail_a(razon, organismo, objeto, venc, tipo, seguros):
    general = tipo.lower().startswith('régimen general') or tipo.lower().startswith('regimen general')
    intro_seg = ('En los pliegos de la Ciudad, a los proveedores que trabajan dentro de sus edificios se les exige mantener durante todo el contrato:'
                 if general else
                 f'En los pliegos de la Ciudad para {tipo.lower()} se exige mantener durante todo el contrato:')
    items = ''.join(f'<li style="margin:0 0 6px 0;">{e(s)}</li>' for s in seguros)
    extra = ('Además, las pólizas deben estar vigentes durante todo el contrato, se renuevan antes de cada vencimiento y se acreditan '
             'ante el organismo, y la aseguradora debe cumplir requisitos de domicilio, calificación y solvencia. En varios pliegos, '
             'cambiar de compañía requiere autorización previa.')
    cuerpo = (INTRO
              + f'<p style="margin:0 0 14px 0;">Vi que <strong>{e(razon)}</strong> tiene vigente el contrato de <em>{e(objeto)}</em> con '
                f'<strong>{e(organismo)}</strong>, hasta el <strong>{e(venc)}</strong>.</p>'
              + f'<p style="margin:0 0 8px 0;">{e(intro_seg)}</p>'
              + f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:0 0 16px 0;"><tr><td style="background:#FBF3EC;'
                f'border-left:4px solid {NARANJA};padding:12px 16px;border-radius:4px;"><ul style="margin:0;padding-left:18px;color:#1d2731;">{items}</ul></td></tr></table>'
              + f'<p style="margin:0 0 14px 0;">{e(extra)}</p>'
              + '<p style="margin:0 0 14px 0;">Les propongo una <strong>revisión sin cargo</strong>: comparamos sus pólizas actuales con lo que pide '
                'el pliego y, si para la próxima renovación hay una opción que cumpla igual y les convenga más, se la presento.</p>' + REENVIO)
    asunto = f'Las pólizas de su contrato con {organismo}'
    texto = (f'Hola, ¿cómo están?\n\nSoy Leandro Vázquez, productor asesor de seguros (matrícula SSN 94.236), de PCP Asesores de Seguros.\n\n'
             f'Vi que {razon} tiene vigente el contrato de {objeto} con {organismo}, hasta el {venc}.\n\n{intro_seg}\n'
             + '\n'.join('- ' + s for s in seguros) + f'\n\n{extra}\n\nLes propongo una revisión sin cargo: comparamos sus pólizas actuales '
             'con lo que pide el pliego y, si para la próxima renovación hay una opción que cumpla igual y les convenga más, se la presento.\n\n'
             'Si los seguros los maneja otra persona, ¿me ayudan a hacerle llegar este mail?' + FIRMA_TXT)
    return asunto, base(f'Revisión sin cargo de las pólizas que exige su contrato con {organismo}.', 'Las pólizas que exige su contrato',
                        cuerpo, 'Quiero la revisión sin cargo', f'Revisión de pólizas - {razon}', razon), texto


def mail_b(razon, organismo, objeto, coberturas):
    bloques, txt = '', ''
    for nombre, desc, ojo in coberturas:
        ojo_html = f'<br><span style="color:{NARANJA};font-weight:bold;">Ojo:</span> {e(ojo)}' if ojo else ''
        bloques += (f'<tr><td style="background:#F1F4F7;border-left:4px solid {AZUL};padding:12px 16px;border-radius:4px;">'
                    f'<strong style="color:{AZUL};">{e(nombre)}</strong><br>{e(desc)}{ojo_html}</td></tr>'
                    '<tr><td style="height:10px;font-size:0;line-height:0;">&nbsp;</td></tr>')
        txt += f'- {nombre}: {desc}' + (f' Ojo: {ojo}' if ojo else '') + '\n'
    cuerpo = (INTRO
              + f'<p style="margin:0 0 14px 0;">Vi que <strong>{e(razon)}</strong> provee <em>{e(objeto)}</em> a <strong>{e(organismo)}</strong>. '
                'Cuando una empresa abastece al Estado de forma continua, hay riesgos que el contrato no pide cubrir pero que afectan '
                'directo al negocio. Por ejemplo:</p>'
              + f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:0 0 6px 0;">{bloques}</table>'
              + '<p style="margin:0 0 14px 0;">Si les sirve, reviso <strong>sin cargo</strong> cómo están cubiertos hoy y les digo si hay algo '
                'que conviene ajustar.</p>' + REENVIO)
    asunto = f'{razon}: lo que su contrato con la Ciudad no cubre'
    texto = (f'Hola, ¿cómo están?\n\nSoy Leandro Vázquez, productor asesor de seguros (matrícula SSN 94.236), de PCP Asesores de Seguros.\n\n'
             f'Vi que {razon} provee {objeto} a {organismo}. Cuando una empresa abastece al Estado de forma continua, hay riesgos que el '
             f'contrato no pide cubrir pero que afectan directo al negocio. Por ejemplo:\n{txt}\nSi les sirve, reviso sin cargo cómo están '
             'cubiertos hoy y les digo si hay algo que conviene ajustar.\n\nSi los seguros los maneja otra persona, ¿me ayudan a hacerle '
             'llegar este mail?' + FIRMA_TXT)
    return asunto, base(f'Riesgos que su contrato con {organismo} no cubre, y cómo resolverlos.', 'Lo que su contrato no cubre',
                        cuerpo, 'Quiero que lo revisemos', f'Revisión de coberturas - {razon}', razon), texto


# --- Coberturas para el grupo B: Reglas por rubro + Banco de Coberturas ---
EQUIVALENCIAS = {
    'transporte de mercaderías': 'Transporte de mercaderías', 'automotor y flota': 'Auto', 'automotor': 'Auto',
    'responsabilidad civil': 'Responsabilidad civil para comercios', 'art': 'ART',
    'vida colectivo': 'Vida colectivo para empleados de comercio', 'integral': 'Integral de comercio',
    'integral de comercio': 'Integral de comercio', 'integral de comercio o industria': 'Integral de comercio',
    'equipos electrónicos': 'Seguro de equipos electrónicos', 'equipos y maquinaria': 'Seguro de equipos electrónicos',
    'riesgos cibernéticos': 'Riesgos cibernéticos (Cyber)', 'accidentes personales': 'Accidentes personales',
    'responsabilidad civil para eventos': 'Responsabilidad civil para eventos', 'todo riesgo construcción': 'Obras y refacciones',
}
NOMBRE_MAIL = {'Auto': 'Automotor y flota', 'Responsabilidad civil para comercios': 'Responsabilidad civil',
               'Vida colectivo para empleados de comercio': 'Vida colectivo', 'Integral de comercio': 'Integral (instalaciones y stock)',
               'Seguro de equipos electrónicos': 'Equipos electrónicos', 'Riesgos cibernéticos (Cyber)': 'Riesgos cibernéticos'}

PREF_OJO = {'Auto': 'uso del veh', 'Integral de comercio': 'infraseguro', 'Transporte de mercaderías': 'adicionales',
            'Seguro de equipos electrónicos': 'exclusi', 'Responsabilidad civil para comercios': 'confusi'}
banco = {}
for f in lista(input.get('banco')):
    cob, ang, _, ext = (celda(f, 0), celda(f, 1), celda(f, 2), celda(f, 3))
    if not cob or not ext:
        continue
    b = banco.setdefault(cob, {'que': '', 'ojo': ''})
    if ang.lower().startswith('qué cubre') and not b['que']:
        b['que'] = ext
    elif ang.lower().startswith('ojo con'):
        pref = PREF_OJO.get(cob)
        if not b['ojo'] or (pref and pref in ang.lower() and not b.get('ojo_pref')):
            b['ojo'] = ext
            b['ojo_pref'] = bool(pref and pref in ang.lower())

reglas_rubro = {}
for f in lista(input.get('reglas_rubro')):
    if celda(f, 0):
        reglas_rubro[celda(f, 0).lower()] = [c.strip() for c in celda(f, 1).split(',') if c.strip()]


def coberturas_b(rubros):
    lista_cob = []
    for r in [x.strip().lower() for x in rubros.split('|') if x.strip()] + ['otros (sin regla propia)']:
        if r in reglas_rubro:
            lista_cob = reglas_rubro[r]
            break
    elegidas = []
    for c in lista_cob:
        if c.lower().startswith('cauci'):
            continue  # la caucion ya esta tomada al adjudicar
        clave = EQUIVALENCIAS.get(c.lower())
        if clave and clave in banco and banco[clave]['que'] and clave not in [x[3] for x in elegidas]:
            elegidas.append((NOMBRE_MAIL.get(clave, clave), banco[clave]['que'], banco[clave]['ojo'], clave))
        if len(elegidas) == 2:
            break
    return [x[:3] for x in elegidas]


# --- Seleccion de empresas ---
modo = (input.get('modo') or 'borrador').strip().lower()
limite = int(input.get('limite') or 10)
estado_nuevo = 'contactada' if modo == 'envio' else 'borrador'
hoy = datetime.now(timezone(timedelta(hours=-3))).strftime('%Y-%m-%d')

candidatas, vistos, descartes = [], set(), {'sin mail valido': 0, 'web a confirmar': 0, 'otro estado': 0}
for i, f in enumerate(lista(input.get('planilla'))):
    if not isinstance(f, list) or not celda(f, 0):
        continue
    if celda(f, 20).lower() != 'detectada' or celda(f, 30):
        descartes['otro estado'] += 1
        continue
    mail = celda(f, 16).lower()
    if not RE_MAIL.match(mail) or RELLENO.search(mail) or mail in vistos:
        descartes['sin mail valido'] += 1
        continue
    if 'confirmar web' in celda(f, 24).lower():
        descartes['web a confirmar'] += 1
        continue
    vistos.add(mail)
    candidatas.append((0 if celda(f, 26) == 'A' else 1, celda(f, 10) or '9999', i, f, mail))
candidatas.sort(key=lambda x: (x[0], x[1]))

mails = []
for grupo, _, i, f, mail in candidatas:
    if len(mails) >= limite:
        break
    fila = i + 2
    razon = nombre_propio(celda(f, 1))
    organismo = nombre_propio(celda(f, 6).split(' | ')[0]) or 'la Ciudad'
    objeto = objeto_texto(celda(f, 7))
    if grupo == 0:
        seguros = [s.strip() for s in re.sub(r'^Seg[uú]n el r[eé]gimen general[^:]*:\s*', '', celda(f, 28)).split(';') if s.strip()]
        tipo = celda(f, 27).split(' | ')[0]
        if not seguros:
            continue
        asunto, cuerpo, texto = mail_a(razon, organismo, objeto, fecha_ar(celda(f, 10)), tipo, seguros)
        modelo = 'A'
    else:
        cobs = coberturas_b(celda(f, 2))
        if not cobs:
            continue
        asunto, cuerpo, texto = mail_b(razon, organismo, objeto, cobs)
        modelo = 'B'
    actualizacion = {'valueInputOption': 'RAW', 'data': [
        {'range': f'Empresas!U{fila}', 'values': [[estado_nuevo]]},
        {'range': f'Empresas!AE{fila}:AF{fila}', 'values': [[hoy, f'Modelo {modelo} ({modo}): {asunto}']]},
    ]}
    mails.append({'para': mail, 'asunto': asunto, 'html': cuerpo, 'texto': texto, 'fila': fila, 'empresa': razon,
                  'modelo': modelo, 'actualizacion': json.dumps(actualizacion, ensure_ascii=False)})

return {
    'modo': modo,
    'cantidad': len(mails),
    'mails': mails,
    'resumen': '<br>'.join(f"Modelo {m['modelo']} · {e(m['empresa'])} · {e(m['para'])}" for m in mails),
    'candidatas_restantes': max(0, len(candidatas) - len(mails)),
    'descartes': json.dumps(descartes, ensure_ascii=False),
}
