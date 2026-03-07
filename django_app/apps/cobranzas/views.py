import urllib.parse
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.urls import reverse
from apps.core.decorators import login_required
from apps.core.db import get_db_cursor, dictfetchall, dictfetchone

@login_required
def dashboard(request):
    try:
        enterprise_id = request.user_data['enterprise_id']
        with get_db_cursor() as cursor:
            # 1. Total Adeudado por Clientes
            cursor.execute("""
                SELECT
                    SUM(CASE 
                        WHEN c.tipo_comprobante IN ('001','002','006','007','011','012','005','010','015') THEN c.importe_total
                        WHEN c.tipo_comprobante IN ('003','008','013') THEN -c.importe_total
                        ELSE 0
                    END) as total_facturado,
                    (SELECT COALESCE(SUM(importe), 0) FROM fin_recibos_detalles JOIN fin_recibos ON fin_recibos_detalles.recibo_id = fin_recibos.id WHERE fin_recibos.enterprise_id = %s AND fin_recibos.tercero_id = c.tercero_id) as total_pagado
                FROM erp_comprobantes c
                JOIN erp_terceros t ON c.tercero_id = t.id AND t.es_cliente = 1
                WHERE c.enterprise_id = %s AND c.modulo IN ('VEN','VENTAS')
            """, [enterprise_id, enterprise_id])
            data_debt = dictfetchone(cursor)
            
            facturado = float(data_debt.get('total_facturado') or 0)
            pagado = float(data_debt.get('total_pagado') or 0)
            adeudado_total = facturado - pagado
            
            # 2. Ultimos Recibos
            cursor.execute("""
                SELECT r.id, r.fecha, r.numero, r.punto_venta, r.monto_total, c.nombre as cliente_nombre
                FROM fin_recibos r
                JOIN erp_terceros c ON r.tercero_id = c.id
                WHERE r.enterprise_id = %s
                ORDER BY r.fecha DESC, r.id DESC
                LIMIT 5
            """, [enterprise_id])
            ultimos_recibos = dictfetchall(cursor)
            
            # KPI
            kpis = {
                'adeudado': adeudado_total,
                'recibos_mes': len(ultimos_recibos)
            }
            
        return render(request, 'cobranzas/dashboard.html', {'kpis': kpis, 'ultimos_recibos': ultimos_recibos})
    except Exception as e:
        messages.error(request, f"Error en Dashboard Cobranzas: {str(e)}")
        return redirect('home')

@login_required
def cuenta_corriente(request):
    # This just redirects to the ventas global CC that already works, or we can copy it later.
    return redirect('ventas:cuenta_corriente_global')

@login_required
def listar_recibos(request):
    enterprise_id = request.user_data['enterprise_id']
    with get_db_cursor() as cursor:
        cursor.execute("""
            SELECT r.*, t.nombre as tercero_nombre, t.cuit as tercero_cuit
            FROM fin_recibos r
            JOIN erp_terceros t ON r.tercero_id = t.id
            WHERE r.enterprise_id = %s
            ORDER BY r.fecha DESC, r.id DESC
            LIMIT 200
        """, [enterprise_id])
        recibos = dictfetchall(cursor)
    return render(request, 'cobranzas/lista_recibos.html', {'recibos': recibos})

@login_required
def emitir_recibo(request):
    enterprise_id = request.user_data['enterprise_id']
    if request.method == 'POST':
        cliente_id = request.POST.get('cliente_id')
        fecha = request.POST.get('fecha')
        punto_venta = request.POST.get('punto_venta', 1)
        observaciones = request.POST.get('observaciones', '')
        
        # Collect chosen invoices
        facturas = []
        for key, value in request.POST.items():
            if key.startswith('pagar_factura_'):
                if value == 'on' or value == '1':
                    factura_id = key.replace('pagar_factura_', '')
                    monto_pagar = request.POST.get(f'monto_factura_{factura_id}', 0)
                    facturas.append({'id': factura_id, 'monto': float(monto_pagar)})
        
        if not facturas:
            messages.error(request, "Debe seleccionar al menos un comprobante a cobrar.")
            return redirect('cobranzas:emitir_recibo')
            
        total_pago = sum([f['monto'] for f in facturas])
        
        try:
            with get_db_cursor() as cursor:
                # Generar numero de recibo (Maximo + 1)
                cursor.execute("SELECT MAX(numero) as max_num FROM fin_recibos WHERE enterprise_id = %s AND punto_venta = %s", [enterprise_id, punto_venta])
                max_res = dictfetchone(cursor)
                nuevo_numero = (max_res.get('max_num') or 0) + 1
                
                # Insertar Recibo
                cursor.execute("""
                    INSERT INTO fin_recibos (enterprise_id, punto_venta, numero, fecha, tercero_id, monto_total, observaciones, estado, user_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, 'EMITIDO', %s)
                """, [enterprise_id, punto_venta, nuevo_numero, fecha, cliente_id, total_pago, observaciones, request.user_data['id']])
                
                cursor.execute("SELECT LAST_INSERT_ID() as new_id")
                recibo_id = dictfetchone(cursor)['new_id']
                
                # Insertar Detalles
                for fact in facturas:
                    cursor.execute("""
                        INSERT INTO fin_recibos_detalles (recibo_id, factura_id, importe, user_id)
                        VALUES (%s, %s, %s, %s)
                    """, [recibo_id, fact['id'], fact['monto'], request.user_data['id']])
                    
                messages.success(request, f"¡Recibo N° {punto_venta:04d}-{nuevo_numero:08d} generado exitosamente por $ {total_pago:,.2f}!")
                return redirect('cobranzas:listar_recibos')
                
        except Exception as e:
            messages.error(request, f"Error al emitir recibo: {str(e)}")
            return redirect('cobranzas:emitir_recibo')

    # GET: Mostrar formulario de cobro
    cliente_id = request.GET.get('cliente_id')
    clientes = []
    facturas_pendientes = []
    with get_db_cursor() as cursor:
        cursor.execute("SELECT id, nombre, cuit FROM erp_terceros WHERE enterprise_id = %s AND es_cliente = 1 ORDER BY nombre", [enterprise_id])
        clientes = dictfetchall(cursor)
        
        if cliente_id:
            # Buscar facturas pendientes (Facturas - Pagado - NC)
            cursor.execute("""
                SELECT c.id, c.fecha_emision, c.tipo_comprobante, c.punto_venta, c.numero, c.importe_total, 
                (SELECT COALESCE(SUM(importe),0) FROM fin_recibos_detalles WHERE factura_id = c.id) as pagado,
                (SELECT COALESCE(SUM(importe_total),0) FROM erp_comprobantes WHERE comprobante_asociado_id = c.id AND tipo_comprobante IN ('003','008','013')) as notas_credito
                FROM erp_comprobantes c
                WHERE c.enterprise_id = %s AND c.tercero_id = %s AND c.modulo IN ('VEN', 'VENTAS')
                AND c.tipo_comprobante IN ('001','002','006','007','011','012','005','010','015')
                HAVING (c.importe_total - pagado - notas_credito) > 0.01
                ORDER BY c.fecha_emision ASC
            """, [enterprise_id, cliente_id])
            comprobantes = dictfetchall(cursor)
            for comp in comprobantes:
                comp['saldo'] = float(comp['importe_total']) - float(comp['pagado']) - float(comp['notas_credito'])
                facturas_pendientes.append(comp)
            
    return render(request, 'cobranzas/emitir_recibo.html', {'clientes': clientes, 'cliente_id': cliente_id, 'facturas': facturas_pendientes})

@login_required
def listar_ordenes_cobro(request):
    # Placeholder for ordenes_cobro (payment requests sent to clients)
    return render(request, 'cobranzas/ordenes_cobro.html', {})
