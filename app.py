import streamlit as st
import pandas as pd
import requests
import io
import dataframe_image as dfi
import base64
from datetime import datetime, timedelta
import pytz 
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill
from openpyxl.drawing.image import Image as OpenpyxlImage
import os

# Biblioteca PIL para manipular a imagem final e escrever o título
from PIL import Image, ImageDraw, ImageFont

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
    "MELI": "logo_meli.png", 
    "MERCADO LIVRE": "logo_meli.png", 
    "AMAZON": "logo_amazon.png", 
    "ADORO": "logo_adoro.png", 
    "AAM": "logo_aam.png"
}

MAPA_GRUPOS = {
    "MELI": "120363000000000000@g.us", 
    "AMAZON": "120363000000000001@g.us", 
    "ADORO": "5511917623237", 
    "AAM": "5511934773679" 
}

# Configurações Evolution API
URL_EVOLUTION = "https://mimo-evolution-api.3sbqz4.easypanel.host/message/sendMedia/teste"
CHAVE_API_EVOLUTION = "429683C4C977415CAAFCCE10F7D57E11"

# ==========================================
# FUNÇÕES DE APOIO
# ==========================================

def embutir_logos_na_imagem(img_path, cliente_nome):
    """Lê a foto da tabela, adiciona um cabeçalho e escreve o título 'PROGRAMAÇÃO - EMPRESA'."""
    try:
        tabela_img = Image.open(img_path)
        largura_tabela, altura_tabela = tabela_img.size
        
        # Aumentamos o cabeçalho para 160px para caber os logos e o título com folga
        altura_cabecalho = 160
        nova_largura = max(largura_tabela, 800) 
        
        nova_img = Image.new('RGB', (nova_largura, altura_tabela + altura_cabecalho), 'white')
        
        # Cola a tabela na parte inferior
        x_tabela = (nova_largura - largura_tabela) // 2
        nova_img.paste(tabela_img, (x_tabela, altura_cabecalho))
        
        draw = ImageDraw.Draw(nova_img)
        
        # 1. Desenha o Título (PROGRAMAÇÃO - EMPRESA)
        texto_titulo = f"PROGRAMAÇÃO - {cliente_nome}"
        
        # Tenta carregar uma fonte, se falhar usa a padrão
        try:
            # Em servidores Linux/Docker geralmente tem essa fonte
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 28)
        except:
            font = ImageFont.load_default()

        # Calcula posição central para o texto
        w_texto = draw.textlength(texto_titulo, font=font)
        x_texto = (nova_largura - w_texto) // 2
        draw.text((x_texto, 100), texto_titulo, fill=(255, 0, 0), font=font) # Vermelho Mimo
        
        # 2. Insere o Logo Mimo (Esquerda)
        try:
            mimo = Image.open('logo_mimo.png')
            mimo.thumbnail((200, 80))
            nova_img.paste(mimo, (20, 20), mimo if mimo.mode == 'RGBA' else None)
        except: pass
        
        # 3. Insere o Logo Cliente (Direita)
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
        print(f"Erro ao montar imagem: {e}")

def gerar_planilha_formatada(df, cliente_id):
    wb = Workbook()
    ws = wb.active
    fill_vermelho = PatternFill(start_color="FF0000", end_color="FF0000", fill_type="solid")
    fonte_branca = Font(color="FFFFFF", bold=True)
    fonte_vermelha_titulo = Font(color="FF0000", bold=True, size=16)
    
    try:
        logo_esq = OpenpyxlImage('logo_mimo.png')
        logo_esq.width, logo_esq.height = 180, 50
        ws.add_image(logo_esq, 'A2')
        for chave, arquivo in MAPA_LOGOS.items():
            if chave in cliente_id:
                logo_c = OpenpyxlImage(arquivo)
                logo_c.width, logo_c.height = 120, 70
                ws.add_image(logo_c, 'F2')
                break
    except: pass
        
    ws.merge_cells('A12:F12')
    ws['A12'] = f"PROGRAMAÇÃO - {cliente_id}"
    ws['A12'].font = fonte_vermelha_titulo
    ws['A12'].alignment = Alignment(horizontal="center")
    
    ws.append([])
    ws.append(["Periodo", "Horas", "Linha", "Empresa", "Prefixo", "Motorista"])
    
    for col in range(1, 7):
        c = ws.cell(row=14, column=col)
        c.fill = fill_vermelho; c.font = fonte_branca; c.alignment = Alignment(horizontal="center")
        
    for _, row in df.iterrows():
        ws.append([row.get(COL_PERIODO,''), row.get(COL_HORA,''), row.get(COL_LINHA,''), row.get(COL_EMPRESA,''), row.get(COL_PREFIXO,''), row.get(COL_MOTORISTA,'')])
        
    ws.column_dimensions['C'].width = 45; ws.column_dimensions['F'].width = 25
    out = io.BytesIO(); wb.save(out); out.seek(0)
    return out

def enviar_evolution(imagem_path, nome_empresa, data_str):
    id_grupo = next((v for k, v in MAPA_GRUPOS.items() if k in nome_empresa), None)
    if not id_grupo: return f"⚠️ Destino não configurado para: {nome_empresa}"

    msg = f"🚌 *Programação de Escala*\n🏢 *Cliente:* {nome_empresa}\n📅 *Data:* {data_str}\n⏱️ *Janela:* Próximas 3h"
    headers = {"Content-Type": "application/json", "apikey": CHAVE_API_EVOLUTION}

    try:
        with open(imagem_path, 'rb') as f:
            base64_data = base64.b64encode(f.read()).decode('ascii')
        
        payload = {"number": id_grupo, "mediatype": "image", "media": base64_data, "caption": msg}
        resp = requests.post(URL_EVOLUTION, headers=headers, json=payload)
            
        if resp.status_code in [200, 201]: return "✅ Escala enviada com sucesso!"
        else: return f"❌ Erro Evolution ({resp.status_code}): {resp.text}"
    except Exception as e: return f"❌ Falha de conexão: {e}"

# ==========================================
# INTERFACE PRINCIPAL
# ==========================================

st.set_page_config(page_title="Gestão Mimo", layout="centered")
st.title("Gerador de Escalas por Cliente 🚌⏳")

if 'clientes_processados' not in st.session_state:
    st.session_state.clientes_processados = {}

if st.button("1. Analisar Planilha e Gerar Prévias", type="primary"):
    with st.spinner("Analisando planilha..."):
        try:
            fuso = pytz.timezone('America/Sao_Paulo')
            agora = datetime.now(fuso).replace(tzinfo=None)
            
            inicio_filtro = agora - timedelta(minutes=20)
            fim_filtro = agora + timedelta(hours=3)
            
            r = requests.get(URL_PLANILHA)
            r.raise_for_status()
            xls = pd.ExcelFile(r.content)
            nome_aba = agora.strftime("%d%m%Y")

            if nome_aba not in [a.strip() for a in xls.sheet_names]:
                st.error(f"❌ Aba {nome_aba} não encontrada."); st.stop()

            df_bruto = pd.read_excel(xls, sheet_name=nome_aba, header=None)
            linha_cabecalho = next((i for i, r in df_bruto.iterrows() if any(str(v).strip().upper() == COLUNA_FILTRO_HORA for v in r.values)), None)
            
            if linha_cabecalho is None: st.error("❌ Cabeçalho não encontrado."); st.stop()
            
            df = df_bruto.iloc[linha_cabecalho + 1:].reset_index(drop=True)
            df.columns = [str(c).strip().upper() for c in df_bruto.iloc[linha_cabecalho]]
            df = df.dropna(subset=[COLUNA_FILTRO_HORA]) 

            def converter_tempo(v):
                if pd.isna(v): return pd.NaT
                try:
                    if hasattr(v, 'hour'): dt = v
                    else: dt = pd.to_datetime(str(v).replace('h', ':').strip())
                    return agora.replace(hour=dt.hour, minute=dt.minute, second=0, microsecond=0)
                except: return pd.NaT

            df['AUX_TIME'] = df[COLUNA_FILTRO_HORA].apply(converter_tempo)
            df_filtrado = df[(df['AUX_TIME'] >= inicio_filtro) & (df['AUX_TIME'] <= fim_filtro)].copy()

            if df_filtrado.empty:
                st.warning("⚠️ Nenhuma viagem nas próximas 3h."); st.stop()

            clientes_dict = {}
            for cliente, group_df in df_filtrado.groupby(COL_EMPRESA):
                cliente_nome = str(cliente).strip().upper()
                nome_seguro = cliente_nome.replace("/", "_").replace(":", "_")
                img_path = f"escala_{nome_seguro}.png"
                
                cols_print = [c for c in [COL_PERIODO, COL_HORA, COL_LINHA, COL_EMPRESA, COL_PREFIXO, COL_MOTORISTA] if c in group_df.columns]
                style = group_df[cols_print].style.set_properties(**{'background-color': 'white', 'color': 'black', 'border': '1px solid black'})\
                    .set_table_styles([{'selector': 'th', 'props': [('background-color', '#FF0000'), ('color', 'white')]}])
                
                dfi.export(style, img_path, table_conversion="matplotlib", max_rows=-1)
                
                # NOVO: Monta a imagem com Logos + Título PROGRAMAÇÃO
                embutir_logos_na_imagem(img_path, cliente_nome)
                
                clientes_dict[cliente_nome] = {
                    "img": img_path, 
                    "excel": gerar_planilha_formatada(group_df, cliente_nome), 
                    "data_str": agora.strftime('%d/%m/%Y')
                }
                
            st.session_state.clientes_processados = clientes_dict
            st.success(f"✅ {len(clientes_dict)} clientes encontrados!")
            
        except Exception as e: st.error(f"❌ Erro: {e}")

if st.session_state.clientes_processados:
    for nome, dados in st.session_state.clientes_processados.items():
        with st.expander(f"📦 CLIENTE: {nome}", expanded=True):
            st.image(dados["img"])
            c1, c2 = st.columns(2)
            with c1:
                if st.button(f"📲 Enviar via WhatsApp: {nome}", key=f"btn_{nome}"):
                    res = enviar_evolution(dados["img"], nome, dados["data_str"])
                    if "✅" in res: st.success(res)
                    else: st.error(res)
            with c2:
                st.download_button(f"📥 Baixar Excel: {nome}", dados["excel"], f"Escala_{nome.replace('/', '_')}.xlsx", key=f"dl_{nome}")
