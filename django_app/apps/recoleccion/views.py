import json
import logging
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from apps.core.decorators import login_required, permission_required
from apps.core.db import get_db_cursor, dictfetchone, dictfetchall

logger = logging.getLogger(__name__)


def _send_count_email(cursor, inv_id, item_id, art_nombre, art_codigo,
                      cantidad, codigo_escaneado, es_forzado, user_id, ent_id):
    """Send HTML email with campaign count details to operator and supervisor."""
    from datetime import datetime

    # Get operator and supervisor emails
    cursor.execute("""
        SELECT u.email, u.nombre, u.apellido
        FROM usuarios u
        WHERE u.id = %s
    """, (user_id,))
    op = dictfetchone(cursor)
    if not op or not op.get('email'):
        logger.warning(f"No email found for user_id {user_id}, skipping email.")
        return

    # Get all campaign items so far for the full table
    cursor.execute("""
        SELECT a.nombre, a.codigo, it.stock_fisico, it.codigo_escaneado, it.es_forzado, it.updated_at
        FROM stk_items_inventario it
        JOIN stk_articulos a ON it.articulo_id = a.id
        WHERE it.inventario_id = %s
        ORDER BY a.nombre
    """, (inv_id,))
    all_items = dictfetchall(cursor)

    # Get campaign name
    cursor.execute("SELECT observaciones FROM stk_inventarios WHERE id = %s", (inv_id,))
    inv_row = dictfetchone(cursor)
    camp_name = (inv_row or {}).get('observaciones') or f"Campaña #{inv_id}"

    # Get supervisor emails (enterprise owner / admin users)
    cursor.execute("""
        SELECT email FROM usuarios 
        WHERE enterprise_id = %s AND email IS NOT NULL AND email != ''
        AND id != %s
        LIMIT 5
    """, (ent_id, user_id))
    supervisors = dictfetchall(cursor)

    op_name = f"{op.get('nombre','')} {op.get('apellido','')}".strip() or f"Usuario #{user_id}"
    now_str = datetime.now().strftime("%d/%m/%Y %H:%M")

    # Build item rows HTML
    rows_html = ""
    for idx, it in enumerate(all_items):
        is_saved = it.get('stock_fisico') is not None and it.get('updated_at') is not None
        row_bg = "#fff8e1" if it.get('es_forzado') else ("#f9f9f9" if idx % 2 == 0 else "#ffffff")
        forzado_badge = '<span style="background:#ff9800;color:#fff;border-radius:4px;padding:2px 6px;font-size:11px;font-weight:bold;">⚠ FORZADO</span>' if it.get('es_forzado') else ""
        qty_display = str(it['stock_fisico']).rstrip('0').rstrip('.') if is_saved else '<em style="color:#aaa">Pendiente</em>'
        cod_scan = it.get('codigo_escaneado') or it.get('codigo') or '-'
        rows_html += f"""
        <tr style="background:{row_bg}">
            <td style="padding:10px 14px;border-bottom:1px solid #eee;">{it['nombre']}</td>
            <td style="padding:10px 14px;border-bottom:1px solid #eee;font-family:monospace;">{it['codigo']}</td>
            <td style="padding:10px 14px;border-bottom:1px solid #eee;font-family:monospace;color:#1565c0;">{cod_scan} {forzado_badge}</td>
            <td style="padding:10px 14px;border-bottom:1px solid #eee;text-align:center;font-weight:bold;">{qty_display}</td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Recuento de Campaña</title></head>
<body style="margin:0;padding:0;background:#f4f4f4;font-family:'Segoe UI',Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f4f4;padding:30px 0;">
<tr><td align="center">
<table width="600" cellpadding="0" cellspacing="0" style="background:#fff;border-radius:10px;overflow:hidden;box-shadow:0 4px 15px rgba(0,0,0,0.1);max-width:600px;width:100%;">
  <tr>
    <td style="background:linear-gradient(135deg,#1e2229,#f39c12);padding:30px;text-align:center;">
      <h1 style="color:#fff;margin:0;font-size:24px;letter-spacing:1px;">📋 RECUENTO DE CAMPAÑA</h1>
      <p style="color:rgba(255,255,255,0.8);margin:8px 0 0;font-size:14px;">{camp_name}</p>
    </td>
  </tr>
  <tr>
    <td style="padding:25px 30px;">
      <p style="color:#555;margin:0 0 5px;font-size:14px;"><strong>Operador:</strong> {op_name}</p>
      <p style="color:#555;margin:0 0 5px;font-size:14px;"><strong>Artículo recién contado:</strong> {art_nombre}</p>
      <p style="color:#555;margin:0 0 20px;font-size:14px;"><strong>Fecha:</strong> {now_str}</p>
      
      <h3 style="color:#1e2229;font-size:15px;margin:0 0 12px;padding-bottom:8px;border-bottom:2px solid #f39c12;">
        Estado Actual de la Campaña
      </h3>
      
      <table width="100%" cellpadding="0" cellspacing="0" style="border-radius:8px;overflow:hidden;border:1px solid #e0e0e0;">
        <thead>
          <tr style="background:#1e2229;color:#fff;">
            <th style="padding:12px 14px;text-align:left;font-size:13px;">Artículo</th>
            <th style="padding:12px 14px;text-align:left;font-size:13px;">Código Sistema</th>
            <th style="padding:12px 14px;text-align:left;font-size:13px;">Código Escaneado</th>
            <th style="padding:12px 14px;text-align:center;font-size:13px;">Cantidad</th>
          </tr>
        </thead>
        <tbody>{rows_html}</tbody>
      </table>
      
      <p style="color:#888;font-size:12px;margin-top:20px;">
        ⚠ Los ítems marcados como <strong>FORZADO</strong> indican que el código escaneado no coincidió con el código del sistema.<br>
        El operador confirmó igualmente el conteo.
      </p>
    </td>
  </tr>
  <tr>
    <td style="background:#1e2229;padding:15px;text-align:center;">
      <p style="color:rgba(255,255,255,0.5);font-size:12px;margin:0;">Enviado automáticamente por Colosal ERP · Sistema de Inventarios</p>
    </td>
  </tr>
</table>
</td></tr></table>
</body></html>"""

    subject = f"[Colosal] Recuento: {art_nombre} — {camp_name}"
    recipients = [op['email']] + [s['email'] for s in supervisors if s.get('email')]

    msg = EmailMultiAlternatives(
        subject=subject,
        body=f"Recuento guardado: {art_nombre} = {cantidad} unidades. Operador: {op_name}",
        from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@colosal.app'),
        to=list(set(recipients))
    )
    msg.attach_alternative(html, "text/html")
    msg.send(fail_silently=True)
    logger.info(f"Count email sent to {recipients} for item {art_nombre}")


@login_required
@permission_required('view_recolectores')
def index(request):
    """Mobile Dashboard for Warehouse Operators"""
    u = request.user_data
    context = {
        'username': u.get('username'),
        'enterprise_id': u.get('enterprise_id'),
        'sid': request.sid,
    }
    return render(request, 'recoleccion/index.html', context)

@login_required
@permission_required('recolector_picking')
def picking(request):
    """Picking / Order Preparation"""
    return render(request, 'recoleccion/picking.html', {
        'username': getattr(request, 'user_data', {}).get('username'),
        'sid': request.sid
    })

@login_required
@permission_required('recolector_counting')
def inventario(request):
    """Inventory Counting Mode (Direct or Campaign)"""
    return render(request, 'recoleccion/inventario.html', {
        'username': getattr(request, 'user_data', {}).get('username'),
        'sid': request.sid
    })

@login_required
@permission_required('recolector_counting')
def campanias(request):
    """List of active inventory campaigns"""
    ent_id = getattr(request, 'user_data', {}).get('enterprise_id', 0)
    with get_db_cursor(dictionary=True) as cursor:
        cursor.execute("""
            SELECT i.id, i.observaciones as nombre, d.nombre as deposito,
                   (SELECT COUNT(*) FROM stk_items_inventario WHERE inventario_id = i.id) as total_items,
                   (SELECT COUNT(*) FROM stk_items_inventario WHERE inventario_id = i.id AND stock_fisico IS NOT NULL) as contados
            FROM stk_inventarios i
            LEFT JOIN stk_depositos d ON i.deposito_id = d.id
            WHERE i.enterprise_id = %s AND i.estado = 'EN_PROCESO'
        """, (ent_id,))
        campanias = dictfetchall(cursor)
        
        for c in campanias:
            c['progreso'] = (c['contados'] * 100 / c['total_items']) if c['total_items'] > 0 else 0
            
    return render(request, 'recoleccion/campanias.html', {
        'campanias': campanias,
        'username': getattr(request, 'user_data', {}).get('username'),
        'sid': request.sid
    })

@login_required
@permission_required('recolector_counting')
def api_get_items_campania(request, inv_id):
    """Get items to count in a campaign"""
    try:
        ent_id = getattr(request, 'user_data', {}).get('enterprise_id', 0)
        with get_db_cursor(dictionary=True) as cursor:
            cursor.execute("""
                SELECT it.id, it.articulo_id, a.nombre, a.codigo,
                       it.stock_sistema, it.stock_fisico, it.user_id,
                       it.codigo_escaneado, it.es_forzado
                FROM stk_items_inventario it
                JOIN stk_articulos a ON it.articulo_id = a.id
                WHERE it.inventario_id = %s AND (it.enterprise_id = %s OR it.enterprise_id = 0)
                ORDER BY a.nombre
            """, (inv_id, ent_id))
            rows = dictfetchall(cursor)

            # Also fetch campaign metadata
            cursor.execute("""
                SELECT observaciones, fecha_inicio, tipo, estado
                FROM stk_inventarios WHERE id = %s
            """, (inv_id,))
            camp_meta = dictfetchone(cursor) or {}

        # Normalize non-JSON-serializable types
        import decimal, datetime
        def safe(v):
            if isinstance(v, decimal.Decimal): return float(v)
            if isinstance(v, (datetime.datetime, datetime.date)): return str(v)
            return v

        items = [{k: safe(v) for k, v in row.items()} for row in rows]
        camp_meta = {k: safe(v) for k, v in camp_meta.items()}
        return JsonResponse({'success': True, 'items': items, 'campania': camp_meta})
    except Exception as e:
        logger.error(f"Error in api_get_items_campania: {e}", exc_info=True)
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

@login_required
@permission_required('recolector_receiving')
def recepcion(request):
    """Receiving / Entry Log"""
    return render(request, 'recoleccion/recepcion.html', {
        'username': getattr(request, 'user_data', {}).get('username'),
        'sid': request.sid
    })

@login_required
@permission_required('recolector_counting')
def save_recuento(request):
    """Save count (Adjust or Campaign Item)"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Solo POST'})
    
    try:
        data = json.loads(request.body)
        ent_id = getattr(request, 'user_data', {}).get('enterprise_id', 0)
        user_id = request.user_data['id']
        
        art_id = data.get('articulo_id')
        cantidad = float(data.get('cantidad', 0))
        camp_id = data.get('campania_id') # Optional: if working on a campaign
        item_id = data.get('item_id') # Optional: specific item row in campaign

        with get_db_cursor(dictionary=True) as cursor:
            # 1. Fetch current stock and valuation
            cursor.execute("""
                SELECT COALESCE(e.cantidad, 0) as stock, a.costo_reposicion as costo, a.nombre
                FROM stk_articulos a
                LEFT JOIN stk_existencias e ON a.id = e.articulo_id AND e.enterprise_id = %s
                WHERE a.id = %s AND a.enterprise_id = %s
                LIMIT 1
            """, (ent_id, art_id, ent_id))
            art_data = dictfetchone(cursor)
            
            if not art_data:
                return JsonResponse({'success': False, 'message': 'Artículo no encontrado'})

            stock_sistema = float(art_data['stock'])
            diferencia = cantidad - stock_sistema
            valor_ajuste = diferencia * float(art_data['costo'])

            # 2. If it's part of a campaign, update the campaign item
            if camp_id and item_id:
                codigo_escaneado = data.get('codigo_escaneado', '')
                es_forzado = 1 if data.get('es_forzado', False) else 0
                
                cursor.execute("""
                    UPDATE stk_items_inventario 
                    SET stock_fisico = %s, user_id = %s, updated_at = NOW(),
                        codigo_escaneado = %s, es_forzado = %s
                    WHERE id = %s AND inventario_id = %s
                """, (cantidad, user_id, codigo_escaneado, es_forzado, item_id, camp_id))
                
                # Send confirmation email
                try:
                    _send_count_email(
                        cursor, inv_id=camp_id, item_id=item_id,
                        art_nombre=art_data['nombre'], art_codigo=art_data['nombre'],
                        cantidad=cantidad, codigo_escaneado=codigo_escaneado,
                        es_forzado=es_forzado, user_id=user_id, ent_id=ent_id
                    )
                except Exception as mail_err:
                    logger.warning(f"Email send failed (non-critical): {mail_err}")
                
                return JsonResponse({
                    'success': True,
                    'message': 'Recuento guardado correctamente',
                    'es_forzado': bool(es_forzado),
                    'codigo_escaneado': codigo_escaneado
                })

            # 3. If it's a direct adjustment (default behavior)
            cursor.execute("""
                INSERT INTO stk_ajustes_pendientes 
                (enterprise_id, articulo_id, cantidad_sistema, cantidad_contada, diferencia, valor_ajuste, user_id, estado)
                VALUES (%s, %s, %s, %s, %s, %s, %s, 'PENDIENTE')
            """, (ent_id, art_id, stock_sistema, cantidad, diferencia, valor_ajuste, user_id))
            
            return JsonResponse({
                'success': True, 
                'message': 'Recuento enviado a aprobación',
                'valor': valor_ajuste,
                'diff': diferencia
            })
            
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})

@login_required
@permission_required('recolector_counting')
def close_campania(request, inv_id):
    """Close campaign and leave uncounted items pending"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Solo POST'})
    
    ent_id = getattr(request, 'user_data', {}).get('enterprise_id', 0)
    try:
        with get_db_cursor() as cursor:
            cursor.execute("""
                UPDATE stk_inventarios 
                SET estado = 'CERRADO', fecha_cierre = NOW() 
                WHERE id = %s AND enterprise_id = %s
            """, (inv_id, ent_id))
        return JsonResponse({'success': True, 'message': 'Campaña cerrada correctamente'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)
