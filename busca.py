"""MOTOR DE BUSCA DE VIAS: COMBINA SIMILARIDADE LEXICAL (DIFFLIB) COM EMBEDDINGS (OPCIONAL).

ESTE ARQUIVO E BIBLIOTECA, NAO ETAPA DE PIPELINE. POR ISSO FICA COMO .py E NAO
DENTRO DE UM NOTEBOOK: SO O NOTEBOOK 04 USA, E ELE USA COMO FERRAMENTA.

O NOTEBOOK 04 TEM UMA CELULA PARA CONSULTAR O MOTOR A MAO. SE VOCE QUISER MEXER
NOS PESOS DA COMBINACAO (VER O METODO buscar), EDITE AQUI E REEXECUTE A CELULA
QUE CRIA O MOTOR.

LE AS VIAS DO BANCO DO V2 (config.BANCO). NAO HA FALLBACK: SE A TABELA
vias_processadas NAO EXISTIR, O ERRO MANDA RODAR O NOTEBOOK 02.
"""

import difflib
import hashlib
import json
import sqlite3
import unicodedata
from pathlib import Path

import numpy as np

import config

# COLUNAS QUE A BUSCA PRECISA ENCONTRAR NA TABELA vias_processadas.
COLUNAS_OBRIGATORIAS = {"via_id", "nome_via", "bairros", "comp_usado"}


# ---------------------------------------------------------------------------
# LEITURA DAS VIAS
# ---------------------------------------------------------------------------

def _parse_bairros(valor):
    """CONVERTE A COLUNA bairros (JSON EM TEXTO) EM UMA LISTA PYTHON."""
    if not valor:
        return []
    try:
        itens = json.loads(valor)
    except (json.JSONDecodeError, TypeError):
        return []
    return itens if isinstance(itens, list) else []


def carregar_vias(caminho_banco=None):
    """LE TODAS AS VIAS DO BANCO DO V2 E DEVOLVE UMA LISTA DE DICIONARIOS."""
    caminho_banco = Path(caminho_banco or config.BANCO)

    # SEM BANCO NAO HA O QUE LER. O NOTEBOOK 02 E QUEM CRIA A TABELA.
    if not caminho_banco.exists():
        raise FileNotFoundError(
            f"BANCO NAO ENCONTRADO: {caminho_banco}\n"
            "RODE O NOTEBOOK 02_malha_viaria.ipynb PARA CRIAR A TABELA vias_processadas."
        )

    conexao = sqlite3.connect(str(caminho_banco))
    conexao.row_factory = sqlite3.Row
    try:
        colunas = {linha[1] for linha in conexao.execute("PRAGMA table_info(vias_processadas)")}

        # TABELA INEXISTENTE DEVOLVE CONJUNTO VAZIO NO PRAGMA.
        if not colunas:
            raise RuntimeError(
                f"A TABELA vias_processadas NAO EXISTE EM {caminho_banco}.\n"
                "RODE O NOTEBOOK 02_malha_viaria.ipynb PRIMEIRO."
            )

        faltando = COLUNAS_OBRIGATORIAS - colunas
        if faltando:
            raise RuntimeError(
                f"A TABELA vias_processadas ESTA SEM AS COLUNAS {sorted(faltando)}.\n"
                "REEXECUTE O NOTEBOOK 02_malha_viaria.ipynb PARA GERAR O SCHEMA COMPLETO."
            )

        linhas = conexao.execute(
            "SELECT via_id, nome_via, bairros, comp_usado FROM vias_processadas"
        ).fetchall()
    finally:
        conexao.close()

    vias = []
    for linha in linhas:
        vias.append({
            "via_id": linha["via_id"],
            "nome_via": linha["nome_via"] or "",
            "bairros": _parse_bairros(linha["bairros"]),
            "comp_usado": linha["comp_usado"],
        })
    return vias


# ---------------------------------------------------------------------------
# NORMALIZACAO DE TEXTO
# ---------------------------------------------------------------------------

def normalizar(texto):
    """DEIXA O TEXTO MINUSCULO E SEM ACENTOS, PARA COMPARAR DE FORMA ROBUSTA."""
    texto = (texto or "").strip().lower()
    texto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in texto if not unicodedata.combining(c))


def _ratio(a, b):
    """SIMILARIDADE LEXICAL ENTRE DUAS STRINGS (0 A 1)."""
    if not a or not b:
        return 0.0
    return difflib.SequenceMatcher(None, a, b).ratio()


# MAPA DE PALAVRAS-NUMERO (JA SEM ACENTO E MINUSCULO, COMO SAI DE normalizar()).
_VALOR_NUMERO = {
    "um": 1, "uma": 1, "dois": 2, "duas": 2, "tres": 3, "quatro": 4, "cinco": 5,
    "seis": 6, "sete": 7, "oito": 8, "nove": 9,
    "dez": 10, "onze": 11, "doze": 12, "treze": 13, "catorze": 14, "quatorze": 14,
    "quinze": 15, "dezesseis": 16, "dezessete": 17, "dezoito": 18, "dezenove": 19,
    "vinte": 20, "trinta": 30, "quarenta": 40, "cinquenta": 50, "sessenta": 60,
    "setenta": 70, "oitenta": 80, "noventa": 90,
    "cem": 100, "cento": 100, "duzentos": 200, "trezentos": 300, "quatrocentos": 400,
    "quinhentos": 500, "seiscentos": 600, "setecentos": 700, "oitocentos": 800,
    "novecentos": 900, "mil": 1000,
}


def _parse_run(palavras):
    """SOMA UMA SEQUENCIA DE PALAVRAS-NUMERO EM UM INTEIRO (ex.: ['cento','onze'] -> 111)."""
    total = 0
    atual = 0
    for palavra in palavras:
        valor = _VALOR_NUMERO[palavra]
        if valor == 1000:
            atual = (atual or 1) * 1000
            total += atual
            atual = 0
        else:
            atual += valor
    return total + atual


def normalizar_numeros(texto):
    """CONVERTE NUMEROS POR EXTENSO EM DIGITOS. ESPERA TEXTO JA NORMALIZADO.

    EX.: "rua vinte e dois" -> "rua 22"; "avenida cento e onze" -> "avenida 111".
    O CONECTOR "e" SO E CONSUMIDO QUANDO LIGA DUAS PALAVRAS-NUMERO.
    """
    tokens = texto.split()
    saida = []
    i = 0
    n = len(tokens)
    while i < n:
        if tokens[i] in _VALOR_NUMERO:
            # COLETA A SEQUENCIA DE PALAVRAS-NUMERO (ACEITANDO "e" ENTRE DUAS DELAS).
            run = [tokens[i]]
            j = i + 1
            while j < n:
                if tokens[j] in _VALOR_NUMERO:
                    run.append(tokens[j])
                    j += 1
                elif tokens[j] == "e" and j + 1 < n and tokens[j + 1] in _VALOR_NUMERO:
                    j += 1  # PULA O CONECTOR, A PROXIMA VOLTA PEGA O NUMERO
                else:
                    break
            saida.append(str(_parse_run(run)))
            i = j
        else:
            saida.append(tokens[i])
            i += 1
    return " ".join(saida)


# ---------------------------------------------------------------------------
# O MOTOR
# ---------------------------------------------------------------------------

class MotorBusca:
    """INDEXA AS VIAS EM MEMORIA E RESPONDE BUSCAS POR NOME DE VIA + BAIRRO."""

    def __init__(self, vias, usar_embeddings=True, modelo=None):
        self.vias = vias
        # VERSOES NORMALIZADAS PRE-CALCULADAS (EVITA REFAZER A CADA BUSCA).
        self.norm_via = [normalizar(v["nome_via"]) for v in vias]
        # MESMOS NOMES COM NUMEROS POR EXTENSO VIRANDO DIGITO ("vinte e dois" -> "22").
        self.norm_via_num = [normalizar_numeros(x) for x in self.norm_via]
        self.norm_bairros = [[normalizar(b) for b in v["bairros"]] for v in vias]
        # TEXTO USADO PELOS EMBEDDINGS: NOME DA VIA + BAIRROS QUE ELA PERCORRE.
        self.corpus = [f'{v["nome_via"]} {" ".join(v["bairros"])}'.strip() for v in vias]

        self.modelo = None
        self.embeddings = None
        if usar_embeddings:
            self._preparar_embeddings(modelo or config.MODELO_EMBEDDINGS)

    def _preparar_embeddings(self, nome_modelo):
        """CARREGA O MODELO E OS EMBEDDINGS DO CORPUS (COM CACHE EM DISCO)."""
        try:
            from sentence_transformers import SentenceTransformer
        except Exception as erro:
            print(f"[BUSCA] sentence_transformers indisponivel ({erro}). USANDO SO LEXICAL.")
            return

        try:
            self.modelo = SentenceTransformer(nome_modelo)
        except Exception as erro:
            print(f"[BUSCA] FALHA AO CARREGAR MODELO '{nome_modelo}' ({erro}). USANDO SO LEXICAL.")
            self.modelo = None
            return

        config.PASTA_CACHE.mkdir(parents=True, exist_ok=True)
        # A CHAVE DO CACHE INCLUI O CORPUS E O MODELO: SE UM DOS DOIS MUDAR, REGERA.
        impressao = hashlib.md5(
            ("||".join(self.corpus) + "@@" + nome_modelo).encode("utf-8")
        ).hexdigest()
        arquivo_cache = config.PASTA_CACHE / f"emb_{impressao}.npy"

        if arquivo_cache.exists():
            self.embeddings = np.load(arquivo_cache)
            print(f"[BUSCA] EMBEDDINGS CARREGADOS DO CACHE ({len(self.embeddings)} VIAS).")
        else:
            print(f"[BUSCA] GERANDO EMBEDDINGS DE {len(self.corpus)} VIAS (PRIMEIRA VEZ)...")
            self.embeddings = self.modelo.encode(
                self.corpus, normalize_embeddings=True, show_progress_bar=False
            ).astype("float32")
            np.save(arquivo_cache, self.embeddings)
            print("[BUSCA] EMBEDDINGS GERADOS E SALVOS EM CACHE.")

    @property
    def usando_embeddings(self):
        """DIZ SE A PARTE SEMANTICA ESTA ATIVA OU SE A BUSCA E SO LEXICAL."""
        return self.modelo is not None and self.embeddings is not None

    def buscar(self, via="", bairro="", limit=10):
        """RANQUEIA AS VIAS PELA PROXIMIDADE COM (NOME DE VIA + BAIRRO) INFORMADOS."""
        n_via = normalizar(via)
        n_bairro = normalizar(bairro)
        total = len(self.vias)

        # COMPONENTE LEXICAL DO NOME DA VIA: COMPARA A FORMA ORIGINAL E A FORMA COM
        # NUMEROS EM DIGITOS, FICANDO COM O MELHOR CASAMENTO. ASSIM "Rua vinte e dois"
        # ENCONTRA "Rua 22" SEM QUEBRAR NOMES POR EXTENSO REAIS (ex.: "Sete de Setembro").
        if n_via:
            n_via_num = normalizar_numeros(n_via)
            via_lex = np.array([
                max(_ratio(n_via, plano), _ratio(n_via_num, numerico))
                for plano, numerico in zip(self.norm_via, self.norm_via_num)
            ])
        else:
            via_lex = np.zeros(total)

        # COMPONENTE LEXICAL DO BAIRRO: MELHOR CASAMENTO ENTRE OS BAIRROS DA VIA.
        if n_bairro:
            bairro_lex = np.array([
                max((_ratio(n_bairro, b) for b in bairros), default=0.0)
                for bairros in self.norm_bairros
            ])
        else:
            bairro_lex = np.zeros(total)

        # COMPONENTE SEMANTICO (EMBEDDINGS), SE DISPONIVEL.
        if self.usando_embeddings:
            consulta = " ".join(p for p in [via, bairro] if p).strip()
            vetor = self.modelo.encode([consulta], normalize_embeddings=True)[0]
            semantico = self.embeddings @ vetor          # COSSENO (-1 A 1)
            semantico = (semantico + 1.0) / 2.0          # NORMALIZA PARA 0 A 1
        else:
            semantico = np.zeros(total)

        # COMBINACAO: O LEXICAL ANCORA O NOME PROPRIO, O SEMANTICO REFORCA.
        # ESTES SAO OS PESOS QUE VALE A PENA EXPERIMENTAR NO NOTEBOOK 04.
        if n_bairro:
            score = 0.45 * via_lex + 0.25 * bairro_lex + 0.30 * semantico
        else:
            score = 0.60 * via_lex + 0.40 * semantico

        # PEGA OS MELHORES E MONTA O RESULTADO.
        ordem = np.argsort(-score)[:limit]
        resultados = []
        for posicao, indice in enumerate(ordem, start=1):
            via_atual = self.vias[indice]
            resultados.append({
                "ranking": posicao,
                "via_id": via_atual["via_id"],
                "nome_via": via_atual["nome_via"],
                "bairros": via_atual["bairros"],
                "comp_usado": via_atual["comp_usado"],
                "score": round(float(score[indice]), 4),
            })
        return resultados

    def mostrar(self, via="", bairro="", limit=10):
        """IMPRIME O RANKING DE FORMA LEGIVEL. ATALHO PARA USO A MAO NO NOTEBOOK."""
        print(f"CONSULTA: via={via!r} bairro={bairro!r} | "
              f"EMBEDDINGS={'ON' if self.usando_embeddings else 'OFF'}\n")
        for r in self.buscar(via=via, bairro=bairro, limit=limit):
            bairros = ", ".join(r["bairros"]) if r["bairros"] else "-"
            comp = f'{r["comp_usado"]:.0f} m' if r["comp_usado"] is not None else "?"
            print(f'  #{r["ranking"]:<2} score={r["score"]:.3f}  {r["nome_via"]}  [{bairros}]  {comp}')
