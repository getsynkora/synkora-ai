import type { ReactNode } from 'react'
import Link from 'next/link'

import type { DocNavSection } from '@/lib/content'

export default function DocsSidebar({
  sections,
  currentHref,
}: {
  sections: DocNavSection[]
  currentHref: string
}) {
  return (
    <aside className="docs-sidebar rounded-[2rem] border border-black/10 bg-white/70 p-5 shadow-[0_24px_60px_rgba(0,0,0,0.05)] backdrop-blur">
      <div className="mb-4 border-b border-black/10 pb-4">
        <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-[#7a736a]">
          Documentation
        </p>
        <h2 className="mt-2 text-lg font-semibold tracking-[-0.03em] text-[#171717]">
          Synkora Docs
        </h2>
      </div>

      <nav className="space-y-5">
        {sections.map((section) => (
          <div key={section.label}>
            <p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.2em] text-[#7a736a]">
              {section.label}
            </p>

            <div className="space-y-1">
              {section.items.map((item) => (
                <SidebarLink key={item.href} href={item.href} currentHref={currentHref}>
                  {item.title}
                </SidebarLink>
              ))}
            </div>

            {section.groups.length > 0 && (
              <div className="mt-3 space-y-3">
                {section.groups.map((group) => (
                  <div key={`${section.label}-${group.label}`}>
                    <p className="mb-1 text-xs font-medium text-[#5f5850]">{group.label}</p>
                    <div className="space-y-1">
                      {group.items.map((item) => (
                        <SidebarLink key={item.href} href={item.href} currentHref={currentHref}>
                          {item.title}
                        </SidebarLink>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
      </nav>
    </aside>
  )
}

function SidebarLink({
  href,
  currentHref,
  children,
}: {
  href: string
  currentHref: string
  children: ReactNode
}) {
  const active = href === currentHref

  return (
    <Link
      href={href}
      className={`block rounded-xl px-3 py-2 text-sm transition-colors ${
        active
          ? 'bg-[#e7f6ef] font-medium text-[#174c39]'
          : 'text-[#4f4942] hover:bg-black/[0.04] hover:text-[#171717]'
      }`}
    >
      {children}
    </Link>
  )
}
