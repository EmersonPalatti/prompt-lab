# Pesquisa: portfólio público de experimentos de prompt

Status da verificação cruzada: **parcial**. As afirmações abaixo têm fonte inspecionada. Onde a fonte não cobre o desenho deste repositório, isso está marcado como convenção local ou recomendação.

Objetivo do Prompt Lab, fixado em `AGENTS.md`: experimentos reproduzíveis de prompt para tarefas de dados (SQL, limpeza, interpretação estatística, relatórios), com saída estruturada, métricas simples e história da iteração, publicado no GitHub sem chaves de API.

## O que a prática documentada sustenta

Um portfólio revisável guarda o prompt no Git, pontua a saída com checagens determinísticas ou de execução, e mostra falha e custo ao lado do prompt. Layouts documentados ou separam prompts, providers e testes atrás de um config, ou registram cada caso como objetivo, prompt exato, saída, análise e refinamento. [S1] [S3]

Texto de prompt sozinho não é o que a escrita de praticantes trata como diferença entre demo e projeto revisável. O que esses textos pedem é um conjunto pequeno de casos com saída esperada, rótulos de falha, custo ou latência, e a reexecução para ver melhora ou regressão. Isso é conselho e relato de prática, não um estudo de contratação. [S16] [S17] [S18] [S19]

## Layout que cabe neste repositório

O `AGENTS.md` pede `experiments/<id>/vN/`, `inputs.yaml` e `results.json`. Essa árvore **não** apareceu como padrão nas docs de promptfoo, DSPy, Instructor, OpenAI Evals nem nos READMEs de portfólio inspecionados. A ausência não prova que ninguém a usa. A convenção local continua válida porque conta a história da iteração, que o portfólio público de Hermeticpoet registra de outro jeito: um Markdown por caso com objetivo, prompt exato, saída, análise, refinamento, parâmetros, data, ambiente e link do model card. [S3]

Promptfoo documenta outro corte: um `promptfooconfig.yaml` na raiz aponta para arquivos em `prompts/` e para testes agrupados por domínio (acurácia, segurança, desempenho, borda). Várias versões ficam no mesmo config para comparação. Prompts longos vão para arquivo e entram no Git. [S1]

Recomendação (não é um padrão publicado): manter a pasta de experimento do `AGENTS.md` como unidade de história, e usar o corte do promptfoo só quando um experimento comparar versões ou providers.

```
experiments/001-sql-generation/
  README.md            # problema, hipótese, o que falhou, por que v2 melhorou
  v1/prompt.md
  v1/system.md
  v2/prompt.md
  inputs.yaml          # casos: entrada + esperado
  results.json         # modelo, data, scores, custo; sem segredo
src/prompt_lab/        # carga de prompt, cliente, schemas Pydantic, métricas
evals/                 # pytest determinístico, sem chamada de API
app/                   # Streamlit
prompts/               # só fragmentos reutilizados por mais de um experimento
.env.example
```

O README de cada experimento segue o conteúdo de [S3]: objetivo, prompt citado (caminho do arquivo, não cópia solta no código), saída observada, análise e o que mudou na versão seguinte.

Juiz LLM, se entrar depois, não nasce pronto. A sequência documentada por Hamel Husain é: especialista de domínio, dataset, rótulo binário mais crítica escrita, correção de erro óbvio, e só então revisão do prompt do juiz com exemplos de crítica. Um bom prompt de juiz não é escrito antes de ver esses dados. [S2]

## Como pontuar tarefas de dados

Métricas pedidas pelo `AGENTS.md`: acurácia em campos estruturados, consistência e custo aproximado. O arquivo não define a fórmula. A pesquisa também não achou uma frase que diga que promptfoo é mais leve que pytest. A escolha abaixo é recomendação para este repo.

| Checagem | O que está documentado | Onde roda |
| --- | --- | --- |
| JSON válido e schema | Igualdade com um JSON esperado; asserção de JSON válido; JSON Schema na asserção. [S5] | Pydantic no código; pytest offline com fixtures |
| SQL por execução | Query gerada roda num DuckDB em memória; erro de banco é registrado; linhas são comparadas à parte do texto SQL. [S6] | `evals/`, sem API |
| SQL por texto | No Spider, *exact match* decompõe cláusulas e compara conjuntos, não a string crua. O score oficial de execução do Spider citado no README é contra SQLite, e Test Suite Accuracy é a métrica oficial de Spider, SParC e CoSQL. [S4] | Opcional; não substitui a execução |
| Consistência factual | Par referência/saída classificado como subconjunto, superconjunto, mesmos detalhes ou discordância. Exige outro modelo. [S8] | Só em eval ao vivo, não no CI padrão |
| Custo | Custo reportado pelo provider pode ter teto (exemplo da doc: 0,001) ou entrar como métrica com peso 0, sem alterar o score de qualidade. [S7] A resposta do LiteLLM traz `usage.prompt_tokens` e `usage.completion_tokens`. [S20] | `results.json` |

Pytest descobre `test_*.py` e `*_test.py` no diretório atual e abaixo. [S14] Esse é o runner do CI que não precisa de chave.

Promptfoo entra como integração leve, não como aplicação: `npx promptfoo@latest eval -c promptfooconfig.yaml -o results.json`. A doc de CI pede Node.js `>=22.22.0` (24 LTS recomendado) e passa a chave por secret do GitHub (`OPENAI_API_KEY`). O workflow de exemplo dispara em pull request quando `prompts/**` ou o config mudam. `promptfoo validate` sai com código 1 se o config for inválido, e isso não chama o modelo. [S21] [S22]

Recomendação de CI em dois degraus:

1. Sempre, sem segredo: `uv sync --locked` e `pytest` nos evals determinísticos (schema e SQL no DuckDB com fixtures).
2. Manual ou em workflow separado: eval ao vivo, só se o secret existir. A pesquisa não achou uma página oficial que descreva um workflow de eval de LLM totalmente offline.

## Setup atual para subir no GitHub

`uv init` no template de aplicação define `requires-python` como `>=3.11` e cria `pyproject.toml`, `.python-version`, `README.md` e `src/<pacote>/` com build `uv_build`. O mesmo limite `>=3.11` aparece nos templates `--lib` e `--no-package`. O modo `--bare` mostrado na mesma página usa `>=3.12`, então `>=3.11` não é todos os modos de `uv init`. [S10]

`uv.lock` ao lado de `pyproject.toml` deve ir para o Git. O `.venv` não. O lockfile é gerido pelo uv e não se edita à mão. Em CI, `uv sync --locked` falha se o `pyproject.toml` tiver mudado sem um lock novo. [S11] [S23]

Cliente: o caminho multi-provider deste projeto é LiteLLM. A doc atual aceita `response_format` como modelo Pydantic e lista, para `json_schema` estrito, modelos da OpenAI, Azure, xAI (Grok-2 ou posterior), Gemini, Vertex, Bedrock, Anthropic API, Groq e Ollama. `supports_response_schema` consulta se o par modelo/provider aceita isso. O conteúdo volta em `response.choices[0].message.content`; validar de novo com Pydantic no nosso código. [S20] O guia da OpenAI, caminho alternativo de cliente direto, passa um `BaseModel` em `text_format` para `client.responses.parse` e lê `response.output_parsed`. [S12]

Streamlit multipágina atual prefere `st.Page` com `st.navigation` no entrypoint de `streamlit run`. A pasta irmã `pages/` continua sendo a alternativa automática: cada `.py` vira uma página. [S13]

Segredos: o `Python.gitignore` oficial ignora `.env`, `.venv`, `.pytest_cache/` e `.streamlit/secrets.toml`. O comentário sobre uv deixa a regra que ignoraria `uv.lock` comentada, isto é, o lock entra no Git. [S15] O GitHub faz secret scanning por padrões de provedor, padrões genéricos e detecção por IA, com push protection na maior parte dos padrões de provedor. [S24] Nenhuma doc inspecionada exige um `.env.example`; isso continua convenção deste projeto, com nomes de variável e valores vazios.

## O que publicar na primeira versão

Incluir: `AGENTS.md`, este relatório, READMEs, prompts, `inputs.yaml`, schemas, evals offline, `pyproject.toml`, `uv.lock`, `.python-version`, `.gitignore`, `.env.example`.

Deixar de fora: `.env`, `.venv`, `secrets.toml`, caches, e qualquer `results.json` que tenha sido gerado com chave ou com texto que não se queira público. Um `results.json` de exemplo, com modelo, data e scores, ajuda quem clona o repo. [S3]

## O que esta pesquisa não fecha

- Nenhuma fonte inspecionada é um estudo controlado do que gestores de contratação pontuam. Números como “20 exemplos” são conselho. [S18]
- O wiki do DataTalks.Club pode ser paráfrase editorial; os episódios não foram ouvidos. [S18]
- O post no X é opinião pessoal, sem método nem evidência de empregador. [S19]
- Docs diretas dos SDKs Anthropic, Groq e Ollama, fora do LiteLLM, não foram o caminho recomendado aqui.
- Anthropic documenta estrutura XML dentro do prompt (`instructions`, `context`, `examples`, `input`), não layout de repositório.

## Fontes

- [S1] Managing Large Promptfoo Configurations — https://www.promptfoo.dev/docs/configuration/modular-configs/
- [S2] Using LLM-as-a-Judge For Evaluation — https://hamel.dev/blog/posts/llm-judge/index.html
- [S3] Prompt Engineering Portfolio README — https://github.com/Hermeticpoet/Prompt_Engineering_Portfolio/blob/main/README.md
- [S4] Spider README (Evaluation) — https://github.com/taoyds/spider/blob/master/README.md
- [S5] Promptfoo deterministic metrics — https://www.promptfoo.dev/docs/configuration/expected-outputs/deterministic/
- [S6] Braintrust, LLM Eval For Text2SQL — https://www.braintrust.dev/docs/cookbook/recipes/Text2SQL-Data
- [S7] Promptfoo cost metric, mesma página de [S5]
- [S8] Promptfoo Factuality — https://www.promptfoo.dev/docs/configuration/expected-outputs/model-graded/factuality/
- [S9] `AGENTS.md` deste repositório
- [S10] Creating projects, uv — https://docs.astral.sh/uv/concepts/projects/init/
- [S11] Structure and files, uv — https://docs.astral.sh/uv/concepts/projects/layout/
- [S12] Structured model outputs, OpenAI — https://developers.openai.com/api/docs/guides/structured-outputs
- [S13] Multipage apps, Streamlit — https://docs.streamlit.io/develop/concepts/multipage-apps/overview
- [S14] How to invoke pytest — https://docs.pytest.org/en/stable/how-to/usage.html
- [S15] Python.gitignore — https://raw.githubusercontent.com/github/gitignore/main/Python.gitignore
- [S16] Your AI Product Needs Evals — https://hamelhusain.substack.com/p/evals
- [S17] Patterns for Building LLM-based Systems & Products — https://eugeneyan.com/writing/llm-patterns/
- [S18] AI Engineering Portfolios, DataTalks.Club — https://datatalks.club/podwiki/wiki/ai-engineering-portfolio-projects/
- [S19] Post de Ali Ramadan — https://x.com/AliRamadan/status/2115113983451463863
- [S20] Structured Outputs (JSON Mode), LiteLLM — https://docs.litellm.ai/docs/completion/json_mode e Output — https://docs.litellm.ai/docs/completion/output
- [S21] Testing Prompts with GitHub Actions, Promptfoo — https://www.promptfoo.dev/docs/integrations/github-action/
- [S22] CI/CD Integration e Command Line, Promptfoo — https://www.promptfoo.dev/docs/integrations/ci-cd/ e https://www.promptfoo.dev/docs/usage/command-line/
- [S23] Working on projects, uv — https://docs.astral.sh/uv/guides/projects/
- [S24] Secret security, GitHub Docs — https://docs.github.com/en/code-security/reference/secret-security
