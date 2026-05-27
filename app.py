import streamlit as st
import pandas as pd
import plotly.express as px
from streamlit_gsheets import GSheetsConnection
from pypdf import PdfReader
import re
import io
from datetime import datetime

# =========================================================
# CONFIGURAÇÃO DA PÁGINA
# =========================================================

st.set_page_config(
    page_title="Dashboard Acadêmico",
    layout="wide"
)

# =========================================================
# CSS
# =========================================================

st.markdown("""
<style>

.main {
    background-color: #f5f5f5;
}

[data-testid="stColumn"] {
    border: 2px solid black !important;
    border-radius: 20px !important;
    padding: 20px !important;
    background-color: white !important;
    margin-bottom: 10px;
}

.stButton > button {
    width: 100%;
    border-radius: 10px;
    border: 1px solid #d0d0d0;
    text-align: left;
}

.stRadio > div {
    flex-direction: row;
    gap: 20px;
}

</style>
""", unsafe_allow_html=True)

# =========================================================
# CONEXÃO GSHEETS
# =========================================================

conn = st.connection(
    "gsheets",
    type=GSheetsConnection
)

# =========================================================
# LINKS DAS PLANILHAS
# =========================================================

DICIONARIO_SALAS = {

    "Sala 1":
    st.secrets["connections"]["gsheets"]["sala1"],

    "Sala 2":
    st.secrets["connections"]["gsheets"]["sala2"],

    "Sala 3":
    st.secrets["connections"]["gsheets"]["sala3"],

    "Sala 4":
    st.secrets["connections"]["gsheets"]["sala4"],

    "Sala 5":
    st.secrets["connections"]["gsheets"]["sala5"],

    "Sala 6":
    st.secrets["connections"]["gsheets"]["sala6"]
}

# =========================================================
# SESSION STATE
# =========================================================

if "pagina" not in st.session_state:
    st.session_state.pagina = "upload"

if "sala_ativa" not in st.session_state:
    st.session_state.sala_ativa = "Sala 1"

if "ano_ativo" not in st.session_state:
    st.session_state.ano_ativo = str(datetime.now().year)

if "aluno_idx" not in st.session_state:
    st.session_state.aluno_idx = 0

if "disciplina_ativa" not in st.session_state:
    st.session_state.disciplina_ativa = None

# =========================================================
# EXTRAÇÃO REAL DO PDF
# =========================================================

def extrair_dados_pdf(arquivo_pdf):

    leitor = PdfReader(io.BytesIO(arquivo_pdf.read()))

    texto = ""

    for pagina in leitor.pages:

        conteudo = pagina.extract_text()

        if conteudo:
            texto += conteudo + "\n"

    linhas = texto.split("\n")

    aluno = ""
    matricula = ""
    serie = ""
    chamada = ""

    dados = []

    for linha in linhas:

        linha = linha.strip()

        if not linha:
            continue

        # =================================================
        # IDENTIFICAÇÃO
        # =================================================

        if "Aluno" in linha and not aluno:
            aluno = linha

        if ("Matr" in linha or "Registro" in linha) and not matricula:
            matricula = linha

        if ("Série" in linha or "Ano" in linha) and not serie:
            serie = linha

        if ("Chamada" in linha or "Nº" in linha) and not chamada:
            chamada = linha

        # =================================================
        # CAPTURA DE NÚMEROS REAIS
        # =================================================

        numeros = re.findall(r"\d+[.,]?\d*", linha)

        if len(numeros) > 0:

            registro = {
                "Aluno": aluno,
                "Matrícula": matricula,
                "Série": serie,
                "Nº Chamada": chamada,
                "Disciplina": linha,
                "Observações": ""
            }

            for i, valor in enumerate(numeros):

                registro[f"Valor {i+1}"] = valor

            dados.append(registro)

    return pd.DataFrame(dados)

# =========================================================
# CARREGAR PLANILHA
# =========================================================

def carregar_planilha(link_planilha):

    try:

        df = conn.read(
            spreadsheet=link_planilha,
            ttl=0
        )

        if df is None:
            return pd.DataFrame()

        return pd.DataFrame(df)

    except:
        return pd.DataFrame()

# =========================================================
# SALVAR PLANILHA
# =========================================================

def salvar_planilha(df_final, link_planilha):

    conn.update(
        spreadsheet=link_planilha,
        data=df_final
    )

# =========================================================
# SUBSTITUIR ALUNO
# =========================================================

def atualizar_dados(df_existente, df_novo):

    if df_existente.empty:
        return df_novo

    alunos_novos = df_novo["Aluno"].unique()

    df_existente = df_existente[
        ~df_existente["Aluno"].isin(alunos_novos)
    ]

    df_final = pd.concat(
        [df_novo, df_existente],
        ignore_index=True
    )

    return df_final

# =========================================================
# PÁGINA UPLOAD
# =========================================================

if st.session_state.pagina == "upload":

    st.title("Upload dos PDFs")

    c1, c2 = st.columns(2)

    with c1:

        sala = st.selectbox(
            "Sala",
            list(DICIONARIO_SALAS.keys())
        )

    with c2:

        ano = st.text_input(
            "Ano",
            value=str(datetime.now().year)
        )

    arquivos = st.file_uploader(
        "Selecione os PDFs",
        type=["pdf"],
        accept_multiple_files=True
    )

    if st.button("PROCESSAR PDFs"):

        if arquivos:

            with st.spinner("Processando..."):

                link_planilha = DICIONARIO_SALAS[sala]

                df_existente = carregar_planilha(
                    link_planilha
                )

                todos = []

                for arquivo in arquivos:

                    df_pdf = extrair_dados_pdf(
                        arquivo
                    )

                    if not df_pdf.empty:

                        df_pdf["Ano"] = ano

                        todos.append(df_pdf)

                if len(todos) > 0:

                    df_novo = pd.concat(
                        todos,
                        ignore_index=True
                    )

                    df_final = atualizar_dados(
                        df_existente,
                        df_novo
                    )

                    salvar_planilha(
                        df_final,
                        link_planilha
                    )

                    st.session_state.sala_ativa = sala
                    st.session_state.ano_ativo = ano
                    st.session_state.pagina = "dashboard"

                    st.rerun()

# =========================================================
# DASHBOARD
# =========================================================

else:

    st.sidebar.title("Dashboards")

    sala_side = st.sidebar.selectbox(
        "Sala",
        list(DICIONARIO_SALAS.keys()),
        index=list(DICIONARIO_SALAS.keys()).index(
            st.session_state.sala_ativa
        )
    )

    if st.sidebar.button("Abrir Dashboard"):

        st.session_state.sala_ativa = sala_side

        st.rerun()

    if st.sidebar.button("Voltar para Upload"):

        st.session_state.pagina = "upload"

        st.rerun()

    # =====================================================
    # LEITURA
    # =====================================================

    link_planilha = DICIONARIO_SALAS[
        st.session_state.sala_ativa
    ]

    df = carregar_planilha(
        link_planilha
    )

    if df.empty:

        st.warning("Sem dados.")

        st.stop()

    if "Ano" in df.columns:

        df = df[
            df["Ano"].astype(str)
            ==
            st.session_state.ano_ativo
        ]

    if df.empty:

        st.warning("Sem dados nesse ano.")

        st.stop()

    alunos = df["Aluno"].dropna().unique().tolist()

    if len(alunos) == 0:

        st.warning("Nenhum aluno.")

        st.stop()

    if st.session_state.aluno_idx >= len(alunos):
        st.session_state.aluno_idx = 0

    aluno_nome = alunos[
        st.session_state.aluno_idx
    ]

    df_aluno = df[
        df["Aluno"] == aluno_nome
    ]

    # =====================================================
    # TOPO
    # =====================================================

    st.title(
        f"{st.session_state.sala_ativa} - {st.session_state.ano_ativo}"
    )

    st.subheader(aluno_nome)

    # =====================================================
    # IDENTIFICAÇÃO
    # =====================================================

    t1, t2 = st.columns([1, 4])

    with t1:

        st.image(
            "https://via.placeholder.com/150",
            use_container_width=True
        )

    with t2:

        c1, c2 = st.columns(2)

        mat = ""
        serie = ""

        if "Matrícula" in df_aluno.columns:
            mat = df_aluno["Matrícula"].iloc[0]

        if "Série" in df_aluno.columns:
            serie = df_aluno["Série"].iloc[0]

        c1.markdown(
            f"""
            <div style="
            border:2px solid black;
            border-radius:15px;
            padding:15px;
            ">
            <b>Matrícula:</b><br>{mat}
            </div>
            """,
            unsafe_allow_html=True
        )

        c2.markdown(
            f"""
            <div style="
            border:2px solid black;
            border-radius:15px;
            padding:15px;
            ">
            <b>Série:</b><br>{serie}
            </div>
            """,
            unsafe_allow_html=True
        )

    st.divider()

    # =====================================================
    # DISCIPLINAS
    # =====================================================

    disciplinas = df_aluno[
        "Disciplina"
    ].dropna().unique().tolist()

    if st.session_state.disciplina_ativa not in disciplinas:

        st.session_state.disciplina_ativa = disciplinas[0]

    m1, m2, m3, m4 = st.columns([2, 3, 2, 2])

    # =====================================================
    # COLUNA DISCIPLINAS
    # =====================================================

    with m1:

        st.write("### Disciplinas")

        for disc in disciplinas:

            if st.button(
                disc,
                key=f"disc_{disc}"
            ):

                st.session_state.disciplina_ativa = disc

                st.rerun()

    # =====================================================
    # LINHA DA DISCIPLINA
    # =====================================================

    linha = df_aluno[
        df_aluno["Disciplina"]
        ==
        st.session_state.disciplina_ativa
    ].iloc[0]

    # =====================================================
    # VALORES REAIS
    # =====================================================

    nomes = []
    valores = []

    for coluna in df.columns:

        if "Valor" in coluna:

            valor = linha[coluna]

            try:

                valor_num = float(
                    str(valor)
                    .replace(",", ".")
                )

                nomes.append(coluna)
                valores.append(valor_num)

            except:
                pass

    # =====================================================
    # GRÁFICO
    # =====================================================

    with m2:

        st.write(
            st.session_state.disciplina_ativa
        )

        if len(valores) > 0:

            fig = px.line(
                x=nomes,
                y=valores,
                markers=True
            )

            st.plotly_chart(
                fig,
                use_container_width=True
            )

    # =====================================================
    # DADOS GERAIS
    # =====================================================

    with m3:

        st.write("### Global")

        st.metric(
            "Quantidade",
            len(df_aluno)
        )

    # =====================================================
    # OBSERVAÇÕES
    # =====================================================

    with m4:

        st.write("### Observações")

        obs = st.text_area(
            "",
            value=str(
                linha["Observações"]
            )
        )

        if st.button("Salvar Observação"):

            idx = df[
                (df["Aluno"] == aluno_nome)
                &
                (
                    df["Disciplina"]
                    ==
                    st.session_state.disciplina_ativa
                )
            ].index

            if len(idx) > 0:

                df.at[
                    idx[0],
                    "Observações"
                ] = obs

                salvar_planilha(
                    df,
                    link_planilha
                )

                st.success("Salvo")

                st.rerun()

    # =====================================================
    # NAVEGAÇÃO
    # =====================================================

    st.divider()

    b1, b2, b3 = st.columns([1, 1, 1])

    with b1:

        if st.button("⬅️ Anterior"):

            st.session_state.aluno_idx = (
                st.session_state.aluno_idx - 1
            ) % len(alunos)

            st.session_state.disciplina_ativa = None

            st.rerun()

    with b2:

        novo = st.selectbox(
            "Aluno",
            alunos,
            index=st.session_state.aluno_idx
        )

        st.session_state.aluno_idx = alunos.index(
            novo
        )

    with b3:

        if st.button("Próximo ➡️"):

            st.session_state.aluno_idx = (
                st.session_state.aluno_idx + 1
            ) % len(alunos)

            st.session_state.disciplina_ativa = None

            st.rerun()
