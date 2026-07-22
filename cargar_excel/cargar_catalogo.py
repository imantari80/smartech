import os
import pandas as pd
import psycopg2
from config import Config

# Conexión usando la variable de entorno o fallback a local
DATABASE_URL = os.environ.get("DATABASE_URL")

ruta_script = os.path.dirname(os.path.abspath(__file__))
excel_file = os.path.join(ruta_script, "catalogo_tecnologico_1200_final.xlsx")

print("📖 Leyendo datos desde el archivo Excel...")
df = pd.read_excel(excel_file, sheet_name="Catálogo Tecnológico Completo")

# Limpieza estricta de la columna PRECIO
if df['PRECIO (S/.)'].dtype == object:
    df['PRECIO_LIMPIO'] = df['PRECIO (S/.)'].astype(str).str.replace('S/.', '', regex=False)
    df['PRECIO_LIMPIO'] = df['PRECIO_LIMPIO'].str.replace(',', '', regex=False).str.strip()
    df['PRECIO_LIMPIO'] = pd.to_numeric(df['PRECIO_LIMPIO'])
else:
    df['PRECIO_LIMPIO'] = df['PRECIO (S/.)']

try:
    if DATABASE_URL:
        conn = psycopg2.connect(DATABASE_URL)
    else:
        conn = psycopg2.connect(**Config.DB_CONFIG_LOCAL)

    cursor = conn.cursor()
    print("🔌 Conexión exitosa a la base de datos.")

    query = """
        INSERT INTO componentes (id, categoria, marca, modelo, descripcion, precio)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO NOTHING;
    """

    records_to_insert = [
        (
            int(row['#']),
            str(row['CATEGORÍA']).strip(),
            str(row['MARCA']).strip(),
            str(row['MODELO']).strip(),
            str(row['DESCRIPCIÓN / CARACTERÍSTICAS']).strip(),
            float(row['PRECIO_LIMPIO'])
        )
        for _, row in df.iterrows()
    ]

    print(f"🚀 Insertando {len(records_to_insert)} registros en la tabla 'componentes'...")
    cursor.executemany(query, records_to_insert)
    conn.commit()
    print("✅ ¡Migración completada exitosamente!")

except Exception as error:
    print("❌ Error durante la migración:", error)
    if 'conn' in locals() and conn:
        conn.rollback()

finally:
    if 'cursor' in locals() and cursor:
        cursor.close()
    if 'conn' in locals() and conn:
        conn.close()
        print("🔌 Conexión a la base de datos cerrada.")