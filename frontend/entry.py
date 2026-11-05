import os
import sys
import webbrowser
import threading
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
django.setup()

from django.core.wsgi import get_wsgi_application
from waitress import serve

application = get_wsgi_application()

def open_browser():
    time.sleep(2)
    webbrowser.open('http://127.0.0.1:8000')

if __name__ == "__main__":
    print("=" * 50)
    print("🏛️ نظام إدارة المكتب الحكومي")
    print("🚀 الخادم يعمل على http://127.0.0.1:8000")
    print("📋 اضغط Ctrl+C لإيقاف الخادم")
    print("=" * 50)
    threading.Thread(target=open_browser, daemon=True).start()
    serve(application, host='127.0.0.1', port=8000)
