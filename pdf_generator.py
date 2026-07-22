import io
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_RIGHT, TA_CENTER


def generar_pdf_proforma(perfil, formato, presupuesto, lineas, gran_total):
    """
    Genera un PDF de la proforma en memoria y devuelve un BytesIO listo para
    enviar con send_file.

    lineas: lista de dicts con claves: categoria, marca, modelo, descripcion,
            cod, precio
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        topMargin=2 * cm, bottomMargin=2 * cm,
        leftMargin=1.8 * cm, rightMargin=1.8 * cm,
    )

    styles = getSampleStyleSheet()
    titulo_style = ParagraphStyle(
        "Titulo", parent=styles["Heading1"], textColor=colors.HexColor("#1a2b4c")
    )
    subtitulo_style = ParagraphStyle(
        "Subtitulo", parent=styles["Normal"], textColor=colors.HexColor("#555555")
    )
    # Estilos de celda: SIEMPRE se usan dentro de Paragraph, nunca strings
    # planos en la tabla, para que el texto haga wrap real y no se
    # sobreponga con la celda vecina.
    celda_style = ParagraphStyle(
        "Celda", parent=styles["Normal"], fontSize=8.5, leading=10.5,
    )
    celda_header_style = ParagraphStyle(
        "CeldaHeader", parent=celda_style, textColor=colors.white,
        fontName="Helvetica-Bold",
    )
    celda_precio_style = ParagraphStyle(
        "CeldaPrecio", parent=celda_style, alignment=TA_RIGHT,
        fontName="Helvetica-Bold",
    )
    celda_cod_style = ParagraphStyle(
        "CeldaCod", parent=celda_style, alignment=TA_CENTER,
    )
    total_label_style = ParagraphStyle(
        "TotalLabel", parent=styles["Normal"], fontSize=12,
        fontName="Helvetica-Bold", alignment=TA_RIGHT,
        textColor=colors.HexColor("#1a2b4c"),
    )

    elementos = []
    elementos.append(Paragraph("SmartTech S.A.C. — Proforma de Cotización", titulo_style))
    elementos.append(Paragraph(
        f"Fecha: {datetime.now().strftime('%d/%m/%Y %H:%M')}", subtitulo_style
    ))
    elementos.append(Paragraph(
        f"Perfil: {perfil} &nbsp;|&nbsp; Formato: {formato} &nbsp;|&nbsp; "
        f"Presupuesto tope: S/. {presupuesto:.2f}", subtitulo_style
    ))
    elementos.append(Spacer(1, 0.6 * cm))

    encabezados = ["Categoría", "Marca / Modelo", "Detalle", "Cód.", "Precio (S/.)"]
    data = [[Paragraph(h, celda_header_style) for h in encabezados]]

    for linea in lineas:
        data.append([
            Paragraph(str(linea.get("categoria", "")), celda_style),
            Paragraph(f"{linea.get('marca', '')} {linea.get('modelo', '')}", celda_style),
            Paragraph(linea.get("descripcion") or "", celda_style),
            Paragraph(str(linea.get("cod", "")), celda_cod_style),
            Paragraph(f"S/. {linea.get('precio', 0):.2f}", celda_precio_style),
        ])

    # Anchos ajustados al área útil de A4 con márgenes de 1.8cm (~17.4cm)
    anchos = [2.8 * cm, 4.0 * cm, 6.6 * cm, 1.8 * cm, 2.4 * cm]

    tabla = Table(data, colWidths=anchos, repeatRows=1)
    tabla.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a2b4c")),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f4f6fa")]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    elementos.append(tabla)

    # El Gran Total va como párrafo aparte (no como fila de la tabla) para
    # que nunca quede pegado visualmente a otra celda.
    elementos.append(Spacer(1, 0.4 * cm))
    elementos.append(Paragraph(
        f"GRAN TOTAL:&nbsp;&nbsp;S/. {gran_total:.2f}", total_label_style
    ))

    elementos.append(Spacer(1, 1 * cm))
    elementos.append(Paragraph(
        "Un asesor Smartech validará el stock exacto al momento de confirmar tu compra. "
        "Esta proforma no representa un comprobante de pago.", subtitulo_style
    ))

    doc.build(elementos)
    buffer.seek(0)
    return buffer