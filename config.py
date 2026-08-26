"""CAMINHOS E CONFIGURACOES COMPARTILHADAS PELOS NOTEBOOKS DO PROJETO_V2.

ESTE ARQUIVO E A FONTE UNICA DE VERDADE PARA CAMINHO DE BANCO, PASTAS E CHAVES.
OS QUATRO NOTEBOOKS IMPORTAM DAQUI, ENTAO NENHUM DELES PRECISA REPETIR CAMINHO.

O BANCO DO V2 E PROPRIO E UNICO: projeto_v2/data/db/db_main.db.
NAO EXISTE FALLBACK PARA OUTRO BANCO. SE UMA TABELA NAO ESTIVER LA, O NOTEBOOK
QUE A PRODUZ AINDA NAO FOI RODADO -- E O ERRO DIZ ISSO.
"""

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# PASTAS
# ---------------------------------------------------------------------------

# PASTA DESTE ARQUIVO (projeto_v2). RESOLVE PARA CAMINHO ABSOLUTO.
PASTA_V2 = Path(__file__).resolve().parent

# RAIZ DO REPOSITORIO (UM NIVEL ACIMA DE projeto_v2).
RAIZ_REPO = PASTA_V2.parent

# PASTA DE DADOS DO V2.
PASTA_DADOS = PASTA_V2 / "data"

# PASTA DO BANCO SQLITE.
PASTA_DB = PASTA_DADOS / "db"

# PASTA DO CACHE DE EMBEDDINGS (ARQUIVOS .npy GERADOS PELO MOTOR DE BUSCA).
PASTA_CACHE = PASTA_DADOS / "cache"

# PASTA ONDE O ZIP DO RENAEST E BAIXADO E EXTRAIDO.
PASTA_TEMP = PASTA_DADOS / "temp"

# GARANTE QUE AS PASTAS EXISTAM ASSIM QUE O MODULO E IMPORTADO.
for _pasta in (PASTA_DB, PASTA_CACHE, PASTA_TEMP):
    _pasta.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# BANCO
# ---------------------------------------------------------------------------

# BANCO UNICO DO V2. TODAS AS TABELAS VIVEM AQUI:
#   acidentes            -> NOTEBOOK 01
#   vias_processadas     -> NOTEBOOK 02
#   acidentes_revisado   -> NOTEBOOK 03
#   padronizacao         -> NOTEBOOK 03 (DICIONARIO REUSAVEL)
#   revisao_cobertura    -> NOTEBOOK 03 (MAPA DE PROGRESSO)
#   associacao_vias      -> NOTEBOOK 04 (DICIONARIO REUSAVEL)
#   associacao_cobertura -> NOTEBOOK 04 (MAPA DE PROGRESSO)
BANCO = PASTA_DB / "db_main.db"

# NAO EXISTE SEGUNDO BANCO NEM FALLBACK. TUDO QUE OS NOTEBOOKS LEEM FOI GRAVADO
# POR UM DELES. OS BANCOS ANTIGOS DA RAIZ (geometria-renaeste.db, sinistros.db)
# SAO DE OUTRA EPOCA E NAO SAO LIDOS AQUI: O DADO QUE ELES CONTEM FOI PRODUZIDO
# POR CODIGO QUE NAO EXISTE MAIS, ENTAO NAO DA PARA EXPLICAR COMO FOI GERADO.


# ---------------------------------------------------------------------------
# LEITURA DO .env
# ---------------------------------------------------------------------------

def _carregar_env(caminho):
    """CARREGA AS VARIAVEIS DE UM ARQUIVO .env PARA O AMBIENTE DO PROCESSO.

    USA python-dotenv SE ESTIVER INSTALADO. SE NAO ESTIVER, FAZ UM PARSER
    SIMPLES DE KEY=VALUE, LINHA A LINHA, SEM SOBRESCREVER O QUE JA EXISTE.
    """
    # SE O ARQUIVO NAO EXISTE, NAO HA NADA A FAZER.
    if not caminho.exists():
        return

    # CAMINHO PREFERIDO: A BIBLIOTECA python-dotenv.
    try:
        from dotenv import load_dotenv
        load_dotenv(caminho)
        return
    except Exception:
        pass

    # CAMINHO ALTERNATIVO: PARSER MANUAL, SEM DEPENDENCIA EXTERNA.
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        # REMOVE ESPACOS NAS PONTAS.
        linha = linha.strip()

        # IGNORA LINHA VAZIA, COMENTARIO E LINHA SEM O SINAL DE IGUAL.
        if not linha or linha.startswith("#") or "=" not in linha:
            continue

        # SEPARA A CHAVE DO VALOR NO PRIMEIRO SINAL DE IGUAL.
        chave, _, valor = linha.partition("=")

        # GRAVA NO AMBIENTE SEM SOBRESCREVER UMA VARIAVEL JA DEFINIDA.
        os.environ.setdefault(chave.strip(), valor.strip().strip('"').strip("'"))


# CARREGA O .env ANTES DE LER QUALQUER CONFIGURACAO.
# PRIORIDADE: O .env DA RAIZ DO REPOSITORIO E, DEPOIS, O DA PASTA api.
_carregar_env(RAIZ_REPO / ".env")
_carregar_env(RAIZ_REPO / "api" / ".env")


# ---------------------------------------------------------------------------
# CHAVES E MODELOS
# ---------------------------------------------------------------------------

# A IA DOS NOTEBOOKS 03 E 04 E CHAMADA PELO PROTOCOLO DA OPENAI, QUE O DEEPSEEK
# IMPLEMENTA. POR ISSO A BIBLIOTECA INSTALADA E A `openai` MESMO QUANDO O MODELO
# E DEEPSEEK. TROCAR DE PROVEDOR E TROCAR CHAVE, MODELO E URL AQUI OU NO .env --
# O CODIGO DOS NOTEBOOKS NAO MUDA.

# CHAVE DA API. ACEITA DEEPSEEK_API_KEY OU OPENAI_API_KEY.
CHAVE_IA = os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY")

# MODELO USADO NA PADRONIZACAO (NOTEBOOK 03) E NA ASSOCIACAO (NOTEBOOK 04).
MODELO_IA = os.getenv("MODELO_IA", "deepseek-v4-flash")

# ENDERECO DA API. E O QUE APONTA O CLIENTE DA OPENAI PARA O DEEPSEEK.
URL_BASE_IA = os.getenv("URL_BASE_IA", "https://api.deepseek.com")

# LIGA OU DESLIGA OS EMBEDDINGS NA BUSCA. COM EMB_ENABLE=0 A BUSCA FICA SO LEXICAL.
USAR_EMBEDDINGS = os.getenv("EMB_ENABLE", "1") != "0"

# MODELO DE EMBEDDINGS. ACEITA 'MODELO' (NOME USADO NO .env DO PROJETO) OU 'EMB_MODEL'.
MODELO_EMBEDDINGS = (
    os.getenv("MODELO")
    or os.getenv("EMB_MODEL")
    or "paraphrase-multilingual-MiniLM-L12-v2"
)


# ---------------------------------------------------------------------------
# COLUNAS ESPERADAS NA TABELA acidentes
# ---------------------------------------------------------------------------

# NOMES DE COLUNA QUE OS NOTEBOOKS 03 E 04 PRECISAM ENCONTRAR NA TABELA acidentes.
# ATENCAO: ESTES NOMES AINDA NAO FORAM CONFERIDOS CONTRA O CSV REAL DO RENAEST.
# O NOTEBOOK 01 TEM UMA ETAPA QUE CONFERE ISSO E AVISA SE ALGUM NOME MUDOU.
# SE MUDAR, BASTA CORRIGIR AQUI -- E O UNICO LUGAR ONDE ESSES NOMES APARECEM.
COLUNA_ID_ACIDENTE = "num_acidente"
COLUNA_ANO = "ano_acidente"
COLUNA_MUNICIPIO = "codigo_ibge"
COLUNA_ENDERECO = "end_acidente"
COLUNA_BAIRRO = "bairro_acidente"

# LISTA FECHADA, USADA PELA CONFERENCIA DO NOTEBOOK 01 E PELA VALIDACAO DO 03.
COLUNAS_OBRIGATORIAS_ACIDENTES = (
    COLUNA_ID_ACIDENTE,
    COLUNA_ANO,
    COLUNA_MUNICIPIO,
    COLUNA_ENDERECO,
    COLUNA_BAIRRO,
)


def resumo():
    """IMPRIME A CONFIGURACAO ATIVA. USADO NA PRIMEIRA CELULA DE CADA NOTEBOOK."""
    print(f"BANCO DO V2       : {BANCO}")
    print(f"  EXISTE?         : {'SIM' if BANCO.exists() else 'NAO (SERA CRIADO)'}")
    print(f"PASTA TEMP        : {PASTA_TEMP}")
    print(f"PASTA CACHE       : {PASTA_CACHE}")
    print(f"CHAVE DA IA       : {'DEFINIDA' if CHAVE_IA else 'AUSENTE'}")
    print(f"MODELO DA IA      : {MODELO_IA}")
    print(f"URL DA IA         : {URL_BASE_IA}")
    print(f"EMBEDDINGS        : {'LIGADOS' if USAR_EMBEDDINGS else 'DESLIGADOS'}")
    print(f"MODELO EMBEDDINGS : {MODELO_EMBEDDINGS}")
