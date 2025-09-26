import os

os.makedirs('logs', exist_ok=True)

bind = '0.0.0.0:8000'
workers = 10
accesslog = './logs/access.log'
timeout = 3000
