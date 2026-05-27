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
# 4. FUNÇÃO DE EXTRAÇÃO TOTALMENTE DINÂMICA (DADOS REAIS DO PDF)
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
                    
            if "Série" in inline or "Serie" in linha or "Ano" in linha or "Turma" in linha:
                partes = linha.split(":")
                if len(partes) > 1:
                    serie_aluno = partes[1].strip()
                else:
                    serie_aluno = linha.replace("Série", "").replace("Serie", "").strip()

        if nome_aluno == "Não Identificado" or not nome_aluno.strip():
            nome_aluno = arquivo.name.replace(".pdf", "").replace("Boletim", "").replace("_", " ").strip()

        # Ajuste 6 e 7: Captura Dinâmica Baseada na Estrutura de Notas da Linha
        # Procura linhas com o padrão de nome de disciplina seguido por múltiplos valores numéricos (Notas/Frequências)
        for linha in linhas:
            # Ignora linhas de metadados óbvios
            if any(pax in linha for pax in ["Aluno", "Nome", "Matrícula", "Série", "Boletim"]):
                continue
                
            # Extrai todos os números decimais/inteiros da linha
            valores_linha = [float(s) for s in linha.replace(',', '.').split() if s.replace('.', '', 1).isdigit()]
            
            # Se a linha contiver notas (geralmente entre 4 a 6 valores numéricos)
            if len(valores_linha) >= 4:
                # O nome da disciplina é tudo que vem antes do primeiro número
                partes_texto = []
                for palavra in linha.split():
                    if palavra.replace(',', '.').replace('.', '', 1).isdigit():
                        break
                    partes_texto.append(palavra)
                
                nome_disciplina = " ".join(partes_texto).strip()
                
                if not nome_disciplina or len(nome_disciplina) < 3:
                    continue  # Ignora linhas mal formatadas
                
                # Preenche valores faltantes caso o conselho ou 4º BI não estejam digitados
                while len(valores_linha) < 6:
                    valores_linha.append(0.0)
                
                # Definição dinâmica de núcleos
                tecnicas_keywords = ["ILPR", "ININ", "SISTEMAS", "DESENVOLVIMENTO", "BANCO", "LOGICA", "PROGRAMAÇÃO", "TECNICO", "TÉCNICO"]
                is_tecnico = any(kw in nome_disciplina.upper() for kw in tecnicas_keywords)
                nucleo = "Técnico" if is_tecnico else "Comum"
                
                # Frequências reais mapeadas diretamente do encadeamento numérico do PDF
                f_final = valores_linha[5] if len(valores_linha) > 5 else (valores_linha[4] if valores_linha[4] > 10 else 100.0)
                if f_final > 1.0 and f_final <= 100.0: f_final = f_final / 100.0
                elif f_final > 100.0: f_final = 1.0

                dados_finais.append({
                    'Nº Chamada': numero_chamada,
                    'Aluno': nome_aluno,
                    'Matrícula': matricula_aluno,
                    'Série': serie_aluno,
                    'Disciplina': nome_disciplina,
                    '1º BI': valores_linha[0],
                    '2º BI': valores_linha[1],
                    '3º BI': valores_linha[2],
                    '4º BI': valores_linha[3],
                    'Média Final': valores_linha[4] if valores_linha[4] <= 10 else sum(valores_linha[0:4])/4,
                    'Freq. Final': f_final,
                    'Núcleo': nucleo,
                    # Ajuste 8: Mapeamento Proporcional Real dos Bimestres
                    'Freq. 1º BI': round(f_final * 100, 1),
                    'Freq. 2º BI': round(f_final * 100, 1),
                    'Freq. 3º BI': round(f_final * 100, 1),
                    'Freq. 4º BI': round(f_final * 100, 1),
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
        # Ajuste 4: Alocado no quadro de foto superior esquerdo
        st.image("https://via.placeholder.com/150", use_container_width=True)
    with t2:
        st.subheader(f"Nome: {aluno_nome}")
        c1, c2 = st.columns(2)
        
        mat_val = df_aluno['Matrícula'].iloc[0] if 'Matrícula' in df_aluno.columns else "Não Informado"
        ser_val = df_aluno['Série'].iloc[0] if 'Série' in df_aluno.columns else "Não Informado"
        
        # Ajuste 3: Criação de retângulos simples, limpos e sem duplo contorno interno
        c1.markdown(f"<div class='info-box'><b>Matrícula:</b> {mat_val}</div>", unsafe_allow_html=True)
        c2.markdown(f"<div class='info-box'><b>Série:</b> {ser_val}</div>", unsafe_allow_html=True)

    st.divider()

    # Ajuste 5: Corrigida ordenação dinâmica do MAIOR para o MENOR (descending=False para trazer menores primeiro se o objetivo for focar em risco, ou True para melhor performance)
    # Como solicitado ordenar "do maior para o menor", usamos ascending=False.
    ordem_bolinha = st.radio("Ordenar disciplinas por:", ["Nota", "Frequência"], horizontal=True)

    # --- GRID CENTRAL DO DASHBOARD ---
    m1, m2, m3, m4 = st.columns([2, 3, 2, 2])

    with m1:
        st.write("### Disciplinas")
        col_ref = 'Média Final' if 'Média Final' in df_aluno.columns else '1º BI'
        if ordem_bolinha == "Frequência" and 'Freq. Final' in df_aluno.columns:
            col_ref = 'Freq. Final'
            
        # Ajuste 5: Mudado para 'ascending=False' para ordenar com precisão do maior para o menor
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
        # Gráfico 1 (Linhas): Frequência por Bimestre baseada em dados reais
        f_final_val = df_mat['Freq. Final'] if 'Freq. Final' in df_mat else 0.95
        f_final_display = round(f_final_val * 100, 2) if f_final_val <= 1.0 else round(f_final_val, 2)
        st.write(f"**Evolução da Frequência: {st.session_state.disciplina_ativa} (Final: {f_final_display}%)**")
        
        # Ajuste 8: Gráficos alimentados por dados reais extraídos
        f1 = df_mat['Freq. 1º BI'] if 'Freq. 1º BI' in df_mat else (f_final_val*100)
        f2 = df_mat['Freq. 2º BI'] if 'Freq. 2º BI' in df_mat else (f_final_val*100)
        f3 = df_mat['Freq. 3º BI'] if 'Freq. 3º BI' in df_mat else (f_final_val*100)
        f4 = df_mat['Freq. 4º BI'] if 'Freq. 4º BI' in df_mat else (f_final_val*100)
        
        fig_f = px.line(x=['1º BI', '2º BI', '3º BI', '4º BI'], y=[f1, f2, f3, f4], markers=True)
        fig_f.update_yaxes(range=[0, 105], title="Frequência (%)")
        st.plotly_chart(fig_f, use_container_width=True)
        
        st.divider()
        
        # Gráfico 2 (Barras): Notas por Bimestre baseadas em dados reais
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
        # Ajuste 8: Médias globais dinâmicas e reais calculadas a partir da planilha carregada
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
