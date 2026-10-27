const pptxgen = require('pptxgenjs');
const fs = require('node:fs');
const path = require('node:path');

const pptx = new pptxgen();
pptx.layout = 'LAYOUT_WIDE';
pptx.author = 'Warden Team';
pptx.subject = 'CCD Mini Project — measured software delivery platform';
pptx.title = 'Warden — verifiable delivery for Kubernetes';
pptx.company = 'Batch C2';
pptx.lang = 'en-US';
pptx.theme = {
  headFontFace: 'Cambria',
  bodyFontFace: 'Calibri',
  lang: 'en-US',
};
pptx.defineSlideMaster({
  title: 'LIGHT',
  background: { color: 'F6F8FA' },
  objects: [
    { text: { text: 'WARDEN  /  CCD MINI PROJECT', options: { x: 0.58, y: 7.12, w: 4.2, h: 0.16, fontFace: 'Calibri', fontSize: 9, color: '75808D', margin: 0, isTextBox: true } } },
  ],
  slideNumber: { x: 12.35, y: 7.1, w: 0.35, h: 0.18, color: '75808D', fontFace: 'Calibri', fontSize: 9 },
});

const W = 13.333;
const H = 7.5;
const C = {
  ink: '17212B',
  charcoal: '18212B',
  charcoal2: '263340',
  slate: '536170',
  muted: '75808D',
  light: 'F6F8FA',
  white: 'FFFFFF',
  line: 'DCE3E8',
  teal: '148A83',
  teal2: '56B8AA',
  mint: 'DDF1EB',
  lime: 'B9E769',
  amber: 'E7AD4B',
  amberLight: 'F8EBD1',
  coral: 'D96960',
  coralLight: 'F5E0DE',
  blueLight: 'E6EDF4',
};
const FONT = 'Calibri';
const HEAD = 'Cambria';
const out = path.join(__dirname, '..', 'docs', 'submission', 'Warden-CCD-Project-Presentation.pptx');
fs.mkdirSync(path.dirname(out), { recursive: true });

function text(slide, value, x, y, w, h, opts = {}) {
  slide.addText(value, {
    x, y, w, h,
    fontFace: opts.fontFace || FONT,
    fontSize: opts.fontSize || 16,
    color: opts.color || C.ink,
    bold: opts.bold || false,
    italic: opts.italic || false,
    margin: opts.margin === undefined ? 0 : opts.margin,
    breakLine: false,
    valign: opts.valign || 'mid',
    align: opts.align || 'left',
    fit: 'shrink',
    isTextBox: true,
    paraSpaceAfterPt: opts.paraSpaceAfterPt || 0,
    transparency: opts.transparency,
  });
}

function shape(slide, type, x, y, w, h, fill, line = fill, extra = {}) {
  slide.addShape(type, {
    x, y, w, h,
    rectRadius: 0.12,
    fill: { color: fill },
    line: { color: line, transparency: line === fill ? 100 : 0, width: 1 },
    ...extra,
  });
}

function circle(slide, x, y, d, fill, line = fill) {
  shape(slide, 'ellipse', x, y, d, d, fill, line);
}

function rule(slide, x1, y1, x2, y2, color = C.line, width = 1.5, arrow = false) {
  slide.addShape('line', {
    x: x1, y: y1, w: x2 - x1, h: y2 - y1,
    line: { color, width, endArrowType: arrow ? 'triangle' : 'none' },
  });
}

function card(slide, x, y, w, h, title, body, accent = C.teal, options = {}) {
  shape(slide, 'roundRect', x, y, w, h, options.fill || C.white, options.line || C.line);
  circle(slide, x + 0.22, y + 0.24, 0.28, accent);
  text(slide, title, x + 0.63, y + 0.19, w - 0.86, 0.38, { fontSize: 18, bold: true, color: C.ink });
  text(slide, body, x + 0.25, y + 0.77, w - 0.5, h - 0.94, { fontSize: options.bodySize || 14, color: C.slate, valign: 'top' });
}

function heading(slide, title, kicker, subtitle) {
  if (kicker) text(slide, kicker.toUpperCase(), 0.62, 0.42, 4.8, 0.2, { fontSize: 10, bold: true, color: C.teal });
  text(slide, title, 0.62, 0.76, 12.05, 0.56, { fontFace: HEAD, fontSize: 32, bold: true, color: C.ink });
  if (subtitle) text(slide, subtitle, 0.64, 1.39, 11.8, 0.38, { fontSize: 14, color: C.slate });
}

function stat(slide, x, y, w, h, value, label, accent = C.teal, note = '') {
  shape(slide, 'roundRect', x, y, w, h, C.white, C.line);
  text(slide, value, x + 0.24, y + 0.18, w - 0.48, 0.64, { fontFace: HEAD, fontSize: 34, bold: true, color: accent });
  text(slide, label, x + 0.24, y + 0.92, w - 0.48, 0.46, { fontSize: 15, bold: true, color: C.ink, valign: 'top' });
  if (note) text(slide, note, x + 0.24, y + h - 0.5, w - 0.48, 0.3, { fontSize: 10, color: C.muted, valign: 'top' });
}

function pill(slide, label, x, y, w, fill, color = C.ink) {
  shape(slide, 'roundRect', x, y, w, 0.34, fill, fill);
  text(slide, label, x + 0.1, y + 0.01, w - 0.2, 0.3, { fontSize: 10, bold: true, color, align: 'center' });
}

function node(slide, x, y, w, h, label, sub, fill = C.white, accent = C.teal) {
  shape(slide, 'roundRect', x, y, w, h, fill, C.line);
  circle(slide, x + 0.14, y + 0.16, 0.3, accent);
  text(slide, label, x + 0.54, y + 0.12, w - 0.68, 0.34, { fontSize: 14, bold: true, color: C.ink });
  text(slide, sub, x + 0.2, y + 0.58, w - 0.4, h - 0.68, { fontSize: 10, color: C.slate, valign: 'top' });
}

function notes(slide, value) {
  slide.addNotes(value);
}

// 1 — Cover
{
  const s = pptx.addSlide();
  s.background = { color: C.charcoal };
  text(s, 'WARDEN', 0.78, 0.86, 5.4, 0.84, { fontFace: HEAD, fontSize: 48, bold: true, color: C.white });
  text(s, 'Verifiable delivery for Kubernetes', 0.82, 1.94, 6.6, 0.6, { fontFace: HEAD, fontSize: 27, bold: true, color: C.lime });
  text(s, 'A delivery platform that connects build provenance, policy checks, progressive rollout and recovery.', 0.84, 2.78, 5.8, 0.9, { fontSize: 18, color: 'D9E1E7', valign: 'top' });
  pill(s, 'CCD MINI PROJECT  •  BATCH C2', 0.84, 4.12, 2.68, C.charcoal2, C.white);
  text(s, 'Abhyuday Gupta  ·  Aditya Chetan Thakur  ·  Sankalp Arya  ·  Shaurya Jain', 0.84, 5.88, 6.3, 0.38, { fontSize: 13, color: 'B6C1CB' });
  // Repeated evidence-chain motif: connected nodes, not decoration bars.
  const pts = [[8.2, 1.4], [10.0, 2.35], [8.55, 3.85], [11.05, 4.55], [9.2, 5.75], [11.75, 1.18]];
  [[0,1],[0,2],[1,2],[1,3],[2,4],[3,4],[1,5],[3,5]].forEach(([a,b]) => rule(s, pts[a][0] + 0.22, pts[a][1] + 0.22, pts[b][0] + 0.22, pts[b][1] + 0.22, '50616F', 1.2));
  pts.forEach((p, i) => circle(s, p[0], p[1], i === 1 || i === 4 ? 0.5 : 0.38, i === 1 || i === 4 ? C.lime : C.teal2));
  text(s, 'From source commit\nto healthy workload', 8.2, 6.38, 3.9, 0.56, { fontSize: 14, color: 'C7D3DC', align: 'center' });
  text(s, 'Project results and remaining verification gates  ·  27 October 2026', 0.84, 6.85, 6.8, 0.25, { fontSize: 10, color: '91A0AC' });
  notes(s, 'Open with the platform claim: one repeatable path takes a service from source to a running workload, with evidence at each hand-off. The platform, not the sample services, is the project.');
}

// 2 — Problem
{
  const s = pptx.addSlide('LIGHT');
  heading(s, 'Software delivery has three connected trust gaps', 'Why Warden', 'A signature is useful only when the build, admission decision and runtime behavior are connected.');
  card(s, 0.68, 2.2, 3.82, 2.54, 'Origin', 'Can the running image be traced to a reviewed source change and a known build workflow?', C.teal);
  card(s, 4.76, 2.2, 3.82, 2.54, 'Admission', 'Will the cluster reject an image that is unsigned, altered or produced by an untrusted builder?', C.amber);
  card(s, 8.84, 2.2, 3.82, 2.54, 'Runtime', 'Can a faulty release be detected and rolled back before it affects most requests?', C.coral);
  circle(s, 2.36, 5.48, 0.54, C.teal);
  circle(s, 6.42, 5.48, 0.54, C.amber);
  circle(s, 10.5, 5.48, 0.54, C.coral);
  rule(s, 2.9, 5.75, 6.4, 5.75, C.line, 2, true);
  rule(s, 6.96, 5.75, 10.52, 5.75, C.line, 2, true);
  text(s, 'Evidence should follow the artifact all the way to the workload.', 2.1, 6.34, 9.2, 0.4, { fontFace: HEAD, fontSize: 21, bold: true, color: C.ink, align: 'center' });
  notes(s, 'The project is motivated by software supply-chain incidents and by the operational gap between a successful build and a safe deployment. A valid signature proves provenance but does not, on its own, make the runtime safe. Sources: in-toto and SLSA [2][3].');
}

// 3 — Four synopsis outcomes
{
  const s = pptx.addSlide('LIGHT');
  heading(s, 'Four project outcomes were measured', 'Synopsis outcomes', 'The scorecard separates verified behavior from the remaining managed-database and enforcement gates.');
  const items = [
    ['01', 'Create a service', 'Five complete kind runs; median 8.6 min; zero manual steps.', C.teal, 'MEASURED'],
    ['02', 'Reject untrusted images', '15/15 controlled attack cases refused on kind and AKS; live image policy remains Audit.', C.amber, 'CONTROLLED TEST'],
    ['03', 'Undo a faulty release', '10/10 historical faults and 4/4 app-only injected faults aborted automatically.', C.coral, 'MEASURED'],
    ['04', 'Provision a database', 'CloudNativePG measured on kind and AKS; Azure Flexible Server code awaits live verification.', C.slate, 'PARTIAL'],
  ];
  items.forEach((it, i) => {
    const y = 2.0 + i * 1.06;
    circle(s, 0.82, y + 0.08, 0.48, it[3]);
    text(s, it[0], 0.82, y + 0.08, 0.48, 0.48, { fontSize: 12, bold: true, color: C.white, align: 'center' });
    text(s, it[1], 1.52, y, 2.68, 0.34, { fontSize: 18, bold: true });
    text(s, it[2], 4.14, y, 6.2, 0.58, { fontSize: 13, color: C.slate, valign: 'top' });
    pill(s, it[4], 10.68, y + 0.1, 1.65, it[4] === 'MEASURED' ? C.mint : it[4] === 'PARTIAL' ? C.blueLight : C.amberLight, it[4] === 'MEASURED' ? C.teal : C.ink);
  });
  notes(s, 'Use this as the honest project summary. The controlled attack suite tests Deny-mode policy copies, while live image verification remains Audit. The Azure database composition has been implemented but is not yet live-tested.');
}

// 4 — Architecture
{
  const s = pptx.addSlide('LIGHT');
  heading(s, 'One path connects source, policy and runtime', 'Platform architecture', 'The sample services stay small so the delivery platform and its controls remain visible.');
  node(s, 0.68, 2.45, 2.18, 1.25, 'Developer', 'warden new\nsource + tests', C.white, C.teal);
  node(s, 3.32, 2.45, 2.18, 1.25, 'Build pipeline', 'scan · sign · SBOM\nprovenance', C.white, C.amber);
  node(s, 5.96, 2.45, 2.18, 1.25, 'Promotion', 'digest-only PR\nGitOps desired state', C.white, C.teal);
  node(s, 8.6, 2.45, 1.9, 1.25, 'Argo CD', 'pulls from Git\nno cluster access in CI', C.white, C.coral);
  node(s, 10.96, 2.45, 1.72, 1.25, 'Cluster', 'kind or AKS\nKubernetes', C.white, C.teal);
  rule(s, 2.87, 3.08, 3.28, 3.08, C.slate, 1.8, true);
  rule(s, 5.51, 3.08, 5.92, 3.08, C.slate, 1.8, true);
  rule(s, 8.15, 3.08, 8.56, 3.08, C.slate, 1.8, true);
  rule(s, 10.51, 3.08, 10.92, 3.08, C.slate, 1.8, true);
  card(s, 1.02, 4.43, 3.35, 1.55, 'Admission', 'VAP checks immutable image references. Kyverno checks supply-chain evidence and pod hygiene.', C.amber, { bodySize: 12 });
  card(s, 4.98, 4.43, 3.35, 1.55, 'Progressive delivery', 'Argo Rollouts shifts traffic and evaluates service metrics before promotion.', C.coral, { bodySize: 12 });
  card(s, 8.94, 4.43, 3.35, 1.55, 'Operations', 'Crossplane provides a shared Database API; Prometheus and GitHub Deployments provide evidence.', C.teal, { bodySize: 12 });
  notes(s, 'Argo CD follows Git as the source of desired state. CI never receives cluster credentials. The trust path includes signatures and attestations, policy checks and progressive delivery. This reflects GitOps principles [4].');
}

// 5 — Trust boundary
{
  const s = pptx.addSlide('LIGHT');
  heading(s, 'CI can propose state; it cannot reach the cluster', 'Trust boundary', 'Every image is promoted by digest through Git, then pulled by Argo CD.');
  shape(s, 'roundRect', 0.8, 2.14, 7.34, 3.64, C.white, C.line);
  text(s, 'GitHub Actions', 1.08, 2.42, 2.1, 0.34, { fontSize: 20, bold: true });
  node(s, 1.08, 3.0, 1.82, 1.15, 'Build + scan', 'no cluster creds', C.blueLight, C.teal);
  node(s, 3.36, 3.0, 1.82, 1.15, 'Sign + attest', 'OIDC only here', C.mint, C.amber);
  node(s, 5.64, 3.0, 2.08, 1.15, 'Promote', 'digest-only change', C.amberLight, C.coral);
  rule(s, 2.94, 3.55, 3.32, 3.55, C.slate, 1.6, true);
  rule(s, 5.22, 3.55, 5.6, 3.55, C.slate, 1.6, true);
  text(s, 'No kubeconfig  ·  no kubectl  ·  no cluster token', 1.1, 4.78, 6.9, 0.36, { fontSize: 15, bold: true, color: C.teal, align: 'center' });
  shape(s, 'roundRect', 8.76, 2.14, 3.75, 3.64, C.charcoal, C.charcoal);
  text(s, 'GitOps cluster', 9.1, 2.48, 2.9, 0.42, { fontSize: 22, bold: true, color: C.white });
  circle(s, 9.16, 3.24, 0.6, C.lime);
  text(s, 'Argo CD', 9.96, 3.21, 1.85, 0.35, { fontSize: 19, bold: true, color: C.white });
  text(s, 'pulls desired state', 9.96, 3.63, 1.9, 0.26, { fontSize: 12, color: 'C3D0D9' });
  circle(s, 9.16, 4.48, 0.6, C.teal2);
  text(s, 'Kubernetes', 9.96, 4.45, 1.95, 0.35, { fontSize: 19, bold: true, color: C.white });
  text(s, 'applies reviewed Git state', 9.96, 4.87, 2.1, 0.26, { fontSize: 12, color: 'C3D0D9' });
  rule(s, 7.77, 3.6, 8.55, 3.6, C.teal, 2.5, true);
  text(s, 'Only a Git change crosses the boundary', 4.1, 6.26, 5.2, 0.38, { fontFace: HEAD, fontSize: 19, bold: true, color: C.ink, align: 'center' });
  notes(s, 'Emphasize job-level permissions: only sign-attest gets id-token: write and that job does not run project code. CI has no kubeconfig and does not invoke kubectl. The promoter changes one digest in Git; Argo CD pulls it.');
}

// 6 — Admission layers
{
  const s = pptx.addSlide('LIGHT');
  heading(s, 'Admission is layered; cryptographic checks remain observable', 'Policy controls', 'Fast structural rules are enforced. Image verification stays in Audit until reliability gates pass.');
  const layers = [
    ['01', 'Digest and registry', 'VAP: immutable digests and approved registries', C.teal, C.mint],
    ['02', 'Supply-chain proof', 'Kyverno: signatures, provenance and SBOM', C.amber, C.amberLight],
    ['03', 'Pod hygiene', 'Kyverno: workload security and runtime defaults', C.coral, C.coralLight],
  ];
  layers.forEach((a, i) => {
    const x = 0.9 + i * 4.15;
    shape(s, 'roundRect', x, 2.25, 3.54, 2.1, C.white, C.line);
    circle(s, x + 0.24, 2.51, 0.48, a[3]);
    text(s, a[0], x + 0.24, 2.51, 0.48, 0.48, { fontSize: 12, bold: true, color: C.white, align: 'center' });
    text(s, a[1], x + 0.88, 2.48, 2.35, 0.4, { fontSize: 18, bold: true });
    text(s, a[2], x + 0.28, 3.28, 3.0, 0.64, { fontSize: 13, color: C.slate, valign: 'top' });
    pill(s, i === 1 ? 'AUDIT' : 'DENY', x + 0.28, 4.63, 0.92, a[4], i === 1 ? C.ink : C.teal);
  });
  shape(s, 'roundRect', 1.05, 5.35, 11.2, 0.93, C.charcoal, C.charcoal);
  text(s, 'Observed cost: 14–15 s per warm Pod  ·  webhook timeout: 30 s  ·  measured worst case leaves only 10–15 s margin', 1.38, 5.56, 10.55, 0.48, { fontSize: 15, bold: true, color: C.white, align: 'center' });
  notes(s, 'Native digest and pod hygiene policies are in Deny. Image verification is not. On the pinned Kyverno release, transient fetch failures and webhook timeouts can reject legitimate Pods, so the project keeps that policy in Audit until readiness criteria pass on kind and AKS.');
}

// 7 — E1
{
  const s = pptx.addSlide('LIGHT');
  heading(s, 'A service environment appears from one command', 'E1 · Service scaffolding', 'The CLI creates the service repository and takes it through build, promotion and a healthy rollout.');
  stat(s, 0.9, 2.18, 2.74, 2.28, '5 / 5', 'full kind runs', C.teal, 'all reached a healthy deployment');
  stat(s, 3.92, 2.18, 2.74, 2.28, '8.6 min', 'median time', C.teal, 'range: 7.6–9.6 minutes');
  stat(s, 6.94, 2.18, 2.74, 2.28, '0', 'manual steps', C.teal, 'from command to healthy service');
  shape(s, 'roundRect', 10.0, 2.18, 2.44, 2.28, C.white, C.line);
  text(s, 'warden new', 10.24, 2.54, 1.94, 0.46, { fontFace: HEAD, fontSize: 21, bold: true, color: C.ink, align: 'center' });
  circle(s, 10.31, 3.45, 0.42, C.teal);
  circle(s, 11.63, 3.45, 0.42, C.lime);
  rule(s, 10.75, 3.66, 11.59, 3.66, C.slate, 1.8, true);
  text(s, 'source → rollout', 10.19, 4.02, 2.05, 0.25, { fontSize: 11, color: C.slate, align: 'center' });
  text(s, 'Still open: Azure E1 runs and a hand-timed baseline for comparison.', 2.2, 5.42, 8.9, 0.48, { fontSize: 17, bold: true, color: C.slate, align: 'center' });
  notes(s, 'E1 was run five times on kind. Median end-to-end time was 8.6 minutes and no manual steps were required. Azure runs and the hand-timed baseline were not completed; keep them listed as open.');
}

// 8 — E2 attacks
{
  const s = pptx.addSlide('LIGHT');
  heading(s, 'The controlled attack suite rejected every case', 'E2 · Admission attacks', 'Each adversarial image was denied for its expected reason in tests on kind and AKS.');
  const labels = Array.from({ length: 14 }, (_, i) => `A${String(i + 1).padStart(2, '0')}`);
  labels.forEach((label, i) => {
    const col = i % 7;
    const row = Math.floor(i / 7);
    const x = 1.05 + col * 1.58;
    const y = 2.36 + row * 1.04;
    circle(s, x, y, 0.6, i % 2 ? C.teal : C.charcoal2);
    text(s, label, x, y, 0.6, 0.6, { fontSize: 13, bold: true, color: C.white, align: 'center' });
  });
  stat(s, 1.12, 4.86, 2.85, 1.4, '15 / 15', 'test cases passed', C.teal, 'including one legitimate control');
  shape(s, 'roundRect', 4.5, 4.91, 7.62, 1.32, C.amberLight, C.amberLight);
  text(s, 'Controlled Deny tests are not live enforcement.', 4.88, 5.16, 6.8, 0.35, { fontSize: 19, bold: true, color: C.ink, align: 'center' });
  text(s, 'The live image policy remains in Audit while Kyverno reliability gates are unresolved.', 4.88, 5.62, 6.8, 0.33, { fontSize: 13, color: C.slate, align: 'center' });
  notes(s, 'There are 14 named attack scenarios plus a legitimate workload control, for 15 tests. Both kind and AKS runs passed. These were policy tests in Deny mode, not a claim that the live cluster refuses unverifiable images.');
}

// 9 — E3 / E5 canary
{
  const s = pptx.addSlide('LIGHT');
  heading(s, 'Faulty releases stop early; healthy releases continue', 'E3 + E5 · Progressive delivery', 'Real signed builds moved through GitOps and Argo Rollouts; the app-only batch used no owner merge.');
  stat(s, 0.9, 2.22, 2.65, 2.15, '4 / 4', 'app-only faults aborted', C.coral, 'all on the success-rate check');
  stat(s, 3.82, 2.22, 2.65, 2.15, '147.6 s', 'median abort time', C.coral, 'range: 145.4–149.6 s');
  stat(s, 6.74, 2.22, 2.65, 2.15, '12 / 12', 'healthy canaries promoted', C.teal, 'app-only batch');
  stat(s, 9.66, 2.22, 2.65, 2.15, '0.39%', 'median error share', C.amber, 'injected-fault request share');
  const x = [1.32, 4.14, 7.1, 10.1];
  const names = ['New digest', '5% canary', 'Analysis fails', 'Stable traffic'];
  const fills = [C.blueLight, C.amberLight, C.coralLight, C.mint];
  names.forEach((n, i) => {
    circle(s, x[i], 5.22, 0.52, i === 2 ? C.coral : i === 3 ? C.teal : C.charcoal2);
    text(s, String(i + 1), x[i], 5.22, 0.52, 0.52, { fontSize: 13, bold: true, color: C.white, align: 'center' });
    text(s, n, x[i] - 0.35, 5.92, 1.35, 0.32, { fontSize: 13, bold: true, color: C.ink, align: 'center' });
    if (i < 3) rule(s, x[i] + 0.55, 5.48, x[i + 1] - 0.08, 5.48, C.slate, 1.8, true);
  });
  text(s, 'Abort → fixed release promoted: median 756.6 s', 3.37, 6.47, 6.7, 0.3, { fontSize: 13, color: C.slate, align: 'center' });
  notes(s, 'Keep experiment series distinct: E3 historical kind runs had 10 of 10 faults abort and 10 of 10 healthy promotions. The app-only E5 repeat had four injected-error faults abort at a 147.6-second median, twelve healthy measured canaries promoted, and four fixes promoted. The injected canary affected a median 0.39 percent of requests. Google SRE describes canary release practice [5].');
}

// 10 — E4 database
{
  const s = pptx.addSlide('LIGHT');
  heading(s, 'One Database contract spans local and managed backends', 'E4 · Self-service data', 'The Crossplane v2 API remains the same; the selected implementation changes by cluster.');
  shape(s, 'roundRect', 0.86, 2.15, 4.7, 2.76, C.white, C.line);
  pill(s, 'MEASURED', 1.16, 2.43, 1.18, C.mint, C.teal);
  text(s, 'CloudNativePG', 1.16, 2.95, 3.9, 0.44, { fontFace: HEAD, fontSize: 23, bold: true });
  text(s, 'kind: 804 s cold  ·  21 s warm\nAKS: 138 s\n\nSix connection keys; `psql` connected; wrong password refused.', 1.18, 3.57, 3.9, 1.04, { fontSize: 14, color: C.slate, valign: 'top' });
  shape(s, 'roundRect', 6.0, 2.15, 6.42, 2.76, C.charcoal, C.charcoal);
  pill(s, 'IMPLEMENTED · LIVE TEST PENDING', 6.34, 2.43, 2.65, C.amberLight, C.ink);
  text(s, 'Azure Flexible Server', 6.34, 2.95, 5.4, 0.44, { fontFace: HEAD, fontSize: 23, bold: true, color: C.white });
  text(s, 'Provider + managed identity + narrow role + one-IP firewall are prepared on review branches.\n\nStill required: service-pod connection, readiness, delete and full teardown.', 6.36, 3.57, 5.45, 1.08, { fontSize: 14, color: 'CED8E0', valign: 'top' });
  shape(s, 'roundRect', 1.62, 5.5, 10.0, 0.7, C.mint, C.mint);
  text(s, 'Same developer request  →  backend chosen by the cluster overlay', 2.0, 5.67, 9.2, 0.38, { fontSize: 18, bold: true, color: C.teal, align: 'center' });
  notes(s, 'Current E4 measurements both used CloudNativePG. The Azure Flexible Server code is in open review PRs and has not been live-tested. Do not describe the managed backend as completed until a service Pod connects and deletion plus teardown have been verified.');
}

// 11 — E5 DORA
{
  const s = pptx.addSlide('LIGHT');
  heading(s, 'The app-only release batch produced a complete delivery dataset', 'E5 · DORA measures', 'Twenty scripted deployments across four services; the batch was designed to include four injected faults.');
  stat(s, 0.9, 2.15, 2.68, 2.18, '20', 'deployments', C.teal, 'five per service');
  stat(s, 3.83, 2.15, 2.68, 2.18, '12.5 min', 'median lead time', C.teal, 'commit to deployment record');
  stat(s, 6.76, 2.15, 2.68, 2.18, '12.6 min', 'median recovery', C.coral, 'failure to fixed release');
  stat(s, 9.69, 2.15, 2.68, 2.18, '20%', 'planned failure rate', C.amber, '4 injected faults of 20');
  const services = [['Books', 12.8], ['Loans', 13.1], ['Members', 12.3], ['Notify', 12.5]];
  text(s, 'Median lead by service', 1.12, 4.83, 3.2, 0.34, { fontSize: 17, bold: true });
  services.forEach((v, i) => {
    const y = 5.34 + i * 0.34;
    text(s, v[0], 1.16, y, 1.05, 0.22, { fontSize: 11, color: C.slate });
    shape(s, 'roundRect', 2.3, y + 0.04, v[1] / 15 * 4.4, 0.16, i === 2 ? C.teal2 : C.teal, C.teal);
    text(s, `${v[1]} min`, 6.9, y - 0.02, 0.82, 0.24, { fontSize: 11, bold: true, color: C.slate });
  });
  shape(s, 'roundRect', 8.3, 4.86, 3.82, 1.84, C.amberLight, C.amberLight);
  text(s, 'Read the sample carefully', 8.62, 5.12, 3.2, 0.34, { fontSize: 17, bold: true });
  text(s, 'Short scripted window; synthetic changes; no human review in lead time. Frequency is not normal team cadence.', 8.62, 5.61, 3.1, 0.78, { fontSize: 12, color: C.slate, valign: 'top' });
  notes(s, 'The app-only batch records 20 deployments, 16 successful and four injected failures, with a 12.5-minute median lead time and 12.6-minute median recovery. The 20 percent change-failure and rework rates are produced by the experiment schedule; they are not a measure of routine team performance. DORA metric definitions are grounded in Accelerate research [6].');
}

// 12 — E6
{
  const s = pptx.addSlide('LIGHT');
  heading(s, 'The environment rebuilds from Git on local and Azure', 'E6 · Reproducibility', 'Each successful round returns GitOps applications to healthy and the four sample services to HTTP 200.');
  text(s, 'LOCAL · KIND', 1.18, 2.23, 4.2, 0.32, { fontSize: 12, bold: true, color: C.teal });
  text(s, '12 / 13', 1.12, 2.78, 3.1, 0.74, { fontFace: HEAD, fontSize: 42, bold: true, color: C.ink });
  text(s, 'successful rebuilds', 1.18, 3.63, 3.4, 0.32, { fontSize: 17, bold: true });
  text(s, 'Median 14.8 min  ·  p90 24.2 min', 1.18, 4.2, 3.9, 0.32, { fontSize: 14, color: C.slate });
  shape(s, 'roundRect', 5.8, 2.2, 0.06, 3.2, C.line, C.line);
  text(s, 'AZURE · AKS', 6.64, 2.23, 4.2, 0.32, { fontSize: 12, bold: true, color: C.teal });
  text(s, '5 / 5', 6.58, 2.78, 3.1, 0.74, { fontFace: HEAD, fontSize: 42, bold: true, color: C.ink });
  text(s, 'successful rebuilds from empty', 6.64, 3.63, 4.5, 0.32, { fontSize: 17, bold: true });
  text(s, 'Median 22 min  ·  zero manual steps', 6.64, 4.2, 4.4, 0.32, { fontSize: 14, color: C.slate });
  pill(s, '4 FAILED AZURE ATTEMPTS RETAINED AND EXPLAINED', 6.64, 4.92, 4.02, C.amberLight, C.ink);
  text(s, 'A rebuild ledger records both successes and failures.', 2.3, 6.2, 8.7, 0.34, { fontSize: 18, bold: true, color: C.ink, align: 'center' });
  notes(s, 'E6 met its target: twelve of thirteen local rebuilds succeeded; five Azure rebuilds succeeded from an empty subscription. Four failed Azure attempts are kept and explained in the ledger. The 2026-10-27 fresh local run took 869 seconds; 23 of 23 applications became Synced/Healthy and all four services returned HTTP 200. Its ledger row marks the worktrees dirty because local instruction files were untracked.');
}

// 13 — E8 cost
{
  const s = pptx.addSlide('LIGHT');
  heading(s, 'Verification latency explains why Deny is staged', 'E8 · Admission cost', 'The webhook budget is 30 seconds, so the warm-path margin is real but not comfortable.');
  const gx = 1.35, gy = 3.15, gw = 9.7;
  shape(s, 'roundRect', gx, gy, gw, 0.44, C.blueLight, C.blueLight);
  shape(s, 'roundRect', gx, gy, gw * 0.48, 0.44, C.teal, C.teal);
  shape(s, 'roundRect', gx + gw * 0.48, gy, gw * 0.18, 0.44, C.amber, C.amber);
  rule(s, gx + gw, gy - 0.42, gx + gw, gy + 0.86, C.coral, 2.5);
  text(s, '14–15 s', gx + 0.2, gy - 1.0, 2.2, 0.4, { fontFace: HEAD, fontSize: 27, bold: true, color: C.teal });
  text(s, 'warm verification', gx + 0.2, gy - 0.55, 2.4, 0.28, { fontSize: 12, color: C.slate });
  text(s, '30 s', gx + gw - 0.3, gy - 1.0, 1.0, 0.4, { fontFace: HEAD, fontSize: 27, bold: true, color: C.coral, align: 'right' });
  text(s, 'webhook timeout', gx + gw - 1.65, gy - 0.55, 1.65, 0.28, { fontSize: 12, color: C.slate, align: 'right' });
  text(s, 'Kind and AKS produced similar warm measurements.', 2.3, 4.14, 8.8, 0.36, { fontSize: 16, bold: true, color: C.ink, align: 'center' });
  shape(s, 'roundRect', 2.18, 5.05, 8.95, 0.85, C.amberLight, C.amberLight);
  text(s, 'Next gate: retry transient fetches, then repeat legitimate-pod and attack suites before changing policy mode.', 2.5, 5.25, 8.3, 0.42, { fontSize: 15, color: C.ink, align: 'center' });
  notes(s, 'E8 measured image verification at 14–15 seconds per warm Pod, similarly on kind and AKS. The webhook timeout is 30 seconds. Transient failures and retries make the remaining margin insufficient for a reliable fail-closed policy. Kyverno stays pinned; this project does not upgrade it to meet the deadline.');
}

// 14 — Engineering lessons
{
  const s = pptx.addSlide('LIGHT');
  heading(s, 'The measurements exposed defects before submission', 'Engineering lessons', 'The platform improved through observed failures, not only happy-path demonstrations.');
  const cards = [
    ['Traffic ownership', 'Argo CD reset a Rollouts-managed Service selector and changed canary traffic share. The sync rules were corrected and forced-sync verified.', C.coral],
    ['Policy exemptions', 'Audit reports hid that legitimate database Pods would be blocked in Deny. The test process now checks real workload classes before enforcement.', C.amber],
    ['Deployment counting', 'Argo CD emitted several deployment records for one revision. The CLI now deduplicates promotion commits and uses final deployment status.', C.teal],
  ];
  cards.forEach((v, i) => card(s, 0.82 + i * 4.15, 2.4, 3.7, 2.78, v[0], v[1], v[2], { bodySize: 13 }));
  text(s, 'Failure evidence changed both the implementation and the measurement method.', 2.0, 5.86, 9.1, 0.46, { fontFace: HEAD, fontSize: 20, bold: true, color: C.ink, align: 'center' });
  notes(s, 'Use these examples to explain rigor: a test found three operational mismatches, and each was fixed and remeasured. The canary traffic issue is described in the evaluation record; the report also discusses policy-mode and DORA counting lessons.');
}

// 15 — Open gates
{
  const s = pptx.addSlide('LIGHT');
  heading(s, 'A short list remains before the project is fully closed', 'Submission gates · 27 Oct 2026', 'These are explicit verification and approval tasks, not features being presented as complete.');
  const gates = [
    ['Azure database', 'Review the two PRs; provision a small Flexible Server; connect from a service Pod; delete it and tear down AKS.', C.amber],
    ['Image enforcement', 'Keep Audit on the pinned Kyverno release; Deny requires five clean releases per service, attack coverage and timeout margin.', C.coral],
    ['Evaluation + release', 'Azure E1 and hand-timed baseline are open; tags require reviewed main branches and final documentation.', C.teal],
    ['Presentation', 'Record the four scenes, update this slide on presentation day and obtain supervisor review. The fresh local rebuild rehearsal passed.', C.slate],
  ];
  gates.forEach((g, i) => {
    const y = 2.12 + i * 0.98;
    circle(s, 0.95, y + 0.07, 0.4, g[2]);
    text(s, String(i + 1), 0.95, y + 0.07, 0.4, 0.4, { fontSize: 12, bold: true, color: C.white, align: 'center' });
    text(s, g[0], 1.58, y, 2.38, 0.34, { fontSize: 17, bold: true });
    text(s, g[1], 4.05, y, 7.85, 0.58, { fontSize: 13, color: C.slate, valign: 'top' });
  });
  pill(s, 'NO KYVERNO VERSION CHANGE', 4.84, 6.3, 2.84, C.mint, C.teal);
  notes(s, 'This is the final gate slide. Current review branches include the Azure implementation but are not merged or live-tested. The user asked to keep the Kyverno version unchanged. M3 depends on measured reliability criteria, not just changing policy mode.');
}

// 16 — Conclusion
{
  const s = pptx.addSlide();
  s.background = { color: C.charcoal };
  text(s, 'A safer path from source\nto running software', 0.82, 0.72, 6.4, 1.42, { fontFace: HEAD, fontSize: 38, bold: true, color: C.white, valign: 'top' });
  text(s, 'Warden joins provenance, policy, GitOps and progressive delivery in one measured platform.', 0.86, 2.55, 5.9, 0.9, { fontSize: 19, color: 'D5DEE5', valign: 'top' });
  const blocks = [
    ['TRACE', 'Signed artifacts\nwith build evidence', C.teal2],
    ['CHECK', 'Policies test\nwhat enters', C.amber],
    ['RECOVER', 'Canaries stop\nfaulty releases', C.lime],
  ];
  blocks.forEach((v, i) => {
    const x = 7.28 + i * 1.82;
    circle(s, x + 0.38, 2.1, 0.62, v[2]);
    text(s, v[0], x, 3.0, 1.4, 0.3, { fontSize: 12, bold: true, color: C.white, align: 'center' });
    text(s, v[1], x - 0.05, 3.48, 1.5, 0.76, { fontSize: 12, color: 'C8D2DA', align: 'center', valign: 'top' });
    if (i < 2) rule(s, x + 1.1, 2.42, x + 2.05, 2.42, '62727F', 1.5, true);
  });
  shape(s, 'roundRect', 0.86, 4.56, 11.5, 1.18, C.charcoal2, C.charcoal2);
  text(s, 'What is proven', 1.2, 4.82, 2.1, 0.34, { fontSize: 17, bold: true, color: C.lime });
  text(s, 'Local and AKS rebuilds  ·  15 controlled attacks  ·  canary rollback  ·  app-only delivery metrics', 3.38, 4.82, 8.2, 0.46, { fontSize: 15, color: C.white });
  text(s, 'What is still open', 1.2, 5.3, 2.1, 0.28, { fontSize: 14, bold: true, color: 'F1BC6A' });
  text(s, 'Live managed Azure database verification  ·  reliable image-verification Deny gate', 3.38, 5.3, 8.2, 0.32, { fontSize: 13, color: 'D9E1E7' });
  text(s, 'WARDEN  ·  CCD MINI PROJECT  ·  BATCH C2', 0.9, 6.72, 5.5, 0.24, { fontSize: 10, color: '91A0AC' });
  notes(s, 'Close by emphasizing what is already measured and what remains open. Do not say the synopsis is fully met until the managed Azure database connects from a service Pod and the live image-verification gate is ready.');
}

// 17 — Sources
{
  const s = pptx.addSlide('LIGHT');
  heading(s, 'Selected foundations', 'References', 'Research and technical articles that informed the platform design.');
  const refs = [
    '[1] Verma, A. et al. “Large-scale cluster management at Google with Borg.” EuroSys, 2015.',
    '[2] Torres-Arias, S. et al. “in-toto: Providing farm-to-table guarantees for bits and bytes.” USENIX Security, 2019.',
    '[3] SLSA. “Provenance: Build track.” Supply-chain Levels for Software Artifacts specification.',
    '[4] OpenGitOps. “OpenGitOps Principles.” Cloud Native Computing Foundation.',
    '[5] Beyer, B. et al. “Canarying Releases.” Site Reliability Engineering, Google.',
    '[6] Forsgren, N., Humble, J., Kim, G. Accelerate: The Science of Lean Software and DevOps. IT Revolution, 2018.',
  ];
  refs.forEach((r, i) => {
    const y = 2.05 + i * 0.63;
    circle(s, 0.95, y + 0.05, 0.24, i % 2 ? C.teal2 : C.teal);
    text(s, r, 1.38, y, 10.7, 0.42, { fontSize: 13, color: C.ink });
  });
  text(s, 'Experiment results are documented separately in the project report and evaluation evidence.', 1.38, 6.22, 10.1, 0.35, { fontSize: 12, color: C.slate, italic: true });
  notes(s, 'The references are papers, standards and technical articles. They are intended as design inspirations, not as evidence that Warden itself achieved a result.');
}

(async () => {
  await pptx.writeFile({ fileName: out });
  console.log(`Wrote ${out}`);
})();
