# 001 — Geração de SQL

## Problema

Dada uma pergunta e o esquema de um mini-warehouse de delivery (restaurantes + pedidos), produzir uma consulta DuckDB cuja execução devolva as linhas esperadas. A saída precisa ser um objeto JSON `{"sql": "..."}` para o pipeline não adivinhar onde está a consulta.

O modelo **não** vê os `INSERT`. Só o `CREATE TABLE`. Quem inventa coluna ou hardcoda total falha na execução.

## Hipóteses

1. Pedir “só o SQL” ainda produz texto. Pedir o contrato JSON no system e no user faz a saída validar; a execução pontua a consulta à parte.
2. Com o contrato já no lugar, dois few-shots de JSON válido (perguntas **fora** do eval) sobem o `pass_rate` no caso que a v2 ainda perde.

Uma variável por vez: v1→v2 muda o contrato; v2→v3 só acrescenta exemplos.

## Run

Mesmo modelo nas três versões: `openrouter/nvidia/nemotron-3-ultra-550b-a55b:free`.

| | v1+v2 | v3 |
|---|---|---|
| quando | 2026-10-28T00:37:49Z | 2026-10-28T01:10:49Z (finished_at) |
| source | `openrouter` | `openrouter` |
| custo USD | 0 (`:free`) | 0 |
| repeats | 1 | 1 |

Tokens no `results.json` são a soma dos casos commitados (v1+v2+v3): 2895 prompt + 3830 completion.

`pytest` não chama o modelo. O `run --version v3` não reescreveu `outputs/v1` nem `outputs/v2`.

## Métricas

`pass_rate` = fração dos casos com `json_ok` **e** `rows_match`. `sql_extracted` é diagnóstico e **não** conta como pass.

| versão | json_ok | sql_extracted | rows_match | pass_rate |
|---|---|---|---|---|
| v1 — só SQL | 0/6 | 5/6 | 5/6 | 0.00 |
| v2 — JSON | 6/6 | 6/6 | 5/6 | 0.83 |
| v3 — JSON + 2 few-shots | 5/6 | 5/6 | 5/6 | 0.83 |

## v1

Prompt em `v1/prompt.md`. Pede a consulta e nada mais.

O SQL de 5 casos estava certo (filtro `paid`, `IS NULL`, JOIN, `LIMIT 1`). O contrato não. `paid_by_city` veio com backticks e `;` — o DuckDB aceita, o `SqlAnswer` não.

`unknown_column` recusou em português. Não há SQL para extrair.

Uma consulta certa ainda é `pass_rate` 0.

## v2

Prompt em `v2/prompt.md`. System e usuário pedem `{"sql": "..."}`.

6/6 validam. 5/6 executam certo. `unknown_column` mete a recusa **dentro** de `sql`:

```json
{"sql": "Incompatible schema: courier_rating column does not exist in the provided tables"}
```

`json_ok` verdadeiro. O DuckDB quebra no parser.

Hipótese 1 confirmada neste modelo e nestes casos.

## v3

Prompt em `v3/prompt.md`. Mesmo contrato da v2. Dois exemplos no user: `COUNT` de `paid` e `name` dos restaurantes em Recife — **não** são casos do eval.

Nos 5 casos que a v2 já passava, a v3 também passa. SQL equivalente (JOIN, `IS NULL`, `LIMIT 1`).

No 6º, few-shot **não** subiu o `pass_rate`. Mudou o modo de falha. Em vez de fingir SQL, o modelo inventou outra chave:

```json
{"error": "Incompatible: column 'courier_rating' not found in schema"}
```

`SqlAnswer` tem `extra='forbid'`. Erro: `Extra inputs are not permitted`. `json_ok` cai de 6/6 para 5/6. `pass_rate` fica 0.83.

Hipótese 2 **não** confirmada. Few-shot de sucessos não ensinou o caso de schema inexistente; o modelo saiu do contrato.

## O que isso mostra (e o que não mostra)

O ganho veio do contrato JSON, não dos exemplos. Few-shot aqui foi nulo no `pass_rate` e pior no formato do caso difícil.

Não mostra consistência (n=1) nem outro modelo.

## Próxima iteração (não feita)

Contrato `sql` **ou** `error`. A v3 já tentou emitir `error` sozinha; o scorer recusou. Só vale se o eval passar a aceitar o segundo ramo — senão estamos punindo a recusa honesta.

## Como reproduzir

```powershell
uv run pytest
uv run python -m prompt_lab score experiments/001-sql-generation
uv run python -m prompt_lab run experiments/001-sql-generation --version v3
```

`run` sem `--version` chama **todas** as versões e reescreve `outputs/`. Com `--version` só toca essa pasta. `score` só relê o Git.
