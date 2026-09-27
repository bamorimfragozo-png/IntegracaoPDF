import io
import json
import re
import unicodedata
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from pypdf import PdfReader
import pdfplumber
from streamlit_gsheets import GSheetsConnection


st.set_page_config(
    page_title="Conselho de Classe - IFSP Boituva",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================
# CONFIGURAÇÕES
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
HTML_PATH = BASE_DIR / "index.html"
STATIC_DIR = BASE_DIR / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)

TECNICAS = [
    "ILPR", "MAIN", "ININ", "LDPR", "RDCO", "LPWE", "SOPE", "INSO", "IPRE",
    "BDDA", "PSCO", "PRIN", "CNVI", "SDRE", "ASRE", "RSFI", "GCLI", "ELET",
    "DCAD", "CAUT", "PROG", "PCOE", "EDIG", "PRI1", "ELIN", "CISUT", "INTI",
    "MAPI", "CNCM", "CLPR", "REPI", "HIEP", "MIMP", "PRI2"
]

COLUNAS_BASE = [
    "Nº Chamada",
    "Aluno",
    "Matrícula",
    "Série",
    "Disciplina",
    "1º BI",
    "2º BI",
    "3º BI",
    "4º BI",
    "Média Final",
    "Freq. Final",
    "Freq. Disciplina",
    "Núcleo",
    "Observações",
    "Aluno Especial?",
    "Necessidades Especiais",
    "Tipo de Necessidade Especial",
    "Transtorno",
    "Tipo de Transtorno",
    "Superdotação",
    "Tipo de Superdotação",
    "Faltas",
    "F1",
    "F2",
    "F3",
    "F4",
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


# ============================================================
# FUNÇÕES AUXILIARES
# ============================================================

def normalizar_espacos(texto):
    return re.sub(r"\s+", " ", str(texto or "")).strip()


def normalizar_chave(texto):
    texto = normalizar_espacos(texto).upper()
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return texto


def slug_sala(sala):
    texto = normalizar_chave(sala).lower()
    texto = re.sub(r"[^a-z0-9]+", "_", texto).strip("_")
    return texto


def para_float(valor):
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return None
    texto = str(valor).strip()
    if not texto or texto in {"-", "—", "–", "nan", "None"}:
        return None
    try:
        return float(texto.replace(",", "."))
    except (ValueError, TypeError):
        return None


def para_int(valor):
    numero = para_float(valor)
    return int(numero) if numero is not None else None


def limpar_valor(valor):
    if valor is None:
        return None
    if isinstance(valor, float) and pd.isna(valor):
        return None
    if pd.isna(valor):
        return None
    if isinstance(valor, (pd.Timestamp,)):
        return valor.isoformat()
    if hasattr(valor, "item"):
        try:
            return valor.item()
        except Exception:
            pass
    return valor


def texto_para_sim_nao(valor):
    texto = normalizar_espacos(valor).lower()
    if texto == "sim":
        return "Sim"
    if texto in {"não", "nao"}:
        return "Não"
    return "Não"


def extrair_sim_nao(texto, rotulo):
    padrao_rotulo = re.escape(rotulo).replace(r"\ ", r"\s+")
    padrao = re.compile(rf"{padrao_rotulo}\s*:?\s*(Sim|Não|Nao)\b", re.IGNORECASE)
    encontrado = padrao.search(texto)
    if not encontrado:
        return "Não"
    return texto_para_sim_nao(encontrado.group(1))


def extrair_campo_texto(texto, rotulo, proximos_rotulos):
    padrao_rotulo = re.escape(rotulo).replace(r"\ ", r"\s+")
    paradas = []
    for item in proximos_rotulos:
        paradas.append(re.escape(item).replace(r"\ ", r"\s+"))
    parada_regex = "|".join(paradas) if paradas else r"$^"
    padrao = re.compile(
        rf"{padrao_rotulo}\s*:?\s*(.*?)\s*(?=(?:{parada_regex})\s*:?[\s]|$)",
        re.IGNORECASE,
    )
    encontrado = padrao.search(texto)
    if not encontrado:
        return "-"
    valor = normalizar_espacos(encontrado.group(1))
    if not valor or valor in {"-", "—", "–"}:
        return "-"
    return valor


def extrair_tipo_superdotacao(texto):
    ocorrencias = list(re.finditer(r"Superdotação\s*:?", texto, re.IGNORECASE))
    for ocorrencia in ocorrencias:
        inicio_valor = ocorrencia.end()
        trecho_anterior = texto[:ocorrencia.start()].rstrip().lower()
        if trecho_anterior.endswith("portador(a) de"):
            continue

        restante = texto[inicio_valor:]
        parada = re.search(r"\s+(?:Disciplina\b|Total\b|INT\.\d+\b)", restante, re.IGNORECASE)
        valor = restante[:parada.start()] if parada else restante
        valor = normalizar_espacos(valor)
        if valor and valor not in {"-", "—", "–", "sim", "não", "nao"}:
            return valor
    return "-"


def extrair_napne(bloco):
    texto = normalizar_espacos(bloco)

    aluno_especial = extrair_sim_nao(texto, "Aluno Especial?")
    if aluno_especial == "Não":
        aluno_especial = extrair_sim_nao(texto, "Aluno Especial")

    necessidades = extrair_sim_nao(texto, "Portador(a) de Necessidades Especiais")
    if necessidades == "Não":
        necessidades = extrair_sim_nao(texto, "Necessidades Especiais")

    tipo_necessidade = extrair_campo_texto(
        texto,
        "Tipo de Necessidade Especial",
        [
            "Portador(a) de Transtorno",
            "Tipo de Transtorno",
            "Portador(a) de Superdotação",
            "Superdotação",
            "Transtorno",
            "Disciplina",
            "Total",
        ],
    )

    transtorno = extrair_sim_nao(texto, "Portador(a) de Transtorno")
    if transtorno == "Não":
        transtorno = extrair_sim_nao(texto, "Transtorno")

    tipo_transtorno = extrair_campo_texto(
        texto,
        "Tipo de Transtorno",
        [
            "Portador(a) de Superdotação",
            "Superdotação",
            "Disciplina",
            "Total",
        ],
    )

    superdotacao = extrair_sim_nao(texto, "Portador(a) de Superdotação")
    if superdotacao == "Não":
        superdotacao = extrair_sim_nao(texto, "Superdotação")

    tipo_superdotacao = extrair_tipo_superdotacao(texto)

    if "Necessidades Especiais" in texto and tipo_necessidade != "-":
        necessidades = "Sim"
    if "Transtorno" in texto and tipo_transtorno != "-":
        transtorno = "Sim"

    return {
        "Aluno Especial?": aluno_especial,
        "Necessidades Especiais": necessidades,
        "Tipo de Necessidade Especial": tipo_necessidade if necessidades == "Sim" else "-",
        "Transtorno": transtorno,
        "Tipo de Transtorno": tipo_transtorno if transtorno == "Sim" else "-",
        "Superdotação": superdotacao,
        "Tipo de Superdotação": tipo_superdotacao if superdotacao == "Sim" else "-",
    }


def extrair_identificacao(bloco, nome_arquivo):
    texto = normalizar_espacos(bloco)

    nome = ""
    matricula = ""
    serie = ""
    curso = ""
    turma = ""
    frequencia = None

    m = re.search(r"Aluno\(a\)\s*:\s*(.*?)\s+Matr[ií]cula\s*:\s*(BT\d+)", texto, re.IGNORECASE)
    if m:
        nome = normalizar_espacos(m.group(1))
        matricula = m.group(2).strip()
    else:
        m_nome = re.search(r"Aluno\(a\)\s*:\s*(.*?)(?=\s+Matr[ií]cula\b|\s+Curso\b|\s+Coef\.|\Z)", texto, re.IGNORECASE)
        if m_nome:
            nome = normalizar_espacos(m_nome.group(1))
        m_mat = re.search(r"Matr[ií]cula\s*:\s*(BT\d+)", texto, re.IGNORECASE)
        if m_mat:
            matricula = m_mat.group(1).strip()

    m_curso = re.search(r"Curso\s*:\s*(.*?)(?=Coef\.|Frequência\b|Chave\b|Per[ií]odo\b)", texto, re.IGNORECASE)
    if m_curso:
        curso = normalizar_espacos(m_curso.group(1))

    m_freq = re.search(r"Frequ[eê]ncia\s*:\s*(\d+(?:[.,]\d+)?)\s*%", texto, re.IGNORECASE)
    if m_freq:
        frequencia = para_float(m_freq.group(1))

    m_turma = re.search(r"Turma\s*:\s*(.*?)\s+Sit\.\s*Per[ií]odo\s*:", texto, re.IGNORECASE)
    if m_turma:
        turma = normalizar_espacos(m_turma.group(1))

    m_serie = re.search(r"(\d{4,}\.[0-9]+\.[A-Z0-9.]+)", texto, re.IGNORECASE)
    if m_serie:
        serie = m_serie.group(1)

    if not nome:
        nome = Path(nome_arquivo).stem.replace("Boletim", "").replace("_", " ").strip()
    if not nome:
        nome = "Não Identificado"

    return {
        "Aluno": nome,
        "Matrícula": matricula,
        "Série": serie,
        "Curso": curso,
        "Turma": turma,
        "Freq. Final": frequencia,
    }


def extrair_nomes_disciplinas_pdf(arquivo_bytes):
    nomes = {}
    try:
        with pdfplumber.open(io.BytesIO(arquivo_bytes)) as pdf:
            for pagina in pdf.pages:
                palavras = pagina.extract_words(x_tolerance=1, y_tolerance=3)
                linhas = []
                for palavra in sorted(palavras, key=lambda w: (w["top"], w["x0"])):
                    if not linhas or abs(palavra["top"] - linhas[-1]["top"]) > 2:
                        linhas.append({"top": palavra["top"], "palavras": [palavra]})
                    else:
                        linhas[-1]["palavras"].append(palavra)

                indices = []
                for i, linha in enumerate(linhas):
                    texto_linha = " ".join(p["text"] for p in linha["palavras"])
                    if re.search(r"INT\.\d+", texto_linha, re.IGNORECASE):
                        indices.append(i)

                for pos, indice in enumerate(indices):
                    linha = sorted(linhas[indice]["palavras"], key=lambda w: w["x0"])
                    texto_linha = " ".join(p["text"] for p in linha)
                    m_codigo = re.search(r"INT\.(\d+)", texto_linha, re.IGNORECASE)
                    if not m_codigo:
                        continue
                    codigo = f"INT.{m_codigo.group(1)}".upper()

                    palavras_nome = []
                    encontrou_traco = False
                    for palavra in linha:
                        token = palavra["text"]
                        if token == "-":
                            encontrou_traco = True
                            continue
                        if encontrou_traco and palavra["x0"] < 280:
                            palavras_nome.append(token)

                    fim = indices[pos + 1] if pos + 1 < len(indices) else len(linhas)
                    for j in range(indice + 1, fim):
                        texto_j = " ".join(p["text"] for p in linhas[j]["palavras"])
                        if re.search(r"^Total\b|INSTITUTO FEDERAL|Este documento foi emitido|Boituva \(SP\)", texto_j, re.IGNORECASE):
                            break
                        for palavra in sorted(linhas[j]["palavras"], key=lambda w: w["x0"]):
                            token = palavra["text"]
                            if 50 <= palavra["x0"] < 280 and not re.fullmatch(r"\d+(?:[.,]\d+)?", token):
                                if token not in {"Cursando", "Aprovado", "Reprovado", "Matriculado", "Dispensado", "Cancelado", "Concluído"}:
                                    palavras_nome.append(token)

                    nome = normalizar_espacos(" ".join(palavras_nome))
                    if nome:
                        nomes[codigo] = nome
    except Exception:
        return nomes
    return nomes


def extrair_disciplinas(bloco, nomes_por_codigo=None):
    texto = normalizar_espacos(bloco)
    padrao_inicio = re.compile(r"INT\.\d+\s*\([^)]*\)\s*-\s*", re.IGNORECASE)
    inicios = list(padrao_inicio.finditer(texto))

    disciplinas = []

    for indice, inicio in enumerate(inicios):
        inicio_dados = inicio.end()
        fim_dados = inicios[indice + 1].start() if indice + 1 < len(inicios) else len(texto)
        trecho = texto[inicio_dados:fim_dados]

        if "Total" in trecho:
            trecho = trecho.split("Total", 1)[0]

        m_meta = re.search(
            r"(?P<nome>.*?)\s+"
            r"(?P<ch_horas>\d+(?:[.,]\d+)?)\s+"
            r"(?P<ch_aulas>\d+)\s+"
            r"(?P<total_aulas>\d+)\s+"
            r"(?P<faltas>\d+)\s+"
            r"(?P<freq>\d+(?:[.,]\d+)?)%\s+"
            r"(?P<rest>.*)$",
            trecho,
            re.IGNORECASE,
        )
        if not m_meta:
            continue

        nome = normalizar_espacos(m_meta.group("nome"))
        m_codigo = re.search(r"INT\.(\d+)", inicio.group(0), re.IGNORECASE)
        codigo = f"INT.{m_codigo.group(1)}".upper() if m_codigo else ""
        if nomes_por_codigo and codigo in nomes_por_codigo:
            nome = nomes_por_codigo[codigo]
        if not nome:
            continue

        faltas = para_int(m_meta.group("faltas"))
        freq_disciplina = para_float(m_meta.group("freq"))
        resto = m_meta.group("rest")

        m_pos_situacao = re.search(
            r"(?:Cursando|Aprovado|Reprovado|Matriculado|Dispensado|Cancelado|Conclu[ií]do|Aguarda Carga Hor[aá]ria).*?"
            r"(?P<mfd>\d{1,2}(?:[.,]\d{1,2})?)\s+"
            r"(?P<pairs>.*)$",
            resto,
            re.IGNORECASE,
        )
        if not m_pos_situacao:
            m_pos_situacao = re.search(
                r"(?P<mfd>\d{1,2}(?:[.,]\d{1,2})?)\s+(?P<pairs>.*)$",
                resto,
                re.IGNORECASE,
            )

        mfd = None
        bimestres = [None, None, None, None]
        faltas_bimestres = [None, None, None, None]

        if m_pos_situacao:
            mfd = para_float(m_pos_situacao.group("mfd"))
            tokens = m_pos_situacao.group("pairs").split()

            for etapa in range(4):
                pos_nota = etapa * 2
                pos_falta = pos_nota + 1
                if pos_nota < len(tokens):
                    bimestres[etapa] = para_float(tokens[pos_nota])
                if pos_falta < len(tokens):
                    faltas_bimestres[etapa] = para_int(tokens[pos_falta])

        if mfd is None:
            candidatos = re.findall(r"(?<!\d)(\d{1,2}(?:[.,]\d{1,2})?)(?!\d)", resto)
            for candidato in candidatos:
                numero = para_float(candidato)
                if numero is not None and 0 <= numero <= 10:
                    mfd = numero
                    break

        tecnico = any(codigo in nome.upper() for codigo in TECNICAS)
        nucleo = "Técnico" if tecnico else "Comum"

        disciplinas.append(
            {
                "Disciplina": nome,
                "1º BI": bimestres[0],
                "2º BI": bimestres[1],
                "3º BI": bimestres[2],
                "4º BI": bimestres[3],
                "Média Final": mfd,
                "Freq. Disciplina": freq_disciplina,
                "Faltas": faltas,
                "F1": faltas_bimestres[0],
                "F2": faltas_bimestres[1],
                "F3": faltas_bimestres[2],
                "F4": faltas_bimestres[3],
                "Núcleo": nucleo,
            }
        )

    return disciplinas


def extrair_dados(arquivos_pdf):
    dados_finais = []
    numero_chamada = 1

    for arquivo in arquivos_pdf:
        try:
            arquivo_bytes = arquivo.getvalue()
            memoria_pdf = io.BytesIO(arquivo_bytes)
            leitor_pdf = PdfReader(memoria_pdf)
            nomes_por_codigo = extrair_nomes_disciplinas_pdf(arquivo_bytes)
        except Exception as erro:
            st.error(f"Erro ao ler o arquivo {arquivo.name}: {erro}")
            continue

        paginas = []
        for pagina in leitor_pdf.pages:
            try:
                paginas.append(pagina.extract_text() or "")
            except Exception:
                paginas.append("")
        texto_completo = "\n".join(paginas)

        marcadores = list(
            re.finditer(
                r"BOLETIM DE NOTAS INDIVIDUAL\s+Aluno\(a\)\s*:",
                texto_completo,
                re.IGNORECASE,
            )
        )
        if marcadores:
            blocos = []
            for i, marcador in enumerate(marcadores):
                fim = marcadores[i + 1].start() if i + 1 < len(marcadores) else len(texto_completo)
                bloco = texto_completo[marcador.start():fim]
                if len(bloco) > 200:
                    blocos.append(bloco)
        else:
            marcadores_aluno = list(re.finditer(r"Aluno\(a\)\s*:", texto_completo, re.IGNORECASE))
            if marcadores_aluno:
                blocos = []
                for i, marcador in enumerate(marcadores_aluno):
                    fim = marcadores_aluno[i + 1].start() if i + 1 < len(marcadores_aluno) else len(texto_completo)
                    bloco = texto_completo[marcador.start():fim]
                    if len(bloco) > 200:
                        blocos.append(bloco)
            else:
                blocos = [texto_completo]

        for bloco in blocos:
            if "Disciplina" not in bloco and "INT." not in bloco:
                continue

            identificacao = extrair_identificacao(bloco, arquivo.name)
            napne = extrair_napne(bloco)
            disciplinas = extrair_disciplinas(bloco, nomes_por_codigo)

            if not identificacao["Matrícula"] or not disciplinas:
                continue

            for disciplina in disciplinas:
                registro = {
                    "Nº Chamada": numero_chamada,
                    **identificacao,
                    **disciplina,
                    **napne,
                    "Observações": "",
                }
                dados_finais.append(registro)

            numero_chamada += 1

    return pd.DataFrame(dados_finais)


def preparar_dataframe(df):
    df = df.copy()
    for coluna in COLUNAS_BASE:
        if coluna not in df.columns:
            df[coluna] = None
    return df


def chave_linha(linha):
    matricula = normalizar_chave(linha.get("Matrícula", ""))
    disciplina = normalizar_chave(linha.get("Disciplina", ""))
    nome = normalizar_chave(linha.get("Aluno", ""))
    identificador = matricula or nome
    return f"{identificador}||{disciplina}"


def mesclar_dados(df_atual, df_novo):
    """Atualiza dados lidos do PDF sem apagar Observações nem dados do NAPNE já salvos."""
    atual = preparar_dataframe(df_atual)
    novo = preparar_dataframe(df_novo)

    atual = atual[atual["Matrícula"].notna() | atual["Aluno"].notna()].copy()

    mapa = {}
    ordem = []

    for _, linha in atual.iterrows():
        registro = {coluna: limpar_valor(linha.get(coluna)) for coluna in COLUNAS_BASE}
        chave = chave_linha(registro)
        if not chave or chave.endswith("||"):
            continue
        if chave not in mapa:
            ordem.append(chave)
        mapa[chave] = registro

    chamadas = pd.to_numeric(atual["Nº Chamada"], errors="coerce") if not atual.empty else pd.Series(dtype=float)
    proxima_chamada = int(chamadas.max()) + 1 if not chamadas.dropna().empty else 1

    for _, linha in novo.iterrows():
        registro = {coluna: limpar_valor(linha.get(coluna)) for coluna in COLUNAS_BASE}
        chave = chave_linha(registro)
        if not chave or chave.endswith("||"):
            continue

        if chave in mapa:
            obs_antiga = mapa[chave].get("Observações")
            if obs_antiga not in (None, "", "nan", "NaN") and not registro.get("Observações"):
                registro["Observações"] = obs_antiga

            registro["Nº Chamada"] = mapa[chave].get("Nº Chamada")
        else:
            registro["Nº Chamada"] = registro.get("Nº Chamada") or proxima_chamada
            proxima_chamada += 1
            ordem.append(chave)

        mapa[chave] = registro

    resultado = pd.DataFrame([mapa[chave] for chave in ordem if chave in mapa])
    resultado = preparar_dataframe(resultado)

    extras = [c for c in resultado.columns if c not in COLUNAS_BASE]
    return resultado[COLUNAS_BASE + extras]


def dataframe_para_json(df):
    """Transforma a planilha em uma estrutura por aluno para o JavaScript."""
    df = preparar_dataframe(df)
    alunos = {}

    for _, linha in df.iterrows():
        matricula = normalizar_espacos(linha.get("Matrícula"))
        nome = normalizar_espacos(linha.get("Aluno"))
        if not matricula or not nome or nome == "Não Identificado":
            continue

        if matricula not in alunos:
            frequencia = para_float(linha.get("Freq. Final"))
            napne_campos = {
                "aluno_especial": texto_para_sim_nao(linha.get("Aluno Especial?")),
                "necessidades": texto_para_sim_nao(linha.get("Necessidades Especiais")),
                "tipo_necessidade": normalizar_espacos(linha.get("Tipo de Necessidade Especial")) or "-",
                "transtorno": texto_para_sim_nao(linha.get("Transtorno")),
                "tipo_transtorno": normalizar_espacos(linha.get("Tipo de Transtorno")) or "-",
                "superdotacao": texto_para_sim_nao(linha.get("Superdotação")),
                "tipo_superdotacao": normalizar_espacos(linha.get("Tipo de Superdotação")) or "-",
            }

            info_napne = []
            if napne_campos["aluno_especial"] == "Sim":
                info_napne.append("Aluno Especial: Sim")
            if napne_campos["necessidades"] == "Sim":
                info_napne.append(f"Necessidade Especial: {napne_campos['tipo_necessidade']}")
            if napne_campos["transtorno"] == "Sim":
                info_napne.append(f"Transtorno: {napne_campos['tipo_transtorno']}")
            if napne_campos["superdotacao"] == "Sim":
                info_napne.append(f"Superdotação: {napne_campos['tipo_superdotacao']}")

            alunos[matricula] = {
                "prontuario": matricula,
                "nome": nome,
                "curso": normalizar_espacos(linha.get("Curso")) or "Técnico em Redes de Computadores Integrado ao Ensino Médio",
                "turma": normalizar_espacos(linha.get("Turma")) or "",
                "serie": normalizar_espacos(linha.get("Série")) or "",
                "frequencia": frequencia,
                "napne": bool(info_napne),
                "napneDados": napne_campos,
                "pneInfo": " | ".join(info_napne) if info_napne else "Nenhum registro de NAPNE encontrado.",
                "deliberacao": normalizar_espacos(linha.get("Observações")),
                "disciplinas": [],
            }

        alunos[matricula]["disciplinas"].append({
            "nome": normalizar_espacos(linha.get("Disciplina")) or "Disciplina",
            "b1": para_float(linha.get("1º BI")),
            "b2": para_float(linha.get("2º BI")),
            "b3": para_float(linha.get("3º BI")),
            "b4": para_float(linha.get("4º BI")),
            "mediaFinal": para_float(linha.get("Média Final")),
            "freq": para_float(linha.get("Freq. Disciplina")),
            "faltas": para_int(linha.get("Faltas")) or 0,
            "f1": para_int(linha.get("F1")),
            "f2": para_int(linha.get("F2")),
            "f3": para_int(linha.get("F3")),
            "f4": para_int(linha.get("F4")),
            "nucleo": normalizar_espacos(linha.get("Núcleo")) or "",
        })

    resultado = list(alunos.values())
    resultado.sort(key=lambda aluno: normalizar_chave(aluno["nome"]))
    return resultado


# ============================================================
# SALVAR DELIBERAÇÃO VINDO DO HTML (Query Params)
# ============================================================

query_params = st.query_params
if query_params.get("action") == "salvar_obs":
    matricula_alvo = normalizar_espacos(query_params.get("matricula", ""))
    nova_obs = query_params.get("obs", "")
    sala_alvo = query_params.get("sala", st.session_state.salaAtiva)

    if sala_alvo in DICIONARIO_SALAS:
        link_sala = DICIONARIO_SALAS[sala_alvo]
        df_sheet = conn.read(spreadsheet=link_sala, ttl=0)
        df_sheet = preparar_dataframe(df_sheet)

        if "Matrícula" in df_sheet.columns:
            mascara = df_sheet["Matrícula"].astype(str).str.strip().str.upper() == matricula_alvo.upper()
            if mascara.any():
                df_sheet.loc[mascara, "Observações"] = nova_obs
                conn.update(spreadsheet=link_sala, data=df_sheet)
                st.toast("Deliberação salva no Google Sheets com sucesso!", icon="✅")

    st.query_params.clear()
    st.session_state.salaAtiva = sala_alvo
    st.session_state.dadosCarregados = True
    st.rerun()


# ============================================================
# SIDEBAR
# ============================================================

st.sidebar.title("Conselho de Classe")
st.sidebar.markdown("---")

if st.sidebar.button("📁 Tela de Upload / Processamento", use_container_width=True):
    st.session_state.dadosCarregados = False
    st.rerun()

if st.sidebar.button("📊 Ficha do Conselho (Dashboard)", use_container_width=True):
    st.session_state.dadosCarregados = True
    st.rerun()


# ============================================================
# TELA 1 — UPLOAD
# ============================================================

if not st.session_state.dadosCarregados:
    st.title("Upload de PDFs")
    st.subheader("Selecione a sala e faça o upload dos relatórios em PDF.")

    sala_selecionada = st.selectbox(
        "Selecione a Sala:",
        list(DICIONARIO_SALAS.keys()),
        index=list(DICIONARIO_SALAS.keys()).index(st.session_state.salaAtiva),
    )
    st.session_state.salaAtiva = sala_selecionada

    arquivos_enviados = st.file_uploader(
        "Envie os PDFs dos boletins:",
        type=["pdf"],
        accept_multiple_files=True,
        key=f"uploader_{slug_sala(sala_selecionada)}",
    )

    if st.button("PROCESSAR E ATUALIZAR DASHBOARD", type="primary"):
        if not arquivos_enviados:
            st.error("Por favor, selecione os arquivos PDF.")
        else:
            with st.spinner("Lendo PDFs, atualizando a planilha e gerando o JSON..."):
                df_novo = extrair_dados(arquivos_enviados)

                if df_novo.empty:
                    st.error("Não foi possível extrair dados válidos dos PDFs enviados.")
                else:
                    link_sala = DICIONARIO_SALAS[sala_selecionada]
                    df_atual = conn.read(spreadsheet=link_sala, ttl=0)
                    df_final = mesclar_dados(df_atual, df_novo)

                    conn.update(spreadsheet=link_sala, data=df_final)

                    st.session_state.salaAtiva = sala_selecionada
                    st.session_state.dadosCarregados = True
                    st.success("Dados processados e salvos com sucesso na planilha!")
                    st.rerun()


# ============================================================
# TELA 2 — DASHBOARD HTML/JS
# ============================================================

else:
    sala_ativa = st.session_state.salaAtiva
    st.sidebar.write(f"Visualizando: **{sala_ativa}**")

    if not HTML_PATH.exists():
        st.error("O arquivo 'index.html' não foi encontrado no repositório.")
    else:
        try:
            df_dashboard = conn.read(
                spreadsheet=DICIONARIO_SALAS[sala_ativa],
                ttl=0,
            )
            dados_json = dataframe_para_json(df_dashboard)

            html_content = HTML_PATH.read_text(encoding="utf-8")

            script_injecao = f"""
            <script>
                window.dadosAlunosInjetados = {json.dumps(dados_json, ensure_ascii=False)};
            </script>
            """

            html_final = html_content.replace("<head>", f"<head>{script_injecao}", 1)

            components.html(
                html_final,
                height=1150,
                scrolling=True,
            )

        except Exception as erro:
            st.error(f"Não foi possível carregar os dados da planilha: {erro}")
