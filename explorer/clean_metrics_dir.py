import os

import psutil

process_names = ["python", "gunicorn", "celery"]
app_pids = []

for proc in psutil.process_iter():
    for process_name in process_names:
        if process_name in proc.name():
            app_pids.append(proc.pid)


cwd = os.getcwd()
os.chdir('metrics')
for file in os.listdir():
    if not (any([f'_{pid}.' in file for pid in app_pids]) or '_.' in file):
        os.remove(file)
