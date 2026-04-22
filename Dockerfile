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

# Copia todo o resto do seu projeto (app.py, webhook_n8n.py, logos, fonte)
COPY . .

# Dá permissão para o Linux executar o arquivo de arranque
RUN chmod +x start.sh

# Libera as duas portas (Painel e Webhook)
EXPOSE 8501
EXPOSE 5000

# Comando final que liga tudo
CMD ["./start.sh"]
