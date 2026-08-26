# Índices RENAEST

Pipeline que liga cada sinistro do RENAEST a uma via concreta da malha viária municipal e
calcula a extensão real dessa via. Com as duas coisas dá para calcular um índice de
sinistralidade: sinistros por quilômetro. Contagem absoluta não serve, porque premia via
comprida.

Cinco notebooks Python, numerados pela ordem de execução, gravando todos no mesmo banco
SQLite. Cada um explica o que está fazendo enquanto faz.

## Estado

| Etapa | Situação |
|---|---|
| 01. Ingestão do RENAEST | pronta |
| 02. Malha viária e extensão corrigida | pronta |
| 03. Padronização dos endereços | pronta |
| 04. Associação do sinistro à via | pronta, 69,0% de cobertura |
| 05. Contagem por via e mapa | pronta |
| **Índice de sinistralidade** | **não calculado** |
| **Auditoria dos resultados** | **não feita** |

O banco já tem as duas grandezas do índice: a contagem em `acidentes_por_via` e a extensão
corrigida em `comp_usado` de `vias_processadas`. Falta dividir uma pela outra. O que existe
hoje é contagem absoluta, que não é ranking de risco.

Nenhum número saído daqui foi conferido contra o boletim de origem, imagem aérea ou cadastro
municipal. Os 69,0% dizem quantas linhas receberam uma via, não quantas receberam a via certa.
Trate tudo como preliminar.

Recorte já processado: Aparecida de Goiânia (IBGE 5201405), 2024, 8.865 sinistros, malha
baixada em 13/08/2026.

## Ordem de execução

```
01_ingestao_renaest  ->  acidentes                  (independente)
02_malha_viaria      ->  vias_processadas           (independente)
03_revisao_enderecos ->  acidentes_revisado         (precisa do 01)
04_associacao_vias   ->  via_id_associada           (precisa do 02 e do 03)
05_mapa_calor        ->  acidentes_por_via + HTML   (precisa do 02 e do 04)
```

Os notebooks 03 e 04 processam um município e um ano por execução, e são retomáveis: execução
interrompida, a seguinte continua de onde parou.

## Como rodar

**1. Ambiente.** Nenhum conda daqui tem tudo:

| | `base` | `brabo` |
|---|---|---|
| JupyterLab | sim | não |
| geopandas, osmnx | não | sim |
| openai, python-dotenv | não | sim |
| sentence-transformers | não | não |

Rode o JupyterLab do `base` com o kernel do `brabo`:

```powershell
conda activate brabo
pip install openai python-dotenv               # ja instalados
pip install sentence-transformers accelerate   # opcional, ~2 GB (puxa o torch)
python -m ipykernel install --user --name brabo --display-name "Python (brabo)"

conda activate base
jupyter lab
```

Selecione o kernel `Python (brabo)` em cada notebook. Com o `python3` do `base`, a primeira
célula falha em `import geopandas`.

**2. Chave da IA.** O `.env` da raiz não existe ainda, e sem ele os notebooks 03 e 04 param na
primeira célula. Uma linha basta:

```
DEEPSEEK_API_KEY=sua-chave
```

O modelo é o `deepseek-v4-flash`, chamado pelo protocolo da OpenAI, e é por isso que a
biblioteca instalada é a `openai`. Trocar de provedor é trocar chave, modelo e URL no
`config.py`; os notebooks não mudam.

**3. O que processar.** Só o `parametros.py`: município, ano, tamanho de lote, aparência do
mapa. Nenhuma célula de notebook tem valor escrito à mão.

O município é escolhido **uma vez**, pelo código do IBGE, e o nome da cidade usado na consulta
ao OpenStreetMap é derivado dele. Antes o notebook 02 trazia `CIDADE` e `ESTADO` à mão enquanto
os notebooks 03, 04 e 05 usavam `CODIGO_IBGE`, duas formas de dizer a mesma coisa e livres para
divergir. Quando divergiam, os sinistros de uma cidade eram associados às ruas de outra e o
resultado saía marcado como `ok`, sem aviso.

Para outro município, acrescente a entrada em `MUNICIPIOS` e aponte `CODIGO_IBGE` para ela. Hoje
o dicionário tem Aparecida de Goiânia, Belo Horizonte, Brasília e São Paulo. Goiânia não está
lá. Os códigos disponíveis, com a contagem de sinistros de cada um, saem da etapa 8 do
notebook 01.

## Arquivos

| arquivo | o que é |
|---|---|
| `parametros.py` | **o único que você edita.** Município, ano, lotes, mapa |
| `config.py` | caminhos, `.env`, chave e modelo da IA, nomes de coluna |
| `busca.py` | o `MotorBusca`. É biblioteca, não etapa; só o notebook 04 usa |
| `limpar_associacao.py` | apaga vínculos que apontam para vias que não existem mais |
| `data/db/db_main.db` | o banco, 2,8 GB depois da carga nacional |
| `cache/` | respostas da Overpass API, guardadas pelo osmnx |
| `data/cache/` | embeddings do motor de busca. Vazio hoje |
| `data/temp/` | o ZIP do RENAEST e sua extração |
| `data/mapas/` | o HTML do notebook 05 |
| `relatorios/` | relatório do PIP em `.md`, `.docx` e `.pdf`, e o `gerar_docx.py` |

Fora os `.py` e os notebooks, nada disso entra no git: o `.gitignore` exclui `/cache`,
`/data/db`, `/data/temp` e `/relatorios`.

Tudo que os notebooks leem foi gravado por um deles. Não há fallback para outro banco: se uma
tabela não está lá, o notebook que a produz não foi rodado, e o erro diz isso.

Os notebooks 03 e 04 dependem de cinco colunas de `acidentes`: `num_acidente`, `ano_acidente`,
`codigo_ibge`, `end_acidente` e `bairro_acidente`. Se algum nome mudar na fonte, a etapa 6 do
notebook 01 avisa, e a correção é nas constantes `COLUNA_*` do `config.py`, único lugar onde
esses nomes aparecem.

## Quatro coisas que vão te morder

**1. Nome repetido é o teto da qualidade.** Das 4.845 vias de Aparecida de Goiânia, 1.704
(35,2%) compartilham nome com outra: são 24 logradouros chamados `Rua 4`, 23 chamados `Rua 3` e
22 chamados `Rua 1`. E 1.840 (38,0%) não têm bairro nenhum para desempatar, porque o
OpenStreetMap não tem o polígono. Sem bairro, a instrução manda ficar com a primeira candidata,
que entre homônimas é arbitrária, e o resultado sai como `ok` com nota alta. A etapa 9 do
notebook 04 mede quanto do seu resultado caiu nisso; em 2024 foram 46,2%. **Olhe esse número
antes de usar os dados.** Aumentar o `TOP_N` não resolve, só multiplica opções igualmente
plausíveis. A saída real é associar por coordenada, usando o `buffer` de 150 m que o notebook
02 já grava e ninguém lê, e isso depende de o RENAEST trazer latitude e longitude.

**2. Reprocessar as vias invalida os vínculos.** O `via_id` deriva do nome, dos bairros e do
centroide, com precisão de 11 m. Qualquer edição no OpenStreetMap que estenda ou corte a via
move o centroide mais que isso, e o identificador muda. Não há chave estrangeira e nada avisa.
Reexecutar o notebook 04 sozinho não resolve: `associacao_vias` é indexado por endereço mais
bairro, então o `par_conhecido()` pula a busca e espalha o `via_id` morto outra vez. Rode
`python limpar_associacao.py` para o diagnóstico e depois com `--confirmar`. Ele apaga só as
decisões órfãs e devolve o recorte para `parcial`; a padronização é preservada, o notebook 03
não roda de novo. Numa medição real, 116 de 2.475 decisões ficaram órfãs, mas carregavam 1.330
sinistros, 22% do total, porque as vias que quebram são as grandes. A etapa 2 do notebook 05
mede isso.

**3. A tabela de vias é de uma cidade só.** `vias_processadas` guarda o nome da cidade em texto,
sem código do IBGE. Se você reprocessar a malha para outra cidade sem limpar a associação, as
decisões antigas continuam no dicionário, indexadas sem município, e vão ser reaproveitadas para
a cidade nova. Trocou de município, rode `limpar_associacao.py --tudo --confirmar`. E o notebook
05 não consegue conferir sozinho que a malha é da cidade certa; ele imprime o nome e pede
conferência a olho.

**4. Reprocessar o RENAEST não corrige o que já foi revisado.** `acidentes` é substituída a cada
execução do notebook 01, mas `acidentes_revisado` copia com `INSERT OR IGNORE` por
`num_acidente`. Linha corrigida na fonte não atualiza a versão revisada.

## O cache congela a malha

A pasta `cache/` guarda 29 MB de respostas da Overpass API de 13/08/2026. Enquanto ela existir,
reexecutar o notebook 02 é rápido e devolve aquela malha, mesmo que o OpenStreetMap já tenha
mudado. Bom para reprodutibilidade, ruim quando você quer a malha atual: aí apague a pasta. A
coluna `baixado_em` de `vias_processadas` registra de qual versão do mapa cada via veio.

## Relatório

Fica em `relatorios/`. O markdown é a fonte; o `.docx` e o `.pdf` saem dele:

```powershell
python relatorios/gerar_docx.py relatorios/Relatorio_Final_PIP_Fabio_Assis.md relatorios/Relatorio_Final_PIP_Fabio_Assis.docx
```

O gerador monta capa, sumário, seções numeradas e tabelas no formato que o PIP exige: A4,
margens 3/2/3/2 cm, Arial 12, entrelinha 1,5, justificado. Fonte, corpo, capa e sumário são
parâmetros no topo do arquivo.

O comando sobrescreve o `.docx`. Se você editou no Word, passe as mudanças para o markdown
antes, senão elas se perdem.
