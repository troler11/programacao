FROM python:3.10-slim

WORKDIR /app

# Sua instalação de dependências básicas
RUN apt-get update && apt-get install -y build-essential && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Instala os pacotes do Python (o playwright precisa estar no seu requirements.txt)
RUN pip install --no-cache-dir -r requirements.txt

# ==========================================
# ADICIONADO: Instalação do Navegador
# ==========================================
# Baixa o Chromium
RUN playwright install chromium
# Instala as dependências do Linux necessárias para o Chromium não travar no modo slim
RUN playwright install-deps chromium

COPY . .

# Expõe a porta 5000 que é o padrão de APIs
EXPOSE 5000

CMD ["python", "app.py"]
