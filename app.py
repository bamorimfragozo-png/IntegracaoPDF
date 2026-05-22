import streamlit as st
import pandas as pd
import plotly.express as px
from streamlit_gsheets import GSheetsConnection
from pypdf import PdfReader
import io

# =========================================================================
# 1. CONFIGURAÇÃO DA PÁGINA E ESTILO (IDÊNTICO AO SEU)
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
    .stButton>button { width: 100%; border: 1px solid #ddd; border-radius: 8px; text-align: left; }
    .stRadio > div { flex-direction: row; gap: 20px; }
    </style>
    """, unsafe_allow_html=True)

# =========================================================================
# 2. CONEXÃO GENÉRICA E DICIONÁRIO DE LINKS (SUBSTITUA PELOS SEUS LINKS REAIS)
# =========================================================================
conn = st.connection("gsheets", type=GSheetsConnection)

# COLOQUE AQUI OS LINKS REAIS DAS SUAS 6 PLANILHAS DO GOOGLE DRIVE
DICIONARIO_SALAS = {
    "Sala 1": "https://docs.google.com/spreadsheets/d/LINK_DA_SALA_1/edit#gid=0",
    "Sala 2": "https://docs.google.com/spreadsheets/d/LINK_DA_SALA_2/edit#gid=0",
    "Sala 3": "https://docs.google.com/spreadsheets/d/LINK_DA_SALA_3/edit#gid=0",
    "Sala 4": "https://docs.google.com/spreadsheets/d/LINK_DA_SALA_4/edit#gid=0",
    "Sala 5": "https://docs.google.com/spreadsheets/d/LINK_DA_SALA_5/edit#gid=0",
    "Sala 6": "https://docs.google.com/spreadsheets/d/LINK_DA_SALA_6/edit#gid=0"
}

# =========================================================================
# 3. ESTADOS DE SESSÃO E FUNÇÃO EXTRAÇÃO DO PDF
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

def extrair_dados_pdf(arquivos_pdf):
    """
    Função para ler os PDFs da memória usando o módulo 'io'.
    Ajuste as regras de extração abaixo de acordo com a estrutura do seu PDF.
    """
    dados_finais = []
    
    for arquivo in arquivos_pdf:
        # Usa o io.BytesIO para ler o arquivo diretamente da memória RAM
        pdf_reader = PdfReader(io.BytesIO(arquivo.read()))
        texto_completo = ""
        for pagina in pdf_reader.pages:
            texto_completo += pagina.extract_text() + "\n"
        
        # [AQUI VAI A SUA LÓGICA DE TRATAMENTO DE TEXTO DO SEU PDF]
        # Exemplo: quebrar por linhas, procurar padrões, etc.
        
    # --- ESTRUTURA DE EXEMPLO (Simulando os dados que alimentam suas imagens) ---
    exemplo_df = pd.DataFrame({
        'Nº Chamada': [1, 1, 2, 2],
        'Aluno': ['Bruno', 'Bruno', 'Beatriz', 'Beatriz'],
        'Matrícula': [3066002.0, 3066002.0, 3066005.0, 3066005.0],
        'Série': ['1º Ano', '1º Ano', '1º Ano', '1º Ano'],
        'Disciplina': ['Matemática', 'Português', 'Matemática', 'Português'],
        '1º BI': [7.5, 8.0, 9.0, 7.0],
        '2º BI': [8.0, 7.5, 8.5, 9.0],
        '3º BI': [6.8, 8.5, 9.2, 8.0],
        '4º BI': [8.5, 9.0, 8.8, 8.5],
        'Média Final': [7.75, 8.25, 8.87, 8.12],
        'Freq. Final': [0.935, 0.95, 0.92, 0.98],
        'Núcleo': ['Comum', 'Comum', 'Comum', 'Comum'],
        'Freq. Jan.': [90, 95, 92, 100], 'Freq. Fev.': [92, 90, 94, 96], 'Freq. Mar.': [88, 92, 90, 94],
        'Freq. Abr.': [95, 96, 91, 92], 'Freq. Mai.': [100, 98, 97, 99], 'Freq. Jun.': [91, 92, 93, 94],
        'Freq. Jul.': [100, 100, 100, 100], 'Freq. Ago.': [93, 94, 95, 96], 'Freq. Set.': [95, 91, 92, 93],
        'Freq. Out.': [92, 93, 94, 95], 'Freq. Nov.': [96, 97, 98, 99], 'Freq. Dez.': [90, 91, 92, 93],
        'Observações': ['', '', '', '']
    })
    return exemplo_df

# =========================================================================
# TELA 1: PÁGINA EM BRANCO PARA UPLOAD (Se os dados não estiverem carregados)
# =========================================================================
if not st.session_state.dados_carregados:
    st.title("📂 Upload de Relatórios (PDF)")
    st.subheader("Escolha a sala desejada e envie os arquivos para atualizar o banco de dados.")
    
    # Usuário seleciona qual das salas quer gerenciar
    sala_selecionada = st.selectbox("Selecione a Sala para atualizar:", list(DICIONARIO_SALAS.keys()))
    
    # Campo para múltiplos uploads
    arquivos_enviados = st.file_uploader("Arraste e solte seus PDFs aqui:", type=["pdf"], accept_multiple_files=True)
    
    if st.button("PROCESSAR E ATUALIZAR DASHBOARD"):
        if arquivos_enviados:
            with st.spinner("Processando PDFs e limpando/sobrescrevendo o Google Sheets..."):
                # 1. Transforma o PDF em DataFrame estruturado
                df_novo = extrair_dados_pdf(arquivos_enviados)
                
                # 2. Captura o link correto baseado na escolha do Selectbox
                link_da_sala_ativa = DICIONARIO_SALAS[sala_selecionada]
                
                # 3. Limpa a planilha antiga e injeta os novos dados passando o link direto
                conn.update(spreadsheet=link_da_sala_ativa, data=df_novo) 
                
                # Guarda na sessão qual sala deve ser exibida no dashboard
                st.session_state.sala_ativa = sala_selecionada
                st.session_state.dados_carregados = True
                
                st.success(f"Planilha da {sala_selecionada} atualizada com sucesso!")
                st.rerun()
        else:
            st.error("Por favor, envie ao menos um arquivo PDF para continuar.")

# =========================================================================
# TELA 2: EXIBIÇÃO DO DASHBOARD COM GRÁFICOS (Após o upload de sucesso)
# =========================================================================
else:
    # Botão lateral na barra para poder voltar e carregar novos dados/outra sala
    if st.sidebar.button("🔄 Voltar para Tela de Upload"):
        st.session_state.dados_carregados = False
        st.session_state.aluno_idx = 0
        st.session_state.disciplina_ativa = None
        st.rerun()

    st.sidebar.write(f"📊 Visualizando: **{st.session_state.sala_ativa}**")

    # 1. Captura o link da sala ativa que guardamos no upload
    link_da_sala_ativa = DICIONARIO_SALAS[st.session_state.sala_ativa]

    # 2. Faz a leitura injetando o link direto
    df = conn.read(spreadsheet=link_da_sala_ativa, ttl="0")
    df.columns = df.columns.str.strip()

    if 'Observações' in df.columns:
        df['Observações'] = df['Observações'].astype(str).replace('nan', '')
    else:
        df['Observações'] = ""

    # Ordenação dos alunos pelo número da chamada
    df_ordem_chamada = df.sort_values(by='Nº Chamada', ascending=True)
    alunos_lista = df_ordem_chamada['Aluno'].unique().tolist()

    # Proteção caso o índice da chamada dê algum erro ao mudar de sala
    if st.session_state.aluno_idx >= len(alunos_lista):
        st.session_state.aluno_idx = 0

    aluno_nome = alunos_lista[st.session_state.aluno_idx]
    df_aluno = df[df['Aluno'] == aluno_nome].copy()

    # --- TOPO: IDENTIFICAÇÃO ---
    t1, t2 = st.columns([1, 4])
    with t1:
        st.markdown("### Foto")
        st.image("https://via.placeholder.com/150", use_container_width=True)
    with t2:
        st.subheader(f"Nome: {aluno_nome}")
        c1, c2 = st.columns(2)
        c1.write(f"**Matrícula:** {df_aluno['Matrícula'].iloc[0]}")
        c2.write(f"**Série:** {df_aluno['Série'].iloc[0]}")

    st.divider()

    # --- OPÇÕES DE ORDENAÇÃO ---
    ordem_bolinha = st.radio("Ordenar disciplinas por menor:", ["Nota", "Frequência"], horizontal=True)

    # --- MIOLO: DISCIPLINAS | GRÁFICOS | GLOBAL | OBSERVAÇÕES ---
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

    if st.session_state.disciplina_ativa is None:
        st.session_state.disciplina_ativa = df_aluno['Disciplina'].iloc[0]

    df_mat = df_aluno[df_aluno['Disciplina'] == st.session_state.disciplina_ativa].iloc[0]

    with m2:
        # Notas
        val_m_final = round(float(df_mat['Média Final']), 2)
        st.write(f"**Evolução: {st.session_state.disciplina_ativa} (Média Final: {val_m_final})**")
        fig_n = px.line(x=['1º BI', '2º BI', '3º BI', '4º BI'], 
                        y=[df_mat['1º BI'], df_mat['2º BI'], df_mat['3º BI'], df_mat['4º BI']], markers=True)
        fig_n.update_yaxes(range=[0, 10.5])
        st.plotly_chart(fig_n, use_container_width=True)
        
        st.divider()
        
        # Frequência
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
            
        fig_f = px.bar(x=[mes.split('.')[1].strip() for mes in meses_cols], y=valores_f)
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
                        
                        # SALVA UTILIZANDO O LINK DIRETO CORRETO DA SALA ATIVA
                        conn.update(spreadsheet=link_da_sala_ativa, data=df)
                        
                        st.session_state.reset_obs += 1
                        st.success("Salvo!")
                        st.rerun()

    # --- RODAPÉ: NAVEGAÇÃO ---
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
