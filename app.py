import streamlit as st
import pandas as pd
import plotly.express as px
from streamlit_gsheets import GSheetsConnection
from pypdf import PdfReader
import io
import re

# =========================================================================
# 1. CONFIGURAÇÃO DA PÁGINA E ESTILO CSS CORRIGIDO (SEM BORDAS DUPLICADAS)
# =========================================================================
st.set_page_config(page_title="Dashboard Acadêmico Integrado", layout="wide")

st.markdown("""
<style>
/* Apenas as colunas principais do grid recebem a borda arredondada */
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
# 4. FUNÇÃO DE EXTRAÇÃO REFEITA (DADOS REAIS DO PDF)
# =========================================================================
def extrair_dados_pdf(arquivos_pdf):
    dados_finais = []
    
    for numero_chamada, arquivo in enumerate(arquivos_pdf, start=1):
        pdf_reader = PdfReader(io.BytesIO(arquivo.read()))
        texto_completo = ""
        for pagina in pdf_reader.pages:
            texto_completo += pagina.extract_text() + "\n"
        
        linhas = [linha.strip() for linha in texto_completo.split('\n') if linha.strip()]
        
        nome_aluno = "Não Identificado"
        matricula_aluno = "Não Identificada"
        serie_aluno = "Não Identificada"
        
        # 1. Captura Limpa de Metadados (Nome, Matrícula BT, Série)
        for linha in linhas:
            if "Aluno" in linha or "Nome" in linha:
                partes = linha.split(":")
                val_nome = partes[1].strip() if len(partes) > 1 else linha.replace("Aluno", "").replace("Nome", "").strip()
                nome_aluno = re.sub(r'\bMatrícula\b.*', '', val_nome, flags=re.IGNORECASE).strip()
                
            # Busca o padrão de prontuário/matrícula do IFSP (ex: BT301234-5 ou BT301234)
            match_bt = re.search(r'\bBT\d+[-\d\w]*\b', linha, re.IGNORECASE)
            if match_bt:
                matricula_aluno = match_bt.group(0).upper()

            if "Série" in linha or "Serie" in linha or "Ano" in linha or "Turma" in linha:
                partes = linha.split(":")
                serie_aluno = partes[1].strip() if len(partes) > 1 else linha.replace("Série", "").replace("Serie", "").strip()

        if nome_aluno == "Não Identificado" or not nome_aluno.strip():
            nome_aluno = arquivo.name.replace(".pdf", "").replace("Boletim", "").replace("_", " ").strip()

        # 2. Processamento das Disciplinas e Notas/Faltas Reais
        mapeamento_disciplinas = {}
        
        for i, linha in enumerate(linhas):
            # Filtro Estrito: ignora linhas de cabeçalho, rodapé ou metadados de etapas (N1, F1...)
            if any(termo in linha for termo in ["Notas das etapas", "Faltas nas etapas", "Aluno", "Matrícula", "Série", "Boletim", "Componente Curricular"]):
                continue
            
            # Uma linha de disciplina válida costuma começar com letras (o nome dela ou o código)
            # Vamos pegar o nome exato até encontrar os números de notas/faltas
            partes_palavras = linha.split()
            if not partes_palavras:
                continue
                
            partes_texto = []
            for palavra in partes_palavras:
                # Se a palavra for puramente numérica ou contiver padrões de notas, paramos de ler o nome
                if palavra.replace(',', '.').replace('.', '', 1).isdigit() or any(x in palavra for x in ["N1", "F1", "N2", "F2"]):
                    break
                partes_texto.append(palavra)
                
            nome_disciplina = " ".join(partes_texto).strip()
            
            # Validação para evitar lixo ou falsas disciplinas registradas
            if len(nome_disciplina) < 4 or any(p in nome_disciplina.upper() for p in ["NOTA", "FALTA", "ETAPA", "TOTAL", "RESULTADO", "N1", "F1"]):
                continue
                
            if nome_disciplina not in mapeamento_disciplinas:
                mapeamento_disciplinas[nome_disciplina] = {
                    'notas': [0.0, 0.0, 0.0, 0.0],
                    'faltas': [0.0, 0.0, 0.0, 0.0],
                    'media_final': 0.0
                }
                
            # Extrai os números da linha atual e das próximas para achar notas (N1-N4) e faltas (F1-F4)
            numeros_contexto = []
            for offset in [0, 1, 2]:
                if i + offset < len(linhas):
                    linha_analise = linhas[i + offset].replace(',', '.')
                    # Extrai floats válidos da linha
                    valores = [float(s) for s in linha_analise.split() if s.replace('.', '', 1).isdigit()]
                    if valores:
                        numeros_contexto.append(valores)
            
            # Atribui os dados reais encontrados nas sublinhas
            if len(numeros_contexto) >= 1:
                # Primeira sequência de números encontrada geralmente são as Notas (N1, N2, N3, N4, Média)
                lista_notas = numeros_contexto[0]
                for idx in range(4):
                    if idx < len(lista_notas):
                        mapeamento_disciplinas[nome_disciplina]['notas'][idx] = lista_notas[idx]
                if len(lista_notas) >= 5:
                    mapeamento_disciplinas[nome_disciplina]['media_final'] = lista_notas[4]
                else:
                    mapeamento_disciplinas[nome_disciplina]['media_final'] = sum(mapeamento_disciplinas[nome_disciplina]['notas'])/4
                    
            if len(numeros_contexto) >= 2:
                # Segunda sequência de números encontrada geralmente são as Faltas (F1, F2, F3, F4)
                lista_faltas = numeros_contexto[1]
                for idx in range(4):
                    if idx < len(lista_faltas):
                        mapeamento_disciplinas[nome_disciplina]['faltas'][idx] = lista_faltas[idx]

        # 3. Construção do dicionário final para salvar na planilha
        for nome_disp, blocos in mapeamento_disciplinas.items():
            tecnicas_keywords = ["ILPR", "ININ", "SISTEMAS", "DESENVOLVIMENTO", "BANCO", "LOGICA", "PROGRAMAÇÃO", "TECNICO", "TÉCNICO", "REDES", "INFRAESTRUTURA"]
            is_tecnico = any(kw in nome_disp.upper() for kw in tecnicas_keywords)
            nucleo = "Técnico" if is_tecnico else "Comum"
            
            total_faltas = sum(blocos['faltas'])
            freq_final_calc = max(0.0, (100.0 - total_faltas) / 100.0)

            dados_finais.append({
                'Nº Chamada': numero_chamada,
                'Aluno': nome_aluno,
                'Matrícula': matricula_aluno,
                'Série': serie_aluno,
                'Disciplina': nome_disp,
                '1º BI': blocos['notas'][0],
                '2º BI': blocos['notas'][1],
                '3º BI': blocos['notas'][2],
                '4º BI': blocos['notas'][3],
                'Média Final': blocos['media_final'],
                'Freq. Final': freq_final_calc,
                'Núcleo': nucleo,
                'Freq. 1º BI': max(0.0, 100.0 - blocos['faltas'][0]),
                'Freq. 2º BI': max(0.0, 100.0 - blocos['faltas'][1]),
                'Freq. 3º BI': max(0.0, 100.0 - blocos['faltas'][2]),
                'Freq. 4º BI': max(0.0, 100.0 - blocos['faltas'][3]),
                'Observações': ''
            })

    return pd.DataFrame(dados_finais)

# =========================================================================
# TELA 1: UPLOAD DOS RELATÓRIOS EM PDF
# =========================================================================
if not st.session_state.dados_carregados:
    st.title("📂 Inicialização de Dados - Upload de PDFs")
    st.subheader("Selecione a sala correspondente e faça o upload dos relatórios em PDF.")
    
    sala_selecionada = st.selectbox("Selecione a Sala:", list(DICIONARIO_SALAS.keys()))
    arquivos_enviados = st.file_uploader("Arraste e solte quantos PDFs desejar aqui:", type=["pdf"], accept_multiple_files=True)
    
    if st.button("PROCESSAR E ATUALIZAR DASHBOARD"):
        if arquivos_enviados:
            with st.spinner("Processando arquivos de texto e injetando na planilha correspondente..."):
                df_novo = extrair_dados_pdf(arquivos_enviados)
                
                if not df_novo.empty:
                    link_da_sala_ativa = DICIONARIO_SALAS[sala_selecionada]
                    conn.update(spreadsheet=link_da_sala_ativa, data=df_novo) 
                    
                    st.session_state.sala_ativa = sala_selecionada
                    st.session_state.dados_carregados = True
                    st.rerun()
                else:
                    st.error("Não foi possível extrair nenhum dado estruturado válido dos arquivos enviados.")
        else:
            st.error("Por favor, selecione e envie os arquivos PDF para processar.")

# =========================================================================
# TELA 2: EXIBIÇÃO VISUAL DO DASHBOARD ACADÊMICO
# =========================================================================
else:
    if st.sidebar.button("🔄 Voltar para Tela de Upload"):
        st.session_state.dados_carregados = False
        st.session_state.aluno_idx = 0
        st.session_state.disciplina_ativa = None
        st.rerun()

    st.sidebar.write(f"📊 Visualizando: **{st.session_state.sala_ativa}**")

    link_da_sala_ativa = DICIONARIO_SALAS[st.session_state.sala_ativa]
    df = conn.read(spreadsheet=link_da_sala_ativa, ttl="0")
    df.columns = df.columns.str.strip()

    if 'Observações' in df.columns:
        df['Observações'] = df['Observações'].astype(str).replace('nan', '')
    else:
        df['Observações'] = ""

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
        
        # Ajuste 2: Removido st.markdown interno com bordas. Cada coluna atua como o único retângulo.
        c1, c2 = st.columns(2)
        mat_val = df_aluno['Matrícula'].iloc[0] if 'Matrícula' in df_aluno.columns else "Não Informado"
        ser_val = df_aluno['Série'].iloc[0] if 'Série' in df_aluno.columns else "Não Informado"
        
        with c1:
            st.write(f"**Matrícula:** {mat_val}")
        with c2:
            st.write(f"**Série:** {ser_val}")

    st.divider()

    ordem_bolinha = st.radio("Ordenar disciplinas por:", ["Nota", "Frequência"], horizontal=True)

    # --- GRID CENTRAL DO DASHBOARD ---
    m1, m2, m3, m4 = st.columns([2, 3, 2, 2])

    with m1:
        st.write("### Disciplinas")
        col_ref = 'Média Final' if 'Média Final' in df_aluno.columns else '1º BI'
        if ordem_bolinha == "Frequência" and 'Freq. Final' in df_aluno.columns:
            col_ref = 'Freq. Final'
            
        df_lista = df_aluno.sort_values(by=col_ref, ascending=False)
        
        for disc in df_lista['Disciplina'].unique():
            if st.button(disc, key=f"btn_{disc}"):
                st.session_state.disciplina_ativa = disc
                st.session_state.reset_obs += 1
                st.rerun()

    if st.session_state.disciplina_ativa is None or st.session_state.disciplina_ativa not in df_aluno['Disciplina'].unique():
        st.session_state.disciplina_ativa = df_aluno['Disciplina'].iloc[0]

    df_mat = df_aluno[df_aluno['Disciplina'] == st.session_state.disciplina_ativa].iloc[0]

    with m2:
        # Mantido Gráfico de Linha para Frequência
        f_final_val = df_mat['Freq. Final'] if 'Freq. Final' in df_mat else 1.0
        f_final_display = round(f_final_val * 100, 2) if f_final_val <= 1.0 else round(f_final_val, 2)
        st.write(f"**Evolução da Frequência: {st.session_state.disciplina_ativa} (Final: {f_final_display}%)**")
        
        f1 = df_mat['Freq. 1º BI'] if 'Freq. 1º BI' in df_mat else (f_final_val*100)
        f2 = df_mat['Freq. 2º BI'] if 'Freq. 2º BI' in df_mat else (f_final_val*100)
        f3 = df_mat['Freq. 3º BI'] if 'Freq. 3º BI' in df_mat else (f_final_val*100)
        f4 = df_mat['Freq. 4º BI'] if 'Freq. 4º BI' in df_mat else (f_final_val*100)
        
        fig_f = px.line(x=['1º BI', '2º BI', '3º BI', '4º BI'], y=[f1, f2, f3, f4], markers=True)
        fig_f.update_yaxes(range=[0, 105], title="Frequência (%)")
        st.plotly_chart(fig_f, use_container_width=True)
        
        st.divider()
        
        # Mantido Gráfico de Barras para Notas
        val_m_final = round(float(df_mat['Média Final']), 2) if 'Média Final' in df_mat else 0.0
        st.write(f"**Notas por Bimestre (Média Final: {val_m_final})**")
        
        n1 = df_mat['1º BI'] if '1º BI' in df_mat else 0.0
        n2 = df_mat['2º BI'] if '2º BI' in df_mat else 0.0
        n3 = df_mat['3º BI'] if '3º BI' in df_mat else 0.0
        n4 = df_mat['4º BI'] if '4º BI' in df_mat else 0.0
        
        fig_n = px.bar(x=['1º BI', '2º BI', '3º BI', '4º BI'], y=[n1, n2, n3, n4])
        fig_n.update_yaxes(range=[0, 10.5], title="Notas")
        st.plotly_chart(fig_n, use_container_width=True)

    with m3:
        st.write("### Global")
        m_comum = df_aluno[df_aluno['Núcleo'] == 'Comum']['Média Final'].mean() if 'Média Final' in df_aluno.columns else 0.0
        m_tec = df_aluno[df_aluno['Núcleo'] == 'Técnico']['Média Final'].mean() if 'Média Final' in df_aluno.columns else 0.0
        nota_mat_df = df_aluno[df_aluno['Disciplina'].str.contains('Matemática', case=False)] if 'Média Final' in df_aluno.columns else pd.DataFrame()
        nota_mat = nota_mat_df['Média Final'].values[0] if not nota_mat_df.empty else 0.0
        
        st.write(f"Média Núcleo Comum: **{round(m_comum, 2) if pd.notna(m_comum) else 0}**")
        st.write(f"Média Núcleo Técnico: **{round(m_tec, 2) if pd.notna(m_tec) else 0}**")
        st.write(f"Média Matemática: **{round(float(nota_mat), 2)}**")
        st.divider()
        
        m_global = df_aluno['Média Final'].mean() if 'Média Final' in df_aluno.columns else 0.0
        st.metric("Média Global", f"{round(m_global, 1)}")

    with m4:
        st.write("### Observações")
        chave_base = f"{aluno_nome}_{st.session_state.disciplina_ativa}_{st.session_state.reset_obs}".replace(" ", "_")
        obs_banco = str(df_mat['Observações']) if 'Observações' in df_mat.index and pd.notna(df_mat['Observações']) else ""
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
        options_ordenadas = sorted(list(dict_chamada.keys()))
        
        escolha_num = st.selectbox(
            "Aluno Nº:", 
            options=options_ordenadas, 
            index=options_ordenadas.index(num_atual)
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
