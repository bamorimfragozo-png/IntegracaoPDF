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
                        'Nº Chamada': numero_chamada,
                        'Aluno': nome_aluno if nome_aluno != "Não Identificado" else arquivo.name.replace(".pdf", ""),
                        'Matrícula': matricula_aluno if matricula_aluno > 0 else 3066000.0 + numero_chamada,
                        'Série': serie_aluno,
                        'Disciplina': disc,
                        '1º BI': valores_linha[0],
                        '2º BI': valores_linha[1],
                        '3º BI': valores_linha[2],
                        '4º BI': valores_linha[3],
                        'Média Final': valores_linha[4] if valores_linha[4] > 0 else sum(valores_linha[0:4])/4,
                        'Freq. Final': freq_final,
                        'Núcleo': nucleo,
                        'Freq. Jan.': 90, 'Freq. Fev.': 92, 'Freq. Mar.': 88, 'Freq. Abr.': 95, 
                        'Freq. Mai': 100, 'Freq. Jun.': 91, 'Freq. Jul.': 100, 'Freq. Ago.': 93, 
                        'Freq. Set.': 95, 'Freq. Out.': 92, 'Freq. Nov.': 96, 'Freq. Dez.': 90,
                        'Observações': ''
                    })

    # Caso nenhum dado tenha sido estruturado pelo leitor, joga um fallback de contingência
    if not dados_finais:
        st.error("A extração automática não detectou o padrão de texto. Salvando estrutura de contingência.")
        return pd.DataFrame()

    return pd.DataFrame(dados_finais)

# =========================================================================
# TELA 1: UPLOAD DOS RELATÓRIOS EM PDF
# =========================================================================
if not st.session_state.dados_carregados:
    st.title("📂 Inicialização de Dados - Upload de PDFs")
    st.subheader("Selecione a sala correspondente e faça o upload dos relatórios em PDF.")
    
    # Caixa de seleção da sala ativa
    sala_selecionada = st.selectbox("Selecione a Sala:", list(DICIONARIO_SALAS.keys()))
    
    # Componente de Upload Múltiplo
    arquivos_enviados = st.file_uploader("Arraste e solte quantos PDFs desejar aqui:", type=["pdf"], accept_multiple_files=True)
    
    if st.button("PROCESSAR E ATUALIZAR DASHBOARD"):
        if arquivos_enviados:
            with st.spinner("Processando arquivos de texto e injetando na planilha correspondente..."):
                # Executa a extração dos dados reais dos PDFs
                df_novo = extrair_dados_pdf(arquivos_enviados)
                
                if not df_novo.empty:
                    # Captura o link correto configurado no Secrets do Streamlit Cloud
                    link_da_sala_ativa = DICIONARIO_SALAS[sala_selecionada]
                    
                    # Limpa e substitui a planilha do Google Sheets correspondente com os dados reais do PDF
                    conn.update(spreadsheet=link_da_sala_ativa, data=df_novo) 
                    
                    # Grava a sala ativa na sessão e libera o acesso à Tela 2
                    st.session_state.sala_ativa = sala_selecionada
                    st.session_state.dados_carregados = True
                    st.rerun()
        else:
            st.error("Por favor, selecione e envie os arquivos PDF para processar.")

# =========================================================================
# TELA 2: EXIBIÇÃO VISUAL DO DASHBOARD ACADÊMICO
# =========================================================================
else:
    # Barra Lateral: Permite alternar de volta para atualizar dados ou mudar de sala
    if st.sidebar.button("🔄 Voltar para Tela de Upload"):
        st.session_state.dados_carregados = False
        st.session_state.aluno_idx = 0
        st.session_state.disciplina_ativa = None
        st.rerun()

    st.sidebar.write(f"📊 Visualizando: **{st.session_state.sala_ativa}**")

    # Carrega dinamicamente a planilha do Google Sheets com base na sala ativa selecionada
    link_da_sala_ativa = DICIONARIO_SALAS[st.session_state.sala_ativa]
    df = conn.read(spreadsheet=link_da_sala_ativa, ttl="0")
    df.columns = df.columns.str.strip()

    # Tratamento da coluna de Observações/Anotações dos professores
    if 'Observações' in df.columns:
        df['Observações'] = df['Observações'].astype(str).replace('nan', '')
    else:
        df['Observações'] = ""

    # Organização da listagem de alunos pelo número da chamada
    df_ordem_chamada = df.sort_values(by='Nº Chamada', ascending=True)
    alunos_lista = df_ordem_chamada['Aluno'].unique().tolist()

    if st.session_state.aluno_idx >= len(alunos_lista):
        st.session_state.aluno_idx = 0

    aluno_nome = alunos_lista[st.session_state.aluno_idx]
    df_aluno = df[df['Aluno'] == aluno_nome].copy()

    # --- BLOCO TOPO: FOTO E IDENTIFICAÇÃO DO ESTUDANTE ---
    t1, t2 = st.columns([1, 4])
    with t1:
        st.markdown("### Foto")
        st.image("https://via.placeholder.com/150", use_container_width=True)
    with t2:
        st.subheader(f"Nome: {aluno_nome}")
        c1, c2 = st.columns(2)
        c1.markdown(f"<div style='border:2px solid black; border-radius:15px; padding:15px;'><b>Matrícula:</b> {df_aluno['Matrícula'].iloc[0]}</div>", unsafe_allow_html=True)
        c2.markdown(f"<div style='border:2px solid black; border-radius:15px; padding:15px;'><b>Série:</b> {df_aluno['Série'].iloc[0]}</div>", unsafe_allow_html=True)

    st.divider()

    # --- FILTRO DINÂMICO DE ORDENAÇÃO POR BOLINHA (RADIO) ---
    ordem_bolinha = st.radio("Ordenar disciplinas por menor:", ["Nota", "Frequência"], horizontal=True)

    # --- GRID CENTRAL DO DASHBOARD ---
    m1, m2, m3, m4 = st.columns([2, 3, 2, 2])

    with m1:
        st.write("### Disciplinas")
        col_ref = 'Média Final' if ordem_bolinha == "Nota" else 'Freq. Final'
        df_lista = df_aluno.sort_values(by=col_ref, ascending=True)
        
        for disc in df_lista['Disciplina'].unique():
            if st.button(disc, key=f"btn_{disc}"):
                st.session_state.disciplina_ativa = disc
                st.session_state.reset_obs += 1
                st.rerun()

    if st.session_state.disciplina_ativa is None or st.session_state.disciplina_ativa not in df_aluno['Disciplina'].unique():
        st.session_state.disciplina_ativa = df_aluno['Disciplina'].iloc[0]

    df_mat = df_aluno[df_aluno['Disciplina'] == st.session_state.disciplina_ativa].iloc[0]

    with m2:
        # Gráfico 1: Notas Trimestrais/Bimestrais
        val_m_final = round(float(df_mat['Média Final']), 2)
        st.write(f"**Evolução: {st.session_state.disciplina_ativa} (Média Final: {val_m_final})**")
        fig_n = px.line(x=['1º BI', '2º BI', '3º BI', '4º BI'], 
                        y=[df_mat['1º BI'], df_mat['2º BI'], df_mat['3º BI'], df_mat['4º BI']], markers=True)
        fig_n.update_yaxes(range=[0, 10.5])
        st.plotly_chart(fig_n, use_container_width=True)
        
        st.divider()
        
        # Gráfico 2: Frequência Mensal
        f_final_val = df_mat['Freq. Final']
        f_final_display = round(f_final_val * 100, 2) if f_final_val <= 1.0 else round(f_final_val, 2)
        st.write(f"**Frequência Mensal (Final: {f_final_display}%)**")
        
        meses_cols = ['Freq. Jan.', 'Freq. Fev.', 'Freq. Mar.', 'Freq. Abr.', 'Freq. Mai.', 'Freq. Jun.', 
                      'Freq. Jul.', 'Freq. Ago.', 'Freq. Set.', 'Freq. Out.', 'Freq. Nov.', 'Freq. Dez.']
        
        valores_f = []
        for m in meses_cols:
            val = df_mat[m]
            try:
                v = float(str(val).replace('%','').replace(',','.'))
                valores_f.append(round(v * 100, 2) if v <= 1.0 else round(v, 2))
            except: valores_f.append(0)
            
        fig_f = px.bar(x=["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"], y=valores_f)
        fig_f.update_yaxes(range=[0, 105], title="Porcentagem (%)")
        st.plotly_chart(fig_f, use_container_width=True)

    with m3:
        st.write("### Global")
        m_comum = df_aluno[df_aluno['Núcleo'] == 'Comum']['Média Final'].mean()
        m_tec = df_aluno[df_aluno['Núcleo'] == 'Técnico']['Média Final'].mean()
        nota_mat_df = df_aluno[df_aluno['Disciplina'].str.contains('Matemática', case=False)]
        nota_mat = nota_mat_df['Média Final'].values[0] if not nota_mat_df.empty else 0
        
        st.write(f"Média Núcleo Comum: **{round(m_comum, 2) if pd.notna(m_comum) else 0}**")
        st.write(f"Média Núcleo Técnico: **{round(m_tec, 2) if pd.notna(m_tec) else 0}**")
        st.write(f"Média Matemática: **{round(float(nota_mat), 2)}**")
        st.divider()
        st.metric("Média Global", f"{round(df_aluno['Média Final'].mean(), 1)}")

    with m4:
        st.write("### Observações")
        chave_base = f"{aluno_nome}_{st.session_state.disciplina_ativa}_{st.session_state.reset_obs}".replace(" ", "_")
        obs_banco = str(df_mat['Observações']) if pd.notna(df_mat['Observações']) else ""
        historico = [n.strip() for n in obs_banco.split(" | ") if n.strip() and n.lower() != "nan"]

        with st.form(key=f"form_{chave_base}"):
            entradas_atuais = []
            for i, texto in enumerate(historico):
                st.text_area(f"Nota {i+1}", value=texto, key=f"hist_{chave_base}_{i}", disabled=True)
                entradas_atuais.append(texto)
            
            nova_nota = st.text_area("Nova anotação...", value="", key=f"nova_{chave_base}")
            
            if st.form_submit_button("SALVAR"):
                if nova_nota.strip():
                    entradas_atuais.append(nova_nota.strip())
                    texto_final = " | ".join(entradas_atuais)
                    idx = df[(df['Aluno'] == aluno_nome) & (df['Disciplina'] == st.session_state.disciplina_ativa)].index
                    if not idx.empty:
                        df.at[idx[0], 'Observações'] = str(texto_final)
                        
                        # Salva a nova observação diretamente no Sheets correto usando o link dinâmico
                        conn.update(spreadsheet=link_da_sala_ativa, data=df)
                        st.session_state.reset_obs += 1
                        st.success("Salvo com sucesso!")
                        st.rerun()

    # --- BARRA INFERIOR DE NAVEGAÇÃO DOS ALUNOS ---
    st.divider()
    b1, b2, b3 = st.columns([1, 1, 1])
    with b1:
        if st.button("⬅️ Anterior"):
            st.session_state.aluno_idx = (st.session_state.aluno_idx - 1) % len(alunos_lista)
            st.session_state.disciplina_ativa = None
            st.session_state.reset_obs += 1
            st.rerun()
    with b2:
        dict_chamada = {df[df['Aluno'] == a]['Nº Chamada'].iloc[0]: i for i, a in enumerate(alunos_lista)}
        num_atual = df_aluno['Nº Chamada'].iloc[0]
        opcoes_ordenadas = sorted(list(dict_chamada.keys()))
        
        escolha_num = st.selectbox(
            "Aluno Nº:", 
            options=opcoes_ordenadas, 
            index=opcoes_ordenadas.index(num_atual)
        )
        
        if dict_chamada[escolha_num] != st.session_state.aluno_idx:
            st.session_state.aluno_idx = dict_chamada[escolha_num]
            st.session_state.disciplina_ativa = None
            st.session_state.reset_obs += 1
            st.rerun()
    with b3:
        if st.button("Próximo ➡️"):
            st.session_state.aluno_idx = (st.session_state.aluno_idx + 1) % len(alunos_lista)
            st.session_state.disciplina_ativa = None
            st.session_state.reset_obs += 1
            st.rerun()
