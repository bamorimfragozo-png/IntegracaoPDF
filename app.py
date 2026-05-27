import streamlit as st
import pandas as pd
import plotly.express as px
from streamlit_gsheets import GSheetsConnection
from pypdf import PdfReader
import io

# =========================================================================
# 1. CONFIGURAÇÃO DA PÁGINA E ESTILO CSS ORIGINAL (BORDAS ARREDONDADAS)
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
# 2. CONEXÃO DIRETA COM O GSHEETS
# =========================================================================
conn = st.connection("gsheets", type=GSheetsConnection)

# =========================================================================
# 3. ESTADOS DE SESSÃO LOCAL PARA NAVEGAÇÃO
# =========================================================================
if 'tela_atual' not in st.session_state:
    st.session_state.tela_atual = "Dashboard"
if 'aluno_idx' not in st.session_state: 
    st.session_state.aluno_idx = 0
if 'disciplina_ativa' not in st.session_state: 
    st.session_state.disciplina_ativa = None
if 'reset_obs' not in st.session_state: 
    st.session_state.reset_obs = 0

# Leitura direta sem cache para sincronização entre usuários
try:
    df = conn.read(ttl="0")
    df.columns = df.columns.str.strip()
except Exception:
    df = pd.DataFrame()

# =========================================================================
# 4. FUNÇÃO DE EXTRAÇÃO REAL DE DADOS DO PDF (SEM DADOS SIMULADOS)
# =========================================================================
def extrair_dados_pdf(arquivos_pdf):
    dados_finais = []
    lista_disciplinas_padrao = ["Matemática", "Português", "História", "Geografia", "Biologia", "Física", "Química", "ILPR", "ININ"]
    
    meses_cols = ['Freq. Jan.', 'Freq. Fev.', 'Freq. Mar.', 'Freq. Abr.', 'Freq. Mai.', 'Freq. Jun.', 
                  'Freq. Jul.', 'Freq. Ago.', 'Freq. Set.', 'Freq. Out.', 'Freq. Nov.', 'Freq. Dez.']

    for numero_chamada, arquivo in enumerate(arquivos_pdf, start=1):
        pdf_reader = PdfReader(io.BytesIO(arquivo.read()))
        texto_completo = ""
        for pagina in pdf_reader.pages:
            texto_completo += pagina.extract_text() + "\n"
        
        linhas = texto_completo.split('\n')
        
        nome_aluno = ""
        matricula_aluno = 0
        serie_aluno = ""
        
        # Procura metadados do aluno nas linhas
        for linha in linhas:
            if "Aluno" in linha or "Nome" in linha:
                partes = linha.split(":")
                nome_aluno = partes[1].strip() if len(partes) > 1 else linha.replace("Aluno", "").replace("Nome", "").strip()
            if "Matrícula" in linha or "Matricula" in linha:
                numeros = ''.join(c for c in linha if c.isdigit())
                if numeros: matricula_aluno = int(numeros)
            if "Série" in linha or "Serie" in linha or "Ano" in linha:
                if "1" in linha: serie_aluno = "1º Ano"
                elif "2" in linha: serie_aluno = "2º Ano"
                elif "3" in linha: serie_aluno = "3º Ano"

        if not nome_aluno:
            nome_aluno = arquivo.name.replace(".pdf", "").replace("Boletim", "").replace("_", " ").strip()

        # Procura linhas de disciplinas e extrai apenas números existentes
        for linha in linhas:
            for disc in lista_disciplinas_padrao:
                if disc.lower() in linha.lower():
                    linha_limpa = linha.replace('%', '').replace(',', '.')
                    valores_linha = []
                    
                    for token in linha_limpa.split():
                        try:
                            valores_linha.append(float(token))
                        except ValueError:
                            pass
                    
                    # Se não houver valores numéricos na linha da disciplina, ela não é processada incorretamente
                    if not valores_linha:
                        continue
                        
                    registro = {
                        'Nº Chamada': numero_chamada,
                        'Aluno': nome_aluno,
                        'Matrícula': matricula_aluno,
                        'Série': serie_aluno,
                        'Disciplina': disc,
                        '1º BI': valores_linha[0] if len(valores_linha) > 0 else 0.0,
                        '2º BI': valores_linha[1] if len(valores_linha) > 1 else 0.0,
                        '3º BI': valores_linha[2] if len(valores_linha) > 2 else 0.0,
                        '4º BI': valores_linha[3] if len(valores_linha) > 3 else 0.0,
                        'Média Final': valores_linha[4] if len(valores_linha) > 4 else 0.0,
                        'Freq. Final': valores_linha[5] if len(valores_linha) > 5 else 0.0,
                        'Núcleo': "Técnico" if disc in ["ILPR", "ININ"] else "Comum",
                        'Observações': ''
                    }
                    
                    # Associa as frequências mensais sequenciais se existirem no texto
                    idx_mes = 6
                    for m in meses_cols:
                        registro[m] = valores_linha[idx_mes] if len(valores_linha) > idx_mes else 0.0
                        idx_mes += 1
                        
                    dados_finais.append(registro)

    return pd.DataFrame(dados_finais)

# =========================================================================
# 5. CONTROLE DE TELAS
# =========================================================================
st.sidebar.title("🧭 Menu")
st.session_state.tela_atual = st.sidebar.radio("Ir para:", ["Ver Dashboard", "Fazer Upload de PDFs"])

# =========================================================================
# TELA: UPLOAD DE PDFS
# =========================================================================
if st.session_state.tela_atual == "Fazer Upload de PDFs":
    st.title("📂 Upload de Relatórios Acadêmicos")
    arquivos_enviados = st.file_uploader("Arraste e solte os PDFs aqui:", type=["pdf"], accept_multiple_files=True)
    
    if st.button("PROCESSAR E ATUALIZAR PLANILHA", use_container_width=True):
        if arquivos_enviados:
            with st.spinner("Processando..."):
                df_novos = extrair_dados_pdf(arquivos_enviados)
                
                if not df_novos.empty:
                    if not df.empty and 'Aluno' in df.columns:
                        # Substituição de linhas duplicadas baseada em Aluno e Disciplina
                        df['chave_id'] = df['Aluno'].astype(str) + "_" + df['Disciplina'].astype(str)
                        df_novos['chave_id'] = df_novos['Aluno'].astype(str) + "_" + df_novos['Disciplina'].astype(str)
                        
                        df_antigo_filtrado = df[~df['chave_id'].isin(df_novos['chave_id'])].copy()
                        df_final = pd.concat([df_antigo_filtrado, df_novos], ignore_index=True)
                        df_final.drop(columns=['chave_id'], errors='ignore', inplace=True)
                    else:
                        df_final = df_novos
                    
                    conn.update(data=df_final)
                    st.success("Planilha atualizada com sucesso!")
                    st.session_state.tela_atual = "Ver Dashboard"
                    st.rerun()
                else:
                    st.error("Nenhum dado numérico foi localizado no padrão de disciplinas.")
        else:
            st.error("Por favor, selecione os arquivos antes de processar.")

# =========================================================================
# TELA: DASHBOARD VISUAL ORIGINAL
# =========================================================================
else:
    if df.empty or 'Aluno' not in df.columns:
        st.info("Nenhum dado encontrado na planilha. Realize o Upload de PDFs.")
    else:
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

        # --- TOPO: IDENTIFICAÇÃO ---
        t1, t2 = st.columns([1, 4])
        with t1:
            st.markdown("### Foto")
            st.image("https://via.placeholder.com/150", use_container_width=True)
        with t2:
            st.subheader(f"Nome: {aluno_nome}")
            c1, c2 = st.columns(2)
            c1.write(f"**Matrícula:** {df_aluno['Matrícula'].iloc[0] if 'Matrícula' in df_aluno.columns else ''}")
            c2.write(f"**Série:** {df_aluno['Série'].iloc[0] if 'Série' in df_aluno.columns else ''}")

        st.divider()

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

        if st.session_state.disciplina_ativa is None or st.session_state.disciplina_ativa not in df_aluno['Disciplina'].unique():
            st.session_state.disciplina_ativa = df_aluno['Disciplina'].iloc[0]

        df_mat = df_aluno[df_aluno['Disciplina'] == st.session_state.disciplina_ativa].iloc[0]

        with m2:
            # Gráfico de Notas (Linhas)
            val_m_final = round(float(df_mat['Média Final']), 2) if 'Média Final' in df_mat else 0.0
            st.write(f"**Evolução: {st.session_state.disciplina_ativa} (Média Final: {val_m_final})**")
            fig_n = px.line(x=['1º BI', '2º BI', '3º BI', '4º BI'], 
                            y=[df_mat.get('1º BI', 0.0), df_mat.get('2º BI', 0.0), df_mat.get('3º BI', 0.0), df_mat.get('4º BI', 0.0)], markers=True)
            fig_n.update_yaxes(range=[0, 10.5])
            st.plotly_chart(fig_n, use_container_width=True)
            
            st.divider()
            
            # Gráfico de Frequência Mensal (Barras Original)
            f_final_val = df_mat.get('Freq. Final', 0.0)
            f_final_display = round(f_final_val * 100, 2) if f_final_val <= 1.0 else round(f_final_val, 2)
            st.write(f"**Frequência Mensal (Final: {f_final_display}%)**")
            
            meses_cols = ['Freq. Jan.', 'Freq. Fev.', 'Freq. Mar.', 'Freq. Abr.', 'Freq. Mai.', 'Freq. Jun.', 
                          'Freq. Jul.', 'Freq. Ago.', 'Freq. Set.', 'Freq. Out.', 'Freq. Nov.', 'Freq. Dez.']
            
            valores_f = []
            for m in meses_cols:
                val = df_mat.get(m, 0.0)
                try:
                    v = float(str(val).replace('%','').replace(',','.'))
                    valores_f.append(round(v * 100, 2) if v <= 1.0 else round(v, 2))
                except: 
                    valores_f.append(0.0)
                
            fig_f = px.bar(x=[mes.split('.')[1].strip() for mes in meses_cols], y=valores_f)
            fig_f.update_yaxes(range=[0, 105], title="Porcentagem (%)")
            st.plotly_chart(fig_f, use_container_width=True)

        with m3:
            st.write("### Global")
            m_comum = df_aluno[df_aluno['Núcleo'] == 'Comum']['Média Final'].mean() if 'Média Final' in df_aluno.columns else 0.0
            m_tec = df_aluno[df_aluno['Núcleo'] == 'Técnico']['Média Final'].mean() if 'Média Final' in df_aluno.columns else 0.0
            nota_mat_df = df_aluno[df_aluno['Disciplina'].str.contains('Matemática', case=False)] if 'Média Final' in df_aluno.columns else pd.DataFrame()
            nota_mat = nota_mat_df['Média Final'].values[0] if not nota_mat_df.empty else 0.0
            
            st.write(f"Média Núcleo Comum: **{round(m_comum, 2) if pd.notna(m_comum) else 0.0}**")
            st.write(f"Média Núcleo Técnico: **{round(m_tec, 2) if pd.notna(m_tec) else 0.0}**")
            st.write(f"Média Matemática: **{round(float(nota_mat), 2)}**")
            st.divider()
            st.metric("Média Global", f"{round(df_aluno['Média Final'].mean(), 1) if 'Média Final' in df_aluno.columns else 0.0}")

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
                            conn.update(data=df)
                            st.session_state.reset_obs += 1
                            st.success("Salvo!")
                            st.rerun()

        # --- RODAPÉ: NAVEGAÇÃO DOS ALUNOS ---
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
            
            escolha_num = st.selectbox("Aluno Nº:", options=opcoes_ordenadas, index=opcoes_ordenadas.index(num_atual))
            
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
