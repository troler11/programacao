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
    "MELI RC01": "logo_meli.png", "MELI SP09/15": "logo_meli.png", "MELI SP10": "logo_meli.png", "ADORO": "logo_adoro.png", 
    "AAM": "logo_aam.png", "JDE": "logo_jde.png", "CMR": "logo_cmr.jpg", "RAIA DROGASIL S/A": "logo_rd.jpg",
    "HELLERMANN": "logo_hellermann.png", "NISSEI": "logo_nissei.png", "WEIR": "logo_weir.png",
    "B BOSCH": "logo_bbosch.png", "CPQ": "logo_cpq.JPG", "EUROFARMA LABORATORIOS S.A.": "logo_raia.jpg", "SILGAN": "logo_silgan.png", 
    "THEOTO S A": "logo_theoto.jpg", "SPUMAPAC": "logo_spumapac.png", "BOLLHOFF": "logo_bollhoff.png", "MELI SP16": "logo_meli.png",  "MELI GRU 01 / ZN SP16": "logo_meli.png",
     "STIHL": "logo_stihl.png"
}

# CORREÇÃO APLICADA AQUI: Adicionadas aspas duplas de fechamento em "5511917623237" para a chave "JDE".
MAPA_GRUPOS = {
    "MELI RC01": "120363280020752507", "ADORO": "5511998833731-1587054382", "AAM": "120363204855765138", "JDE": "5511989174875-1552591041", "CMR": "5511996041777-1559824598",
    "HELLERMANN": "120363221247225251", "NISSEI": "120363401748722742", "B BOSCH": "120363203509890550", "CPQ": "120363221524193054", "RAIA DROGASIL S/A": "120363407253996616", 
    "EUROFARMA LABORATORIOS S.A.": "120363425799324384", "SILGAN": "120363160459079457", "THEOTO S A": "120363223102667295", "SPUMAPAC": "120363159621600904", "BOLLHOFF": "120363419638259481",
    "MELI SP09/15": "120363402150942864", "MELI SP10": "120363049310331127", "WEIR": "120363222601964123", "MELI SP16": "120363422963563713",  "MELI GRU 01 / ZN SP16": "120363422963563713",
    "STIHL": "120363156787150724"
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
        nova_largura = max(largura_tabela, 900) 
        
        nova_img = Image.new('RGB', (nova_largura, altura_tabela + altura_cabecalho), 'white')
        nova_img.paste(tabela_img, ((nova_largura - largura_tabela) // 2, altura_cabecalho))
        
        draw = ImageDraw.Draw(nova_img)
        texto_titulo = f"PROGRAMAÇÃO - {cliente_nome}"
        
        try: 
            font = ImageFont.truetype("DejaVuSans-Bold.ttf", 32)
        except: 
            font = ImageFont.load_default()
            
        w_texto = draw.textlength(texto_titulo, font=font)
        draw.text(((nova_largura - w_texto) // 2, 115), texto_titulo, fill=(255, 0, 0), font=font)
        
        # ==========================================
        # DEFINIÇÃO DOS ARQUIVOS (ESQUERDA E DIREITA)
        # ==========================================
        is_eurofarma = "EUROFARMA" in cliente_nome.upper()

        # Regra da Esquerda: Se Eurofarma -> logo_max, senão -> logo_mimo
        arquivo_esquerda = "logo_max.png" if is_eurofarma else "logo_mimo.png"
        
        # Regra da Direita: Se Eurofarma -> logo_raia.jpg (ou o que estiver no seu mapa), 
        # senão busca no mapa ou usa mimo como fallback
        if is_eurofarma:
            # Buscando o logo específico da Eurofarma no seu MAPA_LOGOS
            arquivo_direita = MAPA_LOGOS.get("EUROFARMA LABORATORIOS S.A.", "logo_raia.jpg")
        else:
            arquivo_direita = next((v for k, v in MAPA_LOGOS.items() if k in cliente_nome.upper()), "logo_mimo.png")

        # ==========================================
        # APLICAÇÃO DOS LOGOS
        # ==========================================
        
        # 1. Aplicar Logo Esquerda
        try:
            img_esq = Image.open(arquivo_esquerda)
            img_esq.thumbnail((200, 80))
            nova_img.paste(img_esq, (20, 20), img_esq if img_esq.mode == 'RGBA' else None)
        except:
            print(f"Erro ao carregar logo esquerda: {arquivo_esquerda}")

        # 2. Aplicar Logo Direita
        try:
            img_dir = Image.open(arquivo_direita)
            try: filtro = Image.Resampling.LANCZOS
            except AttributeError: filtro = Image.LANCZOS
            
            img_dir.thumbnail((210, 90), filtro)
            largura_real_dir, _ = img_dir.size
            posicao_x_dir = nova_largura - largura_real_dir - 20
            nova_img.paste(img_dir, (posicao_x_dir, 20), img_dir if img_dir.mode == 'RGBA' else None)
        except:
            print(f"Erro ao carregar logo direita: {arquivo_direita}")

        nova_img.save(img_path)
        
    except Exception as e: 
        print(f"Erro imagem: {e}")

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
        return "✅ Enviado" if resp.status_code in [200, 201] else f"❌ Erro API: {resp.text}"
    except Exception as e: return f"❌ Falha: {e}"

# ==========================================
# ROTA MULTI-CLIENTE
# ==========================================
@app.route('/gerar_escala', methods=['GET'])
def gerar_escala():
    # Agora aceita nomes separados por vírgula: ?cliente=AMAZON,MELI,ADORO
    clientes_raw = request.args.get('cliente', '')
    horario_alvo = request.args.get('horario', '')

    if not clientes_raw or not horario_alvo:
        return jsonify({"erro": "Faltam parâmetros"}), 400

    lista_clientes = [c.strip().upper() for c in clientes_raw.split(',')]
    resultados_finais = {}

    try:
        fuso = pytz.timezone('America/Sao_Paulo')
        agora = datetime.now(fuso).replace(tzinfo=None)
        
        # Faz o download da planilha uma única vez para todos os clientes (mais rápido)
        r = requests.get(URL_PLANILHA)
        xls = pd.ExcelFile(r.content)
        nome_aba = agora.strftime("%d%m%Y")
        
        if nome_aba not in [a.strip() for a in xls.sheet_names]:
            return jsonify({"erro": f"Aba {nome_aba} não encontrada"}), 404

        df_bruto = pd.read_excel(xls, sheet_name=nome_aba, header=None)
        linha_cab = next((i for i, r in df_bruto.iterrows() if any(str(v).strip().upper() == COLUNA_FILTRO_HORA for v in r.values)), None)
        df_base = df_bruto.iloc[linha_cab + 1:].reset_index(drop=True)
        df_base.columns = [str(c).strip().upper() for c in df_bruto.iloc[linha_cab]]
        
        def converter_tempo(v):
            try:
                dt = v if hasattr(v, 'hour') else pd.to_datetime(str(v).replace('h', ':').strip())
                return agora.replace(hour=dt.hour, minute=dt.minute, second=0)
            except: return pd.NaT

        df_base['AUX_TIME'] = df_base[COLUNA_FILTRO_HORA].apply(converter_tempo)
        
        # Janela de tempo
        hora_obj = datetime.strptime(horario_alvo, '%H:%M').time()
        inicio_f = agora.replace(hour=hora_obj.hour, minute=hora_obj.minute, second=0)
        fim_f = inicio_f + timedelta(hours=2)

        # Loop processando cada cliente da lista
        # Loop processando cada cliente da lista
        for cliente in lista_clientes:
            df_filtrado = df_base[(df_base[COL_EMPRESA].str.contains(cliente, na=False)) & (df_base['AUX_TIME'] >= inicio_f) & (df_base['AUX_TIME'] <= fim_f)].copy()
            
            if df_filtrado.empty:
                resultados_finais[cliente] = "Vazio (Sem viagens)"
                continue

            # CORREÇÃO: Substitui a barra por traço para criar um nome de arquivo válido no Linux
            nome_seguro = cliente.replace('/', '-')
            img_path = f"temp_{nome_seguro}.png"
            cols_p = [COL_PERIODO, COL_HORA, COL_LINHA, COL_EMPRESA, COL_PREFIXO, COL_MOTORISTA]
            
            style = (df_filtrado[cols_p].style
                .hide(axis='index')
                .set_properties(**{
                    'background-color': 'white', 
                    'color': 'black', 
                    'border': '1px solid black',
                    'text-align': 'center'
                })
                .set_table_styles([
                    {'selector': 'table', 'props': [('border-collapse', 'collapse'), ('border', '1px solid black')]},
                    {'selector': 'th', 'props': [
                        ('background-color', '#FF0000'), 
                        ('color', 'white'), 
                        ('border', '1px solid black'), 
                        ('text-align', 'center'),
                        ('font-weight', 'bold')
                    ]},
                    {'selector': 'td', 'props': [('border', '1px solid black')]}
                ])
            )
            
            # MUDANÇA PRINCIPAL AQUI:
            dfi.export(style, img_path, table_conversion="playwright")
            embutir_logos_na_imagem(img_path, cliente)
            
            status = enviar_evolution(img_path, cliente, agora.strftime('%d/%m/%Y'), f"Janela {horario_alvo}")
            resultados_finais[cliente] = status

        return jsonify({"status": "processado", "detalhes": resultados_finais}), 200

    except Exception as e:
        return jsonify({"status": "erro", "detalhe": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
