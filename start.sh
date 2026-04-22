#!/bin/bash

# 1. Inicia o Webhook do n8n (Flask) em segundo plano
python webhook_n8n.py &

# 2. Inicia o Painel (Streamlit) em primeiro plano
streamlit run app.py --server.port=8501 --server.address=0.0.0.0
