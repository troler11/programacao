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
from openpyxl.drawing.image import Image
import os

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
    "ADORO": "120363000000000002@g.us", 
    "AAM": "5511934773679@c.us"
}

URL_WAHA = "https://mimo-waha.3sbqz4.easypanel.host/api/sendImage"
SESSAO_WAHA = "default"

# ATENÇÃO: Se não houver senha configurada no Easypanel, deixe vazio: ""
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
    except: 
        pass
        
    ws.merge_cells('A12:F12')
    ws['A12'] = f"PROGRAMAÇÃO - {cliente_id}"
    ws['A12'].font = fonte_vermelha_titulo
    ws['A12'].alignment = Alignment(horizontal="center")
    
    ws.append([])
    ws.append(["Periodo", "Horas", "Linha", "Empresa", "Prefixo", "Motorista"])
    
    for col in range(1, 7):
        c = ws.cell(row=14, column=col)
        c.fill = fill_vermelho
        c.font = fonte_branca
        c.alignment = Alignment(horizontal="center")
        
    for _, row in df.iterrows():
        ws.append([
            row.get(COL_PERIODO,''), 
            row.get(COL_HORA,''), 
            row.get(COL_LINHA,''), 
            row.get(COL_EMPRESA,''), 
            row.get(COL_PREFIXO,''), 
            row.get(COL_MOTORISTA,'')
        ])
        
    ws.column_dimensions['C'].width = 45
    ws.column_dimensions['F'].width = 25
    out = io.BytesIO()
    wb.save(out)
    out.seek(0)
    return out

def enviar_waha(imagem_path, nome_empresa, data_str):
    id_grupo = next((v for k, v in MAPA_GRUPOS.items() if k in nome_empresa), None)
    if not id_grupo: 
        return f"⚠️ Grupo não configurado para: {nome_empresa}"

    msg = f"🚌 *Programação de Escala*\n🏢 *Cliente:* {nome_empresa}\n📅 *Data:* {data_str}\n⏱️ *Janela:* Próximas 3h"
    
    # Cabeçalhos forçando JSON puro
    headers = {
        "accept": "application/json",
        "Content-Type": "application/json"
    }
    if CHAVE_API_WAHA: 
        headers["X-Api-Key"] = CHAVE_API_WAHA

    try:
        # Lê a imagem gerada e converte para Base64
        with open(imagem_path, 'rb') as f:
            img_bytes = f.read()
            base64_img = base64.b64encode(img_bytes).decode('utf-8')
        
        # Monta o pacote JSON exatamente como o WAHA exige
        payload = {
            "session": SESSAO_WAHA,
            "chatId": id_grupo,
            "caption": msg,
            "file": {
                "mimetype": "image/png",
                "filename": "escala.png",
                "data": base64_img
            }
        }

        # Envio como JSON Puro
        resp = requests.post(URL_WAHA, headers=headers, json=payload)
            
        if resp.status_code in [200, 201]:
            return "✅ Enviado com sucesso!"
        else:
            return f"❌ Erro WAHA ({resp.status_code}): {resp.text}"
            
    except Exception as e:
        return f"❌ Falha de conexão: {e}"

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
            
            # Margem: Busca desde 20 min atrás até 3 horas na frente
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
            
            if linha_cabecalho is None:
                st.error("❌ Cabeçalho não encontrado."); st.stop()
            
            df = df_bruto.iloc[linha_cabecalho + 1:].reset_index(drop=True)
            df.columns = [str(c).strip().upper() for c in df_bruto.iloc[linha_cabecalho]]
            df = df.dropna(subset=[COLUNA_FILTRO_HORA]) 

            # CONVERSOR DE HORA ULTRA-RESISTENTE
            def converter_tempo(v):
                if pd.isna(v): return pd.NaT
                try:
                    if hasattr(v, 'hour'):
                        dt = v
                    else:
                        s = str(v).replace('h', ':').strip()
                        dt = pd.to_datetime(s)
                    return agora.replace(hour=dt.hour, minute=dt.minute, second=0, microsecond=0)
                except:
                    return pd.NaT

            df['AUX_TIME'] = df[COLUNA_FILTRO_HORA].apply(converter_tempo)
            
            # Filtro
            df_filtrado = df[(df['AUX_TIME'] >= inicio_filtro) & (df['AUX_TIME'] <= fim_filtro)].copy()

            if df_filtrado.empty:
                st.warning(f"⚠️ Nenhuma viagem encontrada entre {inicio_filtro.strftime('%H:%M')} e {fim_filtro.strftime('%H:%M')}.")
                st.write("Horários detectados na planilha (primeiros 5):")
                st.write(df[[COLUNA_FILTRO_HORA, 'AUX_TIME']].head(5))
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
            st.error(f"❌ Erro: {e}")

if st.session_state.clientes_processados:
    for nome, dados in st.session_state.clientes_processados.items():
        with st.expander(f"📦 CLIENTE: {nome}", expanded=True):
            st.image(dados["img"])
            c1, c2 = st.columns(2)
            with c1:
                if st.button(f"📲 Enviar WhatsApp: {nome}", key=f"btn_{nome}"):
                    res = enviar_waha(dados["img"], nome, dados["data_str"])
                    if "✅" in res:
                        st.success(res)
                    else:
                        st.error(res)
            with c2:
                st.download_button(f"📥 Baixar Excel: {nome}", dados["excel"], f"Escala_{nome.replace('/', '_')}.xlsx", key=f"dl_{nome}")
