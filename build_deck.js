const pptxgen = require('pptxgenjs');
const fs = require('fs');

const MID = '21295C';      // midnight - fundo escuro
const DEEP = '065A82';     // azul profundo
const TEAL = '1C7293';     // teal
const AMBER = 'D97A29';    // acento quente (bug/alerta)
const GREEN = '1B7F4B';    // negócio/ok
const INK = '17202A';
const INK2 = '55606E';
const LIGHT = 'FFFFFF';
const TINT = 'EEF3F7';

const HEAD = 'Cambria';
const BODY = 'Calibri';

const pres = new pptxgen();
pres.layout = 'LAYOUT_WIDE'; // 13.3 x 7.5
const W = 13.3, Hh = 7.5;

const img = (p) => 'image/png;base64,' + fs.readFileSync(p).toString('base64');

function titleSlide(s, kicker, title, sub) {
  s.background = { color: MID };
  s.addText(kicker, {
    x: 0.9, y: 1.55, w: 11.5, h: 0.4, isTextBox: true, margin: 0,
    fontFace: BODY, fontSize: 15, color: '9BB4D6', charSpacing: 2,
  });
  s.addText(title, {
    x: 0.9, y: 2.05, w: 11.5, h: 1.5, isTextBox: true, margin: 0,
    fontFace: HEAD, fontSize: 46, bold: true, color: LIGHT,
  });
  s.addText(sub, {
    x: 0.9, y: 3.7, w: 10.6, h: 1.2, isTextBox: true, margin: 0,
    fontFace: BODY, fontSize: 17, color: 'C6D6EA', lineSpacing: 26,
  });
}

function head(s, title, sub) {
  s.background = { color: LIGHT };
  s.addText(title, {
    x: 0.65, y: 0.42, w: 12.0, h: 0.62, isTextBox: true, margin: 0,
    fontFace: HEAD, fontSize: 32, bold: true, color: MID,
  });
  if (sub) {
    s.addText(sub, {
      x: 0.65, y: 1.06, w: 12.0, h: 0.42, isTextBox: true, margin: 0,
      fontFace: BODY, fontSize: 14.5, color: INK2,
    });
  }
}

function card(s, { x, y, w, h, fill = TINT, line }) {
  s.addShape(pres.ShapeType.roundRect, {
    x, y, w, h, rectRadius: 0.09,
    fill: { color: fill },
    line: line ? { color: line, width: 1 } : { color: fill, width: 0 },
  });
}

function circleNum(s, n, x, y, color) {
  s.addShape(pres.ShapeType.ellipse, { x, y, w: 0.42, h: 0.42, fill: { color } });
  s.addText(String(n), {
    x, y, w: 0.42, h: 0.42, isTextBox: true, margin: 0,
    align: 'center', valign: 'middle', fontFace: BODY, fontSize: 12.5, bold: true, color: LIGHT,
  });
}

// ---------------------------------------------------------------- 1 capa
{
  const s = pres.addSlide();
  titleSlide(s, 'LLM’s — ENGENHARIAS AVANÇADAS  ·  MÓDULO 7',
    'Agentic Data Quality Workflow',
    'Um time multiagente como SRE de dados: distinguindo sazonalidade de negócio de bug de dados.\nLangChain · CrewAI · DuckDB · OpenAI');
  s.addText('Raphael Costa   ·   Setembro de 2026', {
    x: 0.9, y: 6.2, w: 8, h: 0.4, isTextBox: true, margin: 0,
    fontFace: BODY, fontSize: 13, color: '8FA6C4',
  });
  s.addNotes('Projeto prático do Módulo 7. A tese: em engenharia de dados, o valor não está na capacidade do LLM gerar SQL — está nas cercas que tornam essa geração segura.');
}

// ---------------------------------------------------------------- 2 a pergunta
{
  const s = pres.addSlide();
  head(s, 'Dois eventos. Uma pergunta.', 'Julho de 2025, tabela de vendas diárias de um varejo');
  const items = [
    { d: '09/07', v: '−30,7%', l: 'abaixo da média móvel de 7 dias', c: GREEN, tag: 'É negócio?' },
    { d: '15/07', v: '+59,6%', l: 'acima da média móvel de 7 dias', c: AMBER, tag: 'É bug?' },
  ];
  items.forEach((it, i) => {
    const x = 0.65 + i * 6.15;
    card(s, { x, y: 1.75, w: 5.7, h: 3.0 });
    s.addText(it.d, { x: x + 0.45, y: 2.0, w: 2, h: 0.4, isTextBox: true, margin: 0, fontFace: BODY, fontSize: 15, bold: true, color: INK2 });
    s.addText(it.v, { x: x + 0.45, y: 2.42, w: 4.8, h: 1.0, isTextBox: true, margin: 0, fontFace: HEAD, fontSize: 54, bold: true, color: it.c });
    s.addText(it.l, { x: x + 0.45, y: 3.5, w: 4.8, h: 0.5, isTextBox: true, margin: 0, fontFace: BODY, fontSize: 14, color: INK2 });
    s.addText(it.tag, { x: x + 0.45, y: 4.02, w: 4.8, h: 0.45, isTextBox: true, margin: 0, fontFace: HEAD, fontSize: 22, bold: true, color: MID });
  });
  card(s, { x: 0.65, y: 5.05, w: 11.85, h: 1.55, fill: MID });
  s.addText([
    { text: 'A armadilha: ', options: { bold: true, color: LIGHT } },
    { text: 'um agente afobado “corrige” os dois — e apaga um fato real do negócio.\nDistinguir os casos exige evidência quantitativa, não intuição do modelo.', options: { color: 'C6D6EA' } },
  ], { x: 1.05, y: 5.25, w: 11.1, h: 1.2, isTextBox: true, margin: 0, fontFace: BODY, fontSize: 16, lineSpacing: 26 });
  s.addNotes('A assimetria entre os dois eventos é o núcleo conceitual do exercício.');
}

// ---------------------------------------------------------------- 3 defeitos
{
  const s = pres.addSlide();
  head(s, 'O que havia de errado na base', '5.117 linhas · maio a julho de 2025');
  const grid = [
    ['26', 'pares de pedidos duplicados', 'double ingestion em 15/07', AMBER],
    ['51', 'linhas com unit_price ≤ 0', 'preço inválido ou zerado', AMBER],
    ['88', 'linhas sem customer_id', 'cliente ausente', TEAL],
    ['1.442', 'linhas com canal fora do domínio', '11 grafias para 3 canais', AMBER],
    ['3', 'formatos de data no mesmo campo', 'resolvido na staging', TEAL],
    ['P99', 'outliers de preço acima de 10×', 'cauda longa de unit_price', TEAL],
  ];
  grid.forEach((g, i) => {
    const col = i % 3, row = Math.floor(i / 3);
    const x = 0.65 + col * 4.05, y = 1.72 + row * 2.35;
    card(s, { x, y, w: 3.75, h: 2.05 });
    s.addShape(pres.ShapeType.rect, { x: x + 0.35, y: y + 0.3, w: 0.055, h: 0.42, fill: { color: g[3] } });
    s.addText(g[0], { x: x + 0.55, y: y + 0.22, w: 3.0, h: 0.6, isTextBox: true, margin: 0, fontFace: HEAD, fontSize: 30, bold: true, color: MID });
    s.addText(g[1], { x: x + 0.35, y: y + 0.92, w: 3.1, h: 0.6, isTextBox: true, margin: 0, fontFace: BODY, fontSize: 13.5, bold: true, color: INK });
    s.addText(g[2], { x: x + 0.35, y: y + 1.5, w: 3.1, h: 0.4, isTextBox: true, margin: 0, fontFace: BODY, fontSize: 11.5, color: INK2, italic: true });
  });
  s.addNotes('Problemas injetados deliberadamente no dataset didático, todos com contraparte no mundo real.');
}

// ---------------------------------------------------------------- 4 arquitetura
{
  const s = pres.addSlide();
  head(s, 'Arquitetura', 'Medalhão em DuckDB — sandbox local, sem dependência externa');
  const steps = [
    ['CSV', 'dado de origem', '9BA7B4'],
    ['raw.sales', 'cópia fiel, sem transformação', TEAL],
    ['stg.sales', 'view: parse de datas, tipos, canal', DEEP],
    ['dry-run', 'sandbox em transação revertida', AMBER],
    ['gold.sales_clean', 'só após aprovação humana', GREEN],
  ];
  const bw = 2.28, gap = 0.28;
  steps.forEach((st, i) => {
    const x = 0.65 + i * (bw + gap);
    card(s, { x, y: 1.85, w: bw, h: 1.75, fill: TINT });
    s.addShape(pres.ShapeType.rect, { x: x + 0.28, y: 2.1, w: 0.05, h: 0.34, fill: { color: st[2] } });
    s.addText(st[0], { x: x + 0.45, y: 2.05, w: bw - 0.6, h: 0.45, isTextBox: true, margin: 0, fontFace: BODY, fontSize: 14.5, bold: true, color: MID });
    s.addText(st[1], { x: x + 0.28, y: 2.6, w: bw - 0.5, h: 0.9, isTextBox: true, margin: 0, fontFace: BODY, fontSize: 11.5, color: INK2, lineSpacing: 15 });
    if (i < steps.length - 1) {
      s.addText('›', { x: x + bw + 0.01, y: 2.5, w: gap, h: 0.4, isTextBox: true, margin: 0, align: 'center', fontFace: BODY, fontSize: 22, bold: true, color: '9BA7B4' });
    }
  });
  card(s, { x: 0.65, y: 3.95, w: 11.85, h: 2.55, fill: TINT });
  const stack = [
    ['LangChain', 'ferramentas SQL controladas — o LLM age só via SQL aprovado'],
    ['CrewAI', 'orquestra 5 agentes em processo sequencial, com handoffs rastreáveis'],
    ['DuckDB', 'lakehouse local: funções de janela, quantile_cont, zero infraestrutura'],
    ['OpenAI', 'gpt-4o para coordenação e revisão; gpt-4o-mini para análise e geração'],
  ];
  stack.forEach((r, i) => {
    const y = 4.2 + i * 0.56;
    s.addShape(pres.ShapeType.ellipse, { x: 1.05, y: y + 0.09, w: 0.16, h: 0.16, fill: { color: DEEP } });
    s.addText(r[0], { x: 1.38, y, w: 2.0, h: 0.4, isTextBox: true, margin: 0, fontFace: BODY, fontSize: 14, bold: true, color: MID });
    s.addText(r[1], { x: 3.35, y, w: 8.7, h: 0.4, isTextBox: true, margin: 0, fontFace: BODY, fontSize: 13.5, color: INK2 });
  });
  s.addNotes('A staging é uma view, não uma tabela: garante que toda reexecução parta do dado bruto.');
}

// ---------------------------------------------------------------- 5 agentes
{
  const s = pres.addSlide();
  head(s, 'Cinco agentes, cinco entregáveis', 'Separação de responsabilidades evita o antipadrão “um LLM faz tudo”');
  const ag = [
    ['Orchestrator', 'Consolida sintomas, prioriza e delega', 'plan.json', '—'],
    ['Analyst', 'Responde “é sazonalidade ou bug?” com evidência', 'analysis_findings.json', 'baseline · série diária · canais'],
    ['DataEngineer', 'Gera SQL de correção seguro e idempotente', 'patch.sql', 'guardrails · dry-run'],
    ['Validator', 'Executa o dry-run e mede o impacto real', 'validation_report.json', 'guardrails · dry-run'],
    ['Reviewer', 'Emite o parecer de causa raiz', 'RCA_report.md', '—'],
  ];
  ag.forEach((a, i) => {
    const y = 1.72 + i * 1.03;
    card(s, { x: 0.65, y, w: 11.85, h: 0.9, fill: i % 2 ? LIGHT : TINT, line: i % 2 ? 'E3E9EF' : null });
    circleNum(s, 'T' + i, 0.95, y + 0.24, [MID, DEEP, TEAL, AMBER, GREEN][i]);
    s.addText(a[0], { x: 1.55, y: y + 0.13, w: 2.1, h: 0.32, isTextBox: true, margin: 0, fontFace: BODY, fontSize: 14, bold: true, color: MID });
    s.addText(a[3], { x: 1.55, y: y + 0.45, w: 2.6, h: 0.32, isTextBox: true, margin: 0, fontFace: BODY, fontSize: 10.5, color: INK2, italic: true });
    s.addText(a[1], { x: 4.35, y: y + 0.26, w: 4.9, h: 0.4, isTextBox: true, margin: 0, fontFace: BODY, fontSize: 13, color: INK });
    s.addText(a[2], { x: 9.45, y: y + 0.26, w: 2.8, h: 0.4, isTextBox: true, margin: 0, fontFace: 'Courier New', fontSize: 11.5, color: DEEP });
  });
  s.addNotes('O raciocínio não fica preso num bloco de texto: vira cinco artefatos versionáveis e auditáveis.');
}

// ---------------------------------------------------------------- 6 diagnóstico
{
  const s = pres.addSlide();
  head(s, 'O discriminante: linhas excedentes por dia', 'O Analyst consulta a evidência — não estima');
  s.addImage({ data: img('reports/figs/sazonalidade.png'), x: 0.65, y: 1.6, w: 7.75, h: 3.37 });
  const verdicts = [
    ['09/07', '39 linhas · 39 pedidos', '0 duplicatas', 'NEGÓCIO', 'feriado estadual em SP', GREEN],
    ['15/07', '83 linhas · 57 pedidos', '26 duplicatas', 'BUG', 'double ingestion', AMBER],
  ];
  verdicts.forEach((v, i) => {
    const y = 1.6 + i * 1.78;
    card(s, { x: 8.75, y, w: 3.75, h: 1.58, fill: TINT });
    s.addText(v[0], { x: 9.05, y: y + 0.12, w: 1.2, h: 0.32, isTextBox: true, margin: 0, fontFace: BODY, fontSize: 13, bold: true, color: INK2 });
    s.addText(v[3], { x: 10.1, y: y + 0.1, w: 2.2, h: 0.36, isTextBox: true, margin: 0, align: 'right', fontFace: HEAD, fontSize: 19, bold: true, color: v[5] });
    s.addText(v[1], { x: 9.05, y: y + 0.52, w: 3.2, h: 0.3, isTextBox: true, margin: 0, fontFace: BODY, fontSize: 12, color: INK });
    s.addText(v[2], { x: 9.05, y: y + 0.82, w: 3.2, h: 0.3, isTextBox: true, margin: 0, fontFace: BODY, fontSize: 12, bold: true, color: v[5] });
    s.addText(v[4], { x: 9.05, y: y + 1.14, w: 3.2, h: 0.3, isTextBox: true, margin: 0, fontFace: BODY, fontSize: 11.5, color: INK2, italic: true });
  });
  card(s, { x: 0.65, y: 5.3, w: 11.85, h: 1.25, fill: MID });
  s.addText([
    { text: 'Menos vendas, dados íntegros → é o negócio.   ', options: { color: 'C6D6EA' } },
    { text: 'Mais linhas, mesmos pedidos → é defeito de pipeline.', options: { color: LIGHT, bold: true } },
  ], { x: 1.05, y: 5.5, w: 11.1, h: 0.5, isTextBox: true, margin: 0, fontFace: BODY, fontSize: 16 });
  s.addText('Consequência assimétrica: 15/07 deve ser deduplicado; 09/07 não deve ser tocado.', {
    x: 1.05, y: 5.95, w: 11.1, h: 0.4, isTextBox: true, margin: 0, fontFace: BODY, fontSize: 13.5, color: '9BB4D6',
  });
  s.addNotes('Este é o slide central da apresentação. O discriminante é a diferença entre linhas e pedidos distintos no dia.');
}

// ---------------------------------------------------------------- 7 label drift
{
  const s = pres.addSlide();
  head(s, 'Label drift: 11 grafias, 3 canais', '28% da base fora do domínio válido');
  s.addImage({ data: img('reports/figs/canais.png'), x: 0.65, y: 1.6, w: 8.3, h: 3.46 });
  const notes = [
    ['market_place', '597 linhas'],
    ['store', '439 linhas'],
    ['on_line', '406 linhas'],
  ];
  card(s, { x: 9.3, y: 1.6, w: 3.2, h: 3.46, fill: TINT });
  s.addText('Sobram após a\nnormalização inicial', { x: 9.6, y: 1.82, w: 2.7, h: 0.7, isTextBox: true, margin: 0, fontFace: BODY, fontSize: 13, bold: true, color: MID, lineSpacing: 18 });
  notes.forEach((n, i) => {
    const y = 2.66 + i * 0.72;
    s.addText(n[0], { x: 9.6, y, w: 2.7, h: 0.32, isTextBox: true, margin: 0, fontFace: 'Courier New', fontSize: 13, bold: true, color: AMBER });
    s.addText(n[1], { x: 9.6, y: y + 0.3, w: 2.7, h: 0.3, isTextBox: true, margin: 0, fontFace: BODY, fontSize: 11.5, color: INK2 });
  });
  s.addText('Exigem CASE WHEN explícito no patch', { x: 9.6, y: 4.6, w: 2.7, h: 0.4, isTextBox: true, margin: 0, fontFace: BODY, fontSize: 11.5, color: INK2, italic: true });
  s.addText('Sem o mapeamento, toda agregação por canal reporta seis segmentos onde existem três — e a participação de cada canal fica sistematicamente subestimada.', {
    x: 0.65, y: 5.35, w: 11.85, h: 0.7, isTextBox: true, margin: 0, fontFace: BODY, fontSize: 14, color: INK2, lineSpacing: 22,
  });
}

// ---------------------------------------------------------------- 8 decisões
{
  const s = pres.addSlide();
  head(s, 'Cinco decisões de design no patch', 'Cada uma responde a um jeito específico de errar');
  const dec = [
    ['ORDER BY determinístico no ROW_NUMBER()', 'Sem ele, qual duplicata sobrevive muda entre execuções — e o patch deixa de ser reprodutível.'],
    ['Winsorizar em [P01, P99], não remover', 'Remover reduziria a massa e distorceria o volume; limitar preserva a linha e contém o outlier.'],
    ['customer_id ausente permanece NULL', 'Imputar cria dado falso com aparência de verdadeiro — pior resultado possível para LTV.'],
    ['Canal desconhecido vira NULL, não bucket-padrão', 'Forçar para “online” mascara o surgimento de um canal novo. O nulo obriga a investigar.'],
    ['Flags de auditoria na própria tabela', 'was_winsorized e was_relabeled permitem medir o efeito sem reprocessar: 149 e 1.434 linhas.'],
  ];
  dec.forEach((d, i) => {
    const col = i % 2, row = Math.floor(i / 2);
    const x = 0.65 + col * 6.15;
    const y = 1.68 + row * 1.72;
    const w = i === 4 ? 11.85 : 5.7;
    card(s, { x, y, w, h: 1.5 });
    circleNum(s, i + 1, x + 0.32, y + 0.28, DEEP);
    s.addText(d[0], { x: x + 0.92, y: y + 0.22, w: w - 1.3, h: 0.38, isTextBox: true, margin: 0, fontFace: BODY, fontSize: 14, bold: true, color: MID });
    s.addText(d[1], { x: x + 0.92, y: y + 0.66, w: w - 1.3, h: 0.7, isTextBox: true, margin: 0, fontFace: BODY, fontSize: 12.5, color: INK2, lineSpacing: 17 });
  });
  s.addNotes('Cada decisão tem uma contrapartida explícita — não é preferência estética.');
}

// ---------------------------------------------------------------- 9 governança
{
  const s = pres.addSlide();
  s.background = { color: MID };
  s.addText('Quatro camadas de contenção', { x: 0.65, y: 0.5, w: 12, h: 0.65, isTextBox: true, margin: 0, fontFace: HEAD, fontSize: 32, bold: true, color: LIGHT });
  s.addText('A falha de uma camada não compromete o conjunto', { x: 0.65, y: 1.14, w: 12, h: 0.4, isTextBox: true, margin: 0, fontFace: BODY, fontSize: 14.5, color: '9BB4D6' });
  const layers = [
    ['Guardrails estáticos', 'Bloqueiam DROP, ALTER, UPDATE e DELETE em raw/stg; exigem CREATE OR REPLACE e ROW_NUMBER; detectam colunas inexistentes.'],
    ['Dry-run reversível', 'O patch roda contra tabela temporária em transação encerrada com ROLLBACK. O banco real nunca é tocado — mas as métricas são medidas de verdade.'],
    ['Gates de aceite', 'Duplicatas zeradas · P99 não aumenta · canal no domínio · customer_id não inventado · perda de linhas ≤ 20%.'],
    ['Aprovação humana', 'REQUIRE_HUMAN_APPROVAL=True. A materialização em gold exige comando explícito — o controle humano fica onde a ação se torna irreversível.'],
  ];
  layers.forEach((l, i) => {
    const y = 1.78 + i * 1.28;
    s.addShape(pres.ShapeType.roundRect, { x: 0.65, y, w: 11.85, h: 1.12, rectRadius: 0.08, fill: { color: '2E3A72' } });
    circleNum(s, i + 1, 1.0, y + 0.35, [TEAL, DEEP, AMBER, GREEN][i]);
    s.addText(l[0], { x: 1.62, y: y + 0.14, w: 3.0, h: 0.4, isTextBox: true, margin: 0, fontFace: BODY, fontSize: 15, bold: true, color: LIGHT });
    s.addText(l[1], { x: 1.62, y: y + 0.55, w: 10.4, h: 0.5, isTextBox: true, margin: 0, fontFace: BODY, fontSize: 12.5, color: 'C6D6EA' });
  });
  s.addNotes('Um LLM capaz de escrever SQL é também capaz de escrever DROP TABLE. O valor de engenharia está nas cercas.');
}

// ---------------------------------------------------------------- 10 resultados
{
  const s = pres.addSlide();
  head(s, 'Resultado medido', 'BEFORE (stg.sales) × AFTER (gold.sales_clean), aprovação concedida');
  s.addChart(pres.ChartType.bar, [
    { name: 'AFTER', labels: ['Duplicatas', 'unit_price ≤ 0', 'Canal fora do domínio'], values: [0, 0, 0] },
    { name: 'BEFORE', labels: ['Duplicatas', 'unit_price ≤ 0', 'Canal fora do domínio'], values: [26, 51, 1442] },
  ], {
    x: 0.65, y: 1.68, w: 7.3, h: 3.5,
    barDir: 'bar', barGrouping: 'clustered', barGapWidthPct: 60,
    chartColors: [GREEN, AMBER],
    showTitle: true, title: 'Defeitos eliminados (linhas)', titleColor: MID, titleFontSize: 14, titleFontFace: BODY,
    showValue: true, dataLabelPosition: 'outEnd', dataLabelColor: INK, dataLabelFontSize: 11, dataLabelFontFace: BODY,
    showLegend: true, legendPos: 'b', legendColor: INK2, legendFontSize: 11,
    catAxisLabelColor: INK2, catAxisLabelFontSize: 11, valAxisLabelColor: INK2, valAxisLabelFontSize: 10,
    valGridLine: { color: 'E3E9EF', size: 1 }, catGridLine: { style: 'none' },
  });
  const stats = [
    ['5.117 → 5.091', 'linhas', '−0,51% — exatamente as 26 duplicatas', GREEN],
    ['88 → 88', 'customer_id ausente', 'preservado, jamais inventado', DEEP],
    ['6 → 3', 'rótulos de canal', 'domínio finalmente fechado', TEAL],
  ];
  stats.forEach((st, i) => {
    const y = 1.68 + i * 1.22;
    card(s, { x: 8.3, y, w: 4.2, h: 1.06 });
    s.addText(st[0], { x: 8.6, y: y + 0.12, w: 3.7, h: 0.42, isTextBox: true, margin: 0, fontFace: HEAD, fontSize: 21, bold: true, color: st[3] });
    s.addText(st[1], { x: 8.6, y: y + 0.53, w: 3.7, h: 0.28, isTextBox: true, margin: 0, fontFace: BODY, fontSize: 12, bold: true, color: INK });
    s.addText(st[2], { x: 8.6, y: y + 0.76, w: 3.7, h: 0.28, isTextBox: true, margin: 0, fontFace: BODY, fontSize: 11, color: INK2, italic: true });
  });
  card(s, { x: 0.65, y: 5.42, w: 11.85, h: 1.1, fill: TINT });
  s.addText([
    { text: 'O que mais importa é o que NÃO mudou: ', options: { bold: true, color: MID } },
    { text: 'as vendas de 09/07 seguem intactas e os 88 registros sem cliente continuam nulos. Corrigiu defeito sem apagar fato.', options: { color: INK } },
  ], { x: 1.0, y: 5.68, w: 11.2, h: 0.6, isTextBox: true, margin: 0, fontFace: BODY, fontSize: 14.5 });
}

// ---------------------------------------------------------------- 11 auditoria
{
  const s = pres.addSlide();
  head(s, 'A parte mais instrutiva: o que deu errado', 'A primeira execução concluiu sem erro — e produziu cinco artefatos inutilizáveis');
  const rows = [
    ['JSON e SQL gravados dentro de cercas ```', 'Sanitização como callback de cada Task'],
    ['Colunas created_at e channel, inexistentes', 'Contrato de esquema no prompt + detector nos guardrails'],
    ['Percentis inventados: 10 e 1000 (reais: 33,87 e 229,28)', 'Baseline medido injetado e consultável como ferramenta'],
    ['INSERT INTO em tabela inexistente', 'Guardrail exige CREATE OR REPLACE e ROW_NUMBER'],
    ['Validação em prosa, sem número algum', 'Ferramenta de dry-run entregue e obrigatória'],
    ['RCA: “correções implementadas com sucesso” — nada aplicado', 'Regra de honestidade + RCA determinístico de contra-prova'],
  ];
  s.addText('Falha observada', { x: 0.95, y: 1.62, w: 5.4, h: 0.32, isTextBox: true, margin: 0, fontFace: BODY, fontSize: 12, bold: true, color: AMBER, charSpacing: 1 });
  s.addText('Correção implementada', { x: 6.9, y: 1.62, w: 5.4, h: 0.32, isTextBox: true, margin: 0, fontFace: BODY, fontSize: 12, bold: true, color: GREEN, charSpacing: 1 });
  rows.forEach((r, i) => {
    const y = 2.02 + i * 0.68;
    card(s, { x: 0.65, y, w: 11.85, h: 0.58, fill: i % 2 ? LIGHT : TINT, line: i % 2 ? 'E3E9EF' : null });
    s.addText(r[0], { x: 0.95, y: y + 0.13, w: 5.7, h: 0.34, isTextBox: true, margin: 0, fontFace: BODY, fontSize: 12.5, color: INK });
    s.addText('›', { x: 6.55, y: y + 0.11, w: 0.3, h: 0.34, isTextBox: true, margin: 0, align: 'center', fontFace: BODY, fontSize: 16, bold: true, color: '9BA7B4' });
    s.addText(r[1], { x: 6.9, y: y + 0.13, w: 5.4, h: 0.34, isTextBox: true, margin: 0, fontFace: BODY, fontSize: 12.5, color: INK });
  });
  s.addText('Padrão comum: o modelo produziu texto plausível na ausência de verificação. Nenhuma dessas falhas se resolve com um prompt melhor.', {
    x: 0.65, y: 6.22, w: 11.85, h: 0.5, isTextBox: true, margin: 0, fontFace: BODY, fontSize: 14, bold: true, color: MID,
  });
  s.addNotes('Oito falhas, um único padrão. A correção é sempre um verificador determinístico entre a saída do modelo e o efeito no mundo.');
}

// ---------------------------------------------------------------- 12 conclusão
{
  const s = pres.addSlide();
  s.background = { color: MID };
  s.addText('Conclusão', { x: 0.9, y: 1.3, w: 11.5, h: 0.7, isTextBox: true, margin: 0, fontFace: HEAD, fontSize: 38, bold: true, color: LIGHT });
  const points = [
    'A viabilidade de agentes autônomos em dados depende menos da capacidade do modelo e mais da qualidade das cercas construídas ao redor dele.',
    'O mesmo LLM que inventou percentis e declarou concluída uma correção jamais aplicada produz resultado confiável quando cada saída passa por um verificador determinístico.',
    'A distinção entre sazonalidade e bug só se tornou confiável quando deixou de ser inferência do modelo e passou a ser consulta a evidência quantitativa.',
  ];
  points.forEach((p, i) => {
    const y = 2.35 + i * 1.25;
    s.addShape(pres.ShapeType.ellipse, { x: 0.95, y: y + 0.14, w: 0.18, h: 0.18, fill: { color: [TEAL, DEEP, AMBER][i] } });
    s.addText(p, { x: 1.42, y, w: 10.7, h: 1.0, isTextBox: true, margin: 0, fontFace: BODY, fontSize: 16.5, color: 'DCE7F3', lineSpacing: 27 });
  });
  s.addShape(pres.ShapeType.roundRect, { x: 0.9, y: 6.05, w: 11.5, h: 0.85, rectRadius: 0.08, fill: { color: '2E3A72' } });
  s.addText('O agente decide o que fazer — mas verificar se o que ele fez está correto não pode ser delegado ao próprio agente.', {
    x: 1.25, y: 6.22, w: 10.9, h: 0.5, isTextBox: true, margin: 0, fontFace: HEAD, fontSize: 16, bold: true, color: LIGHT,
  });
  s.addNotes('Lição transferível para ambientes regulados: saúde, farmacêutico, financeiro.');
}

pres.writeFile({ fileName: 'reports/Apresentacao_Agentic_Data_Quality.pptx' })
  .then(f => console.log('[ok]', f));
