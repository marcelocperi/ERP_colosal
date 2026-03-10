---
description: how to start the django development server
---

# Start Django Server with Waitress (Multi-threaded, No Freeze)

Use Waitress instead of `runserver` on Windows to avoid single-thread freezes.

// turbo
1. Kill any existing server on port 8001:
```powershell
Stop-Process -Id (Get-NetTCPConnection -LocalPort 8001 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess) -Force -ErrorAction SilentlyContinue
```

// turbo
2. Start Waitress (4 threads, port 8001):
```powershell
cd c:\Users\marce\Documents\GitHub\Colosal\django_app
..\venv\Scripts\waitress-serve --host=0.0.0.0 --port=8001 --threads=4 colosal_django.wsgi:application
```

> **Why Waitress?**  
> Django `runserver` on Windows is single-threaded — one blocked request (e.g. mobile camera or slow query) freezes the whole server.  
> Waitress is multi-threaded and designed for Windows; 4 threads handle concurrent mobile + desktop requests without freezing.
