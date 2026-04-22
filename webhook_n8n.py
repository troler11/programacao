from flask import Flask, request, jsonify
import pandas as pd
import requests
import dataframe_image as dfi
import base64
from datetime import datetime, timedelta
import pytz
import os
from PIL import Image, ImageDraw, ImageFont

app = Flask(__name__)

# ==========================================
# CONFIGURAÇÕES TÉCNICAS
# ==========================================
URL_PLANILHA = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSH9lJhzNgDz3x05wnE3lc24YKiUQcn_WTNgxEpsSO2jA36rAwSDfLZUkm1SgE_uoKBXvgx1_8sDTXZ/pub?output=xlsx"
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

# Colunas da Planilha
COLUNA_FILTRO_HORA = 'INI'
COL_EMPRESA = 'CLIENTE'

# ==========================================
# MOTOR DE GERAÇÃO DE IMAGEM
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
            # Usando a sua fonte local configurada
            font = ImageFont.truetype("DejaVuSans-Bold.ttf", 32)
        except:
            font = ImageFont.load_default()

        w_texto = draw.textlength(texto_titulo, font=font)
        x_texto = (nova_largura - w_texto) // 2
        draw.text((x_texto, 100), texto_titulo, fill=(255, 0, 0), font=font)
        
        # Colagem dos Logos
        try:
            mimo = Image.open('logo_mimo.png')
            mimo.thumbnail((200, 80))
            nova_img.paste(mimo, (20, 20), mimo if mimo.mode == 'RGBA' else None)
        except: pass
        
        try:
            for chave, arquivo in MAPA_LOGOS.items():
                if chave in cliente_nome:
                    logo_cli = Image.open(arquivo)
                    logo_cli.thumbnail((160, 80))
                    nova_img.paste(logo_cli, (nova_largura - 180, 20), logo_cli if logo_cli.mode == 'RGBA' else None)
                    break
        except: pass
        
        nova_img.save(img_path)
    except Exception as e:
        print(f"Erro imagem: {e}")

# ==========================================
# ROTA QUE O N8N VAI CHAMAR
# ==========================================
@app.route('/n8n/disparar_escala', methods=['POST'])
def processar_escala_sheets():
    dados_n8n = request.json
    cliente_alvo = str(dados_n8n.get('cliente', '')).upper()

    if not cliente_alvo:
        return jsonify({"erro": "Informe o cliente no JSON"}), 400

    try:
        # 1. Configura fuso e horários
        fuso = pytz.timezone('America/Sao_Paulo')
        agora = datetime.now(fuso).replace(tzinfo=None)
        inicio_filtro = agora - timedelta(minutes=20)
        fim_filtro = agora + timedelta(hours=3)

        # 2. Lê a planilha diretamente
        r = requests.get(URL_PLANILHA)
        xls = pd.ExcelFile(r.content)
        nome_aba = agora.strftime("%d%m%Y")

        if nome_aba not in xls.sheet_names:
            return jsonify({"erro": f"Aba {nome_aba} não existe"}), 404

        df_bruto = pd.read_excel(xls, sheet_name=nome_aba, header=None)
        linha_cab = next((i for i, r in df_bruto.iterrows() if any(str(v).strip().upper() == COLUNA_FILTRO_HORA for v in r.values)), None)
        
        df = df_bruto.iloc[linha_cab + 1:].reset_index(drop=True)
        df.columns = [str(c).strip().upper() for c in df_bruto.iloc[linha_cab]]
        df = df.dropna(subset=[COLUNA_FILTRO_HORA])

        # 3. Conversão de tempo e filtro por cliente
        def converter_tempo(v):
            try:
                dt = v if hasattr(v, 'hour') else pd.to_datetime(str(v).replace('h', ':').strip())
                return agora.replace(hour=dt.hour, minute=dt.minute, second=0, microsecond=0)
            except: return pd.NaT

        df['AUX_TIME'] = df[COLUNA_FILTRO_HORA].apply(converter_tempo)
        
        # Filtra pelo cliente enviado pelo n8n e pela janela de 3h
        df_filtrado = df[
            (df[COL_EMPRESA].str.contains(cliente_alvo, na=False)) & 
            (df['AUX_TIME'] >= inicio_filtro) & 
            (df['AUX_TIME'] <= fim_filtro)
        ].copy()

        if df_filtrado.empty:
            return jsonify({"status": "vazio", "msg": "Sem viagens para este cliente agora"}), 200

        # 4. Geração da Imagem
        img_path = f"escala_n8n_{cliente_alvo}.png"
        cols_print = ['ENT', 'INI', 'LINHA', 'CLIENTE', 'FROTA FINAL', 'MOTORISTA']
        style = df_filtrado[cols_print].style.set_properties(**{'background-color': 'white', 'color': 'black', 'border': '1px solid black'})\
                        .set_table_styles([{'selector': 'th', 'props': [('background-color', '#FF0000'), ('color', 'white')]}])
        
        dfi.export(style, img_path, table_conversion="matplotlib")
        embutir_logos_na_imagem(img_path, cliente_alvo)

        # 5. Envio via Evolution
        with open(img_path, 'rb') as f:
            base64_data = base64.b64encode(f.read()).decode('ascii')
        
        id_grupo = next((v for k, v in MAPA_GRUPOS.items() if k in cliente_alvo), None)
        payload = {
            "number": id_grupo,
            "mediatype": "image",
            "media": base64_data,
            "caption": f"🚌 *Escala Automatizada*\n🏢 *Cliente:* {cliente_alvo}\n📅 *Data:* {agora.strftime('%d/%m/%Y')}"
        }
        
        requests.post(URL_EVOLUTION, headers={"apikey": CHAVE_API_EVOLUTION, "Content-Type": "application/json"}, json=payload)

        return jsonify({"status": "sucesso", "cliente": cliente_alvo}), 200

    except Exception as e:
        return jsonify({"erro": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
