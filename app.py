import base64
import io
import json
import os
import re
import pandas as pd
import streamlit as st
from pypdf import PdfReader
from streamlit_gsheets import GSheetsConnection

# CONFIGURAÇÃO DE PÁGINA
st.set_page_config(
    page_title="Conselho de Classe - IFSP Boituva",
    layout="wide",
    initial_sidebar_state="expanded"
)

# LISTA DE DISCIPLINAS TÉCNICAS
tecnicas = [
    "ILPR", "MAIN", "ININ", "LDPR", "RDCO", "LPWE", "SOPE", "INSO", "IPRE",
    "BDDA", "PSCO", "PRIN", "CNVI", "SDRE", "ASRE", "RSFI", "GCLI", "ELET",
    "DCAD", "CAUT", "PROG", "PCOE", "EDIG", "PRI1", "ELIN", "CISUT", "INTI",
    "MAPI", "CNCM", "CLPR", "REPI", "HIEP", "MIMP", "PRI2"
]

# CONEXÃO COM PLANILHAS GOOGLE SHEETS
conn = st.connection("gsheets", type=GSheetsConnection)

DICIONARIO_SALAS = {
    "Redes 1": st.secrets["connections"]["gsheets"]["Redes1"],
    "Redes 2": st.secrets["connections"]["gsheets"]["Redes2"],
    "Redes 3": st.secrets["connections"]["gsheets"]["Redes3"],
    "Automação 1": st.secrets["connections"]["gsheets"]["Automacao1"],
    "Automação 2": st.secrets["connections"]["gsheets"]["Automacao2"],
    "Automação 3": st.secrets["connections"]["gsheets"]["Automacao3"]
}

# GERENCIAMENTO DE ESTADO
if "dadosCarregados" not in st.session_state:
    st.session_state.dadosCarregados = False
if "salaAtiva" not in st.session_state:
    st.session_state.salaAtiva = "Redes 1"

# CAPTURA DE SALVAMENTO VIA QUERY PARAMS
query_params = st.query_params
if "action" in query_params and query_params["action"] == "salvar_obs":
    aluno_alvo = query_params.get("aluno", "")
    nova_obs = query_params.get("obs", "")
    sala_alvo = st.session_state.salaAtiva
    linkSala = DICIONARIO_SALAS[sala_alvo]
    
    try:
        df_sheet = conn.read(spreadsheet=linkSala)
        if "Aluno" in df_sheet.columns and "Observações" in df_sheet.columns:
            df_sheet.loc[
                df_sheet["Aluno"].astype(str).str.strip().str.upper() == aluno_alvo.strip().upper(), 
                "Observações"
            ] = nova_obs
            conn.update(spreadsheet=linkSala, data=df_sheet)
            st.toast(f"Observações de {aluno_alvo} salvas com sucesso!", icon="✅")
    except Exception as e:
        st.error(f"Erro ao salvar observação: {e}")
    st.query_params.clear()

# NAVEGAÇÃO LATERAL
st.sidebar.title("Conselho de Classe")
st.sidebar.markdown("---")

if st.sidebar.button("📁 Tela de Upload / Processamento", use_container_width=True):
    st.session_state.dadosCarregados = False
    st.rerun()

if st.sidebar.button("📊 Ficha do Conselho (Dashboard)", use_container_width=True):
    st.session_state.dadosCarregados = True
    st.rerun()

# -----------------------------------------------------------------------------
# EXTRAÇÃO DE DADOS NAPNE / INCLUSÃO
# -----------------------------------------------------------------------------
def extrairDadosInclusao(texto_completo):
    textoLimpo = texto_completo.lower()
    dados = {
        'Necessidades Especiais': 'Não',
        'Tipo de Necessidade Especial': '-',
        'Transtorno': 'Não',
        'Tipo de Transtorno': '-',
        'Superdotação': 'Não',
        'Tipo de Superdotação': '-'
    }
    if "necessidades especiais" in textoLimpo:
        trecho = re.search(r'necessidades\s+especiais\s*(?:.*\n?){0,3}?(sim|não)', textoLimpo)
        if trecho and "sim" in trecho.group(1):
            dados['Necessidades Especiais'] = 'Sim'
            
    if "transtorno" in textoLimpo:
        trecho = re.search(r'transtorno\s*(?:.*\n?){0,5}?(sim|não)', textoLimpo)
        if trecho and "sim" in trecho.group(1):
            dados['Transtorno'] = 'Sim'
            
    if "superdotação" in textoLimpo:
        trecho = re.search(r'superdotação\s*(?:.*\n?){0,5}?(sim|não)', textoLimpo)
        if trecho and "sim" in trecho.group(1):
            dados['Superdotação'] = 'Sim'

    return dados

# -----------------------------------------------------------------------------
# EXTRAÇÃO PRINCIPAL DO PDF (NOTAS E FREQUÊNCIAS DO SUAP)
# -----------------------------------------------------------------------------
def extrairDados(arquivosPdf):
    dadosFinais = []
    numeroChamada = 1

    for arquivo in arquivosPdf:
        try:
            memoriaPdf = io.BytesIO(arquivo.getvalue())
            leitorPdf = PdfReader(memoriaPdf)
            textoCompleto = ""
            for pag in leitorPdf.pages:
                textoCompleto += (pag.extract_text() or "") + "\n"

            linhas = textoCompleto.split('\n')

            # Nome do Aluno
            nomeAluno = "Não Identificado"
            matchNome = re.search(r"Alunoa:\s*(.*?)\s*Matrícula:", textoCompleto, re.DOTALL | re.IGNORECASE)
            if not matchNome:
                matchNome = re.search(r"Aluno:\s*(.*?)\s*Matrícula:", textoCompleto, re.DOTALL | re.IGNORECASE)
            if matchNome:
                nomeAluno = " ".join(matchNome.group(1).split())
            else:
                nomeAluno = arquivo.name.replace(".pdf", "").strip()

            # Matrícula / Prontuário
            matriculaAluno = "Não Identificada"
            matchMat = re.search(r"(?:Matrícula|Prontuário|prontuario):\s*(.{9})", textoCompleto, re.IGNORECASE)
            if matchMat:
                matriculaAluno = matchMat.group(1).strip()

            # Série / Turma
            serieAluno = "Não Identificada"
            matchSerie = re.search(r"(\d{5}\.\d\.[A-Z0-9\.]+)", textoCompleto)
            if matchSerie:
                serieAluno = matchSerie.group(1).strip()

            dadosNapne = extrairDadosInclusao(textoCompleto)

            # Processamento de Disciplinas e Notas
            mapeamentoDisciplinas = {}
            for linha in linhas:
                linha_str = linha.strip()
                if any(p in linha_str for p in ["Notas das etapas", "Faltas nas etapas", "Diário", "Disciplina", "Total"]):
                    continue

                if re.search(r'[A-Z]{3,4}\.\d{4,5}|[A-Z0-9]{4,5}', linha_str):
                    tokens = linha_str.split()
                    
                    # Procura % de frequência
                    freq_val = 100.0
                    for tok in tokens:
                        if "%" in tok:
                            try:
                                freq_val = float(tok.replace("%", "").replace(",", "."))
                                break
                            except ValueError:
                                pass

                    # Isola valores numéricos das notas
                    numeros = []
                    for t in tokens:
                        t_limpo = t.replace(',', '.')
                        if re.match(r'^\d+(\.\d+)?$', t_limpo):
                            numeros.append(float(t_limpo))

                    # Extração dos 4 bimestres e média final
                    notas = [0.0, 0.0, 0.0, 0.0]
                    mediaFinal = 0.0
                    
                    if len(numeros) >= 4:
                        notas = numeros[:4]
                        if len(numeros) >= 5:
                            mediaFinal = numeros[4]
                        else:
                            notasValidas = [n for n in notas if n > 0]
                            mediaFinal = sum(notasValidas) / len(notasValidas) if notasValidas else 0.0
                    
                    # Nome da disciplina
                    partesTexto = [t for t in tokens if not re.match(r'^\d', t) and "%" not in t and t not in ["Cursando", "Aprovado", "Retido"]]
                    nomeDisp = " ".join(partesTexto).strip()

                    if len(nomeDisp) > 2:
                        mapeamentoDisciplinas[nomeDisp] = {
                            'notas': notas,
                            'mediaFinal': mediaFinal,
                            'freqFinal': freq_val
                        }

            for nomeDisp, infoDisp in mapeamentoDisciplinas.items():
                tecnico = any(kw in nomeDisp.upper() for kw in tecnicas)
                nucleoVal = "Técnico" if tecnico else "Comum"

                dadosFinais.append({
                    'Nº Chamada': int(numeroChamada),
                    'Aluno': nomeAluno,
                    'Matrícula': matriculaAluno,
                    'Série': serieAluno,
                    'Disciplina': nomeDisp,
                    '1º BI': infoDisp['notas'][0],
                    '2º BI': infoDisp['notas'][1],
                    '3º BI': infoDisp['notas'][2],
                    '4º BI': infoDisp['notas'][3],
                    'Média Final': infoDisp['mediaFinal'],
                    'Freq. Final': infoDisp['freqFinal'],
                    'Núcleo': nucleoVal,
                    'Observações': '',
                    'Necessidades Especiais': dadosNapne['Necessidades Especiais'],
                    'Tipo de Necessidade Especial': dadosNapne['Tipo de Necessidade Especial'],
                    'Transtorno': dadosNapne['Transtorno'],
                    'Tipo de Transtorno': dadosNapne['Tipo de Transtorno'],
                    'Superdotação': dadosNapne['Superdotação'],
                    'Tipo de Superdotação': dadosNapne['Tipo de Superdotação']
                })

            numeroChamada += 1

        except Exception as e:
            st.error(f"Erro ao processar o arquivo {arquivo.name}: {e}")

    return pd.DataFrame(dadosFinais)

# -----------------------------------------------------------------------------
# TELA 1: UPLOAD DE ARQUIVOS
# -----------------------------------------------------------------------------
if not st.session_state.dadosCarregados:
    st.title("Upload de PDFs")
    st.subheader("Selecione a sala correspondente e faça o upload dos relatórios em PDF.")

    salaSelecionada = st.selectbox("Selecione a Sala:", list(DICIONARIO_SALAS.keys()))
    st.session_state.salaAtiva = salaSelecionada
    arquivosEnviados = st.file_uploader(
        "Faça o upload dos relatórios em PDF:", 
        type=["pdf"], 
        accept_multiple_files=True, 
        key=f"uploader_{salaSelecionada}"
    )

    if st.button("PROCESSAR E ATUALIZAR DASHBOARD"):
        if arquivosEnviados:
            with st.spinner("Processando arquivos e atualizando planilhas de notas..."):
                BDNovo = extrairDados(arquivosEnviados)

                linkSalaAtiva = DICIONARIO_SALAS[salaSelecionada]
                df_atual = conn.read(spreadsheet=linkSalaAtiva)
                
                df_final = pd.concat([df_atual, BDNovo], ignore_index=True)
                df_final = df_final.drop_duplicates(subset=["Aluno", "Disciplina"], keep="last")

                if not df_final.empty:
                    conn.update(spreadsheet=linkSalaAtiva, data=df_final)

                    # Salva JSON local estruturado
                    dicionario_dados = df_final.to_dict(orient="records")
                    with open("dados_alunos.json", "w", encoding="utf-8") as f:
                        json.dump(dicionario_dados, f, ensure_ascii=False, indent=4)

                    st.session_state.salaAtiva = salaSelecionada
                    st.session_state.dadosCarregados = True
                    st.rerun()
                else:
                    st.error("Não foi possível extrair dados estruturados válidos.")
        else:
            st.error("Por favor, selecione e envie os arquivos PDF para processar.")

# -----------------------------------------------------------------------------
# TELA 2: VISUALIZAÇÃO DO DASHBOARD (HTML / IFRAME)
# -----------------------------------------------------------------------------
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
        prontuario = str(item.get("Matrícula") or item.get("prontuario") or "Sem Prontuário").strip()
        nome = str(item.get("Aluno", "")).strip()

        if nome == "Não Identificado" or not nome:
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

            freq_val = item.get("Freq. Final")
            try:
                freq_val = float(freq_val)
            except (ValueError, TypeError):
                freq_val = 100.0

            obs_val = str(item.get("Observações", ""))
            if obs_val.lower() == "nan" or obs_val.lower() == "none":
                obs_val = ""

            alunosMapeados[prontuario] = {
                "prontuario": prontuario,
                "nome": nome,
                "curso": item.get("Série", "Técnico Integrado"),
                "turma": st.session_state.salaAtiva,
                "frequencia": freq_val,
                "napne": len(pneTexto) > 0,
                "pneInfo": infoNapne,
                "deliberacao": obs_val,
                "disciplinas": []
            }

        def tratar_nota(v):
            if v is None or pd.isna(v): 
                return None
            try: 
                return float(str(v).replace(',', '.'))
            except ValueError: 
                return None

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
        st.error("O arquivo 'index.html' não foi encontrado na raiz da aplicação.")
