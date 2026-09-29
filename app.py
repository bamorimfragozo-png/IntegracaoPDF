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

# CAPTURA DE SALVAMENTO DE OBSERVAÇÕES VIA QUERY PARAMS (IFRAME -> STREAMLIT)
query_params = st.query_params
if "action" in query_params and query_params["action"] == "salvar_obs":
    aluno_alvo = query_params.get("aluno", "")
    nova_obs = query_params.get("obs", "")
    sala_alvo = st.session_state.salaAtiva
    linkSala = DICIONARIO_SALAS[sala_alvo]
    
    df_sheet = conn.read(spreadsheet=linkSala)
    if "Aluno" in df_sheet.columns and "Observações" in df_sheet.columns:
        df_sheet.loc[
            df_sheet["Aluno"].astype(str).str.strip().str.upper() == aluno_alvo.strip().upper(), 
            "Observações"
        ] = nova_obs
        conn.update(spreadsheet=linkSala, data=df_sheet)
        st.toast(f"Observações/Deliberação de {aluno_alvo} salvas com sucesso!", icon="✅")
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
# FUNÇÃO DE EXTRAÇÃO DE DADOS (BASEADA NO CodigoJunho)
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

def extrairDados(arquivosPdf):
    dadosFinais = []
    mapaNapneTemporario = {}
    dadosRastreamento = {"numeroChamada": 1, "ultimoAlunoLido": "", "ultimoNomeVisto": None}

    def processarLinhasNome(linha, nomeNestaPagina):
        if "Aluno" in linha or "Nome" in linha:
            linha_limpa = re.split(r'\bMatrícula\b', linha, flags=re.IGNORECASE)[0]
            partes = linha_limpa.split(":")
            if len(partes) > 1:
                return partes[-1].strip()
            return linha_limpa.replace("Aluno(a)", "").replace("Aluno", "").replace("Nome", "").strip()
        return nomeNestaPagina

    def processarPaginasPdf(paginaIndex, pagina, leitorPdf, textoCompleto, arquivo):
        textoCompleto += pagina.extract_text() + "\n"
        linhasPag = textoCompleto.split('\n')

        def iterarLinhasNome(idx, nomeAtual):
            if idx >= len(linhasPag):
                return nomeAtual
            novoNome = processarLinhasNome(linhasPag[idx], nomeAtual)
            return iterarLinhasNome(idx + 1, novoNome)
            
        nomeNestaPagina = iterarLinhasNome(0, "Não Identificado")
        
        if nomeNestaPagina == "Não Identificado" or not nomeNestaPagina.strip():
            nomeNestaPagina = arquivo.name.replace(".pdf", "").strip()
            
        if dadosRastreamento["ultimoAlunoLido"] != "" and nomeNestaPagina != dadosRastreamento["ultimoAlunoLido"]:
            dadosRastreamento["numeroChamada"] += 1
        
        dadosRastreamento["ultimoAlunoLido"] = nomeNestaPagina
        return textoCompleto

    def buscarMatricula(idx, linhas, matriculaAluno):
        if idx >= len(linhas):
            return matriculaAluno
        linha = linhas[idx]
        termos = ["matrícula", "matricula", "prontuário", "prontuario"]
        for termo in termos:
            if termo in linha.lower():
                buscaBT = re.search(r"cula:\s*(.{9})", linha, re.IGNORECASE)
                if buscaBT:
                    return buscaBT.group(1).strip()
        return buscarMatricula(idx + 1, linhas, matriculaAluno)

    def verificarFiltroPalavras(linha):
        palavras = ["Notas das etapas", "Faltas nas etapas", "Diário", "Disciplina", "Total", "Este documento"]
        return any(p in linha for p in palavras)

    def extrairFrequencia(idx, tokens, calculoFreq):
        if idx >= len(tokens):
            return calculoFreq
        if "%" in tokens[idx]:
            try:
                return float(tokens[idx].replace("%", "").replace(",", "."))
            except ValueError:
                pass
        return extrairFrequencia(idx + 1, tokens, calculoFreq)

    def filtrarTokens(idx, partesDados, tokensFiltrados):
        if idx >= len(partesDados):
            return tokensFiltrados
        tok = partesDados[idx]
        if tok in ["Cursando", "(Aguarda", "Carga", "Horária)", "Horária", "Aprovado", "Retido"] or "%" in tok:
            return filtrarTokens(idx + 1, partesDados, tokensFiltrados)
        if tok == "-" or tok.replace(',', '.').replace('.', '', 1).isdigit():
            tokensFiltrados.append(tok)
        return filtrarTokens(idx + 1, partesDados, tokensFiltrados)

    def preencherEtapas(etapa, pagDado, dadosTabela, notas, faltas):
        if etapa >= 4:
            return pagDado
        if pagDado < len(dadosTabela):
            valNota = dadosTabela[pagDado].replace(',', '.')
            notas[etapa] = float(valNota) if valNota.replace('.', '', 1).isdigit() else 0.0
            pagDado += 1
        if pagDado < len(dadosTabela):
            valFalta = dadosTabela[pagDado]
            faltas[etapa] = float(valFalta) if valFalta.isdigit() else 0.0
            pagDado += 1
        return preencherEtapas(etapa + 1, pagDado, dadosTabela, notas, faltas)

    def processarLinhasDisciplinas(idx, linhas, mapeamentoDisciplinas):
        if idx >= len(linhas):
            return mapeamentoDisciplinas
        linha = linhas[idx]
        
        if verificarFiltroPalavras(linha):
            return processarLinhasDisciplinas(idx + 1, linhas, mapeamentoDisciplinas)

        linhaLimpa = re.sub(r'^\d{5,6}\s+', '', linha.strip())
        if not re.search(r'[A-Z]{3,4}\.\d{4,5}|[A-Z0-9]5,', linhaLimpa):
            return processarLinhasDisciplinas(idx + 1, linhas, mapeamentoDisciplinas)

        tokens = linhaLimpa.split()
        
        def separarTextoDados(t_idx, passou, p_texto, p_dados):
            if t_idx >= len(tokens):
                return p_texto, p_dados
            token = tokens[t_idx]
            if (',' in token and token.replace(',', '').isdigit()) and not passou:
                passou = True
            if not passou:
                p_texto.append(token)
            else:
                p_dados.append(token)
            return separarTextoDados(t_idx + 1, passou, p_texto, p_dados)

        partesTexto, partesDados = separarTextoDados(0, False, [], [])
        nomeDisciplina = " ".join(partesTexto).strip()
        
        if not nomeDisciplina or len(partesDados) < 5:
            return processarLinhasDisciplinas(idx + 1, linhas, mapeamentoDisciplinas)

        calculoFreq = extrairFrequencia(0, tokens, 100.0)
        tokensFiltrados = filtrarTokens(0, partesDados, [])
        dadosTabela = tokensFiltrados[4:]

        notas = [0.0, 0.0, 0.0, 0.0]
        faltas = [0.0, 0.0, 0.0, 0.0]
        
        pagDado = preencherEtapas(0, 0, dadosTabela, notas, faltas)

        if pagDado < len(dadosTabela):
            valMedia = dadosTabela[pagDado].replace(',', '.')
            if valMedia.replace('.', '', 1).isdigit():
                mediaFinal = float(valMedia)
            else:
                notasLancadas = [n for n in notas if n > 0]
                mediaFinal = sum(notasLancadas) / len(notasLancadas) if notasLancadas else 0.0
        else:
            notasLancadas = [n for n in notas if n > 0]
            mediaFinal = sum(notasLancadas) / len(notasLancadas) if notasLancadas else 0.0

        if len(nomeDisciplina) > 3:
            mapeamentoDisciplinas[nomeDisciplina] = {
                'notas': notas,
                'faltas': faltas,
                'mediaFinal': mediaFinal,
                'freqFinal': calculoFreq
            }
        return processarLinhasDisciplinas(idx + 1, linhas, mapeamentoDisciplinas)

    def processarMapeamentoDisciplinas(chaves, idx_d, mapa, nomeAluno, matriculaAluno, serieAluno, dadosNapne):
        if idx_d >= len(chaves):
            return
        nomeDisp = chaves[idx_d]
        infoDisp = mapa[nomeDisp]
        
        tecnico = any(kw in nomeDisp.upper() for kw in tecnicas)
        nucleoVal = "Técnico" if tecnico else "Comum"

        dadosFinais.append({
            'Nº Chamada': int(dadosRastreamento["numeroChamada"]),
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
        processarMapeamentoDisciplinas(chaves, idx_d + 1, mapa, nomeAluno, matriculaAluno, serieAluno, dadosNapne)

    def iterarArquivosPdf(idx_arq):
        if idx_arq >= len(arquivosPdf):
            return
        arquivo = arquivosPdf[idx_arq]
        memoriaPdf = io.BytesIO(arquivo.getvalue())
        try:
            leitorPdf = PdfReader(memoriaPdf)
        except Exception as e:
            st.error(f"Erro ao ler o arquivo {arquivo.name}: {e}")
            iterarArquivosPdf(idx_arq + 1)
            return

        textoCompleto = ""
        for p_idx, pag in enumerate(leitorPdf.pages):
            textoCompleto = processarPaginasPdf(p_idx, pag, leitorPdf, textoCompleto, arquivo)
            
        linhas = textoCompleto.split('\n')

        nomeAluno = "Não Identificado"
        matriculaAluno = "Não Identificada"
        serieAluno = "Não Identificada"

        matchNome = re.search(r"Alunoa:\s*(.*?)\s*Matrícula:", textoCompleto, re.DOTALL | re.IGNORECASE)
        if matchNome:
            nomeAluno = " ".join(matchNome.group(1).split())

        matchSerie = re.search(r"(\d{5}\.\d\.[A-Z0-9\.]+)", textoCompleto)
        if matchSerie:
            serieAluno = matchSerie.group(1).strip()

        matriculaAluno = buscarMatricula(0, linhas, matriculaAluno)

        if nomeAluno == "Não Identificado" or not nomeAluno.strip():
            nomeAluno = arquivo.name.split('.')[0].strip()

        if nomeAluno:
            dadosNapne = extrairDadosInclusao(textoCompleto)
            mapeamentoDisciplinas = processarLinhasDisciplinas(0, linhas, {})
            chavesDisp = list(mapeamentoDisciplinas.keys())
            
            processarMapeamentoDisciplinas(chavesDisp, 0, mapeamentoDisciplinas, nomeAluno, matriculaAluno, serieAluno, dadosNapne)

            if dadosRastreamento["ultimoNomeVisto"] is None:
                dadosRastreamento["ultimoNomeVisto"] = nomeAluno
            if nomeAluno != dadosRastreamento["ultimoNomeVisto"]:
                dadosRastreamento["numeroChamada"] += 1
                dadosRastreamento["ultimoNomeVisto"] = nomeAluno

        iterarArquivosPdf(idx_arq + 1)

    iterarArquivosPdf(0)
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

                if not BDNovo.empty:
                    conn.update(spreadsheet=linkSalaAtiva, data=df_final)

                    # Exportação em JSON estruturado local
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
# TELA 2: VISUALIZAÇÃO DO DASHBOARD (HTML / IFRAME UNIFICADO)
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
