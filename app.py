import streamlit as st
import pandas as pd
import plotly.express as px
from pypdf import PdfReader
import gspread
from google.oauth2.service_account import Credentials
import re

# =========================================================
# CONFIG
# =========================================================

st.set_page_config(
    page_title="Dashboard Acadêmico",
    layout="wide"
)

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
    border-radius: 8px;
}

</style>
""", unsafe_allow_html=True)

# =========================================================
# GOOGLE AUTH
# =========================================================

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets"
]

creds = Credentials.from_service_account_info(
    st.secrets["connections.gsheets"],
    scopes=SCOPES
)

client = gspread.authorize(creds)

# =========================================================
# PLANILHAS
# =========================================================

PLANILHAS = {
    "Sala 1": client.open("Sala 1"),
    "Sala 2": client.open("Sala 2"),
    "Sala 3": client.open("Sala 3"),
    "Sala 4": client.open("Sala 4"),
    "Sala 5": client.open("Sala 5"),
    "Sala 6": client.open("Sala 6"),
}

# =========================================================
# DISCIPLINAS
# =========================================================

DISCIPLINAS = [
    "Matemática",
    "Português",
    "História",
    "Geografia",
    "Biologia",
    "Física",
    "Química",
    "ILPR",
    "ININ"
]

# =========================================================
# SESSION
# =========================================================

if "tela" not in st.session_state:
    st.session_state.tela = "dashboard"

if "aluno_idx" not in st.session_state:
    st.session_state.aluno_idx = 0

if "disciplina_ativa" not in st.session_state:
    st.session_state.disciplina_ativa = None

# =========================================================
# FUNÇÕES
# =========================================================

def obter_ou_criar_aba(planilha, ano):

    try:
        aba = planilha.worksheet(str(ano))

    except:

        aba = planilha.add_worksheet(
            title=str(ano),
            rows=2000,
            cols=30
        )

        cabecalho = [
            "Nº Chamada",
            "Aluno",
            "Matrícula",
            "Série",
            "Disciplina",
            "1º BI",
            "2º BI",
            "3º BI",
            "4º BI",
            "Média Final",
            "Freq. Final",
            "Núcleo",
            "Observações"
        ]

        aba.append_row(cabecalho)

    return aba

# =========================================================

def extrair_dados_pdf(arquivos):

    registros = []

    for numero_chamada, arquivo in enumerate(arquivos, start=1):

        try:

            reader = PdfReader(arquivo)

            texto = ""

            for pagina in reader.pages:

                extraido = pagina.extract_text()

                if extraido:
                    texto += extraido + "\n"

            linhas = texto.split("\n")

            aluno = ""
            matricula = ""
            serie = ""

            for linha in linhas:

                linha_limpa = linha.strip()

                if "Aluno" in linha_limpa:

                    partes = linha_limpa.split(":")

                    if len(partes) > 1:
                        aluno = partes[1].strip()

                if "Matrícula" in linha_limpa or "Matricula" in linha_limpa:

                    nums = re.findall(r"\d+", linha_limpa)

                    if nums:
                        matricula = nums[0]

                if "Série" in linha_limpa or "Serie" in linha_limpa:

                    partes = linha_limpa.split(":")

                    if len(partes) > 1:
                        serie = partes[1].strip()

            if not aluno:
                aluno = arquivo.name.replace(".pdf", "")

            for linha in linhas:

                for disc in DISCIPLINAS:

                    if disc.lower() in linha.lower():

                        numeros = re.findall(
                            r"\d+[.,]?\d*",
                            linha
                        )

                        numeros = [
                            float(n.replace(",", "."))
                            for n in numeros
                        ]

                        registro = {
                            "Nº Chamada": numero_chamada,
                            "Aluno": aluno,
                            "Matrícula": matricula,
                            "Série": serie,
                            "Disciplina": disc,
                            "1º BI": numeros[0] if len(numeros) > 0 else None,
                            "2º BI": numeros[1] if len(numeros) > 1 else None,
                            "3º BI": numeros[2] if len(numeros) > 2 else None,
                            "4º BI": numeros[3] if len(numeros) > 3 else None,
                            "Média Final": numeros[4] if len(numeros) > 4 else None,
                            "Freq. Final": numeros[5] if len(numeros) > 5 else None,
                            "Núcleo": "Técnico" if disc in ["ILPR", "ININ"] else "Comum",
                            "Observações": ""
                        }

                        registros.append(registro)

        except Exception as e:

            st.error(f"Erro no PDF {arquivo.name}: {e}")

    return pd.DataFrame(registros)

# =========================================================

def atualizar_planilha(aba, novos_dados):

    dados_existentes = aba.get_all_records()

    if dados_existentes:
        df_existente = pd.DataFrame(dados_existentes)
    else:
        df_existente = pd.DataFrame()

    if not df_existente.empty:

        for _, row in novos_dados.iterrows():

            df_existente = df_existente[
                ~(
                    (df_existente["Aluno"] == row["Aluno"]) &
                    (df_existente["Disciplina"] == row["Disciplina"])
                )
            ]

        df_final = pd.concat(
            [df_existente, novos_dados],
            ignore_index=True
        )

    else:
        df_final = novos_dados

    df_final = df_final.fillna("")

    aba.clear()

    aba.update(
        [df_final.columns.values.tolist()] +
        df_final.values.tolist()
    )

# =========================================================

def carregar_dataframe(aba):

    dados = aba.get_all_records()

    if not dados:
        return pd.DataFrame()

    return pd.DataFrame(dados)

# =========================================================
# SIDEBAR
# =========================================================

st.sidebar.title("Dashboard")

sala = st.sidebar.selectbox(
    "Sala",
    list(PLANILHAS.keys())
)

ano = st.sidebar.selectbox(
    "Ano",
    [2026, 2027, 2028, 2029]
)

if st.sidebar.button("Tela Upload"):
    st.session_state.tela = "upload"

if st.sidebar.button("Tela Dashboard"):
    st.session_state.tela = "dashboard"

# =========================================================
# ABA
# =========================================================

planilha = PLANILHAS[sala]
aba = obter_ou_criar_aba(planilha, ano)

# =========================================================
# UPLOAD
# =========================================================

if st.session_state.tela == "upload":

    st.title("Upload de PDFs")

    arquivos = st.file_uploader(
        "Envie os PDFs",
        type=["pdf"],
        accept_multiple_files=True
    )

    if st.button("PROCESSAR PDFs"):

        if arquivos:

            with st.spinner("Processando..."):

                novos_dados = extrair_dados_pdf(arquivos)

                if not novos_dados.empty:

                    atualizar_planilha(
                        aba,
                        novos_dados
                    )

                    st.success("Dados atualizados!")

                else:
                    st.warning("Nenhum dado encontrado.")

# =========================================================
# DASHBOARD
# =========================================================

else:

    df = carregar_dataframe(aba)

    st.title(f"{sala} - {ano}")

    if df.empty:

        st.warning("Sem dados.")

        st.stop()

    df.columns = df.columns.str.strip()

    alunos_lista = (
        df.sort_values(by="Nº Chamada")
        ["Aluno"]
        .unique()
        .tolist()
    )

    if st.session_state.aluno_idx >= len(alunos_lista):
        st.session_state.aluno_idx = 0

    aluno_nome = alunos_lista[
        st.session_state.aluno_idx
    ]

    df_aluno = df[
        df["Aluno"] == aluno_nome
    ].copy()

    # =====================================================
    # TOPO
    # =====================================================

    t1, t2 = st.columns([1, 4])

    with t1:

        st.image(
            "https://via.placeholder.com/150",
            use_container_width=True
        )

    with t2:

        st.subheader(aluno_nome)

        c1, c2 = st.columns(2)

        matricula = (
            df_aluno["Matrícula"].iloc[0]
            if "Matrícula" in df_aluno.columns
            else ""
        )

        serie = (
            df_aluno["Série"].iloc[0]
            if "Série" in df_aluno.columns
            else ""
        )

        c1.write(f"**Matrícula:** {matricula}")
        c2.write(f"**Série:** {serie}")

    st.divider()

    # =====================================================
    # ORDEM
    # =====================================================

    ordem = st.radio(
        "Ordenar disciplinas por:",
        ["Nota", "Frequência"],
        horizontal=True
    )

    col_ref = (
        "Média Final"
        if ordem == "Nota"
        else "Freq. Final"
    )

    # =====================================================
    # COLUNAS
    # =====================================================

    m1, m2, m3, m4 = st.columns([2,3,2,2])

    # =====================================================
    # DISCIPLINAS
    # =====================================================

    with m1:

        st.write("### Disciplinas")

        df_lista = df_aluno.sort_values(
            by=col_ref,
            ascending=True
        )

        for disc in df_lista["Disciplina"].unique():

            if st.button(disc):

                st.session_state.disciplina_ativa = disc

                st.rerun()

    if (
        st.session_state.disciplina_ativa is None
        or
        st.session_state.disciplina_ativa
        not in df_aluno["Disciplina"].values
    ):

        st.session_state.disciplina_ativa = (
            df_aluno["Disciplina"].iloc[0]
        )

    df_mat = df_aluno[
        df_aluno["Disciplina"] ==
        st.session_state.disciplina_ativa
    ].iloc[0]

    # =====================================================
    # GRAFICOS
    # =====================================================

    with m2:

        st.write(
            f"### {st.session_state.disciplina_ativa}"
        )

        notas = [
            df_mat["1º BI"],
            df_mat["2º BI"],
            df_mat["3º BI"],
            df_mat["4º BI"]
        ]

        fig_n = px.line(
            x=["1º","2º","3º","4º"],
            y=notas,
            markers=True
        )

        fig_n.update_yaxes(
            range=[0,10]
        )

        st.plotly_chart(
            fig_n,
            use_container_width=True
        )

        freq = df_mat["Freq. Final"]

        if freq != "":

            fig_f = px.bar(
                x=["Frequência"],
                y=[float(freq)]
            )

            fig_f.update_yaxes(
                range=[0,100]
            )

            st.plotly_chart(
                fig_f,
                use_container_width=True
            )

    # =====================================================
    # GLOBAL
    # =====================================================

    with m3:

        st.write("### Global")

        try:

            media_global = pd.to_numeric(
                df_aluno["Média Final"],
                errors="coerce"
            ).mean()

            st.metric(
                "Média Global",
                round(media_global, 2)
            )

        except:
            st.metric("Média Global", 0)

    # =====================================================
    # OBS
    # =====================================================

    with m4:

        st.write("### Observações")

        obs = str(
            df_mat["Observações"]
        )

        nova_obs = st.text_area(
            "Nova observação",
            value=obs
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

            if not idx.empty:

                df.at[
                    idx[0],
                    "Observações"
                ] = nova_obs

                aba.clear()

                aba.update(
                    [df.columns.values.tolist()]
                    +
                    df.values.tolist()
                )

                st.success("Salvo!")

                st.rerun()

    # =====================================================
    # NAVEGAÇÃO
    # =====================================================

    st.divider()

    b1, b2, b3 = st.columns([1,1,1])

    with b1:

        if st.button("⬅️"):

            st.session_state.aluno_idx = (
                st.session_state.aluno_idx - 1
            ) % len(alunos_lista)

            st.session_state.disciplina_ativa = None

            st.rerun()

    with b2:

        escolha = st.selectbox(
            "Aluno Nº",
            list(range(1, len(alunos_lista)+1))
        )

        novo_idx = escolha - 1

        if novo_idx != st.session_state.aluno_idx:

            st.session_state.aluno_idx = novo_idx

            st.session_state.disciplina_ativa = None

            st.rerun()

    with b3:

        if st.button("➡️"):

            st.session_state.aluno_idx = (
                st.session_state.aluno_idx + 1
            ) % len(alunos_lista)

            st.session_state.disciplina_ativa = None

            st.rerun()
