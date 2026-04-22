from flask import Flask, request, jsonify
import pandas as pd
import requests
import dataframe_image as dfi
import base64
from datetime import datetime
import os
from PIL import Image, ImageDraw, ImageFont

app = Flask(__name__)

# ==========================================
# SUAS CONFIGURAÇÕES DA EVOLUTION E LOGOS
# ==========================================
URL_EVOLUTION = "https://mimo-evolution-api.3sbqz4.easypanel.host/message/sendMedia/teste"
CHAVE_API_EVOLUTION = "429683C4C977415CAAFCCE10F7D57E11"

MAPA_LOGOS = {
    "MELI": "logo_meli.png", "MERCADO LIVRE": "logo_meli.png", 
    "AMAZON": "logo_amazon.png", "ADORO": "logo_adoro.png", "AAM": "logo_aam.png"
}
MAPA_GRUPOS = {
    "MELI": "120363000000000000@g.us", "AMAZON": "120363000000000001@g.us", 
    "ADORO": "5511917623237", "AAM": "5511934773679"
}

# ==========================================
# FUNÇÕES DE DESENHO E ENVIO (As mesmas que já fizemos)
# ==========================================
def embutir_logos_na_imagem(img_path, cliente_nome):
    try:
        tabela_img = Image.open(img_path)
        largura_tabela, altura_tabela = tabela_img.size
        altura_cabecalho = 160
        nova_largura = max(largura_tabela, 800) 
        nova_img = Image.new('RGB', (nova_largura, altura_tabela + altura_cabecalho), 'white')
        
        x_tabela = (nova_largura - largura_tabela) // 2
        nova_img.paste(tabela_img, (x_tabela, altura_cabecalho))
        
        draw = ImageDraw.Draw(nova_img)
        texto_titulo = f"PROGRAMAÇÃO - {cliente_nome}"
        try:
            font = ImageFont.truetype("DejaVuSans-Bold.ttf", 32)
        except:
            font = ImageFont.load_default()

        w_texto = draw.textlength(texto_titulo, font=font)
        x_texto = (nova_largura - w_texto) // 2
        draw.text((x_texto, 100), texto_titulo, fill=(255, 0, 0), font=font)
        
        try:
            mimo = Image.open('logo_mimo.png')
            mimo.thumbnail((200, 80))
            nova_img.paste(mimo, (20, 20), mimo if mimo.mode == 'RGBA' else None)
        except: pass
        
        try:
            for chave, arquivo in MAPA_LOGOS.items():
                if chave in cliente_nome:
                    cliente_logo = Image.open(arquivo)
                    cliente_logo.thumbnail((160, 80))
                    nova_img.paste(cliente_logo, (nova_largura - 180, 20), cliente_logo if cliente_logo.mode == 'RGBA' else None)
                    break
        except: pass
        
        nova_img.save(img_path)
    except Exception as e:
        print(f"Erro montagem: {e}")

def enviar_evolution(imagem_path, nome_empresa, msg_texto):
    id_grupo = next((v for k, v in MAPA_GRUPOS.items() if k in nome_empresa), None)
    if not id_grupo: return False, "Destino não configurado"
    if "@c.us" in id_grupo: id_grupo = id_grupo.replace("@c.us", "")

    headers = {"Content-Type": "application/json", "apikey": CHAVE_API_EVOLUTION}
    try:
        with open(imagem_path, 'rb') as f:
            base64_data = base64.b64encode(f.read()).decode('ascii')
        
        payload = {"number": id_grupo, "mediatype": "image", "media": base64_data, "caption": msg_texto}
        resp = requests.post(URL_EVOLUTION, headers=headers, json=payload)
        return resp.status_code in [200, 201], resp.text
    except Exception as e: return False, str(e)

# ==========================================
# ROTA QUE RECEBE OS DADOS DO N8N
# ==========================================
@app.route('/n8n/gerar_escala', methods=['POST'])
def gerar_escala_n8n():
    dados = request.json
    cliente = str(dados.get('cliente', '')).upper()
    viagens = dados.get('viagens', [])
    data_str = datetime.now().strftime('%d/%m/%Y')

    if not cliente or not viagens:
        return jsonify({"erro": "Faltam dados de cliente ou viagens"}), 400

    # 1. Transforma o JSON do n8n em uma Tabela
    df = pd.DataFrame(viagens)
    
    # 2. Formata e gera a imagem cruzando os dados
    img_path = f"escala_auto_{cliente}.png"
    style = df.style.set_properties(**{'background-color': 'white', 'color': 'black', 'border': '1px solid black'})\
                    .set_table_styles([{'selector': 'th', 'props': [('background-color', '#FF0000'), ('color', 'white')]}])
    
    dfi.export(style, img_path, table_conversion="matplotlib")
    embutir_logos_na_imagem(img_path, cliente)

    # 3. Dispara
    msg = f"🚌 *Programação Fixa de Escala*\n🏢 *Cliente:* {cliente}\n📅 *Data:* {data_str}"
    sucesso, log = enviar_evolution(img_path, cliente, msg)

    if sucesso:
        return jsonify({"status": "sucesso", "cliente": cliente}), 200
    else:
        return jsonify({"status": "erro", "detalhe": log}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
