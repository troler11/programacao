import streamlit as st
import pandas as pd
import requests
import io
import dataframe_image as dfi
from datetime import datetime, timedelta
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill
from openpyxl.drawing.image import Image
import os

# ==========================================
# CONFIGURAÇÕES DA EMPRESA E PLANILHA
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
    "ADORO": "120363000000000002@g.us" 
}

URL_WAHA = "http://waha:3000/api/sendImage"
SESSAO_WAHA = "default"
CHAVE_API_WAHA = "" 

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
        # Logo MIMO Esquerda
        logo_esq = Image('logo_mimo.png')
        logo_esq.width = 220  # Ajuste a largura aqui se precisar
        logo_esq.height = 60  # Ajuste a altura aqui se precisar
        ws.add_image(logo_esq, 'A1')

        
        # Logo do Cliente Central
        for chave, arquivo_logo in MAPA_LOGOS.items():
            if chave in cliente_id:
                logo_centro = Image(arquivo_logo)
                logo_centro.width = 160 # Largura do logo do cliente
                logo_centro.height = 100 # Altura do logo do cliente
                ws.add_image(logo_centro, 'F1')
                break
    except Exception as e:
        print(f"Erro ao carregar imagens: {e}")

    ws.merge_cells('A12:F12')
    ws['A12'] = f"PROGRAMAÇÃO - {cliente_id}"
    ws['A12'].font = fonte_vermelha_titulo
    ws['A12'].alignment = Alignment(horizontal="center")

    cabecalhos = ["Periodo", "Horas", "Linha", "Empresa", "Prefixo", "Motorista"]
    ws.append([])
    ws.append(cabecalhos)
    
    for col in range(1, 7):
        c = ws.cell(row=14, column=col)
        c.fill = fill_vermelho
        c.font = fonte_branca
        c.alignment = Alignment(horizontal="center")

    for _, row in df.iterrows():
        ws.append([
            row.get(COL_PERIODO, ''), 
            row.get(COL_HORA, ''), 
            row.get(COL_LINHA, ''), 
            row.get(COL_EMPRESA, ''), 
            row.get(COL_PREFIXO, ''), 
            row.get(COL_MOTORISTA, '')
        ])
    
    ws.column_dimensions['C'].width = 50
    ws.column_dimensions['F'].width = 25
    
    out = io.BytesIO()
    wb.save(out)
    out.seek(0)
    return out

def enviar_waha(imagem_path, nome_empresa, data_str):
    id_grupo = None
    for chave, id_waha in MAPA_GRUPOS.items():
        if chave in nome_empresa:
            id_grupo = id_waha
            break
            
    if not id_grupo:
        return f"⚠️ Grupo não configurado para: {nome_empresa}"

    msg = f"🚌 *Programação de Escala*\n🏢 *Cliente:* {nome_empresa}\n📅 *Data:* {data_str}\n⏱️ *Janela:* Próximas 3h"
    headers = {"accept": "application/json"}
    if CHAVE_API_WAHA: headers["X-Api-Key"] = CHAVE_API_WAHA

    try:
        with open(imagem_path, 'rb') as f:
            resp = requests.post(
                URL_WAHA, 
                headers=headers,
                data={'session': SESSAO_WAHA, 'chatId': id_grupo, 'caption': msg}, 
                files={'file': (imagem_path, f, 'image/png')}
            )
        if resp.status_code in [200, 201]:
            return "✅ Enviado com sucesso!"
        return f"❌ Erro WAHA ({resp.status_code}): {resp.text}"
    except Exception as e:
        return f"❌ Falha de conexão: {e}"

# ==========================================
# INTERFACE PRINCIPAL
# ==========================================

st.set_page_config(page_title="Gestão de Frota", layout="centered")
st.title("Gerador de Escalas Separadas por Cliente 🚌⏳")

if 'clientes_processados' not in st.session_state:
    st.session_state.clientes_processados = {}

if st.button("1. Analisar Planilha e Gerar Prévias", type="primary"):
    with st.spinner("Buscando dados e separando por cliente..."):
        try:
            hoje = datetime.now()
            r = requests.get(URL_PLANILHA)
            r.raise_for_status()
            
            xls = pd.ExcelFile(r.content)
            formatos = [hoje.strftime("%d/%m/%Y"), hoje.strftime("%d_%m_%Y"), hoje.strftime("%d-%m-%Y"), hoje.strftime("%d%m%Y")]
            nome_aba = next((f for f in formatos if f in xls.sheet_names), None)

            if not nome_aba:
                st.error(f"❌ Aba do dia {hoje.strftime('%d/%m/%Y')} não encontrada."); st.stop()

            df_bruto = pd.read_excel(xls, sheet_name=nome_aba, header=None)
            linha_cabecalho = next((i for i, r in df_bruto.iterrows() if any(str(v).strip().upper() == COLUNA_FILTRO_HORA for v in r.values)), None)
            
            if linha_cabecalho is None: st.error("❌ Cabeçalho não encontrado."); st.stop()
                
            df = df_bruto.iloc[linha_cabecalho + 1:].reset_index(drop=True)
            df.columns = [str(c).strip().upper() for c in df_bruto.iloc[linha_cabecalho]]
            df = df.dropna(subset=[COLUNA_FILTRO_HORA]) 

            limite = hoje + timedelta(hours=3)
            def parsing_hora(v):
                try:
                    t = pd.to_datetime(v).time() if isinstance(v, str) else v
                    return datetime.combine(hoje.date(), t.time() if hasattr(t, 'time') else t)
                except: return pd.NaT

            df['AUX_TIME'] = df[COLUNA_FILTRO_HORA].apply(parsing_hora)
            df_filtrado = df[(df['AUX_TIME'] >= hoje) & (df['AUX_TIME'] <= limite)].copy()

            if df_filtrado.empty:
                st.warning("⚠️ Nenhuma viagem nas próximas 3 horas."); st.stop()

            # --- LÓGICA DE SEPARAÇÃO POR CLIENTE ---
            clientes_dict = {}
            for cliente, group_df in df_filtrado.groupby(COL_EMPRESA):
                cliente_nome = str(cliente).strip().upper()
                
                nome_seguro_arquivo = cliente_nome.replace("/", "_").replace("\\", "_").replace(":", "_")
                img_path = f"escala_{nome_seguro_arquivo}_{hoje.strftime('%H%M')}.png"
                
                colunas_print = [c for c in [COL_PERIODO, COL_HORA, COL_LINHA, COL_EMPRESA, COL_PREFIXO, COL_MOTORISTA] if c in group_df.columns]
                style = group_df[colunas_print].style.set_properties(**{'background-color': 'white', 'color': 'black', 'border': '1px solid black'})\
                    .set_table_styles([{'selector': 'th', 'props': [('background-color', '#FF0000'), ('color', 'white')]}])
                
                dfi.export(style, img_path, table_conversion="matplotlib", max_rows=-1)
                
                clientes_dict[cliente_nome] = {
                    "img": img_path,
                    "excel": gerar_planilha_formatada(group_df, cliente_nome),
                    "data_str": hoje.strftime('%d/%m/%Y')
                }
            
            st.session_state.clientes_processados = clientes_dict
            st.success(f"✅ {len(clientes_dict)} clientes identificados!")

        except Exception as e:
            st.error(f"❌ Erro: {e}")

# EXIBIÇÃO DAS PRÉVIAS E BOTÕES DE ENVIO
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
