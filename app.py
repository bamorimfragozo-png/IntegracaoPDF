import streamlit as st
import pandas as pd
import plotly.express as px
from streamlit_gsheets import GSheetsConnection
from pypdf import PdfReader
import io
import re

#CONFIGURAR PÁGINA/CSS
st.set_page_config(page_title="Dashboard Acadêmico", layout="wide")
tecnicas=[
    "ILPR", "MAIN", "ININ", "LDPR", "RDCO", "LPWE", "SOPE",
    "INSO", "IPRE", "BDDA", "PSCO", "PRIN", "CNVI", "SDRE",
    "ASRE", "RSFI", "GCLI","ELET", "DCAD", "CAUT", "PROG", "PCOE",
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

#CONEXÃO COM PLANILHAS
conn=st.connection("gsheets", type=GSheetsConnection)

DICIONARIO_SALAS={
    "Redes 1": st.secrets["connections"]["gsheets"]["Redes1"],
    "Redes 2": st.secrets["connections"]["gsheets"]["Redes2"],
    "Redes 3": st.secrets["connections"]["gsheets"]["Redes3"],
    "Automação 1": st.secrets["connections"]["gsheets"]["Automacao1"],
    "Automação 2": st.secrets["connections"]["gsheets"]["Automacao2"],
    "Automação 3": st.secrets["connections"]["gsheets"]["Automacao3"]
}

#ESTADO DE ATUALIZAÇÃO DO DASHBOARD
if ("dadosCarregados" not in st.session_state):
    st.session_state.dadosCarregados=True
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

#MENU DE NAVEGAÇÃO
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

def Extrair_Foto(leitorPdf, pagina):
    #EXTRAÇÃO DA FOTO DO PDF
    fotos=None
    try:
        #primeiraPagina=leitorPdf.pages[paginaIndex]
        primeiraPagina=pagina
        #if ("/XObject" in pagina["/Resources"]):
        if ("/XObject" in primeiraPagina["/Resources"]):
            xobject=primeiraPagina["/Resources"]["/XObject"].get_object()
            for obj in xobject:
                if (xobject[obj]["/Subtype"]=="/Image"):
                    fotos=xobject[obj].get_data()
                    break
    except Exception:
        fotos=None
    return fotos
    
def Extrair_Nome_Aluno(texto):
    linha=texto
    if ("Aluno" in linha or "Nome" in linha):
        partes=linha.split(":")
    if (len(partes)>1):
        valNome=partes[1].strip()
    else:
        valNome=linha.replace("Aluno", "").replace("Nome", "").strip()
    nomeAluno=re.sub(r'\bMatrícula\b.*', '', valNome, flags=re.IGNORECASE).strip()
    return nomeAluno

def Extrair_Matricula_Aluno(texto):
    linha=texto
    for termo in ["matrícula", "matricula", "prontuário", "prontuario"]:
        if (termo in linha.lower()):
            buscaBT=re.search(r"cula:\s*(.{9})", linha, re.IGNORECASE)
            if (buscaBT):
                matriculaAluno=buscaBT.group(1).strip()
                break
    return matriculaAluno

def Extrair_Serie_Aluno(texto):
    linha=texto
    if ("Série" in linha or "Serie" in linha or "Ano" in linha or "Turma" in linha):
        partes=linha.split(":")
        if (len(partes)>1):
            serieAluno=partes[1].strip()[:27]
    return serieAluno

#EXTRAÇÃO DE DADOS
def extrairDados(arquivosPdf):
    dadosFinais=[]
    ###########################--NAPNE--####################################################
    mapaNapneTemporario={}
    ############################--NAPNE--##################################################
    #for numeroChamada, arquivo in enumerate(arquivosPdf, start=1):
    ########################--VÁRIOS ALUNOS--###################################################
    numeroChamada=1
    ultimoAlunoLido=""
    leitorPdf=None
    for arquivo in arquivosPdf:
    ##################################--VÁRIOS ALUNOS--#####################################
        memoriaPdf=io.BytesIO(arquivo.getvalue())
        try:
            leitorPdf=PdfReader(memoriaPdf)
            #textoCompleto=""
            #for pagina in leitorPdf.pages:
                #textoCompleto+=pagina.extract_text()+"\n"
        except Exception as e:
            st.error(f"Erro ao ler o arquivo {arquivo.name}: {e}")
            continue
        ###################################--VÁRIOS ALUNOS--########################################################
        textoCompleto=""
        for paginaIndex, pagina in enumerate(leitorPdf.pages):
            textoCompleto+=pagina.extract_text() + "\n"
            textoPagina=textoCompleto
            nomeNestaPagina="Não Identificado"
            linhas=textoPagina.split('\n')
            for linha in linhas:
                if ("Aluno" in linha or "Nome" in linha):
                    partes=linha.split(":")
                    if (len(partes)>1):
                        valNome=partes[1].strip()  
                    else:
                        valNome=linha.replace("Aluno", "").replace("Nome", "").strip()
                    nomeNestaPagina=re.sub(r'\bMatrícula\b.*', '', valNome, flags=re.IGNORECASE).strip()
                    
                fotos=Extrair_Foto(leitorPdf,pagina)
                nomeAluno=Extrair_Nome_Aluno(linha)
                matriculaAluno=Extrair_Matricula_Aluno(linha)
                serieAluno=Extrair_Serie_Aluno(linha)
            
            if (nomeNestaPagina=="Não Identificado" or not nomeNestaPagina.strip()):
                nomeNestaPagina=arquivo.name.replace(".pdf", "").strip()
                
            if (ultimoAlunoLido!="" and nomeNestaPagina!=ultimoAlunoLido):
                numeroChamada+=1
            
            ultimoAlunoLido=nomeNestaPagina
            textoCompleto=textoPagina 
        ##################################--VÁRIOS ALUNOS--##################################################
        ##### ALTERACAO PAZINATTO-acrescentado paragrafo, colocando dentro do for de cima
            #EXTRAÇÃO DA FOTO DO PDF

            
            #fotos=None
            #try:
            #    primeiraPagina=leitorPdf.pages[0]
            #    #if ("/XObject" in pagina["/Resources"]):
            #    if ("/XObject" in pagina["/Resources"]):
            #        xobject=pagina["/Resources"]["/XObject"].get_object()
            #        for obj in xobject:
            #            if (xobject[obj]["/Subtype"]=="/Image"):
            #                fotos=xobject[obj].get_data()
            #                break
            #except Exception:
            #    fotos=None
        
        #FIM ALTERACAO PAZINATTO
        
        linhas=textoCompleto.split('\n')
        textoNapne=textoCompleto.replace("\n", " ") #<------------------------------------------------------------------teste NAPNE
        nomeAluno="Não Identificado"
        matriculaAluno="Não Identificada"
        serieAluno="Não Identificada"
        ######################################--NAPNE--#################################################
        necEspeciais="Não"
        tipoNecEspecial="-"
        transtorno="Não"
        tipoTranstorno="-"
        superdotacao="Não"
        tipoSuperdotacao="-"
        ########################################--NAPNE--#################################################

        #for linha in linhas:
            #if ("Aluno" in linha or "Nome" in linha):
            #    partes=linha.split(":")
            #    if (len(partes)>1):
            #      valNome=partes[1].strip()
            #    else:
            #      valNome=linha.replace("Aluno", "").replace("Nome", "").strip()
            #    nomeAluno=re.sub(r'\bMatrícula\b.*', '', valNome, flags=re.IGNORECASE).strip()
            
            #for termo in ["matrícula", "matricula", "prontuário", "prontuario"]:
            #  if (termo in linha.lower()):
            #    buscaBT=re.search(r"cula:\s*(.{9})", linha, re.IGNORECASE)
            #    if (buscaBT):
            #        matriculaAluno=buscaBT.group(1).strip()
            #        break

            #if ("Série" in linha or "Serie" in linha or "Ano" in linha or "Turma" in linha):
            #    partes=linha.split(":")
            #    if (len(partes)>1):
            #        serieAluno=partes[1].strip()[:27]

            #nomeAluno=Extrair_Nome_Aluno(linha)
            #matriculaAluno=Extrair_Matricula_Aluno(linha)
            #serieAluno=Extrair_Serie_Aluno(linha)
        
        #######################--NAPNE--#############################################
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
        ############################--NAPNE--###########################
        if (nomeAluno=="Não Identificado" or not nomeAluno.strip()):
            nomeAluno=arquivo.name.replace(".pdf", "").replace("Boletim", "").replace("_", " ").strip()

        if (fotos):
            st.session_state.fotoAluno[nomeAluno]=fotos
        
        mapeamentoDisciplinas={}

        for linha in linhas:
          encontrou=False
          for p in ["Notas das etapas", "Faltas nas etapas", "Diário", "Disciplina", "Total", "Este documento"]:
            if (p in linha):
              encontrou=True
              break
            if(encontrou):
              continue

            linhaLimpa=re.sub(r'^\d{5,6}\s+', '', linha.strip())
            if (not re.search(r'[A-Z]{3,4}\.\d{4,5}|\([A-Z0-9]{5,}\)', linhaLimpa)):
                continue

            tokens=linhaLimpa.split()
            partesTexto=[]
            partesDados=[]
            passouDaMateria=False

            for token in tokens:
                if ((',' in token and token.replace(',', '').isdigit()) and not passouDaMateria):
                    passouDaMateria=True
                if (not passouDaMateria):
                    partesTexto.append(token)
                else:
                    partesDados.append(token)

            nomeDisciplina=" ".join(partesTexto).strip()
            if (not nomeDisciplina or len(partesDados)<5):
                continue

            #CAPTURA DA FREQUÊNCIA DENTRO DA LINHA ATUAL
            calculoFreq=100.0
            for token in tokens:
                if ("%" in token):
                    try:
                        calculoFreq=float(token.replace("%", "").replace(",", "."))
                    except ValueError:
                        pass
                    break

            tokensFiltrados=[]
            for tok in partesDados:
                if (tok in ["Cursando", "(Aguarda", "Carga", "Horária)", "Horária", "Aprovado", "Retido"] or "%" in tok):
                    continue
                if (tok=="-" or tok.replace(',', '.').replace('.', '', 1).isdigit()):
                    tokensFiltrados.append(tok)

            dadosTabela=tokensFiltrados[4:]

            notas=[0.0, 0.0, 0.0, 0.0]
            faltas=[0.0, 0.0, 0.0, 0.0]

            pagDado=0
            for etapa in range(4):
                if (pagDado<len(dadosTabela)):
                    valNota=dadosTabela[pagDado].replace(',', '.')
                    if (valNota.replace('.','',1).isdigit()):
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

            mediaFinal=0.0
            if (pagDado<len(dadosTabela)):
                valMedia=dadosTabela[pagDado].replace(',', '.')
                if (valMedia.replace('.', '', 1).isdigit()):
                    mediaFinal=float(valMedia)
                else:
                    notasLancadas=[]
                    for n in notas:
                      if (n>0):
                        notasLancadas.append(n)
                    if (notasLancadas):
                      mediaFinal=sum(notasLancadas)/len(notasLancadas)
                    else:
                      mediaFinal=0.0
            else:
                notasLancadas=[]
                for n in notas:
                    if (n>0):
                        notasLancadas.append(n)
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

        for nomeDisp, blocos in mapeamentoDisciplinas.items():
            tecnico=False
            for kw in tecnicas:
              if (kw in nomeDisp.upper()):
                tecnico=True
                break
            if(tecnico):
              nucleo="Técnico"
            else:
              nucleo="Comum"

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
                ###################################################--NAPNE--######################################################
                'Necessidades Especiais': necEspeciais,
                'Tipo de Necessidade Especial': tipoNecEspecial,
                'Transtorno': transtorno,
                'Tipo de Transtorno': tipoTranstorno,
                'Superdotação': superdotacao,
                'Tipo de Superdotação': tipoSuperdotacao
                #####################################################--NAPNE--#####################################################
            })
        #######################################################--VÁRIOS ALUNOS--#################################
        if ('ultimoNomeVisto' not in locals()):
            ultimoNomeVisto=nomeAluno
        
        if (nomeAluno!=ultimoNomeVisto):
            numeroChamada+=1
            ultimoNomeVisto=nomeAluno
        ##############################################--VÁRIOS ALUNOS--#######################################
        ####################################--NAPNE--##########################################################
        if (nomeAluno and nomeAluno!="Não Identificado"):
            mapaNapneTemporario[nomeAluno.strip().upper()]={
                'nec': necEspeciais, 'tipNec': tipoNecEspecial,
                'trans': transtorno, 'tipTrans': tipoTranstorno,
                'super': superdotacao, 'tipSuper': tipoSuperdotacao
            }
    for dado in dadosFinais:
        alunoAlvo=dado['Aluno'].strip().upper()
        if (alunoAlvo in mapaNapneTemporario):
            info=mapaNapneTemporario[alunoAlvo]
            dado['Necessidades Especiais']=info['nec']
            dado['Tipo de Necessidade Especial']=info['tipNec']
            dado['Transtorno']=info['trans']
            dado['Tipo de Transtorno']=info['tipTrans']
            dado['Superdotação']=info['super']
            dado['Tipo de Superdotação']=info['tipSuper']
    ############################################--NAPNE--#################################################################
    return pd.DataFrame(dadosFinais)

#UPLOAD DOS RELATÓRIOS EM PDF
if (not st.session_state.dadosCarregados):
    st.title("Upload de PDFs")
    st.subheader("Selecione a sala correspondente e faça o upload dos relatórios em PDF.")

    salaSelecionada=st.selectbox("Selecione a Sala:", list(DICIONARIO_SALAS.keys()))
    st.session_state.salaAtiva=salaSelecionada #<-----------------------------------------------------------------------------------------------------------------------teste
    arquivosEnviados=st.file_uploader("Faça o upload de quantos PDFs desejar aqui:", type=["pdf"], accept_multiple_files=True, key=f"uploader_{salaSelecionada}")

    if (st.button("PROCESSAR E ATUALIZAR DASHBOARD")):
        if (arquivosEnviados):
            with st.spinner("Processando arquivos e atualizando planilhas de notas..."):
                BDNovo=extrairDados(arquivosEnviados)

                linkSalaAtiva=DICIONARIO_SALAS[salaSelecionada]
                #-------------------------------codigo adicionado para teste----------------------------------------------------------
                df_atual = conn.read(spreadsheet=linkSalaAtiva)
                df_final = pd.concat([df_atual, BDNovo],ignore_index=True)
                df_final = df_final.drop_duplicates(subset=["Aluno", "Disciplina"],keep="last")
                #conn.update(spreadsheet=linkSalaAtiva, data=df_final )

                if (not BDNovo.empty):
                    #linkSalaAtiva=DICIONARIO_SALAS[salaSelecionada]
                    #conn.update(spreadsheet=linkSalaAtiva, data=BDNovo) 
                    conn.update(spreadsheet=linkSalaAtiva, data=df_final) #<----------------------------------------------------------------------------------------------------------teste
                    st.session_state.salaAtiva=salaSelecionada
                    st.session_state.dadosCarregados=True
                    st.session_state.materiaSelecionada=None
                    st.session_state.pagAluno=0
                    st.rerun()
                else:
                    st.error("Não foi possível extrair dados estruturados válidos.")
        else:
            st.error("Por favor, selecione e envie os arquivos PDF para processar.")

#EXIBIÇÃO VISUAL DO DASHBOARD ACADÊMICO
else:
    if ("salaAtiva" not in st.session_state or not st.session_state.salaAtiva):
        st.info("Nenhum relatório foi carregado ainda.")
        st.write("Faça o upload dos PDFs na tela de Upload para visualizar o Dashboard.")
        st.stop()
    
    st.sidebar.write(f"Visualizando: **{st.session_state.salaAtiva}**")

    linkSalaAtiva=DICIONARIO_SALAS[st.session_state.salaAtiva]
    BD=conn.read(spreadsheet=linkSalaAtiva, ttl="0")
    BD.columns=BD.columns.str.strip()
    
    colunasNumericas=['1º BI', '2º BI', '3º BI', '4º BI', 'Média Final', 'Freq. Final']
    for col in colunasNumericas:
        if (col in BD.columns):
            BD[col]=pd.to_numeric(BD[col].astype(str).str.replace(',', '.'), errors='coerce').fillna(0.0)

    if ('Observações' in BD.columns):
        BD['Observações']=BD['Observações'].astype(str).replace('nan', '')
    else:
        BD['Observações']=""

    ordemChamada=BD.sort_values(by='Nº Chamada', ascending=True)
    alunosLista=ordemChamada['Aluno'].unique().tolist()
    
    #st.sidebar.write(f"numeroAlunos:{len(alunosLista)}")
    #st.sidebar.write(alunosLista)
    
    if (not alunosLista):   #<-------------------------------------------------------------------------------------------------------------------------------------------------teste
        st.info("Nenhum relatório foi carregado ainda.")
        st.write("Faça o upload dos PDFs na tela de Upload para visualizar o Dashboard.")
        st.stop()
    
    if (st.session_state.pagAluno>=len(alunosLista)):
        st.session_state.pagAluno=0

    alunoNome=alunosLista[st.session_state.pagAluno]
    BDAluno=BD[BD['Aluno']==alunoNome].copy()

    #FOTO E IDENTIFICAÇÃO DO ESTUDANTE
    t1, t2=st.columns([1, 4])
    with t1:
        st.markdown("### Foto")
        if (alunoNome in st.session_state.fotoAluno):
            st.image(st.session_state.fotoAluno[alunoNome], use_container_width=True)
        else:
            st.image("https://via.placeholder.com/150", use_container_width=True)

    with t2:
        st.subheader(f"Nome: {alunoNome}")

        c1, c2=st.columns(2)
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
        ##########################################--NAPNE--########################################################
        st.markdown("#### Informações de Inclusão (NAPNE)")
        napCol1, napCol2, napCol3=st.columns(3)
        
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
        #########################################--NAPNE--################################################################

    st.divider()

    ordenarPor=st.radio("Ordenar disciplinas por:", ["Nota", "Frequência"], horizontal=True)

    if (ordenarPor!=st.session_state.ordenacao):
        st.session_state.materiaSelecionada=None
        st.session_state.ordenacao=ordenarPor

    # PARTE CENTRAL DASH
    m1, m2, m3, m4=st.columns([2, 3, 2, 2])

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

        for disci in disciplinasOrdenadas:
            if (st.button(disci, key=f"btn_{disci}")):
                st.session_state.materiaSelecionada=disci
                st.session_state.resetObs+=1
                st.rerun()

    if (st.session_state.materiaSelecionada):
        BDMateria=BDAluno[BDAluno['Disciplina']==st.session_state.materiaSelecionada].iloc[0]

        with m2:
            freqFinalVal=float(BDMateria['Freq. Final'])
            if (freqFinalVal<=1.0): 
              porcentagemPresenca=freqFinalVal*100 
            else:
              porcentagemPresenca=freqFinalVal
            porcentagemFaltas=max(0.0, 100.0 - porcentagemPresenca)

            st.write(f"**Visão Anual de Frequência: {st.session_state.materiaSelecionada}**")

            BDFreqRosca=pd.DataFrame({
                "Status":["Presença", "Faltas"],
                "Percentual":[porcentagemPresenca, porcentagemFaltas]
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
            graficoFreq.update_layout(
                showlegend=False,
                margin=dict(t=10, b=10, l=10, r=10),
                height=220
            )
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
            if (not notaMat.empty):
              mediaMat=notaMat['Média Final'].values[0]
            else:
              mediaMat=0.0

            if (pd.notna(mediaComum)):
              mediaComum=round(mediaComum, 2)
            else:
              mediaComum=0 

            if (pd.notna(mediaTec)):
              mediaTec=round(mediaTec, 2) 
            else:
              mediaTec=0
              
            mediaMat=round(float(mediaMat),2)
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
            obsSalva=""
            if ('Observações' in BDMateria.index and pd.notna(BDMateria['Observações'])):
                obsSalva=str(BDMateria['Observações'])
            historico=[]

            for n in obsSalva.split(" | "):
                if (n.strip() and n.lower()!="nan"):
                    historico.append(n.strip())

            with st.form(key=f"form_{chaveObs}"):
                entradasAtuais=[]
                for i, texto in enumerate(historico):
                    st.text_area(f"Nota {i+1}", value=texto, key=f"hist_{chaveObs}_{i}", disabled=True)
                    entradasAtuais.append(texto)

                novaNota=st.text_area("Nova anotação...", value="", key=f"nova_{chaveObs}")

                if (st.form_submit_button("SALVAR")):
                    if (novaNota.strip()):
                        entradasAtuais.append(novaNota.strip())
                        textoFinal=" | ".join(entradasAtuais)
                        pagina=BD[(BD['Aluno']==alunoNome) & (BD['Disciplina']==st.session_state.materiaSelecionada)].index
                        if (not pagina.empty):
                            BD.at[pagina[0], 'Observações']=str(textoFinal)

                            conn.update(spreadsheet=linkSalaAtiva, data=BD)
                            st.session_state.resetObs+=1
                            st.success("Salvo com sucesso!")
                            st.rerun()

    #BARRA INFERIOR DE NAVEGAÇÃO DOS ALUNOS
    st.divider()
    b1, b2, b3=st.columns([1, 1, 1])
    with b1:
        if (st.button("⬅️ Anterior")):
            st.session_state.pagAluno=(st.session_state.pagAluno-1)%len(alunosLista)
            st.session_state.materiaSelecionada=None
            st.session_state.resetObs+=1
            st.rerun()
    with b2:
        dicionarioChamada={
            BD[BD['Aluno']==a]['Nº Chamada'].iloc[0]: i 
            for i, a in enumerate(alunosLista)
        }
        if (not BDAluno.empty):
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
