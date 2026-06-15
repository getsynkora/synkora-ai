'use client'

import Link from 'next/link'
import {
  ArrowRight,
  Bell,
  BrainCircuit,
  CalendarDays,
  CheckCircle2,
  ChevronDown,
  Code2,
  Gauge,
  Layers3,
  Menu,
  MessageSquareText,
  Network,
  Play,
  Search,
  ShieldCheck,
  Sparkles,
  Users,
} from 'lucide-react'
import { missionMap, panelAgents, tracks } from '@/lib/forge-data'

const chartValues = [172, 212, 148, 226, 126, 82, 138, 182, 142, 152, 134, 92]

export default function ForgeExperience() {
  return (
    <main className="landing-page">
      <LandingNav />

      <section className="landing-hero">
        <div className="landing-copy">
          <div className="landing-eyebrow">
            <Sparkles size={16} />
            AI engineering interview operations
          </div>
          <h1>Prepare for the interview loop like an engineering system.</h1>
          <p>
            Synkora Forge is a separate AI Engineering interview and upskilling product built on Synkora. It calibrates coding, system design, production AI depth, communication, and group prep in one premium workspace.
          </p>
          <div className="landing-actions">
            <Link className="landing-primary" href="/workspace">
              Open dashboard
              <ArrowRight size={17} />
            </Link>
            <a className="landing-secondary" href="#tracks">Explore tracks</a>
          </div>
        </div>

        <HeroDashboardPreview />
      </section>

      <section className="landing-stat-strip">
        {[
          ['4', 'signal tracks'],
          ['12', 'readiness dimensions'],
          ['AI', 'panel evaluation'],
          ['Guild', 'group prep'],
        ].map(([value, label]) => (
          <div key={label}>
            <strong>{value}</strong>
            <span>{label}</span>
          </div>
        ))}
      </section>

      <section className="landing-section" id="tracks">
        <div className="landing-section-head">
          <span>Preparation Tracks</span>
          <h2>The system behind serious interview readiness.</h2>
          <p>Forge focuses on the real hiring signal: clarity, speed, architecture judgment, AI production instincts, and the ability to explain tradeoffs under pressure.</p>
        </div>
        <div className="landing-track-grid">
          {tracks.map((track) => (
            <article key={track.id}>
              <div style={{ color: track.accent }}><track.icon size={24} /></div>
              <span>{track.label}</span>
              <h3>{track.title}</h3>
              <p>{track.mission}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="landing-split" id="mission-map">
        <div className="landing-section-head align-left">
          <span>Adaptive Plan</span>
          <h2>Not a course. A calibrated path.</h2>
          <p>Forge changes the prep sequence based on target role, level, scorecard gaps, interview date, and peer review history.</p>
          <Link className="landing-secondary dark" href="/diagnostic">Run diagnostic</Link>
        </div>
        <div className="landing-map">
          {missionMap.map((item) => (
            <article key={item.phase}>
              <strong>{item.phase}</strong>
              <div>
                <h3>{item.title}</h3>
                <p>{item.detail}</p>
              </div>
            </article>
          ))}
        </div>
      </section>

      <section className="landing-section warm-panel">
        <div className="landing-section-head">
          <span>Evaluation Panel</span>
          <h2>Specialist agents, human-style rubrics.</h2>
        </div>
        <div className="landing-agent-grid">
          {panelAgents.map((agent) => (
            <article key={agent.name}>
              <div>{agent.name.slice(0, 1)}</div>
              <span>{agent.role}</span>
              <h3>{agent.name}</h3>
              <p>{agent.focus}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="landing-cta" id="alpha">
        <div>
          <span>Private Alpha</span>
          <h2>Build the cohort before scaling the curriculum.</h2>
          <p>Start with serious AI engineering candidates, tune the scoring model, and wire each surface into Synkora agents, sandbox, RAG, war room, and billing.</p>
        </div>
        <form>
          <input aria-label="Work email" placeholder="work@email.com" type="email" />
          <select aria-label="Target role" defaultValue="ai-engineer">
            <option value="ai-engineer">AI Engineer</option>
            <option value="backend">Backend Engineer</option>
            <option value="ml-platform">ML Platform Engineer</option>
            <option value="staff">Staff Engineer</option>
          </select>
          <button type="button">
            Join alpha
            <Play size={16} />
          </button>
        </form>
      </section>
    </main>
  )
}

function LandingNav() {
  return (
    <nav className="landing-nav" aria-label="Synkora Forge navigation">
      <Link className="landing-brand" href="/">
        <span>SF</span>
        <div>
          <strong>Synkora Forge</strong>
          <em>Interview operations</em>
        </div>
      </Link>
      <div className="landing-links">
        <a href="#tracks">Tracks</a>
        <a href="#mission-map">Plan</a>
        <a href="#alpha">Alpha</a>
      </div>
      <Link className="landing-nav-action" href="/workspace">Open app</Link>
    </nav>
  )
}

function HeroDashboardPreview() {
  return (
    <div className="hero-dashboard-card" aria-label="Synkora Forge dashboard preview">
      <aside className="preview-rail">
        <div className="preview-logo"><Sparkles size={24} /></div>
        {[Gauge, Code2, BrainCircuit, Users, ShieldCheck].map((Icon, index) => (
          <span className={index === 0 ? 'active' : ''} key={index}><Icon size={18} /></span>
        ))}
        <span className="bottom"><Menu size={18} /></span>
      </aside>
      <div className="preview-main">
        <header className="preview-top">
          <div className="preview-tabs">
            <span className="active">Dashboard</span>
            <span>Reports</span>
            <span>Guild</span>
          </div>
          <div className="preview-date">
            <Bell size={15} />
            Fri, 12 Jun
            <em>2</em>
          </div>
          <div className="preview-profile">
            <Search size={16} />
            <span>R</span>
          </div>
        </header>

        <div className="preview-title">
          <div>
            <span>Hayer AI Interview</span>
            <h2>Dashboard</h2>
          </div>
          <button type="button"><CalendarDays size={16} /> 12 Jun - 28 Jun <ChevronDown size={14} /></button>
        </div>

        <section className="preview-grid">
          <article className="preview-card readiness">
            <strong>82</strong>
            <h3>Readiness score</h3>
            <p>AI Engineer loop</p>
            <div className="mini-avatars"><span>A</span><span>D</span><span>M</span><em>480 minutes planned.</em></div>
          </article>
          <article className="preview-card reviews">
            <div><span>7</span>/<strong>16</strong></div>
            <h3>Reviews done</h3>
            <div className="review-mini"><b>3</b><b>4</b></div>
          </article>
          <article className="preview-card team">
            <h3>Team Collaboration</h3>
            {['Ada Chen', 'Dev Malik', 'Mina Rao'].map((name) => (
              <div key={name}><span>{name.slice(0, 1)}</span><p>{name}<em>Review partner</em></p></div>
            ))}
          </article>
          <article className="preview-card chart">
            <h3>Review activity</h3>
            <div className="preview-bars">
              {chartValues.map((value, index) => (
                <span key={`${value}-${index}`} className={index === 3 ? 'hot' : ''} style={{ height: `${Math.max(30, value * 0.72)}px` }} />
              ))}
            </div>
          </article>
          <article className="preview-premium">
            <div>
              <span>Forge Premium</span>
              <h3>Ready for panel depth?</h3>
            </div>
            <div className="preview-figure"><Layers3 size={46} /></div>
          </article>
        </section>
      </div>
    </div>
  )
}
