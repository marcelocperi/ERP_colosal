
import win32serviceutil
import win32service
import win32event
import servicemanager
import socket
import sys
import os
import subprocess
import datetime
import winreg

# Configuración
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
VENV_DIR = os.path.join(PROJECT_DIR, "venv")
PYTHON_EXE = os.path.join(VENV_DIR, "Scripts", "python.exe")
# Punto de entrada para el servidor Django
SCRIPT_PATH = os.path.join(PROJECT_DIR, "run_django.py")

class MultisyncService(win32serviceutil.ServiceFramework):
    _svc_name_ = "ERP_Colosal_Multisync"
    _svc_display_name_ = "ERP Colosal - Multisync"
    _svc_description_ = "Servicio de Produccion de Colosal ERP (Django + Waitress)"

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
        socket.setdefaulttimeout(60)
        self.process = None

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        if self.process:
            try:
                self.process.terminate()
            except:
                pass
        win32event.SetEvent(self.hWaitStop)

    def SvcDoRun(self):
        self.ReportServiceStatus(win32service.SERVICE_RUNNING)
        self.main()

    def main(self):
        try:
            log_dir = os.path.join(PROJECT_DIR, "logs")
            if not os.path.exists(log_dir):
                os.makedirs(log_dir)

            stdout_path = os.path.join(log_dir, "multisync_stdout.log")
            stderr_path = os.path.join(log_dir, "multisync_stderr.log")

            with open(stdout_path, "a", encoding='utf-8') as out, \
                 open(stderr_path, "a", encoding='utf-8') as err:
                
                now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                out.write(f"\n--- Iniciando Multisync Service a las {now_str} ---\n")
                out.flush()
                
                # Ejecutar el runner de Django
                self.process = subprocess.Popen([PYTHON_EXE, SCRIPT_PATH], 
                                             cwd=PROJECT_DIR,
                                             stdout=out,
                                             stderr=err,
                                             creationflags=subprocess.CREATE_NO_WINDOW)
                
                out.write(f"Proceso iniciado con PID: {self.process.pid}\n")
                out.flush()

                while self.process.poll() is None:
                    rc = win32event.WaitForSingleObject(self.hWaitStop, 5000)
                    if rc == win32event.WAIT_OBJECT_0:
                        break
        except Exception as e:
            servicemanager.LogErrorMsg(f"Error en el servicio Multisync: {str(e)}")
        
        if self.process and self.process.poll() is None:
            self.process.terminate()

def install_and_optimize():
    # Encontrar home_path para pythonservice.exe global
    home_path = ""
    cfg_path = os.path.join(VENV_DIR, "pyvenv.cfg")
    if os.path.exists(cfg_path):
        with open(cfg_path, 'r') as f:
            for line in f:
                if line.startswith('home ='):
                    home_path = line.split('=')[1].strip()
                    break
    
    global_host = os.path.join(home_path, "pythonservice.exe") if home_path else None
    
    # Registrar servicio
    win32serviceutil.HandleCommandLine(MultisyncService)
    
    if global_host and os.path.exists(global_host):
        # Optimizar registro
        key_path = f"SYSTEM\\CurrentControlSet\\Services\\{MultisyncService._svc_name_}"
        try:
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path, 0, winreg.KEY_SET_VALUE)
            winreg.SetValueEx(key, "ImagePath", 0, winreg.REG_EXPAND_SZ, f'"{global_host}"')
            winreg.CloseKey(key)
            
            # PYTHONPATH
            param_key = winreg.CreateKey(winreg.HKEY_LOCAL_MACHINE, f"{key_path}\\Parameters")
            extra_paths = [PROJECT_DIR, os.path.join(VENV_DIR, "Lib", "site-packages")]
            winreg.SetValueEx(param_key, "PythonPath", 0, winreg.REG_SZ, ";".join(extra_paths))
            winreg.CloseKey(param_key)
            print("[INFO] Servicio optimizado con éxito.")
        except Exception as e:
            print(f"[WARN] No se pudo optimizar el registro: {e}")

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1].lower() == 'install':
        install_and_optimize()
    else:
        win32serviceutil.HandleCommandLine(MultisyncService)
