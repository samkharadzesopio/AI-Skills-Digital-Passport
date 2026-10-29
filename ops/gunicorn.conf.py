"""Portable web-process configuration; terminate HTTPS at the trusted gateway."""
import os

bind = '127.0.0.1:' + os.environ.get('PORT', '8000')
workers = int(os.environ.get('WEB_CONCURRENCY', '2'))
timeout = 30
graceful_timeout = 30
limit_request_line = 4094
# Browser headers plus Vercel/Render proxy metadata need Gunicorn's standard allowance.
limit_request_fields = 100
limit_request_field_size = 4096
# URL paths can contain public credential references. Do not create raw access logs.
accesslog = None
errorlog = '-'
capture_output = False

# The application does not need Gunicorn's optional administrative control socket.
control_socket_disable = True
