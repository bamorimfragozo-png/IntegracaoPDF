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

# Lista de palavras-chave para identificar matérias técnicas
TECNICAS = [
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

MAPEAMENTO_TURMAS_PERMITIDAS = {
    "Redes 1": ["INT.RED", "INT.RCO", "REDES"],
    "Redes 2": ["INT.RED", "INT.RCO", "REDES"],
    "Redes 3": ["INT.RED", "INT.RCO", "REDES"],
    "Automação 1": ["INT.AUT", "INT.EAU", "AUTOMACAO", "AUTOMAÇÃO"],
    "Automação 2": ["INT.AUT", "INT.EAU", "AUTOMACAO", "AUTOMAÇÃO"],
    "Automação 3": ["INT.AUT", "INT.EAU", "AUTOMACAO", "AUTOMAÇÃO"],
}

if "dadosCarregados" not in st.session_state:
    st.session_state.dadosCarregados = False
if "salaAtiva" not in st.session_state:
    st.session_state.salaAtiva = "Redes 1"

# Processa salvamento vindo do iframe
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

if st.sidebar.button("📁 Upload de PDFs", use_container_width=True):
    st.session_state.dadosCarregados = False
    st.rerun()

if st.sidebar.button("📊 Ficha do Conselho", use_container_width=True):
    st.session_state.dadosCarregados = True
    st.rerun()


def extrair_dados_pdf(arquivos_pdf, sala_selecionada):
    dados_finais = []
    dados_napne = {}

    # Passo 1: Varredura de Fichas NAPNE/PNE
    for arquivo in arquivos_pdf:
        pdf_bytes = io.BytesIO(arquivo.getvalue())
        try:
            reader = PdfReader(pdf_bytes)
            texto = "\n".join([p.extract_text() or "" for p in reader.pages])
        except Exception:
            continue

        # Verifica se é relatório do NAPNE
        if "Necessidades Especiais" in texto or "Transtorno" in texto or "Superdotação" in texto:
            mat_match = re.search(r"BT\d{7}", texto, re.IGNORECASE)
            if mat_match:
                prontuario = mat_match.group(0).upper()
                
                # Extrai tipos de atendimento
                pne = "Sim" if re.search(r"Necessidade\s*Especial:\s*Sim", texto, re.I) or "Portador(a) de Necessidades Especiais Sim" in texto else "Não"
                trans = "Sim" if re.search(r"Transtorno:\s*Sim", texto, re.I) or "Portador(a) de Transtorno Sim" in texto else "Não"
                superdot = "Sim" if re.search(r"Superdotação:\s*Sim", texto, re.I) or "Portador(a) de Superdotação Sim" in texto else "Não"
                
                # Busca descrições específicas
                desc = []
                for linha in texto.split("\n"):
                    if any(k in linha for k in ["Tipo", "Descrição", "Laudo", "Observação"]) and ":" in linha:
                        desc.append(linha.strip())
                
                info_pne_str = " | ".join(desc) if desc else "Aluno com acompanhamento NAPNE cadastrado."
                
                dados_napne[prontuario] = {
                    "pne": pne,
                    "trans": trans,
                    "super": superdot,
                    "info": info_pne_str
                }

    # Passo 2: Varredura de Boletins
    for arquivo in arquivos_pdf:
        pdf_bytes = io.BytesIO(arquivo.getvalue())
        try:
            reader = PdfReader(pdf_bytes)
            texto_completo = "\n".join([p.extract_text() or "" for p in reader.pages])
        except Exception:
            continue

        # Se for ficha pura do NAPNE, pula o processamento de notas
        if "BOLETIM DE NOTAS" not in texto_completo and "Diário" not in texto_completo:
            continue

        # Quebra texto por aluno
        blocos = re.split(r"(?=Aluno\(a\):|BOLETIM DE NOTAS INDIVIDUAL)", texto_completo)

        for bloco in blocos:
            if not bloco.strip():
                continue

            # Validação de Turma
            permitidas = MAPEAMENTO_TURMAS_PERMITIDAS.get(sala_selecionada, [])
            if permitidas and not any(p.upper() in bloco.upper() for p in permitidas):
                continue

            # Nome e Prontuário
            nome = "Não Identificado"
            m_nome = re.search(r"Aluno\(a\):\s*([^\n|]+)", bloco, re.IGNORECASE)
            if m_nome:
                nome = m_nome.group(1).strip()
                nome = re.sub(r"\s+BT\d{7}.*", "", nome, flags=re.IGNORECASE).strip()

            prontuario = ""
            m_mat = re.search(r"BT\d{7}", bloco, re.IGNORECASE)
            if m_mat:
                prontuario = m_mat.group(0).upper()

            if not prontuario:
                continue

            # Frequência Global do Aluno
            freq_global = 100.0
            m_freq = re.search(r"Frequência\s*Global:\s*(\d+[\.,]?\d*)\s*%", bloco, re.IGNORECASE)
            if not m_freq:
                m_freq = re.search(r"(\d+[\.,]?\d*)\s*%\s*de\s*frequência", bloco, re.IGNORECASE)
            if m_freq:
                freq_global = float(m_freq.group(1).replace(",", "."))

            # Processamento de Disciplinas e Notas
            linhas = bloco.split("\n")
            for idx, linha in enumerate(linhas):
                # Padrão de código de disciplina do SUAP
                if re.search(r"INT\.\d{5}|[A-Z]{4}\.\d{5}", linha):
                    nome_materia = linha.strip()
                    
                    # Procura notas na linha atual e nas 3 seguintes
                    bloco_materia = " ".join(linhas[idx:idx+4])
                    # Captura números de notas (ex: 8,5 ou 10.0 ou -)
                    tokens = re.findall(r"\b(\d{1,2}[\.,]\d{1,2}|\d{1,2})\b", bloco_materia)
                    
                    notas = []
                    for t in tokens:
                        try:
                            val = float(t.replace(",", "."))
                            if 0 <= val <= 10.0:
                                notas.append(val)
                        except ValueError:
                            pass

                    b1 = notas[0] if len(notas) > 0 else None
                    b2 = notas[1] if len(notas) > 1 else None
                    b3 = notas[2] if len(notas) > 2 else None
                    b4 = notas[3] if len(notas) > 3 else None

                    validas = [n for n in [b1, b2, b3, b4] if n is not None]
                    media_final = round(sum(validas) / len(validas), 2) if validas else 0.0

                    nap = dados_napne.get(prontuario, {
                        "pne": "Não", "trans": "Não", "super": "Não",
                        "info": "Nenhum registro de PNE/Transtorno/Superdotação."
                    })

                    dados_finais.append({
                        "Aluno": nome,
                        "Matrícula": prontuario,
                        "Série": sala_selecionada,
                        "Disciplina": nome_materia,
                        "1º BI": b1,
                        "2º BI": b2,
                        "3º BI": b3,
                        "4º BI": b4,
                        "Média Final": media_final,
                        "Freq. Final": freq_global,
                        "Núcleo": "Técnico" if any(t in nome_materia.upper() for t in TECNICAS) else "Comum",
                        "Observações": "",
                        "Necessidades Especiais": nap["pne"],
                        "Tipo de Necessidade Especial": nap["info"],
                        "Transtorno": nap["trans"],
                        "Tipo de Transtorno": nap["info"],
                        "Superdotação": nap["super"],
                        "Tipo de Superdotação": nap["info"]
                    })

    return pd.DataFrame(dados_finais)


# --- INTERFACE STREAMLIT ---

if not st.session_state.dadosCarregados:
    st.title("Upload de PDFs - Conselho de Classe")
    salaSelecionada = st.selectbox("Selecione a Sala:", list(DICIONARIO_SALAS.keys()))
    st.session_state.salaAtiva = salaSelecionada
    
    arquivosEnviados = st.file_uploader("Envie os PDFs dos boletins e fichas NAPNE:", type=["pdf"], accept_multiple_files=True)

    if st.button("PROCESSAR E ATUALIZAR DASHBOARD", type="primary"):
        if arquivosEnviados:
            with st.spinner("Processando arquivos..."):
                df_novo = extrair_dados_pdf(arquivosEnviados, salaSelecionada)

                if not df_novo.empty:
                    link_sheet = DICIONARIO_SALAS[salaSelecionada]
                    try:
                        df_antigo = conn.read(spreadsheet=link_sheet, ttl=0)
                    except Exception:
                        df_antigo = pd.DataFrame()

                    # Preserva observações já gravadas
                    if not df_antigo.empty and "Matrícula" in df_antigo.columns and "Observações" in df_antigo.columns:
                        obs_dict = df_antigo.set_index(["Matrícula", "Disciplina"])["Observações"].to_dict()
                        for i, row in df_novo.iterrows():
                            chave = (row["Matrícula"], row["Disciplina"])
                            if chave in obs_dict and pd.notna(obs_dict[chave]):
                                df_novo.at[i, "Observações"] = obs_dict[chave]

                    # Atualiza Planilha Google
                    conn.update(spreadsheet=link_sheet, data=df_novo)

                    # Limpa e grava o JSON sem NaN (evita crash do JavaScript)
                    json_str = df_novo.to_json(orient="records", date_format="iso")
                    dados_limpos = json.loads(json_str)

                    with open("dados_alunos.json", "w", encoding="utf-8") as f:
                        json.dump(dados_limpos, f, ensure_ascii=False, indent=4)

                    st.session_state.dadosCarregados = True
                    st.success("Processamento concluído com sucesso!")
                    st.rerun()
                else:
                    st.error("Nenhum dado válido extraído. Verifique se os PDFs pertencem à sala selecionada.")
        else:
            st.error("Anexe ao menos um arquivo PDF.")

else:
    # Leitura e montagem da estrutura para o HTML
    dados_json = []
    if os.path.exists("dados_alunos.json"):
        with open("dados_alunos.json", "r", encoding="utf-8") as f:
            dados_json = json.load(f)

    # Agrupa por aluno
    alunos = {}
    for r in dados_json:
        p = str(r.get("Matrícula", "")).strip().upper()
        if not p:
            continue

        if p not in alunos:
            alunos[p] = {
                "prontuario": p,
                "nome": r.get("Aluno", "Sem Nome"),
                "curso": r.get("Série", "Técnico Integrado"),
                "turma": st.session_state.salaAtiva,
                "frequencia": float(r.get("Freq. Final") or 100.0),
                "napne": str(r.get("Necessidades Especiais")).upper() == "SIM" or str(r.get("Transtorno")).upper() == "SIM",
                "pneInfo": r.get("Tipo de Necessidade Especial") or "Sem registros no NAPNE.",
                "deliberacao": r.get("Observações") or "",
                "disciplinas": []
            }

        alunos[p]["disciplinas"].append({
            "nome": r.get("Disciplina", "Disciplina"),
            "b1": r.get("1º BI"),
            "b2": r.get("2º BI"),
            "b3": r.get("3º BI"),
            "b4": r.get("4º BI"),
            "faltas": 0
        })

    payload_json = json.dumps(list(alunos.values()), ensure_ascii=False)

    if os.path.exists("index.html"):
        with open("index.html", "r", encoding="utf-8") as f:
            html_template = f.read()

        html_final = html_template.replace("__DADOS_JSON_INJETADOS__", payload_json)
        b64 = base64.b64encode(html_final.encode("utf-8")).decode("utf-8")

        st.markdown(
            f'<iframe src="data:text/html;charset=utf-8;base64,{b64}" style="width: 100%; height: 1100px; border: none;"></iframe>',
            unsafe_allow_html=True
        )
    else:
        st.error("Arquivo 'index.html' não foi localizado.")
