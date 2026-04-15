import streamlit as st
import pandas as pd
import requests
import io
import dataframe_image as dfi
from datetime import datetime, timedelta
import pytz 
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill
from openpyxl.drawing.image import Image
import os

# ==========================================
# CONFIGURAÇÕES DA EMPRESA E PLANILHA
# ==========================================
URL_PLANILHA = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSH9lJhzNgDz3x05wnE3lc24YKiUQcn_WTNgxEpsSO2jA36rAwSDfLZUkm1SgE_uoKBXvgx1_8sDTXZ/pub?output=xlsx"

# Coluna usada para o filtro de 3 horas
COLUNA_FILTRO_HORA = 'INI' 

# Colunas para a planilha final
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
    "ADORO": "120363000000000002@g.us",
    "AAM": "5511934773679@c.us" 
}

URL_WAHA = "https://mimo-waha.3sbqz4.easypanel.host/api/sendImage"
SESSAO_WAHA = "default"
CHAVE_API_WAHA = "teste" 

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
        logo_esq = Image('logo_mimo.png')
        logo_esq.width, logo_esq.height = 180, 50
        ws.add_image(logo_esq, 'A2')

        for chave, arquivo in MAPA_LOGOS.items():
            if chave in cliente_id:
                logo_c = Image(arquivo)
                logo_c.width, logo_c.height = 120, 70
                ws.add_image(logo_c, 'F2')
                break
    except: pass

    ws.merge_cells('A12:F12')
    ws['A12'] = f"PROGRAMAÇÃO - {cliente_id}"
    ws['A12'].font = fonte_vermelha_titulo
    ws['A12'].alignment = Alignment(horizontal="center")

    cabecalhos = ["Periodo", "Horas", "Linha", "Empresa", "Prefixo", "Motorista"]
    ws.append([]); ws.append(cabecalhos)
    for col in range(1, 7):
        c = ws.cell(row=14, column=col)
        c.fill, c.font, c.alignment = fill_vermelho, fonte_branca, Alignment(horizontal="center")

    for _, row in df.iterrows():
        ws.append([row.get(COL_PERIODO,''), row.get(COL_HORA,''), row.get(COL_LINHA,''), 
                   row.get(COL_EMPRESA,''), row.get(COL_PREFIXO,''), row.get(COL_MOTORISTA,'')])
    
    ws.column_dimensions['C'].width, ws.column_dimensions['F'].width = 45, 25
    out = io.BytesIO(); wb.save(out); out.seek(0)
    return out

def enviar_waha(imagem_path, nome_empresa, data_str):
    id_grupo = next((v for k, v in MAPA_GRUPOS.items() if k in nome_empresa), None)
    if not id_grupo: return f"⚠️ Grupo não configurado para: {nome_empresa}"

    msg = f"🚌 *Programação de Escala*\n🏢 *Cliente:* {nome_empresa}\n📅 *Data:* {data_str}\n⏱️ *Janela:* Próximas 3h"
    headers = {"accept": "application/json"}
    if CHAVE_API_WAHA: headers["X-Api-Key"] = CHAVE_API_WAHA
    
    try:
        with open(imagem_path, 'rb') as f:
            resp = requests.post(
                URL_WAHA, 
                headers=headers,
                params={'session': 'default'}, 
                data={'chatId': id_grupo, 'caption': msg}, 
                files={'file': ('image.png', f, 'image/png')}
            )
        if resp.status_code in [200, 201]: return "✅ Enviado com sucesso!"
        return f"❌ Erro WAHA ({resp.status_code}): {resp.text}"
    except Exception as e: return f"❌ Falha de conexão: {e}"

# ==========================================
# INTERFACE PRINCIPAL
# ==========================================

st.set_page_config(page_title="Gestão Mimo", layout="centered")
st.title("Gerador de Escalas por Cliente 🚌⏳")

if 'clientes_processados' not in st.session_state:
    st.session_state.clientes_processados = {}

if st.button("1. Analisar Planilha e Gerar Prévias", type="primary"):
    with st.spinner("Buscando dados no Google Sheets..."):
        try:
            # Força o horário de Brasília e remove fuso para comparação limpa
            fuso = pytz.timezone('America/Sao_Paulo')
            agora = datetime.now(fuso).replace(tzinfo=None)
            
            # Pequeno ajuste: se for 11:23, vamos considerar desde 11:20 para não perder viagens que acabaram de começar
            hoje_inicio = agora - timedelta(minutes=5)
            limite = agora + timedelta(hours=3)
            
            r = requests.get(URL_PLANILHA)
            r.raise_for_status()
            
            xls = pd.ExcelFile(r.content)
            abas_reais = [a.strip() for a in xls.sheet_names]
            nome_aba = agora.strftime("%d%m%Y")

            if nome_aba not in abas_reais:
                st.error(f"❌ Não achei a aba de hoje ({nome_aba}). Abas lidas: {xls.sheet_names}")
                st.stop()

            df_bruto = pd.read_excel(xls, sheet_name=nome_aba, header=None)
            linha_cabecalho = next((i for i, r in df_bruto.iterrows() if any(str(v).strip().upper() == COLUNA_FILTRO_HORA for v in r.values)), None)
            
            if linha_cabecalho is None: st.error("❌ Cabeçalho não encontrado."); st.stop()
                
            df = df_bruto.iloc[linha_cabecalho + 1:].reset_index(drop=True)
            df.columns = [str(c).strip().upper() for c in df_bruto.iloc[linha_cabecalho]]
            df = df.dropna(subset=[COLUNA_FILTRO_HORA]) 

            # FUNÇÃO DE PARSING REFORÇADA
            def parsing_hora(v):
                if pd.isna(v): return pd.NaT
                try:
                    # Se já for um objeto de tempo/datetime
                    if hasattr(v, 'hour'):
                        h, m = v.hour, v.minute
                    else:
                        # Se for string "11:30" ou "11h30"
                        s = str(v).replace('h', ':').strip()
                        t = pd.to_datetime(s)
                        h, m = t.hour, t.minute
                    # Retorna um timestamp com a data de hoje e a hora da planilha
                    return agora.replace(hour=h, minute=m, second=0, microsecond=0)
                except:
                    return pd.NaT

            df['AUX_TIME'] = df[COLUNA_FILTRO_HORA].apply(parsing_hora)
            
            # Filtro comparando agora com o limite de 3h
            df_filtrado = df[(df['AUX_TIME'] >= hoje_inicio) & (df['AUX_TIME'] <= limite)].copy()

            if df_filtrado.empty:
                # Se não achou nada, mostramos o que ele tentou buscar para ajudar a debugar
                st.warning(f"⚠️ Nenhuma viagem nas próximas 3h.")
                st.write(f"Buscando entre: **{hoje_inicio.strftime('%H:%M')}** e **{limite.strftime('%H:%M')}**")
                st.stop()

            clientes_dict = {}
            for cliente, group_df in df_filtrado.groupby(COL_EMPRESA):
                cliente_nome = str(cliente).strip().upper()
                nome_seguro = cliente_nome.replace("/", "_").replace(":", "_")
                img_path = f"escala_{nome_seguro}.png"
                
                cols_print = [c for c in [COL_PERIODO, COL_HORA, COL_LINHA, COL_EMPRESA, COL_PREFIXO, COL_MOTORISTA] if c in group_df.columns]
                style = group_df[cols_print].style.set_properties(**{'background-color': 'white', 'color': 'black', 'border': '1px solid black'})\
                    .set_table_styles([{'selector': 'th', 'props': [('background-color', '#FF0000'), ('color', 'white')]}])
                
                dfi.export(style, img_path, table_conversion="matplotlib", max_rows=-1)
                
                clientes_dict[cliente_nome] = {
                    "img": img_path,
                    "excel": gerar_planilha_formatada(group_df, cliente_nome),
                    "data_str": agora.strftime('%d/%m/%Y')
                }
            
            st.session_state.clientes_processados = clientes_dict
            st.success(f"✅ {len(clientes_dict)} clientes encontrados!")

        except Exception as e:
            st.error(f"❌ Erro no processamento: {e}")

if st.session_state.clientes_processados:
    for nome, dados in st.session_state.clientes_processados.items():
        with st.expander(f"📦 CLIENTE: {nome}", expanded=True):
            st.image(dados["img"])
            c1, c2 = st.columns(2)
            with c1:
                if st.button(f"📲 Enviar WhatsApp: {nome}", key=f"btn_{nome}"):
                    res = enviar_waha(dados["img"], nome, dados["data_str"])
                    if "✅" in res: st.success(res)
                    else: st.error(res)
            with c2:
                st.download_button(f"📥 Baixar Excel: {nome}", dados["excel"], f"Escala_{nome.replace('/', '_')}.xlsx", key=f"dl_{nome}")
