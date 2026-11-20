import { HeadphonesIcon, BarChart3, Code2 } from 'lucide-react'

const features = [
  {
    Icon: HeadphonesIcon,
    title: 'Enterprise Support Hub',
    description: 'Handle customer queries 24/7 using your knowledge base, with HITL approval gates for escalations, full audit trail, and RBAC-controlled access.',
  },
  {
    Icon: Code2,
    title: 'Engineering Intelligence',
    description: 'Automated code review, CI/CD monitoring, and incident triage, integrated with GitHub, GitLab, Jira, and Slack via secured OAuth credentials.',
  },
  {
    Icon: BarChart3,
    title: 'Executive Analytics',
    description: 'Real-time dashboards, automated reporting, and data insights from your connected databases, with encrypted connections and row-level access control.',
  },
]

export default function AnimatedFeatures() {
  return (
    <section className="landing bg-paper px-6 py-20">
      <div className="mx-auto max-w-7xl">
        <div className="mb-16 text-center">
          <h2 className="mb-4 text-4xl font-medium tracking-[-0.05em] text-ink">
            Enterprise AI, deployed across your org
          </h2>
          <p className="text-xl leading-relaxed text-ink-soft">
            Real agents doing real work, with the audit trails, access controls, and integrations your enterprise requires
          </p>
        </div>

        <div className="grid gap-8 md:grid-cols-3">
          {features.map(({ Icon, title, description }) => (
            <div key={title} className="rounded-2xl border border-ink/10 bg-white p-8 shadow-soft">
              <div className="mb-6 flex h-14 w-14 items-center justify-center rounded-xl bg-sand-deep">
                <Icon className="h-6 w-6 text-ink" aria-hidden="true" />
              </div>
              <h3 className="mb-3 text-xl font-semibold tracking-[-0.03em] text-ink">{title}</h3>
              <p className="leading-relaxed text-ink-soft">{description}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
