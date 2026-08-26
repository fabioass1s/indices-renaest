# Índices RENAEST

Cinco notebooks Python que pegam os sinistros de trânsito do RENAEST, onde o local é texto
livre copiado do boletim, e devolvem cada sinistro ligado a uma via concreta da malha viária do
município, com a extensão daquela via. Serve para calcular sinistros por quilômetro em vez de
contagem absoluta.

Todos gravam no mesmo banco SQLite e explicam o que estão fazendo enquanto fazem.

## O que cada notebook faz

**01. Ingestão.** Consulta a API do portal de dados abertos do Ministério dos Transportes, pega
o recurso mais recente pela data de publicação, baixa, extrai e carrega o CSV nacional em blocos
de 50.000 linhas na tabela `acidentes`. Confere no fim se as cinco colunas de que os notebooks
seguintes dependem existem mesmo.

**02. Malha viária.** Baixa a rede dirigível do OpenStreetMap pelo OSMnx, junta trechos de mesmo
nome que estão a até 100 m um do outro, cruza com polígonos de bairro, calcula a extensão de cada
via e corrige os casos de pista dupla, em que a avenida foi desenhada como duas linhas paralelas
e a soma bruta dobra a extensão. Grava `vias_processadas`, com um `via_id` por via e um buffer de
150 m em volta dela.

**03. Padronização.** Manda os pares distintos de endereço e bairro para um modelo de linguagem,
que devolve a forma canônica: `RUA J 32  CEP 74950-010` vira `Rua J-32`. Guarda o resultado em
dicionário reaproveitável, então o mesmo endereço não é enviado duas vezes.

**04. Associação.** Para cada endereço padronizado, o `MotorBusca` propõe as seis vias mais
parecidas e um modelo de linguagem escolhe entre elas. Cada linha termina em `ok`, `sem_via` ou
`pendente`, e o vínculo vai para a coluna `via_id_associada`.

**05. Mapa.** Agrega os sinistros por via em `acidentes_por_via` e desenha um mapa interativo em
`data/mapas/mapa_calor_vias.html`, colorindo a própria linha da via.

Dependências: o 01 e o 02 são independentes. O 03 precisa do 01. O 04 precisa do 02 e do 03. O
05 precisa do 02 e do 04. Os notebooks 03 e 04 processam um município e um ano por execução, e
são retomáveis: execução interrompida, a seguinte continua de onde parou.

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

**3. O que processar.** Só o `parametros.py`: município, ano, tamanho de lote, aparência do mapa.
Nenhuma célula de notebook tem valor escrito à mão.

O município é escolhido uma vez, pelo código do IBGE, e o nome da cidade usado na consulta ao
OpenStreetMap é derivado dele. Para rodar outro município, acrescente a entrada em `MUNICIPIOS`
e aponte `CODIGO_IBGE` para ela. Hoje o dicionário tem Aparecida de Goiânia, Belo Horizonte,
Brasília e São Paulo. Os códigos disponíveis, com a contagem de sinistros de cada um, saem da
etapa 8 do notebook 01.

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
| `relatorios/` | relatório do PIP e o `gerar_docx.py` que o converte |

Fora os `.py` e os notebooks, nada disso entra no git: o `.gitignore` exclui `/cache`,
`/data/db`, `/data/temp` e `/relatorios`.

Tudo que os notebooks leem foi gravado por um deles. Não há fallback para outro banco: se uma
tabela não está lá, o notebook que a produz não foi rodado, e o erro diz isso.

Os notebooks 03 e 04 dependem de cinco colunas de `acidentes`: `num_acidente`, `ano_acidente`,
`codigo_ibge`, `end_acidente` e `bairro_acidente`. Se algum nome mudar na fonte, a etapa 6 do
notebook 01 avisa, e a correção é nas constantes `COLUNA_*` do `config.py`, único lugar onde
esses nomes aparecem.

## Armadilhas

**Nome repetido derruba a associação.** Muitas vias dividem nome com outra do mesmo município, e
boa parte delas não tem bairro na malha para servir de desempate, porque o OpenStreetMap não tem
o polígono. Sem bairro, a instrução manda ficar com a primeira candidata, e o resultado sai como
`ok` com nota alta, indistinguível de um acerto. A etapa 9 do notebook 04 mede quanto do
resultado caiu nisso. Aumentar o `TOP_N` não resolve, só multiplica opções igualmente plausíveis.

**Reprocessar o notebook 02 invalida vínculos.** O `via_id` deriva do nome, dos bairros e do
centroide, com precisão de 11 m. Edição no OpenStreetMap que estenda ou corte a via move o
centroide mais que isso, e o identificador muda. Não há chave estrangeira e nada avisa.
Reexecutar o 04 sozinho não resolve: `associacao_vias` é indexado por endereço mais bairro, então
o `par_conhecido()` pula a busca e espalha o `via_id` morto outra vez. Rode
`python limpar_associacao.py` para ver o diagnóstico e depois com `--confirmar`. Ele apaga só as
decisões órfãs; a padronização é preservada, o 03 não roda de novo. A etapa 2 do notebook 05
também mede isso.

**`vias_processadas` é de uma cidade só.** Guarda o nome da cidade em texto, sem código do IBGE.
Reprocessar a malha para outra cidade sem limpar a associação faz as decisões antigas, indexadas
sem município, serem reaproveitadas para a cidade nova. Trocou de município, rode
`limpar_associacao.py --tudo --confirmar`.

**Reprocessar o RENAEST não corrige o que já foi revisado.** `acidentes` é substituída a cada
execução do notebook 01, mas `acidentes_revisado` copia com `INSERT OR IGNORE` por
`num_acidente`.

**O cache congela a malha.** A pasta `cache/` guarda as respostas da Overpass API. Enquanto ela
existir, reexecutar o notebook 02 é rápido e devolve a mesma malha, mesmo que o OpenStreetMap já
tenha mudado. Para pegar a malha atual, apague a pasta. A coluna `baixado_em` de
`vias_processadas` registra de qual versão do mapa cada via veio.

**Sem `sentence-transformers`, a busca é só lexical.** Funciona, mas as candidatas pioram, e é a
qualidade delas que limita o resultado do notebook 04. `data/cache/` vazio significa que nenhuma
execução usou embeddings.

## Relatório

O relatório do PIP fica em `relatorios/`, com o markdown como fonte:

```powershell
python relatorios/gerar_docx.py relatorios/Relatorio_Final_PIP_Fabio_Assis.md relatorios/Relatorio_Final_PIP_Fabio_Assis.docx
```

O comando sobrescreve o `.docx`. Se você editou no Word, passe as mudanças para o markdown
antes, senão elas se perdem.
