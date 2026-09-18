import multiprocessing
import os

bind = "0.0.0.0:8000"
workers = int(os.environ.get("WORKER_COUNT", multiprocessing.cpu_count() * 2 + 1))
worker_class = "gthread"
threads = int(os.environ.get("WORKER_THREADS", 4))
timeout = 60
graceful_timeout = 30
keepalive = 5
max_requests = 2000
max_requests_jitter = 200
accesslog = "-"
errorlog = "-"
loglevel = os.environ.get("LOG_LEVEL", "info").lower()
access_log_format = '%(h)s "%(r)s" %(s)s %(b)s %(L)ss "%(a)s" rid=%({x-request-id}o)s'
forwarded_allow_ips = os.environ.get("FORWARDED_ALLOW_IPS", "127.0.0.1")
limit_request_line = 4094
limit_request_fields = 100
