import streamlit as st
import pandas as pd
import plotly.express as px
from streamlit_gsheets import GSheetsConnection
from pypdf import PdfReader
import io
import re


# =========================================================================
# 1. CONFIGURAÇÃO DA PÁGINA E ESTILO CSS
# =========================================================================
st.set_page_config(page_title="Dashboard Acadêmico Integrado", layout="wide")


tecnicas = [
    "ILPR", "MAIN", "ININ", "LDPR", "RDCO", "SOPE", "LPWE", "INSO", 
    "IPRE", "BDDA", "PSCO", "GCLI", "PRIN", "CNVI", "SDRE", "ASRE", 
    "RSFI", "ELET", "DCAD", "CAUT", "PROG", "PCOE", "EDIG", "PRI1", 
    "ELIN", "CISUT", "INTI", "MAPI", "CNCM", "CLPR", "REPI", "HIEP", 
    "MIMP", "PRI2"
]


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
.info-box {
    background-color: #fdfdfd;
    font-size: 16px;
    padding: 5px 0px;
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
if 'fotos_alunos' not in st.session_state:
    st.session_state.fotos_alunos = {}
if 'filtro_anterior' not in st.session_state:
    st.session_state.filtro_anterior = "Nota"


# =========================================================================
# 4. FUNÇÃO DE EXTRAÇÃO COM RETORNO DE FOTOS CORRIGIDO
# =========================================================================
def extrair_dados_pdf(arquivos_pdf):
    dados_finais = []
    
    for numero_chamada, arquivo in enumerate(arquivos_pdf, start=1):
        pdf_buffer = io.BytesIO(arquivo.getvalue())
        try:
            pdf_reader = PdfReader(pdf_buffer)
            texto_completo = ""
            for pagina in pdf_reader.pages:
                texto_completo += pagina.extract_text() + "\n"
        except Exception as e:
            st.error(f"Erro ao ler o arquivo {arquivo.name}: {e}")
            continue
        
        # --- EXTRAÇÃO DA FOTO DO PDF ---
        foto_bytes = None
        try:
            primeira_pagina = pdf_reader.pages[0]
            if "/XObject" in primeira_pagina["/Resources"]:
                xobject = primeira_pagina["/Resources"]["/XObject"].get_object()
                for obj in xobject:
                    if xobject[obj]["/Subtype"] == "/Image":
                        foto_bytes = xobject[obj].get_data()
                        break 
        except Exception:
            foto_bytes = None
        
        linhas = texto_completo.split('\n')
        nome_aluno = "Não Identificado"
        matricula_aluno = "Não Identificada"
        serie_aluno = "Não Identificada"
        
        for linha in linhas:
            if "Aluno" in linha or "Nome" in linha:
                partes = linha.split(":")
                val_nome = partes[1].strip() if len(partes) > 1 else linha.replace("Aluno", "").replace("Nome", "").strip()
                nome_aluno = re.sub(r'\bMatrícula\b.*', '', val_nome, flags=re.IGNORECASE).strip()
                
            if any(termo in linha.lower() for termo in ["matrícula", "matricula", "prontuário", "prontuario"]):
                match_bt = re.search(r"cula:\s*(.{9})", linha, re.IGNORECASE)
                if match_bt:
                    matricula_aluno = match_bt.group(1).strip()


            if "Série" in linha or "Serie" in linha or "Ano" in linha or "Turma" in linha:
                partes = inline = linha.split(":")
                if len(partes) > 1:
                    serie_aluno = partes[1].strip()[:27]


        if nome_aluno == "Não Identificado" or not nome_aluno.strip():
            nome_aluno = arquivo.name.replace(".pdf", "").replace("Boletim", "").replace("_", " ").strip()


        if foto_bytes:
            st.session_state.fotos_alunos[nome_aluno] = foto_bytes


        mapeamento_disciplinas = {}


        for linha in linhas:
            if any(p in linha for p in ["Notas das etapas", "Faltas nas etapas", "Diário", "Disciplina", "Total", "Este documento"]):
                continue
            
            linha_limpa = re.sub(r'^\d{5,6}\s+', '', linha.strip())
            if not re.search(r'[A-Z]{3,4}\.\d{4,5}|\([A-Z0-9]{5,}\)', linha_limpa):
                continue
                
            tokens = linha_limpa.split()
            partes_texto = []
            partes_dados = []
            passou_da_materia = False
            
            for token in tokens:
                if (',' in token and token.replace(',', '').isdigit()) and not passou_da_materia:
                    passou_da_materia = True
                if not passou_da_materia:
                    partes_texto.append(token)
                else:
                    partes_dados.append(token)
            
            nome_disciplina = " ".join(partes_texto).strip()
            if not nome_disciplina or len(partes_dados) < 5:
                continue


            tokens_filtrados = []
            for t in partes_dados:
                if t in ["Cursando", "(Aguarda", "Carga", "Horária)", "Horária", "Aprovado", "Retido"] or "%" in t:
                    continue
                if t == "-" or t.replace(',', '.').replace('.', '', 1).isdigit():
                    tokens_filtrados.append(t)
            
            dados_tabela = tokens_filtrados[4:] 


            notas = [0.0, 0.0, 0.0, 0.0]
            faltas = [0.0, 0.0, 0.0, 0.0]
            
            idx_dado = 0
            for b in range(4):
                if idx_dado < len(dados_tabela):
                    val_n = dados_tabela[idx_dado].replace(',', '.')
                    notas[b] = float(val_n) if val_n.replace('.', '', 1).isdigit() else 0.0
                    idx_dado += 1
                if idx_dado < len(dados_tabela):
                    val_f = dados_tabela[idx_dado]
                    faltas[b] = float(val_f) if val_f.isdigit() else 0.0
                    idx_dado += 1


            media_final = 0.0
            if idx_dado < len(dados_tabela):
                val_md = dados_tabela[idx_dado].replace(',', '.')
                if val_md.replace('.', '', 1).isdigit():
                    media_final = float(val_md)
                else:
                    notas_lancadas = [n for n in notas if n > 0]
                    media_final = sum(notas_lancadas) / len(notas_lancadas) if notas_lancadas else 0.0
            else:
                notas_lancadas = [n for n in notas if n > 0]
                media_final = sum(notas_lancadas) / len(notas_lancadas) if notas_lancadas else 0.0


            if len(nome_disciplina) > 3:
                mapeamento_disciplinas[nome_disciplina] = {
                    'notas': notas,
                    'faltas': faltas,
                    'media_final': media_final
                }


        for nome_disp, blocos in mapeamento_disciplinas.items():
            is_tecnico = any(kw in nome_disp.upper() for kw in tecnicas)
            if is_tecnico:
                nucleo = "Técnico"
            else:
                nucleo = "Comum"
            
            tables generator
            freq_final_calc = 100.0
            for token in tokens:
                if "%" in token:
                    try:
                        freq_final_calc = float(token.replace("%", "").replace(",", "."))
                    except ValueError:
                        pass
                    break

            dados_finais.append({
                'Nº Chamada': int(numero_chamada),
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
    arquivos_enviados = st.file_uploader("Arraste e solte quantos PDFs desejar aqui:", type=["pdf"], accept_multiple_files=True, key=f"uploader_{sala_selecionada}")
    
    if st.button("PROCESSAR E ATUALIZAR DASHBOARD"):
        if arquivos_enviados:
            with st.spinner("Processando arquivos e atualizando planilhas de notas..."):
                df_novo = extrair_dados_pdf(arquivos_enviados)
                
                if not df_novo.empty:
                    link_da_sala_ativa = DICIONARIO_SALAS[sala_selecionada]
                    conn.update(spreadsheet=link_da_sala_ativa, data=df_novo) 
                    
                    st.session_state.sala_ativa = sala_selecionada
                    st.session_state.dados_carregados = True
                    st.session_state.disciplina_ativa = None
                    st.session_state.aluno_idx = 0
                    st.rerun()
                else:
                    st.error("Não foi possível extrair dados estruturados válidos.")
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


    colunas_numericas = ['1º BI', '2º BI', '3º BI', '4º BI', 'Média Final', 'Freq. Final', 'Freq. 1º BI', 'Freq. 2º BI', 'Freq. 3º BI', 'Freq. 4º BI']
    for col in colunas_numericas:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col].astype(str).str.replace(',', '.'), errors='coerce').fillna(0.0)


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
        if aluno_nome in st.session_state.fotos_alunos:
            st.image(st.session_state.fotos_alunos[aluno_nome], use_container_width=True)
        else:
            st.image("https://via.placeholder.com/150", use_container_width=True)
        
    with t2:
        st.subheader(f"Nome: {aluno_nome}")
        
        c1, c2 = st.columns(2)
        mat_val = df_aluno['Matrícula'].iloc[0] if 'Matrícula' in df_aluno.columns else "Não Informado"
        ser_val = df_aluno['Série'].iloc[0] if 'Série' in df_aluno.columns else "Não Informado"
        
        c1.markdown(f"<div class='info-box'><b>Matrícula:</b> {mat_val}</div>", unsafe_allow_html=True)
        c2.markdown(f"<div class='info-box'><b>Série:</b> {ser_val}</div>", unsafe_allow_html=True)


    st.divider()


    ordem_bolinha = st.radio("Ordenar disciplinas por:", ["Nota", "Frequência"], horizontal=True)
    
    if ordem_bolinha != st.session_state.filtro_anterior:
        st.session_state.disciplina_ativa = None
        st.session_state.filtro_anterior = ordem_bolinha


    # --- GRID CENTRAL DO DASHBOARD ---
    m1, m2, m3, m4 = st.columns([2, 3, 2, 2])


    with m1:
        st.write("### Disciplinas")
        col_ref = 'Média Final' if 'Média Final' in df_aluno.columns else '1º BI'
        if ordem_bolinha == "Frequência" and 'Freq. Final' in df_aluno.columns:
            col_ref = 'Freq. Final'
            
        df_lista = df_aluno.sort_values(by=col_ref, ascending=True)
        disciplinas_ordenadas = df_lista['Disciplina'].unique().tolist()
        
        if st.session_state.disciplina_ativa is None or st.session_state.disciplina_ativa not in disciplinas_ordenadas:
            if disciplinas_ordenadas:
                st.session_state.disciplina_ativa = disciplinas_ordenadas[0]
        
        for disc in disciplinas_ordenadas:
            if st.button(disc, key=f"btn_{disc}"):
                st.session_state.disciplina_ativa = disc
                st.session_state.reset_obs += 1
                st.rerun()


    if st.session_state.disciplina_ativa:
        df_mat = df_aluno[df_aluno['Disciplina'] == st.session_state.disciplina_ativa].iloc[0]


        with m2:
            f_final_val = float(df_mat['Freq. Final'])
            # Garante que tratamos a porcentagem se ela vier como decimal (ex: 0.85 -> 85% ou 85.0 -> 85%)
            porcentagem_presenca = f_final_val * 100 if f_final_val <= 1.0 else f_final_val
            porcentagem_faltas = max(0.0, 100.0 - porcentagem_presenca)
            
            st.write(f"**Visão Anual de Frequência: {st.session_state.disciplina_ativa}**")
            
            # Criação do DataFrame de dados para o gráfico de Rosca (Donut)
            df_rosca = pd.DataFrame({
                "Status": ["Presença", "Faltas"],
                "Percentual": [porcentagem_presenca, porcentagem_faltas]
            })
            
            # Gráfico de Rosca estilizado
            fig_f = px.pie(
                df_rosca, 
                names="Status", 
                values="Percentual", 
                hole=0.6,
                color="Status",
                color_discrete_map={"Presença": "#2ecc71", "Faltas": "#e74c3c"}
            )
            
            # Ajustes para exibir o rótulo interno perfeitamente
            fig_f.update_traces(textinfo="percent+label", hoverinfo="label+percent")
            fig_f.update_layout(
                showlegend=False, 
                margin=dict(t=10, b=10, l=10, r=10),
                height=220
            )
            st.plotly_chart(fig_f, use_container_width=True)
            
            st.divider()
            
            val_m_final = round(float(df_mat['Média Final']), 2)
            st.write(f"**Notas por Bimestre (Média Final: {val_m_final})**")
            
            n1 = float(df_mat['1º BI'])
            n2 = float(df_mat['2º BI'])
            n3 = float(df_mat['3º BI'])
            n4 = float(df_mat['4º BI'])
            
            fig_n = px.bar(x=['1º BI', '2º BI', '3º BI', '4º BI'], y=[n1, n2, n3, n4])
            fig_n.update_yaxes(range=[0, 10.5], title="Notas")
            st.plotly_chart(fig_n, use_container_width=True)


        with m3:
            st.write("### Global")
            m_comum = df_aluno[df_aluno['Núcleo'] == 'Comum']['Média Final'].mean()
            m_tec = df_aluno[df_aluno['Núcleo'] == 'Técnico']['Média Final'].mean()
            nota_mat_df = df_aluno[df_aluno['Disciplina'].str.contains('Matemática', case=False)]
            nota_mat = nota_mat_df['Média Final'].values[0] if not nota_mat_df.empty else 0.0
            
            st.write(f"Média Núcleo Comum: **{round(m_comum, 2) if pd.notna(m_comum) else 0}**")
            st.write(f"Média Núcleo Técnico: **{round(m_tec, 2) if pd.notna(m_tec) else 0}**")
            st.write(f"Média Matemática: **{round(float(nota_mat), 2)}**")
            st.divider()
            
            m_global = df_aluno['Média Final'].mean()
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
        num_atual = df_aluno['Nº Chamada'].iloc[0] if not df_aluno.empty else 1
        opcoes_ordenadas = sorted(list(dict_chamada.keys()))
        
        idx_selecao = opcoes_ordenadas.index(num_atual) if num_atual in opcoes_ordenadas else 0
        
        escolha_num = st.selectbox(
            "Aluno Nº:", 
            options=opcoes_ordenadas, 
            index=idx_selecao
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


