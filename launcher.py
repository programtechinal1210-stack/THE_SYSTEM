"""THE_SYSTEM desktop launcher for development and packaged Windows installs."""
import json
import os
import secrets
import socket
import subprocess
import sys
import time
import webbrowser
from datetime import datetime
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parent
DEV_SERVICES = (
    (8001, "http://127.0.0.1:8001/health", ["-m", "uvicorn", "api.main:app", "--host", "127.0.0.1", "--port", "8001"], ROOT / "backend"),
    (8000, "http://127.0.0.1:8000/health/", ["manage.py", "runserver", "127.0.0.1:8000", "--noreload"], ROOT / "frontend"),
)
SERVICES = DEV_SERVICES


def is_frozen():
    return bool(getattr(sys, "frozen", False))


def runtime_root(environment=None):
    environment = environment or os.environ
    explicit = environment.get("THE_SYSTEM_DATA_ROOT")
    if explicit:
        return Path(explicit).expanduser().resolve()
    program_data = environment.get("PROGRAMDATA")
    if not program_data:
        raise RuntimeError("تعذر تحديد PROGRAMDATA لتخزين بيانات النظام.")
    return Path(program_data) / "THE_SYSTEM"


def ensure_runtime_layout(root):
    paths = {name: root / name for name in ("data", "config", "license", "backups", "logs", "runtime", "media")}
    for path in paths.values():
        path.mkdir(parents=True, exist_ok=True)
    return paths


def load_or_create_secrets(config_dir):
    path = config_dir / "runtime-secrets.json"
    if path.exists():
        payload = json.loads(path.read_text(encoding="utf-8"))
    else:
        payload = {"secret_key": secrets.token_urlsafe(48), "jwt_secret_key": secrets.token_urlsafe(48), "created_at": datetime.now().astimezone().isoformat()}
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(path)
    if not payload.get("secret_key") or not payload.get("jwt_secret_key"):
        raise RuntimeError("ملف أسرار التشغيل غير صالح.")
    return payload


def packaged_services(binary_dir):
    return (
        (8001, "http://127.0.0.1:8001/health", binary_dir / "THE_SYSTEM_Backend.exe"),
        (8000, "http://127.0.0.1:8000/health/", binary_dir / "THE_SYSTEM_Frontend.exe"),
    )


def packaged_environment(root, paths):
    runtime_secrets = load_or_create_secrets(paths["config"])
    environment = os.environ.copy()
    environment.update({
        "APP_ENV": "production", "DEBUG": "false", "DJANGO_DEBUG": "false",
        "DJANGO_ALLOWED_HOSTS": "127.0.0.1,localhost", "SECRET_KEY": runtime_secrets["secret_key"],
        "DJANGO_SECRET_KEY": runtime_secrets["secret_key"], "JWT_SECRET_KEY": runtime_secrets["jwt_secret_key"],
        "DATABASE_URL": f"sqlite+aiosqlite:///{(paths['data'] / 'core.db').as_posix()}",
        "DJANGO_DATABASE_PATH": str(paths["data"] / "frontend.db"), "THE_SYSTEM_DATA_ROOT": str(root),
        "MEDIA_ROOT": str(paths["media"]), "UPLOAD_ROOT": str(paths["media"]),
        "API_BASE_URL": "http://127.0.0.1:8001/api/v1", "PYTHONUTF8": "1",
    })
    return environment


def require_system_python():
    if sys.prefix != sys.base_prefix:
        raise RuntimeError("شغّل النظام باستخدام Python النظام مباشرة؛ بيئات venv غير مدعومة.")


def require_free_ports(ports):
    for port in ports:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            try:
                probe.bind(("127.0.0.1", port))
            except OSError as exc:
                raise RuntimeError(f"المنفذ {port} مستخدم بالفعل؛ لن تبدأ نسخة أخرى أو تتصل بقاعدة بياناتها.") from exc


def wait_until_healthy(url, process, timeout=45):
    deadline = time.monotonic() + timeout
    last_error = "لم يستجب بعد"
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"توقفت الخدمة قبل الجاهزية (رمز الخروج {process.returncode}): {url}")
        try:
            with urlopen(url, timeout=1) as response:
                if response.status == 200:
                    return
                last_error = f"HTTP {response.status}"
        except (OSError, URLError) as exc:
            last_error = str(exc)
        time.sleep(0.25)
    raise RuntimeError(f"انتهت مهلة فحص الجاهزية للخدمة {url}: {last_error}")


def main():
    try:
        services = packaged_services(ROOT) if is_frozen() else DEV_SERVICES
        if not is_frozen():
            require_system_python()
        require_free_ports(service[0] for service in services)
    except RuntimeError as exc:
        print(f"THE_SYSTEM لم يبدأ: {exc}", file=sys.stderr)
        return 2
    if is_frozen():
        try:
            root = runtime_root()
            paths = ensure_runtime_layout(root)
            environment = packaged_environment(root, paths)
        except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
            print(f"THE_SYSTEM لم يجهز بيئة التشغيل: {exc}", file=sys.stderr)
            return 2
    else:
        environment = os.environ.copy()
        environment.setdefault("API_BASE_URL", "http://127.0.0.1:8001/api/v1")
        environment.setdefault("DJANGO_DEBUG", "true")
        environment.setdefault("PYTHONUTF8", "1")
    processes = []
    try:
        if is_frozen():
            for _, _, executable in services:
                if not executable.is_file():
                    raise RuntimeError(f"ملف خدمة مفقود: {executable.name}")
                processes.append(subprocess.Popen([str(executable)], cwd=ROOT, env=environment, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)))
        else:
            for _, _, arguments, directory in services:
                processes.append(subprocess.Popen([sys.executable, *arguments], cwd=directory, env=environment, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)))
        for service, process in zip(services, processes):
            wait_until_healthy(service[1], process)
        webbrowser.open("http://127.0.0.1:8000/auth/login/")
        while all(process.poll() is None for process in processes):
            time.sleep(0.5)
        print("إحدى الخدمتين توقفت؛ أُوقف المشغّل لتفادي تشغيل جزئي.", file=sys.stderr)
        return 1
    except RuntimeError as exc:
        print(f"THE_SYSTEM لم يكتمل إقلاعه: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 0
    finally:
        for process in processes:
            if process.poll() is None:
                process.terminate()
        for process in processes:
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


if __name__ == "__main__":
    sys.exit(main())
