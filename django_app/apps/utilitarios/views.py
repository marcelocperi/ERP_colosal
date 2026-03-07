import json
import subprocess
import sys
import os
import datetime
import threading
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.contrib import messages
from apps.core.decorators import login_required
from apps.core.db import get_db_cursor, dictfetchall, dictfetchone


def calcular_proxima_ejecucion(frecuencia, planificacion_str):
    """Calcula la próxima ejecución a partir de ahora según la planificación."""
    try:
        now = datetime.datetime.now()
        plan = json.loads(planificacion_str) if isinstance(planificacion_str, str) else planificacion_str
        if not plan:
            return None

        if frecuencia == 'semanal' and plan.get('days'):
            days = [int(d) for d in plan['days']]
            hour, minute = map(int, plan.get('hour', '00:00').split(':'))
            for offset in range(0, 8):
                candidate = now + datetime.timedelta(days=offset)
                if candidate.isoweekday() in days:
                    candidate = candidate.replace(hour=hour, minute=minute, second=0, microsecond=0)
                    if candidate > now:
                        return candidate.strftime('%Y-%m-%d %H:%M:%S')

        elif frecuencia == 'diaria' and plan.get('hour'):
            hour, minute = map(int, plan['hour'].split(':'))
            candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if candidate <= now:
                candidate += datetime.timedelta(days=1)
            return candidate.strftime('%Y-%m-%d %H:%M:%S')

        elif frecuencia == 'minutos' and plan.get('minutes'):
            mins = int(plan['minutes'])
            candidate = now + datetime.timedelta(minutes=mins)
            return candidate.strftime('%Y-%m-%d %H:%M:%S')

    except Exception:
        pass
    return None


@login_required
def gestor_crons(request):
    with get_db_cursor() as cursor:
        cursor.execute(
            "SELECT * FROM sys_crons WHERE enterprise_id = %s OR enterprise_id = 0 ORDER BY id DESC",
            [request.user_data['enterprise_id']]
        )
        crons = dictfetchall(cursor)

    now = datetime.datetime.now()
    for cron in crons:
        proxima = cron.get('proxima_ejecucion')
        if proxima is None or (isinstance(proxima, datetime.datetime) and proxima < now):
            cron['proxima_ejecucion'] = calcular_proxima_ejecucion(
                cron.get('frecuencia'), cron.get('planificacion')
            )
        # Serializar fechas para JSON en template
        for key, val in list(cron.items()):
            if isinstance(val, (datetime.date, datetime.datetime)):
                cron[key] = val.isoformat()

    day_choices = [
        ('Lun', 1), ('Mar', 2), ('Mié', 3), ('Jue', 4),
        ('Vie', 5), ('Sáb', 6), ('Dom', 7)
    ]
    return render(request, 'utilitarios/crons.html', {'crons': crons, 'day_choices': day_choices})


@login_required
def run_cron(request, cron_id):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido'}, status=405)

    with get_db_cursor() as cursor:
        cursor.execute(
            "SELECT * FROM sys_crons WHERE id = %s AND (enterprise_id = %s OR enterprise_id = 0)",
            [cron_id, request.user_data['enterprise_id']]
        )
        cron = dictfetchone(cursor)

    if not cron:
        return JsonResponse({'success': False, 'error': 'Cron no encontrado'}, status=404)

    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    start_time = datetime.datetime.now()

    with get_db_cursor() as cursor:
        cursor.execute(
            "INSERT INTO sys_crons_logs (cron_id, fecha_inicio, status, resultado) VALUES (%s, %s, %s, %s)",
            [cron_id, start_time, 'exito', 'Iniciando ejecución forzada...']
        )
        log_id = cursor.lastrowid

    def _run_in_thread():
        try:
            cmd = cron['comando'].split()
            env = os.environ.copy()
            env['CRON_UI_MODE'] = '1'
            result = subprocess.run(
                [sys.executable] + cmd[1:] if cmd[0] in ('python', 'python3') else cmd,
                cwd=project_root,
                capture_output=True, text=True, timeout=300, encoding='utf-8', env=env
            )
            end_time = datetime.datetime.now()
            status = 'exito' if result.returncode == 0 else 'error'
            output = (result.stdout or '') + (result.stderr or '')
            proxima = calcular_proxima_ejecucion(cron['frecuencia'], cron['planificacion'])
            with get_db_cursor() as c:
                c.execute(
                    "UPDATE sys_crons_logs SET fecha_fin=%s, status=%s, resultado=%s WHERE id=%s",
                    [end_time, status, output[:2000] or 'Sin salida', log_id]
                )
                c.execute(
                    "UPDATE sys_crons SET ultima_ejecucion=%s, proxima_ejecucion=%s WHERE id=%s",
                    [end_time, proxima, cron_id]
                )
        except Exception as ex:
            with get_db_cursor() as c:
                c.execute(
                    "UPDATE sys_crons_logs SET fecha_fin=%s, status=%s, resultado=%s WHERE id=%s",
                    [datetime.datetime.now(), 'error', str(ex), log_id]
                )

    t = threading.Thread(target=_run_in_thread, daemon=True)
    t.start()
    return JsonResponse({'success': True, 'log_id': log_id, 'message': 'Cron iniciado en background'})


@login_required
def get_cron_logs(request, cron_id):
    with get_db_cursor() as cursor:
        cursor.execute(
            "SELECT * FROM sys_crons_logs WHERE cron_id = %s ORDER BY fecha_inicio DESC LIMIT 50",
            [cron_id]
        )
        logs = dictfetchall(cursor)

    for log in logs:
        if log.get('fecha_inicio') and isinstance(log['fecha_inicio'], datetime.datetime):
            log['fecha_inicio'] = log['fecha_inicio'].strftime("%Y-%m-%d %H:%M:%S")
        if log.get('fecha_fin') and isinstance(log['fecha_fin'], datetime.datetime):
            log['fecha_fin'] = log['fecha_fin'].strftime("%Y-%m-%d %H:%M:%S")

    return JsonResponse(logs, safe=False)


@login_required
def save_cron(request):
    if request.method != 'POST':
        return redirect('utilitarios:gestor_crons')

    cron_id = request.POST.get('id')
    nombre = request.POST.get('nombre')
    descripcion = request.POST.get('descripcion')
    comando = request.POST.get('comando')
    frecuencia = request.POST.get('frecuencia') or 'diaria'

    planificacion = {
        'days': request.POST.getlist('days[]'),
        'hour': request.POST.get('hour'),
        'minutes': request.POST.get('minutes')
    }
    proxima = calcular_proxima_ejecucion(frecuencia, planificacion)

    with get_db_cursor() as cursor:
        if cron_id:
            cursor.execute("""
                UPDATE sys_crons
                SET nombre=%s, descripcion=%s, comando=%s, frecuencia=%s, planificacion=%s, proxima_ejecucion=%s
                WHERE id=%s AND (enterprise_id=%s OR enterprise_id=0)
            """, [nombre, descripcion, comando, frecuencia, json.dumps(planificacion), proxima, cron_id,
                  request.user_data['enterprise_id']])
        else:
            cursor.execute("""
                INSERT INTO sys_crons (nombre, descripcion, comando, frecuencia, planificacion, proxima_ejecucion, enterprise_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, [nombre, descripcion, comando, frecuencia, json.dumps(planificacion), proxima,
                  request.user_data['enterprise_id']])

    messages.success(request, "Cron guardado correctamente")
    return redirect('utilitarios:gestor_crons')


@login_required
def delete_cron(request, cron_id):
    if request.method != 'POST':
        return JsonResponse({'success': False}, status=405)

    with get_db_cursor() as cursor:
        cursor.execute(
            "DELETE FROM sys_crons WHERE id=%s AND (enterprise_id=%s OR enterprise_id=0)",
            [cron_id, request.user_data['enterprise_id']]
        )
    return JsonResponse({'success': True})
