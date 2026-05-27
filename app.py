import streamlit as st
import pandas as pd
import pypdf
import re
from streamlit_gsheets import GSheetsConnection

# ==============================================================================
# CONFIGURAÇÃO DA PÁGINA
# ==============================================================================
st.set_page_config(
    page_title="Dashboard Escolar - SUAP",
    page_icon="📂",
    layout="wide"
)

# Conexão central com o Google Sheets
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception as e:
    st.error("Erro ao conectar com o Google Sheets. Verifique o arquivo de segredos do Streamlit.")
    st.stop()

# ==============================================================================
# LOGICA DE EXTRAÇÃO E LIMPEZA DE DADOS DO PDF (PADRÃO SUAP)
# ==============================================================================
def extrair_dados_suap(arquivos_enviados, sala_selecionada):
    dados_totais = []
    
    for arquivo in arquivos_enviados:
        try:
            leitor = pypdf.PdfReader(arquivo)
            texto_completo = ""
            for pagina in leitor.pages:
                texto_completo += pagina.extract_text() + "\n"
            
            linhas = texto_completo.split("\n")
            
            # Extração da Matrícula correta (ex: BT3044548)
            matricula = "Não encontrada"
            for linha in linhas:
                if "Matrícula:" in linha:
                    match = re.search(r'Matrícula:\s*([A-Za-z0-9]+)', linha)
                    if match:
                        matricula = match.group(1)
                        break
            
            # Extração do Aluno
            aluno = "Desconhecido"
            for linha in linhas:
                if "Aluno(a):" in linha:
                    match = re.search(r'Aluno\(a\):\s*(.*?)\s*(?:Matrícula:|Curso:|$)', linha)
                    if match:
                        aluno = match.group(1).strip()
                        break

            # Processamento estrito das disciplinas que possuem código de Diário
            padrao_diario = re.compile(r'^(\d{5,6})\s+(.*)')
            
            for linha in linhas:
                linha = linha.strip()
                match_diario = padrao_diario.match(linha)
                
                if match_diario:
                    diario_codigo = match_diario.group(1)
                    resto_linha = match_diario.group(2).strip()
                    
                    if "Total" in linha or "Horas" in linha or "Aulas" in linha:
                        continue
                        
                    # Isolar notas decimais existentes (ex: 10,00) ou traços (-)
                    partes_notas = re.findall(r'\b\d{1,2},\d{2}\b|\b-\b', resto_linha)
                    
                    # Limpeza para obter puramente o Nome da Disciplina
                    nome_disciplina = re.sub(r'\b\d{1,2},\d{2}\b|\b-\b|Cursando.*|Aguardando.*', '', resto_linha).strip()
                    nome_disciplina = re.sub(r'\s+\d+(?:,\d+)?(?=\s|$)', '', nome_disciplina).strip()
                    nome_disciplina = re.sub(r'\s+', ' ', nome_disciplina)
                    
                    # Atribuição estrita das notas das etapas (sem inventar dados)
                    n1, n2, n3, n4 = 0.0, 0.0, 0.0, 0.0
                    valores_limpos = [float(v.replace(',', '.')) if v != '-' else 0.0 for v in partes_notas]
                    
                    try: n1 = valores_limpos[0]
                    except: pass
                    try: n2 = valores_limpos[1]
                    except: pass
                    try: n3 = valores_limpos[2]
                    except: pass
                    try: n4 = valores_limpos[3]
                    except: pass
                    
                    # Frequência Real
                    frequencia = 100.0
                    match_freq = re.search(r'(\d{1,3})%', linha)
                    if match_freq:
                        frequencia = float(match_freq.group(1))

                    dados_totais.append({
                        "Sala": sala_selecionada,
                        "Matrícula": matricula,
                        "Aluno": aluno,
                        "Disciplina": nome_disciplina,
                        "N1": n1,
                        "N2": n2,
                        "N3": n3,
                        "N4": n4,
                        "Frequência": frequencia
                    })
        except Exception as e:
            st.error(f"Erro no arquivo {arquivo.name}: {e}")
            
    return pd.DataFrame(dados_totais)

# ==============================================================================
# CARREGAMENTO GLOBAL DOS DADOS DA PLANILHA
# ==============================================================================
@st.cache_data(ttl=5)
def puxar_dados_nuvem():
    try:
        df = conn.read()
        if df is not None and not df.empty:
            return df
        return pd.DataFrame(columns=["Sala", "Matrícula", "Aluno", "Disciplina", "N1", "N2", "N3", "N4", "Frequência"])
    except:
        return pd.DataFrame(columns=["Sala", "Matrícula", "Aluno", "Disciplina", "N1", "N2", "N3", "N4", "Frequência"])

# Puxa o banco de dados completo unificado
df_banco_completo = puxar_dados_nuvem()

# ==============================================================================
# INTERFACE PRINCIPAL: CONTROLE DE SALAS E NAVEGAÇÃO
# ==============================================================================
st.title("📂 Inicialização de Dados - Upload de PDFs")
st.write("### Selecione a sala correspondente e faça o upload dos relatórios em PDF.")

# Campo essencial recuperado: Seleção da sala no topo da aplicação
lista_salas_disponiveis = ["Sala 1", "Sala 2", "Sala 3", "Sala 4"]
sala_atual = st.selectbox("Selecione a Sala:", lista_salas_disponiveis)

# Separa apenas os dados que pertencem à sala selecionada no momento
dados_sala_especifica = df_banco_completo[df_banco_completo["Sala"] == sala_atual]

# Estrutura em Abas: Uma para Visualizar Gráficos e outra para gerenciar os PDFs daquela Sala
aba_dashboard, aba_upload = st.tabs(["📊 Visualizar Dashboard", "🔄 Gerenciar PDFs (Upload)"])

# ------------------------------------------------------------------------------
# ABA 1: VISUALIZAÇÃO DO DASHBOARD (Acesso direto para sua amiga)
# ------------------------------------------------------------------------------
with aba_dashboard:
    if not dados_sala_especifica.empty:
        st.success(f"Dados da **{sala_atual}** carregados! Sua amiga pode visualizar esta aba sem fazer novos uploads.")
        
        # Seleção de alunos pertencentes estritamente a esta sala
        alunos_da_sala = dados_sala_especifica["Aluno"].unique()
        aluno_selecionado = st.selectbox("Selecione o Aluno para Análise:", alunos_da_sala, key="filtro_aluno")
        
        dados_aluno = dados_sala_especifica[dados_sala_especifica["Aluno"] == aluno_selecionado]
        matricula_aluno = dados_aluno["Matrícula"].iloc[0]
        
        # Painel de identificação
        c1, c2 = st.columns([1, 3])
        with c1:
            st.metric(label="Matrícula", value=str(matricula_aluno))
        with c2:
            st.subheader(f"Estudante: {aluno_selecionado}")
            
        st.divider()
        
        # Filtro de Matéria e renderização dos gráficos reais
        materias_aluno = dados_aluno["Disciplina"].unique()
        materia_selecionada = st.selectbox("Escolha a Disciplina:", materias_aluno, key="filtro_materia")
        
        dados_materia = dados_aluno[dados_aluno["Disciplina"] == materia_selecionada].iloc[0]
        
        # DataFrame estruturado para as colunas do gráfico do aluno
        df_grafico = pd.DataFrame({
            "Bimestre": ["1º BI", "2º BI", "3º BI", "4º BI"],
            "Nota": [float(dados_materia["N1"]), float(dados_materia["N2"]), float(dados_materia["N3"]), float(dados_materia["N4"])]
        })
        
        col_grafico, col_metricas = st.columns([2, 1])
        with col_grafico:
            st.bar_chart(data=df_grafico, x="Bimestre", y="Nota")
        with col_metricas:
            st.metric(label="Frequência Final", value=f"{dados_materia['Frequência']}%")
            
            # Média parcial real apenas com bimestres avaliados (>0)
            notas_validas = [n for n in [dados_materia["N1"], dados_materia["N2"], dados_materia["N3"], dados_materia["N4"]] if n > 0.0]
            media = sum(notas_validas) / len(notas_validas) if notas_validas else 0.0
            st.metric(label="Média Parcial", value=f"{media:.2f}")
            
    else:
        st.info(f"O banco de dados para a **{sala_atual}** está vazio. Vá até a aba 'Gerenciar PDFs (Upload)' para cadastrar os boletins desta turma.")

# ------------------------------------------------------------------------------
# ABA 2: ÁREA DE UPLOAD E ATUALIZAÇÃO DA SALA SELECIONADA
# ------------------------------------------------------------------------------
with aba_upload:
    st.write(f" Envie os novos arquivos em PDF correspondentes à **{sala_atual}**.")
    
    arquivos_pdf = st.file_uploader(
        "Arraste e solte os PDFs aqui:", 
        type=["pdf"], 
        accept_multiple_files=True,
        key="uploader_arquivos"
    )
    
    if st.button("PROCESSAR E ATUALIZAR DASHBOARD", key="btn_atualizar"):
        if arquivos_pdf:
            with st.spinner("Analisando estrutura do SUAP e salvando na nuvem..."):
                # Extrai novos dados configurando a coluna da sala atual
                df_novos_dados = extrair_dados_suap(arquivos_pdf, sala_atual)
                
                if not df_novos_dados.empty:
                    # Remove os dados antigos daquela sala específica na base completa para evitar duplicidade
                    df_base_limpa = df_banco_completo[df_banco_completo["Sala"] != sala_atual]
                    
                    # Junta os registros das outras salas com os novos dados atualizados desta sala
                    df_consolidado_final = pd.concat([df_base_limpa, df_novos_dados], ignore_index=True)
                    
                    # Atualiza o Google Sheets central na nuvem
                    conn.update(data=df_consolidado_final)
                    st.success(f"Dados da {sala_atual} atualizados com sucesso na nuvem!")
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.error("Nenhum diário válido estruturado foi capturado do PDF.")
        else:
            st.warning("Por favor, anexe arquivos em PDF antes de clicar no botão.")
            
    if st.button(f"🗑️ Apagar apenas os dados da {sala_atual}"):
        df_restante = df_banco_completo[df_banco_completo["Sala"] != sala_atual]
        conn.update(data=df_restante)
        st.cache_data.clear()
        st.rerun()
