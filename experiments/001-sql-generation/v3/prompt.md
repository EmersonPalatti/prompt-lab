Esquema:

{{schema}}

Exemplos (mesmo esquema, mesma forma de resposta):

Pergunta: Quantos pedidos têm status paid? Coluna n.
{"sql": "SELECT COUNT(*) AS n FROM orders WHERE status = 'paid'"}

Pergunta: Nomes dos restaurantes em Recife. Coluna name.
{"sql": "SELECT name FROM restaurants WHERE city = 'Recife'"}

Pergunta: {{question}}

Responda com um JSON neste formato, sem texto em volta:

{"sql": "SELECT ..."}
