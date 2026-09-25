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
    "ILPR", "MAIN", "ININ", "LDPR", "RDCO", "LPWE", "SOPE", "INSO", "IPRE",
    "BDDA", "PSCO", "PRIN", "CNVI", "SDRE", "ASRE", "RSFI", "GCLI", "ELET",
    "DCAD", "CAUT", "PROG", "PCOE", "EDIG", "PRI1", "ELIN", "CISUT", "INTI",
    "MAPI", "CNCM", "CLPR", "REPI", "HIEP", "MIMP", "PRI2"
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


# FUNÇÃO APERFEIÇOADA DE EXTRAÇÃO DE DADOS DOS PDFS
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
        for pagina in leitorPdf.pages:
            textoCompleto += pagina.extract_text() + "\n"

        # IDENTIFICAÇÃO DO ALUNO
        nomeAluno = "Não Identificado"
        matriculaAluno = "Não Identificada"
        serieAluno = "Não Identificada"
        freqGlobal = 100.0

        for linha in textoCompleto.split("\n"):
            if "Aluno(a):" in linha or "Aluno:" in linha:
                nomeAluno = linha.split(":")[-1].strip()
            elif "Matrícula:" in linha:
                buscaMat = re.search(r"BT\d+", linha, re.IGNORECASE)
                if buscaMat:
                    matriculaAluno = buscaMat.group(0).strip()
            elif "Curso:" in linha or "Turma:" in linha:
                if "2026" in linha or "TÉCNICO" in linha:
                    serieAluno = linha.split(":")[-1].strip()
            elif "Frequência:" in linha:
                buscaFreq = re.search(r"(\d+[\.,]?\d*)\s*%", linha)
                if buscaFreq:
                    freqGlobal = float(buscaFreq.group(1).replace(",", "."))

        if nomeAluno == "Não Identificado" or not nomeAluno:
            nomeAluno = arquivo.name.replace(".pdf", "").replace("Boletim", "").replace("_", " ").strip()

        if ultimoAlunoLido != "" and nomeAluno != ultimoAlunoLido:
            numeroChamada += 1
        ultimoAlunoLido = nomeAluno

        # EXTRAÇÃO DE DADOS DO NAPNE
        necEspeciais = "Não"
        tipoNecEspecial = "-"
        transtorno = "Não"
        tipoTranstorno = "-"
        superdotacao = "Não"
        tipoSuperdotacao = "-"

        mPne = re.search(r"Portador\(a\)\s+de\s+Necessidades\s+Especiais\s+(Sim|Não)", textoCompleto, re.IGNORECASE)
        if mPne: necEspeciais = mPne.group(1)
        mTipPne = re.search(r"Tipo\s+de\s+Necessidade\s+Especial\s+-?\s*([^\n]+)", textoCompleto, re.IGNORECASE)
        if mTipPne: tipoNecEspecial = mTipPne.group(1).strip()

        mTrans = re.search(r"Portador\(a\)\s+de\s+Transtorno\s+(Sim|Não)", textoCompleto, re.IGNORECASE)
        if mTrans: transtorno = mTrans.group(1)
        mTipTrans = re.search(r"Tipo\s+de\s+Transtorno\s+-?\s*([^\n]+)", textoCompleto, re.IGNORECASE)
        if mTipTrans: tipoTranstorno = mTipTrans.group(1).strip()

        mSuper = re.search(r"Portador\(a\)\s+de\s+Superdotação\s+(Sim|Não)", textoCompleto, re.IGNORECASE)
        if mSuper: superdotacao = mSuper.group(1)
        mTipSuper = re.search(r"Superdotação\s+-?\s*([^\n]+)", textoCompleto, re.IGNORECASE)
        if mTipSuper: tipoSuperdotacao = mTipSuper.group(1).strip()

        mapaNapneTemporario[nomeAluno.strip().upper()] = {
            "nec": necEspeciais, "tipNec": tipoNecEspecial,
            "trans": transtorno, "tipTrans": tipoTranstorno,
            "super": superdotacao, "tipSuper": tipoSuperdotacao
        }

        # EXTRAÇÃO DAS DISCIPLINAS E NOTAS
        # Padrão para capturar a linha da disciplina (ex: INT.11287 (BTVPOR3) - LÍNGUA PORTUGUESA 3)
        linhasPadrao = re.findall(r"([A-Z]{3,4}\.\d{4,5}\s*\([A-Z0-9]+\)\s*-\s*[^0-9\n]+)([\s\S]*?)(?=[A-Z]{3,4}\.\d{4,5}\s*\([A-Z0-9]+\)|Total|Este documento|$)", textoCompleto)

        for matchDisci in linhasPadrao:
            nomeDisciplina = matchDisci[0].strip()
            blocoTexto = matchDisci[1].strip()

            # Captura todas as notas (ex: 10,00, 9.50, 8.5) no bloco da disciplina
            valoresEncontrados = re.findall(r"\b(\d{1,2}[\.,]\d{1,2})\b", blocoTexto)
            notasFloat = []
            for v in valoresEncontrados:
                try:
                    val = float(v.replace(",", "."))
                    if val <= 10.0:  # Descarta cargas horárias (ex: 60.0, 80.0)
                        notasFloat.append(val)
                except ValueError:
                    pass

            # Atribui aos bimestres
            b1 = notasFloat[0] if len(notasFloat) > 0 else None
            b2 = notasFloat[1] if len(notasFloat) > 1 else None
            b3 = notasFloat[2] if len(notasFloat) > 2 else None
            b4 = notasFloat[3] if len(notasFloat) > 3 else None

            notasValidas = [n for n in [b1, b2, b3, b4] if n is not None]
            mediaFinal = round(sum(notasValidas) / len(notasValidas), 2) if notasValidas else 0.0

            # Identificação de Núcleo Técnico ou Comum
            tecnico = any(kw in nomeDisciplina.upper() for kw in tecnicas)
            nucleo = "Técnico" if tecnico else "Comum"

            dadosFinais.append({
                "Nº Chamada": int(numeroChamada),
                "Aluno": nomeAluno,
                "Matrícula": matriculaAluno,
                "Série": serieAluno,
                "Disciplina": nomeDisciplina,
                "1º BI": b1,
                "2º BI": b2,
                "3º BI": b3,
                "4º BI": b4,
                "Média Final": mediaFinal,
                "Freq. Final": freqGlobal,
                "Núcleo": nucleo,
                "Observações": "",
                "Necessidades Especiais": necEspeciais,
                "Tipo de Necessidade Especial": tipoNecEspecial,
                "Transtorno": transtorno,
                "Tipo de Transtorno": tipoTranstorno,
                "Superdotação": superdotacao,
                "Tipo de Superdotação": tipoSuperdotacao,
            })

    # Atualiza dados NAPNE cruzados
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


# TELA 1: UPLOAD DE BOLETINS
if not st.session_state.dadosCarregados:
    st.title("Upload de PDFs do Conselho de Classe")
    st.subheader("Selecione a turma e envie os relatórios para gerar o JSON e atualizar a planilha.")

    salaSelecionada = st.selectbox("Selecione a Sala/Turma:", list(DICIONARIO_SALAS.keys()))
    st.session_state.salaAtiva = salaSelecionada

    arquivosEnviados = st.file_uploader(
        "Envie os PDFs dos boletins dos alunos:",
        type=["pdf"],
        accept_multiple_files=True,
        key=f"uploader_{salaSelecionada}",
    )

    if st.button("PROCESSAR E ATUALIZAR DASHBOARD", type="primary"):
        if arquivosEnviados:
            with st.spinner("Processando PDFs, atualizando Planilha e gerando JSON..."):
                BDNovo = extrairDados(arquivosEnviados)

                if not BDNovo.empty:
                    linkSalaAtiva = DICIONARIO_SALAS[salaSelecionada]
                    df_atual = conn.read(spreadsheet=linkSalaAtiva)
                    df_final = pd.concat([df_atual, BDNovo], ignore_index=True)
                    df_final = df_final.drop_duplicates(subset=["Aluno", "Disciplina"], keep="last")
                    
                    conn.update(spreadsheet=linkSalaAtiva, data=df_final)

                    # ATIVIDADE 1: Salva o dicionário gerado em JSON
                    dicionario_dados = df_final.to_dict(orient="records")
                    with open("dados_alunos.json", "w", encoding="utf-8") as f:
                        json.dump(dicionario_dados, f, ensure_ascii=False, indent=4)

                    st.session_state.dadosCarregados = True
                    st.success("Planilha atualizada e dados_alunos.json gerado com sucesso!")
                    st.rerun()
                else:
                    st.error("Nenhum dado estruturado pôde ser extraído.")
        else:
            st.error("Selecione ao menos um arquivo PDF.")

# TELA 2: DASHBOARD (HTML / JS INTEGRADO - ATIVIDADE 2)
else:
    st.sidebar.write(f"Turma Ativa: **{st.session_state.salaAtiva}**")

    dados_para_html = []
    if os.path.exists("dados_alunos.json"):
        with open("dados_alunos.json", "r", encoding="utf-8") as f:
            dados_para_html = json.load(f)
    else:
        linkSalaAtiva = DICIONARIO_SALAS[st.session_state.salaAtiva]
        df_sheet = conn.read(spreadsheet=linkSalaAtiva, ttl="0")
        dados_para_html = df_sheet.where(pd.notnull(df_sheet), None).to_dict(orient="records")

    alunosMapeados = {}
    for item in dados_para_html:
        prontuario = str(item.get("Matrícula") or item.get("prontuario") or "BT300000").strip()

        if prontuario not in alunosMapeados:
            alunosMapeados[prontuario] = {
                "prontuario": prontuario,
                "nome": item.get("Aluno", "Aluno Desconhecido"),
                "curso": item.get("Série", "Técnico em Redes"),
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

    json_estruturado = json.dumps(list(alunosMapeados.values()), ensure_ascii=False)

    if os.path.exists("index.html"):
        with open("index.html", "r", encoding="utf-8") as f:
            html_content = f.read()

        html_injetado = html_content.replace("__DADOS_JSON_INJETADOS__", json_estruturado)

        import base64
        b64_html = base64.b64encode(html_injetado.encode('utf-8')).decode('utf-8')

        iframe_code = f"""
        <iframe 
            src="data:text/html;charset=utf-8;base64,{b64_html}"
            style="width: 100%; height: 1100px; border: none; border-radius: 8px;"
        ></iframe>
        """
        st.markdown(iframe_code, unsafe_allow_html=True)
    else:
        st.error("O arquivo 'index.html' não foi encontrado no repositório GitHub.")
