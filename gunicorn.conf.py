"""Unico profilo di avvio per Render, Docker e installazioni native."""
import os

bind = '0.0.0.0:' + os.environ.get('PORT', '5001')
# Un solo processo inizializza schema e default; i thread servono richieste concorrenti.
workers = 1
threads = 4
timeout = 120
graceful_timeout = 30
keepalive = 5
accesslog = '-'
errorlog = '-'
capture_output = True
