# Limitações dos dois modelos, em linguagem simples (para a defesa)

Regra de ouro: **diga as limitações antes de perguntarem**. Todos os números abaixo vêm dos arquivos do projeto (entre parênteses, onde conferir).

## Modelo 1: quilometragem estimada

**O que é.** Não é o hodômetro do carro. É uma **média esperada para carros parecidos** (mesma idade, combustível e tipo de propriedade), ajustada para o nível de Israel com as estatísticas oficiais do CBS. Uma frase para a banca: *"Se você me der a idade, o combustível e o tipo de propriedade, eu digo quanto carros assim costumam ter rodado; não digo quanto este carro rodou."*

**Por que só idade, combustível e propriedade.** São as únicas informações que o registro israelense dá *e* que ajudam nos testes. Marca e modelo foram testados e **não ajudam de forma consistente**: em um mercado pioraram o resultado em 16% e em outros dois melhoraram só 1 a 5% (`docs/FINAL_TECHNICAL_REVIEW.md`, seção 1). Tipo de propriedade (carro de leasing roda mais que carro particular) é o único dado por veículo com base oficial.

**Limitações, em palavras simples**
1. **Não vale para um carro individual.** A faixa mostrada (80%) é larga, mais ou menos do tamanho da própria estimativa, porque carros iguais rodam muito diferente. Não existe odômetro individual em dados abertos de Israel para provar o contrário.
2. **Desempenho: igual a uma tabela.** Em três países, o modelo calibrado fica entre 0,8% melhor e 2,4% pior que uma tabela simples "média por faixa de idade" (`ml/model1_vs_cbs_results.json`). Por isso o sistema nunca chama isso de medição.
3. **Faltam dados para alguns casos, e o sistema avisa** ("Low reliability"): carros elétricos (quase nenhum no treino), híbridos e a gás com mais de 7 anos (2 a 5 carros por ano de idade) e combinações que implicam mais de 40.000 km por ano, mais do que o CBS publica para qualquer grupo. Cerca de 7,6% dos veículos da amostra recebem o aviso (`docs/LIMITATIONS.md`).
4. **A calibração é "por média".** Ela acerta o nível de grupos (idade × propriedade, erro de 3,7% nas células oficiais que não foram usadas no ajuste), mas não reduz a incerteza de um carro.
5. Acima de 13 anos o treino não tem informação: usam-se as taxas anuais oficiais do CBS.

## Modelo 2: risco de defeito na próxima inspeção anual

**O que é.** Uma ordenação: "este carro está mais para o fim ou para o começo da fila dos carros de referência". Mostra três níveis (Baixo, Moderado, Alto). **Não é probabilidade**, não é previsão de quebra, e **não foi validado em carros de Israel**. Uma frase: *"Comparado com milhares de carros ingleses inspecionados, este carro está numa posição de risco baixa, média ou alta para defeito no freio, na parte elétrica ou no motor."*

**Limitações, em palavras simples**
1. **O alvo é "defeito encontrado na inspeção", não "pane".** É o evento real e verificável mais próximo que existe em dados abertos.
2. **Dados de outro país.** Treino com a inspeção inglesa (MOT); validação independente com a holandesa (RDW). Os resultados de inspeção de Israel não são abertos.
3. **Boa parte do nível é a idade.** Carros de 3 a 5 anos quase sempre aparecem em Baixo (96% no freio) e os de 15 a 20 anos em Alto (96%). É o esperado: carro velho tem mais defeito. A linha "comparado com carros da mesma idade" mostra o que sobra além da idade.
4. **O quanto o modelo acrescenta além da idade, em números** (`docs/MODEL2_VS_AGE_BASELINE.md`), comparando com uma regra que usa só a idade, nos mesmos dados de teste:
   * Só com dados do registro, o ganho de AUC é pequeno: +0,02 a +0,03 na Inglaterra. Na Holanda (dados novos para o modelo) é **+0,005 no freio (praticamente nada)**, +0,015 na parte elétrica e +0,019 no motor.
   * Com o resultado da inspeção anterior, o ganho sobe para +0,04 a +0,06 (Inglaterra) e +0,02 a +0,04 (Holanda). Com o hodômetro medido também, até +0,05 a +0,08 (Inglaterra).
   * Dentro de uma mesma idade, o AUC é 0,54 a 0,63 (só registro) contra 0,50 da regra por idade: separa um pouco, não muito. Recall e Precision melhoram alguns pontos percentuais.
   * **Em uma frase honesta:** *"O modelo é uma melhoria modesta sobre classificar só pela idade; o ganho é pequeno para freios sem histórico e maior para a parte elétrica, para o motor e quando há resultado da inspeção anterior ou o hodômetro."*
5. **Não cobre cerca de 29% da frota** (carros com menos de 3 anos, que ainda não passaram na primeira inspeção; elétricos; a gás; mais de 20 anos). O sistema diz "sem estimativa" e explica o motivo, em vez de chutar.
6. **Marca fora do treino** (cerca de 1% dos veículos cobertos) entra como "outras marcas", com aviso. O **nome do modelo do carro não é usado**: não se repetiu da Inglaterra para a Holanda e só uns 50% dos carros de Israel têm um nome que existe no treino.
7. **Odômetro:** o hodômetro *medido* ajuda; a estimativa do Modelo 1 **não** alimenta o Modelo 2 (não ajudou em nenhum experimento). É uma diferença do SRS original, registrada como C24.

## Segurança do sistema, em três frases
Ler é livre; gravar registros exige uma **chave da oficina** (porque o resultado de inspeção gravado é entrada do Modelo 2, e qualquer um poderia mudar o risco do carro de outra pessoa). A chave fica só no `.env` (nunca no navegador nem no git), com limite de requisições, de registros por carro e validação de datas. É propositalmente simples (sem login, como o SRS pede): prova "uma oficina autorizada", não *quem* gravou.

## Perguntas difíceis, respostas curtas
* **"Então para que serve o machine learning?"** — Ele acrescenta uma melhoria modesta sobre a idade, maior quando há histórico de inspeção ou hodômetro, e é a base para o sistema melhorar quando o Ministério abrir os resultados de Israel. A comparação com a regra por idade está documentada, com números, e a escala é apresentada como relativa por isso.
* **"Por que não usar só a idade?"** — Seria quase tão bom para o freio sem histórico. Mas o modelo usa também combustível, marca, histórico e hodômetro, e dá a posição dentro da mesma idade; e a escala comparável entre carros é a mesma.
* **"Isso prevê quebra?"** — Não. Prevê defeito encontrado na inspeção anual, e como posição relativa.
* **"Funciona em Israel?"** — Não foi validado em Israel; a validação foi na Holanda, país diferente do treino. O sistema diz isso na tela.
* **"A quilometragem está certa?"** — É uma média para carros parecidos, com faixa larga; quando não há dados suficientes, o sistema avisa em vez de mostrar um número que pareça preciso.
* **"Por que o hodômetro estimado não entra no Modelo 2, como no SRS?"** — Testei: não melhora nada (variação de AUC entre −0,001 e +0,002). Forçar a ligação seria artificial. O hodômetro *medido* entra e melhora o modelo.
