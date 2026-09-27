import base64
import io
import json
import os
import re
import pandas as pd
import streamlit as st
from pypdf import PdfReader
from streamlit_gsheets import GSheetsConnection


def limpar_tipo(texto):
    """Limpa hífens, traços e espaços no início do texto capturado."""
    if not texto:
        return "-"
    texto_limpo = re.sub(r"^[\s\-\–\—]+", "", texto).strip()
    return texto_limpo if texto_limpo not in ["", "-"] else "-"


def extrair_dados_pdf(pdf_file):
    dados_extraidos = []

    # Leitura do PDF usando PyPDF
    reader = PdfReader(pdf_file)
    texto_completo = ""
    for page in reader.pages:
        texto_pagina = page.extract_text()
        if texto_pagina:
            texto_completo += texto_pagina + "\n"

    # Divide o documento por blocos de alunos ou registros
    blocos = re.split(r"(?=Matrícula\s*:)", texto_completo, flags=re.IGNORECASE)

    for bloco in blocos:
        if not bloco.strip():
            continue

        bloco_limpo = " ".join(bloco.split())

        # Valores padrão
        nec_especiais = "Não"
        tipo_nec_especial = "-"
        transtorno = "Não"
        tipo_transtorno = "-"
        superdotacao = "Não"
        tipo_superdotacao = "-"

        # Extração das Necessidades Especiais
        m_pne = re.search(
            r"Portador\(a\)\s+de\s+Necessidades\s+Especiais\s*:?\s*(Sim|Não)",
            bloco_limpo,
            re.IGNORECASE,
        )
        if m_pne:
            nec_especiais = m_pne.group(1).capitalize()

        m_tip_pne = re.search(
            r"Tipo\s+de\s+Necessidade\s+Especial\s*:?\s*(.*?)(?=Portador|\bTranstorno\b|\bSuperdotação\b|Disciplina|\Z)",
            bloco_limpo,
            re.IGNORECASE,
        )
        if m_tip_pne:
            tipo_nec_especial = limpar_tipo(m_tip_pne.group(1))

        # Extração de Transtornos
        m_trans = re.search(
            r"Portador\(a\)\s+de\s+Transtorno\s*:?\s*(Sim|Não)",
            bloco_limpo,
            re.IGNORECASE,
        )
        if m_trans:
            transtorno = m_trans.group(1).capitalize()

        m_tip_trans = re.search(
            r"Tipo\s+de\s+Transtorno\s*:?\s*(.*?)(?=Portador|\bSuperdotação\b|Disciplina|\Z)",
            bloco_limpo,
            re.IGNORECASE,
        )
        if m_tip_trans:
            tipo_transtorno = limpar_tipo(m_tip_trans.group(1))

        # Extração de Superdotação
        m_super = re.search(
            r"Portador\(a\)\s+de\s+Superdotação\s*:?\s*(Sim|Não)",
            bloco_limpo,
            re.IGNORECASE,
        )
        if m_super:
            superdotacao = m_super.group(1).capitalize()

        m_tip_super = re.search(
            r"Tipo\s+de\s+Superdotação\s*:?\s*(.*?)(?=Disciplina|\Z)",
            bloco_limpo,
            re.IGNORECASE,
        )
        if m_tip_super:
            tipo_superdotacao = limpar_tipo(m_tip_super.group(1))

        # Adiciona o registro processado
        dados_extraidos.append(
            {
                "necEspeciais": nec_especiais,
                "tipoNecEspecial": tipo_nec_especial,
                "transtorno": transtorno,
                "tipoTranstorno": tipo_transtorno,
                "superdotacao": superdotacao,
                "tipoSuperdotacao": tipo_superdotacao,
            }
        )

    return dados_extraidos


# Conexão com Google Sheets (se aplicável ao seu projeto)
# conn = st.connection("gsheets", type=GSheetsConnection)

st.title("Processador de Relatórios NAPNE")

uploaded_file = st.file_uploader(
    "Selecione o arquivo PDF:", type=["pdf"], accept_multiple_files=False
)

if uploaded_file is not None:
    with st.spinner("Processando o relatório..."):
        dados = extrair_dados_pdf(uploaded_file)
        if dados:
            st.success("Dados extraídos com sucesso!")
            df = pd.DataFrame(dados)
            st.dataframe(df, use_container_width=True)
        else:
            st.warning("Nenhum registro encontrado no documento.")
