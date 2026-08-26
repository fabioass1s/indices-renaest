"""APAGA AS DECISOES DE ASSOCIACAO PARA QUE O NOTEBOOK 04 POSSA REFAZE-LAS.

QUANDO USAR
-----------
SEMPRE QUE VOCE REPROCESSAR O NOTEBOOK 02. O `via_id` E DERIVADO DA GEOMETRIA DA VIA,
ENTAO UMA MALHA NOVA GERA IDENTIFICADORES NOVOS, E TODO VINCULO GRAVADO ANTES PASSA A
APONTAR PARA VIA QUE NAO EXISTE MAIS.

POR QUE REEXECUTAR O 04 NAO BASTA
---------------------------------
O README MANDA REPROCESSAR O 04 DEPOIS DO 02, MAS SO ISSO NAO RESOLVE. O NOTEBOOK 04
GUARDA CADA DECISAO NA TABELA `associacao_vias`, INDEXADA POR ENDERECO + BAIRRO -- E
**SEM O MUNICIPIO**. NA PROXIMA EXECUCAO, `par_conhecido()` VE O PAR NO DICIONARIO,
PULA A BUSCA E A IA, E ESPALHA O `via_id` ANTIGO OUTRA VEZ.

O RESULTADO E SILENCIOSO: AS LINHAS SAEM MARCADAS COMO 'ok', COM NOTA, APONTANDO PARA
VIAS APAGADAS. QUEM DESCOBRE E O AVISO DE VINCULO ORFAO DO NOTEBOOK 05.

DOIS MODOS
----------
**SOMENTE OS ORFAOS (PADRAO).** APAGA SO AS DECISOES CUJO `via_id` DESAPARECEU DA MALHA,
E ZERA SO AS LINHAS DE ACIDENTE QUE APONTAVAM PARA ELAS.

E QUASE SEMPRE O MODO CERTO. REPROCESSAR A MESMA CIDADE NO OPENSTREETMAP POUCO DEPOIS
DEVOLVE QUASE A MESMA GEOMETRIA, ENTAO A MAIORIA DOS `via_id` SOBREVIVE -- APAGAR TUDO
JOGARIA FORA MILHARES DE DECISOES BOAS E GASTARIA COTA DE IA PARA REFAZE-LAS IGUAIS.

**TUDO (`--tudo`).** APAGA `associacao_vias` E `associacao_cobertura` INTEIRAS E ZERA AS
COLUNAS DE ASSOCIACAO DE TODAS AS LINHAS. USE QUANDO VOCE TROCOU DE CIDADE, MUDOU A
INSTRUCAO ENVIADA A IA OU OS PESOS DA BUSCA, E QUER TODAS AS DECISOES REFEITAS.

O QUE OS DOIS MODOS ZERAM EM `acidentes_revisado`
-------------------------------------------------
AS COLUNAS `via_id_associada`, `nome_via_associada`, `assoc_score`, `assoc_status`,
`assoc_modelo` E `assoc_em`. VOLTAR `assoc_status` PARA NULL E O QUE FAZ O
`marcar_pendentes()` DO NOTEBOOK 04 PEGAR ESSAS LINHAS DE NOVO.

O RECORTE AFETADO TAMBEM VOLTA PARA `parcial` NA COBERTURA. SEM ISSO, UM RECORTE
MARCADO `ok` FARIA O NOTEBOOK 04 PULAR TODAS AS ETAPAS E NUNCA CONSERTAR NADA.

O QUE ELE **NAO** TOCA
----------------------
- `padronizacao` E `revisao_cobertura`
- `revisao_status`, `end_acidente_padronizado` E `bairro_acidente_padronizado`

A REVISAO DE ENDERECO NAO DEPENDE DA MALHA: E SO NORMALIZACAO DE TEXTO, SERVE PARA
QUALQUER CIDADE E PARA QUALQUER VERSAO DAS VIAS. APAGAR ELA SERIA JOGAR FORA A PARTE
CARA DO TRABALHO SEM MOTIVO -- O NOTEBOOK 03 NAO PRECISA RODAR DE NOVO.

COMO USAR
---------
    python limpar_associacao.py                    # SO MOSTRA O QUE SERIA APAGADO
    python limpar_associacao.py --confirmar        # APAGA OS ORFAOS
    python limpar_associacao.py --tudo --confirmar # APAGA TODAS AS DECISOES
"""

import sqlite3
import sys
from pathlib import Path

# GARANTE QUE O config.py SEJA ENCONTRADO, RODANDO DE ONDE FOR.
sys.path.insert(0, str(Path(__file__).resolve().parent))

import config

# COLUNAS QUE O NOTEBOOK 04 PREENCHE EM acidentes_revisado.
COLUNAS_DE_ASSOCIACAO = (
    "via_id_associada",
    "nome_via_associada",
    "assoc_score",
    "assoc_status",
    "assoc_modelo",
    "assoc_em",
)


def tabelas_do_banco(conn):
    """NOMES DAS TABELAS QUE EXISTEM NO BANCO."""
    return {linha[0] for linha in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}


def contar(conn, sql):
    """CONTA UMA COISA, DEVOLVENDO ZERO SE A TABELA OU COLUNA NAO EXISTIR."""
    try:
        return conn.execute(sql).fetchone()[0]
    except sqlite3.Error:
        return 0


def diagnostico(conn):
    """MOSTRA O ESTADO ATUAL E DEVOLVE QUANTOS VINCULOS ESTAO ORFAOS."""
    tabelas = tabelas_do_banco(conn)

    decisoes = contar(conn, "SELECT count(*) FROM associacao_vias")
    com_via = contar(conn, "SELECT count(*) FROM associacao_vias WHERE via_id IS NOT NULL")
    linhas_ok = contar(conn, "SELECT count(*) FROM acidentes_revisado WHERE assoc_status='ok'")
    cobertura = contar(conn, "SELECT count(*) FROM associacao_cobertura")

    print("ESTADO ATUAL")
    print(f"  DECISOES EM associacao_vias      : {decisoes}  (COM VIA: {com_via})")
    print(f"  RECORTES EM associacao_cobertura : {cobertura}")
    print(f"  LINHAS COM assoc_status='ok'     : {linhas_ok}")

    # SEM A MALHA NAO DA PARA SABER QUANTOS VINCULOS ESTAO ORFAOS.
    if "vias_processadas" not in tabelas:
        print()
        print("  A TABELA 'vias_processadas' NAO EXISTE: O NOTEBOOK 02 AINDA ESTA RODANDO OU")
        print("  NAO FOI RODADO. TODO VINCULO EXISTENTE ESTA ORFAO POR DEFINICAO.")
        return decisoes

    orfaos = contar(conn, """
        SELECT count(*) FROM associacao_vias
        WHERE via_id IS NOT NULL
          AND via_id NOT IN (SELECT via_id FROM vias_processadas)
    """)
    linhas_orfas = contar(conn, """
        SELECT count(*) FROM acidentes_revisado
        WHERE via_id_associada IS NOT NULL
          AND via_id_associada NOT IN (SELECT via_id FROM vias_processadas)
    """)

    print()
    print(f"  DECISOES APONTANDO PARA VIA INEXISTENTE : {orfaos} DE {com_via}")
    print(f"  LINHAS DE ACIDENTE NA MESMA SITUACAO    : {linhas_orfas}")

    if com_via and orfaos == 0:
        print()
        print("  NENHUM VINCULO ORFAO. NAO HA MOTIVO PARA LIMPAR: A ASSOCIACAO ATUAL")
        print("  CORRESPONDE A MALHA QUE ESTA NO BANCO.")

    return orfaos


def colunas_para_zerar(conn):
    """AS COLUNAS DE ASSOCIACAO QUE REALMENTE EXISTEM NESTE BANCO."""
    existentes = {linha[1] for linha in conn.execute(
        "PRAGMA table_info(acidentes_revisado)")}
    return [c for c in COLUNAS_DE_ASSOCIACAO if c in existentes]


def voltar_cobertura_para_parcial(conn, recortes):
    """MARCA OS RECORTES AFETADOS COMO 'parcial'.

    UM RECORTE EM 'ok' FAZ O NOTEBOOK 04 PULAR TODAS AS ETAPAS DE PROCESSAMENTO.
    SEM ISSO, AS LINHAS QUE ACABAMOS DE ZERAR NUNCA SERIAM REPROCESSADAS.
    """
    if "associacao_cobertura" not in tabelas_do_banco(conn):
        return

    for ano, ibge in recortes:
        conn.execute(
            "UPDATE associacao_cobertura SET status='parcial' "
            "WHERE ano=? AND codigo_ibge=?",
            (ano, ibge),
        )

    if recortes:
        alvos = ", ".join(f"{ano}/{ibge}" for ano, ibge in sorted(recortes))
        print(f"  associacao_cobertura : {alvos} -> 'parcial'")


def limpar_orfaos(conn):
    """APAGA SO AS DECISOES CUJA VIA DESAPARECEU DA MALHA."""
    tabelas = tabelas_do_banco(conn)

    if "vias_processadas" not in tabelas:
        raise RuntimeError(
            "SEM 'vias_processadas' NAO DA PARA SABER QUAL VINCULO ESTA ORFAO.\n"
            "ESPERE O NOTEBOOK 02 TERMINAR, OU USE --tudo PARA APAGAR TODAS AS DECISOES."
        )

    # OS RECORTES AFETADOS, ANTES DE ZERAR AS LINHAS.
    recortes = set(conn.execute(f"""
        SELECT DISTINCT {config.COLUNA_ANO}, {config.COLUNA_MUNICIPIO}
        FROM acidentes_revisado
        WHERE via_id_associada IS NOT NULL
          AND via_id_associada NOT IN (SELECT via_id FROM vias_processadas)
    """).fetchall())

    cursor = conn.execute("""
        DELETE FROM associacao_vias
        WHERE via_id IS NOT NULL
          AND via_id NOT IN (SELECT via_id FROM vias_processadas)
    """)
    print(f"  associacao_vias      : {cursor.rowcount} DECISOES ORFAS APAGADAS")

    zerar = colunas_para_zerar(conn)
    if zerar:
        atribuicoes = ", ".join(f"{c}=NULL" for c in zerar)
        cursor = conn.execute(f"""
            UPDATE acidentes_revisado SET {atribuicoes}
            WHERE via_id_associada IS NOT NULL
              AND via_id_associada NOT IN (SELECT via_id FROM vias_processadas)
        """)
        print(f"  acidentes_revisado   : {cursor.rowcount} LINHAS ZERADAS")

    voltar_cobertura_para_parcial(conn, recortes)
    conn.commit()


def limpar_tudo(conn):
    """APAGA TODAS AS DECISOES DE ASSOCIACAO. NAO TOCA NA REVISAO DE ENDERECO."""
    tabelas = tabelas_do_banco(conn)

    if "associacao_vias" in tabelas:
        cursor = conn.execute("DELETE FROM associacao_vias")
        print(f"  associacao_vias      : {cursor.rowcount} DECISOES APAGADAS")

    if "associacao_cobertura" in tabelas:
        cursor = conn.execute("DELETE FROM associacao_cobertura")
        print(f"  associacao_cobertura : {cursor.rowcount} RECORTES APAGADOS")

    if "acidentes_revisado" in tabelas:
        zerar = colunas_para_zerar(conn)
        if zerar:
            atribuicoes = ", ".join(f"{c}=NULL" for c in zerar)
            cursor = conn.execute(f"UPDATE acidentes_revisado SET {atribuicoes}")
            print(f"  acidentes_revisado   : {cursor.rowcount} LINHAS ZERADAS")

    conn.commit()


def main():
    confirmado = "--confirmar" in sys.argv
    tudo = "--tudo" in sys.argv

    print(f"BANCO: {config.BANCO}")
    print(f"MODO : {'TUDO' if tudo else 'SOMENTE OS ORFAOS'}")
    print()

    conn = sqlite3.connect(str(config.BANCO))

    try:
        orfaos = diagnostico(conn)

        print()
        if not confirmado:
            print("=" * 70)
            print("NADA FOI APAGADO. ESTA E UMA EXECUCAO DE CONFERENCIA.")
            print()
            if tudo:
                print("PARA APAGAR TODAS AS DECISOES:")
                print("   python limpar_associacao.py --tudo --confirmar")
            else:
                print("PARA APAGAR SO AS DECISOES ORFAS (RECOMENDADO):")
                print("   python limpar_associacao.py --confirmar")
                print()
                print("PARA APAGAR TODAS AS DECISOES, INCLUSIVE AS QUE AINDA VALEM:")
                print("   python limpar_associacao.py --tudo --confirmar")
            print("=" * 70)
            return

        if not tudo and orfaos == 0:
            print("NENHUM VINCULO ORFAO. NADA A FAZER.")
            print("SE VOCE QUER REFAZER TODAS AS DECISOES DE PROPOSITO, USE --tudo.")
            return

        print("APAGANDO...")
        if tudo:
            limpar_tudo(conn)
        else:
            limpar_orfaos(conn)

        print()
        print("PRONTO. AGORA RODE O NOTEBOOK 04: ELE VAI DECIDIR DE NOVO SO OS PARES")
        print("QUE FICARAM SEM DECISAO. O NOTEBOOK 03 NAO PRECISA RODAR -- A")
        print("PADRONIZACAO DOS ENDERECOS FOI PRESERVADA.")
        print()
        print("DEPOIS DO 04, RODE O NOTEBOOK 05 PARA REFAZER O MAPA.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
