const fs = require('fs');
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType, PageBreak,
  Table, TableRow, TableCell, WidthType, ShadingType, BorderStyle, ImageRun,
  TableOfContents, Footer, PageNumber, LevelFormat, convertInchesToTwip
} = require('docx');

const INK = '0B0B0B', INK2 = '52514E', ACC = '1F3864', LINE = 'D9D9D9';
const HEAD_BG = '1F3864', ALT_BG = 'F2F4F8';
const PAGE_W = 12240 - 2 * 1440; // Letter, 1" margins => 9360 dxa

const P = (text, opts = {}) => new Paragraph({
  spacing: { after: opts.after ?? 140, line: 300 },
  alignment: opts.align ?? AlignmentType.JUSTIFIED,
  indent: opts.indent,
  children: Array.isArray(text) ? text : [new TextRun({ text, size: 21, color: INK, font: 'Calibri' })],
});

const R = (text, o = {}) => new TextRun({
  text, size: o.size ?? 21, bold: o.bold, italics: o.italics,
  color: o.color ?? INK, font: o.font ?? 'Calibri',
});
const CODE = (text) => new TextRun({ text, size: 19, font: 'Consolas', color: '1F3864' });

const H = (text, level) => new Paragraph({
  heading: level, spacing: { before: 300, after: 160 },
  children: [new TextRun({ text, bold: true, color: ACC, font: 'Calibri' })],
});

const BULLET = (children, level = 0) => new Paragraph({
  numbering: { reference: 'bullets', level },
  spacing: { after: 90, line: 290 },
  children: Array.isArray(children) ? children : [R(children)],
});

const NUM = (children, ref = 'nums') => new Paragraph({
  numbering: { reference: ref, level: 0 },
  spacing: { after: 90, line: 290 },
  children: Array.isArray(children) ? children : [R(children)],
});

function cell(children, { w, bg, bold, align, head }) {
  return new TableCell({
    width: { size: w, type: WidthType.DXA },
    shading: bg ? { type: ShadingType.CLEAR, fill: bg, color: 'auto' } : undefined,
    margins: { top: 90, bottom: 90, left: 130, right: 130 },
    children: [new Paragraph({
      alignment: align ?? AlignmentType.LEFT,
      spacing: { after: 0, line: 260 },
      children: (Array.isArray(children) ? children : [children]).map(c =>
        typeof c === 'string'
          ? new TextRun({ text: c, size: 19, bold: bold || head, color: head ? 'FFFFFF' : INK, font: 'Calibri' })
          : c),
    })],
  });
}

function table(headers, rows, widths, aligns = []) {
  const border = { style: BorderStyle.SINGLE, size: 2, color: LINE };
  const trs = [new TableRow({
    tableHeader: true,
    children: headers.map((h, i) => cell(h, { w: widths[i], bg: HEAD_BG, head: true, align: aligns[i] })),
  })];
  rows.forEach((r, ri) => {
    trs.push(new TableRow({
      children: r.map((c, i) => cell(c, { w: widths[i], bg: ri % 2 ? ALT_BG : undefined, align: aligns[i] })),
    }));
  });
  return new Table({
    columnWidths: widths,
    width: { size: widths.reduce((a, b) => a + b, 0), type: WidthType.DXA },
    borders: { top: border, bottom: border, left: border, right: border, insideHorizontal: border, insideVertical: border },
    rows: trs,
  });
}

const SPACE = (h = 120) => new Paragraph({ spacing: { after: h }, children: [] });

function figure(path, widthPx, heightPx, caption) {
  return [
    new Paragraph({
      alignment: AlignmentType.CENTER, spacing: { before: 120, after: 60 },
      children: [new ImageRun({ type: 'png', data: fs.readFileSync(path), transformation: { width: widthPx, height: heightPx } })],
    }),
    new Paragraph({
      alignment: AlignmentType.CENTER, spacing: { after: 200 },
      children: [R(caption, { size: 18, italics: true, color: INK2 })],
    }),
  ];
}

const kids = [];

// ---------------- Capa ----------------
kids.push(
  SPACE(1400),
  new Paragraph({
    alignment: AlignmentType.CENTER, spacing: { after: 80 },
    children: [R('LLM’s — Engenharias Avançadas', { size: 24, color: INK2 })],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER, spacing: { after: 60 },
    children: [R('Módulo 7 — Projeto Prático com Agentic Workflows com LLM', { size: 22, color: INK2 })],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER, spacing: { before: 420, after: 120 },
    border: { top: { style: BorderStyle.SINGLE, size: 12, color: ACC } },
    children: [],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER, spacing: { after: 100 },
    children: [R('Agentic Data Quality Workflow', { size: 44, bold: true, color: ACC })],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER, spacing: { after: 120 },
    children: [R('Um time multiagente como SRE de dados: distinguindo sazonalidade de negócio de bug de dados com LangChain, CrewAI e DuckDB', { size: 22, color: INK2, italics: true })],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER, spacing: { before: 40, after: 900 },
    border: { bottom: { style: BorderStyle.SINGLE, size: 12, color: ACC } },
    children: [],
  }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 60 }, children: [R('Raphael Costa', { size: 24, bold: true })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 60 }, children: [R('Engenharia de Dados & Machine Learning', { size: 21, color: INK2 })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 60 }, children: [R('Setembro de 2026', { size: 21, color: INK2 })] }),
  new Paragraph({ children: [new PageBreak()] }),
);

// ---------------- Sumário ----------------
kids.push(
  H('Sumário', HeadingLevel.HEADING_1),
  new TableOfContents('Sumário', { hyperlink: true, headingStyleRange: '1-2' }),
  new Paragraph({ children: [new PageBreak()] }),
);

// ---------------- 1 ----------------
kids.push(
  H('1. Introdução e objetivo', HeadingLevel.HEADING_1),
  P('Este relatório documenta a implementação do projeto prático proposto no Módulo 7 da disciplina LLM’s — Engenharias Avançadas: um agentic workflow multiagente que atua como Site Reliability Engineer de dados. O sistema observa uma tabela de vendas diárias, detecta problemas reais de qualidade, distingue variação legítima de negócio de defeito de dados, propõe SQL de remediação, valida o impacto em dry-run e emite um relatório de causa raiz rastreável.'),
  P([
    R('A tese central do projeto é que autonomia sem contenção não é utilizável em ambientes de dados. Um LLM capaz de escrever SQL é também capaz de escrever '),
    CODE('DROP TABLE'),
    R('. Por isso o valor de engenharia aqui não está na capacidade de gerar SQL — está nas '),
    R('cercas', { bold: true }),
    R(' que tornam essa geração segura: sandbox, guardrails estáticos, dry-run reversível, gates de aceite quantitativos e aprovação humana antes da materialização.'),
  ]),
  P('Uma segunda contribuição, não prevista no enunciado original, emergiu da auditoria da execução inicial do projeto: os agentes produziram artefatos sintaticamente inválidos e um relatório final que afirmava uma correção jamais aplicada. A Seção 9 documenta essas falhas e as correções de engenharia que as eliminaram — material que, na prática, é a parte mais instrutiva do trabalho.'),

  H('2. Cenário e dataset', HeadingLevel.HEADING_1),
  P('Uma empresa de varejo mantém uma tabela de vendas diária com 5.117 registros referentes a maio–julho de 2025, distribuídos entre três lojas e três canais de venda. Em julho de 2025 dois eventos chamaram atenção do time de dados:'),
  BULLET([R('queda acentuada em 09/07/2025', { bold: true }), R(' — coincidente com o feriado estadual de São Paulo (Revolução Constitucionalista);')]),
  BULLET([R('pico atípico em 15/07/2025', { bold: true }), R(' — sem campanha de marketing ou evento comercial correspondente.')]),
  P('Somam-se a isso problemas crônicos de qualidade injetados deliberadamente no dataset didático:'),
  SPACE(60),
  table(
    ['Problema', 'Manifestação', 'Volume'],
    [
      ['Double ingestion', 'Pedidos repetidos na mesma chave (order_id, date)', '26 pares / 52 linhas'],
      ['Preço inválido', 'unit_price igual a zero ou nulo', '51 linhas'],
      ['Outliers de preço', 'valores acima de 10× a mediana da categoria', 'cauda além do P99'],
      ['Cliente ausente', 'customer_id vazio', '88 linhas'],
      ['Label drift', 'channel com 11 grafias para 3 canais reais', '1.442 linhas fora do domínio'],
      ['Datas mistas', '%Y-%m-%d, %d/%m/%Y e %Y/%m/%d no mesmo campo', 'tratado na staging'],
    ],
    [2400, 4560, 2400],
    [null, null, AlignmentType.RIGHT],
  ),
  SPACE(160),
  P('A armadilha didática é precisamente a assimetria entre os dois eventos de julho: um agente afobado “corrige” ambos e, ao fazê-lo, apaga um fato real do negócio. Distinguir os dois casos exige evidência quantitativa, não intuição do modelo.'),

  H('3. Arquitetura da solução', HeadingLevel.HEADING_1),
  P([
    R('O pipeline segue a arquitetura medalhão em três camadas dentro de um único arquivo DuckDB, escolhido como '),
    R('data lakehouse de sala de aula', { italics: true }),
    R(': execução local, sem dependência de infraestrutura externa, com dialeto SQL analítico completo (funções de janela, '),
    CODE('quantile_cont'),
    R(', CTEs).'),
  ]),
  SPACE(60),
  table(
    ['Camada', 'Objeto', 'Responsabilidade'],
    [
      ['raw', 'raw.sales (tabela)', 'cópia fiel do CSV, sem transformação — preserva a evidência original'],
      ['staging', 'stg.sales (view)', 'parse multiformato de datas, cast de tipos, normalização inicial de canal'],
      ['gold', 'gold.sales_clean (tabela)', 'dados corrigidos e auditáveis, materializados só após aprovação'],
    ],
    [1500, 2760, 5100],
  ),
  SPACE(160),
  P([
    R('A camada '),
    CODE('stg'),
    R(' é deliberadamente uma '),
    R('view', { italics: true }),
    R(', não uma tabela: garante que qualquer reexecução parta sempre do dado bruto e torna impossível que uma correção parcial se acumule silenciosamente entre rodadas.'),
  ]),
  P([
    R('Sobre essa base, '),
    R('LangChain', { bold: true }),
    R(' fornece as ferramentas SQL controladas, '),
    R('CrewAI', { bold: true }),
    R(' orquestra cinco agentes em processo sequencial, e '),
    R('OpenAI', { bold: true }),
    R(' provê os modelos de raciocínio (gpt-4o para decisões de coordenação e revisão; gpt-4o-mini para as tarefas analíticas e de geração de SQL, onde o custo por token importa mais que a profundidade).'),
  ]),

  H('4. Papéis dos agentes e entregáveis', HeadingLevel.HEADING_1),
  P('A separação de responsabilidades é o que evita o antipadrão “um LLM faz tudo”. Cada agente tem missão, ferramentas e critério de aceite próprios, e cada handoff produz um artefato inspecionável em disco:'),
  SPACE(60),
  table(
    ['#', 'Agente', 'Missão', 'Entregável'],
    [
      ['T0', 'Orchestrator', 'Consolidar sintomas, priorizar e delegar', 'reports/plan.json'],
      ['T1', 'Analyst', 'Responder “é sazonalidade ou bug?” com evidência', 'reports/analysis_findings.json'],
      ['T2', 'DataEngineer', 'Gerar SQL de correção seguro e idempotente', 'reports/patch.sql'],
      ['T3', 'Validator', 'Executar dry-run e medir impacto real', 'reports/validation_report.json'],
      ['T4', 'Reviewer', 'Emitir parecer de causa raiz', 'reports/RCA_report.md'],
    ],
    [560, 1800, 3900, 3100],
  ),
  SPACE(160),
  P('A rastreabilidade decorre dessa granularidade: o raciocínio não fica preso num único bloco de texto do modelo, mas dividido em cinco entregáveis versionáveis que podem ser auditados, comparados entre execuções e discutidos individualmente.'),

  H('5. Diagnóstico: sazonalidade de negócio × bug de dados', HeadingLevel.HEADING_1),
  P([
    R('O agente Analyst recebe a ferramenta '),
    CODE('seasonality_evidence'),
    R(', que devolve a série diária com média móvel de 7 dias, comparação '),
    R('week-over-week', { italics: true }),
    R(' e — o discriminante decisivo — a contagem de linhas excedentes por dia (diferença entre linhas e pedidos distintos). O modelo não estima esses números: ele os consulta.'),
  ]),
);
kids.push(...figure('reports/figs/sazonalidade.png', 620, 270,
  'Figura 1 — Série diária de julho/2025. Os dois eventos têm assinaturas opostas.'));
kids.push(
  SPACE(60),
  table(
    ['Dia', 'Linhas', 'Pedidos distintos', 'Linhas excedentes', 'Desvio vs. MM7', 'Veredito'],
    [
      ['09/07', '39', '39', '0', '−30,7%', 'Negócio (feriado)'],
      ['15/07', '83', '57', '26', '+59,6%', 'Bug (double ingestion)'],
    ],
    [900, 1000, 1900, 1900, 1660, 2000],
    [null, AlignmentType.RIGHT, AlignmentType.RIGHT, AlignmentType.RIGHT, AlignmentType.RIGHT, null],
  ),
  SPACE(160),
  P([
    R('A leitura é inequívoca. Em 09/07 o volume cai 30,7% abaixo da média móvel, mas '),
    R('cada pedido aparece exatamente uma vez', { bold: true }),
    R(' — não há duplicidade. Menos vendas, dados íntegros: é o negócio. Em 15/07 o volume sobe 59,6%, e das 83 linhas apenas 57 correspondem a pedidos distintos; as 26 excedentes são reingestões do mesmo pedido no mesmo dia. Mais linhas, mesmos pedidos: é defeito de pipeline.'),
  ]),
  P('A consequência operacional é assimétrica e merece destaque: 15/07 deve ser deduplicado; 09/07 não deve ser tocado. Aplicar “correção” a uma queda legítima destruiria a evidência de um efeito real de calendário e comprometeria qualquer previsão de demanda construída sobre esses dados.'),

  H('6. Label drift no campo de canal', HeadingLevel.HEADING_1),
  P('O campo channel chega da origem com 11 grafias distintas para três canais reais. A normalização feita na staging (minúsculas, hífen e espaço convertidos em underscore) resolve a maior parte, mas deixa três variantes fora do domínio válido, somando 1.442 linhas — 28% da base.'),
);
kids.push(...figure('reports/figs/canais.png', 620, 256,
  'Figura 2 — Distribuição dos rótulos brutos de canal. Em laranja, os que a normalização inicial não resolve.'));
kids.push(
  P([
    R('As variantes remanescentes — '),
    CODE('market_place'), R(', '), CODE('store'), R(' e '), CODE('on_line'),
    R(' — exigem mapeamento explícito por '),
    CODE('CASE WHEN'),
    R(' no patch. Sem isso, qualquer agregação por canal reporta seis segmentos onde existem três, e a participação de mercado de cada canal fica sistematicamente subestimada.'),
  ]),

  H('7. Patch de remediação e decisões de design', HeadingLevel.HEADING_1),
  P([
    R('O patch materializa '),
    CODE('gold.sales_clean'),
    R(' a partir de '),
    CODE('stg.sales'),
    R(' com '),
    CODE('CREATE OR REPLACE TABLE'),
    R(' — idempotente por construção. Cinco decisões de design merecem justificativa:'),
  ]),
  NUM([R('Deduplicação com ORDER BY determinístico. ', { bold: true }), R('A remoção usa ROW_NUMBER() particionado por (order_id, date_parsed), mantendo rn = 1. O ponto sutil: sem uma cláusula ORDER BY determinística, qual das duplicatas sobrevive varia entre execuções, e o patch deixa de ser reprodutível. Ordena-se por todas as colunas de negócio, garantindo o mesmo resultado em qualquer rodada.')]),
  NUM([R('Winsorização em vez de remoção de outliers. ', { bold: true }), R('Valores de unit_price são limitados ao intervalo [P01, P99] = [33,87; 229,28] com clamp explícito, e preços ≤ 0 recebem P01. Remover os extremos reduziria a massa de dados e distorceria o volume de vendas; limitar preserva a linha e contém o efeito do outlier sobre médias e somas.')]),
  NUM([R('customer_id ausente permanece NULL. ', { bold: true }), R('Imputar um identificador de cliente criaria dado falso com aparência de dado verdadeiro — o pior resultado possível para uma análise de recorrência ou LTV. Um nulo explícito é informação; um identificador inventado é contaminação silenciosa.')]),
  NUM([R('Canal desconhecido vira NULL, não um bucket-padrão. ', { bold: true }), R('Forçar rótulo não reconhecido para “online” — como fazia uma implementação anterior — mascara o surgimento de um canal novo. O nulo obriga a investigação; o bucket-padrão a esconde.')]),
  NUM([R('Flags de auditoria na própria tabela. ', { bold: true }), R('As colunas booleanas was_winsorized e was_relabeled registram quais linhas o patch alterou, permitindo medir o efeito da correção sem reprocessar o pipeline. Na execução documentada: 149 linhas winsorizadas e 1.434 rerrotuladas.')]),

  H('8. Governança: guardrails e human-in-the-loop', HeadingLevel.HEADING_1),
  P('A segurança do workflow é organizada em quatro camadas independentes, de modo que a falha de uma não compromete o conjunto.'),

  H('8.1 Guardrails estáticos', HeadingLevel.HEADING_2),
  P([
    R('Antes de qualquer execução, o SQL gerado passa por análise de padrões que bloqueia '),
    CODE('DROP'), R(', '), CODE('ALTER'), R(', '), CODE('UPDATE'), R(' e '), CODE('DELETE'),
    R(' sobre raw e stg, além de '),
    CODE('ATTACH'), R(', '), CODE('DETACH'), R(', '), CODE('PRAGMA'), R(' e '), CODE('VACUUM'),
    R('. Exige-se também a presença dos elementos obrigatórios (CREATE OR REPLACE e ROW_NUMBER) e detectam-se colunas inexistentes — um erro recorrente do modelo, discutido na Seção 9.'),
  ]),

  H('8.2 Dry-run em sandbox reversível', HeadingLevel.HEADING_2),
  P([
    R('O patch é reescrito para apontar a uma tabela temporária e executado dentro de uma transação encerrada com '),
    CODE('ROLLBACK'),
    R('. O banco real nunca é tocado durante a validação, mas as métricas resultantes são medidas sobre a execução verdadeira do SQL — não estimadas por um modelo. Se o SQL não compila, o erro do DuckDB retorna ao agente para correção.'),
  ]),

  H('8.3 Gates de aceite quantitativos', HeadingLevel.HEADING_2),
  P('O resultado do dry-run é confrontado com cinco critérios objetivos; qualquer reprovação impede a aplicação:'),
  SPACE(60),
  table(
    ['Gate', 'Critério', 'Resultado'],
    [
      ['dedupe_zerou_duplicatas', 'dup_est = 0 na gold', 'passou'],
      ['p99_nao_aumentou', 'P99 da gold ≤ P99 da staging', 'passou'],
      ['canal_dentro_do_dominio', 'nenhum rótulo fora de {online, in_store, marketplace}', 'passou'],
      ['customer_id_nao_inventado', 'nulos preservados, não imputados', 'passou'],
      ['perda_de_linhas_aceitavel', 'redução de linhas ≤ 20%', 'passou (0,51%)'],
    ],
    [2900, 4560, 1900],
  ),
  SPACE(160),

  H('8.4 Aprovação humana', HeadingLevel.HEADING_2),
  P([
    R('Com '),
    CODE('REQUIRE_HUMAN_APPROVAL = True'),
    R(', o SQL é salvo em '),
    CODE('reports/patch.sql'),
    R(' e o fluxo para. A materialização em gold exige comando explícito ('),
    CODE('python -m src.apply_patch --approve'),
    R('), o que preserva o ponto de controle humano exatamente onde a ação se torna irreversível.'),
  ]),

  H('9. Auditoria da execução original: falhas e correções', HeadingLevel.HEADING_1),
  P('A primeira execução do projeto concluiu sem erro aparente e produziu todos os cinco artefatos. Uma inspeção detalhada, porém, revelou que nenhum deles era utilizável. Essa seção documenta as falhas e as correções aplicadas, por serem o aprendizado mais transferível do trabalho.'),
  SPACE(60),
  table(
    ['Falha observada', 'Causa raiz', 'Correção implementada'],
    [
      ['Todos os JSON e o SQL gravados dentro de cercas markdown (```json), tornando-os inválidos',
        'Nenhum pós-processamento entre a saída do modelo e o arquivo em disco',
        'Módulo postprocess.py registrado como callback de cada Task: remove cercas, extrai o JSON balanceado e valida o schema'],
      ['patch.sql referenciando as colunas created_at e channel, inexistentes na staging',
        'Prompt não informava o esquema real; o modelo preencheu com convenções plausíveis',
        'Contrato de dados explícito nas descrições das Tasks + detector de colunas inexistentes nos guardrails'],
      ['Percentis inventados (P01 = 10, P99 = 1000) contra os reais (33,87 e 229,28)',
        'O baseline existia em disco mas não chegava ao agente',
        'Valores medidos injetados no prompt e disponibilizados como ferramenta consultável'],
      ['INSERT INTO em tabela inexistente, violando o requisito de idempotência',
        'Requisito declarado no prompt mas nunca verificado',
        'Guardrail de requisitos obrigatórios exige CREATE OR REPLACE e ROW_NUMBER'],
      ['validation_report.json com impacto descrito em prosa, sem número algum',
        'O Validator não tinha ferramenta de execução — só podia descrever',
        'Ferramenta de dry-run entregue ao agente e obrigatória na descrição da Task'],
      ['RCA declarando “APROVADO: correções implementadas com sucesso” sem nada ter sido aplicado',
        'O Reviewer não tinha acesso ao estado real de aplicação',
        'Regra de honestidade no prompt + gerador determinístico de RCA a partir das métricas medidas'],
      ['tools.py inteiro sem uso: nenhum agente recebia ferramentas',
        'Módulo escrito mas nunca conectado ao crew',
        'Ferramentas atribuídas por papel: Analyst, DataEngineer e Validator'],
      ['gold.sales_clean construída por um script que contornava os agentes',
        'Contorno adotado para destravar a entrega quando o patch do agente falhava',
        'Patch de referência determinístico como fallback auditado, com o patch rejeitado preservado em disco'],
    ],
    [2900, 3100, 3360],
  ),
  SPACE(160),
  P([
    R('Há um padrão comum a essas oito falhas: em todos os casos '),
    R('o modelo produziu texto plausível na ausência de verificação', { bold: true }),
    R('. Nenhuma delas se resolve com um prompt melhor — todas se resolvem com um verificador determinístico entre a saída do modelo e o efeito no mundo. É o mesmo princípio de engenharia que separa um schema validado de um contrato apenas documentado.'),
  ]),
  P([
    R('Vale registrar também a decisão de projeto sobre o fallback. Quando o patch do agente não executa em dry-run, o pipeline não falha nem finge sucesso: adota o patch de referência determinístico, preserva o SQL rejeitado em '),
    CODE('reports/patch_agent_rejected.sql'),
    R(' e registra o acionamento em '),
    CODE('reports/fallback_notice.json'),
    R('. Degradação graciosa com trilha de auditoria, em vez de silêncio.'),
  ]),

  H('10. Resultados', HeadingLevel.HEADING_1),
  P('Métricas medidas no DuckDB antes e depois da aplicação do patch, com aprovação humana concedida:'),
  SPACE(60),
  table(
    ['Métrica', 'BEFORE (stg.sales)', 'AFTER (gold.sales_clean)', 'Δ'],
    [
      ['Linhas', '5.117', '5.091', '−26'],
      ['Duplicatas por (order_id, data)', '26', '0', '−26'],
      ['unit_price ≤ 0 ou nulo', '51', '0', '−51'],
      ['Linhas com canal fora do domínio', '1.442', '0', '−1.442'],
      ['Rótulos distintos de canal', '6', '3', '−3'],
      ['customer_id ausente', '88', '88', '0 (preservado)'],
      ['P01 de unit_price', '33,87', '36,92', '+3,05'],
      ['P99 de unit_price', '229,28', '226,82', '−2,46'],
    ],
    [3200, 2100, 2500, 1560],
    [null, AlignmentType.RIGHT, AlignmentType.RIGHT, AlignmentType.RIGHT],
  ),
  SPACE(160),
  P('A perda total de linhas é de 0,51% — exatamente as 26 duplicatas, nada além disso. O deslocamento dos percentis é o efeito esperado da winsorização e da eliminação dos preços zerados: o P01 sobe porque os zeros deixam de puxar a cauda inferior; o P99 desce porque os extremos superiores foram limitados.'),
  P([
    R('O ponto de maior valor analítico, porém, é o que '),
    R('não', { bold: true, italics: true }),
    R(' mudou. As vendas de 09/07 permanecem intactas na camada gold, e os 88 registros sem cliente continuam nulos. O workflow corrigiu defeito sem apagar fato — que era, desde o início, o critério real de sucesso.'),
  ]),

  H('11. Limitações e próximos passos', HeadingLevel.HEADING_1),
  NUM([R('A correção trata o sintoma, não a causa. ', { bold: true }), R('A deduplicação limpa a camada gold, mas a duplicidade continuará chegando enquanto a ingestão não tiver chave idempotente — uma constraint única em (order_id, date_parsed) ou uma operação MERGE no lugar do append.')], 'nums2'),
  NUM([R('As checagens deveriam ser contratos, não relatórios. ', { bold: true }), R('Hoje o baseline informa; deveria bloquear. Promover as verificações a testes de contrato executados a cada carga, com falha do pipeline quando duplicatas ou rótulos fora do domínio aparecem, transforma diagnóstico em prevenção.')], 'nums2'),
  NUM([R('Feriados deveriam ser dimensão, não conhecimento tácito. ', { bold: true }), R('O sistema depende de um agente inferir que 09/07 é feriado em SP. Uma tabela de calendário tornaria a explicação automática e auditável, além de eliminar uma classe inteira de falso positivo.')], 'nums2'),
  NUM([R('Winsorizar com limites móveis pode mascarar mudança real. ', { bold: true }), R('Se os percentis são recalculados a cada carga, uma elevação legítima de patamar de preço será absorvida como se fosse ruído. Monitorar a série de P01 e P99 ao longo do tempo é condição para usar a técnica com segurança.')], 'nums2'),
  NUM([R('Custo e determinismo do componente LLM. ', { bold: true }), R('Cada execução completa consome tokens e não é reprodutível bit a bit. Para uso recorrente, o caminho é fixar as partes determinísticas em código e reservar o LLM para a interpretação e a narrativa — que é exatamente onde ele agrega valor sobre uma regra.')], 'nums2'),

  H('12. Conclusão', HeadingLevel.HEADING_1),
  P('O projeto demonstra que a viabilidade de agentes autônomos em engenharia de dados depende menos da capacidade do modelo e mais da qualidade das cercas construídas ao redor dele. O mesmo LLM que, sem verificação, inventou percentis, referenciou colunas inexistentes e declarou concluída uma correção jamais aplicada, produz resultado confiável quando cada saída passa por um verificador determinístico e cada ação irreversível exige aprovação humana.'),
  P('A distinção entre sazonalidade e bug — o núcleo conceitual do exercício — só se tornou confiável quando deixou de ser uma inferência do modelo e passou a ser uma consulta a evidência quantitativa. Essa é a lição transferível para ambientes regulados como saúde, farmacêutico e financeiro: o agente decide o que fazer, mas a verificação de que o que ele fez está correto não pode ser delegada ao próprio agente.'),

  H('Referências', HeadingLevel.HEADING_1),
  P('CHASE, H. LangChain Documentation. 2025. Disponível em: https://python.langchain.com/. Acesso em: 10 set. 2026.', { align: AlignmentType.LEFT }),
  P('CREWAI. CrewAI Documentation. 2025. Disponível em: https://docs.crewai.com/. Acesso em: 10 set. 2026.', { align: AlignmentType.LEFT }),
  P('DUCKDB FOUNDATION. DuckDB Documentation. 2025. Disponível em: https://duckdb.org/docs/. Acesso em: 10 set. 2026.', { align: AlignmentType.LEFT }),
  P('RODRIGUES, T. A. LLM’s — Engenharias Avançadas. Material didático da disciplina, 2025.', { align: AlignmentType.LEFT }),
  P('VASWANI, A. et al. Attention is All You Need. Advances in Neural Information Processing Systems, v. 30, p. 5998–6008, 2017.', { align: AlignmentType.LEFT }),
  P('ZHOU, J. et al. LLMOps: Operationalizing Large Language Models. arXiv preprint, 2023. Disponível em: https://arxiv.org/abs/2309.09560. Acesso em: 10 set. 2026.', { align: AlignmentType.LEFT }),
);

const doc = new Document({
  creator: 'Raphael Costa',
  title: 'Agentic Data Quality Workflow — Módulo 7',
  numbering: {
    config: [
      { reference: 'bullets', levels: [{ level: 0, format: LevelFormat.BULLET, text: '•', alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: convertInchesToTwip(0.32), hanging: convertInchesToTwip(0.2) } } } }] },
      { reference: 'nums', levels: [{ level: 0, format: LevelFormat.DECIMAL, text: '%1.', alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: convertInchesToTwip(0.36), hanging: convertInchesToTwip(0.24) } } } }] },
      { reference: 'nums2', levels: [{ level: 0, format: LevelFormat.DECIMAL, text: '%1.', alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: convertInchesToTwip(0.36), hanging: convertInchesToTwip(0.24) } } } }] },
    ],
  },
  styles: {
    default: { document: { run: { font: 'Calibri', size: 21, color: INK } } },
    paragraphStyles: [
      { id: 'Heading1', name: 'Heading 1', basedOn: 'Normal', next: 'Normal', quickFormat: true, run: { size: 30, bold: true, color: ACC, font: 'Calibri' }, paragraph: { spacing: { before: 320, after: 160 } } },
      { id: 'Heading2', name: 'Heading 2', basedOn: 'Normal', next: 'Normal', quickFormat: true, run: { size: 24, bold: true, color: ACC, font: 'Calibri' }, paragraph: { spacing: { before: 240, after: 120 } } },
    ],
  },
  sections: [{
    properties: { page: { size: { width: 12240, height: 15840 }, margin: { top: 1440, bottom: 1440, left: 1440, right: 1440 } } },
    footers: {
      default: new Footer({
        children: [new Paragraph({
          alignment: AlignmentType.CENTER,
          children: [new TextRun({ children: [PageNumber.CURRENT], size: 18, color: INK2 })],
        })],
      }),
    },
    children: kids,
  }],
});

Packer.toBuffer(doc).then(b => {
  fs.writeFileSync('reports/Relatorio_Agentic_Data_Quality.docx', b);
  console.log('[ok] reports/Relatorio_Agentic_Data_Quality.docx');
});
