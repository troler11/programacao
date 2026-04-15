# 1. Usa uma imagem oficial e leve do Python
FROM python:3.10-slim

# 2. Define a pasta de trabalho dentro do servidor/container
WORKDIR /app

# 3. Instala dependências do Linux necessárias para gerar a imagem da tabela
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# 4. Copia o arquivo de requisitos primeiro (ajuda a deixar o processo mais rápido)
COPY requirements.txt .

# 5. Instala as bibliotecas do Python listadas no requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# 6. Copia todo o resto dos seus arquivos (app.py, imagens dos logos, etc)
COPY . .

# 7. Informa ao servidor que o Streamlit usará a porta 8501
EXPOSE 8501

# 8. O comando que o servidor vai rodar para ligar o seu site
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
