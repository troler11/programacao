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
# CONFIGURAÇÕES DA SUA EMPRESA
# ==========================================

# 1. URL da sua planilha do Google Sheets (deve terminar em pub?output=xlsx)
URL_PLANILHA = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSH9lJhzNgDz3x05wnE3lc24YKiUQcn_WTNgxEpsSO2jA36rAwSDfLZUkm1SgE_uoKBXvgx1_8sDTXZ/pub?output=xlsx"

# 2. Mapeamento dos Logos (A chave deve ser parte do nome que aparece na planilha)
MAPA_LOGOS = {
    "MELI": "logo_meli.png",
    "MERCADO LIVRE": "logo_meli.png",
    "AMAZON": "logo_amazon.png"
}

# 3. Mapeamento dos Grupos de WhatsApp no WAHA
MAPA_GRUPOS = {
    "MELI": "120363000000000000@g.us", # Substitua pelo ID real do grupo
    "AMAZON": "120363000000000001@g.us"
}

# 4. Endereço do Servidor WAHA
URL_WAHA = "http://localhost:3000/api/sendImage"
SESSAO_WAHA = "default"

# ==========================================
# FUNÇÕES DO SISTEMA
# ==========================================

def gerar_planilha_formatada(df, cliente_identificador):
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
        
        # Procura qual logo usar baseado no nome do cliente
        for chave, arquivo_logo in MAPA_LOGOS.items():
            if chave in cliente_identificador:
                logo_centro = Image(arquivo_logo)
                ws.add_image(logo_centro, 'C1')
                break
    except Exception as e:
        pass # Ignora erro de imagem para não travar o sistema

    # Título
    ws.merge_cells('A12:F12')
    ws['A12'] = "PROGRAMAÇÃO DE ENTRADA/SAIDA (PRÓXIMAS 3H)"
    ws['A12'].font = fonte_vermelha_titulo
    ws['A12'].alignment = Alignment(horizontal="center")

    # Cabeçalhos
    cabecalhos = ["Periodo", "Horas", "Linha", "Empresa", "Prefixo", "Motorista"]
    ws.append([]) # Linha 13 vazia
    ws.append(cabecalhos) # Linha 14 com cabeçalhos
    
    for col in range(1, 7):
        celula = ws.cell(row=14, column=col)
        celula.fill = fill_vermelho
        celula.font = fonte_branca
        celula.alignment = Alignment(horizontal="center")

    # Inserir Dados (Usa get para não quebrar se a coluna não existir com esse nome exato)
    for index, row in df.iterrows():
        linha_dados = [
            row.get('Periodo', ''), 
            row.get('Horas', ''),   
            row.get('Linha', ''), 
            row.get('Empresa', ''), 
            row.get('Prefixo', ''), 
            row.get('Motorista', '')
        ]
        ws.append(linha_dados)
        
    ws.column_dimensions['C'].width = 50
    ws.column_dimensions['F'].width = 25

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output

def enviar_waha(imagem_path, nome_empresa, data_escala):
    # Tenta achar o ID do grupo verificando se a chave está contida no nome da empresa
    id_grupo = None
    for chave, id_waha in MAPA_GRUPOS.items():
        if chave in nome_empresa:
            id_grupo = id_waha
            break
            
    if not id_grupo:
        st.warning(f"⚠️ Grupo de WhatsApp não configurado para a empresa/cliente: {nome_empresa}")
        return False

    mensagem = f"🚌 *Programação de Entrada/Saída*\n🏢 *Cliente:* {nome_empresa}\n📅 *Data:* {data_escala}\n⏱️ *Filtro:* Próximas 3 horas\n\nSegue a escala atualizada:"

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
                st.success(f"✅ Escala das próximas 3h enviada com sucesso para o grupo via WhatsApp!")
                return True
            else:
                st.error(f"❌ Erro do WAHA ao enviar: {response.text}")
                return False
                
    except requests.exceptions.ConnectionError:
        st.error("❌ Erro de Conexão: O servidor WAHA não está respondendo na porta 3000.")
        return False
    except Exception as e:
        st.error(f"❌ Erro inesperado: {e}")
        return False

# ==========================================
# INTERFACE DO SITE (STREAMLIT)
# ==========================================

st.set_page_config(page_title="Automação de Escalas", layout="centered")
st.title("Gerador de Escalas (Próximas 3 Horas) 🚌⏳")

if st.button("Executar: Filtrar Planilha e Enviar WhatsApp", type="primary"):
    with st.spinner("Conectando ao Google Sheets e filtrando horários..."):
        try:
            hoje = datetime.now()
            nome_aba = hoje.strftime("%d") # Aba com o dia de hoje (ex: "16")
            
            # Baixa a planilha
            r = requests.get(URL_PLANILHA)
            r.raise_for_status()
            
            # Lê a aba do dia
            df = pd.read_excel(r.content, sheet_name=nome_aba)
            
            # ==========================================
            # LÓGICA DE FILTRO: PRÓXIMAS 3 HORAS
            # ==========================================
            limite = hoje + timedelta(hours=3)

            def formatar_para_tempo_real(valor):
                try:
                    if isinstance(valor, str): # Se for texto "11:50"
                        t = pd.to_datetime(valor).time()
                        return datetime.combine(hoje.date(), t)
                    elif hasattr(valor, 'hour') and hasattr(valor, 'minute'):
                        if hasattr(valor, 'year'): 
                            return datetime.combine(hoje.date(), valor.time())
                        else: 
                            return datetime.combine(hoje.date(), valor)
                except:
                    pass
                return pd.NaT

            # Cria uma coluna oculta para o Python fazer as contas de tempo
            df['FILTRO_TEMPO'] = df['Horas'].apply(formatar_para_tempo_real)

            # Corta a tabela mantendo apenas >= Agora e <= Agora + 3 horas
            df = df[(df['FILTRO_TEMPO'] >= hoje) & (df['FILTRO_TEMPO'] <= limite)]
            
            # Apaga a coluna de cálculo
            df = df.drop(columns=['FILTRO_TEMPO'])

            if df.empty:
                st.warning(f"⚠️ Não há nenhuma viagem programada entre {hoje.strftime('%H:%M')} e {limite.strftime('%H:%M')}.")
                st.stop() # Interrompe o processo aqui
            # ==========================================
            
            # Identifica o cliente (Pegando a primeira linha restante, coluna 'Empresa')
            # Se sua coluna se chamar "CLIENTE", troque 'Empresa' por 'CLIENTE'
            coluna_cliente = 'Empresa' if 'Empresa' in df.columns else df.columns[3]
            cliente_atual = str(df[coluna_cliente].iloc[0]).strip().upper() 
            st.info(f"📍 Cliente identificado na operação: {cliente_atual}")
            
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
                'props': [('background-color', '#FF0000'), ('color', 'white'), ('font-weight', 'bold')]
            }])
            
            nome_imagem = f"escala_3h_{cliente_atual}.png"
            dfi.export(df_estilizado, nome_imagem, table_conversion="matplotlib") 
            
            # 3. Disparar via WAHA
            enviar_waha(nome_imagem, cliente_atual, hoje.strftime('%d/%m/%Y'))
            
            # 4. Disponibilizar Excel para Download
            st.download_button(
                label="📥 Baixar Excel do Corte (3 horas)",
                data=excel_gerado,
                file_name=f"Escala_3h_{hoje.strftime('%d-%m-%Y_%Hh')}_{cliente_atual}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            
        except ValueError:
            st.error(f"❌ Não foi encontrada uma aba chamada '{nome_aba}' na planilha.")
        except Exception as e:
            st.error(f"❌ Ocorreu um erro no processo: {e}")
