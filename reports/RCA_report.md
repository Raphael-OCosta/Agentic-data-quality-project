### Contexto

A análise dos dados de vendas revelou várias questões que podem impactar a precisão das decisões de negócios. Problemas como duplicidade de registros, preços zero ou nulos, e variações nos rótulos de canais foram identificados, cada um com diferentes níveis de prioridade e impacto no negócio.

### Evidências

1. **Queda de vendas em 09/07**: Houve uma queda significativa nas vendas, com um desvio de -30,71% em relação à média móvel de 7 dias, possivelmente devido a um feriado em São Paulo. Foram registrados 39 pedidos, comparados a 51 na semana anterior.

2. **Pico de vendas em 15/07**: Um aumento suspeito nas vendas foi observado, com um desvio de +59,62% em relação à média móvel de 7 dias. Foram identificadas 26 linhas duplicadas no dia, sugerindo uma possível ingestão dupla de dados.

3. **Duplicidade de registros**: Foram encontrados 26 pares duplicados, totalizando 52 linhas duplicadas, o que pode levar a análises incorretas.

4. **Registros com customer_id ausente**: Existem 88 registros sem `customer_id`, o que pode afetar a segmentação de clientes.

5. **Preços zero ou nulos**: Foram identificados 51 registros com preços zero ou nulos, distorcendo a análise de receita.

6. **Label drift de channel_norm**: Foram encontrados 1.442 registros fora do domínio esperado para `channel_norm`, com variações como "market_place", "store" e "on_line".

### Correção proposta

- **Duplicidade de registros**: Implementar um processo de deduplicação para remover registros duplicados.
- **Preços zero ou nulos**: Revisar e corrigir registros com preços inválidos.
- **Label drift de channel_norm**: Normalizar os rótulos de canal para garantir consistência com o domínio esperado.
- **Registros com customer_id ausente**: Investigar a origem dos registros ausentes e implementar medidas para garantir a captura completa dos dados de clientes.

### Validação (antes × depois)

- **Antes**: 5.117 registros, 26 pares duplicados, 51 preços zero ou nulos, 1.442 rótulos de canal fora do domínio, 88 `customer_id` ausentes.
- **Depois (simulado)**: 5.091 registros, 0 pares duplicados, 0 preços zero ou nulos, 0 rótulos de canal fora do domínio, 88 `customer_id` ausentes.

### Decisão

**APROVADO para aplicar**: As correções propostas são necessárias para melhorar a integridade dos dados e a precisão das análises de negócios.

### Próximos passos

1. Implementar as correções propostas para deduplicação, normalização de rótulos de canal e revisão de preços.
2. Monitorar continuamente os dados para identificar e corrigir rapidamente quaisquer problemas futuros.
3. Revisar o processo de coleta de dados para garantir a captura completa e precisa de `customer_id`.