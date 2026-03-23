import time

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False


def collect() -> dict:
    if not HAS_PSUTIL:
        return {
            "cpu_percent": None,
            "memory_percent": None,
            "disk_percent": None,
            "load_avg_1m": None,
            "uptime_seconds": None,
        }

    cpu = psutil.cpu_percent(interval=0.5)
    mem = psutil.virtual_memory().percent
    disk = psutil.disk_usage("/").percent

    try:
        load_avg = psutil.getloadavg()[0]
    except (AttributeError, OSError):
        load_avg = None

    try:
        boot_time = psutil.boot_time()
        uptime = int(time.time() - boot_time)
    except Exception:
        uptime = None

    return {
        "cpu_percent": cpu,
        "memory_percent": mem,
        "disk_percent": disk,
        "load_avg_1m": load_avg,
        "uptime_seconds": uptime,
    }
