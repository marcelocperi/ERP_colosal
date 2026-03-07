import os
import sys

# Añadir el directorio del proyecto al path
sys.path.append(os.path.join(os.getcwd(), 'django_app'))

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'colosal_django.settings')
import django
django.setup()

from django.db import connection

def inscribir():
    sugerencias = [
        "Migración Quart -> Django: Se detectó que el parser de templates de Django es estricto con las etiquetas multilineales. Se deben evitar saltos de línea dentro de {% if %}, {% for %}, etc.",
        "Seguridad de Sesión: Se implementó el mecanismo de bind_cookie para persistencia de tab affinity. Verificar que el JS en base.html cargue correctamente.",
        "Corrección de Datos Fiscales: Se reemplazó la consulta a la tabla inexistente sys_condiciones_fiscales por una lista estática de condiciones AFIP estándar."
    ]
    
    with connection.cursor() as cursor:
        # Primero ver columnas
        cursor.execute("DESCRIBE sys_proyectos_requerimientos")
        columns = [col[0] for col in cursor.fetchall()]
        print(f"Columnas detectadas: {columns}")
        
        # Asumimos una estructura básica: titulo, descripcion, estado
        # Intentamos insertar
        for sug in sugerencias:
            try:
                # Ajustamos según las columnas comunes en este sistema
                if 'requerimiento' in columns:
                    cursor.execute("INSERT INTO sys_proyectos_requerimientos (requerimiento, estado) VALUES (%s, 'PENDIENTE')", [sug])
                elif 'descripcion' in columns:
                    cursor.execute("INSERT INTO sys_proyectos_requerimientos (descripcion, estado) VALUES (%s, 'PENDIENTE')", [sug])
                else:
                    print(f"No se pudo determinar columna para insertar: {sug}")
            except Exception as e:
                print(f"Error al insertar sugerencia: {e}")
        
    print("Proceso finalizado.")

if __name__ == "__main__":
    inscribir()
