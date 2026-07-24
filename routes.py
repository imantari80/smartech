from flask import Blueprint, request, jsonify, render_template, session, send_file, redirect, url_for
import re
import io
import urllib.parse
import psycopg2
from datetime import datetime, timedelta
from services import (
    obtener_conexion,
    cotizar_equipo_completo,
    armar_cpu_personalizado,
    buscar_periferico,
)
from pdf_generator import generar_pdf_proforma
import chat_logger
from export_estadisticas import generar_reporte_excel, resumen_dashboard
from auth import verificar_credenciales, login_requerido

chat_bp = Blueprint('chat', __name__)

# ==========================================
# CONSTANTES DE LENGUAJE NATURAL
# ==========================================
NEGACIONES = [
    'no', 'nada', 'ninguno', 'ninguna', 'nada mas', 'nada más',
    'ya no', 'no gracias', 'no quiero', 'listo', 'ya esta', 'ya está',
    'finalizar', 'terminar', 'eso es todo', 'suficiente', 'asi esta bien',
    'así está bien', 'ninguno gracias', 'no por ahora',
]
AFIRMACIONES = [
    'si', 'sí', 'acepto', 'bueno', 'vale', 'ok', 'dale', 'claro',
    'de acuerdo', 'perfecto', 'convence', '👍', 'correcto', 'confirmo',
]

ICONOS_CATEGORIA = {
    'Procesador': '🧠',
    'Placa Madre': '📋',
    'Memoria RAM': '⚡',
    'Disco Sólido': '💾',
    'Tarjeta de Video': '🎮',
    'Disipador / Enfriamiento': '❄️',
    'Fuente de Poder': '🔌',
    'Gabinete': '📦',
    'Teclado': '⌨️',
    'Mouse': '🖱️',
    'Monitor': '🖥️',
    'Auriculares': '🎧',
    'Parlante': '🔊',
    'Laptop': '💻',
    'All-in-One': '🖥️',
    'CPU de Fábrica': '🖥️',
}

CATEGORIAS_PERIFERICO = {
    'teclado': 'Teclado',
    'mouse': 'Mouse',
    'monitor': 'Monitor',
    'auricular': 'Auriculares',
    'audifono': 'Auriculares',
    'parlante': 'Parlante',
    'altavoz': 'Parlante',
}


def es_negacion(mensaje):
    return any(n in mensaje for n in NEGACIONES)


def es_afirmacion(mensaje):
    return any(a in mensaje for a in AFIRMACIONES)


def detectar_categoria_periferico(mensaje):
    for clave, categoria in CATEGORIAS_PERIFERICO.items():
        if clave in mensaje:
            return categoria
    return None


def frase_presupuesto(presupuesto, perfil):
    """Redacción empática y adaptativa según el rango del presupuesto (Fase 2)."""
    accion = {
        'Gamer': 'jugar sin cuellos de botella',
        'Estudiante de Ingeniería o Diseño': 'renderizar y trabajar tus proyectos',
        'Colegio': 'estudiar cómodamente',
        'Uso Doméstico / Ofimática': 'trabajar sin contratiempos',
    }.get(perfil, 'usar tu equipo')

    if presupuesto >= 4000:
        return (
            f"🎉 ¡Excelente presupuesto! Con <b>S/. {presupuesto:.2f}</b> vamos a diseñarte "
            f"una configuración de <b>alto rendimiento</b>, sacándole el máximo provecho a cada componente."
        )
    elif presupuesto >= 2000:
        return (
            f"👍 ¡Buen presupuesto! Con <b>S/. {presupuesto:.2f}</b> armamos una configuración "
            f"equilibrada y con una excelente relación calidad-precio."
        )
    else:
        return (
            f"💡 ¡Perfecto! Con <b>S/. {presupuesto:.2f}</b> vamos a optimizar cada Sol para "
            f"ofrecerte el mejor rendimiento y equilibrio posible dentro de tu presupuesto, "
            f"para que puedas {accion}."
        )


def _linea_item(categoria_label, item):
    icono = ICONOS_CATEGORIA.get(categoria_label, '🔹')
    beneficio = item.get('descripcion') or 'Buen rendimiento y confiabilidad para tu día a día'
    return {
        'categoria': categoria_label,
        'icono': icono,
        'marca': item['marca'],
        'modelo': item['modelo'],
        'descripcion': beneficio,
        'cod': item['cod'],
        'precio': item['precio'],
    }


def _texto_linea(linea):
    return (
        f"• {linea['icono']} <b>{linea['categoria']}:</b> {linea['marca']} {linea['modelo']} "
        f"| {linea['descripcion']}. Cod: {linea['cod']}. ➔ <b>S/. {linea['precio']:.2f}</b><br>"
    )


def construir_proforma(perfil, formato, presupuesto, cursor):
    """Construye la propuesta de hardware (Fase 3). Devuelve (texto, lineas, total, imposible)."""
    lineas = []

    if formato in ['Laptop', 'All-in-One', 'CPU de Fábrica']:
        equipo = cotizar_equipo_completo(cursor, formato, presupuesto)
        if not equipo:
            return None, None, None, True  # sin stock alguno: imposible
        if equipo.get('imposible'):
            return None, None, equipo['precio'], True
        lineas.append(_linea_item(formato, equipo))
        total = equipo['precio']
    else:
        pc = armar_cpu_personalizado(cursor, perfil, presupuesto)
        if not pc:
            return None, None, None, True
        if pc.get('imposible'):
            return None, None, pc['total'], True

        orden_categorias = [
            ('Procesador', 'cpu'),
            ('Placa Madre', 'placa'),
            ('Memoria RAM', 'ram'),
            ('Disco Sólido', 'ssd'),
            ('Tarjeta de Video', 'gpu'),
            ('Disipador / Enfriamiento', 'cooler'),
            ('Fuente de Poder', 'psu'),
            ('Gabinete', 'case'),
        ]
        for label, clave in orden_categorias:
            item = pc.get(clave)
            if item:
                lineas.append(_linea_item(label, item))
        total = pc['total']

    encabezado = (
        f"🤖 <b>[PROPUESTA DE HARDWARE SMARTECH]</b><br>"
        f"Analizando inventario disponible para perfil <b>{perfil}</b> en formato "
        f"<b>{formato}</b> (Presupuesto tope: S/. {presupuesto:.2f})<br><br>"
    )
    cuerpo = "".join(_texto_linea(l) for l in lineas)
    nota_ajuste = ""
    if total > presupuesto:
        nota_ajuste = (
            "<br>📌 <i>Nota: para mantener la mejor relación calidad-precio, esta configuración "
            "tiene un pequeño ajuste sobre tu presupuesto inicial.</i><br>"
        )
    cierre = (
        f"<br>💰 <b>Costo Total de Configuración: S/. {total:.2f}</b>{nota_ajuste}<br><br>"
        "¿Te convence esta configuración de hardware? Responde <b>SÍ</b> para ver periféricos "
        "y complementos, o <b>NO</b> si deseas modificar el presupuesto inicial."
    )
    texto = encabezado + cuerpo + cierre
    return texto, lineas, total, False


def construir_cierre(session_obj):
    """Fase 5: resumen final + comandos de PDF y WhatsApp."""
    lineas_equipo = session_obj.get('proforma_equipo') or []
    lineas_perifericos = session_obj.get('perifericos_agregados') or []
    todas = lineas_equipo + lineas_perifericos
    gran_total = sum(l['precio'] for l in todas)

    resumen = "".join(_texto_linea(l) for l in todas)

    texto_whatsapp = (
        f"Hola Smartech, deseo confirmar mi proforma:\n" +
        "\n".join(f"- {l['categoria']}: {l['marca']} {l['modelo']} (Cod {l['cod']}) S/. {l['precio']:.2f}" for l in todas) +
        f"\nGRAN TOTAL: S/. {gran_total:.2f}"
    )
    whatsapp_link = "https://wa.me/51922555282?text=" + urllib.parse.quote(texto_whatsapp)

    texto = (
        "📄 <b>[PROFORMA FINALIZADA CON ÉXITO]</b><br><br>"
        + resumen +
        f"<br>💰 <b>Gran Total: S/. {gran_total:.2f}</b><br><br>"
        "Tu configuración está lista para ser procesada. Haz clic en las siguientes opciones "
        "para continuar:<br><br>"
        "<a href='/api/generar-pdf' target='_blank'>📥 Descargar Proforma en PDF</a><br>"
        f"<a href='{whatsapp_link}' target='_blank'>🟢 Enviar Cotización a un Asesor por WhatsApp</a><br><br>"
        "¡Gracias por elegir Smartech! Un asesor humano validará tu stock de inmediato al recibir tu mensaje."
    )
    return texto, gran_total


# ==========================================
# RUTAS DE VISTA Y NAVEGACIÓN
# ==========================================

@chat_bp.route('/')
def index():
    session.clear()
    session['paso'] = 1
    for k in ['perfil', 'formato', 'presupuesto', 'sub_paso_periferico',
              'cat_periferico_elegido', 'proforma_equipo', 'perifericos_agregados',
              'esperando_confirmacion_proforma']:
        session[k] = None
    return render_template('index.html')


@chat_bp.route('/productos')
def productos():
    return render_template('productos.html')


@chat_bp.route('/servicios')
def servicios():
    return render_template('servicios.html')


@chat_bp.route('/cotizador')
def cotizador():
    return render_template('cotizador.html')


@chat_bp.route('/nosotros')
def nosotros():
    return render_template('nosotros.html')


@chat_bp.route('/mi-cuenta', methods=['GET', 'POST'])
def mi_cuenta():
    """
    Acceso EXCLUSIVO para administradores del sistema. No existe registro
    público: las cuentas se crean directamente en la base de datos
    (ver crear_admin.py / tabla `administradores`).
    """
    if session.get('admin_id'):
        return redirect(url_for('chat.dashboard'))

    error = None
    if request.method == 'POST':
        usuario = request.form.get('usuario', '').strip()
        password = request.form.get('password', '')

        try:
            admin = verificar_credenciales(usuario, password)
        except psycopg2.OperationalError:
            admin = None
            error = "⚠️ No se pudo conectar con la base de datos. Intenta nuevamente en unos minutos."

        if admin:
            session['admin_id'] = admin['id']
            session['admin_usuario'] = admin['usuario']
            session['admin_nombre'] = admin['nombre']
            return redirect(url_for('chat.dashboard'))
        elif not error:
            error = "Usuario o contraseña incorrectos."

    return render_template('mi_cuenta.html', error=error)


@chat_bp.route('/dashboard')
@login_requerido
def dashboard():
    return render_template('dashboard.html', admin_nombre=session.get('admin_nombre'))


@chat_bp.route('/logout')
def logout():
    session.pop('admin_id', None)
    session.pop('admin_usuario', None)
    session.pop('admin_nombre', None)
    return redirect(url_for('chat.mi_cuenta'))


# ==========================================
# ENDPOINTS API (CHAT Y PDF)
# ==========================================

@chat_bp.route('/api/generar-pdf')
def generar_pdf():
    lineas_equipo = session.get('proforma_equipo') or []
    lineas_perifericos = session.get('perifericos_agregados') or []
    todas = lineas_equipo + lineas_perifericos
    if not todas:
        return jsonify({"respuesta": "⚠️ Aún no hay una proforma generada para descargar."}), 400

    gran_total = sum(l['precio'] for l in todas)
    buffer = generar_pdf_proforma(
        perfil=session.get('perfil', ''),
        formato=session.get('formato', ''),
        presupuesto=session.get('presupuesto', 0.0),
        lineas=todas,
        gran_total=gran_total,
    )
    return send_file(
        buffer, mimetype='application/pdf',
        as_attachment=True, download_name='Proforma_Smartech.pdf'
    )


@chat_bp.route('/api/estadisticas/resumen')
@login_requerido
def resumen_estadisticas():
    """KPIs rápidos + serie de los últimos 14 días, para las tarjetas y el
    gráfico del dashboard. Solo accesible con sesión de administrador."""
    try:
        return jsonify(resumen_dashboard())
    except psycopg2.OperationalError:
        return jsonify({"error": "No se pudo conectar a la base de datos."}), 503


@chat_bp.route('/api/estadisticas/exportar')
@login_requerido
def exportar_estadisticas():
    """
    Exporta a Excel las estadísticas de uso del chatbot (cuántas consultas
    se hicieron) en un rango de fechas, agrupadas por día, semana o mes.

    Parámetros de query string (todos opcionales):
      - desde      : 'YYYY-MM-DD' (por defecto: hace 30 días)
      - hasta      : 'YYYY-MM-DD' (por defecto: hoy)
      - agrupacion : 'dia' | 'semana' | 'mes'  (por defecto: 'dia')

    Ejemplos:
      /api/estadisticas/exportar
      /api/estadisticas/exportar?agrupacion=semana
      /api/estadisticas/exportar?desde=2026-01-01&hasta=2026-06-30&agrupacion=mes
    """
    agrupacion = request.args.get('agrupacion', 'dia')
    hasta_str = request.args.get('hasta')
    desde_str = request.args.get('desde')

    try:
        hoy = datetime.now().date()
        fecha_fin_incl = (
            datetime.strptime(hasta_str, '%Y-%m-%d').date() if hasta_str else hoy
        )
        fecha_inicio = (
            datetime.strptime(desde_str, '%Y-%m-%d').date() if desde_str
            else fecha_fin_incl - timedelta(days=30)
        )
    except ValueError:
        return jsonify({"error": "Formato de fecha inválido. Usa YYYY-MM-DD."}), 400

    fecha_fin_exclusiva = fecha_fin_incl + timedelta(days=1)  # incluye todo el día 'hasta'

    try:
        buffer = generar_reporte_excel(
            datetime.combine(fecha_inicio, datetime.min.time()),
            datetime.combine(fecha_fin_exclusiva, datetime.min.time()),
            agrupacion=agrupacion,
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except psycopg2.OperationalError:
        return jsonify({"error": "No se pudo conectar a la base de datos."}), 503

    nombre_archivo = f"Estadisticas_Chatbot_{fecha_inicio}_a_{fecha_fin_incl}_{agrupacion}.xlsx"
    return send_file(
        buffer,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=nombre_archivo,
    )


@chat_bp.route('/api/chat', methods=['POST'])
def chat():
    mensaje = request.json.get('mensaje', '').lower().strip()
    paso_actual = session.get('paso', 1)

    if paso_actual in [4, 5]:
        try:
            prueba_conn = obtener_conexion()
            prueba_conn.close()
        except psycopg2.OperationalError:
            return jsonify({
                "respuesta": "🤖 ❌ En este momento mi base de datos PostgreSQL se encuentra apagada o "
                             "fuera de servicio. Por favor, enciende el servidor de la base de datos "
                             "para poder procesar tu stock."
            })

    try:
        conn = obtener_conexion()
        cursor = conn.cursor()
    except Exception:
        cursor = None
        conn = None

    def cerrar():
        if cursor:
            cursor.close()
        if conn:
            conn.close()

    # ── Registro de la consulta para fines estadísticos (best-effort: si
    #    falla, nunca interrumpe la respuesta real del chatbot) ──
    sesion_id = chat_logger.obtener_sesion_id(session)
    chat_logger.registrar_evento(
        conn, cursor, sesion_id, paso_actual, mensaje,
        perfil=session.get('perfil'),
        formato=session.get('formato'),
        presupuesto=session.get('presupuesto'),
    )

    try:
        # ==========================================
        # PASO 1: IDENTIFICAR PERFIL
        # ==========================================
        if paso_actual == 1:
            if any(p in mensaje for p in ['gamer', 'jug', 'juego']):
                session['perfil'] = 'Gamer'
            elif any(p in mensaje for p in ['ingenieria', 'ingeniería', 'disen', 'diseñ', 'arquitectura', 'autocad', 'render']):
                session['perfil'] = 'Estudiante de Ingeniería o Diseño'
            elif any(p in mensaje for p in ['colegio', 'escuela', 'escolar', 'hijo']):
                session['perfil'] = 'Colegio'
            elif any(p in mensaje for p in ['domestico', 'doméstico', 'oficina', 'ofimatica', 'ofimática', 'word', 'excel', 'casa']):
                session['perfil'] = 'Uso Doméstico / Ofimática'
            else:
                cerrar()
                return jsonify({
                    "respuesta": "🤖 ¡Hola! Bienvenido a Smartech, tu aliado en soluciones informáticas. "
                                 "Para armar la configuración ideal para ti, cuéntame primero: "
                                 "<b>¿Cuál es tu perfil de uso?</b><br><br>"
                                 "1. 🎮 Gamer<br>"
                                 "2. 📐 Estudiante de Ingeniería o Diseño<br>"
                                 "3. 🎒 Estudiante de Colegio<br>"
                                 "4. 💼 Uso Doméstico / Ofimática (Word, Excel)"
                })

            session['paso'] = 2
            cerrar()
            return jsonify({
                "respuesta": f"✅ Perfil registrado: <b>{session['perfil']}</b>.<br><br>"
                             "Ahora cuéntame, <b>¿qué formato de computadora prefieres?</b><br>"
                             "• <b>CPU para armar</b> (Componentes por separado)<br>"
                             "• <b>CPU de fábrica</b> (Pre-armada de marca)<br>"
                             "• <b>Laptop</b> (Portátil)<br>"
                             "• <b>All-in-One</b> (Todo en uno)"
            })

        # ==========================================
        # PASO 2: IDENTIFICAR FORMATO
        # ==========================================
        if paso_actual == 2:
            if any(f in mensaje for f in ['fabrica', 'fábrica', 'pre-armada', 'marca']):
                session['formato'] = 'CPU de Fábrica'
            elif any(f in mensaje for f in ['armar', 'separado', 'piezas']):
                session['formato'] = 'CPU para armar'
            elif any(f in mensaje for f in ['laptop', 'portatil', 'portátil']):
                session['formato'] = 'Laptop'
            elif any(f in mensaje for f in ['all-in-one', 'todo en uno', 'aio']):
                session['formato'] = 'All-in-One'
            else:
                cerrar()
                return jsonify({
                    "respuesta": "⚠️ Por favor, selecciona uno de los formatos disponibles:<br>"
                                 "• CPU para armar<br>• CPU de fábrica<br>• Laptop<br>• All-in-One"
                })

            session['paso'] = 3
            cerrar()
            return jsonify({
                "respuesta": f"✅ Formato seleccionado: <b>{session['formato']}</b>.<br><br>"
                             "💵 ¿Cuál es tu <b>presupuesto máximo estimado en Soles (S/.)</b>?"
            })

        # ==========================================
        # PASO 3: DEFINIR PRESUPUESTO
        # ==========================================
        if paso_actual == 3:
            numeros = re.findall(r'\d+', mensaje)
            if not numeros:
                cerrar()
                return jsonify({
                    "respuesta": "⚠️ No logré identificar un monto numérico. Por favor dime tu "
                                 "presupuesto máximo estimado en números (Ejemplo: 2500)."
                })

            session['presupuesto'] = float(numeros[0])
            session['paso'] = 4
            paso_actual = 4

        # ==========================================
        # PASO 4: PRESENTAR PROPUESTA DE HARDWARE Y CONFIRMAR
        # ==========================================
        if paso_actual == 4:
            if session.get('esperando_confirmacion_proforma'):
                if es_negacion(mensaje):
                    session['esperando_confirmacion_proforma'] = False
                    session['paso'] = 3
                    cerrar()
                    return jsonify({
                        "respuesta": "🔄 Sin problema. Vamos a recalcular tu configuración. Por favor, "
                                     "indícame nuevamente tu <b>presupuesto máximo estimado en Soles (S/.)</b>:"
                    })
                elif es_afirmacion(mensaje):
                    session['esperando_confirmacion_proforma'] = False
                    session['paso'] = 5
                    session['sub_paso_periferico'] = 'preguntar_interes'
                    paso_actual = 5
                else:
                    cerrar()
                    return jsonify({
                        "respuesta": "🤔 Por favor confírmame de forma clara: ¿te convence esta "
                                     "configuración para pasar a los periféricos? Responde <b>SÍ</b> "
                                     "para avanzar o <b>NO</b> para cambiar el presupuesto."
                    })

            if paso_actual == 4:
                perfil = session['perfil']
                formato = session['formato']
                presupuesto = session['presupuesto']

                intro = frase_presupuesto(presupuesto, perfil) + "<br><br>"
                texto, lineas, total, imposible = construir_proforma(perfil, formato, presupuesto, cursor)

                if imposible:
                    session['paso'] = 3
                    cerrar()
                    return jsonify({
                        "respuesta": f"😔 Con S/. {presupuesto:.2f} no logramos armar una configuración "
                                     f"técnicamente viable para el perfil <b>{perfil}</b> en formato "
                                     f"<b>{formato}</b>. Por favor, indícame un presupuesto mayor para "
                                     f"recalcular tu equipo ideal."
                    })

                session['proforma_equipo'] = lineas
                session['esperando_confirmacion_proforma'] = True
                cerrar()
                return jsonify({"respuesta": intro + texto})

        # ==========================================
        # PASO 5: PRESENTAR Y BUSCAR PERIFÉRICOS
        # ==========================================
        if paso_actual == 5:
            sub_paso = session.get('sub_paso_periferico', 'preguntar_interes')

            if sub_paso == 'preguntar_interes':
                session['sub_paso_periferico'] = 'evaluar_interes'
                cerrar()
                return jsonify({
                    "respuesta": "✨ <b>[FASE FINAL: COMPLEMENTOS Y PERIFÉRICOS]</b><br>"
                                 "¡Excelente elección! Ahora coordinemos tus accesorios adicionales.<br><br>"
                                 "❓ <b>¿Deseas agregar algún periférico o accesorio a tu cotización?</b> "
                                 "(Teclado, Mouse, Monitor, Auriculares, Parlante...)"
                })

            elif sub_paso == 'evaluar_interes':
                categoria_directa = detectar_categoria_periferico(mensaje)
                if categoria_directa:
                    session['cat_periferico_elegido'] = categoria_directa
                    session['sub_paso_periferico'] = 'solicitar_presupuesto_periferico'
                    cerrar()
                    return jsonify({
                        "respuesta": f"💵 ¿Cuál es tu <b>presupuesto aproximado en Soles (S/.)</b> "
                                     f"exclusivo para adquirir tu <b>{categoria_directa}</b>?"
                    })
                if es_negacion(mensaje):
                    session['sub_paso_periferico'] = 'finalizado'
                    texto, _ = construir_cierre(session)
                    cerrar()
                    return jsonify({"respuesta": texto})
                else:
                    session['sub_paso_periferico'] = 'solicitar_categoria'
                    cerrar()
                    return jsonify({
                        "respuesta": "📝 ¡Perfecto! Escribe qué accesorio deseas agregar:<br>"
                                     "• <i>Teclado</i><br>• <i>Mouse</i><br>• <i>Monitor</i><br>"
                                     "• <i>Auriculares</i><br>• <i>Parlante</i>"
                    })

            elif sub_paso == 'solicitar_categoria':
                if es_negacion(mensaje):
                    session['sub_paso_periferico'] = 'finalizado'
                    texto, _ = construir_cierre(session)
                    cerrar()
                    return jsonify({"respuesta": texto})

                categoria = detectar_categoria_periferico(mensaje)
                if not categoria:
                    cerrar()
                    return jsonify({
                        "respuesta": "⚠️ No logré identificar esa categoría. Escribe si deseas un "
                                     "<i>Teclado</i>, <i>Mouse</i>, <i>Monitor</i>, <i>Auriculares</i> "
                                     "o <i>Parlante</i>, o responde <b>NO</b> si prefieres finalizar."
                    })
                session['cat_periferico_elegido'] = categoria
                session['sub_paso_periferico'] = 'solicitar_presupuesto_periferico'
                cerrar()
                return jsonify({
                    "respuesta": f"💵 ¿Cuál es tu <b>presupuesto aproximado en Soles (S/.)</b> "
                                 f"exclusivo para adquirir tu <b>{categoria}</b>?"
                })

            elif sub_paso == 'solicitar_presupuesto_periferico':
                if es_negacion(mensaje):
                    session['sub_paso_periferico'] = 'finalizado'
                    texto, _ = construir_cierre(session)
                    cerrar()
                    return jsonify({"respuesta": texto})

                numeros = re.findall(r'\d+', mensaje)
                if not numeros:
                    cerrar()
                    return jsonify({
                        "respuesta": "⚠️ Por favor, introduce el monto en números para evaluar "
                                     "nuestro catálogo (Ejemplo: 80)."
                    })

                presupuesto_peri = float(numeros[0])
                categoria_peri = session.get('cat_periferico_elegido', 'Teclado')
                item = buscar_periferico(cursor, categoria_peri, presupuesto_peri)

                if item:
                    linea = _linea_item(categoria_peri, item)
                    perifericos = session.get('perifericos_agregados') or []
                    perifericos.append(linea)
                    session['perifericos_agregados'] = perifericos
                    nota = ""
                    if item.get('adaptado') and item['precio'] > presupuesto_peri:
                        nota = "<br>📌 <i>Nota: es la opción más cercana disponible en stock.</i>"
                    resp = (
                        "🔎 <b>[OPCIÓN LOCALIZADA EN INVENTARIO]</b><br>"
                        + _texto_linea(linea) + nota
                    )
                else:
                    resp = (
                        f"❌ No encontré un {categoria_peri} disponible en este momento, pero puedo "
                        f"revisar otra categoría contigo.<br>"
                    )

                session['sub_paso_periferico'] = 'solicitar_categoria'
                resp += "<br>➕ ¿Deseas agregar <b>otro accesorio</b>? Escribe el nombre " \
                        "(<i>Teclado</i>, <i>Mouse</i>, etc.) o responde <b>NO</b> si terminamos."
                cerrar()
                return jsonify({"respuesta": resp})

            elif sub_paso == 'finalizado':
                texto, _ = construir_cierre(session)
                cerrar()
                return jsonify({"respuesta": texto})

    except Exception as e:
        cerrar()
        return jsonify({"respuesta": f"⚠️ Error de procesamiento interno: {str(e)}"})

    cerrar()
    return jsonify({"respuesta": "🤖 Escríbeme algo para continuar con tu cotización."})