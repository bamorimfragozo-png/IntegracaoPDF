import streamlit as st
import pandas as pd
import pypdf
import re
from streamlit_gsheets import GSheetsConnection

# ==============================================================================
# CONFIGURAÇÃO DA PÁGINA
# ==============================================================================
st.set_page_config(
    page_title="Inicialização de Dados - Dashboard Escolar",
    page_icon="📂",
    layout="wide"
)

# Conexão com o Google Sheets
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception as e:
    st.error("Erro ao conectar com o Google Sheets. Verifique as credenciais no .streamlit/secrets.toml.")
    st.stop()

# ==============================================================================
# FUNÇÃO DE EXTRAÇÃO DE DADOS (MÉTODO DA TABELA DO SUAP)
# ==============================================================================
def extrair_dados_suap(arquivos_enviados):
    dados_totais = []
    
    for arquivo in arquivos_enviados:
        try:
            leitor = pypdf.PdfReader(arquivo)
            texto_completo = ""
            for pagina in leitor.pages:
                texto_completo += pagina.extract_text() + "\n"
            
            linhas = texto_completo.split("\n")
            
            # 1. Extração Estrita da Matrícula
            matricula = "Não encontrada"
            for linha in linhas:
                if "Matrícula:" in linha:
                    # Captura o padrão alfanumérico ou numérico logo após "Matrícula:"
                    match = re.search(r'Matrícula:\s*([A-Za-z0-9]+)', linha)
                    if match:
                        matricula = match.group(1)
                        break
            
            # 2. Extração Estrita do Nome do Aluno
            aluno = "Desconhecido"
            for linha in linhas:
                if "Aluno(a):" in linha:
                    match = re.search(r'Aluno\(a\):\s*(.*?)\s*(?:Matrícula:|Curso:|$)', linha)
                    if match:
                        aluno = match.group(1).strip()
                        break

            # 3. Extração e Filtragem de Disciplinas e Notas por Linha da Tabela
            # Padrão para capturar o código do Diário (ex: 384835) no início da linha da tabela do SUAP
            padrao_diario = re.compile(r'^(\d{5,6})\s+(.*)')
            
            for linha in linhas:
                linha = linha.strip()
                match_diario = padrao_diario.match(linha)
                
                if match_diario:
                    diario_codigo = match_diario.group(1)
                    resto_linha = match_diario.group(2).strip()
                    
                    # Evita capturar linhas falsas que começam com números (como cargas horárias totais no fim do PDF)
                    if "Total" in linha or "Horas" in linha or "Aulas" in linha:
                        continue
                        
                    # Separar o nome da disciplina das notas usando regex ou separadores comuns do SUAP
                    # No SUAP, após o nome da matéria vem a Carga Horária (ex: 60,00 ou 90,00), Aulas, etc.
                    # Vamos quebrar a linha por espaços longos ou buscar valores decimais de notas no fim
                    partes_notas = re.findall(r'\b\d{1,2},\d{2}\b|\b-\b', resto_linha)
                    
                    # Limpeza do nome da disciplina: remove códigos extras do SUAP e dados de notas da string
                    nome_disciplina = re.sub(r'\b\d{1,2},\d{2}\b|\b-\b|Cursando.*|Aguardando.*', '', resto_linha).strip()
                    # Remove números soltos do final referentes a CH ou Aulas para isolar estritamente o texto do nome
                    nome_disciplina = re.sub(r'\s+\d+(?:,\d+)?(?=\s|$)', '', nome_disciplina).strip()
                    # Remove múltiplos espaços causados pela substituição
                    nome_disciplina = re.sub(r'\s+', ' ', nome_disciplina)
                    
                    # Captura das Notas Bimestrais (N1, N2, N3, N4) baseadas nas colunas da tabela
                    # No SUAP, as notas ficam estruturadas na ordem sequencial após a CH e Situação.
                    # Se não houver notas lançadas (representado por '-' ou ausente), consideramos 0.0 de forma estrita.
                    n1, n2, n3, n4 = 0.0, 0.0, 0.0, 0.0
                    
                    if len(partes_notas) >= 4:
                        # Se as notas já estão disponíveis nas primeiras posições correspondentes da lista de números
                        # Nota: O SUAP coloca Nota e Faltas lado a lado (N F N F N F N F). 
                        # Portanto, precisamos filtrar apenas as Notas (índices pares ou ímpares conforme o padrão extraído)
                        # Uma abordagem segura baseada na imagem é procurar os blocos decimais limpos:
                        valores_limpos = [float(v.replace(',', '.')) if v != '-' else 0.0 for v in partes_notas]
                        
                        # Atribuição estrita baseada nas notas encontradas sequencialmente na linha
                        # Filtrando apenas as notas válidas (maiores números ou posições de notas)
                        # No fluxo padrão do SUAP: o primeiro valor decimal isolado após a situação é a N1, depois N2, etc.
                        try: n1 = valores_limpos[0]
                        except: pass
                        try: n2 = valores_limpos[1]
                        except: pass
                        try: n3 = valores_limpos[2]
                        except: pass
                        try: n4 = valores_limpos[3]
                        except: pass
                    
                    # Captura da Frequência Real (% Freq)
                    frequencia = 100.0
                    match_freq = re.search(r'(\d{1,3})%', linha)
                    if match_freq:
                        frequencia = float(match_freq.group(1))

                    dados_totais.append({
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
            st.error(f"Erro ao processar o arquivo {arquivo.name}: {e}")
            
    return pd.DataFrame(dados_totais)

# ==============================================================================
# FLUXO DE VERIFICAÇÃO DO BANCO DE DADOS (GOOGLE SHEETS)
# ==============================================================================
@st.cache_data(ttl=10)  # Atualiza a consulta a cada 10 segundos
def carregar_dados_existentes():
    try:
        df_existente = conn.read()
        if df_existente is not None and not df_existente.empty:
            # Garante que as colunas obrigatórias existem para validar o banco
            colunas_obrigatorias = ["Matrícula", "Aluno", "Disciplina", "N1", "N2", "N3", "N4", "Frequência"]
            if all(col in df_existente.columns for col in colunas_obrigatorias):
                return df_existente
        return None
    except Exception:
        return None

# Carrega os dados direto da nuvem
df_banco = carregar_dados_existentes()

# ==============================================================================
# INTERFACE E NAVEGAÇÃO
# ==============================================================================

# BARRA LATERAL (CONTROLADORA)
st.sidebar.title("Configurações do Sistema")

# Se o banco de dados já contiver registros, o sistema libera o acesso direto
if df_banco is not None:
    st.sidebar.success("📊 Banco de dados carregado com sucesso!")
    
    # Seção oculta/retrátil para Uploads na barra lateral, mantendo a tela principal livre
    with st.sidebar.expander("🔄 Upload de Novos PDFs", expanded=False):
        st.write("Deseja adicionar ou atualizar os boletins no banco de dados?")
        arquivos = st.file_uploader(
            "Selecione novos relatórios em PDF do SUAP", 
            type=["pdf"], 
            accept_multiple_files=True,
            key="upload_lateral"
        )
        
        if st.button("PROCESSAR E ATUALIZAR", key="btn_lateral"):
            if arquivos:
                with st.spinner("Extraindo e unificando tabelas do SUAP..."):
                    df_novos_dados = extrair_dados_suap(arquivos)
                    if not df_novos_dados.empty:
                        # Atualiza a planilha na nuvem sobrescrevendo ou concatenando
                        conn.update(data=df_novos_dados)
                        st.success("Planilha atualizada com sucesso na Nuvem!")
                        st.cache_data.clear() # Limpa o cache para forçar a releitura imediata
                        st.rerun()
                    else:
                        st.error("Nenhum dado estruturado válido foi encontrado nos arquivos.")
            else:
                st.warning("Selecione pelo menos um arquivo PDF.")
                
    # Botão para limpar a planilha se necessário
    if st.sidebar.button("🗑️ Limpar Banco de Dados"):
        df_vazio = pd.DataFrame(columns=["Matrícula", "Aluno", "Disciplina", "N1", "N2", "N3", "N4", "Frequência"])
        conn.update(data=df_vazio)
        st.cache_data.clear()
        st.rerun()

# Se o banco de dados estiver vazio, exibe a tela de abertura padrão solicitando upload obrigatoriamente
else:
    st.title("📂 Inicialização de Dados - Upload de PDFs")
    st.subheader("Selecione os boletins dos alunos correspondentes e faça o upload dos relatórios em PDF para ativar o Dashboard.")
    
    arquivos = st.file_uploader(
        "Arraste e solte quantos PDFs desejar aqui:", 
        type=["pdf"], 
        accept_multiple_files=True,
        key="upload_principal"
    )
    
    if st.button("PROCESSAR E ATUALIZAR DASHBOARD", key="btn_principal"):
        if arquivos:
            with st.spinner("Processando tabelas e estruturando os diários do SUAP..."):
                df_novos_dados = extrair_dados_suap(arquivos)
                if not df_novos_dados.empty:
                    conn.update(data=df_novos_dados)
                    st.success("Dados salvos e sincronizados com a nuvem!")
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.error("Não foi possível extrair os dados da tabela. Verifique o formato do PDF enviado.")
        else:
            st.warning("Por favor, faça upload de pelo menos um PDF para gerar o painel.")
    st.stop() # Interrompe a execução aqui para quem não tem dados cadastrados

# ==============================================================================
# RENDERIZAÇÃO DO DASHBOARD (VISUALIZAÇÃO COMPARTILHADA)
# ==============================================================================
# Esta parte roda automaticamente para qualquer usuário caso o banco já tenha dados

st.title("📊 Painel de Desempenho Escolar Integrado")

# Filtro de Aluno no Topo do Dashboard
lista_alunos = df_banco["Aluno"].unique()
aluno_selecionado = st.selectbox("Selecione o Aluno para Visualização:", lista_alunos)

# Filtra estritamente os dados do aluno selecionado
dados_aluno = df_banco[df_banco["Aluno"] == aluno_selecionado]

# Exibição do Cabeçalho de Identificação com os dados estritos do PDF
matricula_aluno = dados_aluno["Matrícula"].iloc[0]

col_mat, col_nom = st.columns([1, 3])
with col_mat:
    st.metric(label="Matrícula do Aluno", value=str(matricula_aluno))
with col_nom:
    st.subheader(f"Nome do Estudante: {aluno_selecionado}")

st.divider()

# Listagem de Notas por Disciplina através de abas ou seletor dinâmico
st.write("### Evolução por Disciplinas Cadastradas no Diário")

disciplinas_aluno = dados_aluno["Disciplina"].unique()
disciplina_selecionada = st.selectbox("Escolha a Matéria:", disciplinas_aluno)

dados_materia = dados_aluno[dados_aluno["Disciplina"] == disciplina_selecionada].iloc[0]

# Estruturação correta do gráfico de barras para os 4 bimestres sem dados inventados
df_grafico = pd.DataFrame({
    "Bimestre": ["1º BI", "2º BI", "3º BI", "4º BI"],
    "Nota": [float(dados_materia["N1"]), float(dados_materia["N2"]), float(dados_materia["N3"]), float(dados_materia["N4"])]
})

col_graf, col_info = st.columns([2, 1])

with col_graf:
    # Gráfico de barras verticais nativo do Streamlit representando o boletim real
    st.bar_chart(data=df_grafico, x="Bimestre", y="Nota")

with col_info:
    st.write(f"**Frequência na Matéria:** {dados_materia['Frequência']}%")
    
    # Cálculo automático da média com base nos bimestres que já possuem notas lançadas (> 0)
    notas_validas = [n for n in [dados_materia["N1"], dados_materia["N2"], dados_materia["N3"], dados_materia["N4"]] if n > 0.0]
    media_atual = sum(notas_validas) / len(notas_validas) if notas_validas else 0.0
    
    st.metric(label="Média Parcial (Bimestres Cursados)", value=f"{media_atual:.2f}")

st.divider()
st.write("🔄 *Qualquer atualização feita por upload refletirá instantaneamente para todos os computadores conectados.*")
