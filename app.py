from flask import Flask, request, jsonify
import pandas as pd
import requests
import io
import dataframe_image as dfi
import base64
from datetime import datetime, timedelta
import pytz 
import os
from PIL import Image, ImageDraw, ImageFont

app = Flask(__name__)

# ==========================================
# CONFIGURAÇÕES
# ==========================================
URL_PLANILHA = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSH9lJhzNgDz3x05wnE3lc24YKiUQcn_WTNgxEpsSO2jA36rAwSDfLZUkm1SgE_uoKBXvgx1_8sDTXZ/pub?output=xlsx"
COLUNA_FILTRO_HORA = 'INI' 
COL_PERIODO = 'ENT'           
COL_HORA = 'INI'              
COL_LINHA = 'LINHA'           
COL_EMPRESA = 'CLIENTE'       
COL_PREFIXO = 'FROTA FINAL' 
COL_MOTORISTA = 'MOTORISTA'   

MAPA_LOGOS = {
    "MELI": "logo_meli.png", "MERCADO LIVRE": "logo_meli.png", 
    "AMAZON": "logo_amazon.png", "ADORO": "logo_adoro.png", "AAM": "logo_aam.png"
}

MAPA_GRUPOS = {
    "MELI": "120363000000000000@g.us", "AMAZON": "120363000000000001@g.us", 
    "ADORO": "5511917623237", "AAM": "5511934773679"
}

URL_EVOLUTION = "https://mimo-evolution-api.3sbqz4.easypanel.host/message/sendMedia/teste"
CHAVE_API_EVOLUTION = "429683C4C977415CAAFCCE10F7D57E11"

# ==========================================
# FUNÇÕES DE APOIO
# ==========================================
def embutir_logos_na_imagem(img_path, cliente_nome):
    try:
        tabela_img = Image.open(img_path)
        largura_tabela, altura_tabela = tabela_img.size
        altura_cabecalho = 160
        nova_largura = max(largura_tabela, 800) 
        nova_img = Image.new('RGB', (nova_largura, altura_tabela + altura_cabecalho), 'white')
        nova_img.paste(tabela_img, ((nova_largura - largura_tabela) // 2, altura_cabecalho))
        draw = ImageDraw.Draw(nova_img)
        texto_titulo = f"PROGRAMAÇÃO - {cliente_nome}"
        try: font = ImageFont.truetype("DejaVuSans-Bold.ttf", 32)
        except: font = ImageFont.load_default()
        w_texto = draw.textlength(texto_titulo, font=font)
        draw.text(((nova_largura - w_texto) // 2, 100), texto_titulo, fill=(255, 0, 0), font=font)
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
    except Exception as e: print(f"Erro imagem: {e}")

def enviar_evolution(imagem_path, nome_empresa, data_str, contexto):
    id_grupo = next((v for k, v in MAPA_GRUPOS.items() if k in nome_empresa), None)
    if not id_grupo: return f"⚠️ Destino não configurado: {nome_empresa}"
    msg = f"🚌 *Programação de Escala*\n🏢 *Cliente:* {nome_empresa}\n📅 *Data:* {data_str}\n⏱️ *Janela:* {contexto}"
    headers = {"Content-Type": "application/json", "apikey": CHAVE_API_EVOLUTION}
    try:
        with open(imagem_path, 'rb') as f:
            base64_data = base64.b64encode(f.read()).decode('ascii')
        payload = {"number": id_grupo, "mediatype": "image", "media": base64_data, "caption": msg}
        resp = requests.post(URL_EVOLUTION, headers=headers, json=payload)
        return "✅ Escala enviada!" if resp.status_code in [200, 201] else f"❌ Erro: {resp.text}"
    except Exception as e: return f"❌ Falha: {e}"

# ==========================================
# ROTA DA API (O QUE O N8N CHAMA)
# ==========================================
@app.route('/gerar_escala', methods=['GET'])
def gerar_escala():
    cliente_alvo = request.args.get('cliente', '').upper()
    horario_alvo = request.args.get('horario', '')

    if not cliente_alvo or not horario_alvo:
        return jsonify({"erro": "Faltam parametros cliente e horario"}), 400

    try:
        fuso = pytz.timezone('America/Sao_Paulo')
        agora = datetime.now(fuso).replace(tzinfo=None)
        hora_obj = datetime.strptime(horario_alvo, '%H:%M').time()
        inicio_filtro = agora.replace(hour=hora_obj.hour, minute=hora_obj.minute, second=0)
        fim_filtro = inicio_filtro + timedelta(hours=2)
        
        r = requests.get(URL_PLANILHA)
        xls = pd.ExcelFile(r.content)
        nome_aba = agora.strftime("%d%m%Y")
        
        if nome_aba not in [a.strip() for a in xls.sheet_names]:
            return jsonify({"erro": f"Aba {nome_aba} não encontrada"}), 404

        df_bruto = pd.read_excel(xls, sheet_name=nome_aba, header=None)
        linha_cab = next((i for i, r in df_bruto.iterrows() if any(str(v).strip().upper() == COLUNA_FILTRO_HORA for v in r.values)), None)
        df = df_bruto.iloc[linha_cab + 1:].reset_index(drop=True)
        df.columns = [str(c).strip().upper() for c in df_bruto.iloc[linha_cab]]
        
        def converter_tempo(v):
            try:
                dt = v if hasattr(v, 'hour') else pd.to_datetime(str(v).replace('h', ':').strip())
                return agora.replace(hour=dt.hour, minute=dt.minute, second=0)
            except: return pd.NaT

        df['AUX_TIME'] = df[COLUNA_FILTRO_HORA].apply(converter_tempo)
        df_filtrado = df[(df[COL_EMPRESA].str.contains(cliente_alvo, na=False)) & (df['AUX_TIME'] >= inicio_filtro) & (df['AUX_TIME'] <= fim_filtro)].copy()
        
        if df_filtrado.empty:
            return jsonify({"status": "vazio", "msg": "Nenhuma viagem encontrada"}), 200

        img_path = f"auto_{cliente_alvo}.png"
        cols_p = [COL_PERIODO, COL_HORA, COL_LINHA, COL_EMPRESA, COL_PREFIXO, COL_MOTORISTA]
        style = df_filtrado[cols_p].style.set_properties(**{'background-color': 'white', 'color': 'black', 'border': '1px solid black'}).set_table_styles([{'selector': 'th', 'props': [('background-color', '#FF0000'), ('color', 'white')]}])
        
        dfi.export(style, img_path, table_conversion="matplotlib")
        embutir_logos_na_imagem(img_path, cliente_alvo)
        
        resultado = enviar_evolution(img_path, cliente_alvo, agora.strftime('%d/%m/%Y'), f"Janela {horario_alvo}")
        return jsonify({"status": "sucesso", "resultado": resultado}), 200

    except Exception as e:
        return jsonify({"status": "erro", "detalhe": str(e)}), 500

if __name__ == '__main__':
    # A API roda na porta 5000 por padrão
    app.run(host='0.0.0.0', port=5000)
