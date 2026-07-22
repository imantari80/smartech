import psycopg2
from config import Config

# Umbral de tolerancia: si el ítem más barato disponible supera el presupuesto
# en más de este porcentaje, se considera "técnicamente imposible".
TOLERANCIA_IMPOSIBLE = 0.45  # 45% por encima del presupuesto


def obtener_conexion():
    # Si existe DATABASE_URL (entorno Render/Nube), se conecta usando la URL
    if hasattr(Config, 'DATABASE_URL') and Config.DATABASE_URL:
        return psycopg2.connect(Config.DATABASE_URL)
    
    # Si no, se conecta a la base de datos local de desarrollo
    return psycopg2.connect(**Config.DB_CONFIG_LOCAL)


def formatear_cod(id_producto):
    """Genera un código corto de 3 dígitos a partir del ID real en BD."""
    return str(id_producto % 1000).zfill(3)


def clasificar_gama(precio, minimo, maximo):
    """Clasifica un componente en Entrada / Media / Alta según su posición
    relativa dentro del rango de precios de su categoría."""
    if maximo is None or minimo is None or maximo == minimo:
        return "Media"
    posicion = (float(precio) - float(minimo)) / (float(maximo) - float(minimo))
    if posicion < 0.33:
        return "Entrada"
    elif posicion < 0.7:
        return "Media"
    return "Alta"


def obtener_rango_precios(cursor, categoria):
    cursor.execute(
        "SELECT MIN(precio), MAX(precio) FROM componentes WHERE categoria = %s;",
        (categoria,)
    )
    return cursor.fetchone()


def _row_a_item(row):
    """Convierte una fila (id, marca, modelo, descripcion, precio) en dict."""
    if not row:
        return None
    return {
        "id": row[0],
        "cod": formatear_cod(row[0]),
        "marca": row[1],
        "modelo": row[2],
        "descripcion": row[3],
        "precio": float(row[4]),
    }


def cotizar_equipo_completo(cursor, categoria_bd, presupuesto):
    """Busca Laptops, All-in-One o CPU de Fábrica.
    Presupuesto flexible: primero intenta el mejor equipo dentro del tope;
    si no hay nada dentro del presupuesto, cae a la opción más económica
    disponible en stock (adaptación de gama), en vez de rechazar de inmediato.
    """
    cursor.execute(
        "SELECT id, marca, modelo, descripcion, precio FROM componentes "
        "WHERE categoria = %s AND precio <= %s ORDER BY precio DESC LIMIT 1;",
        (categoria_bd, presupuesto)
    )
    row = cursor.fetchone()
    adaptado = False

    if not row:
        cursor.execute(
            "SELECT id, marca, modelo, descripcion, precio FROM componentes "
            "WHERE categoria = %s ORDER BY precio ASC LIMIT 1;",
            (categoria_bd,)
        )
        row = cursor.fetchone()
        adaptado = True

    item = _row_a_item(row)
    if not item:
        return None  # No hay stock en absoluto para esa categoría

    if adaptado and item["precio"] > presupuesto * (1 + TOLERANCIA_IMPOSIBLE):
        item["imposible"] = True
    else:
        item["imposible"] = False
    item["adaptado"] = adaptado
    return item


def buscar_periferico(cursor, categoria, max_precio):
    """Busca el periférico más óptimo y cercano al presupuesto remanente.
    Nunca deja al usuario sin opción: si nada calza en presupuesto, ofrece
    la alternativa más económica disponible."""
    cursor.execute(
        "SELECT id, marca, modelo, descripcion, precio FROM componentes "
        "WHERE categoria = %s AND precio <= %s ORDER BY precio DESC LIMIT 1;",
        (categoria, max_precio)
    )
    row = cursor.fetchone()
    adaptado = False
    if not row:
        cursor.execute(
            "SELECT id, marca, modelo, descripcion, precio FROM componentes "
            "WHERE categoria = %s ORDER BY precio ASC LIMIT 1;",
            (categoria,)
        )
        row = cursor.fetchone()
        adaptado = True

    item = _row_a_item(row)
    if item:
        item["adaptado"] = adaptado
    return item


def _elegir_componente(cursor, categoria, filtro_modelo, orden):
    cursor.execute(
        f"SELECT id, marca, modelo, descripcion, precio FROM componentes "
        f"WHERE categoria=%s AND modelo ILIKE %s ORDER BY precio {orden} LIMIT 1;",
        (categoria, filtro_modelo)
    )
    row = cursor.fetchone()
    if not row:
        # Sin resultados con el filtro de modelo: caemos a cualquier opción
        # disponible de la categoría (nunca dejamos el build vacío).
        cursor.execute(
            f"SELECT id, marca, modelo, descripcion, precio FROM componentes "
            f"WHERE categoria=%s ORDER BY precio {orden} LIMIT 1;",
            (categoria,)
        )
        row = cursor.fetchone()
    return _row_a_item(row)


def armar_cpu_personalizado(cursor, perfil, presupuesto):
    """
    Arma una PC por piezas evitando cuellos de botella:
    - Define una 'gama objetivo' (Entrada / Media / Alta) según el presupuesto.
    - Reserva presupuesto para la GPU ANTES de elegir CPU en perfiles que la
      requieren (Gamer / Ingeniería), evitando procesadores tope de gama
      emparejados con gráficas débiles.
    - Presupuesto flexible: solo se marca como 'imposible' si ni siquiera la
      configuración más económica cabe razonablemente cerca del presupuesto.
    """
    es_ofimatica = perfil in ["Colegio", "Uso Doméstico / Ofimática"]
    requiere_gpu = perfil in ["Gamer", "Estudiante de Ingeniería o Diseño"]

    if presupuesto < 2000:
        gama = "entrada"
    elif presupuesto < 4000:
        gama = "media"
    else:
        gama = "alta"

    orden = "ASC" if gama == "entrada" else "DESC"

    # Filtro de CPU: evita gama entusiasta (i9/Ryzen 9) si el presupuesto no la sostiene
    if es_ofimatica:
        filtro_cpu = "%i3%"
    elif gama == "entrada":
        filtro_cpu = "%i3%"
    elif gama == "media":
        filtro_cpu = "%i5%"
    else:
        filtro_cpu = "%"

    categorias = {
        "placa": ("Placa Madre", "%"),
        "ram": ("Memoria RAM", "%8 GB%" if (perfil == "Uso Doméstico / Ofimática" and gama == "entrada") else "%"),
        "ssd": ("Disco Sólido", "%512GB%" if (perfil == "Uso Doméstico / Ofimática" and gama == "entrada") else "%"),
        "psu": ("Fuente de Poder", "%"),
        "cooler": ("Disipador / Enfriamiento", "%Stock%" if es_ofimatica else "%"),
        "case": ("Gabinete", "%"),
    }

    pc = {}
    total_base = 0.0

    # 1) Si el perfil requiere GPU, la reservamos primero para asegurar sinergia
    presupuesto_restante = presupuesto
    if requiere_gpu:
        cursor.execute(
            "SELECT id, marca, modelo, descripcion, precio FROM componentes "
            "WHERE categoria='Tarjeta de Video' AND precio <= %s ORDER BY precio DESC LIMIT 1;",
            (presupuesto * (0.45 if gama == "alta" else 0.35),)
        )
        row = cursor.fetchone()
        if not row:
            # Cae a la GPU más económica disponible (adaptación, no rechazo)
            cursor.execute(
                "SELECT id, marca, modelo, descripcion, precio FROM componentes "
                "WHERE categoria='Tarjeta de Video' ORDER BY precio ASC LIMIT 1;"
            )
            row = cursor.fetchone()
        gpu = _row_a_item(row)
        if not gpu:
            return None  # No hay ninguna GPU en stock: imposible
        pc["gpu"] = gpu
        total_base += gpu["precio"]
        presupuesto_restante -= gpu["precio"]
        # Si la GPU ya consumió casi todo el presupuesto, forzamos CPU de entrada
        if presupuesto_restante < presupuesto * 0.3:
            filtro_cpu = "%i3%"
    else:
        pc["gpu"] = None

    # 2) CPU acorde a la gama y a lo que sobró tras la GPU
    pc["cpu"] = _elegir_componente(cursor, "Procesador", filtro_cpu, orden)
    if not pc["cpu"]:
        return None
    total_base += pc["cpu"]["precio"]

    # 3) Resto de componentes obligatorios
    for clave, (cat, filtro) in categorias.items():
        pc[clave] = _elegir_componente(cursor, cat, filtro, orden)
        if not pc[clave]:
            return None
        total_base += pc[clave]["precio"]

    pc["total"] = total_base
    pc["imposible"] = total_base > presupuesto * (1 + TOLERANCIA_IMPOSIBLE)
    pc["adaptado"] = total_base > presupuesto

    return pc