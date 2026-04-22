from flask import Flask, request, jsonify
import pandas as pd
import requests
import dataframe_image as dfi
import base64
from datetime import datetime
import os
from PIL import Image, ImageDraw, ImageFont

app = Flask(__name__)

# === CONFIGURAÇÕES DA EVOLUTION ===
URL_EVOLUTION = "https://mimo-evolution-api.3sbqz4.easypanel.host/message/sendMedia/teste"
CHAVE_API_EVOLUTION = "429683C4C977415CAAFCCE10F7D57E11"

MAPA_LOGOS = {
    "MELI": "logo_meli.png", "MERCADO LIVRE": "logo_meli.png", 
    "AMAZON": "logo_amazon.png", "ADORO": "logo_adoro.png", "AAM": "logo_aam.png"
}
MAPA_GRUPOS = {
    "MELI": "120363000000000000@g.us", 
    "AMAZON": "120363000000000001@g.us", 
    "ADORO": "5511917623237", 
    "AAM": "5511934773679"
}

def montar_imagem_com_logos(img_path, cliente_nome):
    try:
        tabela_img = Image.open(img_path)
        largura_tabela, altura_tabela = tabela_img.size
        altura_cabecalho = 160
        nova_largura = max(largura_tabela, 800)
        
        nova_img = Image.new('RGB', (nova_largura, altura_tabela + altura_cabecalho), 'white')
        nova_img.paste(tabela_img, ((nova_largura - largura_tabela) // 2, altura_cabecalho))
        
        draw = ImageDraw.Draw(nova_img)
        texto = f"PROGRAMAÇÃO - {cliente_nome}"
        try:
            font = ImageFont.truetype("DejaVuSans-Bold.ttf", 32)
        except:
            font = ImageFont.load_default()
            
        w_texto = draw.textlength(texto, font=font)
        draw.text(((nova_largura - w_texto) // 2, 100), texto, fill=(255, 0, 0), font=font)
        
        # Logos Mimo e Cliente
        try:
            mimo = Image.open('logo_mimo.png')
            mimo.thumbnail((200, 80))
            nova_img.paste(mimo, (20, 20), mimo if mimo.mode == 'RGBA' else None)
            
            for chave, arq in MAPA_LOGOS.items():
                if chave in cliente_nome:
                    c_logo = Image.open(arq)
                    c_logo.thumbnail((160, 80))
                    nova_img.paste(c_logo, (nova_largura - 180, 20), c_logo if c_logo.mode == 'RGBA' else None)
                    break
        except: pass
        nova_img.save(img_path)
    except Exception as e: print(f"Erro montagem: {e}")

@app.route('/render_e_enviar', methods=['POST'])
def webhook_render():
    dados = request.json
    cliente = dados.get('cliente', '').upper()
    linhas_da_planilha = dados.get('viagens', []) # Dados vindos do Sheets via n8n
    
    if not cliente or not linhas_da_planilha:
        return jsonify({"erro": "Dados vazios"}), 400

    # 1. Transforma os dados do Sheets em Imagem
    df = pd.DataFrame(linhas_da_planilha)
    
    # Remove colunas desnecessárias que o Sheets possa enviar
    cols_desejadas = ['ENT', 'INI', 'LINHA', 'CLIENTE', 'FROTA FINAL', 'MOTORISTA']
    df = df[[c for c in cols_desejadas if c in df.columns]]

    img_path = f"temp_escala.png"
    style = df.style.set_properties(**{'background-color': 'white', 'color': 'black', 'border': '1px solid black'})\
                    .set_table_styles([{'selector': 'th', 'props': [('background-color', '#FF0000'), ('color', 'white')]}])
    
    dfi.export(style, img_path, table_conversion="matplotlib")
    montar_imagem_com_logos(img_path, cliente)

    # 2. Envio Evolution (O formato que funcionou)
    try:
        with open(img_path, 'rb') as f:
            b64 = base64.b64encode(f.read()).decode('ascii')
        
        id_grupo = MAPA_GRUPOS.get(cliente)
        payload = {
            "number": id_grupo,
            "mediatype": "image",
            "media": b64,
            "caption": f"🚌 *Escala de Linhas*\n🏢 *Cliente:* {cliente}\n📅 *Data:* {datetime.now().strftime('%d/%m/%Y')}"
        }
        requests.post(URL_EVOLUTION, headers={"apikey": CHAVE_API_EVOLUTION, "Content-Type": "application/json"}, json=payload)
        return jsonify({"status": "OK"}), 200
    except Exception as e:
        return jsonify({"erro": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
