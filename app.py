import streamlit as st
import pandas as pd
import plotly.express as px
from streamlit_gsheets import GSheetsConnection
from pypdf import PdfReader
import io
import re

# =========================================================================
# 1. CONFIGURAÇÃO DA PÁGINA E ESTILO CSS ATUALIZADO (REMOVIDO REQUADRO DUPLO)
# =========================================================================
st.set_page_config(page_title="Dashboard Acadêmico Integrado", layout="wide")

st.markdown("""
<style>
[data-testid="stColumn"] {
    border: 2px solid black !important;
    border-radius: 15px !important;
    padding: 20px !important;
    background-color: white !important;
    margin-bottom: 10px;
}
.stButton>button { 
    width: 100%; 
    border: 1px solid #ddd; 
    border-radius: 8px; 
    text-align: left; 
}
.stRadio > div { 
    flex-direction: row; 
    gap: 20px; 
}
/* Estilização para caixas simples sem recuadro interno do Streamlit */
.info-box {
    border: 2px solid black; 
    border-radius: 15px; 
    padding: 15px;
    background-color: #fdfdfd;
    font-size: 16px;
}
</style>
""", unsafe_allow_html=True)

# =========================================================================
# 2. CONEXÃO E DICIONÁRIO DINÂMICO
# =========================================================================
conn = st.connection("gsheets", type=GSheetsConnection)

DICIONARIO_SALAS = {
    "Sala 1": st.secrets["connections"]["gsheets"]["sala1"],
    "Sala 2": st.secrets["connections"]["gsheets"]["sala2"],
    "Sala 3": st.secrets["connections"]["gsheets"]["sala3"],
    "Sala 4": st.secrets["connections"]["gsheets"]["sala4"],
    "Sala 5": st.secrets["connections"]["gsheets"]["sala5"],
    "Sala 6": st.secrets["connections"]["gsheets"]["sala6"]
}

# =========================================================================
# 3. ESTADOS DE SESSÃO (SESSION STATE)
# =========================================================================
if 'dados_carregados' not in st.session_state:
    st.session_state.dados_carregados = False
if 'aluno_idx' not in st.session_state: 
    st.session_state.aluno_idx = 0
if 'disciplina_ativa' not in st.session_state: 
    st.session_state.disciplina_ativa = None
if 'reset_obs' not in st.session_state: 
    st.session_state.reset_obs = 0
if 'sala_ativa' not in st.session_state:
    st.session_state.sala_ativa = "Sala 1"

# =========================================================================
# 4. FUNÇÃO DE EXTRAÇÃO TOTALMENTE DINÂMICA CORRIGIDA (SEM INLINE)
# =========================================================================
def extrair_dados_pdf(arquivos_pdf):
    dados_finais = []
    
    for numero_chamada, arquivo in enumerate(arquivos_pdf, start=1):
        pdf_reader = PdfReader(io.BytesIO(arquivo.read()))
        texto_completo = ""
        for pagina in pdf_reader.pages:
            texto_completo += pagina.extract_text() + "\n"
        
        linhas = texto_completo.split('\n')
        
        nome_aluno = "Não Identificado"
        matricula_aluno = "Não Identificada"
        serie_aluno = "Não Identificada"
        
        # 1. Captura limpa dos Metadados do Aluno
        for linha in linhas:
            if "Aluno" in linha or "Nome" in linha:
                partes = linha.split(":")
                val_nome = partes[1].strip() if len(partes) > 1 else linha.replace("Aluno", "").replace("Nome", "").strip()
                # Ajuste 1: Remove a palavra 'Matrícula' residual do nome do aluno se houver
                nome_aluno = re.sub(r'\bMatrícula\b.*', '', val_nome, flags=re.IGNORECASE).strip()
                
            if "Matrícula" in linha or "Matricula" in linha:
                partes = linha.split(":")
                if len(partes) > 1:
                    matricula_aluno = ''.join(c for c in partes[1] if c.isdigit() or c == '-')
                else:
                    numeros = ''.join(c for c in linha if c.isdigit())
                    if numeros: matricula_aluno = numeros
                    
            # CORRIGIDO DEFINITIVAMENTE: Mudado de 'inline' para 'linha' para evitar o NameError
            if "Série" in linha or "Serie" in linha or "Ano" in linha or "Turma" in linha:
                partes = linha.split(":")
                if len(partes) > 1:
                    serie_aluno = partes[1].strip()
                else:
                    serie_aluno = linha.replace("Série", "").replace("Serie", "").strip()

        if nome_aluno == "Não Identificado" or not nome_aluno.strip():
            nome_aluno = arquivo.name.replace(".pdf", "").replace("Boletim", "").replace("_", " ").strip()

        # Ajuste 6 e 7: Captura Dinâmica Baseada na Estrutura de Notas da Linha
        for linha in linhas:
            if any(pax in linha for pax in ["Aluno", "Nome", "Matrícula", "Série", "Boletim"]):
                continue
                
            valores_linha = [float(s) for s in linha.replace(',', '.').split() if s.replace('.', '', 1).isdigit()]
            
            if len(valores_linha) >= 4:
                partes_texto = []
                for palavra in linha.split():
                    if palavra.replace(',', '.').replace('.', '', 1).isdigit():
                        break
                    partes_texto.append(palavra)
                
                nome_disciplina = " ".join(partes_texto).strip()
                
                if not nome_disciplina or len(nome_disciplina) < 3:
                    continue
                
                while len(valores_linha) < 6:
                    valores_linha.append(0.0)
                
                tecnicas_keywords = ["ILPR", "ININ", "SISTEMAS", "DESENVOLVIMENTO", "BANCO", "LOGICA", "PROGRAMAÇÃO", "TECNICO", "TÉCNICO"]
                is_tecnico = any(kw in nome_disciplina.upper() for kw in tecnicas_keywords)
                nucleo = "Técnico" if is_tecnico else "Comum"
                
                f_final = valores_linha[5] if len(valores_linha) > 5 else (valores_linha[4] if valores_linha[4] > 10 else 100.0)
                if f_final > 1.0 and f_final <= 100.0: f_final = f_final / 100.0
                elif f_final > 100.0: f_final = 1.0

                dados_finais.append({
                    'Nº Chamada': numero_chamada,
                    'Aluno': nome_aluno,
                    'Matrícula': matricula_aluno,
                    'Série': serie_aluno,
                    'Disciplina': nome_disciplina,
                    '1º BI':
