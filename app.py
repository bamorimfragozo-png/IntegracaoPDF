import streamlit as st
import pandas as pd
import plotly.express as px
from streamlit_gsheets import GSheetsConnection
from pypdf import PdfReader
import io
import re

# CONFIGURAR PÁGINA/CSS
st.set_page_config(page_title="Dashboard Acadêmico", layout="wide")
tecnicas=[
    "ILPR", "MAIN", "ININ", "LDPR", "RDCO", "LPWE", "SOPE",
    "INSO", "IPRE", "BDDA", "PSCO", "PRIN", "CNVI", "SDRE",
    "ASRE", "RSFI", "GCLI", "ELET", "DCAD", "CAUT", "PROG", 
    "PCOE","EDIG", "PRI1", "ELIN", "CISUT", "INTI", "MAPI", 
    "CNCM", "CLPR", "REPI", "HIEP", "MIMP", "PRI2"
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
conn=st.connection("gsheets", type=GSheetsConnection)

DICIONARIO_SALAS={
    "Redes 1": st.secrets["connections"]["gsheets"]["Redes1"],
    "Redes 2": st.secrets["connections"]["gsheets"]["Redes2"],
    "Redes 3": st.secrets["connections"]["gsheets"]["Redes3"],
    "Automação 1": st.secrets["connections"]["gsheets"]["Automacao1"],
    "Automação 2": st.secrets["connections"]["gsheets"]["Automacao2"],
    "Automação 3": st.secrets["connections"]["gsheets"]["Automacao3"]
}

# ESTADO DE ATUALIZAÇÃO DO DASHBOARD
if ("dadosCarregados" not in st.session_state):
    st.session_state.dadosCarregados=False
if ("pagAluno" not in st.session_state):
    st.session_state.pagAluno=0
if ("materiaSelecionada" not in st.session_state):
    st.session_state.materiaSelecionada=None
if ("resetObs" not in st.session_state):
    st.session_state.resetObs=0
if ("salaAtiva" not in st.session_state):
    st.session_state.salaAtiva="Redes 1"
if ("fotoAluno" not in st.session_state):
    st.session_state.fotoAluno={}
if ("ordenacao" not in st.session_state):
    st.session_state.ordenacao="Nota"

# MENU DE NAVEGAÇÃO
st.sidebar.markdown("### Navegação")
if ('salaSelecionada' in locals()): 
    st.session_state.salaAtiva=salaSelecionada

if (st.sidebar.button("Tela de Upload")):
    st.session_state.dadosCarregados=False
    st.session_state.materiaSelecionada=None
    st.session_state.pagAluno=0
    st.rerun()

if (st.sidebar.button("Dashboard")):
    st.session_state.dadosCarregados=True
    st.session_state.materiaSelecionada=None
    st.session_state.pagAluno=0
    st.rerun()

# EXTRAÇÃO DE DADOS
def extrairDadosInclusao(texto_completo):
    textoLimpo=texto_completo.lower()
    
    dados={
        'Necessidades Especiais': 'Não',
        'Tipo de Necessidade Especial': '-',
        'Transtorno': 'Não',
        'Tipo de Transtorno': '-',
        'Superdotação': 'Não',
        'Tipo de Superdotação': '-'
    }
    
    # 1. Busca por Necessidades Especiais
    if ("necessidades especiais" in textoLimpo):
        # Pega as próximas palavras após o termo para ver se acha um "sim" perdido
        trecho=re.search(r'necessidades\s+especiais\s*(?:.*\n?){0,3}?(sim|não)', textoLimpo)
        if (trecho and "sim" in trecho.group(1)):
            dados['Necessidades Especiais']='Sim'
            
    # 2. Busca por Transtorno
    if ("transtorno" in textoLimpo):
        # No PDF do SUAP, o "Sim" geralmente vem logo abaixo ou próximo do termo, por isso fazer a busca assim
        trecho=re.search(r'transtorno\s*(?:.*\n?){0,5}?(sim|não)', textoLimpo)
        if (trecho and "sim" in trecho.group(1)):
            dados['Transtorno']='Sim'
            
    # 3. Busca por Superdotação
    if ("superdotação" in textoLimpo):
        trecho=re.search(r'superdotação\s*(?:.*\n?){0,5}?(sim|não)', textoLimpo)
        if (trecho and "sim" in trecho.group(1)):
            dados['Superdotação']='Sim'

    return dados

def extrairDados(arquivosPdf):
    dadosFinais=[]
    mapaNapneTemporario={}
    
    # Rastreia o progresso dos alunos e chamadas ao longo do PDF
    dadosRastreamento={"numeroChamada": 1, "ultimoAlunoLido": "", "ultimoNomeVisto": None}

    # FUNÇÕES SUBSTITUTAS DOS LOOPS 'FOR'
    def processarLinhasNome(linha, nomeNestaPagina):
        if ("Aluno" in linha or "Nome" in linha):
            # 1. Remove tudo a partir da palavra 'Matrícula'
            linha_limpa=re.split(r'\bMatrícula\b', linha, flags=re.IGNORECASE)[0]
        
            # 2. Divide nos dois-pontos (:) para separar os rótulos do nome
            partes=linha_limpa.split(":")
        
            # 3. Pega a última parte (que será o nome) e limpa os espaços
            if (len(partes)>1):
                return partes[-1].strip()
        
            # Caso não haja dois-pontos, remove os rótulos diretos
            return linha_limpa.replace("Aluno(a)", "").replace("Aluno", "").replace("Nome", "").strip()
        
        return nomeNestaPagina
    def processarPaginasPdf(paginaIndex, pagina, leitorPdf, textoCompleto, arquivo):
        textoCompleto+=pagina.extract_text() + "\n"
        textoPagina=textoCompleto
        nomeNestaPagina="Não Identificado"
        
        # Substituição do for linha in textoPagina.split('\n')
        linhasPag=textoPagina.split('\n')
        def iterarLinhasNome(idx, nomeAtual):
            if (idx>=len(linhasPag)):
                return nomeAtual
            novoNome=processarLinhasNome(linhasPag[idx], nomeAtual)
            return iterarLinhasNome(idx + 1, novoNome)
            
        nomeNestaPagina=iterarLinhasNome(0, nomeNestaPagina)
        
        if (nomeNestaPagina=="Não Identificado" or not nomeNestaPagina.strip()):
            nomeNestaPagina=arquivo.name.replace(".pdf", "").strip()
            
        if (dadosRastreamento["ultimoAlunoLido"]!="" and nomeNestaPagina != dadosRastreamento["ultimoAlunoLido"]):
            dadosRastreamento["numeroChamada"]+=1
        
        dadosRastreamento["ultimoAlunoLido"]=nomeNestaPagina
        return textoPagina

    def buscarMatricula(idx, linhas, matriculaAluno):
        if (idx>=len(linhas)):
            return matriculaAluno
        linha=linhas[idx]
        
        termos=["matrícula", "matricula", "prontuário", "prontuario"]
        def checarTermos(t_idx):
            if (t_idx>=len(termos)):
                return None
            if (termos[t_idx] in linha.lower()):
                buscaBT=re.search(r"cula:\s*(.{9})", linha, re.IGNORECASE)
                if (buscaBT):
                    return buscaBT.group(1).strip()
            return checarTermos(t_idx+1)
            
        resultado=checarTermos(0)
        if (resultado):
            return resultado
        return buscarMatricula(idx+1, linhas, matriculaAluno)

    def extrairLinhasMetadados(idx, linhas, nomeAluno, serieAluno):
        # Mantida apenas para compatibilidade, retorna os valores sem alterar nada
        return nomeAluno, serieAluno

    def verificarFiltroPalavras(linha):
        palavras=["Notas das etapas", "Faltas nas etapas", "Diário", "Disciplina", "Total", "Este documento"]
        def iterarPalavras(p_idx):
            if (p_idx>=len(palavras)):
                return False
            if (palavras[p_idx] in linha):
                return True
            return iterarPalavras(p_idx+1)
        return iterarPalavras(0)

    def extrairFrequencia(idx, tokens, calculoFreq):
        if (idx>=len(tokens)):
            return calculoFreq
        if ("%" in tokens[idx]):
            try:
                return float(tokens[idx].replace("%", "").replace(",", "."))
            except ValueError:
                pass
            return calculoFreq
        return extrairFrequencia(idx + 1, tokens, calculoFreq)

    def filtrarTokens(idx, partesDados, tokensFiltrados):
        if (idx>=len(partesDados)):
            return tokensFiltrados
        tok=partesDados[idx]
        if (tok in ["Cursando", "(Aguarda", "Carga", "Horária)", "Horária", "Aprovado", "Retido"] or "%" in tok):
            return filtrarTokens(idx + 1, partesDados, tokensFiltrados)
        if (tok=="-" or tok.replace(',', '.').replace('.', '', 1).isdigit()):
            tokensFiltrados.append(tok)
        return filtrarTokens(idx+1, partesDados, tokensFiltrados)

    def preencherEtapas(etapa, pagDado, dadosTabela, notas, faltas):
        if (etapa>=4):
            return pagDado
        if (pagDado<len(dadosTabela)):
            valNota=dadosTabela[pagDado].replace(',', '.')
            if (valNota.replace('.', '', 1).isdigit()):
                notas[etapa]=float(valNota)
            else:
                notas[etapa]=0.0
            pagDado+=1
        if (pagDado<len(dadosTabela)):
            valFalta=dadosTabela[pagDado]
            if (valFalta.isdigit()):
                faltas[etapa]=float(valFalta)
            else:
                faltas[etapa]=0.0
            pagDado+=1
        return preencherEtapas(etapa + 1, pagDado, dadosTabela, notas, faltas)

    def recolherNotasLancadas(idx, notas, notasLancadas):
        if (idx>=len(notas)):
            return notasLancadas
        if (notas[idx]>0):
            notasLancadas.append(notas[idx])
        return recolherNotasLancadas(idx+1, notas, notasLancadas)

    def processarLinhasDisciplinas(idx, linhas, mapeamentoDisciplinas):
        if (idx>=len(linhas)):
            return mapeamentoDisciplinas
        linha=linhas[idx]
        
        if (verificarFiltroPalavras(linha)):
            return processarLinhasDisciplinas(idx+1, linhas, mapeamentoDisciplinas)

        linhaLimpa=re.sub(r'^\d{5,6}\s+', '', linha.strip())
        if not (re.search(r'[A-Z]{3,4}\.\d{4,5}|\([A-Z0-9]{5,}\)', linhaLimpa)):
            return processarLinhasDisciplinas(idx+1, linhas, mapeamentoDisciplinas)

        tokens=linhaLimpa.split()
        
        def separarTextoDados(t_idx, passou, p_texto, p_dados):
            if (t_idx>=len(tokens)):
                return p_texto, p_dados
            token=tokens[t_idx]
            if ((',' in token and token.replace(',', '').isdigit()) and not passou):
                passou=True
            if not (passou):
                p_texto.append(token)
            else:
                p_dados.append(token)
            return separarTextoDados(t_idx+1, passou, p_texto, p_dados)

        partesTexto, partesDados=separarTextoDados(0, False, [], [])
        nomeDisciplina=" ".join(partesTexto).strip()
        
        if not (nomeDisciplina or len(partesDados)<5):
            return processarLinhasDisciplinas(idx+1, linhas, mapeamentoDisciplinas)

        calculoFreq=extrairFrequencia(0, tokens, 100.0)
        tokensFiltrados=filtrarTokens(0, partesDados, [])
        dadosTabela=tokensFiltrados[4:]

        notas=[0.0, 0.0, 0.0, 0.0]
        faltas=[0.0, 0.0, 0.0, 0.0]
        
        pagDado=preencherEtapas(0, 0, dadosTabela, notas, faltas)

        mediaFinal=0.0
        if (pagDado<len(dadosTabela)):
            valMedia=dadosTabela[pagDado].replace(',', '.')
            if (valMedia.replace('.', '', 1).isdigit()):
                mediaFinal=float(valMedia)
            else:
                notasLancadas=recolherNotasLancadas(0, notas, [])
                if (notasLancadas):
                  mediaFinal=sum(notasLancadas)/len(notasLancadas) 
                else:
                  mediaFinal=0.0
        else:
            notasLancadas=recolherNotasLancadas(0, notas, [])
            if (notasLancadas):
              mediaFinal=sum(notasLancadas)/len(notasLancadas) 
            else:
              mediaFinal=0.0

        if (len(nomeDisciplina)>3):
            mapeamentoDisciplinas[nomeDisciplina]={
                'notas': notas,
                'faltas': faltas,
                'mediaFinal': mediaFinal,
                'freqFinal': calculoFreq
            }
        return processarLinhasDisciplinas(idx+1, linhas, mapeamentoDisciplinas)

    def checarTecnico(idx_t, nomeDisp):
        if (idx_t>=len(tecnicas)):
            return False
        if (tecnicas[idx_t] in nomeDisp.upper()):
            return True
        return checarTecnico(idx_t+1, nomeDisp)

    def processarMapeamentoDisciplinas(chaves, idx_d, mapa, nomeAluno, matriculaAluno, serieAluno, dadosNapne, linhas):
        # Condição de parada da recursão: se percorreu todas as disciplinas do aluno
        if idx_d>=len(chaves):
            return
    
        nomeDisp=chaves[idx_d]
        siglaDisp=mapa[nomeDisp]
    
        # --- Início do bloco original de busca de notas/faltas ---
        def buscarNotasFaltas(idx_l, n1_a, f1_a, n2_a, f2_a, n3_a, f3_a, n4_a, f4_a, med_a, totF_a, Sit_a, obs_a):   ######################################################################################################################
            if (idx_l>=len(linhas)):
                return n1_a, f1_a, n2_a, f2_a, n3_a, f3_a, n4_a, f4_a, med_a, totF_a, Sit_a, obs_a
                
            linha=linhas[idx_l].strip()
            if (linha.startswith(nomeDisp) or linha.startswith(siglaDisp)):
                partes=linha.split()
                if (len(partes)>=12):
                    return (partes[-11], partes[-10], partes[-9], partes[-8], 
                            partes[-7], partes[-6], partes[-5], partes[-4], 
                            partes[-3], partes[-2], partes[-1], "-")
            return buscarNotasFaltas(idx_l + 1, n1_a, f1_a, n2_a, f2_a, n3_a, f3_a, n4_a, f4_a, med_a, totF_a, Sit_a, obs_a)
            
        n1, f1, n2, f2, n3, f3, n4, f4, med, totF, Sit, obs = buscarNotasFaltas(0, "-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-")
        # --- Fim do bloco original ---
    
        # Grava na lista final associando cada disciplina às colunas da planilha do Google Sheets
        dadosFinais.append({
            'Nº Chamada': int(dadosRastreamento["numeroChamada"]),
            'Aluno': nomeAluno,
            'Matrícula': matriculaAluno,
            'Série': serieAluno,
            'Disciplina': nomeDisp,
            '1º BI': n1, 
            '2º BI': n2, 
            '3º BI': n3, 
            '4º BI': n4,
            'Média Final': med, 
            'Freq. Final': calculoFreq, 
            'Núcleo': nucleoVal,
            'Observações': obs,
            'Necessidades Especiais': dadosNapne['Necessidades Especiais'],
            'Tipo de Necessidade Especial': dadosNapne['Tipo de Necessidade Especial'],
            'Transtorno': dadosNapne['Transtorno'],
            'Tipo de Transtorno': dadosNapne['Tipo de Transtorno'],
            'Superdotação': dadosNapne['Superdotação'],
            'Tipo de Superdotação': dadosNapne['Tipo de Superdotação']
        })
        
        # Chamada recursiva para a próxima disciplina do aluno, repassando o dicionário completo e as linhas
        processarMapeamentoDisciplinas(chaves, idx_d+1, mapa, nomeAluno, matriculaAluno, serieAluno, dadosNapne, linhas)

    def processarFotos(leitorPdf):
        try:
            primeiraPagina=leitorPdf.pages[0]
            # Se a página contiver imagens extraíveis diretamente
            if (hasattr(primeiraPagina, 'images') and len(primeiraPagina.images)>0):
                # Retorna os bytes da primeira imagem encontrada na página do aluno
                return primeiraPagina.images[0].data
        except Exception:
            pass
        return None

    def iterarArquivosPdf(idx_arq):
        if (idx_arq>=len(arquivosPdf)):
            return
        arquivo=arquivosPdf[idx_arq]
        memoriaPdf=io.BytesIO(arquivo.getvalue())
        try:
            leitorPdf=PdfReader(memoriaPdf)
        except Exception as e:
            st.error(f"Erro ao ler o arquivo {arquivo.name}: {e}")
            iterarArquivosPdf(idx_arq+1)
            return

        textoCompleto=""
        paginas=leitorPdf.pages
        
        def iterarPaginas(p_idx, txt):
            if (p_idx>=len(paginas)):
                return txt
            novoTxt=processarPaginasPdf(p_idx, paginas[p_idx], leitorPdf, txt, arquivo)
            return iterarPaginas(p_idx+1, novoTxt)

        # 1. Extrai todo o texto do PDF primeiro
        textoCompleto=iterarPaginas(0, textoCompleto)
        linhas=textoCompleto.split('\n')
        textoNapne=textoCompleto.replace("\n", " ")

        # 2. Inicializa as variáveis com valores padrão antes de usá-las
        nomeAluno="Não Identificado"
        matriculaAluno="Não Identificada"
        serieAluno="Não Identificada"
        necEspeciais="Não"
        tipoNecEspecial="-"
        transtorno="Não"
        tipoTranstorno="-"
        superdotacao="Não"
        tipoSuperdotacao="-"

        # 3. Executa as buscas por Regex para preencher as variáveis do aluno corrente
        matchNome=re.search(
            r"Aluno\(a\):\s*(.*?)\s*Matrícula:",
            textoCompleto,
            re.DOTALL | re.IGNORECASE
        )
        if (matchNome):
            nomeAluno=" ".join(matchNome.group(1).split())

        matchSerie=re.search(r"(\d{5}\.\d\.[A-Z0-9\.]+)", textoCompleto)
        if (matchSerie):
            serieAluno=matchSerie.group(1).strip()

        matriculaAluno=buscarMatricula(0, linhas, matriculaAluno)

        # Se falhar na extração por regex, usa o nome do arquivo limpo
        if (nomeAluno=="Não Identificado" or not nomeAluno.strip()):
            nomeAluno=arquivo.name.split('.')[0].strip()

        # 4. Agora que o nomeAluno EXISTE com certeza absoluta, rodamos as lógicas dependentes
        if (nomeAluno):
            # Captura a foto do aluno
            fotos=processarFotos(leitorPdf)
            if ((fotos)):
                st.session_state.fotoAluno[nomeAluno]=fotos

            # Extrai os dados novos do NAPNE através da função dedicada
            dadosNapne=extrairDadosInclusao(textoCompleto)

            # Processa e mapeia as disciplinas do aluno
            mapeamentoDisciplinas=processarLinhasDisciplinas(0, linhas, {})
            chavesDisp=list(mapeamentoDisciplinas.keys())
            
            processarMapeamentoDisciplinas(
                chavesDisp, 
                0, 
                mapeamentoDisciplinas, 
                nomeAluno, 
                matriculaAluno, 
                serieAluno, 
                dadosNapne,
                linhas
            )

            # RegEx NAPNE legada (Mantida para alimentar o mapaNapneTemporario antigo se necessário)
            match=re.search(r"Portador\(a\)\s+de\s+Necessidades\s+Especiais\s+(Sim|Não)", textoNapne, re.IGNORECASE)
            if (match): 
              necEspeciais=match.group(1)
            match=re.search(r"Tipo\s+de\s+Necessidade\s+Especial\s+-?\s*(.+?)\s*(?=Portador\(a\)|$)", textoNapne, re.IGNORECASE)
            if (match): 
              tipoNecEspecial=match.group(1)
            match=re.search(r"Portador\(a\)\s+de\s+Transtorno\s+(Sim|Não)", textoNapne, re.IGNORECASE)
            if (match): 
              transtorno=match.group(1)
            match=re.search(r"Tipo\s+de\s+Transtorno\s+-?\s*(.+?)\s*(?=Portador\(a\)|$)", textoNapne, re.IGNORECASE)
            if (match): 
              tipoTranstorno=match.group(1)
            match=re.search(r"Portador\(a\)\s+de\s+Superdotação\s+(Sim|Não)", textoNapne, re.IGNORECASE)
            if (match): 
              superdotacao=match.group(1)
            match=re.search(r"Superdotação\s+-?\s*(.+?)\s*$", textoNapne, re.IGNORECASE)
            if (match): 
              tipoSuperdotacao=match.group(1)

            if (dadosRastreamento["ultimoNomeVisto"] is None):
                dadosRastreamento["ultimoNomeVisto"]=nomeAluno
            
            if (nomeAluno!=dadosRastreamento["ultimoNomeVisto"]):
                dadosRastreamento["numeroChamada"]+=1
                dadosRastreamento["ultimoNomeVisto"]=nomeAluno

            mapaNapneTemporario[nomeAluno.strip().upper()]={
                'nec': necEspeciais, 'tipNec': tipoNecEspecial,
                'trans': transtorno, 'tipTrans': tipoTranstorno,
                'super': superdotacao, 'tipSuper': tipoSuperdotacao
            }

        # 5. Vai para o próximo arquivo PDF da fila
        iterarArquivosPdf(idx_arq + 1)

    def mapearDadosFinaisNapne(idx):
        if idx>=len(dadosFinais):
            return
        dado=dadosFinais[idx]
        alunoAlvo=dado['Aluno'].strip().upper()
        if (alunoAlvo in mapaNapneTemporario):
            info=mapaNapneTemporario[alunoAlvo]
            dado['Necessidades Especiais']=info['nec']
            dado['Tipo de Necessidade Especial']=info['tipNec']
            dado['Transtorno']=info['trans']
            dado['Tipo de Transtorno']=info['tipTrans']
            dado['Superdotação']=info['super']
            dado['Tipo de Superdotação']=info['tipSuper']
        mapearDadosFinaisNapne(idx+1)

    # Execução das funções iterativas principais em substituição aos loops principais
    iterarArquivosPdf(0)
    mapearDadosFinaisNapne(0)
    
    return pd.DataFrame(dadosFinais)


# UPLOAD DOS RELATÓRIOS EM PDF
if not (st.session_state.dadosCarregados):
    st.title("Upload de PDFs")
    st.subheader("Selecione a sala correspondente e faça o upload dos relatórios em PDF.")

    salaSelecionada=st.selectbox("Selecione a Sala:", list(DICIONARIO_SALAS.keys()))
    st.session_state.salaAtiva=salaSelecionada 
    arquivosEnviados=st.file_uploader("Faça o upload de quantos PDFs desejar aqui:", type=["pdf"], accept_multiple_files=True, key=f"uploader_{salaSelecionada}")

    if (st.button("PROCESSAR E ATUALIZAR DASHBOARD")):
        if (arquivosEnviados):
            with st.spinner("Processando arquivos e atualizando planilhas de notas..."):
                BDNovo=extrairDados(arquivosEnviados)

                linkSalaAtiva=DICIONARIO_SALAS[salaSelecionada]
                df_atual=conn.read(spreadsheet=linkSalaAtiva)
                df_final=pd.concat([df_atual, BDNovo], ignore_index=True)
                df_final=df_final.drop_duplicates(subset=["Aluno", "Disciplina"], keep="last")

                if not (BDNovo.empty):
                    conn.update(spreadsheet=linkSalaAtiva, data=df_final) 
                    st.session_state.salaAtiva=salaSelecionada
                    st.session_state.dadosCarregados=True
                    st.session_state.materiaSelecionada=None
                    st.session_state.pagAluno=0
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

    linkSalaAtiva=DICIONARIO_SALAS[st.session_state.salaAtiva]
    BD=conn.read(spreadsheet=linkSalaAtiva, ttl="30m")
    
    colunasNumericas=['1º BI', '2º BI', '3º BI', '4º BI', 'Média Final', 'Freq. Final']
    
    # Substituição do for col in colunasNumericas
    def tratarColunasNumericas(idx):
        if (idx>=len(colunasNumericas)):
            return
        col=colunasNumericas[idx]
        if (col in BD.columns):
            BD[col]=pd.to_numeric(BD[col].astype(str).str.replace(',', '.'), errors='coerce').fillna(0.0)
        tratarColunasNumericas(idx+1)
        
    tratarColunasNumericas(0)

    if ('Observações' in BD.columns):
        BD['Observações']=BD['Observações'].astype(str).replace('nan', '')
    else:
        BD['Observações']=""
        
    ordemChamada=BD.sort_values(by='Nº Chamada', ascending=True)
    alunosLista=ordemChamada['Aluno'].unique().tolist()
    
    if not (alunosLista): 
        st.info("Nenhum relatório foi carregado ainda.")
        st.write("Faça o upload dos PDFs na tela de Upload para visualizar o Dashboard.")
        st.stop()
    
    if (st.session_state.pagAluno>=len(alunosLista)):
        st.session_state.pagAluno=0

    alunoNome=alunosLista[st.session_state.pagAluno]
    BDAluno=BD[BD['Aluno']==alunoNome].copy()

    # FOTO E IDENTIFICAÇÃO DO ESTUDANTE
    t1, t2=st.columns([1, 4])
    with t1:
        st.markdown("### Foto")
        if (alunoNome in st.session_state.fotoAluno):
            st.image(st.session_state.fotoAluno[alunoNome], use_container_width=True)
        else:
            st.image("https://via.placeholder.com/150", use_container_width=True)

    with t2:
        st.subheader(f"Nome: {alunoNome}")

        c1, c2 = st.columns(2)
        if ('Matrícula' in BDAluno.columns):
          matriculaVal=BDAluno['Matrícula'].iloc[0]  
        else:
          matriculaVal="Não Informado"
        if ('Série' in BDAluno.columns):
          serieVal=BDAluno['Série'].iloc[0]  
        else:
          serieVal="Não Informado"

        c1.markdown(f"<div class='info-box'><b>Matrícula:</b> {matriculaVal}</div>", unsafe_allow_html=True)
        c2.markdown(f"<div class='info-box'><b>Série:</b> {serieVal}</div>", unsafe_allow_html=True)
        
        st.markdown("#### Informações de Inclusão (NAPNE)")
        napCol1, napCol2, napCol3 = st.columns(3)

        if ('Necessidades Especiais' in BDAluno.columns):
          valPne=BDAluno['Necessidades Especiais'].iloc[0]  
        else:
          valPne="Não Informado"
        if ('Tipo de Necessidade Especial' in BDAluno.columns):
          valTipPne=BDAluno['Tipo de Necessidade Especial'].iloc[0]  
        else:
          valTipPne="-"
        if ('Transtorno' in BDAluno.columns):
          valTrans=BDAluno['Transtorno'].iloc[0]  
        else:
          valTrans="Não Informado"
        if ('Tipo de Transtorno' in BDAluno.columns):
          valTipTrans=BDAluno['Tipo de Transtorno'].iloc[0]  
        else:
          valTipTrans="-"
        if ('Superdotação' in BDAluno.columns):
          valSuper=BDAluno['Superdotação'].iloc[0]  
        else:
          valSuper="Não Informado"
        if ('Tipo de Superdotação' in BDAluno.columns):
          valTipSuper=BDAluno['Tipo de Superdotação'].iloc[0]  
        else:
          valTipSuper="-"

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

    ordenarPor=st.radio("Ordenar disciplinas por:", ["Nota", "Frequência"], horizontal=True)

    if (ordenarPor!=st.session_state.ordenacao):
        st.session_state.materiaSelecionada=None
        st.session_state.ordenacao=ordenarPor

    # PARTE CENTRAL DASH
    m1, m2, m3, m4 = st.columns([2, 3, 2, 2])

    with m1:
        st.write("### Disciplinas")
        if ('Média Final' in BDAluno.columns):
          colunaRef='Média Final'  
        else:
          colunaRef='1º BI'
        if (ordenarPor=="Frequência" and 'Freq. Final' in BDAluno.columns):
            colunaRef='Freq. Final'

        BDLista=BDAluno.sort_values(by=colunaRef, ascending=True)
        disciplinasOrdenadas=BDLista['Disciplina'].unique().tolist()

        if (st.session_state.materiaSelecionada is None or st.session_state.materiaSelecionada not in disciplinasOrdenadas):
            if (disciplinasOrdenadas):
                st.session_state.materiaSelecionada=disciplinasOrdenadas[0]

        # Substituição do for disci in disciplinasOrdenadas
        def renderizarBotoesDisciplina(idx):
            if (idx>=len(disciplinasOrdenadas)):
                return
            disci=disciplinasOrdenadas[idx]
            if (st.button(disci, key=f"btn_{disci}")):
                st.session_state.materiaSelecionada=disci
                st.session_state.resetObs+=1
                st.rerun()
            renderizarBotoesDisciplina(idx+1)
            
        renderizarBotoesDisciplina(0)

    if (st.session_state.materiaSelecionada):
        BDMateria=BDAluno[BDAluno['Disciplina']==st.session_state.materiaSelecionada].iloc[0]

        with m2:
            freqFinalVal=float(BDMateria['Freq. Final'])
            if (freqFinalVal<=1.0):
              porcentagemPresenca=freqFinalVal*100  
            else:
              porcentagemPresenca=freqFinalVal
            porcentagemFaltas=max(0.0, 100.0-porcentagemPresenca)

            st.write(f"**Visão Anual de Frequência: {st.session_state.materiaSelecionada}**")

            BDFreqRosca=pd.DataFrame({
                "Status": ["Presença", "Faltas"],
                "Percentual": [porcentagemPresenca, porcentagemFaltas]
            })

            graficoFreq=px.pie(
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

            valMediaFim=round(float(BDMateria['Média Final']), 2)
            st.write(f"**Notas por Bimestre (Média Final: {valMediaFim})**")

            n1=float(BDMateria['1º BI'])
            n2=float(BDMateria['2º BI'])
            n3=float(BDMateria['3º BI'])
            n4=float(BDMateria['4º BI'])

            graficoNota=px.bar(x=['1º BI', '2º BI', '3º BI', '4º BI'], y=[n1, n2, n3, n4])
            graficoNota.update_yaxes(range=[0, 10.5], title="Notas")
            st.plotly_chart(graficoNota, use_container_width=True)

        with m3:
            st.write("### Global")
            mediaComum=BDAluno[BDAluno['Núcleo']=='Comum']['Média Final'].mean()
            mediaTec=BDAluno[BDAluno['Núcleo']=='Técnico']['Média Final'].mean()
            notaMat=BDAluno[BDAluno['Disciplina'].str.contains('Matemática', case=False)]
            if not (notaMat.empty):
              mediaMat=notaMat['Média Final'].values[0]  
            else:
              mediaMat=0.0

            if (pd.notna(mediaComum)):
              mediaComum=round(mediaComum, 2)  
            else:
              mediaComum= 0 
            if (pd.notna(mediaTec)):
              mediaTec=round(mediaTec, 2)
            else:
              mediaTec=0
            mediaMat=round(float(mediaMat), 2)
            
            st.write(f"Média Núcleo Comum: **{mediaComum}**")
            st.write(f"Média Núcleo Técnico: **{mediaTec}**") 
            st.write(f"Média Matemática: **{mediaMat}**")
            st.divider()

            mediaGlobal=BDAluno['Média Final'].mean()         
            if (pd.notna(mediaGlobal)):    
              mediaGlobal=round(mediaGlobal, 1) 
            else:
              mediaGlobal=0.0
            st.metric("Média Global", f"{mediaGlobal}")

        with m4:
            st.write("### Observações")
            chaveObs=f"{alunoNome}_{st.session_state.materiaSelecionada}_{st.session_state.resetObs}".replace(" ", "_")
            if ('Observações' in BDMateria and pd.notna(BDMateria['Observações'])):
              obsSalva=str(BDMateria['Observações']) 
            else:
              obsSalva=""
            
            # Substituição do for n in obsSalva.split(" | ")
            historicoItens=obsSalva.split(" | ")
            def gerarHistorico(h_idx, listaHist):
                if (h_idx>=len(historicoItens)):
                    return listaHist
                item=historicoItens[h_idx]
                if (item.strip() and item.lower()!="nan"):
                    listaHist.append(item.strip())
                return gerarHistorico(h_idx+1, listaHist)
                
            historico=gerarHistorico(0, [])

            with st.form(key=f"form_{chaveObs}"):
                entradasAtuais=[]
                
                # Substituição do for i, texto in enumerate(historico)
                def renderizarHistoricoForm(idx_form):
                    if (idx_form>=len(historico)):
                        return
                    textoHist=historico[idx_form]
                    st.text_area(f"Nota {idx_form+1}", value=textoHist, key=f"hist_{chaveObs}_{idx_form}", disabled=True)
                    entradasAtuais.append(textoHist)
                    renderizarHistoricoForm(idx_form+1)
                    
                renderizarHistoricoForm(0)

                novaNota=st.text_area("Nova anotação...", value="", key=f"nova_{chaveObs}")

                if (st.form_submit_button("SALVAR")):
                    if (novaNota.strip()):
                        entradasAtuais.append(novaNota.strip())
                        textoFinal=" | ".join(entradasAtuais)
                        pagina=BD[(BD['Aluno']==alunoNome) & (BD['Disciplina']==st.session_state.materiaSelecionada)].index
                        if not (pagina.empty):
                            BD.at[pagina[0], 'Observações']=str(textoFinal)

                            conn.update(spreadsheet=linkSalaAtiva, data=BD)
                            st.session_state.resetObs+=1
                            st.success("Salvo com sucesso!")
                            st.rerun()

    # BARRA INFERIOR DE NAVEGAÇÃO DOS ALUNOS
    st.divider()
    b1, b2, b3=st.columns([1, 1, 1])
    with b1:
        if (st.button("⬅️ Anterior")):
            st.session_state.pagAluno=(st.session_state.pagAluno-1)%len(alunosLista)
            st.session_state.materiaSelecionada=None
            st.session_state.resetObs+=1
            st.rerun()
    with b2:
        dicionarioChamada={}
        # Substituição da list comprehension que continha um for interno
        def construirDicionarioChamada(idx_c):
            if (idx_c>=len(alunosLista)):
                return
            a=alunosLista[idx_c]
            dicionarioChamada[BD[BD['Aluno']==a]['Nº Chamada'].iloc[0]]=idx_c
            construirDicionarioChamada(idx_c+1)
            
        construirDicionarioChamada(0)
        
        if not (BDAluno.empty):
          numAtual=BDAluno['Nº Chamada'].iloc[0]  
        else:
          numAtual=1
        opcoesOrdenadas=sorted(list(dicionarioChamada.keys()))
        if (numAtual in opcoesOrdenadas):
          paginaSelecao=opcoesOrdenadas.index(numAtual)  
        else:
          paginaSelecao=0

        escolhaNum=st.selectbox(
            "Aluno Nº:",
            options=opcoesOrdenadas,
            index=paginaSelecao
        )

        if (dicionarioChamada[escolhaNum]!=st.session_state.pagAluno):
            st.session_state.pagAluno=dicionarioChamada[escolhaNum]
            st.session_state.materiaSelecionada=None
            st.session_state.resetObs+=1
            st.rerun()
    with b3:
        if (st.button("Próximo ➡️")):
            st.session_state.pagAluno=(st.session_state.pagAluno+1)%len(alunosLista)
            st.session_state.materiaSelecionada=None
            st.session_state.resetObs+=1
            st.rerun()
