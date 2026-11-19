# Chat com a OpenAI: configurar e testar de verdade (sem expor a chave)

O chat funciona **sem chave** (responde com um modelo determinístico, baseado nos mesmos fatos, e diz isso). Com chave, o `gpt-4o-mini` redige a resposta usando **somente** os fatos produzidos pelo sistema. Este roteiro leva uns 10 minutos. A chamada real à OpenAI **não pôde ser testada no desenvolvimento** (não havia chave): o teste abaixo é o que falta fazer, uma vez, antes da apresentação.

## 1. Criar a chave (no site da OpenAI)

1. Entre em `platform.openai.com` (a assinatura do ChatGPT **não** paga a API; é uma conta de API à parte).
2. *Billing*: adicione um crédito pequeno (prepago; alguns dólares bastam) e defina um **limite mensal** e um alerta de uso. Esse é o seu teto de gasto, independente do código.
3. *API keys* → *Create new secret key* (de preferência dentro de um projeto só para este trabalho). **Copie a chave na hora**: ela não aparece de novo.

## 2. Colocar a chave no `.env` (e só lá)

1. Abra o arquivo `.env` da pasta do projeto com um editor de texto e preencha a linha (sem aspas e sem espaços):
   `OPENAI_API_KEY=cole_a_chave_aqui`
2. **Nunca** cole a chave no chat com o Claude, no git, em e-mail, em slide ou em captura de tela. O `.env` não vai para o git (confira: `git check-ignore -v .env` deve apontar `.gitignore`), e o contêiner do frontend **não** recebe esse arquivo.
3. Recrie o backend para ele ler o arquivo de novo (`restart` simples não relê o `.env`):

```bash
docker compose up -d --force-recreate backend
```

## 3. Testar

```bash
python scripts/check_openai.py --direct
```

* O script chama o seu `POST /api/v1/chat` e imprime de onde veio a resposta (`source`), o modelo e o começo do texto; com `--direct` ele também pergunta à própria OpenAI se a chave é aceita para o modelo. **Ele nunca imprime a chave**: lê do seu `.env` e a envia só para `api.openai.com`.
* Resultado esperado: `source: openai | model: gpt-4o-mini` e `OpenAI answered HTTP 200: key accepted`.
* Em seguida, no dashboard, abra o chat e faça uma pergunta: a resposta deve indicar que veio do modelo de linguagem (e não "rule-based").

| O que aparece | Significado | O que fazer |
|---|---|---|
| `source: deterministic_fallback`, nota `no OPENAI_API_KEY configured` | O backend não vê a chave | Chave vazia no `.env` ou o backend não foi recriado (passo 2.3) |
| `--direct`: HTTP 401 | Chave recusada (errada, revogada ou com caractere extra copiado) | Gere outra e cole sem espaços |
| `--direct`: HTTP 429 | Sem crédito ou limite de uso atingido | Veja *Billing* e *Usage limits* |
| `--direct`: HTTP 404 | Modelo indisponível para a chave | Troque `OPENAI_MODEL` no `.env` (padrão `gpt-4o-mini`) |
| `--direct` 200 mas a nota diz `language model call failed (...)` | Rede, tempo esgotado (25 s) ou resposta inválida | Tente de novo; o chat nunca quebra: cai no modelo determinístico |

## 4. O que é enviado à OpenAI e o que protege o seu gasto

* Só os **fatos do sistema** (marca, modelo, ano, combustível, tipo de propriedade, quilometragem estimada ou medida, níveis de risco, regras de manutenção, recalls) mais a pergunta do usuário (até 1000 caracteres). **A placa não é enviada** (teste `test_the_plate_is_not_sent_to_the_language_model`), nem dados do proprietário (o sistema não os tem). O texto do usuário nunca entra no prompt de sistema (teste de injeção de instruções).
* O backend limita o chat a **15 perguntas por minuto por endereço** e cada resposta tem tamanho limitado; some a isso o limite mensal que você definiu no passo 1.
* Se a chamada falhar, a nota mostra só o **tipo** do erro, nunca cabeçalhos nem a chave.

## 5. Depois da apresentação

Revogue a chave em *API keys* (ou apague a linha do `.env`) e recrie o backend. Para compartilhar o projeto use sempre `python scripts/make_share_zip.py`: ele só inclui arquivos versionados, então o `.env` nunca entra.
