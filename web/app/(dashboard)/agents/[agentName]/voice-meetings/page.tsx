'use client'

import { useParams } from 'next/navigation'
import { Mic } from 'lucide-react'
import AgentPageShell, { AgentPagePanel } from '@/components/agents/AgentPageShell'
import VoiceMeetingsSettings from '@/components/agents/VoiceMeetingsSettings'

export default function AgentVoiceMeetingsPage() {
  const params = useParams()
  const agentName = decodeURIComponent(params?.agentName as string || '')

  return (
    <AgentPageShell
      agentName={agentName}
      title="Voice & Meetings"
      description="Configure inbound phone calls, browser voice calls, and meeting bot behaviour."
      icon={Mic}
      badge="Voice Hub"
    >
      <AgentPagePanel>
        <div className="p-6 md:p-8">
          <VoiceMeetingsSettings agentSlug={agentName} />
        </div>
      </AgentPagePanel>
    </AgentPageShell>
  )
}
