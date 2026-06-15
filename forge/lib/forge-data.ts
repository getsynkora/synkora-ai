import type { LucideIcon } from 'lucide-react'
import {
  Binary,
  BrainCircuit,
  Code2,
  DatabaseZap,
  GitBranch,
  Network,
  PanelsTopLeft,
  Users,
} from 'lucide-react'

export type Track = {
  id: string
  label: string
  title: string
  mission: string
  signal: string
  score: number
  accent: string
  icon: LucideIcon
  checkpoints: string[]
}

export type PanelAgent = {
  name: string
  role: string
  focus: string
}

export const tracks: Track[] = [
  {
    id: 'coding',
    label: 'DSA',
    title: 'Algorithm Signal Review',
    mission: 'Solve a graph traversal problem, explain complexity, then refactor around a failing edge case.',
    signal: 'Problem decomposition',
    score: 82,
    accent: '#2A41E8',
    icon: Code2,
    checkpoints: ['Clarify input bounds', 'Pick the pattern', 'Prove complexity', 'Defend edge cases'],
  },
  {
    id: 'systems',
    label: 'Design',
    title: 'System Design Review',
    mission: 'Design a company-scale notification platform with fanout, retries, observability, and cost controls.',
    signal: 'Tradeoff judgment',
    score: 74,
    accent: '#0EA5E9',
    icon: Network,
    checkpoints: ['Define SLOs', 'Shape data model', 'Choose queues', 'Handle incidents'],
  },
  {
    id: 'ai',
    label: 'AI Eng',
    title: 'AI Reliability Review',
    mission: 'Repair a hallucinating support agent using retrieval evaluation, prompt boundaries, and trace analysis.',
    signal: 'Production AI judgment',
    score: 69,
    accent: '#14B8A6',
    icon: BrainCircuit,
    checkpoints: ['Inspect traces', 'Tune retrieval', 'Design eval set', 'Set rollback gates'],
  },
  {
    id: 'group',
    label: 'Guild',
    title: 'Collaborative Review Room',
    mission: 'Run a four-person preparation room with rotating interviewer, driver, observer, and bar raiser roles.',
    signal: 'Collaborative signal',
    score: 91,
    accent: '#F59E0B',
    icon: Users,
    checkpoints: ['Assign roles', 'Time the loop', 'Review scorecards', 'Plan next reps'],
  },
]

export const panelAgents: PanelAgent[] = [
  {
    name: 'Ada',
    role: 'Coding Interviewer',
    focus: 'Pattern recognition, complexity, and edge-case pressure.',
  },
  {
    name: 'Dijkstra',
    role: 'System Designer',
    focus: 'Architecture tradeoffs, scaling limits, and failure paths.',
  },
  {
    name: 'Rhea',
    role: 'AI Engineering Lead',
    focus: 'RAG, evals, agents, latency, safety, and observability.',
  },
  {
    name: 'Mira',
    role: 'Bar Raiser',
    focus: 'Communication, ownership stories, and hiring-loop signal.',
  },
]

export const missionMap = [
  {
    phase: '01',
    title: 'Diagnostic Review',
    detail: 'A 35-minute baseline across code, system design, AI engineering, and communication.',
    icon: PanelsTopLeft,
  },
  {
    phase: '02',
    title: 'Adaptive Plan',
    detail: 'A structured path that unlocks practice based on weaknesses, target role, and interview date.',
    icon: GitBranch,
  },
  {
    phase: '03',
    title: 'Practice Environment',
    detail: 'Timed coding, design, RAG, agent, and debugging rounds with replayable feedback.',
    icon: Binary,
  },
  {
    phase: '04',
    title: 'Readiness Signal',
    detail: 'A scorecard that tracks improvement, loop readiness, and group-prep contribution.',
    icon: DatabaseZap,
  },
]

export const buildPlan = [
  'Standalone Forge web product with its own brand, routing, and waitlist.',
  'Synkora API bridge for auth, tenant context, agents, chat streaming, and billing.',
  'Problem runner backed by Synkora sandbox execution and curated test cases.',
  'War-room interview panel using specialist Synkora agents and structured scoring.',
  'Knowledge-base curriculum for DSA patterns, system design, AI engineering, and company-style loops.',
  'Guild rooms for group practice, rotating roles, shared scorecards, and weekly missions.',
]
