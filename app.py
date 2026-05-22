import streamlit as st
import pandas as pd
import plotly.express as px
from streamlit_gsheets import GSheetsConnection
from pypdf import PdfReader
import io

# 1. Configuração da Página e Estilo
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

# 2. Inicialização dos Estados de Sessão
if 'dados_carregados' not in st.session_state:
    st.session_state.dados_carregados = False
if 'aluno_idx' not in st.session_state: 
    st.session_state.aluno_idx = 0
if 'disciplina_ativa' not in st.session_state: 
    st.session_state.disciplina_ativa = None
if 'reset_obs' not in st.session_state: 
    st.session_state.reset_obs = 0

# Conexão com o Google Sheets
conn = st.connection("gsheets", type=GSheetsConnection)

# --- FUNÇÃO DE LEITURA DO PDF E PARSER (EXEMPLO GENÉRICO) ---
def extrair_dados_pdf(arquivos_pdf):
    """
    Lê os PDFs carregados e transforma em um DataFrame do Pandas.
    Ajuste a lógica interna com base no layout de texto do seu PDF específico.
    """
    dados_finais = []
    
    for arquivo in arquivos_pdf:
        pdf_reader = PdfReader(io.BytesIO(arquivo.read()))
        texto_completo = ""
        for pagina in pdf_reader.pages:
            texto_completo += pagina.extract_text() + "\n"
        
        # --- LÓGICA DE EXEMPLO PARA SIMULAR A EXTRAÇÃO DE LINHAS ---
        # Substitua esta lógica simulada pelas regras reais de extração das colunas do seu PDF
        linhas = texto_completo.split('\n')
        for linha in lines:
            if "Matrícula" in linha or "Aluno" in linha or csv_condicao: 
                # Parsear dados aqui e dar append em dados_finais
                pass
                
    # Criando o DataFrame baseado na estrutura real das suas imagens
    # Exemplo simulado com a estrutura que o seu dashboard atual consome:
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

# ==========================================
# TELA 1: UPLOAD DOS ARQUIVOS (PÁGINA EM BRANCO)
# ==========================================
if not st.session_state.dados_carregados:
    st.title("📂 Inicialização de Dados - Upload de PDFs")
    st.subheader("Selecione a sala correspondente e faça o upload dos relatórios em PDF.")
    
    # Seleção de qual das 6 salas/planilhas será atualizada
    sala_selecionada = st.selectbox("Selecione a Sala:", [f"Sala {i}" for i in range(1, 7)])
    
    arquivos_enviados = st.file_uploader("Arraste e solte quantos PDFs desejar aqui:", type=["pdf"], accept_multiple_files=True)
    
    if st.button("PROCESSAR E ATUALIZAR DASHBOARD"):
        if arquivos_enviados:
            with st.spinner("Processando PDFs e limpando/atualizando o Google Sheets..."):
                # 1. Transforma o PDF em DataFrame (Dados e Colunas criados dinamicamente)
                df_novo = extrair_dados_pdf(arquivos_enviados)
                
                # 2. Atualiza a planilha no Google Sheets (Sobrescreve tudo na planilha)
                # NOTA: Para gerenciar 6 salas, você pode configurar worksheets diferentes: worksheet=sala_selecionada
                conn.update(data=df_novo) 
                
                st.session_state.dados_carregados = True
                st.success("Planilha atualizada com sucesso!")
                st.rerun()
        else:
            st.error("Por favor, envie pelo menos um arquivo PDF.")

# ==========================================
# TELA 2: EXIBIÇÃO DO DASHBOARD (APÓS UPLOAD)
# ==========================================
else:
    # Botão para resetar e voltar para a tela de upload se necessário
    if st.sidebar.button("🔄 Fazer Novo Upload / Limpar"):
        st.session_state.dados_carregados = False
        st.session_state.aluno_idx = 0
        st.session_state.disciplina_ativa = None
        st.rerun()

    # Leitura dos dados atualizados diretamente da Planilha Google
    df = conn.read(ttl="0")
    df.columns = df.columns.str.strip()

    if 'Observações' in df.columns:
        df['Observações'] = df['Observações'].astype(str).replace('nan', '')
    else:
        df['Observações'] = ""

    # Ordenação da lista de alunos pelo número da chamada
    df_ordem_chamada = df.sort_values(by='Nº Chamada', ascending=True)
    alunos_lista = df_ordem_chamada['Aluno'].unique().tolist()

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

    # --- MIOLO ---
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
        # Gráfico de Notas
        val_m_final = round(float(df_mat['Média Final']), 2)
        st.write(f"**Evolução: {st.session_state.disciplina_ativa} (Média Final: {val_m_final})**")
        fig_n = px.line(x=['1º BI', '2º BI', '3º BI', '4º BI'], 
                        y=[df_mat['1º BI'], df_mat['2º BI'], df_mat['3º BI'], df_mat['4º BI']], markers=True)
        fig_n.update_yaxes(range=[0, 10.5])
        st.plotly_chart(fig_n, use_container_width=True)
        
        st.divider()
        
        # Gráfico de Frequência
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
                        conn.update(data=df)
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
