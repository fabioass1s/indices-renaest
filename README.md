# projeto_v2 — pipelines em notebooks

Vincular cada acidente do RENAEST a uma via concreta do banco (`via_id`), e desenhar o
resultado num mapa.

Cinco notebooks, numerados pela ordem de execução. Cada um faz uma etapa, grava no
mesmo banco e explica o que está fazendo enquanto faz.

## Ordem de execução

```
01_ingestao_renaest      ->  tabela `acidentes`
                                 |
02_malha_viaria          ->  tabela `vias_processadas`
                                 |                    |
03_revisao_enderecos  <----------+                    |
   (precisa do 01)      ->  tabela `acidentes_revisado`
                                 |                    |
04_associacao_vias    <----------+--------------------+
   (precisa do 02 e do 03)  ->  coluna `via_id_associada`
                                 |
05_mapa_calor         <----------+
   (precisa do 02 e do 04)  ->  tabela `acidentes_por_via`
                                 e `data/mapas/mapa_calor_vias.html`
```

O **01** e o **02** são independentes entre si — rode na ordem que quiser. O **03**
exige o 01. O **04** exige os dois anteriores. O **05** exige o 02 e o 04.

Os notebooks 03 e 04 processam **um município e um ano por execução**.

## Você edita um arquivo só: `parametros.py`

Município, ano, tamanho de lote, aparência do mapa — tudo vive no `parametros.py`.
Nenhuma primeira célula de notebook tem valor escrito à mão; todas apenas dão nomes
curtos ao que vem de lá.

A divisão entre os dois arquivos de configuração:

- **`parametros.py`** — o que você quer processar. Muda a cada execução.
- **`config.py`** — onde as coisas estão: caminho do banco, pastas, chave e modelo da
  IA, nomes de coluna do RENAEST. Muda raramente.

O município é escolhido **uma vez**, pelo código do IBGE, e o nome da cidade usado na
consulta ao OpenStreetMap é derivado dele. Antes o notebook 02 trazia `CIDADE` e
`ESTADO` escritos à mão enquanto os notebooks 03, 04 e 05 usavam `CODIGO_IBGE` — duas
formas de dizer a mesma coisa, livres para divergir. Quando divergiam, os acidentes de
uma cidade eram associados às ruas de outra, aproveitando nomes que coincidem, e o
resultado saía marcado como `ok` sem nenhum aviso.

## Antes da primeira execução

Hoje nenhum ambiente conda tem tudo o que os notebooks precisam:

| | `base` | `brabo` |
|---|---|---|
| JupyterLab | sim | não |
| geopandas, osmnx | não | sim |
| openai, python-dotenv | não | sim |
| sentence-transformers | não | não |

O caminho é rodar o **JupyterLab do `base`** com o **kernel do `brabo`**, e completar
o que falta no `brabo`.

```powershell
# 1. completa as bibliotecas que faltam no brabo
conda activate brabo
pip install openai python-dotenv               # ja instalados
pip install sentence-transformers accelerate   # opcional, ~2 GB (puxa o torch)

# 2. registra o brabo como kernel do Jupyter (só na primeira vez)
python -m ipykernel install --user --name brabo --display-name "Python (brabo)"

# 3. abre o JupyterLab, que vive no base
conda activate base
jupyter lab
```

Ao abrir cada notebook, **selecione o kernel `Python (brabo)`**. Com o kernel padrão
`python3` (o `base`), a primeira célula falha em `import geopandas`.

A `DEEPSEEK_API_KEY` é lida do `.env` da raiz do repositório. Sem ela, os notebooks
03 e 04 param na primeira célula com mensagem explícita.

Sem `sentence-transformers`, a busca do notebook 04 cai para comparação de texto
apenas — funciona, mas as candidatas pioram, e é justamente a qualidade delas que
limita o resultado final.

## Arquivos

| arquivo | o que é |
|---|---|
| `parametros.py` | **o único que você edita.** Município, ano, lotes, aparência do mapa. Os cinco notebooks importam daqui |
| `config.py` | caminhos, `.env`, chave e modelo da IA, nomes de coluna. Onde as coisas estão |
| `busca.py` | o `MotorBusca`. É biblioteca, não etapa; só o notebook 04 usa |
| `limpar_associacao.py` | apaga vínculos que apontam para vias que não existem mais. Rode depois de reprocessar o notebook 02 |
| `data/db/db_main.db` | o banco. Criado na primeira execução |
| `data/cache/` | embeddings do motor de busca, gerados uma vez |
| `data/temp/` | o ZIP do RENAEST e sua extração |
| `data/mapas/` | o HTML gerado pelo notebook 05 |

## Um banco só, sem fallback

Tudo que os notebooks leem foi gravado por um deles. Não há leitura automática de
nenhum outro banco.

Os arquivos `geometria-renaeste.db` e `sinistros.db` na raiz do repositório são de
outra época e **não** são usados aqui. O dado neles foi produzido por código que não
existe mais nesta forma — importar dali encheria o banco com resultados que nenhum
notebook daqui gerou, e depois não haveria como explicar de onde saíram.

Consequência prática: o notebook 02 sempre baixa e processa a malha do OpenStreetMap.
Demora alguns minutos na primeira vez.

## Se um nome de coluna do RENAEST mudar

Os notebooks 03 e 04 dependem de cinco colunas da tabela `acidentes`:
`num_acidente`, `ano_acidente`, `codigo_ibge`, `end_acidente`, `bairro_acidente`.

Esses nomes vieram da versão anterior do projeto e **nunca foram conferidos contra o
CSV real** — até agora nenhum script daqui tinha carregado o arquivo de acidentes em
banco. A etapa 6 do notebook 01 confere e mostra o que faltou.

Se algum nome estiver diferente, corrija as constantes `COLUNA_*` no `config.py`. É o
único lugar onde eles aparecem.

## Limitações conhecidas

Estas não são falhas de código. São limites do método, e valem para qualquer
resultado que sair daqui.

### 1. Nome repetido é o teto da qualidade

Cerca de **35% das vias compartilham nome com outra via da mesma cidade** — existem
23 ruas chamadas `Rua 1` em Aparecida de Goiânia. Dessas vias que colidem, **38% não
têm bairro nenhum** para servir de desempate, porque o OpenStreetMap não tem o
polígono daquele bairro.

Quando não há bairro para desempatar, a instrução manda ficar com a primeira
candidata — que entre várias homônimas é praticamente arbitrária. O resultado sai
marcado como `ok`, com nota alta, e nada na tabela distingue esse caso de um acerto
real.

A etapa 9 do notebook 04 mede exatamente quanto do seu resultado caiu nessa
situação. **Olhe esse número antes de usar os dados.**

Aumentar o `TOP_N` não resolve: mostrar 10 homônimas em vez de 6 só aumenta o número
de opções igualmente plausíveis. A saída real seria associar por coordenada, usando o
`buffer` de 150 m que o notebook 02 já grava e ninguém ainda lê — mas isso depende de
o RENAEST trazer latitude e longitude do acidente.

### 2. Reprocessar as vias invalida os vínculos

O `via_id` é derivado do nome, dos bairros e do centroide da via, com precisão de
cerca de 11 metros. Qualquer edição no OpenStreetMap que estenda ou corte a via move o
centroide muito mais que isso, e o identificador muda.

Aí `via_id_associada` e o dicionário `associacao_vias` passam a apontar para vias que
não existem mais. Não há chave estrangeira e nada avisa.

**Reexecutar o notebook 04 sozinho não resolve.** O dicionário `associacao_vias` é
indexado por endereço + bairro, então o `par_conhecido()` vê o par, pula a busca e a IA,
e espalha o `via_id` morto outra vez — marcado como `ok`, com nota.

Rode `python limpar_associacao.py` (mostra o diagnóstico) e depois com `--confirmar`.
Ele apaga **só** as decisões órfãs e devolve o recorte para `parcial`, para o 04 refazer
apenas o que ficou sem decisão. A padronização de endereço é preservada — o notebook 03
não precisa rodar de novo.

Na prática o estrago é parcial e concentrado: reprocessar a mesma cidade pouco depois
devolve quase a mesma geometria, então a maioria dos `via_id` sobrevive. Numa medição
real, 116 de 2.475 decisões ficaram órfãs — mas elas carregavam 1.330 acidentes, 22% do
total, porque as vias que quebram são as grandes.

A etapa 2 do notebook 05 mede isso e avisa. A coluna `baixado_em` na tabela
`vias_processadas` registra de qual versão do mapa aquele resultado veio.

### 3. A tabela de vias é de uma cidade só

`vias_processadas` guarda uma cidade por vez, e não guarda o código do IBGE — só o nome
da cidade, em texto.

O `parametros.py` fecha a porta principal: o município é escolhido uma vez, pelo código
do IBGE, e o nome usado na consulta ao OpenStreetMap é derivado dele, então o notebook 02
e os notebooks 03/04/05 não podem mais falar de cidades diferentes.

O que continua aberto: se você reprocessar a malha para outra cidade **sem** limpar a
associação, as decisões antigas seguem no dicionário, indexadas por endereço + bairro
sem município, e serão reaproveitadas para a cidade nova. Trocou de município, rode o
`limpar_associacao.py --tudo --confirmar`.

E o notebook 05 não consegue conferir automaticamente que a malha é da cidade certa,
porque o código do IBGE não está na tabela de vias. Ele imprime a cidade e pede
conferência a olho.

### 4. Reprocessar o RENAEST não corrige o que já foi revisado

A tabela `acidentes` é substituída a cada execução do notebook 01, mas `acidentes_revisado`
copia com `INSERT OR IGNORE` por `num_acidente`. Uma linha corrigida na fonte não
atualiza a versão já revisada.

## O que mudou em relação à versão em API

O código veio de `api/pipelines/`, que continua funcionando e não foi tocada. Além dos
comentários e da narrativa, cinco correções entraram na migração:

- **A revisão travava em `parcial` para sempre.** Endereços como `NAO INFORMADO` fazem o
  Gemini responder `null`, que é a resposta certa — mas o código tratava isso como falha
  de chamada e descartava. Os pares nunca entravam no dicionário, a cobertura nunca
  fechava, e **toda execução reenviava os mesmos endereços impossíveis, gastando cota**.
  Agora `null` deliberado e chamada que falhou são coisas diferentes.
- **O aviso de `via_id` duplicado era um erro fatal disfarçado.** Imprimia e seguia, e o
  índice único estourava logo depois, com a tabela já substituída. Agora falha antes de
  gravar.
- **A descoberta do arquivo do RENAEST** assumia que a ordem da lista do portal era
  cronológica. Agora ordena pela data.
- **A instrução do Gemini na associação** dizia "até 10 candidatas" enquanto o código
  enviava 6. Agora o número vem da variável `TOP_N` e não pode divergir.
- **O contador `distintos` da cobertura** era sobrescrito por um número menor ao retomar
  um recorte. Agora soma.
