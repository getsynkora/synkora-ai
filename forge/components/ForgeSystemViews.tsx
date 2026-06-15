'use client'

import { useEffect, useMemo, useState } from 'react'
import Link from 'next/link'
import {
  ArrowRight,
  Bell,
  BookOpen,
  BrainCircuit,
  CalendarDays,
  ChevronDown,
  CheckCircle2,
  Circle,
  Clock3,
  Code2,
  Cpu,
  Gauge,
  Layers3,
  Lock,
  MoreHorizontal,
  Network,
  Play,
  Plus,
  Save,
  Search,
  ShieldCheck,
  Sparkles,
  Star,
  UserPlus,
  Users,
} from 'lucide-react'
import ForgeAppShell, { PageHeader, ScoreBars } from '@/components/ForgeAppShell'
import {
  defaultProfile,
  evaluateChoices,
  evaluateDiagnostic,
  forgeMissions,
  panelFeedback,
  pricingPlans,
  scoreTextAnswer,
  synkoraBridge,
  type ForgeProfile,
  type Scorecard,
} from '@/lib/forge-system'
import { getCodingProblemDetail } from '@/lib/coding-problems'
import { useForgeProfile, useForgeScorecards } from '@/lib/use-forge-state'

const forge75Problems = [
  ['Array / String', 'Merge Strings Alternately', 'Easy', 'LC75'],
  ['Array / String', 'Greatest Common Divisor of Strings', 'Easy', 'LC75'],
  ['Array / String', 'Kids With the Greatest Number of Candies', 'Easy', 'LC75'],
  ['Array / String', 'Can Place Flowers', 'Easy', 'LC75'],
  ['Array / String', 'Reverse Vowels of a String', 'Easy', 'LC75'],
  ['Array / String', 'Reverse Words in a String', 'Medium', 'LC75'],
  ['Array / String', 'Product of Array Except Self', 'Medium', 'LC75'],
  ['Array / String', 'Increasing Triplet Subsequence', 'Medium', 'LC75'],
  ['Array / String', 'String Compression', 'Medium', 'LC75'],
  ['Two Pointers', 'Move Zeroes', 'Easy', 'LC75'],
  ['Two Pointers', 'Is Subsequence', 'Easy', 'LC75'],
  ['Two Pointers', 'Container With Most Water', 'Medium', 'LC75'],
  ['Two Pointers', 'Max Number of K-Sum Pairs', 'Medium', 'LC75'],
  ['Sliding Window', 'Maximum Average Subarray I', 'Easy', 'LC75'],
  ['Sliding Window', 'Maximum Number of Vowels in a Substring', 'Medium', 'LC75'],
  ['Sliding Window', 'Max Consecutive Ones III', 'Medium', 'LC75'],
  ['Sliding Window', "Longest Subarray of 1's After Deleting One Element", 'Medium', 'LC75'],
  ['Prefix Sum', 'Find the Highest Altitude', 'Easy', 'LC75'],
  ['Prefix Sum', 'Find Pivot Index', 'Easy', 'LC75'],
  ['Hash Map / Set', 'Find the Difference of Two Arrays', 'Easy', 'LC75'],
  ['Hash Map / Set', 'Unique Number of Occurrences', 'Easy', 'LC75'],
  ['Hash Map / Set', 'Determine if Two Strings Are Close', 'Medium', 'LC75'],
  ['Hash Map / Set', 'Equal Row and Column Pairs', 'Medium', 'LC75'],
  ['Stack', 'Removing Stars From a String', 'Medium', 'LC75'],
  ['Stack', 'Asteroid Collision', 'Medium', 'LC75'],
  ['Stack', 'Decode String', 'Medium', 'LC75'],
  ['Queue', 'Number of Recent Calls', 'Easy', 'LC75'],
  ['Queue', 'Dota2 Senate', 'Medium', 'LC75'],
  ['Linked List', 'Delete the Middle Node of a Linked List', 'Medium', 'LC75'],
  ['Linked List', 'Odd Even Linked List', 'Medium', 'LC75'],
  ['Linked List', 'Reverse Linked List', 'Easy', 'LC75'],
  ['Linked List', 'Maximum Twin Sum of a Linked List', 'Medium', 'LC75'],
  ['Binary Tree DFS', 'Maximum Depth of Binary Tree', 'Easy', 'LC75'],
  ['Binary Tree DFS', 'Leaf-Similar Trees', 'Easy', 'LC75'],
  ['Binary Tree DFS', 'Count Good Nodes in Binary Tree', 'Medium', 'LC75'],
  ['Binary Tree DFS', 'Path Sum III', 'Medium', 'LC75'],
  ['Binary Tree DFS', 'Longest ZigZag Path in a Binary Tree', 'Medium', 'LC75'],
  ['Binary Tree DFS', 'Lowest Common Ancestor of a Binary Tree', 'Medium', 'LC75'],
  ['Binary Tree BFS', 'Binary Tree Right Side View', 'Medium', 'LC75'],
  ['Binary Tree BFS', 'Maximum Level Sum of a Binary Tree', 'Medium', 'LC75'],
  ['Binary Search Tree', 'Search in a Binary Search Tree', 'Easy', 'LC75'],
  ['Binary Search Tree', 'Delete Node in a BST', 'Medium', 'LC75'],
  ['Graph DFS', 'Keys and Rooms', 'Medium', 'LC75'],
  ['Graph DFS', 'Number of Provinces', 'Medium', 'LC75'],
  ['Graph DFS', 'Reorder Routes to Make All Paths Lead to the City Zero', 'Medium', 'LC75'],
  ['Graph DFS', 'Evaluate Division', 'Medium', 'LC75'],
  ['Graph BFS', 'Nearest Exit from Entrance in Maze', 'Medium', 'LC75'],
  ['Graph BFS', 'Rotting Oranges', 'Medium', 'LC75'],
  ['Heap / Priority Queue', 'Kth Largest Element in a Stream', 'Easy', 'LC75'],
  ['Heap / Priority Queue', 'Smallest Number in Infinite Set', 'Medium', 'LC75'],
  ['Heap / Priority Queue', 'Maximum Subsequence Score', 'Medium', 'LC75'],
  ['Heap / Priority Queue', 'Total Cost to Hire K Workers', 'Medium', 'LC75'],
  ['Binary Search', 'Guess Number Higher or Lower', 'Easy', 'LC75'],
  ['Binary Search', 'Successful Pairs of Spells and Potions', 'Medium', 'LC75'],
  ['Binary Search', 'Find Peak Element', 'Medium', 'LC75'],
  ['Binary Search', 'Koko Eating Bananas', 'Medium', 'LC75'],
  ['Backtracking', 'Letter Combinations of a Phone Number', 'Medium', 'LC75'],
  ['Backtracking', 'Combination Sum III', 'Medium', 'LC75'],
  ['Dynamic Programming', 'N-th Tribonacci Number', 'Easy', 'LC75'],
  ['Dynamic Programming', 'Min Cost Climbing Stairs', 'Easy', 'LC75'],
  ['Dynamic Programming', 'House Robber', 'Medium', 'LC75'],
  ['Dynamic Programming', 'Domino and Tromino Tiling', 'Medium', 'LC75'],
  ['Dynamic Programming', 'Unique Paths', 'Medium', 'LC75'],
  ['Dynamic Programming', 'Longest Common Subsequence', 'Medium', 'LC75'],
  ['Dynamic Programming', 'Best Time to Buy and Sell Stock with Transaction Fee', 'Medium', 'LC75'],
  ['Dynamic Programming', 'Edit Distance', 'Medium', 'LC75'],
  ['Bit Manipulation', 'Counting Bits', 'Easy', 'LC75'],
  ['Bit Manipulation', 'Single Number', 'Easy', 'LC75'],
  ['Bit Manipulation', 'Minimum Flips to Make a OR b Equal to c', 'Medium', 'LC75'],
  ['Trie', 'Implement Trie', 'Medium', 'LC75'],
  ['Trie', 'Search Suggestions System', 'Medium', 'LC75'],
  ['Intervals', 'Non-overlapping Intervals', 'Medium', 'LC75'],
  ['Intervals', 'Minimum Number of Arrows to Burst Balloons', 'Medium', 'LC75'],
  ['Monotonic Stack', 'Daily Temperatures', 'Medium', 'LC75'],
  ['Monotonic Stack', 'Online Stock Span', 'Medium', 'LC75'],
] as const

type CodingTrack = 'forge75' | 'top150' | 'blind'

type CodingRunResult = {
  status: 'idle' | 'running' | 'passed' | 'failed' | 'error'
  passed?: number
  total?: number
  tests?: {
    name: string
    status: 'passed' | 'failed' | 'error'
    input: unknown[]
    expected: unknown
    actual?: unknown
    error?: string
  }[]
  error?: string
}

const codingTrackCopy: Record<CodingTrack, {
  label: string
  title: string
  description: string
  badge: string
  extension: string
}> = {
  forge75: {
    label: 'Forge 75',
    title: 'Turn problem solving into a story-driven interview map.',
    description: 'A warm, structured course experience for FAANG-style coding patterns: solve, explain, review, repeat with peers, and graduate into Top Interview 150 coverage.',
    badge: 'Forge 75 / Coding System',
    extension: 'Top Interview track queued',
  },
  top150: {
    label: 'Top Interview 150',
    title: 'Build the larger interview library without losing the storyline.',
    description: 'Use the Forge 75 core as the first campaign, then expand into broader arrays, graphs, dynamic programming, intervals, and design-adjacent coding drills.',
    badge: 'Top Interview 150 / Expansion',
    extension: '150-question roadmap active',
  },
  blind: {
    label: 'Blind-style sprint',
    title: 'Run the classic high-pressure pattern sprint with review loops.',
    description: 'Compress the core list into timed missions, explain-before-code checkpoints, peer rotation, and bar-raiser feedback for every solved row.',
    badge: 'Blind-style / Sprint Mode',
    extension: 'Timed sprint active',
  },
}

const patternPlaybook: Record<string, string> = {
  'Array / String': 'State the invariant, transform in-place when possible, and defend edge cases around empty strings, duplicates, and overflow.',
  'Two Pointers': 'Name pointer movement rules before coding. The key signal is proving why one pointer can move without missing an answer.',
  'Sliding Window': 'Define the window contract first: what enters, what leaves, and when the answer is updated.',
  'Prefix Sum': 'Translate repeated range or running-total questions into a cumulative state you can query in constant time.',
  'Hash Map / Set': 'Explain the key design and collision of meanings. Good interviews care about what the map represents, not just that it exists.',
  Stack: 'Make the stack invariant explicit. Every push and pop should preserve a story about unresolved work.',
  Queue: 'Model time and order directly. Queue problems usually test whether old events expire or rotate correctly.',
  'Linked List': 'Use pointer diagrams and name each temporary pointer before mutation to avoid losing nodes.',
  'Binary Tree DFS': 'Choose preorder, inorder, postorder, or path-state recursion intentionally, then define the return value.',
  'Binary Tree BFS': 'Keep level boundaries clean. Interviewers watch for queue size snapshots and off-by-one level bugs.',
  'Binary Search Tree': 'Use ordering guarantees aggressively and call out how deletion or search changes tree shape.',
  'Graph DFS': 'Clarify visited-state ownership and whether the graph is directed, undirected, weighted, or implicit.',
  'Graph BFS': 'Use BFS when distance, spread, or nearest exit matters. Mark visited when enqueuing, not after popping.',
  'Heap / Priority Queue': 'Define the ranking key. Heap questions are usually about keeping only the best k candidates alive.',
  'Binary Search': 'Search the answer space, not only an array. State monotonicity and boundary decisions before code.',
  Backtracking: 'Define choice, constraint, goal, and undo. The clarity of the recursion tree matters more than speed at first.',
  'Dynamic Programming': 'Name the state, transition, base cases, and traversal order before optimizing memory.',
  'Bit Manipulation': 'Translate the bit operation into plain English and prove why each bit can be handled independently.',
  Trie: 'Use trie when prefix sharing is the product. Explain memory tradeoffs and terminal markers.',
  Intervals: 'Sort by the dimension that makes conflict visible, then explain merge or greedy decisions.',
  'Monotonic Stack': 'Keep the stack ordered by a useful property. Each element should enter and leave at most once.',
}

export function WorkspaceView() {
  const { profile } = useForgeProfile()
  const { scorecards } = useForgeScorecards()
  const latest = scorecards[0] ?? sampleScorecard
  const readiness = Math.round((latest.overall + latest.coding + latest.systemDesign + latest.aiEngineering) / 4)
  const chartValues = [178, 214, 132, 224, 126, 74, 121, 169, 132, 136, 128, 84]
  const candidates = [
    ['Ada Chen', 'AI Reliability', 'L5 Review', latest.aiEngineering],
    ['Dev Malik', 'System Design', 'L5 Loop', latest.systemDesign],
    ['Mina Rao', 'Coding Patterns', 'Senior Loop', latest.coding],
    ['Noah Kim', 'Panel Communication', 'Mock Loop', latest.communication],
  ]

  return (
    <ForgeAppShell>
      <section className="workspace-frame">
        <div className="dashboard-shell">
          <header className="dash-topbar">
            <div className="dash-tabs">
              <Link className="active" href="/workspace">Dashboard</Link>
              <Link href="/diagnostic">Reports</Link>
              <Link href="/guild">Guild</Link>
            </div>
            <div className="dash-date">
              <button type="button" aria-label="Notifications"><Bell size={17} /></button>
              <span>Fri, 12 Jun <em>2</em></span>
            </div>
            <div className="dash-profile">
              <button type="button" aria-label="Search"><Search size={18} /></button>
              <div className="profile-chip">
                <span>{profile.name.slice(0, 1)}</span>
                <div><strong>{profile.name}</strong><em>{profile.targetRole}</em></div>
                <ChevronDown size={16} />
              </div>
            </div>
          </header>

          <section className="dash-hero">
            <div>
              <span>Synkora Forge</span>
              <h1>AI Interview<br />Dashboard</h1>
            </div>
            <div className="dash-filters">
              <button type="button"><CalendarDays size={17} /> 12 Jun - 28 Jun <ChevronDown size={15} /></button>
              <button type="button"><Clock3 size={17} /> 24h <ChevronDown size={15} /></button>
            </div>
          </section>

          <section className="dash-grid">
            <article className="dash-card posted-card">
              <div className="card-menu"><MoreHorizontal size={18} /></div>
              <strong>{readiness}</strong>
              <h2>Readiness score</h2>
              <p>{profile.targetRole} for {profile.targetCompany}</p>
              <div className="avatar-stack">
                {['A', 'D', 'M', 'N'].map((item) => <span key={item}>{item}</span>)}
                <em>{profile.weeklyHours * 60} minutes planned this week.</em>
              </div>
            </article>

            <article className="dash-card interview-card">
              <div className="score-fraction"><span>{scorecards.length || 7}</span>/<strong>16</strong></div>
              <h2>Reviews done</h2>
              <div className="review-split">
                <div><strong>3</strong><span>Human mock</span></div>
                <div><strong>4</strong><span>AI panel review</span></div>
              </div>
            </article>

            <article className="dash-card team-card">
              <div className="team-title">
                <h2>Team Collaboration</h2>
                <button type="button"><UserPlus size={16} /> Add member</button>
              </div>
              {candidates.map(([name, role, loop, score]) => (
                <div className="team-row" key={String(name)}>
                  <span>{String(name).slice(0, 1)}</span>
                  <div><strong>{String(name)}</strong><em>{String(role)} · {String(loop)}</em></div>
                  <b>{Number(score)}</b>
                </div>
              ))}
            </article>

            <article className="dash-card chart-card">
              <div className="panel-title-row">
                <div>
                  <span className="card-kicker">Practice rhythm</span>
                  <h2>Review activity</h2>
                </div>
                <button type="button"><MoreHorizontal size={18} /></button>
              </div>
              <div className="bar-chart" aria-label="Review activity chart">
                {chartValues.map((value, index) => (
                  <span
                    key={`${value}-${index}`}
                    className={index === 3 ? 'hot' : ''}
                    style={{ height: `${Math.max(34, value)}px`, animationDelay: `${index * 0.05}s` }}
                  />
                ))}
              </div>
              <div className="chart-axis"><span>12 Jun</span><span>18 Jun</span><span>28 Jun</span></div>
            </article>

            <article className="premium-card">
              <div>
                <span>Forge Premium</span>
                <h2>Ready to go beyond static interview prep?</h2>
                <p>Unlock calibrated AI panels, guild rooms, and deeper production AI reviews.</p>
                <Link href="/plans">View plans</Link>
              </div>
              <div className="art-figure">
                <span className="helmet" />
                <span className="visor" />
                <span className="cube cube-a" />
                <span className="cube cube-b" />
                <span className="cube cube-c" />
              </div>
            </article>
          </section>
        </div>
      </section>
    </ForgeAppShell>
  )
}

export function OnboardingView() {
  const { profile, setProfile } = useForgeProfile()
  const [draft, setDraft] = useState<ForgeProfile>(profile)
  const [saved, setSaved] = useState(false)

  return (
    <ForgeAppShell>
      <PageHeader
        kicker="02 / Auth + Onboarding"
        title="Candidate setup"
        description="Mock auth and onboarding profile. This becomes real Synkora tenant auth, SSO, user profile, and subscription context later."
      />

      <section className="os-grid two">
        <form className="os-card form-card">
          <label>Name<input value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} /></label>
          <label>Email<input value={draft.email} onChange={(e) => setDraft({ ...draft, email: e.target.value })} /></label>
          <label>Target role
            <select value={draft.targetRole} onChange={(e) => setDraft({ ...draft, targetRole: e.target.value as ForgeProfile['targetRole'] })}>
              <option>AI Engineer</option>
              <option>Backend Engineer</option>
              <option>ML Platform Engineer</option>
              <option>Staff Engineer</option>
            </select>
          </label>
          <label>Target company<input value={draft.targetCompany} onChange={(e) => setDraft({ ...draft, targetCompany: e.target.value })} /></label>
          <label>Level<input value={draft.level} onChange={(e) => setDraft({ ...draft, level: e.target.value })} /></label>
          <label>Weekly hours<input type="number" value={draft.weeklyHours} onChange={(e) => setDraft({ ...draft, weeklyHours: Number(e.target.value) })} /></label>
          <button
            className="os-button"
            type="button"
            onClick={() => {
              setProfile(draft)
              setSaved(true)
            }}
          >
            <Save size={16} />
            Save profile
          </button>
          {saved ? <p className="success-note">Profile saved locally for this prototype.</p> : null}
        </form>

        <article className="os-card">
          <span className="card-kicker">Generated path</span>
          <h2>{draft.targetRole} campaign</h2>
          <p>Forge will generate missions based on target role, level, interview date, and available weekly hours.</p>
          <div className="timeline-list">
            {['Diagnostic loop', 'Coding pattern sprint', 'System design room', 'AI reliability lab', 'Mock loop panel'].map((item, index) => (
              <div key={item}><span>{index + 1}</span>{item}</div>
            ))}
          </div>
        </article>
      </section>
    </ForgeAppShell>
  )
}

export function DiagnosticView() {
  const { addScorecard } = useForgeScorecards()
  const [answers, setAnswers] = useState({
    coding: 'I would use a hash map to track complements, prove O(n), and test duplicate or negative values.',
    design: 'I would clarify SLOs, use queues for fanout, store notification state in a database, and add retries.',
    ai: 'I would inspect traces, measure retrieval quality, build eval sets, and add guardrails for risky answers.',
    communication: 'I clarify assumptions first, explain tradeoffs, call out risk, and state why I choose an approach.',
  })
  const [scorecard, setScorecard] = useState<Scorecard | null>(null)

  const submit = () => {
    const next = evaluateDiagnostic(answers)
    setScorecard(next)
    addScorecard(next)
  }

  return (
    <ForgeAppShell>
      <section className="warm-page-shell diagnostic-shell">
        <header className="warm-hero compact">
          <div>
            <span>Diagnostic Engine</span>
            <h1>Baseline readiness review</h1>
            <p>Answer four focused prompts. Forge calibrates coding, system design, AI engineering, and communication into one scorecard.</p>
          </div>
          <button className="warm-primary" type="button" onClick={submit}>
            <Play size={16} />
            Generate scorecard
          </button>
        </header>

        <section className="diagnostic-grid">
          <div className="diagnostic-prompts">
            {Object.entries(answers).map(([key, value], index) => (
              <label className="diagnostic-question" key={key}>
                <span>{String(index + 1).padStart(2, '0')}</span>
                <strong>{labelFor(key)}</strong>
                <textarea value={value} onChange={(e) => setAnswers({ ...answers, [key]: e.target.value })} />
              </label>
            ))}
          </div>

          <ScorecardPanel scorecard={scorecard ?? sampleScorecard} variant="warm" />
        </section>
      </section>
    </ForgeAppShell>
  )
}

export function CodingArenaView() {
  const initialSolvedCount = 19
  const [activeTrack, setActiveTrack] = useState<CodingTrack>('forge75')
  const [search, setSearch] = useState('')
  const [activeTopic, setActiveTopic] = useState('All')
  const [activeProblemIndex, setActiveProblemIndex] = useState(initialSolvedCount)
  const [completedProblems, setCompletedProblems] = useState<Set<number>>(
    () => new Set(Array.from({ length: initialSolvedCount }, (_, index) => index)),
  )
  const [reviewQueue, setReviewQueue] = useState<Set<number>>(
    () => new Set(Array.from({ length: 7 }, (_, index) => initialSolvedCount + index)),
  )
  const [sprintStarted, setSprintStarted] = useState(false)
  const [guildJoined, setGuildJoined] = useState(false)
  const [solutionDrafts, setSolutionDrafts] = useState<Record<string, string>>({})
  const [runResult, setRunResult] = useState<CodingRunResult>({ status: 'idle' })
  const completedCount = completedProblems.size
  const reviewCount = reviewQueue.size
  const progress = Math.round((completedCount / forge75Problems.length) * 100)
  const topicStats = useMemo(() => {
    const groups = new Map<string, typeof forge75Problems[number][]>()
    forge75Problems.forEach((problem) => {
      groups.set(problem[0], [...(groups.get(problem[0]) ?? []), problem])
    })

    return Array.from(groups.entries()).map(([topic, problems]) => ({
      topic,
      count: problems.length,
      solved: forge75Problems.filter((problem, index) => problem[0] === topic && completedProblems.has(index)).length,
    }))
  }, [completedProblems])
  const difficultyTotals = useMemo(() => ({
    easy: forge75Problems.filter((problem) => problem[2] === 'Easy').length,
    medium: forge75Problems.filter((problem) => problem[2] === 'Medium').length,
    hard: forge75Problems.filter((problem) => String(problem[2]) === 'Hard').length,
  }), [])
  const activeCopy = codingTrackCopy[activeTrack]
  const visibleProblems = useMemo(() => {
    const query = search.trim().toLowerCase()
    return forge75Problems
      .map((problem, index) => ({ problem, index }))
      .filter(({ problem }) => activeTopic === 'All' || problem[0] === activeTopic)
      .filter(({ problem }) => {
        if (!query) return true
        return problem.some((value) => value.toLowerCase().includes(query))
      })
  }, [activeTopic, search])
  const selectedProblem = forge75Problems[activeProblemIndex] ?? forge75Problems[0]
  const selectedDetail = useMemo(
    () => getCodingProblemDetail(selectedProblem, activeProblemIndex),
    [activeProblemIndex, selectedProblem],
  )
  const currentCode = solutionDrafts[selectedDetail.slug] ?? selectedDetail.starterCode
  const nextIncompleteIndex = forge75Problems.findIndex((_, index) => !completedProblems.has(index))
  const nextProblemIndex = nextIncompleteIndex >= 0 ? nextIncompleteIndex : 0
  const nextProblem = forge75Problems[nextProblemIndex]
  const selectedSolved = completedProblems.has(activeProblemIndex)
  const selectedInReview = reviewQueue.has(activeProblemIndex)

  useEffect(() => {
    setRunResult({ status: 'idle' })
  }, [selectedDetail.slug])

  const openProblem = (index: number) => {
    setActiveProblemIndex(index)
    setActiveTopic(forge75Problems[index][0])
  }

  const startNextSprint = () => {
    setSprintStarted(true)
    setSearch('')
    openProblem(nextProblemIndex)
  }

  const toggleSolved = () => {
    setCompletedProblems((current) => {
      const next = new Set(current)
      if (next.has(activeProblemIndex)) {
        next.delete(activeProblemIndex)
      } else {
        next.add(activeProblemIndex)
      }
      return next
    })
  }

  const toggleReview = () => {
    setReviewQueue((current) => {
      const next = new Set(current)
      if (next.has(activeProblemIndex)) {
        next.delete(activeProblemIndex)
      } else {
        next.add(activeProblemIndex)
      }
      return next
    })
  }

  const clearFilters = () => {
    setSearch('')
    setActiveTopic('All')
  }

  const updateCurrentCode = (code: string) => {
    setSolutionDrafts((current) => ({
      ...current,
      [selectedDetail.slug]: code,
    }))
  }

  const resetCurrentCode = () => {
    setSolutionDrafts((current) => ({
      ...current,
      [selectedDetail.slug]: selectedDetail.starterCode,
    }))
    setRunResult({ status: 'idle' })
  }

  const runSubmission = async () => {
    if (!selectedDetail.judgeReady) {
      setRunResult({
        status: 'error',
        error: 'The problem is loaded, but the executable Python judge for this row is not configured yet.',
      })
      return
    }

    setRunResult({ status: 'running' })

    try {
      const response = await fetch('/api/coding/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          slug: selectedDetail.slug,
          code: currentCode,
        }),
      })
      const result = await response.json() as CodingRunResult
      setRunResult(result)

      if (result.status === 'passed') {
        setCompletedProblems((current) => new Set(current).add(activeProblemIndex))
        setReviewQueue((current) => {
          const next = new Set(current)
          next.delete(activeProblemIndex)
          return next
        })
      }
    } catch (error) {
      setRunResult({
        status: 'error',
        error: error instanceof Error ? error.message : 'Unable to run Python submission.',
      })
    }
  }

  return (
    <ForgeAppShell>
      <section className="warm-page-shell coding-study-shell">
        <header className="coding-course-hero">
          <div className="course-hero-copy">
            <span><BookOpen size={15} /> {activeCopy.badge}</span>
            <h1>{activeCopy.title}</h1>
            <p>{activeCopy.description}</p>
            <div className="course-track-tabs" aria-label="Coding study tracks">
              <button className={activeTrack === 'forge75' ? 'active' : ''} type="button" onClick={() => setActiveTrack('forge75')}>
                <Star size={15} />Forge 75
              </button>
              <button className={activeTrack === 'top150' ? 'active' : ''} type="button" onClick={() => setActiveTrack('top150')}>
                <Lock size={15} />Top Interview 150
              </button>
              <button className={activeTrack === 'blind' ? 'active' : ''} type="button" onClick={() => setActiveTrack('blind')}>
                <ShieldCheck size={15} />Blind-style sprint
              </button>
            </div>
          </div>

          <aside className="course-progress-card" aria-label="Forge 75 progress">
            <div className="progress-ring" style={{ background: `conic-gradient(var(--forge-orange) ${progress}%, #ECE6DF ${progress}% 100%)` }}>
              <em>{progress}%</em>
            </div>
            <span>Course progress</span>
            <strong>{completedCount}/{forge75Problems.length} solved</strong>
            <p>{reviewCount} in review queue. Next chapter starts with {nextProblem[0]}.</p>
            <button type="button" onClick={startNextSprint}><Play size={16} />{sprintStarted ? 'Sprint active' : 'Start next sprint'}</button>
          </aside>
        </header>

        <section className="coding-study-grid">
          <aside className="study-sidebar">
            <label className="study-search">
              <Search size={16} />
              <input
                placeholder="Search patterns"
                aria-label="Search coding patterns"
                value={search}
                onChange={(event) => setSearch(event.target.value)}
              />
            </label>
            <div className="study-sidebar-head">
              <span>Pattern map</span>
              <strong>{visibleProblems.length} visible</strong>
            </div>
            <div className="study-topic-list">
              <button className={activeTopic === 'All' ? 'active' : ''} type="button" onClick={() => setActiveTopic('All')}>
                <span>00</span>
                <strong>All patterns</strong>
                <em>{forge75Problems.length} qs</em>
              </button>
              {topicStats.map((item, index) => (
                <button className={activeTopic === item.topic ? 'active' : ''} key={item.topic} type="button" onClick={() => setActiveTopic(item.topic)}>
                  <span>{String(index + 1).padStart(2, '0')}</span>
                  <strong>{item.topic}</strong>
                  <em>{item.solved}/{item.count}</em>
                </button>
              ))}
            </div>
          </aside>

          <main className="study-main">
            <section className="coding-stat-grid" aria-label="Coding progress stats">
              <article>
                <Code2 size={18} />
                <span>Total set</span>
                <strong>{forge75Problems.length}</strong>
                <p>Forge 75 aligned questions</p>
              </article>
              <article>
                <CheckCircle2 size={18} />
                <span>Solved</span>
                <strong>{completedCount}</strong>
                <p>Ready for review replay</p>
              </article>
              <article>
                <Layers3 size={18} />
                <span>Patterns</span>
                <strong>{topicStats.length}</strong>
                <p>From arrays to monotonic stack</p>
              </article>
              <article>
                <Lock size={18} />
                <span>Extension</span>
                <strong>150</strong>
                <p>{activeCopy.extension}</p>
              </article>
            </section>

            <article className="coding-story-card">
              <div>
                <span>{sprintStarted ? 'Sprint running' : 'Selected mission'}</span>
                <h2>{selectedProblem[0]} mission</h2>
                <p>
                  Your next sprint is not just solving {selectedProblem[1]}. Forge asks for the pattern,
                  brute-force contrast, complexity proof, and a narrated dry run for peer review.
                </p>
              </div>
              <div className="story-orbit" aria-hidden="true">
                <span className="orbit-core"><Code2 size={24} /></span>
                <span className="orbit-node node-one">O(n)</span>
                <span className="orbit-node node-two">trace</span>
                <span className="orbit-node node-three">proof</span>
              </div>
            </article>

            <section className="coding-lab-card">
              <header className="coding-lab-head">
                <div>
                  <span>Loaded problem</span>
                  <h2>{selectedDetail.title}</h2>
                  <p>{selectedDetail.topic} · {selectedDetail.difficulty} · {selectedDetail.source}</p>
                </div>
                <span className={selectedDetail.judgeReady ? 'judge-live' : 'judge-draft'}>
                  {selectedDetail.judgeReady ? 'Python judge live' : 'Prompt loaded'}
                </span>
              </header>

              <div className="problem-brief-grid">
                <article>
                  <span>Prompt</span>
                  <p>{selectedDetail.statement}</p>
                </article>
                <article>
                  <span>Signature</span>
                  <code>{selectedDetail.signature}</code>
                </article>
              </div>

              <div className="example-grid">
                {selectedDetail.examples.map((example, index) => (
                  <div key={`${selectedDetail.slug}-example-${index}`}>
                    <span>Example {index + 1}</span>
                    <code>Input: {example.input}</code>
                    <code>Output: {example.output}</code>
                    {example.note ? <p>{example.note}</p> : null}
                  </div>
                ))}
              </div>

              <div className="constraint-row">
                {selectedDetail.constraints.map((constraint) => <span key={constraint}>{constraint}</span>)}
              </div>

              <div className="python-workbench">
                <div className="editor-panel">
                  <div className="editor-toolbar">
                    <span>Python submission</span>
                    <button type="button" onClick={resetCurrentCode}>Reset starter</button>
                  </div>
                  <textarea
                    className="python-editor"
                    value={currentCode}
                    onChange={(event) => updateCurrentCode(event.target.value)}
                    spellCheck={false}
                  />
                  <div className="run-actions">
                    <button type="button" onClick={runSubmission} disabled={runResult.status === 'running'}>
                      <Play size={16} />
                      {runResult.status === 'running' ? 'Running Python' : 'Run submission'}
                    </button>
                    <span>{selectedDetail.tests.length} local tests</span>
                  </div>
                </div>

                <aside className={`result-panel ${runResult.status}`}>
                  <span>Judge result</span>
                  {runResult.status === 'idle' ? (
                    <p>Run your Python solution to see per-test feedback here.</p>
                  ) : null}
                  {runResult.status === 'running' ? (
                    <p>Executing with a 3 second timeout.</p>
                  ) : null}
                  {runResult.status === 'error' ? (
                    <p>{runResult.error}</p>
                  ) : null}
                  {runResult.status === 'passed' || runResult.status === 'failed' ? (
                    <>
                      <strong>{runResult.passed}/{runResult.total} tests passed</strong>
                      <div className="judge-tests">
                        {runResult.tests?.map((test) => (
                          <div className={test.status} key={test.name}>
                            <b>{test.name}</b>
                            <code>Input: {formatJudgeValue(test.input)}</code>
                            <code>Expected: {formatJudgeValue(test.expected)}</code>
                            {'actual' in test ? <code>Actual: {formatJudgeValue(test.actual)}</code> : null}
                            {test.error ? <pre>{test.error}</pre> : null}
                          </div>
                        ))}
                      </div>
                    </>
                  ) : null}
                  <div className="hint-list">
                    {selectedDetail.hints.map((hint) => <em key={hint}>{hint}</em>)}
                  </div>
                </aside>
              </div>
            </section>

            <section className="problem-board">
              <header className="problem-board-head">
                <div>
                  <span>Question bank</span>
                  <h2>75 core interview questions</h2>
                </div>
                <div className="difficulty-summary">
                  <span className="easy">{difficultyTotals.easy} Easy</span>
                  <span className="medium">{difficultyTotals.medium} Medium</span>
                  <span className="hard">{difficultyTotals.hard} Hard</span>
                </div>
              </header>

              <div className="problem-list" role="list" aria-label="Forge 75 problem list">
                {visibleProblems.map(({ problem: [topic, title, difficulty, source], index }) => {
                  const solved = completedProblems.has(index)
                  const reviewing = reviewQueue.has(index)
                  return (
                    <article
                      className={`problem-row ${solved ? 'solved' : reviewing ? 'reviewing' : ''} ${activeProblemIndex === index ? 'selected' : ''}`}
                      key={title}
                      role="listitem"
                      tabIndex={0}
                      onClick={() => openProblem(index)}
                      onKeyDown={(event) => {
                        if (event.key === 'Enter' || event.key === ' ') {
                          event.preventDefault()
                          openProblem(index)
                        }
                      }}
                    >
                      <div className="problem-status">
                        {solved ? <CheckCircle2 size={18} /> : <Circle size={18} />}
                      </div>
                      <div className="problem-index">{String(index + 1).padStart(2, '0')}</div>
                      <div className="problem-title">
                        <strong>{title}</strong>
                        <span>{topic}</span>
                      </div>
                      <span className={`difficulty-pill ${difficulty.toLowerCase()}`}>{difficulty}</span>
                      <span className="source-pill">{source}</span>
                      <button
                        type="button"
                        aria-label={`Open ${title}`}
                        onClick={(event) => {
                          event.stopPropagation()
                          openProblem(index)
                        }}
                      >
                        <ArrowRight size={16} />
                      </button>
                    </article>
                  )
                })}
                {visibleProblems.length === 0 ? (
                  <div className="problem-empty">
                    <strong>No questions found</strong>
                    <span>Clear the filter or search a different pattern.</span>
                    <button type="button" onClick={clearFilters}>Reset filters</button>
                  </div>
                ) : null}
              </div>
            </section>
          </main>

          <aside className="study-right-rail">
            <article className="next-sprint-card">
              <span>Problem detail</span>
              <h2>{selectedDetail.title}</h2>
              <p>{selectedDetail.topic} · {selectedDetail.difficulty} · #{String(activeProblemIndex + 1).padStart(2, '0')} from {selectedDetail.source}.</p>
              <div className="detail-status-row">
                <span className={selectedSolved ? 'done' : ''}>{selectedSolved ? 'Solved' : 'Unsolved'}</span>
                <span className={selectedInReview ? 'review' : ''}>{selectedInReview ? 'In review' : 'Not reviewed'}</span>
                <span className={selectedDetail.judgeReady ? 'review' : ''}>{selectedDetail.judgeReady ? 'Judge ready' : 'Judge pending'}</span>
              </div>
              <p>{patternPlaybook[selectedDetail.topic] ?? 'Explain the invariant, complexity, edge cases, and failure cases before writing code.'}</p>
              <div className="sprint-steps">
                {['Pattern recall', 'Code pass', 'Dry run', 'Peer review'].map((step, index) => (
                  <div key={step}><strong>{String(index + 1).padStart(2, '0')}</strong><span>{step}</span></div>
                ))}
              </div>
              <div className="detail-actions">
                <button type="button" onClick={toggleSolved}>{selectedSolved ? 'Mark unsolved' : 'Mark solved'}</button>
                <button type="button" onClick={toggleReview}>{selectedInReview ? 'Remove review' : 'Send to review'}</button>
              </div>
            </article>

            <article className="peer-room-card">
              <span>Group prep</span>
              <h2>Saturday Coding Guild</h2>
              <p>Four candidates rotate driver, reviewer, interviewer, and bar-raiser roles.</p>
              <div className="peer-stack">
                {['A', 'R', 'M', 'D'].map((item) => <b key={item}>{item}</b>)}
                <em>4 seats</em>
              </div>
              <button type="button" onClick={() => setGuildJoined((current) => !current)}>
                {guildJoined ? 'Seat reserved' : 'Join guild room'}
              </button>
            </article>

            <article className="coding-note-card">
              <span>{activeTopic === 'All' ? 'Review rule' : activeTopic}</span>
              <p>{activeTopic === 'All' ? 'A solved row is only complete when the candidate can explain the invariant, complexity, and failure cases without reading code.' : patternPlaybook[activeTopic]}</p>
              <button type="button" onClick={clearFilters}>Show full list</button>
            </article>
          </aside>
        </section>
      </section>
    </ForgeAppShell>
  )
}

export function SystemDesignView() {
  const [answer, setAnswer] = useState('I would define SLOs, separate API from workers, publish events to queues, store notification state in a database, add retry policies, idempotency keys, cache templates, and observability dashboards.')
  const score = scoreTextAnswer(answer, ['slo', 'queue', 'database', 'retry', 'idempotency', 'cache', 'observability', 'worker'])

  return (
    <ForgeAppShell>
      <PageHeader
        kicker="05 / System Design Arena"
        title="Notification platform design review"
        description="A design canvas with requirements, architecture notes, interviewer interruptions, and rubric scoring."
      />
      <section className="os-grid two">
        <article className="os-card form-card">
          <label>Architecture answer<textarea value={answer} onChange={(e) => setAnswer(e.target.value)} /></label>
          <ScoreBars scores={[{ label: 'Design depth', value: score }, { label: 'Reliability', value: Math.min(100, score + 4) }, { label: 'Tradeoffs', value: Math.max(0, score - 8) }]} />
        </article>
        <article className="os-card interrupt-card">
          <span className="card-kicker">Interviewer interruptions</span>
          {['What happens when push provider latency spikes?', 'How do you prevent duplicate notifications?', 'Where do you draw the SLO boundary?', 'How do you debug a bad fanout incident?'].map((item) => (
            <div key={item}><Clock3 size={16} />{item}</div>
          ))}
        </article>
      </section>
    </ForgeAppShell>
  )
}

export function AIEngineeringView() {
  const expected = ['trace', 'eval', 'retrieval', 'rollback']
  const [selected, setSelected] = useState<string[]>(['trace', 'eval'])
  const score = evaluateChoices(selected, expected)

  const toggle = (item: string) => {
    setSelected((current) => current.includes(item) ? current.filter((x) => x !== item) : [...current, item])
  }

  return (
    <ForgeAppShell>
      <PageHeader
        kicker="06 / AI Engineering Arena"
        title="RAG reliability review"
        description="A production AI mission for traces, retrieval quality, evals, guardrails, latency, and rollback gates."
      />
      <section className="os-grid two">
        <article className="os-card">
          <span className="card-kicker">Incident</span>
          <h2>Support agent hallucinated refund policy</h2>
          <p>The agent cited stale policy and invented a refund exception. Pick the actions you would take before shipping a fix.</p>
          <div className="choice-grid">
            {[
              ['trace', 'Inspect Langfuse-style traces and retrieved chunks'],
              ['temperature', 'Only lower temperature and retry'],
              ['eval', 'Build a regression eval set for refund scenarios'],
              ['retrieval', 'Measure retrieval recall and chunk freshness'],
              ['rewrite', 'Rewrite the entire app immediately'],
              ['rollback', 'Add rollout and rollback gates'],
            ].map(([id, label]) => (
              <button key={id} type="button" className={selected.includes(id) ? 'selected' : ''} onClick={() => toggle(id)}>
                {selected.includes(id) ? <CheckCircle2 size={17} /> : <Circle size={17} />}
                {label}
              </button>
            ))}
          </div>
        </article>
        <article className="os-card">
          <span className="card-kicker">AI engineering score</span>
          <div className="big-score">{score}</div>
          <p>{score >= 75 ? 'Strong production AI instincts.' : 'Keep practicing evals, retrieval diagnosis, and release safety.'}</p>
          <div className="rubric-row">
            <span>Traces</span>
            <span>Evals</span>
            <span>Retrieval</span>
            <span>Rollback</span>
          </div>
        </article>
      </section>
    </ForgeAppShell>
  )
}

export function MockLoopView() {
  const { scorecards } = useForgeScorecards()
  const scorecard = scorecards[0] ?? sampleScorecard
  const feedback = panelFeedback(scorecard)

  return (
    <ForgeAppShell>
      <PageHeader
        kicker="07 / War Room Mock Loop"
        title="Four-agent calibrated panel"
        description="A Synkora war-room style mock loop: coding interviewer, system designer, AI lead, and bar raiser produce a shared scorecard."
      />
      <section className="os-grid two">
        {feedback.map((item) => (
          <article className="os-card panel-agent" key={item.agent}>
            <div className="agent-mark">{item.agent.slice(0, 1)}</div>
            <span>{item.agent}</span>
            <p>{item.verdict}</p>
          </article>
        ))}
      </section>
    </ForgeAppShell>
  )
}

export function GuildView() {
  const members = [
    ['Aisha', 'Interviewer', '+18'],
    ['Raju', 'Driver', '+14'],
    ['Mina', 'Observer', '+11'],
    ['Dev', 'Bar Raiser', '+9'],
  ]

  return (
    <ForgeAppShell>
      <section className="warm-page-shell guild-shell">
        <header className="warm-hero">
          <div>
            <span>Guild Prep</span>
            <h1>Group review room</h1>
            <p>Cohorts rotate roles, run timed AI systems reviews, share scorecards, and improve together with structured peer signal.</p>
          </div>
          <button className="warm-primary" type="button"><Plus size={16} />Create room</button>
        </header>

        <section className="guild-grid">
          <article className="guild-main-card">
            <div className="panel-title-row">
              <div>
                <span className="card-kicker">Next room</span>
                <h2>Saturday AI Systems Review</h2>
              </div>
              <span className="guild-time">75 min</span>
            </div>
            <p>RAG incident review with rotating interviewer, driver, observer, and bar raiser roles.</p>
            <div className="guild-roles">
              {['Interviewer', 'Driver', 'Observer', 'Bar Raiser'].map((role) => <span key={role}><Users size={15} />{role}</span>)}
            </div>
            <div className="guild-timeline">
              {['Warmup', 'Live review', 'Panel feedback', 'Next reps'].map((item, index) => (
                <div key={item}><strong>{String(index + 1).padStart(2, '0')}</strong><span>{item}</span></div>
              ))}
            </div>
          </article>

          <article className="guild-members-card">
            <div className="panel-title-row">
              <h2>Team Collaboration</h2>
              <button type="button">Add member</button>
            </div>
            {members.map(([name, role, delta]) => (
              <div className="guild-member" key={name}>
                <span>{name.slice(0, 1)}</span>
                <div><strong>{name}</strong><em>{role}</em></div>
                <b>{delta}</b>
              </div>
            ))}
          </article>

          <article className="guild-premium-card">
            <span>Guild Premium</span>
            <h2>Run a calibrated cohort, not a chat group.</h2>
            <p>Unlock shared rubrics, weekly challenges, and AI panel summaries for every room.</p>
            <Link href="/plans">View plans</Link>
          </article>
        </section>
      </section>
    </ForgeAppShell>
  )
}

export function PlansView() {
  return (
    <ForgeAppShell>
      <PageHeader
        kicker="09 / Payments + Plans"
        title="Monetization model"
        description="Plan packaging for individual candidates, group guilds, and cohort operators. This will wire into Synkora billing."
      />
      <section className="os-grid three">
        {pricingPlans.map((plan) => (
          <article className="os-card plan-card" key={plan.name}>
            <span className="card-kicker">{plan.name}</span>
            <h2>{plan.price}</h2>
            <p>{plan.description}</p>
            <ul>{plan.features.map((feature) => <li key={feature}>{feature}</li>)}</ul>
            <button className="os-button">Select plan</button>
          </article>
        ))}
      </section>
    </ForgeAppShell>
  )
}

export function AdminView() {
  return (
    <ForgeAppShell>
      <PageHeader
        kicker="10 / Admin + Content Ops"
        title="Operations console"
        description="Admin tools for curriculum, rubrics, question banks, cohorts, Synkora bridge wiring, and scoring calibration."
      />
      <section className="os-grid two">
        <article className="os-card">
          <span className="card-kicker">Mission builder</span>
          <div className="admin-list">
            {forgeMissions.map((mission) => (
              <div key={mission.id}>
                <strong>{mission.title}</strong>
                <span>{mission.track} · {mission.difficulty} · {mission.duration}</span>
              </div>
            ))}
          </div>
        </article>
        <article className="os-card">
          <span className="card-kicker">Synkora bridge</span>
          <div className="admin-list">
            {synkoraBridge.map((item) => (
              <div key={item.layer}>
                <strong>{item.layer}</strong>
                <span>{item.endpoint} · {item.status}</span>
              </div>
            ))}
          </div>
        </article>
      </section>
    </ForgeAppShell>
  )
}

function ScorecardPanel({ scorecard, variant }: { scorecard: Scorecard; variant?: 'warm' }) {
  return (
    <article className={variant === 'warm' ? 'warm-scorecard' : 'os-card'}>
      <span className="card-kicker">Scorecard</span>
      <h2>{scorecard.title}</h2>
      <div className="big-score">{scorecard.overall}</div>
      <ScoreBars
        scores={[
          { label: 'Coding', value: scorecard.coding },
          { label: 'System Design', value: scorecard.systemDesign },
          { label: 'AI Engineering', value: scorecard.aiEngineering },
          { label: 'Communication', value: scorecard.communication },
        ]}
      />
      <div className="insight-grid">
        <div><strong>Strengths</strong>{scorecard.strengths.map((item) => <p key={item}>{item}</p>)}</div>
        <div><strong>Gaps</strong>{scorecard.gaps.map((item) => <p key={item}>{item}</p>)}</div>
      </div>
    </article>
  )
}

function labelFor(key: string) {
  const labels: Record<string, string> = {
    coding: 'Coding answer',
    design: 'System design answer',
    ai: 'AI engineering answer',
    communication: 'Communication style',
  }
  return labels[key] ?? key
}

function formatJudgeValue(value: unknown) {
  if (typeof value === 'string') return value

  try {
    return JSON.stringify(value)
  } catch {
    return String(value)
  }
}

const sampleScorecard: Scorecard = evaluateDiagnostic({
  coding: defaultProfile.targetRole + ' hash map complexity edge tests',
  design: 'slo queue database retry cache observability worker partition',
  ai: 'trace eval retrieval embedding latency guardrail rollback',
  communication: 'clarify assumptions because tradeoff risk',
})
