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

# Mapeamento de validação para impedir envio de PDF na sala errada
MAPEAMENTO_TURMAS_PERMITIDAS = {
    "Redes 1": ["INT.RED", "INT.RCO"],
    "Redes 2": ["INT.RED", "INT.RCO"],
    "Redes 3": ["INT.RED", "INT.RCO"],
    "Automação 1": ["INT.AUT", "INT.EAU"],
    "Automação 2": ["INT.AUT", "INT.EAU"],
    "Automação 3": ["INT.AUT", "INT.EAU"],
}

if "dadosCarregados" not in st.session_state:
    st.session_state.dadosCarregados = False
if "salaAtiva" not in st.session_state:
    st.session_state.salaAtiva = "Redes 1"

# Captura de salvamento via query params (comunicação iframe -> streamlit)
query_params = st.query_params
if "action" in query_params and query_params["action"] == "salvar_obs":
    aluno_alvo = query_params.get("aluno", "")
    nova_obs = query_params.get("obs", "")
    sala_alvo = st.session_state.salaAtiva
    linkSala = DICIONARIO_SALAS[sala_alvo]
    
    try:
        df_sheet = conn.read(spreadsheet=linkSala, ttl=0)
        if "Aluno" in df_sheet.columns and "Observações" in df_sheet.columns:
            mascara = df_sheet["Aluno"].astype(str).str.strip().str.upper() == aluno_alvo.strip().upper()
            df_sheet.loc[mascara, "Observações"] = nova_obs
            conn.update(spreadsheet=linkSala, data=df_sheet)
            st.toast(f"Deliberação de {aluno_alvo} salva no Google Sheets!", icon="✅")
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


def extrairDados(arquivosPdf, sala_selecionada):
    dadosFinais = []
    dadosNapne = {} # Prontuário -> Dados NAPNE

    # 1º Passo: Ler arquivos e separar por tipo (Boletim x Ficha PNE/SUAP)
    for arquivo in arquivosPdf:
        memoriaPdf = io.BytesIO(arquivo.getvalue())
        try:
            leitorPdf = PdfReader(memoriaPdf)
        except Exception as e:
            st.error(f"Erro ao ler arquivo {arquivo.name}: {e}")
            continue

        textoCompleto = "\n".join([p.extract_text() or "" for p in leitorPdf.pages])

        # --- A. LEITURA DE FICHA PNE / SUAP (NAPNE) ---
        if "Dados Gerais" in textoCompleto and ("Portador(a)" in textoCompleto or "Necessidades Especiais" in textoCompleto):
            prontuario_pne = ""
            mPront = re.search(r"Matricula\s*(BT\d{7})", textoCompleto, re.IGNORECASE)
            if not mPront:
                mPront = re.search(r"\((BT\d{7})\)", textoCompleto)
            if mPront:
                prontuario_pne = mPront.group(1).upper()

            pne_sim = "Sim" if re.search(r"Portador\(a\)\s*de\s*Necessidades\s*Especiais\s*Sim", textoCompleto, re.IGNORECASE) else "Não"
            trans_sim = "Sim" if re.search(r"Portador\(a\)\s*de\s*Transtorno\s*Sim", textoCompleto, re.IGNORECASE) else "Não"
            super_sim = "Sim" if re.search(r"Portador\(a\)\s*de\s*Superdotação\s*Sim", textoCompleto, re.IGNORECASE) else "Não"

            tip_pne = "-"
            mTipPne = re.search(r"Tipo\s+de\s+Necessidade\s+Especial\s+([^\n]+)", textoCompleto)
            if mTipPne and mTipPne.group(1).strip() not in ["-", ""]:
                tip_pne = mTipPne.group(1).strip()

            tip_trans = "-"
            mTipTrans = re.search(r"Tipo\s+de\s+Transtorno\s+([^\n]+)", textoCompleto)
            if mTipTrans and mTipTrans.group(1).strip() not in ["-", ""]:
                tip_trans = mTipTrans.group(1).strip()

            tip_super = "-"
            mTipSuper = re.search(r"Tipo\s+de\s+Superdotação\s+([^\n]+)", textoCompleto)
            if mTipSuper and mTipSuper.group(1).strip() not in ["-", ""]:
                tip_super = mTipSuper.group(1).strip()

            if prontuario_pne:
                dadosNapne[prontuario_pne] = {
                    'pne': pne_sim, 'tipo_pne': tip_pne,
                    'trans': trans_sim, 'tipo_trans': tip_trans,
                    'super': super_sim, 'tipo_super': tip_super
                }
            continue

        # --- B. LEITURA DE BOLETIM DE NOTAS INDIVIDUAL ---
        blocosBoletins = re.split(r"(?=BOLETIM DE NOTAS INDIVIDUAL|Aluno\(a\):)", textoCompleto)

        for bloco in blocosBoletins:
            if "Disciplina" not in bloco and "TÉCNICO" not in bloco:
                continue

            # Validação de Turma/Sala
            siglas_permitidas = MAPEAMENTO_TURMAS_PERMITIDAS.get(sala_selecionada, [])
            if siglas_permitidas and not any(sigla in bloco for sigla in siglas_permitidas):
                st.warning(f"Atenção: O PDF de {arquivo.name} parece não pertencer à turma {sala_selecionada}. Processamento suspenso para este bloco.")
                continue

            nomeAluno = "Não Identificado"
            matriculaAluno = ""
            serieAluno = ""
            freqGlobal = 100.0

            mNome = re.search(r"Aluno\(a\):\s*([^\n|]+)", bloco, re.IGNORECASE)
            if mNome:
                nomeAluno = mNome.group(1).strip()
                nomeAluno = re.sub(r"Matrícula:.*", "", nomeAluno, flags=re.IGNORECASE).strip()

            mMat = re.search(r"BT\d{7}", bloco)
            if mMat:
                matriculaAluno = mMat.group(0).strip().upper()

            mTurma = re.search(r"202\d[12]\.\d\.[A-Z0-9\.]+", bloco)
            if mTurma:
                serieAluno = mTurma.group(0).strip()

            # Captura precisa da frequência global do aluno no boletim
            mFreq = re.search(r"Frequência\s*:\s*\|?\s*(\d+[\.,]?\d*)\s*%", bloco, re.IGNORECASE)
            if mFreq:
                freqGlobal = float(mFreq.group(1).replace(",", "."))

            # Extração das Disciplinas
            linhas = bloco.split('\n')
            for idx, linha in enumerate(linhas):
                if re.search(r"INT\.\d{5}", linha):
                    nomeMateria = linha.strip()
                    # Procura notas nas linhas seguintes do diário
                    blocoContexto = " ".join(linhas[idx:idx+4])
                    candidatosNotas = re.findall(r"\b(\d{1,2}[\.,]\d{1,2})\b", blocoContexto)
                    
                    notasEncontradas = []
                    for val in candidatosNotas:
                        try:
                            num = float(val.replace(",", "."))
                            if num <= 10.0:
                                notasEncontradas.append(num)
                        except ValueError:
                            pass

                    b1 = notasEncontradas[0] if len(notasEncontradas) > 0 else None
                    b2 = notasEncontradas[1] if len(notasEncontradas) > 1 else None
                    b3 = notasEncontradas[2] if len(notasEncontradas) > 2 else None
                    b4 = notasEncontradas[3] if len(notasEncontradas) > 4 else None

                    notasValidas = [n for n in [b1, b2, b3, b4] if n is not None]
                    mediaFinal = round(sum(notasValidas) / len(notasValidas), 2) if notasValidas else 0.0

                    tecnico = any(kw in nomeMateria.upper() for kw in tecnicas)
                    nucleo = "Técnico" if tecnico else "Comum"

                    # Cruza com os dados do NAPNE se existirem
                    nap_info = dadosNapne.get(matriculaAluno, {
                        'pne': 'Não', 'tipo_pne': '-',
                        'trans': 'Não', 'tipo_trans': '-',
                        'super': 'Não', 'tipo_super': '-'
                    })

                    dadosFinais.append({
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
                        'Núcleo': nucleo,
                        'Observações': '',
                        'Necessidades Especiais': nap_info['pne'],
                        'Tipo de Necessidade Especial': nap_info['tipo_pne'],
                        'Transtorno': nap_info['trans'],
                        'Tipo de Transtorno': nap_info['tipo_trans'],
                        'Superdotação': nap_info['super'],
                        'Tipo de Superdotação': nap_info['tipo_super']
                    })

    return pd.DataFrame(dadosFinais)


# TELA 1: UPLOAD
if not st.session_state.dadosCarregados:
    st.title("Upload de PDFs - Conselho de Classe")
    st.subheader("Selecione a sala e faça o upload dos relatórios em PDF.")

    salaSelecionada = st.selectbox("Selecione a Sala:", list(DICIONARIO_SALAS.keys()))
    st.session_state.salaAtiva = salaSelecionada
    arquivosEnviados = st.file_uploader("Envie os PDFs dos boletins e fichas PNE:", type=["pdf"], accept_multiple_files=True, key=f"uploader_{salaSelecionada}")

    if st.button("PROCESSAR E ATUALIZAR DASHBOARD"):
        if arquivosEnviados:
            with st.spinner("Processando arquivos, validando turmas e salvando JSON..."):
                BDNovo = extrairDados(arquivosEnviados, salaSelecionada)

                if not BDNovo.empty:
                    linkSalaAtiva = DICIONARIO_SALAS[salaSelecionada]
                    try:
                        df_atual = conn.read(spreadsheet=linkSalaAtiva, ttl=0)
                    except Exception:
                        df_atual = pd.DataFrame()

                    # Lógica de substituição/Upsert por Prontuário e Disciplina sem apagar histórico de observações antigas
                    if not df_atual.empty and "Matrícula" in df_atual.columns and "Disciplina" in df_atual.columns:
                        # Preserva as Observações anteriores digitadas no Conselho
                        if "Observações" in df_atual.columns:
                            obs_map = df_atual.set_index(["Matrícula", "Disciplina"])["Observações"].to_dict()
                            for idx, row in BDNovo.iterrows():
                                chave = (row["Matrícula"], row["Disciplina"])
                                if chave in obs_map and pd.notna(obs_map[chave]) and str(obs_map[chave]).strip() != "":
                                    BDNovo.at[idx, "Observações"] = obs_map[chave]

                        df_final = pd.concat([df_atual, BDNovo], ignore_index=True)
                        df_final = df_final.drop_duplicates(subset=["Matrícula", "Disciplina"], keep="last")
                    else:
                        df_final = BDNovo

                    # 1. Salva na Planilha do Google
                    conn.update(spreadsheet=linkSalaAtiva, data=df_final)

                    # 2. Salva em arquivo JSON local para o Dashboard JS
                    dicionario_dados = df_final.where(pd.notnull(df_final), None).to_dict(orient="records")
                    with open("dados_alunos.json", "w", encoding="utf-8") as f:
                        json.dump(dicionario_dados, f, ensure_ascii=False, indent=4)

                    st.session_state.salaAtiva = salaSelecionada
                    st.session_state.dadosCarregados = True
                    st.success("Dados processados com sucesso!")
                    st.rerun()
                else:
                    st.error("Não foi possível extrair dados válidos dos arquivos anexados.")
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
        df_sheet = conn.read(spreadsheet=linkSalaAtiva, ttl=0)
        dados_para_html = df_sheet.where(pd.notnull(df_sheet), None).to_dict(orient="records")

    alunosMapeados = {}
    for item in dados_para_html:
        prontuario = str(item.get("Matrícula") or item.get("prontuario") or "").strip().upper()
        nome = str(item.get("Aluno", "")).strip()

        if not prontuario or nome == "Não Identificado" or not nome:
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
                "curso": item.get("Série", "Técnico Integrado"),
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
            "faltas": 0
        })

    json_estruturado = json.dumps(list(alunosMapeados.values()), ensure_ascii=False)

    # Botão para atualizar manualmente a partir do JSON
    col1, col2 = st.columns([8, 2])
    with col2:
        if st.button("🔄 Recarregar JSON no Painel", use_container_width=True):
            st.rerun()

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
        st.error("O arquivo 'index.html' não foi encontrado.")
