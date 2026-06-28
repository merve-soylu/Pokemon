from datetime import datetime

def log(level, msg, site=None):
    now = datetime.now().strftime("%H:%M:%S")
    if site:
        print(f"[{now}] [{level}] [{site}] {msg}")
    else:
        print(f"[{now}] [{level}] {msg}")

def banner():
    print("""
========================================
        Pokemon Tracker Pro v2
========================================
""")