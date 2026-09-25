import base64
import io
import json
import os
import re
import pandas as pd
import streamlit as st
from pypdf import PdfReader
from streamlit_gsheets import GSheetsConnection

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

conn = st.connection("gsheets", type=GSheetsConnection)

DICIONARIO_SALAS = {
    "Redes 1": st.secrets["connections"]["gsheets"]["Redes1"],
    "Redes 2": st.secrets["connections"]["gsheets"]["Redes2"],
    "Redes 3": st.secrets["connections"]["gsheets"]["Redes3"],
    "Automação 1": st.secrets["connections"]["gsheets"]["Automacao1"],
    "Automação 2": st.secrets["connections"]["gsheets"]["Automacao2"],
    "Automação 3": st.secrets["connections"]["gsheets"]["Automacao3"],
}

if "dadosCarregados" not in st.session_state:
    st.session_state.dadosCarregados = False
if "salaAtiva" not in st.session_state:
    st.session_state.salaAtiva = "Redes 1"

st.sidebar.title("Conselho de Classe")
st.sidebar.markdown("---")

if st.sidebar.button("📁 Tela de Upload / Processamento", use_container_width=True):
    st.session_state.dadosCarregados = False
    st.rerun()

if st.sidebar.button("📊 Ficha do Conselho (Dashboard)", use_container_width=True):
    st.session_state.dadosCarregados = True
    st.rerun()


# EXTRAÇÃO DE DADOS CORRIGIDA PARA O SUAP
def extrairDados(arquivosPdf):
    dadosFinais = []
    mapaNapneTemporario = {}
    numeroChamada = 1

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

        linhas = textoCompleto.split('\n')
        textoNapne = textoCompleto.replace("\n", " ")

        nomeAluno = ""
        matriculaAluno = ""
        serieAluno = ""
        freqGlobal = 100.0

        # BUSCA CORRIGIDA DE NOME NO SUAP (Considerando quebra de linha)
        for i, linha in enumerate(linhas):
            if "Aluno(a):" in linha or "Aluno:" in linha:
                # Se o nome estiver na linha seguinte
                if i + 1 < len(linhas) and not ":" in linhas[i + 1]:
                    nomeAluno = linhas[i + 1].strip()
                else:
                    nomeAluno = linha.split(":")[-1].strip()

            if "Matrícula:" in linha:
                buscaMat = re.search(r"BT\d+", linha, re.IGNORECASE)
                if buscaMat:
                    matriculaAluno = buscaMat.group(0).strip()

            if "Turma:" in linha or "Curso:" in linha:
                if "202" in linha or "TÉCNICO" in linha or "RED" in linha:
                    serieAluno = linha.split(":")[-1].strip()

            if "Frequência:" in linha:
                buscaFreq = re.search(r"(\d+[\.,]?\d*)\s*%", linha)
                if buscaFreq:
                    freqGlobal = float(buscaFreq.group(1).replace(",", "."))

        if not nomeAluno or nomeAluno == "Não Identificado":
            nomeAluno = arquivo.name.replace(".pdf", "").replace("Boletim", "").replace("_", " ").strip()

        # DADOS DO NAPNE
        necEspeciais = "Não"
        tipoNecEspecial = "-"
        transtorno = "Não"
        tipoTranstorno = "-"
        superdotacao = "Não"
        tipoSuperdotacao = "-"

        mPne = re.search(r"Portador\(a\)\s+de\s+Necessidades\s+Especiais\s+(Sim|Não)", textoNapne, re.IGNORECASE)
        if mPne: necEspeciais = mPne.group(1)
        mTipPne = re.search(r"Tipo\s+de\s+Necessidade\s+Especial\s+-?\s*([^\n]+)", textoNapne, re.IGNORECASE)
        if mTipPne: tipoNecEspecial = mTipPne.group(1).strip()

        mTrans = re.search(r"Portador\(a\)\s+de\s+Transtorno\s+(Sim|Não)", textoNapne, re.IGNORECASE)
        if mTrans: transtorno = mTrans.group(1)
        mTipTrans = re.search(r"Tipo\s+de\s+Transtorno\s+-?\s*([^\n]+)", textoNapne, re.IGNORECASE)
        if mTipTrans: tipoTranstorno = mTipTrans.group(1).strip()

        mSuper = re.search(r"Portador\(a\)\s+de\s+Superdotação\s+(Sim|Não)", textoNapne, re.IGNORECASE)
        if mSuper: superdotacao = mSuper.group(1)
        mTipSuper = re.search(r"Superdotação\s+-?\s*([^\n]+)", textoNapne, re.IGNORECASE)
        if mTipSuper: tipoSuperdotacao = mTipSuper.group(1).strip()

        mapaNapneTemporario[nomeAluno.strip().upper()] = {
            'nec': necEspeciais, 'tipNec': tipoNecEspecial,
            'trans': transtorno, 'tipTrans': tipoTranstorno,
            'super': superdotacao, 'tipSuper': tipoSuperdotacao
        }

        # PROCESSAMENTO DAS DISCIPLINAS E NOTAS
        mapeamentoDisciplinas = {}

        for linha in linhas:
            linhaLimpa = re.sub(r'^\d{5,6}\s+', '', linha.strip())
            if not re.search(r'[A-Z]{3,4}\.\d{4,5}|\([A-Z0-9]{5,}\)', linhaLimpa):
                continue

            tokens = linhaLimpa.split()
            partesTexto = []
            partesDados = []
            passouDaMateria = False

            for token in tokens:
                if (',' in token or '.' in token) and token.replace(',', '').replace('.', '').isdigit() and not passouDaMateria:
                    passouDaMateria = True
                if not passouDaMateria:
                    partesTexto.append(token)
                else:
                    partesDados.append(token)

            nomeDisciplina = " ".join(partesTexto).strip()
            if not nomeDisciplina:
                continue

            tokensFiltrados = []
            for tok in partesDados:
                if tok in ["Cursando", "(Aguarda", "Carga", "Horária)", "Horária", "Aprovado", "Retido"] or "%" in tok:
                    continue
                if tok == "-" or tok.replace(',', '.').replace('.', '', 1).isdigit():
                    tokensFiltrados.append(tok)

            dadosTabela = tokensFiltrados[4:] if len(tokensFiltrados) >= 4 else tokensFiltrados

            notas = [None, None, None, None]
            pagDado = 0
            for etapa in range(4):
                if pagDado < len(dadosTabela):
                    valNota = dadosTabela[pagDado].replace(',', '.')
                    if valNota.replace('.', '', 1).isdigit():
                        notas[etapa] = float(valNota)
                    pagDado += 2  # Pula valor e falta correlata

            notasValidas = [n for n in notas if n is not None]
            mediaFinal = round(sum(notasValidas) / len(notasValidas), 2) if notasValidas else 0.0

            if len(nomeDisciplina) > 3:
                mapeamentoDisciplinas[nomeDisciplina] = {
                    'notas': notas,
                    'mediaFinal': mediaFinal,
                    'freqFinal': freqGlobal
                }

        for nomeDisp, blocos in mapeamentoDisciplinas.items():
            tecnico = any(kw in nomeDisp.upper() for kw in tecnicas)
            nucleo = "Técnico" if tecnico else "Comum"

            dadosFinais.append({
                'Nº Chamada': int(numeroChamada),
                'Aluno': nomeAluno,
                'Matrícula': matriculaAluno,
                'Série': serieAluno,
                'Disciplina': nomeDisp,
                '1º BI': blocos['notas'][0],
                '2º BI': blocos['notas'][1],
                '3º BI': blocos['notas'][2],
                '4º BI': blocos['notas'][3],
                'Média Final': blocos['mediaFinal'],
                'Freq. Final': blocos['freqFinal'],
                'Núcleo': nucleo,
                'Observações': '',
                'Necessidades Especiais': necEspeciais,
                'Tipo de Necessidade Especial': tipoNecEspecial,
                'Transtorno': transtorno,
                'Tipo de Transtorno': tipoTranstorno,
                'Superdotação': superdotacao,
                'Tipo de Superdotação': tipoSuperdotacao
            })

        numeroChamada += 1

    # Cruzamento de dados NAPNE
    for dado in dadosFinais:
        alunoAlvo = dado['Aluno'].strip().upper()
        if alunoAlvo in mapaNapneTemporario:
            info = mapaNapneTemporario[alunoAlvo]
            dado['Necessidades Especiais'] = info['nec']
            dado['Tipo de Necessidade Especial'] = info['tipNec']
            dado['Transtorno'] = info['trans']
            dado['Tipo de Transtorno'] = info['tipTrans']
            dado['Superdotação'] = info['super']
            dado['Tipo de Superdotação'] = info['tipSuper']

    return pd.DataFrame(dadosFinais)


# TELA 1: UPLOAD
if not st.session_state.dadosCarregados:
    st.title("Upload de PDFs")
    st.subheader("Selecione a sala e faça o upload dos relatórios em PDF.")

    salaSelecionada = st.selectbox("Selecione a Sala:", list(DICIONARIO_SALAS.keys()))
    st.session_state.salaAtiva = salaSelecionada
    arquivosEnviados = st.file_uploader("Envie os PDFs dos boletins:", type=["pdf"], accept_multiple_files=True, key=f"uploader_{salaSelecionada}")

    if st.button("PROCESSAR E ATUALIZAR DASHBOARD"):
        if arquivosEnviados:
            with st.spinner("Processando arquivos, atualizando planilha e gerando JSON..."):
                BDNovo = extrairDados(arquivosEnviados)

                linkSalaAtiva = DICIONARIO_SALAS[salaSelecionada]
                df_atual = conn.read(spreadsheet=linkSalaAtiva)

                # Remove linhas sem identificação
                if "Aluno" in df_atual.columns:
                    df_atual = df_atual[df_atual["Aluno"] != "Não Identificado"]

                # Concatena e descarta duplicatas apenas do mesmo aluno/disciplina (preservando outros alunos)
                df_final = pd.concat([df_atual, BDNovo], ignore_index=True)
                df_final = df_final.drop_duplicates(subset=["Aluno", "Disciplina"], keep="last")

                if not BDNovo.empty:
                    # 1. Salva no Google Sheets
                    conn.update(spreadsheet=linkSalaAtiva, data=df_final)

                    # 2. ATIVIDADE 1: Salva o dicionário gerado em arquivo JSON
                    dicionario_dados = df_final.to_dict(orient="records")
                    with open("dados_alunos.json", "w", encoding="utf-8") as f:
                        json.dump(dicionario_dados, f, ensure_ascii=False, indent=4)

                    st.session_state.salaAtiva = salaSelecionada
                    st.session_state.dadosCarregados = True
                    st.rerun()
                else:
                    st.error("Não foi possível extrair dados válidos do PDF.")
        else:
            st.error("Por favor, selecione os arquivos PDF.")

# TELA 2: DASHBOARD (HTML/JS EXIBIDO COM O SEU LAYOUT ORIGINAL)
else:
    st.sidebar.write(f"Visualizando: **{st.session_state.salaAtiva}**")

    dados_para_html = []
    if os.path.exists("dados_alunos.json"):
        with open("dados_alunos.json", "r", encoding="utf-8") as f:
            dados_para_html = json.load(f)
    else:
        linkSalaAtiva = DICIONARIO_SALAS[st.session_state.salaAtiva]
        df_sheet = conn.read(spreadsheet=linkSalaAtiva, ttl="0")
        dados_para_html = df_sheet.where(pd.notnull(df_sheet), None).to_dict(orient="records")

    # Mapeamento do JSON para a estrutura bancoAlunos do HTML
    alunosMapeados = {}
    for item in dados_para_html:
        prontuario = str(item.get("Matrícula") or item.get("prontuario") or "BT300000").strip()
        nome = str(item.get("Aluno", "")).strip()

        if nome == "Não Identificado" or not nome:
            continue

        if prontuario not in alunosMapeados:
            alunosMapeados[prontuario] = {
                "prontuario": prontuario,
                "nome": nome,
                "curso": item.get("Série", "Técnico em Redes de Computadores"),
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
            if v is None or pd.isna(v): return None
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

        b64_html = base64.b64encode(html_injetado.encode('utf-8')).decode('utf-8')
        iframe_code = f"""
        <iframe 
            src="data:text/html;charset=utf-8;base64,{b64_html}"
            style="width: 100%; height: 1150px; border: none; border-radius: 8px;"
        ></iframe>
        """
        st.markdown(iframe_code, unsafe_allow_html=True)
    else:
        st.error("O arquivo 'index.html' não foi encontrado na raiz do projeto no GitHub.")
