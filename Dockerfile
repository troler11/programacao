# 1. Usa uma imagem oficial e leve do Python
FROM python:3.10-slim

# 2. Define a pasta de trabalho dentro do servidor/container
WORKDIR /app

# 3. Instala dependências do Linux necessárias (Nomes atualizados)
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# 4. Copia o arquivo de requisitos primeiro
COPY requirements.txt .

# 5. Instala as bibliotecas do Python listadas no requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# 6. Copia todo o resto dos seus arquivos
COPY . .

# 7. Informa ao servidor que o Streamlit usará a porta 8501
EXPOSE 8501

# 8. O comando que o servidor vai rodar para ligar o seu site
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
