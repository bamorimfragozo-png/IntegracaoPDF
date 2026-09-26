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

# PROCESSAMENTO DO SALVAMENTO DE DELIBERAÇÃO
query_params = st.query_params
if "action" in query_params and query_params["action"] == "salvar_obs":
    aluno_alvo = query_params.get("aluno", "")
    nova_obs = query_params.get("obs", "")
    sala_alvo = st.session_state.salaAtiva
    linkSala = DICIONARIO_SALAS[sala_alvo]
    
    try:
        df_sheet = conn.read(spreadsheet=linkSala)
        if "Aluno" in df_sheet.columns and "Observações" in df_sheet.columns:
            mask = df_sheet["Aluno"].astype(str).str.strip().str.upper() == aluno_alvo.strip().upper()
            df_sheet.loc[mask, "Observações"] = nova_obs
            conn.update(spreadsheet=linkSala, data=df_sheet)
            
            # Atualiza o JSON local instantaneamente
            if os.path.exists("dados_alunos.json"):
                with open("dados_alunos.json", "r", encoding="utf-8") as f:
                    dados_json = json.load(f)
                for d in dados_json:
                    if str(d.get("Aluno")).strip().upper() == aluno_alvo.strip().upper():
                        d["Observações"] = nova_obs
                with open("dados_alunos.json", "w", encoding="utf-8") as f:
                    json.dump(dados_json, f, ensure_ascii=False, indent=4)
                    
            st.toast(f"Deliberação de {aluno_alvo} salva na planilha!", icon="✅")
    except Exception as e:
        st.error(f"Erro ao salvar deliberação: {e}")
    st.query_params.clear()

st.sidebar.title("Conselho de Classe")
st.sidebar.markdown("---")

if st.sidebar.button("📁 Tela de Upload / Processamento", use_container_width=True):
    st.session_state.dadosCarregados = False
    st.rerun()

if st.sidebar.button("📊 Ficha do Conselho (Dashboard)", use_container_width=True):
    st.session_state.dadosCarregados = True
    st.rerun()


def extrairDados(arquivosPdf):
    dadosFinais = []
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

        blocosBoletins = re.split(r"(?=BOLETIM DE NOTAS INDIVIDUAL|Aluno\(a\):)", textoCompleto)

        for bloco in blocosBoletins:
            if "Disciplina" not in bloco and "TÉCNICO" not in bloco:
                continue

            blocoLimpo = re.sub(r'\s+', ' ', bloco)

            nomeAluno = ""
            matriculaAluno = ""
            serieAluno = ""
            freqGlobal = 100.0

            mNome = re.search(r"Aluno\(a\):\s*([^\n|]+)", bloco, re.IGNORECASE)
            if mNome:
                nomeAluno = mNome.group(1).strip()
                nomeAluno = re.sub(r"Matrícula:.*", "", nomeAluno, flags=re.IGNORECASE).strip()

            if not nomeAluno:
                mNome2 = re.search(r"BOLETIM DE NOTAS INDIVIDUAL\s*([^\n]+)", bloco, re.IGNORECASE)
                if mNome2:
                    nomeAluno = mNome2.group(1).strip()

            mMat = re.search(r"BT\d{7}", bloco)
            if mMat: matriculaAluno = mMat.group(0).strip()

            mTurma = re.search(r"202\d[12]\.\d\.[A-Z0-9\.]+", bloco)
            if mTurma: serieAluno = mTurma.group(0).strip()

            mFreq = re.search(r"Frequência\s*:\s*\|?\s*(\d+[\.,]?\d*)\s*%", blocoLimpo, re.IGNORECASE)
            if mFreq:
                freqGlobal = float(mFreq.group(1).replace(",", "."))

            if not nomeAluno or nomeAluno == "Não Identificado":
                nomeAluno = arquivo.name.replace(".pdf", "").replace("Boletim", "").replace("_", " ").strip()

            # EXTRAÇÃO FLEXÍVEL DO NAPNE
            necEspeciais = "Não"
            tipoNecEspecial = "-"
            transtorno = "Não"
            tipoTranstorno = "-"
            superdotacao = "Não"
            tipoSuperdotacao = "-"

            if "Sim" in re.findall(r"Necessidades\s+Especiais\s*:?\s*(Sim|Não)", blocoLimpo, re.IGNORECASE):
                necEspeciais = "Sim"
            mTipPne = re.search(r"Tipo\s+de\s+Necessidade\s+Especial\s*:?\s*(.*?)(?=Portador|\bTranstorno\b|\bSuperdotação\b|Disciplina|\Z)", blocoLimpo, re.IGNORECASE)
            if mTipPne and len(mTipPne.group(1).strip()) > 1:
                tipoNecEspecial = mTipPne.group(1).strip()

            if "Sim" in re.findall(r"Transtorno\s*:?\s*(Sim|Não)", blocoLimpo, re.IGNORECASE):
                transtorno = "Sim"
            mTipTrans = re.search(r"Tipo\s+de\s+Transtorno\s*:?\s*(.*?)(?=Portador|\bSuperdotação\b|Disciplina|\Z)", blocoLimpo, re.IGNORECASE)
            if mTipTrans and len(mTipTrans.group(1).strip()) > 1:
                tipoTranstorno = mTipTrans.group(1).strip()

            if "Sim" in re.findall(r"Superdotação\s*:?\s*(Sim|Não)", blocoLimpo, re.IGNORECASE):
                superdotacao = "Sim"
            mTipSuper = re.search(r"Tipo\s+de\s+Superdotação\s*:?\s*(.*?)(?=Disciplina|\Z)", blocoLimpo, re.IGNORECASE)
            if mTipSuper and len(mTipSuper.group(1).strip()) > 1:
                tipoSuperdotacao = mTipSuper.group(1).strip()

            # DISCIPLINAS
            padraoBloco = re.findall(
                r"(INT\.\d{5}\s*\([A-Z0-9]+\)\s*-\s*[^0-9\n]+)([\s\S]*?)(?=(?:INT\.\d{5}|Total|Este documento|Boituva|\Z))",
                bloco
            )

            for match in padraoBloco:
                nomeMateria = match[0].strip()
                blocoTexto = match[1]

                if "Turma:" in nomeMateria or "Sit." in nomeMateria or "Série" in nomeMateria:
                    continue

                candidatosNumeros = re.findall(r"\b(\d{1,3}[\.,]?\d{0,2})\b", blocoTexto)
                
                candidatosNotas = []
                faltasMateria = 0
                freqMateria = freqGlobal

                for val in candidatosNumeros:
                    try:
                        num = float(val.replace(",", "."))
                        if num <= 10.0:
                            candidatosNotas.append(num)
                        elif num > 10.0 and num <= 100.0:
                            freqMateria = num
                    except ValueError:
                        pass

                mFaltas = re.search(r"Faltas\s*:\s*(\d+)", blocoTexto, re.IGNORECASE)
                if mFaltas:
                    faltasMateria = int(mFaltas.group(1))

                b1 = candidatosNotas[0] if len(candidatosNotas) > 0 else None
                b2 = candidatosNotas[1] if len(candidatosNotas) > 1 else None
                b3 = candidatosNotas[2] if len(candidatosNotas) > 2 else None
                b4 = candidatosNotas[3] if len(candidatosNotas) > 3 else None

                notasValidas = [n for n in [b1, b2, b3, b4] if n is not None]
                mediaFinal = round(sum(notasValidas) / len(notasValidas), 2) if notasValidas else 0.0

                tecnico = any(kw in nomeMateria.upper() for kw in tecnicas)
                nucleo = "Técnico" if tecnico else "Comum"

                dadosFinais.append({
                    'Nº Chamada': int(numeroChamada),
                    'Aluno': nomeAluno,
                    'Matrícula': matriculaAluno,
                    'Série': serieAluno,
                    'Disciplina': nomeMateria,
                    '1º BI': b1,
                    '2º BI': b2,
                    '3º BI': b3,
                    '4º BI': b4,
                    'Média Final': mediaFinal,
                    'Freq. Final': freqGlobal,
                    'Freq. Matéria': freqMateria,
                    'Faltas Matéria': faltasMateria,
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

                if "Aluno" in df_atual.columns:
                    df_atual = df_atual[~df_atual["Aluno"].astype(str).str.contains("BT30", na=False)]
                    df_atual = df_atual[df_atual["Aluno"] != "Não Identificado"]

                df_final = pd.concat([df_atual, BDNovo], ignore_index=True)
                df_final = df_final.drop_duplicates(subset=["Aluno", "Disciplina"], keep="last")

                if not BDNovo.empty:
                    conn.update(spreadsheet=linkSalaAtiva, data=df_final)

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

# TELA 2: DASHBOARD HTML
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

    alunosMapeados = {}
    for item in dados_para_html:
        prontuario = str(item.get("Matrícula") or item.get("prontuario") or "BT300000").strip()
        nome = str(item.get("Aluno", "")).strip()

        if nome == "Não Identificado" or not nome or nome.startswith("BT30"):
            continue

        if prontuario not in alunosMapeados:
            pneTexto = []
            if str(item.get("Necessidades Especiais")).strip().lower() == "sim": 
                pneTexto.append(f"PNE: {item.get('Tipo de Necessidade Especial') or '-'}")
            if str(item.get("Transtorno")).strip().lower() == "sim": 
                pneTexto.append(f"Transtorno: {item.get('Tipo de Transtorno') or '-'}")
            if str(item.get("Superdotação")).strip().lower() == "sim": 
                pneTexto.append(f"Superdotação: {item.get('Tipo de Superdotação') or '-'}")

            infoNapne = " | ".join(pneTexto) if pneTexto else "Nenhum registro de PNE/Transtorno/Superdotação."

            alunosMapeados[prontuario] = {
                "prontuario": prontuario,
                "nome": nome,
                "curso": item.get("Série", "Técnico em Redes de Computadores"),
                "turma": st.session_state.salaAtiva,
                "frequencia": float(item.get("Freq. Final") or 100),
                "napne": len(pneTexto) > 0,
                "pneInfo": infoNapne,
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
            "frequenciaMateria": float(item.get("Freq. Matéria") or item.get("Freq. Final") or 100),
            "faltas": int(item.get("Faltas Matéria") or 0)
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
        st.error("O arquivo 'index.html' não foi encontrado no repositório GitHub.")
