import streamlit as st
import pandas as pd
import plotly.express as px
from streamlit_gsheets import GSheetsConnection
from pypdf import PdfReader
import io

# =========================================================================
# 1. CONFIGURAÇÃO DA PÁGINA E ESTILO CSS LIMPO (BORDAS ARREDONDADAS)
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
</style>
""", unsafe_allow_html=True)

# =========================================================================
# 2. CONEXÃO E DICIONÁRIO DINÂMICO CONECTADO AO SECRETS DO STREAMLIT
# =========================================================================
conn = st.connection("gsheets", type=GSheetsConnection)

# Busca os links das 6 planilhas diretamente do painel Secrets de forma segura
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
# 4. FUNÇÃO DE EXTRAÇÃO REAL DE DADOS DO PDF
# =========================================================================
def extrair_dados_pdf(arquivos_pdf):
    """
    Função que lê os arquivos PDF da memória via io.BytesIO e extrai
    as informações reais de texto de cada página para montar o DataFrame.
    """
    dados_finais = []
    
    for numero_chamada, arquivo in enumerate(arquivos_pdf, start=1):
        # Lê os bytes do arquivo na memória RAM
        pdf_reader = PdfReader(io.BytesIO(arquivo.read()))
        texto_completo = ""
        for pagina in pdf_reader.pages:
            texto_completo += pagina.extract_text() + "\n"
        
        linhas = texto_completo.split('\n')
        
        # Variáveis de controle para capturar os dados do aluno atual
        nome_aluno = "Não Identificado"
        matricula_aluno = 0.0
        serie_aluno = "1º Ano"
        
        # 1ª Passada: Identificar os metadados do Aluno no PDF
        for linha in linhas:
            if "Aluno" in linha or "Nome" in linha:
                # Tenta quebrar pelo sinal de dois pontos se houver
                partes = linha.split(":")
                nome_aluno = partes[1].strip() if len(partes) > 1 else linha.replace("Aluno", "").strip()
            if "Matrícula" in linha or "Matricula" in linha:
                try:
                    # Extrai apenas os números da matrícula
                    numeros = ''.join(c for c in linha if c.isdigit())
                    if numeros: matricula_aluno = float(numeros)
                except: pass
            if "Série" in inline or "Serie" in linha or "Ano" in linha:
                if "1" in linha: serie_aluno = "1º Ano"
                elif "2" in linha: serie_aluno = "2º Ano"
                elif "3" in linha: serie_aluno = "3º Ano"

        # Lista de disciplinas comuns para mapeamento automático de notas
        lista_disciplinas_padrao = ["Matemática", "Português", "História", "Geografia", "Biologia", "Física", "Química", "ILPR", "ININ"]
        
        # 2ª Passada: Buscar as linhas de disciplinas e capturar as notas/frequências reais
        for linha in linhas:
            for disc in list(set(lista_disciplinas_padrao)):
                if disc.lower() in linha.lower():
                    # Captura todos os números/decimais presentes na linha da matéria
                    valores_linha = [float(s) for s in linha.replace(',', '.').split() if s.replace('.', '', 1).isdigit()]
                    
                    # Preenche com notas padrões caso faltem bimestres na linha para não quebrar o código
                    while len(valores_linha) < 5:
                        valores_linha.append(0.0)
                        
                    # Define se pertence ao núcleo comum ou técnico
                    nucleo = "Técnico" if disc in ["ILPR", "ININ"] else "Comum"
                    
                    # Frequência padrão baseada no PDF ou simulada em 95% se não capturada
                    freq_final = valores_linha[5] if len(valores_linha) > 5 else 0.95
                    if freq_final > 1.0: freq_final = freq_final / 100.0

                    # Monta o dicionário estruturado com os dados reais capturados
                    dados_finais.append({
