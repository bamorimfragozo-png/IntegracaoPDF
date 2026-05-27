import streamlit as st
import pandas as pd
import plotly.express as px
import gspread
import re
from google.oauth2.service_account import Credentials
from pypdf import PdfReader
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

.stSelectbox div[data-baseweb="select"] {
    border-radius: 10px !important;
}

</style>
""", unsafe_allow_html=True)

# =========================================================
# GOOGLE SHEETS
# =========================================================

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

credentials = Credentials.from_service_account_info(
    st.secrets["gcp_service_account"],
    scopes=SCOPES
)

client = gspread.authorize(credentials)

# =========================================================
# PLANILHAS DAS SALAS
# =========================================================

SALAS = {
    "Sala 1": client.open("Sala_1"),
    "Sala 2": client.open("Sala_2"),
    "Sala 3": client.open("Sala_3"),
    "Sala 4": client.open("Sala_4"),
    "Sala 5": client.open("Sala_5"),
    "Sala 6": client.open("Sala_6")
}

# =========================================================
# SESSION STATE
# =========================================================

if "pagina" not in st.session_state:
    st.session_state.pagina = "upload"

if "sala" not in st.session_state:
    st.session_state.sala = "Sala 1"

if "ano" not in st.session_state:
    st.session_state.ano = str(datetime.now().year)

if "aluno_idx" not in st.session_state:
    st.session_state.aluno_idx = 0

if "disciplina" not in st.session_state:
    st.session_state.disciplina = None

# =========================================================
# FUNÇÃO: CRIAR ABA ANUAL
# =========================================================

def obter_aba(planilha, ano):

    nome_aba = str(ano)

    try:
        aba = planilha.worksheet(nome_aba)

    except:

        aba = planilha.add_worksheet(
            title=nome_aba,
            rows=5000,
            cols=100
        )

        cabecalho = [
            "Aluno",
            "Matrícula",
            "Série",
            "Disciplina",
            "Nº Chamada",
            "Observações"
        ]

        aba.append_row(cabecalho)

    return aba

# =========================================================
# EXTRAÇÃO REAL DO PDF
# =========================================================

def extrair_pdf(arquivo):

    leitor = PdfReader(arquivo)

    texto = ""

    for pagina in leitor.pages:

        t = pagina.extract_text()

        if t:
            texto += t + "\n"

    linhas = texto.split("\n")

    aluno = ""
    matricula = ""
    serie = ""
    chamada = ""

    disciplinas = []

    for linha in linhas:

        linha_limpa = linha.strip()

        # =========================
        # ALUNO
        # =========================

        if "Aluno" in linha_limpa:

            aluno = linha_limpa

        # =========================
        # MATRÍCULA
        # =========================

        if "Matr" in linha_limpa:

            matricula = linha_limpa

        # =========================
        # SÉRIE
        # =========================

        if "Ano" in linha_limpa or "Série" in linha_limpa:

            serie = linha_limpa

        # =========================
        # DISCIPLINAS
        # =========================

        numeros = re.findall(r"\d+[.,]?\d*", linha_limpa)

        if len(numeros) >= 1:

            disciplinas.append({
                "linha": linha_limpa,
                "numeros": numeros
            })

    return {
        "aluno": aluno,
        "matricula": matricula,
        "serie": serie,
        "chamada": chamada,
        "disciplinas": disciplinas
    }

# =========================================================
# SALVAR DADOS
# =========================================================

def salvar_planilha(aba, dados):

    registros = aba.get_all_records()

    df_existente = pd.DataFrame(registros)

    novas_linhas = []

    for disc in dados["disciplinas"]:

        linha = {
            "Aluno": dados["aluno"],
            "Matrícula": dados["matricula"],
            "Série": dados["serie"],
            "Disciplina": disc["linha"],
            "Nº Chamada": dados["chamada"],
            "Observações": ""
        }

        for i, numero in enumerate(disc["numeros"]):

            linha[f"Valor {i+1}"] = numero

        novas_linhas.append(linha)

    df_novo = pd.DataFrame(novas_linhas)

    # =====================================================
    # REMOVE DADOS ANTIGOS DO MESMO ALUNO
    # =====================================================

    if not df_existente.empty:

        df_existente = df_existente[
            df_existente["Aluno"] != dados["aluno"]
        ]

    df_final = pd.concat(
        [df_novo, df_existente],
        ignore_index=True
    )

    aba.clear()

    aba.update(
        [df_final.columns.values.tolist()] +
        df_final.values.tolist()
    )

# =========================================================
# LEITURA DA PLANILHA
# =========================================================

def carregar_df(aba):

    registros = aba.get_all_records()

    if len(registros) == 0:
        return pd.DataFrame()

    return pd.DataFrame(registros)

# =========================================================
# PÁGINA: UPLOAD
# =========================================================

if st.session_state.pagina == "upload":

    st.title("Upload de PDFs")

    col1, col2 = st.columns(2)

    with col1:

        sala = st.selectbox(
            "Sala",
            list(SALAS.keys())
        )

    with col2:

        ano = st.text_input(
            "Ano",
            value=str(datetime.now().year)
        )

    arquivos = st.file_uploader(
        "PDFs",
        type=["pdf"],
        accept_multiple_files=True
    )

    if st.button("PROCESSAR"):

        if arquivos:

            planilha = SALAS[sala]

            aba = obter_aba(planilha, ano)

            for arquivo in arquivos:

                dados = extrair_pdf(arquivo)

                salvar_planilha(aba, dados)

            st.session_state.sala = sala
            st.session_state.ano = ano
            st.session_state.pagina = "dashboard"

            st.rerun()

# =========================================================
# DASHBOARD
# =========================================================

else:

    sidebar = st.sidebar

    sidebar.title("Dashboards")

    sala = sidebar.selectbox(
        "Sala",
        list(SALAS.keys()),
        index=list(SALAS.keys()).index(
            st.session_state.sala
        )
    )

    ano = sidebar.text_input(
        "Ano",
        value=st.session_state.ano
    )

    if sidebar.button("Ir para Dashboard"):

        st.session_state.sala = sala
        st.session_state.ano = ano

        st.rerun()

    if sidebar.button("Voltar para Upload"):

        st.session_state.pagina = "upload"

        st.rerun()

    planilha = SALAS[st.session_state.sala]

    aba = obter_aba(
        planilha,
        st.session_state.ano
    )

    df = carregar_df(aba)

    if df.empty:

        st.warning("Nenhum dado.")

        st.stop()

    alunos = df["Aluno"].unique().tolist()

    if st.session_state.aluno_idx >= len(alunos):
        st.session_state.aluno_idx = 0

    aluno = alunos[st.session_state.aluno_idx]

    df_aluno = df[
        df["Aluno"] == aluno
    ]

    # =====================================================
    # TOPO
    # =====================================================

    st.title(
        f"{st.session_state.sala} - {st.session_state.ano}"
    )

    st.header(aluno)

    # =====================================================
    # CARDS
    # =====================================================

    c1, c2, c3 = st.columns(3)

    with c1:

        mat = ""

        if "Matrícula" in df_aluno.columns:
            mat = df_aluno["Matrícula"].iloc[0]

        st.markdown(f"""
        <div style="
            border:1px solid #ccc;
            padding:20px;
            border-radius:15px;
        ">
        <h4>Matrícula</h4>
        <p>{mat}</p>
        </div>
        """, unsafe_allow_html=True)

    with c2:

        serie = ""

        if "Série" in df_aluno.columns:
            serie = df_aluno["Série"].iloc[0]

        st.markdown(f"""
        <div style="
            border:1px solid #ccc;
            padding:20px;
            border-radius:15px;
        ">
        <h4>Série</h4>
        <p>{serie}</p>
        </div>
        """, unsafe_allow_html=True)

    with c3:

        qtd = len(df_aluno)

        st.markdown(f"""
        <div style="
            border:1px solid #ccc;
            padding:20px;
            border-radius:15px;
        ">
        <h4>Disciplinas</h4>
        <p>{qtd}</p>
        </div>
        """, unsafe_allow_html=True)

    st.divider()

    # =====================================================
    # DISCIPLINAS
    # =====================================================

    disciplinas = df_aluno["Disciplina"].tolist()

    disciplina = st.selectbox(
        "Disciplina",
        disciplinas
    )

    linha = df_aluno[
        df_aluno["Disciplina"] == disciplina
    ].iloc[0]

    # =====================================================
    # PEGAR APENAS VALORES NUMÉRICOS
    # =====================================================

    valores = []

    nomes = []

    for coluna in df_aluno.columns:

        if "Valor" in coluna:

            try:

                valor = float(
                    str(linha[coluna]).replace(",", ".")
                )

                valores.append(valor)

                nomes.append(coluna)

            except:
                pass

    # =====================================================
    # GRÁFICO
    # =====================================================

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
    # OBSERVAÇÕES
    # =====================================================

    st.subheader("Observações")

    obs = st.text_area(
        "",
        value=str(linha["Observações"])
    )

    if st.button("Salvar Observação"):

        registros = aba.get_all_records()

        df_edit = pd.DataFrame(registros)

        idx = df_edit[
            (df_edit["Aluno"] == aluno)
            &
            (df_edit["Disciplina"] == disciplina)
        ].index

        if len(idx) > 0:

            df_edit.at[idx[0], "Observações"] = obs

            aba.clear()

            aba.update(
                [df_edit.columns.values.tolist()]
                +
                df_edit.values.tolist()
            )

            st.success("Salvo")

            st.rerun()

    st.divider()

    # =====================================================
    # NAVEGAÇÃO
    # =====================================================

    n1, n2, n3 = st.columns(3)

    with n1:

        if st.button("⬅️"):

            st.session_state.aluno_idx = (
                st.session_state.aluno_idx - 1
            ) % len(alunos)

            st.rerun()

    with n2:

        novo_aluno = st.selectbox(
            "Aluno",
            alunos,
            index=st.session_state.aluno_idx
        )

        st.session_state.aluno_idx = alunos.index(
            novo_aluno
        )

    with n3:

        if st.button("➡️"):

            st.session_state.aluno_idx = (
                st.session_state.aluno_idx + 1
            ) % len(alunos)

            st.rerun()
