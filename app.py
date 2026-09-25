import io
import json
import os
import re
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from pypdf import PdfReader
from streamlit_gsheets import GSheetsConnection

# CONFIGURAÇÃO DA PÁGINA
st.set_page_config(
    page_title="Conselho de Classe - IFSP Boituva",
    layout="wide",
    initial_sidebar_state="expanded",
)

tecnicas = [
    "ILPR",
    "MAIN",
    "ININ",
    "LDPR",
    "RDCO",
    "LPWE",
    "SOPE",
    "INSO",
    "IPRE",
    "BDDA",
    "PSCO",
    "PRIN",
    "CNVI",
    "SDRE",
    "ASRE",
    "RSFI",
    "GCLI",
    "ELET",
    "DCAD",
    "CAUT",
    "PROG",
    "PCOE",
    "EDIG",
    "PRI1",
    "ELIN",
    "CISUT",
    "INTI",
    "MAPI",
    "CNCM",
    "CLPR",
    "REPI",
    "HIEP",
    "MIMP",
    "PRI2",
]

# CONEXÃO COM PLANILHAS
conn = st.connection("gsheets", type=GSheetsConnection)

DICIONARIO_SALAS = {
    "Redes 1": st.secrets["connections"]["gsheets"]["Redes1"],
    "Redes 2": st.secrets["connections"]["gsheets"]["Redes2"],
    "Redes 3": st.secrets["connections"]["gsheets"]["Redes3"],
    "Automação 1": st.secrets["connections"]["gsheets"]["Automacao1"],
    "Automação 2": st.secrets["connections"]["gsheets"]["Automacao2"],
    "Automação 3": st.secrets["connections"]["gsheets"]["Automacao3"],
}

# ESTADOS DE SESSÃO
if "dadosCarregados" not in st.session_state:
    st.session_state.dadosCarregados = False
if "salaAtiva" not in st.session_state:
    st.session_state.salaAtiva = "Redes 1"

# MENU LATERAL
st.sidebar.title("Conselho de Classe")
st.sidebar.markdown("---")

if st.sidebar.button("📁 Tela de Upload / Processamento", use_container_width=True):
    st.session_state.dadosCarregados = False
    st.rerun()

if st.sidebar.button("📊 Ficha do Conselho (Dashboard)", use_container_width=True):
    st.session_state.dadosCarregados = True
    st.rerun()


# FUNÇÃO DE EXTRAÇÃO DE DADOS
def extrairDados(arquivosPdf):
    dadosFinais = []
    mapaNapneTemporario = {}
    numeroChamada = 1
    ultimoAlunoLido = ""

    for arquivo in arquivosPdf:
        memoriaPdf = io.BytesIO(arquivo.getvalue())
        try:
            leitorPdf = PdfReader(memoriaPdf)
        except Exception as e:
            st.error(f"Erro ao ler o arquivo {arquivo.name}: {e}")
            continue

        textoCompleto = ""
        for paginaIndex, pagina in enumerate(leitorPdf.pages):
            textoCompleto += pagina.extract_text() + "\n"
            textoPagina = textoCompleto
            nomeNestaPagina = "Não Identificado"

            for linha in textoPagina.split("\n"):
                if "Aluno" in linha or "Nome" in linha:
                    partes = linha.split(":")
                    if len(partes) > 1:
                        valNome = partes[1].strip()
                    else:
                        valNome = (
                            linha.replace("Aluno", "")
                            .replace("Nome", "")
                            .strip()
                        )
                    nomeNestaPagina = re.sub(
                        r"\bMatrícula\b.*", "", valNome, flags=re.IGNORECASE
                    ).strip()

            if (
                nomeNestaPagina == "Não Identificado"
                or not nomeNestaPagina.strip()
            ):
                nomeNestaPagina = arquivo.name.replace(".pdf", "").strip()

            if (
                ultimoAlunoLido != ""
                and nomeNestaPagina != ultimoAlunoLido
            ):
                numeroChamada += 1

            ultimoAlunoLido = nomeNestaPagina
            textoCompleto = textoPagina

        linhas = textoCompleto.split("\n")
        textoNapne = textoCompleto.replace("\n", " ")
        nomeAluno = "Não Identificado"
        matriculaAluno = "Não Identificada"
        serieAluno = "Não Identificada"

        necEspeciais = "Não"
        tipoNecEspecial = "-"
        transtorno = "Não"
        tipoTranstorno = "-"
        superdotacao = "Não"
        tipoSuperdotacao = "-"

        for linha in linhas:
            if "Aluno" in linha or "Nome" in linha:
                partes = linha.split(":")
                if len(partes) > 1:
                    valNome = partes[1].strip()
                else:
                    valNome = (
                        linha.replace("Aluno", "").replace("Nome", "").strip()
                    )
                nomeAluno = re.sub(
                    r"\bMatrícula\b.*", "", valNome, flags=re.IGNORECASE
                ).strip()

            for termo in ["matrícula", "matricula", "prontuário", "prontuario"]:
                if termo in linha.lower():
                    buscaBT = re.search(
                        r"cula:\s*(.{9})", linha, re.IGNORECASE
                    )
                    if buscaBT:
                        matriculaAluno = buscaBT.group(1).strip()
                        break

            if (
                "Série" in linha
                or "Serie" in linha
                or "Ano" in linha
                or "Turma" in linha
            ):
                partes = linha.split(":")
                if len(partes) > 1:
                    serieAluno = partes[1].strip()[:27]

        match = re.search(
            r"Portador\(a\)\s+de\s+Necessidades\s+Especiais\s+(Sim|Não)",
            textoNapne,
            re.IGNORECASE,
        )
        if match:
            necEspeciais = match.group(1)

        match = re.search(
            r"Tipo\s+de\s+Necessidade\s+Especial\s+-?\s*(.+?)\s*(?=Portador\(a\)|$)",
            textoNapne,
            re.IGNORECASE,
        )
        if match:
            tipoNecEspecial = match.group(1)

        match = re.search(
            r"Portador\(a\)\s+de\s+Transtorno\s+(Sim|Não)",
            textoNapne,
            re.IGNORECASE,
        )
        if match:
            transtorno = match.group(1)

        match = re.search(
            r"Tipo\s+de\s+Transtorno\s+-?\s*(.+?)\s*(?=Portador\(a\)|$)",
            textoNapne,
            re.IGNORECASE,
        )
        if match:
            tipoTranstorno = match.group(1)

        match = re.search(
            r"Portador\(a\)\s+de\s+Superdotação\s+(Sim|Não)",
            textoNapne,
            re.IGNORECASE,
        )
        if match:
            superdotacao = match.group(1)

        match = re.search(
            r"Superdotação\s+-?\s*(.+?)\s*$", textoNapne, re.IGNORECASE
        )
        if match:
            tipoSuperdotacao = match.group(1)

        if nomeAluno == "Não Identificado" or not nomeAluno.strip():
            nomeAluno = (
                arquivo.name.replace(".pdf", "")
                .replace("Boletim", "")
                .replace("_", " ")
                .strip()
            )

        mapeamentoDisciplinas = {}

        for linha in linhas:
            encontrou = False
            for p in [
                "Notas das etapas",
                "Faltas nas etapas",
                "Diário",
                "Disciplina",
                "Total",
                "Este documento",
            ]:
                if p in linha:
                    encontrou = True
                    break
            if encontrou:
                continue

            linhaLimpa = re.sub(r"^\d{5,6}\s+", "", linha.strip())
            if not re.search(
                r"[A-Z]{3,4}\.\d{4,5}|\([A-Z0-9]{5,}\)", linhaLimpa
            ):
                continue

            tokens = linhaLimpa.split()
            partesTexto = []
            partesDados = []
            passouDaMateria = False

            for token in tokens:
                if (
                    "," in token and token.replace(",", "").isdigit()
                ) and not passouDaMateria:
                    passouDaMateria = True
                if not passouDaMateria:
                    partesTexto.append(token)
                else:
                    partesDados.append(token)

            nomeDisciplina = " ".join(partesTexto).strip()
            if not nomeDisciplina or len(partesDados) < 5:
                continue

            calculoFreq = 100.0
            for token in tokens:
                if "%" in token:
                    try:
                        calculoFreq = float(
                            token.replace("%", "").replace(",", ".")
                        )
                    except ValueError:
                        pass
                    break

            tokensFiltrados = []
            for tok in partesDados:
                if (
                    tok
                    in [
                        "Cursando",
                        "(Aguarda",
                        "Carga",
                        "Horária)",
                        "Horária",
                        "Aprovado",
                        "Retido",
                    ]
                    or "%" in tok
                ):
                    continue
                if tok == "-" or tok.replace(",", ".").replace(".", "", 1).isdigit():
                    tokensFiltrados.append(tok)

            dadosTabela = tokensFiltrados[4:]

            notas = [None, None, None, None]
            faltas = [0.0, 0.0, 0.0, 0.0]

            pagDado = 0
            for etapa in range(4):
                if pagDado < len(dadosTabela):
                    valNota = dadosTabela[pagDado].replace(",", ".")
                    if valNota.replace(".", "", 1).isdigit():
                        notas[etapa] = float(valNota)
                    pagDado += 1
                if pagDado < len(dadosTabela):
                    valFalta = dadosTabela[pagDado]
                    if valFalta.isdigit():
                        faltas[etapa] = float(valFalta)
                    pagDado += 1

            mediaFinal = 0.0
            notasValidas = [n for n in notas if n is not None]
            if notasValidas:
                mediaFinal = sum(notasValidas) / len(notasValidas)

            if len(nomeDisciplina) > 3:
                mapeamentoDisciplinas[nomeDisciplina] = {
                    "notas": notas,
                    "faltas": faltas,
                    "mediaFinal": mediaFinal,
                    "freqFinal": calculoFreq,
                }

        for nomeDisp, blocos in mapeamentoDisciplinas.items():
            tecnico = any(kw in nomeDisp.upper() for kw in tecnicas)
            nucleo = "Técnico" if tecnico else "Comum"

            dadosFinais.append(
                {
                    "Nº Chamada": int(numeroChamada),
                    "Aluno": nomeAluno,
                    "Matrícula": matriculaAluno,
                    "Série": serieAluno,
                    "Disciplina": nomeDisp,
                    "1º BI": blocos["notas"][0],
                    "2º BI": blocos["notas"][1],
                    "3º BI": blocos["notas"][2],
                    "4º BI": blocos["notas"][3],
                    "Média Final": blocos["mediaFinal"],
                    "Freq. Final": blocos["freqFinal"],
                    "Núcleo": nucleo,
                    "Observações": "",
                    "Necessidades Especiais": necEspeciais,
                    "Tipo de Necessidade Especial": tipoNecEspecial,
                    "Transtorno": transtorno,
                    "Tipo de Transtorno": tipoTranstorno,
                    "Superdotação": superdotacao,
                    "Tipo de Superdotação": tipoSuperdotacao,
                }
            )

        if "ultimoNomeVisto" not in locals():
            ultimoNomeVisto = nomeAluno

        if nomeAluno != ultimoNomeVisto:
            numeroChamada += 1
            ultimoNomeVisto = nomeAluno

        if nomeAluno and nomeAluno != "Não Identificado":
            mapaNapneTemporario[nomeAluno.strip().upper()] = {
                "nec": necEspeciais,
                "tipNec": tipoNecEspecial,
                "trans": transtorno,
                "tipTrans": tipoTranstorno,
                "super": superdotacao,
                "tipSuper": tipoSuperdotacao,
            }

    for dado in dadosFinais:
        alunoAlvo = dado["Aluno"].strip().upper()
        if alunoAlvo in mapaNapneTemporario:
            info = mapaNapneTemporario[alunoAlvo]
            dado["Necessidades Especiais"] = info["nec"]
            dado["Tipo de Necessidade Especial"] = info["tipNec"]
            dado["Transtorno"] = info["trans"]
            dado["Tipo de Transtorno"] = info["tipTrans"]
            dado["Superdotação"] = info["super"]
            dado["Tipo de Superdotação"] = info["tipSuper"]

    return pd.DataFrame(dadosFinais)


# TELA 1: UPLOAD DE BOLETIMS EM PDF
if not st.session_state.dadosCarregados:
    st.title("Upload de PDFs do Conselho de Classe")
    st.subheader(
        "Selecione a turma e envie os relatórios para gerar o JSON e atualizar a planilha."
    )

    salaSelecionada = st.selectbox(
        "Selecione a Sala/Turma:", list(DICIONARIO_SALAS.keys())
    )
    st.session_state.salaAtiva = salaSelecionada

    arquivosEnviados = st.file_uploader(
        "Envie os PDFs dos boletins dos alunos:",
        type=["pdf"],
        accept_multiple_files=True,
        key=f"uploader_{salaSelecionada}",
    )

    if st.button("PROCESSAR E ATUALIZAR DASHBOARD", type="primary"):
        if arquivosEnviados:
            with st.spinner(
                "Processando PDFs, atualizando Planilha e gerando JSON..."
            ):
                BDNovo = extrairDados(arquivosEnviados)

                if not BDNovo.empty:
                    # 1. Salva no Google Sheets
                    linkSalaAtiva = DICIONARIO_SALAS[salaSelecionada]
                    df_atual = conn.read(spreadsheet=linkSalaAtiva)
                    df_final = pd.concat([df_atual, BDNovo], ignore_index=True)
                    df_final = df_final.drop_duplicates(
                        subset=["Aluno", "Disciplina"], keep="last"
                    )
                    conn.update(spreadsheet=linkSalaAtiva, data=df_final)

                    # 2. ATIVIDADE 1: Salva o dicionário gerado no arquivo JSON
                    dicionario_dados = df_final.to_dict(orient="records")
                    with open("dados_alunos.json", "w", encoding="utf-8") as f:
                        json.dump(
                            dicionario_dados, f, ensure_ascii=False, indent=4
                        )

                    st.session_state.dadosCarregados = True
                    st.success(
                        "Planilha atualizada e dados_alunos.json gerado com sucesso!"
                    )
                    st.rerun()
                else:
                    st.error("Nenhum dado estruturado pôde ser extraído.")
        else:
            st.error("Selecione ao menos um arquivo PDF.")

# TELA 2: DASHBOARD (HTML / JS INTEGRADO)
else:
    st.sidebar.write(f"Turma Ativa: **{st.session_state.salaAtiva}**")

    # 1. Lê os dados do arquivo JSON gerado ou carrega da planilha
    dados_para_html = []
    if os.path.exists("dados_alunos.json"):
        with open("dados_alunos.json", "r", encoding="utf-8") as f:
            dados_para_html = json.load(f)
    else:
        linkSalaAtiva = DICIONARIO_SALAS[st.session_state.salaAtiva]
        df_sheet = conn.read(spreadsheet=linkSalaAtiva, ttl="0")
        # Substitui NaN por None para gerar JSON válido sem erros no JS
        dados_para_html = df_sheet.where(pd.notnull(df_sheet), None).to_dict(orient="records")

    # 2. Agrupa e estrutura por aluno para o JavaScript
    alunosMapeados = {}
    for item in dados_para_html:
        prontuario = str(item.get("Matrícula") or item.get("prontuario") or "BT300000").strip()
        
        if prontuario not in alunosMapeados:
            alunosMapeados[prontuario] = {
                "prontuario": prontuario,
                "nome": item.get("Aluno", "Aluno Desconhecido"),
                "curso": item.get("Série", "Técnico em Informática"),
                "turma": st.session_state.salaAtiva,
                "frequencia": float(item.get("Freq. Final") or 100),
                "napne": (
                    str(item.get("Necessidades Especiais", "")).strip().lower() == "sim"
                    or str(item.get("Transtorno", "")).strip().lower() == "sim"
                ),
                "pneInfo": f"PNE: {item.get('Tipo de Necessidade Especial') or '-'} | Transtorno: {item.get('Tipo de Transtorno') or '-'}",
                "acoesNapne": [],
                "deliberacao": str(item.get("Observações", "")) if item.get("Observações") and str(item.get("Observações")).lower() != "nan" else "",
                "disciplinas": []
            }

        # Função auxiliar para tratar notas numéricas ou manter null
        def tratar_nota(v):
            if v is None: return None
            try: return float(str(v).replace(',', '.'))
            except ValueError: return None

        alunosMapeados[prontuario]["disciplinas"].append({
            "nome": item.get("Disciplina", "Disciplina"),
            "b1": tratar_nota(item.get("1º BI")),
            "b2": tratar_nota(item.get("2º BI")),
            "b3": tratar_nota(item.get("3º BI")),
            "b4": tratar_nota(item.get("4º BI")),
            "faltas": 0
        })

    # Converte o dicionário Python final para uma string JSON que o JS lê perfeitamente
    json_estruturado = json.dumps(list(alunosMapeados.values()), ensure_ascii=False)

    # 3. Renderiza o HTML injetando a variável bancoAlunos
    if os.path.exists("index.html"):
        with open("index.html", "r", encoding="utf-8") as f:
            html_content = f.read()

        html_injetado = html_content.replace("__DADOS_JSON_INJETADOS__", json_estruturado)
        components.html(html_injetado, height=1050, scrolling=True)
    else:
        st.error("O arquivo 'index.html' não foi encontrado no repositório GitHub.")
