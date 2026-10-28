# 002 — Limpeza de dados

## Problema

Normalizar registros de pedidos sujos (cidade, status, nulos, chave extra) para `id`, `city`, `status`, `amount`.

## Hipótese

Pedir “as linhas limpas” ainda produz CSV, NDJSON ou objeto solto. Pedir `{"rows": [...]}` no system e no user faz a saída validar; `field_accuracy` pontua os campos à parte.

Uma variável: só o contrato. Sem few-shot.

## Run

| | |
|---|---|
| source | `openrouter` |
| model | `openrouter/nvidia/nemotron-3-ultra-550b-a55b:free` |
| quando | 2026-10-28T01:21:55Z → 01:23:44Z |
| tokens | 3844 prompt + 3642 completion |
| custo USD | 0 (`:free`) |
| repeats | 1 |

## Métricas

`pass_rate` = `json_ok` e `rows_match`. `field_accuracy` = média, por caso, da fração de `city`/`status`/`amount` certos no `id`. Sem JSON válido, o caso fica 0 — não parseamos CSV.

| versão | json_ok | rows_match | field_accuracy | pass_rate |
|---|---|---|---|---|
| v1 — texto | 0/6 | 0/6 | 0.00 | 0.00 |
| v2 — `{"rows": [...]}` | 6/6 | 6/6 | 1.00 | 1.00 |

## v1

Prompt em `v1/prompt.md`. Pede as linhas e nada mais.

O conteúdo muitas vezes estava certo. O envelope não:

- `city_typo`: NDJSON (um objeto por linha). O parser vê lixo depois do primeiro `{`.
- `mixed_batch`: CSV. `Sao Paulo` / city vazia / `99` batem o esperado, mas o scorer não lê tabela.
- `extra_notes`: um objeto `{"id": 1, ...}` sem a chave `rows`. `CleanAnswer` recusa extras.

`pass_rate` 0. O harness recusa adivinhar o formato.

## v2

Prompt em `v2/prompt.md`. System e usuário pedem `{"rows": [...]}`.

6/6 validam e 6/6 batem os campos. `unknown_status` manteve `cancelado`. `extra_notes` dropou `notes`. `null_city` não inventou cidade.

Hipótese confirmada neste modelo e nestes 6 casos.

## O que isso mostra (e o que não mostra)

O mesmo padrão do 001: o ganho veio do contrato, não de few-shot (que nem entrou). Aqui o teto foi 1.0 porque o caso difícil tinha regra explícita (“mantenha o original”), não coluna fantasma.

Não mostra consistência (n=1) nem outro modelo.

## Como reproduzir

```powershell
uv run pytest
uv run python -m prompt_lab score experiments/002-data-cleaning
uv run python -m prompt_lab run experiments/002-data-cleaning
```

O `run` exige `OPENROUTER_API_KEY` e reescreve `outputs/`.
