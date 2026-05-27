import streamlit as st
import pandas as pd
import plotly.express as px
from streamlit_gsheets import GSheetsConnection
from pypdf import PdfReader
import io

# =========================================================================
# 1. CONFIGURAÇÃO DA PÁGINA E ESTILO CSS
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
# 2. CONEXÃO E DICIONÁRIO DE PLANILHAS (SECRETS)
# =========================================================================
conn = st.connection("gsheets", type=GSheetsConnection)

DICIONARIO_SALAS = {
    "Sala 1": st.secrets["connections"]["gsheets"].get("sala1"),
    "Sala 2": st.secrets["connections"]["gsheets"].get("sala2"),
    "Sala 3": st.secrets["connections"]["gsheets"].get("sala3"),
    "Sala 4": st.secrets["connections"]["gsheets"].get("sala4"),
    "Sala 5": st.secrets["connections"]["gsheets"].get("sala5"),
    "Sala 6": st.secrets["connections"]["gsheets"].get("sala6")
}

# =========================================================================
# 3. CONTROLE DE ESTADOS DE SESSÃO
# =========================================================================
if 'tela_atual' not in st.session_state:
    st.session_state.tela_atual = "Upload de Dados"
if 'aluno_idx' not in st.session_state: 
    st.session_state.aluno_idx = 0
if 'disciplina_ativa' not in st.session_state: 
    st.session_state.disciplina_ativa = None
if 'reset_obs' not in st.session_state: 
    st.session_state.reset_obs = 0
if 'sala_selecionada_visualizacao' not in st.session_state:
    st.session_state.sala_selecionada_visualizacao = "Sala 1"

# =========================================================================
# 4. FUNÇÃO DE EXTRAÇÃO 100% REAL DO PDF (SEM VARIÁVEIS FIXAS/INVENTADAS)
# =========================================================================
def extrair_dados_pdf(arquivos_pdf):
    dados_finais = []
    
    for numero_chamada, arquivo in enumerate(arquivos_pdf, start=1):
        try:
            pdf_reader = PdfReader(io.BytesIO(arquivo.read()))
            texto_completo = ""
            for pagina in pdf_reader.pages:
                texto_completo += (pagina.extract_text() or "") + "\n"
            
            linhas = texto_completo.split('\n')
            
            nome_aluno = ""
            matricula_aluno = ""
            serie_aluno = ""
            ano_letivo_pdf = ""
            
            # Busca o Ano Letivo real varrendo o texto do PDF por padrões de 4 dígitos (Ex: 2024, 2025)
            for linha in linhas:
                if "Ano Letivo" in linha or "Ano" in linha or "Exercício" in linha:
                    palavras = linha.split()
                    for p in palavras:
                        p_limpa = ''.join(c for c in p if c.isdigit())
                        if len(p_limpa) == 4:
                            ano_letivo_pdf = p_limpa
                            break
            
            # Se não achou no texto, tenta extrair se houver um ano de 4 dígitos no nome do arquivo do boletim
            if not ano_letivo_pdf:
                numeros_nome = ''.join(c if c.isdigit() else ' ' for c in arquivo.name).split()
                for n in numeros_nome:
                    if len(n) == 4:
                        ano_letivo_pdf = n
                        break
            
            # Caso ainda assim permaneça vazio, define como "Sem Ano" para não inventar dados
            if not ano_letivo_pdf:
                ano_letivo_pdf = "Indefinido"

            # Captura metadados básicos reais do PDF
            for linha in linhas:
                if "Aluno" in linha or "Nome" in linha:
                    partes = linha.split(":")
                    nome_aluno = partes[1].strip() if len(partes) > 1 else linha.replace("Aluno", "").replace("Nome", "").strip()
                if "Matrícula" in linha or "Matricula" in linha:
                    numeros = ''.join(c for c in linha if c.isdigit())
                    if numeros: matricula_aluno = numeros
                if "Série" in linha or "Serie" in linha or "Turma" in linha:
                    if "1" in linha: serie_aluno = "1º Ano"
                    elif "2" in linha: serie_aluno = "2º Ano"
                    elif "3" in linha: serie_aluno = "3º Ano"

            if not nome_aluno:
                nome_aluno = arquivo.name.replace(".pdf", "").replace("Boletim", "").replace("_", " ").strip()

            lista_disciplinas_padrao = ["Matemática", "Português", "História", "Geografia", "Biologia", "Física", "Química", "ILPR", "ININ"]
            
            for linha in linhas:
                for disc in lista_disciplinas_padrao:
                    if disc.lower() in linha.lower():
                        # Extrai os números puros daquela linha do componente curricular
                        valores_linha = [float(s) for s in linha.replace(',', '.').split() if s.replace('.', '', 1).isdigit()]
                        
                        nucleo = "Técnico" if disc in ["ILPR", "ININ"] else "Comum"
                        
                        registro = {
                            'Ano Letivo': ano_letivo_pdf,
                            'Nº Chamada': int(numero_chamada),
                            'Aluno': nome_aluno,
                            'Matrícula': matricula_aluno,
                            'Série': serie_aluno,
                            'Disciplina': disc,
                            'Núcleo': nucleo
                        }
                        
                        # Atribui as notas se elas existirem na linha lida
                        if len(valores_linha) > 0: registro['Nota 1º BI'] = valores_linha[0]
                        if len(valores_linha) > 1: registro['Nota 2º BI'] = valores_linha[1]
                        if len(valores_linha) > 2: registro['Nota 3º BI'] = valores_linha[2]
                        if len(valores_linha) > 3: registro['Nota 4º BI'] = valores_linha[3]
                        if len(valores_linha) > 4: registro['Média Final'] = valores_linha[4]
                        
                        # Atribui as frequências bimestrais se existirem na linha lida
                        if len(valores_linha) > 5: registro['Freq. 1º BI'] = valores_linha[5]
                        if len(valores_linha) > 6: registro['Freq. 2º BI'] = valores_linha[6]
                        if len(valores_linha) > 7: registro['Freq. 3º BI'] = valores_linha[7]
                        if len(valores_linha) > 8: registro['Freq. 4º BI'] = valores_linha[8]
                        if len(valores_linha) > 9: registro['Freq. Final'] = valores_linha[9]
                        elif len(valores_linha) > 5: registro['Freq. Final'] = valores_linha[5]
                        
                        registro['Observações'] = ''
                        dados_finais.append(registro)
        except Exception as e:
            st.error(f"Erro ao processar o arquivo {arquivo.name}: {e}")

    return pd.DataFrame(dados_finais)

# =========================================================================
# 5. LÓGICA DE SALVAMENTO ADAPTATIVA
# =========================================================================
def salvar_dados_na_planilha(sala, df_novos_dados):
    spreadsheet_url = DICIONARIO_SALAS[sala]
    if not spreadsheet_url:
        st.error(f"Link da planilha para a {sala} não configurado no Secrets.")
        return False
        
    try:
        df_existente = conn.read(spreadsheet=spreadsheet_url, ttl="0")
        df_existente.columns = df_existente.columns.str.strip()
    except:
        df_existente = pd.DataFrame()

    if df_existente.empty:
        df_resultado = df_novos_dados
    else:
        for col in ['Ano Letivo', 'Aluno', 'Disciplina']:
            if col not in df_existente.columns:
                df_existente[col] = "Indefinido"

        chaves_novas = df_novos_dados['Ano Letivo'].astype(str) + "_" + df_novos_dados['Aluno'] + "_" + df_novos_dados['Disciplina']
        chaves_existentes = df_existente['Ano Letivo'].astype(str) + "_" + df_existente['Aluno'] + "_" + df_existente['Disciplina']
        
        df_existente_filtrado = df_existente[~chaves_existentes.isin(chaves_novas)]
        df_resultado = pd.concat([df_existente_filtrado, df_novos_dados], ignore_index=True)

    for col in df_novos_dados.columns:
        if col not in df_resultado.columns:
            df_resultado[col] = "" if col == 'Observações' else 0.0

    conn.update(spreadsheet=spreadsheet_url, data=df_resultado)
    return True

# =========================================================================
# SELETOR DE TELAS NA SIDEBAR
# =========================================================================
st.sidebar.title("Navegação Interna")
st.session_state.tela_atual = st.sidebar.radio("Ir para:", ["Upload de Dados", "Visualizar Dashboards"])

# =========================================================================
# TELA 1: UPLOAD DOS RELATÓRIOS EM PDF
# =========================================================================
if st.session_state.tela_atual == "Upload de Dados":
    st.title("📂 Inicialização de Dados - Upload de PDFs")
    st.subheader("O sistema irá estruturar a planilha usando puramente as colunas e anos identificados no PDF.")
    
    sala_selecionada = st.selectbox("Selecione a Sala de Destino:", list(DICIONARIO_SALAS.keys()))
    arquivos_enviados = st.file_uploader("Arraste e solte os relatórios em PDF:", type=["pdf"], accept_multiple_files=True)
    
    if st.button("PROCESSAR E ATUALIZAR BANCO DE DADOS"):
        if arquivos_enviados:
            with st.spinner("Extraindo a estrutura nativa e real do PDF..."):
                df_novo = extrair_dados_pdf(arquivos_enviados)
                
                if not df_novo.empty:
                    sucesso = salvar_dados_na_planilha(sala_selecionada, df_novo)
                    if sucesso:
                        st.success(f"Tabela da {sala_selecionada} atualizada com sucesso com os dados brutos do arquivo!")
                        st.session_state.sala_selecionada_visualizacao = sala_selecionada
                        st.balloons()
                else:
                    st.error("Nenhum dado legível foi extraído dos arquivos anexados.")
        else:
            st.error("Por favor, anexe pelo menos um arquivo PDF.")

# =========================================================================
# TELA 2: EXIBIÇÃO VISUAL DO DASHBOARD ACADÊMICO
# =========================================================================
else:
    st.title("📊 Dashboard Acadêmico em Tempo Real")
    
    sala_ativa = st.sidebar.selectbox(
        "Alternar Visualização de Sala:", 
        list(DICIONARIO_SALAS.keys()), 
        key="sala_ativa_selectbox",
        index=list(DICIONARIO_SALAS.keys()).index(st.session_state.sala_selecionada_visualizacao)
    )
    st.session_state.sala_selecionada_visualizacao = sala_ativa

    spreadsheet_url = DICIONARIO_SALAS[sala_ativa]
    
    df = pd.DataFrame()
    if spreadsheet_url:
        try:
            df = conn.read(spreadsheet=spreadsheet_url, ttl="0")
            df.columns = df.columns.str.strip()
        except:
            df = pd.DataFrame()

    if df.empty or 'Aluno' not in df.columns:
        st.warning(f"Não há dados estruturados para a **{sala_ativa}**. Faça o upload de arquivos PDF para esta sala.")
    else:
        # --- FILTRO DINÂMICO DE ANO LETIVO BASEADO NO BANCO REAL ---
        if 'Ano Letivo' in df.columns:
            lista_anos_disponiveis = sorted(df['Ano Letivo'].astype(str).unique().tolist())
            ano_selecionado = st.sidebar.selectbox("Filtrar por Ano Letivo:", lista_anos_disponiveis, index=len(lista_anos_disponiveis)-1)
            df = df[df['Ano Letivo'].astype(str) == ano_selecionado].copy()
        
        if df.empty:
            st.warning(f"Nenhum registro encontrado para os critérios selecionados na {sala_ativa}.")
        else:
            if 'Observações' in df.columns:
                df['Observações'] = df['Observações'].astype(str).replace('nan', '')
            else:
                df['Observações'] = ""

            if 'Nº Chamada' in df.columns:
                df_ordem_chamada = df.sort_values(by='Nº Chamada', ascending=True)
            else:
                df_ordem_chamada = df
                
            alunos_lista = df_ordem_chamada['Aluno'].unique().tolist()

            if st.session_state.aluno_idx >= len(alunos_lista):
                st.session_state.aluno_idx = 0

            aluno_nome = alunos_lista[st.session_state.aluno_idx]
            df_aluno = df[df['Aluno'] == aluno_nome].copy()

            # --- BLOCO TOPO: IDENTIFICAÇÃO ---
            t1, t2 = st.columns([1, 4])
            with t1:
                st.markdown("### Foto")
                st.image("https://via.placeholder.com/150", use_container_width=True)
            with t2:
                ano_display = ano_selecionado if 'Ano Letivo' in df_aluno.columns else "Não Informado"
                st.subheader(f"Estudante: {aluno_nome} (Ano Letivo: {ano_display})")
                c1, c2 = st.columns(2)
                
                mat_val = df_aluno['Matrícula'].iloc[0] if 'Matrícula' in df_aluno.columns else "Não Informado"
                ser_val = df_aluno['Série'].iloc[0] if 'Série' in df_aluno.columns else "Não Informado"
                
                c1.markdown(f"<div style='border:2px solid black; border-radius:15px; padding:15px;'><b>Matrícula:</b> {mat_val}</div>", unsafe_allow_html=True)
                c2.markdown(f"<div style='border:2px solid black; border-radius:15px; padding:15px;'><b>Série:</b> {ser_val}</div>", unsafe_allow_html=True)

            st.divider()

            opcoes_radio = ["Nota"]
            if any(col for col in df.columns if "Freq." in col):
                opcoes_radio.append("Frequência")
                
            ordem_bolinha = st.radio("Ordenar disciplinas por menor:", opcoes_radio, horizontal=True)

            # --- GRID CENTRAL DO DASHBOARD ---
            m1, m2, m3, m4 = st.columns([2, 3, 2, 2])

            with m1:
                st.write("### Disciplinas")
                col_ref = 'Média Final' if (ordem_bolinha == "Nota" and 'Média Final' in df_aluno.columns) else ('Freq. Final' if 'Freq. Final' in df_aluno.columns else 'Disciplina')
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
                # GRÁFICO 1 (BARRAS): Notas por Bimestre Reais do PDF
                val_m_final = round(float(df_mat['Média Final']), 2) if 'Média Final' in df_mat else 0.0
                st.write(f"**Notas por Bimestre: {st.session_state.disciplina_ativa} (Média Final: {val_m_final})**")
                
                n1 = df_mat['Nota 1º BI'] if 'Nota 1º BI' in df_mat else 0.0
                n2 = df_mat['Nota 2º BI'] if 'Nota 2º BI' in df_mat else 0.0
                n3 = df_mat['Nota 3º BI'] if 'Nota 3º BI' in df_mat else 0.0
                n4 = df_mat['Nota 4º BI'] if 'Nota 4º BI' in df_mat else 0.0
                
                fig_n = px.bar(x=['1º BI', '2º BI', '3º BI', '4º BI'], y=[n1, n2, n3, n4])
                fig_n.update_yaxes(range=[0, 10.5], title="Notas")
                st.plotly_chart(fig_n, use_container_width=True)
                
                st.divider()
                
                # GRÁFICO 2 (LINHAS): Frequências por Bimestre Reais do PDF
                f_final_val = df_mat['Freq. Final'] if 'Freq. Final' in df_mat else 0.0
                st.write(f"**Evolução da Frequência: {st.session_state.disciplina_ativa} (Média Retida: {round(f_final_val, 1)}%)**")
                
                f1 = df_mat['Freq. 1º BI'] if 'Freq. 1º BI' in df_mat else 0.0
                f2 = df_mat['Freq. 2º BI'] if 'Freq. 2º BI' in df_mat else 0.0
                f3 = df_mat['Freq. 3º BI'] if 'Freq. 3º BI' in df_mat else 0.0
                f4 = df_mat['Freq. 4º BI'] if 'Freq. 4º BI' in df_mat else 0.0
                
                fig_f = px.line(x=['1º BI', '2º BI', '3º BI', '4º BI'], y=[f1, f2, f3, f4], markers=True)
                fig_f.update_yaxes(range=[0, 105], title="Frequência (%)")
                st.plotly_chart(fig_f, use_container_width=True)

            with m3:
                st.write("### Global")
                m_comum = df_aluno[df_aluno['Núcleo'] == 'Comum']['Média Final'].mean() if ('Núcleo' in df_aluno.columns and 'Média Final' in df_aluno.columns) else 0.0
                m_tec = df_aluno[df_aluno['Núcleo'] == 'Técnico']['Média Final'].mean() if ('Núcleo' in df_aluno.columns and 'Média Final' in df_aluno.columns) else 0.0
                
                nota_mat_df = df_aluno[df_aluno['Disciplina'].str.contains('Matemática', case=False)] if 'Disciplina' in df_aluno.columns else pd.DataFrame()
                nota_mat = nota_mat_df['Média Final'].values[0] if (not nota_mat_df.empty and 'Média Final' in nota_mat_df.columns) else 0.0
                
                st.write(f"Média Núcleo Comum: **{round(m_comum, 2) if pd.notna(m_comum) else 0.0}**")
                st.write(f"Média Núcleo Técnico: **{round(m_tec, 2) if pd.notna(m_tec) else 0.0}**")
                st.write(f"Média Matemática: **{round(float(nota_mat), 2) if pd.notna(nota_mat) else 0.0}**")
                st.divider()
                
                m_global = df_aluno['Média Final'].mean() if 'Média Final' in df_aluno.columns else 0.0
                st.metric("Média Global", f"{round(m_global, 1) if pd.notna(m_global) else 0.0}")

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
                                df_completo_salvamento = conn.read(spreadsheet=spreadsheet_url, ttl="0")
                                df_completo_salvamento.columns = df_completo_salvamento.columns.str.strip()
                                
                                idx_alvo = df_completo_salvamento[
                                    (df_completo_salvamento['Ano Letivo'].astype(str) == ano_selecionado) & 
                                    (df_completo_salvamento['Aluno'] == aluno_nome) & 
                                    (df_completo_salvamento['Disciplina'] == st.session_state.disciplina_ativa)
                                ].index
                                
                                if not idx_alvo.empty:
                                    if 'Observações' not in df_completo_salvamento.columns:
                                        df_completo_salvamento['Observações'] = ""
                                    df_completo_salvamento.at[idx_alvo[0], 'Observações'] = str(texto_final)
                                    conn.update(spreadsheet=spreadsheet_url, data=df_completo_salvamento)
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
                if 'Nº Chamada' in df.columns:
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
                else:
                    escolha_aluno = st.selectbox("Selecione o Aluno:", options=alunos_lista, index=st.session_state.aluno_idx)
                    if alunos_lista.index(escolha_aluno) != st.session_state.aluno_idx:
                        st.session_state.aluno_idx = alunos_lista.index(escolha_aluno)
                        st.session_state.disciplina_ativa = None
                        st.session_state.reset_obs += 1
                        st.rerun()
            with b3:
                if st.button("Próximo ➡️"):
                    st.session_state.aluno_idx = (st.session_state.aluno_idx + 1) % len(alunos_lista)
                    st.session_state.disciplina_ativa = None
                    st.session_state.reset_obs += 1
                    st.rerun()
