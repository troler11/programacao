import streamlit as st
import pandas as pd
import requests
import io
import dataframe_image as dfi
from datetime import datetime
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill
from openpyxl.drawing.image import Image

# ==========================================
# CONFIGURAÇÕES DA SUA EMPRESA
# ==========================================

# 1. URL da sua planilha do Google Sheets (deve terminar em pub?output=xlsx)
URL_PLANILHA = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSH9lJhzNgDz3x05wnE3lc24YKiUQcn_WTNgxEpsSO2jA36rAwSDfLZUkm1SgE_uoKBXvgx1_8sDTXZ/pub?output=xlsx"

# 2. Mapeamento dos Logos (O nome do cliente deve estar exatamente igual ao do Excel)
MAPA_LOGOS = {
    "MERCADO LIVRE": "logo_meli.png",
    "AMAZON": "logo_amazon.png",
    "SHOPEE": "logo_shopee.png"
}

# 3. Mapeamento dos Grupos de WhatsApp no WAHA
MAPA_GRUPOS = {
    "MERCADO LIVRE": "120363000000000000@g.us", # Substitua pelo ID real do grupo
    "AMAZON": "120363000000000001@g.us"         # Substitua pelo ID real do grupo
}

# 4. Endereço do Servidor WAHA
# Se estiver no mesmo PC, use localhost. Se for num VPS, coloque o IP (ex: http://192.168.1.100:3000/api/sendImage)
URL_WAHA = "http://localhost:3000/api/sendImage"
SESSAO_WAHA = "default"

# ==========================================
# FUNÇÕES DO SISTEMA
# ==========================================

def gerar_planilha_formatada(df, cliente):
    wb = Workbook()
    ws = wb.active
    
    fill_vermelho = PatternFill(start_color="FF0000", end_color="FF0000", fill_type="solid")
    fonte_branca = Font(color="FFFFFF", bold=True)
    fonte_vermelha_titulo = Font(color="FF0000", bold=True, size=16)

    # Inserir Logos
    try:
        logo_mimo_esq = Image('logo_mimo.png')
        ws.add_image(logo_mimo_esq, 'A1')
        
        logo_mimo_dir = Image('logo_mimo.png')
        ws.add_image(logo_mimo_dir, 'F1')
        
        if cliente in MAPA_LOGOS:
            logo_centro = Image(MAPA_LOGOS[cliente])
            ws.add_image(logo_centro, 'C1')
    except Exception:
        pass # Ignora erro de imagem silenciosamente para não travar o processo

    # Título
    ws.merge_cells('A12:F12')
    ws['A12'] = "PROGRAMAÇÃO DE ENTRADA/SAIDA"
    ws['A12'].font = fonte_vermelha_titulo
    ws['A12'].alignment = Alignment(horizontal="center")

    # Cabeçalhos
    cabecalhos = ["Periodo", "Horas", "Linha", "Empresa", "Prefixo", "Motorista"]
    ws.append([]) # Linha 13
    ws.append(cabecalhos) # Linha 14
    
    for col in range(1, 7):
        celula = ws.cell(row=14, column=col)
        celula.fill = fill_vermelho
        celula.font = fonte_branca
        celula.alignment = Alignment(horizontal="center")

    # Inserir Dados (Ajuste os nomes das colunas de acordo com sua aba)
    for index, row in df.iterrows():
        linha_dados = [
            row.get('PERIODO', ''), 
            row.get('HORAS', ''),   # Ajuste aqui conforme o original
            row.get('LINHA', ''), 
            row.get('EMPRESA', ''), 
            row.get('PREFIXO', ''), 
            row.get('MOTORISTA', '')
        ]
        ws.append(linha_dados)
        
    ws.column_dimensions['C'].width = 50
    ws.column_dimensions['F'].width = 25

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output

def enviar_waha(imagem_path, nome_empresa, data_escala):
    id_grupo = MAPA_GRUPOS.get(nome_empresa)
    
    if not id_grupo:
        st.warning(f"⚠️ Grupo de WhatsApp não configurado para: {nome_empresa}")
        return False

    mensagem = f"🚌 *Programação de Entrada/Saída*\n🏢 *Cliente:* {nome_empresa}\n📅 *Data:* {data_escala}\n\nSegue a escala de hoje:"

    try:
        with open(imagem_path, 'rb') as img_file:
            files = {'file': (imagem_path, img_file, 'image/png')}
            data = {
                'session': SESSAO_WAHA,
                'chatId': id_grupo,
                'caption': mensagem
            }
            
            response = requests.post(URL_WAHA, data=data, files=files)
            
            if response.status_code in [200, 201]:
                st.success(f"✅ Escala enviada com sucesso para o grupo da {nome_empresa} via WhatsApp!")
                return True
            else:
                st.error(f"❌ Erro do WAHA ao enviar: {response.text}")
                return False
                
    except requests.exceptions.ConnectionError:
        st.error("❌ Erro de Conexão: O servidor WAHA não está respondendo. Verifique se o Docker está rodando.")
        return False
    except Exception as e:
        st.error(f"❌ Erro inesperado: {e}")
        return False

# ==========================================
# INTERFACE DO SITE (STREAMLIT)
# ==========================================

st.set_page_config(page_title="Automação de Escalas", layout="centered")
st.title("Gerador e Disparador de Escalas 🚌🚀")

if st.button("Executar: Gerar Planilha e Enviar para o WhatsApp", type="primary"):
    with st.spinner("Conectando ao Google Sheets e processando..."):
        try:
            hoje = datetime.now()
            nome_aba = hoje.strftime("%d") # Ajuste se o formato da aba for diferente
            
            r = requests.get(URL_PLANILHA)
            r.raise_for_status()
            
            df = pd.read_excel(r.content, sheet_name=nome_aba)
            
            # Pega o cliente (primeiro valor da coluna 5, índice 4)
            cliente_atual = str(df.iloc[0, 4]).strip().upper() 
            st.info(f"📍 Cliente identificado: {cliente_atual}")
            
            # 1. Gerar Excel
            excel_gerado = gerar_planilha_formatada(df, cliente_atual)
            
            # 2. Gerar Print da Tabela
            st.text("Gerando imagem da tabela para o WhatsApp...")
            df_estilizado = df.style.set_properties(**{
                'background-color': 'white',
                'color': 'black',
                'border': '1px solid black'
            }).set_table_styles([{
                'selector': 'th',
                'props': [('background-color', 'red'), ('color', 'white'), ('font-weight', 'bold')]
            }])
            
            nome_imagem = f"escala_{cliente_atual}.png"
            # O matplotlib é usado para evitar problemas de falta de Google Chrome no servidor Linux/VPS
            dfi.export(df_estilizado, nome_imagem, table_conversion="matplotlib") 
            
            # 3. Disparar via WAHA
            enviar_waha(nome_imagem, cliente_atual, hoje.strftime('%d/%m/%Y'))
            
            # 4. Disponibilizar Excel para Download
            st.download_button(
                label="📥 Fazer Download do Excel Formatado",
                data=excel_gerado,
                file_name=f"Programacao_{hoje.strftime('%d-%m-%Y')}_{cliente_atual}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            
        except ValueError:
            st.error(f"❌ Não foi encontrada uma aba chamada '{nome_aba}' na planilha de hoje.")
        except Exception as e:
            st.error(f"❌ Ocorreu um erro no processo: {e}")
