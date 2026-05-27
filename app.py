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

# =========================================================
# CSS
# =========================================================

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
    st.secrets["connections"]["gsheets"],
    scopes=SCOPES
)

client = gspread.authorize(creds)

# =========================================================
# PLANILHAS
# USE URLS REAIS
# =========================================================

PLANILHAS = {

    "Sala 1": client.open_by_url(
        "https://docs.google.com/spreadsheets/d/1AHJl32OV7dw5XoNvxCLWvdjEZCVEuuxCm91LbOk3RUI/edit?usp=sharing"
    ),

    "Sala 2": client.open_by_url(
        "https://docs.google.com/spreadsheets/d/19Vq5dinFVch39zl4ECEx97qKCsQ5HjP58SBcwrUFNUM/edit?usp=sharing"
    ),

    "Sala 3": client.open_by_url(
        "https://docs.google.com/spreadsheets/d/19BQ-zpl78NnMZTH2d9JdgtDaLE2xQblR65VgrsxaNIM/edit?usp=sharing"
    ),

    "Sala 4": client.open_by_url(
        "https://docs.google.com/spreadsheets/d/1-GUoRPAvLMGZPYbg-dwP-7C--I4ZxFI3yj7AjO62-5w/edit?usp=sharing"
    ),

    "Sala 5": client.open_by_url(
        "https://docs.google.com/spreadsheets/d/1CDTOojkHV65gqXlB7zEDJQUyJlYb-T-rLqgFiu9MTVU/edit?usp=sharing"
    ),

    "Sala 6": client.open_by_url(
        "https://docs.google.com/spreadsheets/d/1TZqPXPp0172r-x9DrZAZ9J39WUP8KxfzKk4MRe2g_yA/edit?usp=sharing"
    )
}

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
# FUNÇÃO ABA
# =========================================================

def obter_ou_criar_aba(planilha, ano):

    nome_aba = str(ano)

    try:

        aba = planilha.worksheet(nome_aba)

    except:

        aba = planilha.add_worksheet(
            title=nome_aba,
            rows=5000,
            cols=50
        )

    return aba

# =========================================================
# EXTRAÇÃO PDF
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

            # =================================================
            # METADADOS
            # =================================================

            for linha in linhas:

                linha_limpa = linha.strip()

                if "Aluno" in linha_limpa:

                    partes = linha_limpa.split(":")

                    if len(partes) > 1:
                        aluno = partes[1].strip()

                if (
                    "Matrícula" in linha_limpa
                    or
                    "Matricula" in linha_limpa
                ):

                    nums = re.findall(r"\d+", linha_limpa)

                    if nums:
                        matricula = nums[0]

                if (
                    "Série" in linha_limpa
                    or
                    "Serie" in linha_limpa
                ):

                    partes = linha_limpa.split(":")

                    if len(partes) > 1:
                        serie = partes[1].strip()

            if not aluno:
                aluno = arquivo.name.replace(".pdf", "")

            # =================================================
            # LINHAS COM NÚMEROS
            # =================================================

            for linha in linhas:

                numeros = re.findall(
                    r"\d+[.,]?\d*",
                    linha
                )

                numeros_convertidos = []

                for n in numeros:

                    try:
                        numeros_convertidos.append(
                            float(
                                n.replace(",", ".")
                            )
                        )

                    except:
                        pass

                # ignora linhas sem números úteis
                if len(numeros_convertidos) < 2:
                    continue

                # tenta descobrir nome da disciplina
                texto_sem_numeros = re.sub(
                    r"\d+[.,]?\d*",
                    "",
                    linha
                ).strip()

                # ignora linhas vazias
                if not texto_sem_numeros:
                    continue

                registro = {

                    "Nº Chamada": numero_chamada,

                    "Aluno": aluno,

                    "Matrícula": matricula,

                    "Série": serie,

                    "Disciplina": texto_sem_numeros,

                    "Observações": ""
                }

                # adiciona valores dinamicamente
                for i, valor in enumerate(
                    numeros_convertidos
                ):

                    registro[f"Valor {i+1}"] = valor

                registros.append(registro)

        except Exception as e:

            st.error(
                f"Erro no PDF {arquivo.name}: {e}"
            )

    return pd.DataFrame(registros)

# =========================================================
# UPDATE PLANILHA
# =========================================================

def atualizar_planilha(aba, novos_dados):

    dados_existentes = aba.get_all_records()

    if dados_existentes:

        df_existente = pd.DataFrame(
            dados_existentes
        )

    else:

        df_existente = pd.DataFrame()

    if not df_existente.empty:

        for _, row in novos_dados.iterrows():

            if (
                "Aluno" in df_existente.columns
                and
                "Disciplina" in df_existente.columns
            ):

                df_existente = df_existente[
                    ~(
                        (
                            df_existente["Aluno"]
                            ==
                            row["Aluno"]
                        )
                        &
                        (
                            df_existente["Disciplina"]
                            ==
                            row["Disciplina"]
                        )
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
        [
            df_final.columns.values.tolist()
        ]
        +
        df_final.values.tolist()
    )

# =========================================================
# CARREGAR DF
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

if st.sidebar.button("Upload"):
    st.session_state.tela = "upload"

if st.sidebar.button("Dashboard"):
    st.session_state.tela = "dashboard"

# =========================================================
# PLANILHA
# =========================================================

planilha = PLANILHAS[sala]

aba = obter_ou_criar_aba(
    planilha,
    ano
)

# =========================================================
# UPLOAD
# =========================================================

if st.session_state.tela == "upload":

    st.title("Upload PDFs")

    arquivos = st.file_uploader(
        "Envie os PDFs",
        type=["pdf"],
        accept_multiple_files=True
    )

    if st.button("PROCESSAR"):

        if arquivos:

            with st.spinner(
                "Lendo PDFs..."
            ):

                novos_dados = extrair_dados_pdf(
                    arquivos
                )

                if not novos_dados.empty:

                    atualizar_planilha(
                        aba,
                        novos_dados
                    )

                    st.success(
                        "Dados atualizados!"
                    )

                else:

                    st.warning(
                        "Nenhum dado encontrado."
                    )

# =========================================================
# DASHBOARD
# =========================================================

else:

    df = carregar_dataframe(aba)

    st.title(f"{sala} - {ano}")

    if df.empty:

        st.warning("Sem dados.")

        st.stop()

    alunos_lista = (
        df["Aluno"]
        .dropna()
        .unique()
        .tolist()
    )

    if not alunos_lista:

        st.warning("Sem alunos.")

        st.stop()

    if (
        st.session_state.aluno_idx
        >=
        len(alunos_lista)
    ):

        st.session_state.aluno_idx = 0

    aluno_nome = alunos_lista[
        st.session_state.aluno_idx
    ]

    df_aluno = df[
        df["Aluno"] == aluno_nome
    ]

    # =====================================================
    # TOPO
    # =====================================================

    st.subheader(aluno_nome)

    # =====================================================
    # DISCIPLINAS
    # =====================================================

    disciplinas = (
        df_aluno["Disciplina"]
        .dropna()
        .unique()
        .tolist()
    )

    cols = st.columns(4)

    for i, disc in enumerate(disciplinas):

        with cols[i % 4]:

            if st.button(
                disc,
                key=disc
            ):

                st.session_state.disciplina_ativa = disc

                st.rerun()

    if (
        st.session_state.disciplina_ativa
        is None
    ):

        st.session_state.disciplina_ativa = disciplinas[0]

    df_disc = df_aluno[
        df_aluno["Disciplina"]
        ==
        st.session_state.disciplina_ativa
    ]

    linha = df_disc.iloc[0]

    # =====================================================
    # VALORES
    # =====================================================

    valores = []

    labels = []

    for col in df.columns:

        if "Valor" in col:

            try:

                val = float(linha[col])

                valores.append(val)

                labels.append(col)

            except:
                pass

    if valores:

        fig = px.line(
            x=labels,
            y=valores,
            markers=True
        )

        st.plotly_chart(
            fig,
            use_container_width=True
        )

    # =====================================================
    # OBS
    # =====================================================

    obs = str(
        linha["Observações"]
    )

    nova_obs = st.text_area(
        "Observações",
        value=obs
    )

    if st.button("Salvar Observação"):

        idx = df[
            (
                df["Aluno"]
                ==
                aluno_nome
            )
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
                [
                    df.columns.values.tolist()
                ]
                +
                df.values.tolist()
            )

            st.success("Salvo!")

            st.rerun()

    # =====================================================
    # NAVEGAÇÃO
    # =====================================================

    st.divider()

    b1, b2, b3 = st.columns(3)

    with b1:

        if st.button("⬅️"):

            st.session_state.aluno_idx -= 1

            if st.session_state.aluno_idx < 0:

                st.session_state.aluno_idx = (
                    len(alunos_lista) - 1
                )

            st.rerun()

    with b2:

        escolha = st.selectbox(
            "Aluno",
            alunos_lista,
            index=st.session_state.aluno_idx
        )

        novo_idx = alunos_lista.index(
            escolha
        )

        if (
            novo_idx
            !=
            st.session_state.aluno_idx
        ):

            st.session_state.aluno_idx = novo_idx

            st.rerun()

    with b3:

        if st.button("➡️"):

            st.session_state.aluno_idx += 1

            if (
                st.session_state.aluno_idx
                >=
                len(alunos_lista)
            ):

                st.session_state.aluno_idx = 0

            st.rerun()
