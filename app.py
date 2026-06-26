import streamlit as st
import pandas as pd
import plotly.express as px
from streamlit_gsheets import GSheetsConnection
from pypdf import PdfReader
import io
import re

# CONFIGURAR PÁGINA/CSS
st.set_page_config(page_title="Dashboard Acadêmico", layout="wide")
tecnicas = [
    "ILPR", "MAIN", "ININ", "LDPR", "RDCO", "LPWE", "SOPE",
    "INSO", "IPRE", "BDDA", "PSCO", "PRIN", "CNVI", "SDRE",
    "ASRE", "RSFI", "GCLI", "ELET", "DCAD", "CAUT", "PROG", "PCOE",
    "EDIG", "PRI1", "ELIN", "CISUT", "INTI", "MAPI", "CNCM",
    "CLPR", "REPI", "HIEP", "MIMP", "PRI2"
]

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
    border: 1px solid #ddd;
    border-radius: 8px;
    text-align: left;
}
.stRadio > div {
    flex-direction: row;
    gap: 20px;
}
.info-box {
    background-color: #fdfdfd;
    font-size: 16px;
    padding: 5px 0px;
}
</style>
""", unsafe_allow_html=True)

# CONEXÃO COM PLANILHAS
conn = st.connection("gsheets", type=GSheetsConnection)

DICIONARIO_SALAS = {
    "Redes 1": st.secrets["connections"]["gsheets"]["Redes1"],
    "Redes 2": st.secrets["connections"]["gsheets"]["Redes2"],
    "Redes 3": st.secrets["connections"]["gsheets"]["Redes3"],
    "Automação 1": st.secrets["connections"]["gsheets"]["Automacao1"],
    "Automação 2": st.secrets["connections"]["gsheets"]["Automacao2"],
    "Automação 3": st.secrets["connections"]["gsheets"]["Automacao3"]
}

# ESTADO DE ATUALIZAÇÃO DO DASHBOARD
if ("dadosCarregados" not in st.session_state):
    st.session_state.dadosCarregados = False
if ("pagAluno" not in st.session_state):
    st.session_state.pagAluno = 0
if ("materiaSelecionada" not in st.session_state):
    st.session_state.materiaSelecionada = None
if ("resetObs" not in st.session_state):
    st.session_state.resetObs = 0
if ("salaAtiva" not in st.session_state):
    st.session_state.salaAtiva = "Redes 1"
if ("fotoAluno" not in st.session_state):
    st.session_state.fotoAluno = {}
if ("ordenacao" not in st.session_state):
    st.session_state.ordenacao = "Nota"

# MENU DE NAVEGAÇÃO
st.sidebar.markdown("### Navegação")
if ('salaSelecionada' in locals()): 
    st.session_state.salaAtiva = salaSelecionada

if (st.sidebar.button("Tela de Upload")):
    st.session_state.dadosCarregados = False
    st.session_state.materiaSelecionada = None
    st.session_state.pagAluno = 0
    st.rerun()

if (st.sidebar.button("Dashboard")):
    st.session_state.dadosCarregados = True
    st.session_state.materiaSelecionada = None
    st.session_state.pagAluno = 0
    st.rerun()

# EXTRAÇÃO DE DADOS
def extrair_dados_inclusao(texto_completo):
    # Deixamos em minúsculo para facilitar a busca
    texto_limpo = texto_completo.lower()
    
    dados = {
        'Necessidades Especiais': 'Não',
        'Tipo de Necessidade Especial': '-',
        'Transtorno': 'Não',
        'Tipo de Transtorno': '-',
        'Superdotação': 'Não',
        'Tipo de Superdotação': '-'
    }
    
    # 1. Busca por Necessidades Especiais
    if "necessidades especiais" in texto_limpo:
        # Pega as próximas palavras após o termo para ver se acha um "sim" perdido
        trecho = re.search(r'necessidades\s+especiais\s*(?:.*\n?){0,3}?(sim|não)', texto_limpo)
        if trecho and "sim" in trecho.group(1):
            dados['Necessidades Especiais'] = 'Sim'
            
    # 2. Busca por Transtorno
    if "transtorno" in texto_limpo:
        # No PDF do SUAP, o "Sim" geralmente vem logo abaixo ou próximo do termo
        trecho = re.search(r'transtorno\s*(?:.*\n?){0,5}?(sim|não)', texto_limpo)
        if trecho and "sim" in trecho.group(1):
            dados['Transtorno'] = 'Sim'
            
    # 3. Busca por Superdotação
    if "superdotação" in texto_limpo:
        trecho = re.search(r'superdotação\s*(?:.*\n?){0,5}?(sim|não)', texto_limpo)
        if trecho and "sim" in trecho.group(1):
            dados['Superdotação'] = 'Sim'

    return dados

def extrairDados(arquivosPdf):
    dadosFinais = []
    mapaNapneTemporario = {}
    
    # Contexto mutável compartilhado para simular o comportamento dos loops externos anterior
    contexto_chamada = {"numeroChamada": 1, "ultimoAlunoLido": "", "ultimoNomeVisto": None}

    # FUNÇÕES SUBSTITUTAS DOS LOOPS 'FOR'

    def processar_linhas_nome(linha, nomeNestaPagina):
        if "Aluno" in linha or "Nome" in linha:
            # 1. Remove tudo a partir da palavra 'Matrícula'
            linha_limpa = re.split(r'\bMatrícula\b', linha, flags=re.IGNORECASE)[0]
        
            # 2. Divide nos dois-pontos (:) para separar os rótulos do nome
            partes = linha_limpa.split(":")
        
            # 3. Pega a última parte (que será o nome) e limpa os espaços
            if len(partes) > 1:
                return partes[-1].strip()
        
            # Caso não haja dois-pontos, remove os rótulos diretos
            return linha_limpa.replace("Aluno(a)", "").replace("Aluno", "").replace("Nome", "").strip()
        
        return nomeNestaPagina
    def processar_paginas_pdf(paginaIndex, pagina, leitorPdf, textoCompleto, arquivo):
        textoCompleto += pagina.extract_text() + "\n"
        textoPagina = textoCompleto
        nomeNestaPagina = "Não Identificado"
        
        # Substituição do for linha in textoPagina.split('\n')
        linhas_pag = textoPagina.split('\n')
        def iterar_linhas_nome(idx, nome_atual):
            if idx >= len(linhas_pag):
                return nome_atual
            novo_nome = processar_linhas_nome(linhas_pag[idx], nome_atual)
            return iterar_linhas_nome(idx + 1, novo_nome)
            
        nomeNestaPagina = iterar_linhas_nome(0, nomeNestaPagina)
        
        if (nomeNestaPagina == "Não Identificado" or not nomeNestaPagina.strip()):
            nomeNestaPagina = arquivo.name.replace(".pdf", "").strip()
            
        if (contexto_chamada["ultimoAlunoLido"] != "" and nomeNestaPagina != contexto_chamada["ultimoAlunoLido"]):
            contexto_chamada["numeroChamada"] += 1
        
        contexto_chamada["ultimoAlunoLido"] = nomeNestaPagina
        return textoPagina

    def buscar_matricula(idx, linhas, matriculaAluno):
        if idx >= len(linhas):
            return matriculaAluno
        linha = linhas[idx]
        
        termos = ["matrícula", "matricula", "prontuário", "prontuario"]
        def checar_termos(t_idx):
            if t_idx >= len(termos):
                return None
            if termos[t_idx] in linha.lower():
                buscaBT = re.search(r"cula:\s*(.{9})", linha, re.IGNORECASE)
                if buscaBT:
                    return buscaBT.group(1).strip()
            return checar_termos(t_idx + 1)
            
        resultado = checar_termos(0)
        if resultado:
            return resultado
        return buscar_matricula(idx + 1, linhas, matriculaAluno)

    def extrair_linhas_metadados(idx, linhas, nomeAluno, serieAluno):
        # Mantida apenas para compatibilidade, retorna os valores sem alterar nada
        return nomeAluno, serieAluno

    def verificar_filtro_palavras(linha):
        palavras = ["Notas das etapas", "Faltas nas etapas", "Diário", "Disciplina", "Total", "Este documento"]
        def iterar_palavras(p_idx):
            if p_idx >= len(palavras):
                return False
            if palavras[p_idx] in linha:
                return True
            return iterar_palavras(p_idx + 1)
        return iterar_palavras(0)

    def extrair_frequencia(idx, tokens, calculoFreq):
        if idx >= len(tokens):
            return calculoFreq
        if "%" in tokens[idx]:
            try:
                return float(tokens[idx].replace("%", "").replace(",", "."))
            except ValueError:
                pass
            return calculoFreq
        return extrair_frequencia(idx + 1, tokens, calculoFreq)

    def filtrar_tokens(idx, partesDados, tokensFiltrados):
        if idx >= len(partesDados):
            return tokensFiltrados
        tok = partesDados[idx]
        if (tok in ["Cursando", "(Aguarda", "Carga", "Horária)", "Horária", "Aprovado", "Retido"] or "%" in tok):
            return filtrar_tokens(idx + 1, partesDados, tokensFiltrados)
        if (tok == "-" or tok.replace(',', '.').replace('.', '', 1).isdigit()):
            tokensFiltrados.append(tok)
        return filtrar_tokens(idx + 1, partesDados, tokensFiltrados)

    def preencher_etapas(etapa, pagDado, dadosTabela, notas, faltas):
        if etapa >= 4:
            return pagDado
        if (pagDado < len(dadosTabela)):
            valNota = dadosTabela[pagDado].replace(',', '.')
            if (valNota.replace('.', '', 1).isdigit()):
                notas[etapa] = float(valNota)
            else:
                notas[etapa] = 0.0
            pagDado += 1
        if (pagDado < len(dadosTabela)):
            valFalta = dadosTabela[pagDado]
            if (valFalta.isdigit()):
                faltas[etapa] = float(valFalta)
            else:
                faltas[etapa] = 0.0
            pagDado += 1
        return preencher_etapas(etapa + 1, pagDado, dadosTabela, notas, faltas)

    def recolher_notas_lancadas(idx, notas, notasLancadas):
        if idx >= len(notas):
            return notasLancadas
        if notas[idx] > 0:
            notasLancadas.append(notas[idx])
        return recolher_notas_lancadas(idx + 1, notas, notasLancadas)

    def processar_linhas_disciplinas(idx, linhas, mapeamentoDisciplinas):
        if idx >= len(linhas):
            return mapeamentoDisciplinas
        linha = linhas[idx]
        
        if verificar_filtro_palavras(linha):
            return processar_linhas_disciplinas(idx + 1, linhas, mapeamentoDisciplinas)

        linhaLimpa = re.sub(r'^\d{5,6}\s+', '', linha.strip())
        if (not re.search(r'[A-Z]{3,4}\.\d{4,5}|\([A-Z0-9]{5,}\)', linhaLimpa)):
            return processar_linhas_disciplinas(idx + 1, linhas, mapeamentoDisciplinas)

        tokens = linhaLimpa.split()
        
        def separar_texto_dados(t_idx, passou, p_texto, p_dados):
            if t_idx >= len(tokens):
                return p_texto, p_dados
            token = tokens[t_idx]
            if ((',' in token and token.replace(',', '').isdigit()) and not passou):
                passou = True
            if (not passou):
                p_texto.append(token)
            else:
                p_dados.append(token)
            return separar_texto_dados(t_idx + 1, passou, p_texto, p_dados)

        partesTexto, partesDados = separar_texto_dados(0, False, [], [])
        nomeDisciplina = " ".join(partesTexto).strip()
        
        if (not nomeDisciplina or len(partesDados) < 5):
            return processar_linhas_disciplinas(idx + 1, linhas, mapeamentoDisciplinas)

        calculoFreq = extrair_frequencia(0, tokens, 100.0)
        tokensFiltrados = filtrar_tokens(0, partesDados, [])
        dadosTabela = tokensFiltrados[4:]

        notas = [0.0, 0.0, 0.0, 0.0]
        faltas = [0.0, 0.0, 0.0, 0.0]
        
        pagDado = preencher_etapas(0, 0, dadosTabela, notas, faltas)

        mediaFinal = 0.0
        if (pagDado < len(dadosTabela)):
            valMedia = dadosTabela[pagDado].replace(',', '.')
            if (valMedia.replace('.', '', 1).isdigit()):
                mediaFinal = float(valMedia)
            else:
                notasLancadas = recolher_notas_lancadas(0, notas, [])
                mediaFinal = sum(notasLancadas) / len(notasLancadas) if notasLancadas else 0.0
        else:
            notasLancadas = recolher_notas_lancadas(0, notas, [])
            mediaFinal = sum(notasLancadas) / len(notasLancadas) if notasLancadas else 0.0

        if (len(nomeDisciplina) > 3):
            mapeamentoDisciplinas[nomeDisciplina] = {
                'notas': notas,
                'faltas': faltas,
                'mediaFinal': mediaFinal,
                'freqFinal': calculoFreq
            }
        return processar_linhas_disciplinas(idx + 1, linhas, mapeamentoDisciplinas)

    def checar_tecnico(idx_t, nomeDisp):
        if idx_t >= len(tecnicas):
            return False
        if tecnicas[idx_t] in nomeDisp.upper():
            return True
        return checar_tecnico(idx_t + 1, nomeDisp)

    def processar_mapeamento_disciplinas(chaves, idx_d, mapa, nomeAluno, matriculaAluno, serieAluno, dados_napne):
    # Condição de parada da recursão: se percorreu todas as disciplinas do aluno
    if idx_d >= len(chaves):
        return
    
    nomeDisp = chaves[idx_d]
    siglaDisp = mapa[nomeDisp]
    
    # --- Início do seu bloco original de busca de notas/faltas ---
    # (Ele continua igual, buscando N1, F1, N2, F2... no PDF)
    def buscar_notas_faltas(idx_l, n1_a, f1_a, n2_a, f2_a, n3_a, f3_a, n4_a, f4_a, med_a, totF_a, Sit_a, obs_a):
        if idx_l >= len(linhas):
            return n1_a, f1_a, n2_a, f2_a, n3_a, f3_a, n4_a, f4_a, med_a, totF_a, Sit_a, obs_a
            
        linha = linhas[idx_l].strip()
        if linha.startswith(nomeDisp) or linha.startswith(siglaDisp):
            partes = linha.split()
            if len(partes) >= 12:
                # Exemplo padrão de captura do seu código original
                return (partes[-11], partes[-10], partes[-9], partes[-8], 
                        partes[-7], partes[-6], partes[-5], partes[-4], 
                        partes[-3], partes[-2], partes[-1], "-")
        return buscar_notas_faltas(idx_l + 1, n1_a, f1_a, n2_a, f2_a, n3_a, f3_a, n4_a, f4_a, med_a, totF_a, Sit_a, obs_a)
        
    n1, f1, n2, f2, n3, f3, n4, f4, med, totF, Sit, obs = buscar_notas_faltas(0, "-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-")
    # --- Fim do bloco original ---

    # Grava na lista final associando cada disciplina às colunas da planilha do Google Sheets
    dadosFinais.append({
        'Nº Chamada': int(contexto_chamada["numeroChamada"]),
        'Aluno': nomeAluno,
        'Matrícula': matriculaAluno,
        'Série': serieAluno,
        'Disciplina': nomeDisp,
        'Sigla': siglaDisp,
        'B1': n1, 'F1': f1, 
        'B2': n2, 'F2': f2, 
        'B3': n3, 'F3': f3, 
        'B4': n4, 'F4': f4,
        'Média': med, 
        'Faltas': totF, 
        'Resultado': Sit, 
        'Observações': obs,
        
        # Colunas de inclusão mapeadas com as chaves exatas do seu Sheets:
        'Portador Necessidades Especiais': dados_napne['Necessidades Especiais'],
        'Tipo Necessidade Especial': dados_napne['Tipo de Necessidade Especial'],
        'Portador Transtorno': dados_napne['Transtorno'],
        'Tipo Transtorno': dados_napne['Tipo de Transtorno'],
        'Portador Superdotação': dados_napne['Superdotação'],
        'Superdotação': dados_napne['Tipo de Superdotação']
    })
    
    # Chamada recursiva para a próxima disciplina do aluno, repassando o dicionário completo
    processar_mapeamento_disciplinas(chaves, idx_d + 1, mapa, nomeAluno, matriculaAluno, serieAluno, dados_napne)

    def processar_fotos(leitorPdf):
        try:
            primeiraPagina = leitorPdf.pages[0]
            # Se a página contiver imagens extraíveis diretamente
            if hasattr(primeiraPagina, 'images') and len(primeiraPagina.images) > 0:
                # Retorna os bytes da primeira imagem encontrada na página do aluno
                return primeiraPagina.images[0].data
        except Exception:
            pass
        return None

    def iterar_arquivos_pdf(idx_arq):
        if idx_arq >= len(arquivosPdf):
            return
        arquivo = arquivosPdf[idx_arq]
        memoriaPdf = io.BytesIO(arquivo.getvalue())
        try:
            leitorPdf = PdfReader(memoriaPdf)
        except Exception as e:
            st.error(f"Erro ao ler o arquivo {arquivo.name}: {e}")
            iterar_arquivos_pdf(idx_arq + 1)
            return

        textoCompleto = ""
        paginas = leitorPdf.pages
        
        def iterar_paginas(p_idx, txt):
            if p_idx >= len(paginas):
                return txt
            novo_txt = processar_paginas_pdf(p_idx, paginas[p_idx], leitorPdf, txt, arquivo)
            return iterar_paginas(p_idx + 1, novo_txt)

        textoCompleto = iterar_paginas(0, textoCompleto)
        linhas = textoCompleto.split('\n')
        textoNapne = textoCompleto.replace("\n", " ")

        dados_napne = extrair_dados_inclusao(textoCompleto)

        chaves_disp = list(mapeamentoDisciplinas.keys())
        processar_mapeamento_disciplinas(
            chaves_disp, 
            0, 
            mapeamentoDisciplinas, 
            nomeAluno, 
            matriculaAluno, 
            serieAluno, 
            dados_napne
        )
        
        contexto_chamada["numeroChamada"] += 1
        
        nomeAluno = "Não Identificado"
        matriculaAluno = "Não Identificada"
        serieAluno = "Não Identificada"
        necEspeciais = "Não"
        tipoNecEspecial = "-"
        transtorno = "Não"
        tipoTranstorno = "-"
        superdotacao = "Não"
        tipoSuperdotacao = "-"

        # 🎯 EXTRAÇÃO ATUALIZADA VIA REGEX (À PROVA DE QUEBRAS DE LINHA)
        
        # 1. Procura o Nome que vem logo a seguir a "BOLETIM DE NOTAS INDIVIDUAL"
        match_nome = re.search(
            r"Aluno\(a\):\s*(.*?)\s*Matrícula:",
            textoCompleto,
            re.DOTALL | re.IGNORECASE
        )

        if match_nome:
            nomeAluno = " ".join(match_nome.group(1).split())

        # 2. Procura a Turma/Série baseada no padrão numérico do IF (ex: 20261.3.BTV...)
        match_serie = re.search(r"(\d{5}\.\d\.[A-Z0-9\.]+)", textoCompleto)
        if match_serie:
            serieAluno = match_serie.group(1).strip()

        # 3. Procura a Matrícula chamando a sua função recursiva original
        matriculaAluno = buscar_matricula(0, linhas, matriculaAluno)

        # RegEx NAPNE (Seu bloco original mantido)
        match = re.search(r"Portador\(a\)\s+de\s+Necessidades\s+Especiais\s+(Sim|Não)", textoNapne, re.IGNORECASE)
        if match: necEspeciais = match.group(1)
        match = re.search(r"Tipo\s+de\s+Necessidade\s+Especial\s+-?\s*(.+?)\s*(?=Portador\(a\)|$)", textoNapne, re.IGNORECASE)
        if match: tipoNecEspecial = match.group(1)
        match = re.search(r"Portador\(a\)\s+de\s+Transtorno\s+(Sim|Não)", textoNapne, re.IGNORECASE)
        if match: transtorno = match.group(1)
        match = re.search(r"Tipo\s+de\s+Transtorno\s+-?\s*(.+?)\s*(?=Portador\(a\)|$)", textoNapne, re.IGNORECASE)
        if match: tipoTranstorno = match.group(1)
        match = re.search(r"Portador\(a\)\s+de\s+Superdotação\s+(Sim|Não)", textoNapne, re.IGNORECASE)
        if match: superdotacao = match.group(1)
        match = re.search(r"Superdotação\s+-?\s*(.+?)\s*$", textoNapne, re.IGNORECASE)
        if match: tipoSuperdotacao = match.group(1)

        # Proteção contra falhas: se não extrair nada, usa o nome do arquivo de forma limpa
        if (nomeAluno == "Não Identificado" or not nomeAluno.strip()):
            nomeAluno = arquivo.name.split('.')[0].strip()

        # Grava a foto usando a chave correta com o nome do aluno que acabou de ser extraído
        fotos = processar_fotos(leitorPdf)
        if (fotos):
            st.session_state.fotoAluno[nomeAluno] = fotos
        
        mapeamentoDisciplinas = processar_linhas_disciplinas(0, linhas, {})
        processar_mapeamento_disciplinas(list(mapeamentoDisciplinas.keys()), 0, mapeamentoDisciplinas, nomeAluno, matriculaAluno, serieAluno, necEspeciais, tipoNecEspecial, transtorno, tipoTranstorno, superdotacao, tipoSuperdotacao)

        if (contexto_chamada["ultimoNomeVisto"] is None):
            contexto_chamada["ultimoNomeVisto"] = nomeAluno
        
        if (nomeAluno != contexto_chamada["ultimoNomeVisto"]):
            contexto_chamada["numeroChamada"] += 1
            contexto_chamada["ultimoNomeVisto"] = nomeAluno

        if (nomeAluno and nomeAluno != "Não Identificado"):
            mapaNapneTemporario[nomeAluno.strip().upper()] = {
                'nec': necEspeciais, 'tipNec': tipoNecEspecial,
                'trans': transtorno, 'tipTrans': tipoTranstorno,
                'super': superdotacao, 'tipSuper': tipoSuperdotacao
            }
        iterar_arquivos_pdf(idx_arq + 1)

    def mapear_dados_finais_napne(idx):
        if idx >= len(dadosFinais):
            return
        dado = dadosFinais[idx]
        alunoAlvo = dado['Aluno'].strip().upper()
        if (alunoAlvo in mapaNapneTemporario):
            info = mapaNapneTemporario[alunoAlvo]
            dado['Necessidades Especiais'] = info['nec']
            dado['Tipo de Necessidade Especial'] = info['tipNec']
            dado['Transtorno'] = info['trans']
            dado['Tipo de Transtorno'] = info['tipTrans']
            dado['Superdotação'] = info['super']
            dado['Tipo de Superdotação'] = info['tipSuper']
        mapear_dados_finais_napne(idx + 1)

    # Execução das funções iterativas principais em substituição aos loops principais
    iterar_arquivos_pdf(0)
    mapear_dados_finais_napne(0)
    
    return pd.DataFrame(dadosFinais)


# UPLOAD DOS RELATÓRIOS EM PDF
if (not st.session_state.dadosCarregados):
    st.title("Upload de PDFs")
    st.subheader("Selecione a sala correspondente e faça o upload dos relatórios em PDF.")

    salaSelecionada = st.selectbox("Selecione a Sala:", list(DICIONARIO_SALAS.keys()))
    st.session_state.salaAtiva = salaSelecionada 
    arquivosEnviados = st.file_uploader("Faça o upload de quantos PDFs desejar aqui:", type=["pdf"], accept_multiple_files=True, key=f"uploader_{salaSelecionada}")

    if (st.button("PROCESSAR E ATUALIZAR DASHBOARD")):
        if (arquivosEnviados):
            with st.spinner("Processando arquivos e atualizando planilhas de notas..."):
                BDNovo = extrairDados(arquivosEnviados)

                linkSalaAtiva = DICIONARIO_SALAS[salaSelecionada]
                df_atual = conn.read(spreadsheet=linkSalaAtiva)
                df_final = pd.concat([df_atual, BDNovo], ignore_index=True)
                df_final = df_final.drop_duplicates(subset=["Aluno", "Disciplina"], keep="last")

                if (not BDNovo.empty):
                    conn.update(spreadsheet=linkSalaAtiva, data=df_final) 
                    st.session_state.salaAtiva = salaSelecionada
                    st.session_state.dadosCarregados = True
                    st.session_state.materiaSelecionada = None
                    st.session_state.pagAluno = 0
                    st.rerun()
                else:
                    st.error("Não foi possível extrair dados estruturados válidos.")
        else:
            st.error("Por favor, selecione e envie os arquivos PDF para processar.")

# EXIBIÇÃO VISUAL DO DASHBOARD ACADÊMICO
else:
    if ("salaAtiva" not in st.session_state or not st.session_state.salaAtiva):
        st.info("Nenhum relatório foi carregado ainda.")
        st.write("Faça o upload dos PDFs na tela de Upload para visualizar o Dashboard.")
        st.stop()
    
    st.sidebar.write(f"Visualizando: **{st.session_state.salaAtiva}**")

    linkSalaAtiva = DICIONARIO_SALAS[st.session_state.salaAtiva]
    BD = conn.read(spreadsheet=linkSalaAtiva, ttl="30m")
    
    colunasNumericas = ['1º BI', '2º BI', '3º BI', '4º BI', 'Média Final', 'Freq. Final']
    
    # Substituição do for col in colunasNumericas
    def tratar_colunas_numericas(idx):
        if idx >= len(colunasNumericas):
            return
        col = colunasNumericas[idx]
        if (col in BD.columns):
            BD[col] = pd.to_numeric(BD[col].astype(str).str.replace(',', '.'), errors='coerce').fillna(0.0)
        tratar_colunas_numericas(idx + 1)
        
    tratar_colunas_numericas(0)

    if ('Observações' in BD.columns):
        BD['Observações'] = BD['Observações'].astype(str).replace('nan', '')
    else:
        BD['Observações'] = ""
        
    ordemChamada = BD.sort_values(by='Nº Chamada', ascending=True)
    alunosLista = ordemChamada['Aluno'].unique().tolist()
    
    if (not alunosLista): 
        st.info("Nenhum relatório foi carregado ainda.")
        st.write("Faça o upload dos PDFs na tela de Upload para visualizar o Dashboard.")
        st.stop()
    
    if (st.session_state.pagAluno >= len(alunosLista)):
        st.session_state.pagAluno = 0

    alunoNome = alunosLista[st.session_state.pagAluno]
    BDAluno = BD[BD['Aluno'] == alunoNome].copy()

    # FOTO E IDENTIFICAÇÃO DO ESTUDANTE
    t1, t2 = st.columns([1, 4])
    with t1:
        st.markdown("### Foto")
        if (alunoNome in st.session_state.fotoAluno):
            st.image(st.session_state.fotoAluno[alunoNome], use_container_width=True)
        else:
            st.image("https://via.placeholder.com/150", use_container_width=True)

    with t2:
        st.subheader(f"Nome: {alunoNome}")

        c1, c2 = st.columns(2)
        matriculaVal = BDAluno['Matrícula'].iloc[0] if 'Matrícula' in BDAluno.columns else "Não Informado"
        serieVal = BDAluno['Série'].iloc[0] if 'Série' in BDAluno.columns else "Não Informado"

        c1.markdown(f"<div class='info-box'><b>Matrícula:</b> {matriculaVal}</div>", unsafe_allow_html=True)
        c2.markdown(f"<div class='info-box'><b>Série:</b> {serieVal}</div>", unsafe_allow_html=True)
        
        st.markdown("#### Informações de Inclusão (NAPNE)")
        napCol1, napCol2, napCol3 = st.columns(3)
        
        valPne = BDAluno['Necessidades Especiais'].iloc[0] if 'Necessidades Especiais' in BDAluno.columns else "Não Informado"
        valTipPne = BDAluno['Tipo de Necessidade Especial'].iloc[0] if 'Tipo de Necessidade Especial' in BDAluno.columns else "-"
        valTrans = BDAluno['Transtorno'].iloc[0] if 'Transtorno' in BDAluno.columns else "Não Informado"
        valTipTrans = BDAluno['Tipo de Transtorno'].iloc[0] if 'Tipo de Transtorno' in BDAluno.columns else "-"
        valSuper = BDAluno['Superdotação'].iloc[0] if 'Superdotação' in BDAluno.columns else "Não Informado"
        valTipSuper = BDAluno['Tipo de Superdotação'].iloc[0] if 'Tipo de Superdotação' in BDAluno.columns else "-"

        with napCol1:
            st.markdown(f"<div class='info-box'><b>Possui PNE:</b> {valPne}</div>", unsafe_allow_html=True)
            if (str(valPne).strip().lower() in ["sim", "s"]):
                st.markdown(f"<div class='info-box' style='color: #e67e22;'><b>Tipo de PNE:</b> {valTipPne}</div>", unsafe_allow_html=True)
                
        with napCol2:
            st.markdown(f"<div class='info-box'><b>Possui Transtorno:</b> {valTrans}</div>", unsafe_allow_html=True)
            if (str(valTrans).strip().lower() in ["sim", "s"]):
                st.markdown(f"<div class='info-box' style='color: #e67e22;'><b>Tipo Transtorno:</b> {valTipTrans}</div>", unsafe_allow_html=True)
                
        with napCol3:
            st.markdown(f"<div class='info-box'><b>Superdotação:</b> {valSuper}</div>", unsafe_allow_html=True)
            if (str(valSuper).strip().lower() in ["sim", "s"]):
                st.markdown(f"<div class='info-box' style='color: #e67e22;'><b>Tipo Superdotação:</b> {valTipSuper}</div>", unsafe_allow_html=True)

    st.divider()

    ordenarPor = st.radio("Ordenar disciplinas por:", ["Nota", "Frequência"], horizontal=True)

    if (ordenarPor != st.session_state.ordenacao):
        st.session_state.materiaSelecionada = None
        st.session_state.ordenacao = ordenarPor

    # PARTE CENTRAL DASH
    m1, m2, m3, m4 = st.columns([2, 3, 2, 2])

    with m1:
        st.write("### Disciplinas")
        colunaRef = 'Média Final' if 'Média Final' in BDAluno.columns else '1º BI'
        if (ordenarPor == "Frequência" and 'Freq. Final' in BDAluno.columns):
            colunaRef = 'Freq. Final'

        BDLista = BDAluno.sort_values(by=colunaRef, ascending=True)
        disciplinasOrdenadas = BDLista['Disciplina'].unique().tolist()

        if (st.session_state.materiaSelecionada is None or st.session_state.materiaSelecionada not in disciplinasOrdenadas):
            if (disciplinasOrdenadas):
                st.session_state.materiaSelecionada = disciplinasOrdenadas[0]

        # Substituição do for disci in disciplinasOrdenadas
        def renderizar_botoes_disciplina(idx):
            if idx >= len(disciplinasOrdenadas):
                return
            disci = disciplinasOrdenadas[idx]
            if (st.button(disci, key=f"btn_{disci}")):
                st.session_state.materiaSelecionada = disci
                st.session_state.resetObs += 1
                st.rerun()
            renderizar_botoes_disciplina(idx + 1)
            
        renderizar_botoes_disciplina(0)

    if (st.session_state.materiaSelecionada):
        BDMateria = BDAluno[BDAluno['Disciplina'] == st.session_state.materiaSelecionada].iloc[0]

        with m2:
            freqFinalVal = float(BDMateria['Freq. Final'])
            porcentagemPresenca = freqFinalVal * 100 if freqFinalVal <= 1.0 else freqFinalVal
            porcentagemFaltas = max(0.0, 100.0 - porcentagemPresenca)

            st.write(f"**Visão Anual de Frequência: {st.session_state.materiaSelecionada}**")

            BDFreqRosca = pd.DataFrame({
                "Status": ["Presença", "Faltas"],
                "Percentual": [porcentagemPresenca, porcentagemFaltas]
            })

            graficoFreq = px.pie(
                BDFreqRosca,
                names="Status",
                values="Percentual",
                hole=0.6,
                color="Status",
                color_discrete_map={"Presença": "#2ecc71", "Faltas": "#e74c3c"}
            )

            graficoFreq.update_traces(textinfo="percent+label", hoverinfo="label+percent")
            graficoFreq.update_layout(showlegend=False, margin=dict(t=10, b=10, l=10, r=10), height=220)
            st.plotly_chart(graficoFreq, use_container_width=True)

            st.divider()

            valMediaFim = round(float(BDMateria['Média Final']), 2)
            st.write(f"**Notas por Bimestre (Média Final: {valMediaFim})**")

            n1 = float(BDMateria['1º BI'])
            n2 = float(BDMateria['2º BI'])
            n3 = float(BDMateria['3º BI'])
            n4 = float(BDMateria['4º BI'])

            graficoNota = px.bar(x=['1º BI', '2º BI', '3º BI', '4º BI'], y=[n1, n2, n3, n4])
            graficoNota.update_yaxes(range=[0, 10.5], title="Notas")
            st.plotly_chart(graficoNota, use_container_width=True)

        with m3:
            st.write("### Global")
            mediaComum = BDAluno[BDAluno['Núcleo'] == 'Comum']['Média Final'].mean()
            mediaTec = BDAluno[BDAluno['Núcleo'] == 'Técnico']['Média Final'].mean()
            notaMat = BDAluno[BDAluno['Disciplina'].str.contains('Matemática', case=False)]
            mediaMat = notaMat['Média Final'].values[0] if not notaMat.empty else 0.0

            mediaComum = round(mediaComum, 2) if pd.notna(mediaComum) else 0 
            mediaTec = round(mediaTec, 2) if pd.notna(mediaTec) else 0
            mediaMat = round(float(mediaMat), 2)
            
            st.write(f"Média Núcleo Comum: **{mediaComum}**")
            st.write(f"Média Núcleo Técnico: **{mediaTec}**") 
            st.write(f"Média Matemática: **{mediaMat}**")
            st.divider()

            mediaGlobal = BDAluno['Média Final'].mean()             
            mediaGlobal = round(mediaGlobal, 1) if pd.notna(mediaGlobal) else 0.0
            st.metric("Média Global", f"{mediaGlobal}")

        with m4:
            st.write("### Observações")
            chaveObs = f"{alunoNome}_{st.session_state.materiaSelecionada}_{st.session_state.resetObs}".replace(" ", "_")
            obsSalva = str(BDMateria['Observações']) if ('Observações' in BDMateria.index and pd.notna(BDMateria['Observações'])) else ""
            
            # Substituição do for n in obsSalva.split(" | ")
            historico_itens = obsSalva.split(" | ")
            def gerar_historico(h_idx, lista_hist):
                if h_idx >= len(historico_itens):
                    return lista_hist
                item = historico_itens[h_idx]
                if (item.strip() and item.lower() != "nan"):
                    lista_hist.append(item.strip())
                return gerar_historico(h_idx + 1, lista_hist)
                
            historico = gerar_historico(0, [])

            with st.form(key=f"form_{chaveObs}"):
                entradasAtuais = []
                
                # Substituição do for i, texto in enumerate(historico)
                def renderizar_historico_form(idx_form):
                    if idx_form >= len(historico):
                        return
                    texto_hist = historico[idx_form]
                    st.text_area(f"Nota {idx_form+1}", value=texto_hist, key=f"hist_{chaveObs}_{idx_form}", disabled=True)
                    entradasAtuais.append(texto_hist)
                    renderizar_historico_form(idx_form + 1)
                    
                renderizar_historico_form(0)

                novaNota = st.text_area("Nova anotação...", value="", key=f"nova_{chaveObs}")

                if (st.form_submit_button("SALVAR")):
                    if (novaNota.strip()):
                        entradasAtuais.append(novaNota.strip())
                        textoFinal = " | ".join(entradasAtuais)
                        pagina = BD[(BD['Aluno'] == alunoNome) & (BD['Disciplina'] == st.session_state.materiaSelecionada)].index
                        if (not pagina.empty):
                            BD.at[pagina[0], 'Observações'] = str(textoFinal)

                            conn.update(spreadsheet=linkSalaAtiva, data=BD)
                            st.session_state.resetObs += 1
                            st.success("Salvo com sucesso!")
                            st.rerun()

    # BARRA INFERIOR DE NAVEGAÇÃO DOS ALUNOS
    st.divider()
    b1, b2, b3 = st.columns([1, 1, 1])
    with b1:
        if (st.button("⬅️ Anterior")):
            st.session_state.pagAluno = (st.session_state.pagAluno - 1) % len(alunosLista)
            st.session_state.materiaSelecionada = None
            st.session_state.resetObs += 1
            st.rerun()
    with b2:
        dicionarioChamada = {}
        # Substituição da list comprehension que continha um for interno
        def construir_dicionario_chamada(idx_c):
            if idx_c >= len(alunosLista):
                return
            a = alunosLista[idx_c]
            dicionarioChamada[BD[BD['Aluno'] == a]['Nº Chamada'].iloc[0]] = idx_c
            construir_dicionario_chamada(idx_c + 1)
            
        construir_dicionario_chamada(0)
        
        numAtual = BDAluno['Nº Chamada'].iloc[0] if not BDAluno.empty else 1
        opcoesOrdenadas = sorted(list(dicionarioChamada.keys()))
        paginaSelecao = opcoesOrdenadas.index(numAtual) if numAtual in opcoesOrdenadas else 0

        escolhaNum = st.selectbox(
            "Aluno Nº:",
            options=opcoesOrdenadas,
            index=paginaSelecao
        )

        if (dicionarioChamada[escolhaNum] != st.session_state.pagAluno):
            st.session_state.pagAluno = dicionarioChamada[escolhaNum]
            st.session_state.materiaSelecionada = None
            st.session_state.resetObs += 1
            st.rerun()
    with b3:
        if (st.button("Próximo ➡️")):
            st.session_state.pagAluno = (st.session_state.pagAluno + 1) % len(alunosLista)
            st.session_state.materiaSelecionada = None
            st.session_state.resetObs += 1
            st.rerun()
