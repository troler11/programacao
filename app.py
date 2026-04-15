import streamlit as st
import pandas as pd
import requests
import io
import dataframe_image as dfi
from datetime import datetime, timedelta
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill
from openpyxl.drawing.image import Image

# ==========================================
# CONFIGURAÇÕES
# ==========================================

URL_PLANILHA = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSH9lJhzNgDz3x05wnE3lc24YKiUQcn_WTNgxEpsSO2jA36rAwSDfLZUkm1SgE_uoKBXvgx1_8sDTXZ/pub?output=xlsx"

MAPA_LOGOS = {
    "MELI": "logo_meli.png",
    "MERCADO LIVRE": "logo_meli.png",
    "AMAZON": "logo_amazon.png"
}

MAPA_GRUPOS = {
    "MELI": "120363000000000000@g.us", # Substituir pelo ID real
    "AMAZON": "120363000000000001@g.us"
}

# No Easypanel, a URL deve apontar para o nome do serviço (waha)
URL_WAHA = "http://waha:3000/api/sendImage"
SESSAO_WAHA = "default"

# ==========================================
# FUNÇÕES DE APOIO
# ==========================================

def gerar_planilha_formatada(df, cliente_id):
    wb = Workbook()
    ws = wb.active
    fill_vermelho = PatternFill(start_color="FF0000", end_color="FF0000", fill_type="solid")
    fonte_branca = Font(color="FFFFFF", bold=True)
    fonte_vermelha_titulo = Font(color="FF0000", bold=True, size=16)

    try:
        ws.add_image(Image('logo_mimo.png'), 'A1')
        ws.add_image(Image('logo_mimo.png'), 'F1')
        for chave, logo in MAPA_LOGOS.items():
            if chave in cliente_id:
                ws.add_image(Image(logo), 'C1')
                break
    except: pass

    ws.merge_cells('A12:F12')
    ws['A12'] = "PROGRAMAÇÃO DE ENTRADA/SAIDA (PRÓXIMAS 3H)"
    ws['A12'].font = fonte_vermelha_titulo
    ws['A12'].alignment = Alignment(horizontal="center")

    cabecalhos = ["Periodo", "Horas", "Linha", "Empresa", "Prefixo", "Motorista"]
    ws.append([]); ws.append(cabecalhos)
    for col in range(1, 7):
        c = ws.cell(row=14, column=col)
        c.fill, c.font, c.alignment = fill_vermelho, fonte_branca, Alignment(horizontal="center")

    for _, row in df.iterrows():
        ws.append([row.get('Periodo',''), row.get('Horas',''), row.get('Linha',''), 
                   row.get('Empresa',''), row.get('Prefixo',''), row.get('Motorista','')])
    
    ws.column_dimensions['C'].width, ws.column_dimensions['F'].width = 50, 25
    out = io.BytesIO(); wb.save(out); out.seek(0)
    return out

def enviar_waha(imagem_path, nome_empresa, data_str):
    id_grupo = next((v for k, v in MAPA_GRUPOS.items() if k in nome_empresa), None)
    if not id_grupo:
        st.warning(f"⚠️ Grupo não configurado para: {nome_empresa}"); return False

    msg = f"🚌 *Programação de Escala*\n🏢 *Cliente:* {nome_empresa}\n📅 *Data:* {data_str}\n⏱️ *Janela:* Próximas 3h"
    try:
        with open(imagem_path, 'rb') as f:
            resp = requests.post(URL_WAHA, data={'session': SESSAO_WAHA, 'chatId': id_grupo, 'caption': msg}, 
                                 files={'file': (imagem_path, f, 'image/png')})
        if resp.status_code in [200, 201]:
            st.success("✅ Enviado para o WhatsApp!"); return True
        st.error(f"❌ Erro WAHA: {resp.text}"); return False
    except Exception as e:
        st.error(f"❌ Conexão falhou: {e}"); return False

# ==========================================
# INTERFACE PRINCIPAL
# ==========================================

st.set_page_config(page_title="Gestão Mimo", layout="centered")
st.title("Gerador de Escalas 🚌⏳")

if st.button("Filtrar e Enviar para o WhatsApp", type="primary"):
    with st.spinner("Processando dados..."):
        try:
            hoje = datetime.now()
            r = requests.get(URL_PLANILHA)
            r.raise_for_status()
            
            # Busca inteligente de abas
            xls = pd.ExcelFile(r.content)
            formatos = [hoje.strftime("%d/%m/%Y"), hoje.strftime("%d_%m_%Y"), hoje.strftime("%d-%m-%Y"), hoje.strftime("%d%m%Y")]
            nome_aba = next((f for f in formatos if f in xls.sheet_names), None)

            if not nome_aba:
                st.error(f"❌ Aba de hoje não encontrada. Disponíveis: {xls.sheet_names}"); st.stop()

            df = pd.read_excel(xls, sheet_name=nome_aba)
            
            # Filtro de 3 horas
            limite = hoje + timedelta(hours=3)
            def parsing_hora(v):
                try:
                    t = pd.to_datetime(v).time() if isinstance(v, str) else v
                    return datetime.combine(hoje.date(), t.time() if hasattr(t, 'time') else t)
                except: return pd.NaT

            df['AUX_TIME'] = df['Horas'].apply(parsing_hora)
            df = df[(df['AUX_TIME'] >= hoje) & (df['AUX_TIME'] <= limite)].drop(columns=['AUX_TIME'])

            if df.empty:
                st.warning("⚠️ Nenhuma viagem nas próximas 3 horas."); st.stop()

            cliente = str(df['Empresa'].iloc[0]).strip().upper()
            st.info(f"📍 Operação: {cliente}")

            # Geração de ficheiros
            excel = gerar_planilha_formatada(df, cliente)
            img_path = f"escala_{hoje.strftime('%H%M')}.png"
            
            style = df.style.set_properties(**{'background-color': 'white', 'color': 'black', 'border': '1px solid black'})\
                .set_table_styles([{'selector': 'th', 'props': [('background-color', '#FF0000'), ('color', 'white')]}])
            dfi.export(style, img_path, table_conversion="matplotlib")

            if enviar_waha(img_path, cliente, hoje.strftime('%d/%m/%Y')):
                st.download_button("📥 Descarregar Excel", excel, f"Escala_{cliente}.xlsx")

        except Exception as e:
            st.error(f"❌ Erro crítico: {e}")
