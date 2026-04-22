# Usa uma versão leve do Python
FROM python:3.10-slim

# Define a pasta de trabalho lá dentro
WORKDIR /app

# Instala bibliotecas do sistema necessárias para compilar imagens
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copia e instala as dependências do Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia todo o resto do seu projeto (app.py, logos, fonte)
COPY . .

# Libera a porta principal do Painel
EXPOSE 8501

# Comando final com proteção CORS e XSRF desativadas, e modo headless ativado
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0", "--server.enableCORS=false", "--server.enableXsrfProtection=false", "--server.headless=true"]
