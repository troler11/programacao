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
# CONFIGURAÇÕES DA EMPRESA E PLANILHA
# ==========================================
URL_PLANILHA = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSH9lJhzNgDz3x05wnE3lc24YKiUQcn_WTNgxEpsSO2jA36rAwSDfLZUkm1SgE_uoKBXvgx1_8sDTXZ/pub?output=xlsx"

# NOMES EXATOS DAS COLUNAS DA SUA PLANILHA ONLINE
COLUNA_FILTRO_HORA = 'INI' # Qual coluna tem a hora para calcular as próximas 3h? (ex: INI, SAI ou ENT)

# Mapeamento: O que puxar para a planilha final formatada
COL_PERIODO = 'ENT'           # Vai puxar da coluna ENT (ou mude para SAI)
COL_HORA = 'INI'              # Vai puxar da coluna INI
COL_LINHA = 'LINHA'           # Vai puxar da coluna LINHA
COL_EMPRESA = 'CLIENTE'       # Vai puxar da coluna CLIENTE
COL_PREFIXO = 'FROTA ENVIADA' # Pode ser FROTA FINAL ou FROTA ESCALADA, altere se precisar
COL_MOTORISTA = 'MOTORISTA'   # Vai puxar da coluna MOTORISTA

# Configuração de Logos e WhatsApp
MAPA_LOGOS = {
    "MELI": "logo_meli.png",
    "MERCADO LIVRE": "logo_meli.png",
    "AMAZON": "logo_amazon.png"
}

MAPA_GRUPOS = {
    "MELI": "120363000000000000@g.us", # ID do Grupo Mercado Livre
    "AMAZON": "120363000000000001@g.us" # ID do Grupo Amazon
}

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

    # Estes são os cabeçalhos que vão aparecer no Excel BONITO
    cabecalhos = ["Periodo", "Horas", "Linha", "Empresa", "Prefixo", "Motorista"]
    ws.append([]); ws.append(cabecalhos)
    for col in range(1, 7):
        c = ws.cell(row=14, column=col)
        c.fill, c.font, c.alignment = fill_vermelho, fonte_branca, Alignment(horizontal="center")

    # Inserindo os dados baseado nas colunas do seu sistema
    for _, row in df.iterrows():
        ws.append([
            row.get(COL_PERIODO, ''), 
            row.get(COL_HORA, ''), 
            row.get(COL_LINHA, ''), 
            row.get(COL_EMPRESA, ''), 
            row.get(COL_PREFIXO, ''), 
            row.get(COL_MOTORISTA, '')
        ])
    
    ws.column_dimensions['C'].width, ws.column_dimensions['F'].width = 50, 25
    out = io.BytesIO(); wb.save(out); out.seek(0)
    return out

def enviar_waha(imagem_path, nome_empresa, data_str):
    id_grupo = next((v for k, v in MAPA_GRUPOS.items() if k in nome_empresa), None)
    if not id_grupo:
        st.warning(f"⚠️ Grupo não configurado para: {nome_empresa}"); return False

    msg = f"🚌 *Programação de Escala*\n🏢 *Cliente:* {nome_empresa}\n📅 *Data:* {data_str}\n⏱️ *Janela:* Próximas 3h\n\nSegue a escala atualizada:"
    try:
        with open(imagem_path, 'rb') as f:
            resp = requests.post(URL_WAHA, data={'session': SESSAO_WAHA, 'chatId': id_grupo, 'caption': msg}, 
                                 files={'file': (imagem_path, f, 'image/png')})
        if resp.status_code in [200, 201]:
            st.success("✅ Enviado para o WhatsApp com sucesso!"); return True
        st.error(f"❌ Erro WAHA: {resp.text}"); return False
    except Exception as e:
        st.error(f"❌ Conexão falhou: O servidor do WhatsApp (WAHA) está rodando? Erro: {e}"); return False

# ==========================================
# INTERFACE PRINCIPAL
# ==========================================

st.set_page_config(page_title="Gestão de Frota", layout="centered")
st.title("Gerador Automático de Escalas 🚌⏳")

if st.button("Filtrar e Enviar para o WhatsApp", type="primary"):
    with st.spinner("Analisando a planilha e filtrando horários..."):
        try:
            hoje = datetime.now()
            r = requests.get(URL_PLANILHA)
            r.raise_for_status()
            
            # 1. Busca inteligente do nome da aba
            xls = pd.ExcelFile(r.content)
            formatos = [hoje.strftime("%d/%m/%Y"), hoje.strftime("%d_%m_%Y"), hoje.strftime("%d-%m-%Y"), hoje.strftime("%d%m%Y")]
            nome_aba = next((f for f in formatos if f in xls.sheet_names), None)

            if not nome_aba:
                st.error(f"❌ Aba do dia de hoje ({hoje.strftime('%d/%m/%Y')}) não encontrada. Abas disponíveis: {xls.sheet_names}")
                st.stop()

            # 2. Varredura inteligente de Cabeçalho (Pula imagens e logos)
            df_bruto = pd.read_excel(xls, sheet_name=nome_aba, header=None)
            linha_cabecalho = None
            for index, row in df_bruto.iterrows():
                valores_linha = [str(val).strip().upper() for val in row.values]
                if COLUNA_FILTRO_HORA in valores_linha or COL_EMPRESA in valores_linha:
                    linha_cabecalho = index
                    break
            
            if linha_cabecalho is None:
                st.error(f"❌ Não encontrei a linha de cabeçalhos. Tem certeza que as colunas '{COLUNA_FILTRO_HORA}' e '{COL_EMPRESA}' existem na planilha de hoje?")
                st.stop()
                
            df = df_bruto.iloc[linha_cabecalho + 1:].reset_index(drop=True)
            df.columns = df_bruto.iloc[linha_cabecalho]
            df.columns = [str(col).strip().upper() for col in df.columns] # Garante que tudo fique maiúsculo
            
            df = df.dropna(subset=[COLUNA_FILTRO_HORA]) 

            # 3. Filtro de 3 horas
            limite = hoje + timedelta(hours=3)
            def parsing_hora(v):
                try:
                    t = pd.to_datetime(v).time() if isinstance(v, str) else v
                    return datetime.combine(hoje.date(), t.time() if hasattr(t, 'time') else t)
                except: return pd.NaT

            df['AUX_TIME'] = df[COLUNA_FILTRO_HORA].apply(parsing_hora)
            df = df[(df['AUX_TIME'] >= hoje) & (df['AUX_TIME'] <= limite)].drop(columns=['AUX_TIME'])

            if df.empty:
                st.warning(f"⚠️ Nenhuma viagem escalada para as próximas 3 horas (entre {hoje.strftime('%H:%M')} e {limite.strftime('%H:%M')}).")
                st.stop()

            # Pega o cliente da primeira linha para direcionar a automação
            cliente = str(df[COL_EMPRESA].iloc[0]).strip().upper()
            st.info(f"📍 Operação Identificada: {cliente}")

            # 4. Geração de arquivos
            excel = gerar_planilha_formatada(df, cliente)
            img_path = f"escala_{hoje.strftime('%H%M')}.png"
            
            # Formata a tabela pra virar imagem
            # Escolhendo as colunas específicas para o print do Whatsapp
            colunas_print = [COL_PERIODO, COL_HORA, COL_LINHA, COL_EMPRESA, COL_PREFIXO, COL_MOTORISTA]
            # Caso alguma coluna não exista, o robô não trava
            colunas_existentes = [c for c in colunas_print if c in df.columns] 
            df_print = df[colunas_existentes]

            style = df_print.style.set_properties(**{'background-color': 'white', 'color': 'black', 'border': '1px solid black'})\
                .set_table_styles([{'selector': 'th', 'props': [('background-color', '#FF0000'), ('color', 'white')]}])
            
            # COMANDO MAX_ROWS=-1 ADICIONADO ABAIXO:
            dfi.export(style, img_path, table_conversion="matplotlib", max_rows=-1)

            # 5. Envio e Download
            if enviar_waha(img_path, cliente, hoje.strftime('%d/%m/%Y')):
                st.download_button("📥 Descarregar Excel Formatado", excel, f"Escala_{cliente}.xlsx")

        except Exception as e:
            st.error(f"❌ Erro no processamento: {e}")
