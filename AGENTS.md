# AGENTS.md

## Projeto
Prompt Lab é um pipeline de avaliação para LLM em tarefa de dados: contrato JSON, execução no DuckDB ou comparação de campos, versões de prompt, tokens/custo, CI offline.

Não é um chat e não é treino de modelo. O recorte de portfólio é **avaliar e versionar** pipelines de SQL e de limpeza.

## Stack atual
- **Linguagem**: Python 3.11+ (desenvolvimento em 3.12)
- **Eval**: DuckDB em memória (SQL) ou acurácia de campo (limpeza)
- **Contrato**: Pydantic (`SqlAnswer`, `CleanAnswer`, `ExperimentSpec`)
- **Runner ao vivo**: LiteLLM → OpenRouter
- **Interface**: Streamlit (lê `outputs/`, não chama modelo)
- **Testes**: pytest em `evals/` (nunca chama API)
- **Gerenciamento**: uv

## Roadmap (não é stack atual)
pandas, Polars, promptfoo, juiz LLM, CoT, change-point, federação.

## Estrutura
```
experiments/001-sql-generation/
experiments/002-data-cleaning/
  README.md
  v1/ v2/          # prompts
  inputs.yaml      # casos + esperado
  outputs/         # texto bruto do modelo
  results.json     # métricas + model + tokens; sem segredo
src/prompt_lab/    # schema, scorer SQL, scorer limpeza, runner
evals/
app/
```

## Convenções
- Cada experimento: problema, hipótese, versões, resultados, o que falhou.
- Saída estruturada (JSON / Pydantic) no contrato do modelo.
- `pytest` e CI nunca leem `.env`.
- Não commitar chaves. `.env` + `.env.example`.
- Modelo pinado (nunca `openrouter/free`).
- Comandos no README principal.

## O que o agente deve fazer
- Manter prompts em `.md` / `.yaml` separados do código.
- Se a v2 perder no run real, iterar v3 — não reescrever `outputs/`.
- Documentar métricas: `json_ok`, `sql_extracted` (diagnóstico), `rows_match`, `pass_rate`.

## O que evitar
- Código monolítico misturando prompt + eval.
- Experimento sem história de iteração.
- Dependências pesadas sem necessidade (além do LiteLLM no runner).
