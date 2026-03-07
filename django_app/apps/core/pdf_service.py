"""
apps/core/pdf_service.py
Servicio centralizado para generación de PDFs usando xhtml2pdf.
Compatible con el layout de facturas AFIP del sistema Colosal.
"""
import io
import logging
from django.template.loader import render_to_string
from django.http import HttpResponse

logger = logging.getLogger(__name__)


def render_to_pdf(template_name: str, context: dict, filename: str = 'documento.pdf') -> HttpResponse:
    """
    Renderiza un template Django a PDF usando xhtml2pdf.
    Retorna un HttpResponse con el PDF listo para descarga.
    
    Args:
        template_name: nombre del template (ej: 'ventas/factura_pdf.html')
        context: contexto de datos del template
        filename: nombre del archivo para la descarga
    Returns:
        HttpResponse con Content-Type application/pdf
    """
    try:
        from xhtml2pdf import pisa

        html_string = render_to_string(template_name, context)
        buffer = io.BytesIO()

        pisa_status = pisa.CreatePDF(
            src=io.StringIO(html_string),
            dest=buffer,
            encoding='UTF-8',
        )

        if pisa_status.err:
            logger.error(f"Error xhtml2pdf generando {filename}: {pisa_status.err}")
            return HttpResponse(f"Error generando PDF: {pisa_status.err}", status=500)

        buffer.seek(0)
        response = HttpResponse(buffer.read(), content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="{filename}"'
        return response

    except ImportError:
        return HttpResponse("xhtml2pdf no está instalado.", status=500)
    except Exception as e:
        logger.exception(f"Error inesperado generando PDF {filename}: {e}")
        return HttpResponse(f"Error interno al generar PDF: {e}", status=500)


def render_to_pdf_bytes(template_name: str, context: dict) -> bytes | None:
    """
    Renderiza un template Django a PDF y retorna los bytes.
    Útil para enviar el PDF por email como adjunto.
    
    Returns:
        bytes del PDF, o None si hubo error.
    """
    try:
        from xhtml2pdf import pisa

        html_string = render_to_string(template_name, context)
        buffer = io.BytesIO()

        pisa_status = pisa.CreatePDF(
            src=io.StringIO(html_string),
            dest=buffer,
            encoding='UTF-8',
        )

        if pisa_status.err:
            logger.error(f"Error xhtml2pdf en render_to_pdf_bytes: {pisa_status.err}")
            return None

        return buffer.getvalue()

    except Exception as e:
        logger.exception(f"Error inesperado en render_to_pdf_bytes: {e}")
        return None
