export type ForgeRole = 'AI Engineer' | 'Backend Engineer' | 'ML Platform Engineer' | 'Staff Engineer'

export type ForgeProfile = {
  name: string
  email: string
  targetRole: ForgeRole
  targetCompany: string
  level: string
  interviewDate: string
  weeklyHours: number
}

export type Scorecard = {
  id: string
  title: string
  overall: number
  coding: number
  systemDesign: number
  aiEngineering: number
  communication: number
  createdAt: string
  strengths: string[]
  gaps: string[]
  nextMissions: string[]
}

export type Mission = {
  id: string
  track: 'Diagnostic' | 'Coding' | 'System Design' | 'AI Engineering' | 'Mock Loop' | 'Guild'
  title: string
  duration: string
  difficulty: 'Foundation' | 'Interview' | 'Staff'
  story: string
  rubric: string[]
}

export type TestResult = {
  name: string
  status: 'passed' | 'failed'
  detail: string
}

export const defaultProfile: ForgeProfile = {
  name: 'Raju',
  email: 'raju@example.com',
  targetRole: 'AI Engineer',
  targetCompany: 'Big Tech',
  level: 'L5 / Senior',
  interviewDate: '2026-08-15',
  weeklyHours: 8,
}

export const forgeMissions: Mission[] = [
  {
    id: 'diagnostic-loop',
    track: 'Diagnostic',
    title: '35-Minute Baseline Loop',
    duration: '35m',
    difficulty: 'Interview',
    story: 'A recruiter drops you into a compressed loop to map your current signal across code, design, AI systems, and communication.',
    rubric: ['Problem decomposition', 'Architecture tradeoffs', 'AI production judgment', 'Clear explanation'],
  },
  {
    id: 'two-sum-pattern',
    track: 'Coding',
    title: 'Pattern Gauntlet: Two Sum Under Pressure',
    duration: '25m',
    difficulty: 'Foundation',
    story: 'Start simple, then prove you can explain constraints, complexity, edge cases, and production-quality implementation choices.',
    rubric: ['Correctness', 'Complexity', 'Edge cases', 'Communication'],
  },
  {
    id: 'notification-platform',
    track: 'System Design',
    title: 'Design a Notification Platform',
    duration: '45m',
    difficulty: 'Interview',
    story: 'A company needs reliable fanout across email, push, and in-app channels with retries, SLOs, and auditability.',
    rubric: ['Requirements', 'Data model', 'Queues', 'Reliability', 'Observability'],
  },
  {
    id: 'rag-reliability',
    track: 'AI Engineering',
    title: 'Repair a Hallucinating RAG Agent',
    duration: '40m',
    difficulty: 'Staff',
    story: 'A support agent cites stale policy and invents refund terms. You must debug retrieval, evals, prompts, and rollback gates.',
    rubric: ['Trace analysis', 'Retrieval quality', 'Eval design', 'Safety controls'],
  },
  {
    id: 'bar-raiser-panel',
    track: 'Mock Loop',
    title: 'Four-Agent Bar Raiser Panel',
    duration: '60m',
    difficulty: 'Interview',
    story: 'Coding, system design, AI engineering, and bar raiser agents debate your answers and produce a hiring-style scorecard.',
    rubric: ['Technical signal', 'Depth', 'Clarity', 'Ownership'],
  },
  {
    id: 'guild-rotation',
    track: 'Guild',
    title: 'Guild Rotation Room',
    duration: '75m',
    difficulty: 'Interview',
    story: 'A small group rotates interviewer, driver, observer, and bar raiser roles with shared scorecards and weekly missions.',
    rubric: ['Role discipline', 'Feedback quality', 'Consistency', 'Improvement'],
  },
]

export const pricingPlans = [
  {
    name: 'Solo Forge',
    price: '$29',
    description: 'For individual candidates preparing for AI engineering and backend loops.',
    features: ['Diagnostic loop', 'Coding arena', 'System design arena', 'AI engineering missions'],
  },
  {
    name: 'Guild',
    price: '$79',
    description: 'For small groups running structured prep rooms and shared scorecards.',
    features: ['Everything in Solo', 'Guild rooms', 'Role rotation', 'Weekly group challenges'],
  },
  {
    name: 'Cohort',
    price: 'Custom',
    description: 'For bootcamps, universities, and teams running AI engineering prep programs.',
    features: ['Admin console', 'Mission builder', 'Cohort analytics', 'Custom Synkora agents'],
  },
]

export const synkoraBridge = [
  { layer: 'Auth', endpoint: 'Synkora tenant auth / SSO', status: 'stubbed' },
  { layer: 'Agents', endpoint: 'Chat streaming + specialist interviewers', status: 'ready to wire' },
  { layer: 'Sandbox', endpoint: 'Code execution service + hidden tests', status: 'ready to wire' },
  { layer: 'Knowledge Base', endpoint: 'Curriculum RAG + company loop content', status: 'ready to wire' },
  { layer: 'War Room', endpoint: 'Multi-agent debate workflow', status: 'ready to wire' },
  { layer: 'Billing', endpoint: 'Plans, credits, subscriptions', status: 'ready to wire' },
]

export function scoreTextAnswer(answer: string, keywords: string[]) {
  const normalized = answer.toLowerCase()
  const hits = keywords.filter((keyword) => normalized.includes(keyword.toLowerCase()))
  return Math.min(100, 35 + hits.length * 10 + Math.min(25, Math.floor(answer.length / 80)))
}

export function evaluateDiagnostic(input: {
  coding: string
  design: string
  ai: string
  communication: string
}): Scorecard {
  const coding = scoreTextAnswer(input.coding, ['hash', 'map', 'complexity', 'edge', 'test'])
  const systemDesign = scoreTextAnswer(input.design, ['slo', 'queue', 'cache', 'database', 'retry', 'partition'])
  const aiEngineering = scoreTextAnswer(input.ai, ['eval', 'retrieval', 'trace', 'embedding', 'latency', 'guardrail'])
  const communication = scoreTextAnswer(input.communication, ['tradeoff', 'assumption', 'clarify', 'because', 'risk'])
  const overall = Math.round((coding + systemDesign + aiEngineering + communication) / 4)

  return {
    id: `score-${Date.now()}`,
    title: 'Diagnostic Loop Scorecard',
    overall,
    coding,
    systemDesign,
    aiEngineering,
    communication,
    createdAt: new Date().toISOString(),
    strengths: [
      coding >= 70 ? 'Structured problem-solving signal' : 'Willingness to reason through constraints',
      systemDesign >= 70 ? 'Good architecture tradeoff awareness' : 'Baseline design instincts are forming',
      aiEngineering >= 70 ? 'Production AI vocabulary and judgment' : 'Clear opportunity to build AI systems depth',
    ],
    gaps: [
      coding < 75 ? 'Tighten pattern recognition and complexity proof' : 'Practice faster implementation under time pressure',
      systemDesign < 75 ? 'Add reliability, data model, and SLO detail' : 'Push deeper on bottlenecks and cost controls',
      aiEngineering < 75 ? 'Practice RAG evals, traces, and rollback gates' : 'Calibrate answers with concrete incident examples',
    ],
    nextMissions: ['two-sum-pattern', 'notification-platform', 'rag-reliability'],
  }
}

export function evaluateCodingSubmission(code: string): { score: number; tests: TestResult[]; feedback: string[] } {
  const normalized = code.toLowerCase()
  const usesLookup = normalized.includes('map') || normalized.includes('{}') || normalized.includes('object')
  const returnsIndices = normalized.includes('return') && (normalized.includes('[') || normalized.includes('array'))
  const handlesTarget = normalized.includes('target')
  const avoidsNestedBruteForce = !normalized.includes('for (let j') && !normalized.includes('for(let j')
  const score = [usesLookup, returnsIndices, handlesTarget, avoidsNestedBruteForce].filter(Boolean).length * 25

  return {
    score,
    tests: [
      { name: '[2,7,11,15], target 9', status: usesLookup && returnsIndices ? 'passed' : 'failed', detail: 'Expected indices [0,1].' },
      { name: '[3,2,4], target 6', status: handlesTarget && returnsIndices ? 'passed' : 'failed', detail: 'Expected indices [1,2].' },
      { name: 'Complexity audit', status: avoidsNestedBruteForce ? 'passed' : 'failed', detail: 'Expected O(n) lookup-based approach.' },
    ],
    feedback: [
      usesLookup ? 'Good: lookup structure is present.' : 'Add a hash map from value to index.',
      returnsIndices ? 'Good: answer returns index-like output.' : 'Return the pair of indices, not values.',
      handlesTarget ? 'Good: target value is part of the logic.' : 'Make the target/complement relationship explicit.',
    ],
  }
}

export function evaluateChoices(selected: string[], expected: string[]) {
  const correct = selected.filter((item) => expected.includes(item)).length
  const wrong = selected.filter((item) => !expected.includes(item)).length
  return Math.max(0, Math.min(100, Math.round((correct / expected.length) * 100 - wrong * 12)))
}

export function panelFeedback(scorecard: Scorecard) {
  return [
    {
      agent: 'Ada',
      verdict: scorecard.coding >= 75 ? 'Coding signal is interview-ready for this level.' : 'Coding signal needs more fast pattern reps.',
    },
    {
      agent: 'Dijkstra',
      verdict: scorecard.systemDesign >= 75 ? 'Design answer shows scalable tradeoff awareness.' : 'Design answer needs clearer SLOs, queues, and failure handling.',
    },
    {
      agent: 'Rhea',
      verdict: scorecard.aiEngineering >= 75 ? 'AI engineering judgment is credible and production-oriented.' : 'AI track needs evals, traces, retrieval metrics, and safety gates.',
    },
    {
      agent: 'Mira',
      verdict: scorecard.communication >= 75 ? 'Communication has strong hiring-loop clarity.' : 'Narrate assumptions and tradeoffs more deliberately.',
    },
  ]
}
