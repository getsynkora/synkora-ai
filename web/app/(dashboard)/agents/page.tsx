'use client'

import { useState, useEffect, useRef, useCallback, type CSSProperties, type MouseEvent as ReactMouseEvent } from 'react'
import { createPortal } from 'react-dom'
import { useRouter } from 'next/navigation'
import toast from 'react-hot-toast'
import {
  Plus, Trash2, Bot, Users, MoreVertical,
  Settings, Copy, Globe, Lock, Activity, Search, Sparkles, ChevronDown
} from 'lucide-react'
import { apiClient } from '@/lib/api/client'

interface SubAgent {
  id: string
  sub_agent_id: string
  sub_agent_name: string
  sub_agent_type: string
  execution_order: number
  is_active: boolean
}

interface Agent {
  id: string
  agent_name: string
  slug: string
  public_slug?: string
  agent_type: string
  description: string | null
  avatar: string | null
  status: string
  workflow_type: string | null
  execution_count: number
  success_rate: number
  created_at: string
  sub_agents_count: number
  sub_agents: SubAgent[]
  is_public: boolean
  category: string | null
  tags: string[]
  is_sub_agent: boolean
}

// Ink-style SVG illustrations — warm parchment palette, no avatars needed
const INK = '#1c1816'
const BG = '#f3ecdf'
const WASH = '#e5dac9'

function AgentIllustration({ name }: { name: string }) {
  let h = 0
  for (let i = 0; i < name.length; i++) h = name.charCodeAt(i) + ((h << 5) - h)
  const idx = Math.abs(h) % 8

  const shared = 'absolute inset-0 h-full w-full'

  if (idx === 0) return (
    // Mesh — node graph, orchestration
    <svg viewBox="0 0 400 280" fill="none" xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="xMidYMid slice" className={shared} aria-hidden>
      <rect width="400" height="280" fill={BG}/>
      <ellipse cx="200" cy="145" rx="140" ry="95" fill={WASH} opacity="0.55"/>
      <circle cx="200" cy="140" r="13" fill={INK}/>
      <circle cx="200" cy="140" r="22" fill="none" stroke={INK} strokeWidth="1" opacity="0.28"/>
      <circle cx="200" cy="140" r="40" fill="none" stroke={INK} strokeWidth="0.5" opacity="0.16"/>
      {([
        [112,88,8,0.85],[292,83,7,0.8],[90,185,6,0.7],
        [314,172,9,0.9],[200,52,7,0.75],[152,222,5,0.65],[258,218,6,0.7],
      ] as [number,number,number,number][]).map(([cx,cy,r,op],i) => (
        <circle key={i} cx={cx} cy={cy} r={r} fill={INK} opacity={op}/>
      ))}
      {([
        [112,88,1.5,0.45],[292,83,1.5,0.45],[90,185,1.2,0.35],
        [314,172,2,0.5],[200,52,1.5,0.45],[152,222,1,0.35],[258,218,1.5,0.45],
      ] as [number,number,number,number][]).map(([x2,y2,w,op],i) => (
        <line key={i} x1="200" y1="140" x2={x2} y2={y2} stroke={INK} strokeWidth={w} opacity={op}/>
      ))}
      <line x1="112" y1="88" x2="200" y2="52" stroke={INK} strokeWidth="0.75" opacity="0.2"/>
      <line x1="292" y1="83" x2="314" y2="172" stroke={INK} strokeWidth="0.75" opacity="0.2"/>
      <line x1="152" y1="222" x2="90" y2="185" stroke={INK} strokeWidth="0.75" opacity="0.2"/>
      <circle cx="58" cy="50" r="2.5" fill={INK} opacity="0.1"/><circle cx="347" cy="52" r="1.5" fill={INK} opacity="0.08"/>
      <circle cx="52" cy="242" r="2" fill={INK} opacity="0.08"/><circle cx="352" cy="238" r="1.5" fill={INK} opacity="0.07"/>
    </svg>
  )

  if (idx === 1) return (
    // Stream — flowing data lines with card fragments
    <svg viewBox="0 0 400 280" fill="none" xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="xMidYMid slice" className={shared} aria-hidden>
      <rect width="400" height="280" fill={BG}/>
      <ellipse cx="200" cy="148" rx="175" ry="80" fill={WASH} opacity="0.4"/>
      <path d="M25 95 C110 78 155 118 225 98 S335 74 378 92" stroke={INK} strokeWidth="2" opacity="0.6" strokeLinecap="round"/>
      <path d="M25 135 C105 118 162 150 232 134 S332 114 378 132" stroke={INK} strokeWidth="1.5" opacity="0.5" strokeLinecap="round"/>
      <path d="M25 170 C95 155 158 180 228 166 S330 148 378 168" stroke={INK} strokeWidth="2" opacity="0.55" strokeLinecap="round"/>
      <path d="M25 205 C100 192 168 212 242 198 S338 182 378 202" stroke={INK} strokeWidth="1.5" opacity="0.45" strokeLinecap="round"/>
      <rect x="105" y="76" width="48" height="36" rx="2.5" fill="#f9f5ee" stroke={INK} strokeWidth="1.5"/>
      <line x1="113" y1="88" x2="145" y2="88" stroke={INK} strokeWidth="1" opacity="0.45"/>
      <line x1="113" y1="97" x2="138" y2="97" stroke={INK} strokeWidth="1" opacity="0.35"/>
      <line x1="113" y1="106" x2="143" y2="106" stroke={INK} strokeWidth="1" opacity="0.35"/>
      <rect x="238" y="115" width="48" height="36" rx="2.5" fill="#f9f5ee" stroke={INK} strokeWidth="1.5"/>
      <line x1="246" y1="127" x2="278" y2="127" stroke={INK} strokeWidth="1" opacity="0.45"/>
      <line x1="246" y1="136" x2="270" y2="136" stroke={INK} strokeWidth="1" opacity="0.35"/>
      <line x1="246" y1="145" x2="276" y2="145" stroke={INK} strokeWidth="1" opacity="0.35"/>
      <rect x="128" y="185" width="48" height="36" rx="2.5" fill="#f9f5ee" stroke={INK} strokeWidth="1.5"/>
      <line x1="136" y1="197" x2="168" y2="197" stroke={INK} strokeWidth="1" opacity="0.45"/>
      <line x1="136" y1="206" x2="158" y2="206" stroke={INK} strokeWidth="1" opacity="0.35"/>
      <line x1="136" y1="215" x2="165" y2="215" stroke={INK} strokeWidth="1" opacity="0.35"/>
      <circle cx="60" cy="58" r="2" fill={INK} opacity="0.1"/><circle cx="345" cy="62" r="1.5" fill={INK} opacity="0.08"/>
      <circle cx="355" cy="232" r="2" fill={INK} opacity="0.08"/>
    </svg>
  )

  if (idx === 2) return (
    // Iris — observing eye with radial lines
    <svg viewBox="0 0 400 280" fill="none" xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="xMidYMid slice" className={shared} aria-hidden>
      <rect width="400" height="280" fill={BG}/>
      <circle cx="200" cy="140" r="100" fill={WASH} opacity="0.5"/>
      <circle cx="200" cy="140" r="88" fill="none" stroke={INK} strokeWidth="2" opacity="0.45"/>
      <circle cx="200" cy="140" r="70" fill="none" stroke={INK} strokeWidth="1" opacity="0.28"/>
      <circle cx="200" cy="140" r="54" fill="none" stroke={INK} strokeWidth="1.5" opacity="0.35"/>
      {Array.from({length:16},(_,i) => {
        const a=(i/16)*Math.PI*2
        return <line key={i} x1={200+Math.cos(a)*56} y1={140+Math.sin(a)*56} x2={200+Math.cos(a)*85} y2={140+Math.sin(a)*85} stroke={INK} strokeWidth="0.75" opacity="0.28"/>
      })}
      {[-28,-14,0,14,28].map((dy,i) => {
        const half = Math.sqrt(Math.max(0, 88*88-dy*dy))
        return <line key={i} x1={200-half} y1={140+dy} x2={200+half} y2={140+dy} stroke={INK} strokeWidth="0.5" opacity="0.12"/>
      })}
      <circle cx="200" cy="140" r="28" fill={INK} opacity="0.88"/>
      <circle cx="190" cy="130" r="7" fill="white" opacity="0.1"/>
      <circle cx="60" cy="50" r="2" fill={INK} opacity="0.1"/><circle cx="342" cy="54" r="1.5" fill={INK} opacity="0.08"/>
      <circle cx="58" cy="240" r="1.5" fill={INK} opacity="0.08"/><circle cx="348" cy="235" r="2" fill={INK} opacity="0.08"/>
    </svg>
  )

  if (idx === 3) return (
    // Bloom — organic branching tree
    <svg viewBox="0 0 400 280" fill="none" xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="xMidYMid slice" className={shared} aria-hidden>
      <rect width="400" height="280" fill={BG}/>
      <ellipse cx="200" cy="150" rx="130" ry="90" fill={WASH} opacity="0.45"/>
      <path d="M200 268 L200 168" stroke={INK} strokeWidth="4.5" strokeLinecap="round" opacity="0.8"/>
      <path d="M200 205 Q152 172 118 145" stroke={INK} strokeWidth="2.5" strokeLinecap="round" opacity="0.7"/>
      <path d="M200 205 Q248 170 282 143" stroke={INK} strokeWidth="2.5" strokeLinecap="round" opacity="0.7"/>
      <path d="M200 178 Q165 148 142 116" stroke={INK} strokeWidth="2" strokeLinecap="round" opacity="0.62"/>
      <path d="M200 178 Q235 146 255 112" stroke={INK} strokeWidth="2" strokeLinecap="round" opacity="0.62"/>
      <path d="M200 168 L200 82" stroke={INK} strokeWidth="2" strokeLinecap="round" opacity="0.6"/>
      <path d="M142 116 Q126 96 116 74" stroke={INK} strokeWidth="1.25" strokeLinecap="round" opacity="0.48"/>
      <path d="M142 116 Q136 92 148 70" stroke={INK} strokeWidth="1.25" strokeLinecap="round" opacity="0.44"/>
      <path d="M255 112 Q272 90 280 68" stroke={INK} strokeWidth="1.25" strokeLinecap="round" opacity="0.48"/>
      <path d="M255 112 Q262 86 246 66" stroke={INK} strokeWidth="1.25" strokeLinecap="round" opacity="0.44"/>
      <path d="M200 100 Q184 84 180 64" stroke={INK} strokeWidth="1.25" strokeLinecap="round" opacity="0.44"/>
      <path d="M200 100 Q216 82 220 62" stroke={INK} strokeWidth="1.25" strokeLinecap="round" opacity="0.44"/>
      {([
        [116,74,5,0.72],[148,70,5,0.68],[280,68,5,0.72],[246,66,5,0.68],
        [180,64,5,0.68],[220,62,5,0.68],[118,145,7,0.62],[282,143,7,0.62],
      ] as [number,number,number,number][]).map(([cx,cy,r,op],i) => (
        <circle key={i} cx={cx} cy={cy} r={r} fill={INK} opacity={op}/>
      ))}
      <circle cx="55" cy="55" r="2" fill={INK} opacity="0.1"/><circle cx="348" cy="245" r="1.5" fill={INK} opacity="0.08"/>
    </svg>
  )

  if (idx === 4) return (
    // Spiral — converging vortex
    <svg viewBox="0 0 400 280" fill="none" xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="xMidYMid slice" className={shared} aria-hidden>
      <rect width="400" height="280" fill={BG}/>
      <circle cx="200" cy="140" r="112" fill={WASH} opacity="0.42"/>
      {Array.from({length:12},(_,i) => {
        const a=(i/12)*Math.PI*2
        return <line key={i} x1="200" y1="140" x2={200+Math.cos(a)*100} y2={140+Math.sin(a)*100} stroke={INK} strokeWidth="0.5" opacity="0.1"/>
      })}
      <path d="M200 140 Q262 88 314 140 Q334 178 292 214 Q246 244 188 228 Q126 208 112 156 Q102 98 144 62 Q186 28 244 42 Q306 58 334 118" fill="none" stroke={INK} strokeWidth="3" opacity="0.62" strokeLinecap="round"/>
      <path d="M200 140 Q247 110 270 143 Q280 165 263 184 Q243 202 218 197 Q186 190 176 165 Q168 138 184 118 Q200 100 224 107" fill="none" stroke={INK} strokeWidth="2" opacity="0.5" strokeLinecap="round"/>
      <path d="M200 140 Q218 126 226 141 Q230 152 222 161 Q213 168 206 164 Q198 160 197 151 Q197 142 202 139" fill="none" stroke={INK} strokeWidth="1.5" opacity="0.38" strokeLinecap="round"/>
      <circle cx="200" cy="140" r="6" fill={INK} opacity="0.88"/>
      <circle cx="60" cy="42" r="2" fill={INK} opacity="0.1"/><circle cx="344" cy="48" r="1.5" fill={INK} opacity="0.08"/>
      <circle cx="55" cy="245" r="1.5" fill={INK} opacity="0.08"/><circle cx="350" cy="240" r="2" fill={INK} opacity="0.08"/>
      <circle cx="358" cy="135" r="1" fill={INK} opacity="0.1"/><circle cx="46" cy="148" r="1.5" fill={INK} opacity="0.1"/>
    </svg>
  )

  if (idx === 5) return (
    // Stack — layered document planes
    <svg viewBox="0 0 400 280" fill="none" xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="xMidYMid slice" className={shared} aria-hidden>
      <rect width="400" height="280" fill={BG}/>
      <ellipse cx="200" cy="150" rx="158" ry="92" fill={WASH} opacity="0.4"/>
      <rect x="88" y="188" width="228" height="44" rx="4" fill="#ede5d6" stroke={INK} strokeWidth="1.5" opacity="0.58"/>
      <line x1="103" y1="204" x2="198" y2="204" stroke={INK} strokeWidth="1" opacity="0.32"/>
      <line x1="103" y1="215" x2="173" y2="215" stroke={INK} strokeWidth="1" opacity="0.28"/>
      <line x1="103" y1="224" x2="188" y2="224" stroke={INK} strokeWidth="1" opacity="0.28"/>
      <rect x="76" y="142" width="228" height="44" rx="4" fill="#f0e8d9" stroke={INK} strokeWidth="1.5" opacity="0.73"/>
      <line x1="91" y1="158" x2="188" y2="158" stroke={INK} strokeWidth="1" opacity="0.38"/>
      <line x1="91" y1="169" x2="162" y2="169" stroke={INK} strokeWidth="1" opacity="0.32"/>
      <line x1="91" y1="179" x2="180" y2="179" stroke={INK} strokeWidth="1" opacity="0.32"/>
      <rect x="64" y="92" width="228" height="48" rx="4" fill="#f5ede0" stroke={INK} strokeWidth="2" opacity="0.88"/>
      <line x1="79" y1="110" x2="182" y2="110" stroke={INK} strokeWidth="1.2" opacity="0.48"/>
      <line x1="79" y1="122" x2="152" y2="122" stroke={INK} strokeWidth="1" opacity="0.38"/>
      <line x1="79" y1="133" x2="175" y2="133" stroke={INK} strokeWidth="1" opacity="0.38"/>
      <line x1="64" y1="140" x2="76" y2="142" stroke={INK} strokeWidth="1" opacity="0.38"/>
      <line x1="292" y1="140" x2="304" y2="142" stroke={INK} strokeWidth="1" opacity="0.38"/>
      <line x1="76" y1="186" x2="88" y2="188" stroke={INK} strokeWidth="1" opacity="0.32"/>
      <line x1="304" y1="186" x2="316" y2="188" stroke={INK} strokeWidth="1" opacity="0.32"/>
      <circle cx="55" cy="55" r="2" fill={INK} opacity="0.1"/><circle cx="350" cy="50" r="1.5" fill={INK} opacity="0.08"/>
      <circle cx="52" cy="245" r="1.5" fill={INK} opacity="0.08"/><circle cx="350" cy="240" r="2" fill={INK} opacity="0.08"/>
    </svg>
  )

  // idx === 6: Avatar — ink figure at workstation
  return (
    <svg viewBox="0 0 400 280" fill="none" xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="xMidYMid slice" className={shared} aria-hidden>
      <rect width="400" height="280" fill={BG}/>
      <ellipse cx="190" cy="155" rx="145" ry="105" fill={WASH} opacity="0.48"/>
      {/* Desk surface */}
      <path d="M55 192 Q195 186 345 192" stroke={INK} strokeWidth="2.5" strokeLinecap="round" opacity="0.65"/>
      {/* Chair back */}
      <path d="M148 132 Q148 120 168 118 Q188 120 188 132 L188 190 L148 190 Z" fill={INK} opacity="0.12" stroke={INK} strokeWidth="1.5" strokeLinejoin="round"/>
      {/* Chair legs */}
      <line x1="153" y1="190" x2="148" y2="248" stroke={INK} strokeWidth="2" strokeLinecap="round" opacity="0.4"/>
      <line x1="183" y1="190" x2="188" y2="248" stroke={INK} strokeWidth="2" strokeLinecap="round" opacity="0.4"/>
      <line x1="140" y1="230" x2="196" y2="230" stroke={INK} strokeWidth="1.5" strokeLinecap="round" opacity="0.3"/>
      {/* Body/torso silhouette */}
      <path d="M168 158 Q155 168 152 192 Q168 195 188 192 Q185 168 172 158 Z" fill={INK} opacity="0.78"/>
      {/* Head */}
      <circle cx="170" cy="142" r="20" fill={INK} opacity="0.85"/>
      {/* Arm reaching forward */}
      <path d="M178 172 Q200 178 222 184" stroke={INK} strokeWidth="4" strokeLinecap="round" opacity="0.6"/>
      {/* Monitor */}
      <rect x="218" y="98" width="95" height="68" rx="4" fill="#f9f5ee" stroke={INK} strokeWidth="2" opacity="0.9"/>
      {/* Screen content */}
      <line x1="229" y1="116" x2="302" y2="116" stroke={INK} strokeWidth="1.2" opacity="0.4"/>
      <line x1="229" y1="128" x2="285" y2="128" stroke={INK} strokeWidth="1" opacity="0.32"/>
      <line x1="229" y1="139" x2="296" y2="139" stroke={INK} strokeWidth="1" opacity="0.32"/>
      <line x1="229" y1="150" x2="272" y2="150" stroke={INK} strokeWidth="1" opacity="0.28"/>
      {/* Screen glow hint */}
      <rect x="218" y="98" width="95" height="68" rx="4" fill={INK} opacity="0.03"/>
      {/* Monitor stand */}
      <line x1="265" y1="166" x2="265" y2="186" stroke={INK} strokeWidth="2" strokeLinecap="round" opacity="0.45"/>
      <line x1="252" y1="187" x2="278" y2="187" stroke={INK} strokeWidth="2" strokeLinecap="round" opacity="0.45"/>
      {/* Keyboard */}
      <rect x="200" y="186" width="70" height="10" rx="2" fill="none" stroke={INK} strokeWidth="1" opacity="0.35"/>
      {/* Ambient dots */}
      <circle cx="62" cy="50" r="2.5" fill={INK} opacity="0.1"/>
      <circle cx="342" cy="54" r="1.5" fill={INK} opacity="0.08"/>
      <circle cx="58" cy="244" r="1.5" fill={INK} opacity="0.08"/>
      <circle cx="348" cy="240" r="2" fill={INK} opacity="0.08"/>
      <circle cx="100" cy="88" r="1.5" fill={INK} opacity="0.1"/>
      <circle cx="320" cy="240" r="1" fill={INK} opacity="0.08"/>
    </svg>
  )

  // idx === 7: Prism — chaos (red vortex) meets order (geometric network + green energy)
  return (
    <svg viewBox="0 0 400 280" fill="none" xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="xMidYMid slice" className={shared} aria-hidden>
      <defs>
        <radialGradient id="ag-burst" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="#00e676" stopOpacity="0.95"/>
          <stop offset="45%" stopColor="#1abc9c" stopOpacity="0.45"/>
          <stop offset="100%" stopColor="#1abc9c" stopOpacity="0"/>
        </radialGradient>
      </defs>
      <rect width="400" height="280" fill="#f2e8d5"/>
      {/* Red/orange watercolor wash layers */}
      <ellipse cx="148" cy="148" rx="118" ry="95" fill="#e8622a" opacity="0.11"/>
      <ellipse cx="135" cy="155" rx="95" ry="75" fill="#c0392b" opacity="0.09"/>
      <ellipse cx="158" cy="138" rx="78" ry="62" fill="#e67e22" opacity="0.08"/>
      {/* Vortex spiral */}
      <path d="M162 145 Q200 92 238 122 Q262 145 240 175 Q214 208 172 200 Q128 190 115 156 Q105 112 138 84 Q172 58 212 70 Q258 84 270 128" fill="none" stroke="#c0392b" strokeWidth="3.5" opacity="0.68" strokeLinecap="round"/>
      <path d="M162 145 Q188 116 208 133 Q222 147 210 164 Q194 180 172 174 Q148 166 143 148 Q138 126 154 113 Q172 100 193 110" fill="none" stroke="#c0392b" strokeWidth="2" opacity="0.48" strokeLinecap="round"/>
      {/* Red/orange shard triangles — outer ring */}
      <polygon points="92,85 110,74 104,100" fill="#c0392b" opacity="0.78"/>
      <polygon points="115,60 130,52 126,72" fill="#e74c3c" opacity="0.72"/>
      <polygon points="74,125 90,114 86,138" fill="#c0392b" opacity="0.68"/>
      <polygon points="83,168 98,157 94,178" fill="#d35400" opacity="0.7"/>
      <polygon points="105,200 120,190 116,210" fill="#c0392b" opacity="0.65"/>
      <polygon points="145,222 157,208 164,223" fill="#e74c3c" opacity="0.68"/>
      <polygon points="185,218 196,204 202,220" fill="#c0392b" opacity="0.62"/>
      <polygon points="216,198 228,185 234,200" fill="#d35400" opacity="0.7"/>
      <polygon points="232,166 244,155 248,172" fill="#e74c3c" opacity="0.65"/>
      <polygon points="234,116 248,105 250,124" fill="#c0392b" opacity="0.7"/>
      <polygon points="215,85 228,74 230,93" fill="#e74c3c" opacity="0.68"/>
      <polygon points="186,68 198,58 202,76" fill="#c0392b" opacity="0.72"/>
      <polygon points="152,64 160,53 168,67" fill="#d35400" opacity="0.65"/>
      {/* Mid-scatter shards */}
      <polygon points="65,106 73,98 71,112" fill="#e74c3c" opacity="0.55"/>
      <polygon points="68,152 76,145 74,160" fill="#c0392b" opacity="0.5"/>
      <polygon points="78,190 86,183 84,198" fill="#d35400" opacity="0.52"/>
      <polygon points="200,228 208,218 213,230" fill="#c0392b" opacity="0.45"/>
      <polygon points="248,182 255,173 258,186" fill="#e74c3c" opacity="0.5"/>
      <polygon points="255,135 262,126 265,140" fill="#c0392b" opacity="0.55"/>
      <polygon points="247,95 254,86 257,100" fill="#d35400" opacity="0.55"/>
      <polygon points="98,67 105,59 108,72" fill="#c0392b" opacity="0.55"/>
      {/* Outer sparse fragments */}
      <polygon points="44,92 51,85 49,98" fill="#e74c3c" opacity="0.32"/>
      <polygon points="38,146 45,138 47,152" fill="#c0392b" opacity="0.28"/>
      <polygon points="50,200 58,192 56,206" fill="#d35400" opacity="0.28"/>
      {/* Green energy burst */}
      <circle cx="212" cy="143" r="30" fill="url(#ag-burst)"/>
      <circle cx="213" cy="166" r="18" fill="url(#ag-burst)" opacity="0.65"/>
      <circle cx="212" cy="143" r="5" fill="#00e676" opacity="0.95"/>
      <circle cx="213" cy="166" r="3.5" fill="#00e676" opacity="0.85"/>
      <line x1="212" y1="143" x2="195" y2="127" stroke="#00e676" strokeWidth="1.5" opacity="0.68"/>
      <line x1="212" y1="143" x2="231" y2="129" stroke="#00e676" strokeWidth="1.5" opacity="0.62"/>
      <line x1="212" y1="143" x2="199" y2="161" stroke="#00e676" strokeWidth="1.5" opacity="0.6"/>
      <line x1="212" y1="143" x2="227" y2="157" stroke="#00e676" strokeWidth="1.5" opacity="0.58"/>
      <line x1="213" y1="166" x2="222" y2="180" stroke="#00e676" strokeWidth="1" opacity="0.5"/>
      {/* Right sphere */}
      <circle cx="308" cy="140" r="68" fill="#f5ede0" stroke="#2c3e50" strokeWidth="2.5" opacity="0.88"/>
      <circle cx="308" cy="140" r="50" fill="none" stroke="#2c3e50" strokeWidth="1" opacity="0.3"/>
      {/* Network nodes */}
      {([
        [308,72,5,0.82],[352,93,5,0.78],[372,138,5,0.82],[354,184,5,0.78],
        [308,205,5,0.82],[262,184,5,0.78],[242,138,5,0.82],[262,93,5,0.78],
        [330,80,3.5,0.68],[362,112,3.5,0.65],[368,165,3.5,0.68],[342,196,3.5,0.65],
        [280,198,3.5,0.68],[250,165,3.5,0.65],[248,112,3.5,0.68],[278,80,3.5,0.65],
      ] as [number,number,number,number][]).map(([cx,cy,r,op],i) => (
        <circle key={i} cx={cx} cy={cy} r={r} fill="#2c3e50" opacity={op}/>
      ))}
      {/* Network triangulation lines */}
      {([
        [308,72,352,93,1.2,0.42],[352,93,372,138,1.2,0.42],[372,138,354,184,1.2,0.42],[354,184,308,205,1.2,0.42],
        [308,205,262,184,1.2,0.42],[262,184,242,138,1.2,0.42],[242,138,262,93,1.2,0.42],[262,93,308,72,1.2,0.42],
        [308,72,330,80,0.75,0.22],[330,80,352,93,0.75,0.22],[352,93,362,112,0.75,0.22],[362,112,372,138,0.75,0.22],
        [372,138,368,165,0.75,0.22],[368,165,354,184,0.75,0.22],[354,184,342,196,0.75,0.22],[342,196,308,205,0.75,0.22],
        [308,205,280,198,0.75,0.22],[280,198,262,184,0.75,0.22],[262,184,250,165,0.75,0.22],[250,165,242,138,0.75,0.22],
        [242,138,248,112,0.75,0.22],[248,112,262,93,0.75,0.22],[262,93,278,80,0.75,0.22],[278,80,308,72,0.75,0.22],
        [308,72,308,205,0.75,0.18],[352,93,262,184,0.75,0.18],[372,138,242,138,0.75,0.18],[354,184,262,93,0.75,0.18],
        [330,80,280,198,0.75,0.18],[362,112,250,165,0.75,0.18],[368,165,248,112,0.75,0.18],[342,196,278,80,0.75,0.18],
      ] as [number,number,number,number,number,number][]).map(([x1,y1,x2,y2,w,op],i) => (
        <line key={i} x1={x1} y1={y1} x2={x2} y2={y2} stroke="#2c3e50" strokeWidth={w} opacity={op}/>
      ))}
      {/* Infinity symbol — two overlapping circles */}
      <circle cx="293" cy="140" r="18" fill="none" stroke="#2c3e50" strokeWidth="2.5" opacity="0.75"/>
      <circle cx="323" cy="140" r="18" fill="none" stroke="#2c3e50" strokeWidth="2.5" opacity="0.75"/>
      <ellipse cx="308" cy="140" rx="7" ry="14" fill="#f5ede0"/>
      {/* Green streaming lines */}
      <path d="M363 122 Q390 108 400 102" stroke="#1abc9c" strokeWidth="3.5" opacity="0.72" strokeLinecap="round"/>
      <path d="M371 136 Q398 132 400 130" stroke="#1abc9c" strokeWidth="5" opacity="0.82" strokeLinecap="round"/>
      <path d="M371 145 Q398 149 400 151" stroke="#1abc9c" strokeWidth="4" opacity="0.75" strokeLinecap="round"/>
      <path d="M363 158 Q390 170 400 176" stroke="#1abc9c" strokeWidth="3" opacity="0.65" strokeLinecap="round"/>
      <path d="M354 172 Q382 188 400 196" stroke="#1abc9c" strokeWidth="2" opacity="0.48" strokeLinecap="round"/>
    </svg>
  )
}

const slugify = (text: string): string =>
  text.toLowerCase().trim()
    .replace(/[^\w\s-]/g, '')
    .replace(/[\s_-]+/g, '-')
    .replace(/^-+|-+$/g, '')

const formatNumber = (num: number): string => {
  if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M'
  if (num >= 1000) return (num / 1000).toFixed(1) + 'K'
  return num.toString()
}

const formatDate = (value: string): string => {
  if (!value) return 'Recently'
  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  }).format(new Date(value))
}

// Filter Dropdown — portal-based so it escapes the overflow-y-auto scroll container
const FILTER_OPTIONS = [
  { value: 'all', label: 'All' },
  { value: 'active', label: 'Active' },
  { value: 'public', label: 'Public' },
  { value: 'workflow', label: 'Workflows' },
] as const

type FilterType = 'all' | 'active' | 'public' | 'workflow'

function FilterDropdown({
  value,
  onChange,
}: {
  value: FilterType
  onChange: (v: FilterType) => void
}) {
  const [open, setOpen] = useState(false)
  const [anchorRect, setAnchorRect] = useState<DOMRect | null>(null)
  const btnRef = useRef<HTMLButtonElement>(null)
  const menuRef = useRef<HTMLDivElement>(null)
  const selected = FILTER_OPTIONS.find((o) => o.value === value)!

  useEffect(() => {
    if (!open) return
    const handleClick = (e: MouseEvent) => {
      if (
        menuRef.current && !menuRef.current.contains(e.target as Node) &&
        btnRef.current && !btnRef.current.contains(e.target as Node)
      ) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [open])

  const toggle = () => {
    if (!open && btnRef.current) setAnchorRect(btnRef.current.getBoundingClientRect())
    setOpen((v) => !v)
  }

  return (
    <>
      <button
        ref={btnRef}
        onClick={toggle}
        className="flex w-full items-center justify-between rounded-[0.35rem] border border-black/10 bg-white/[0.72] px-4 py-3 text-[13px] text-[#171717] outline-none transition-all focus:border-[#ff5f8f] focus:ring-2 focus:ring-[#ff5f8f]/20 md:text-[14px]"
        style={{ borderColor: open ? '#ff5f8f' : undefined, boxShadow: open ? '0 0 0 2px rgba(255,95,143,0.2)' : undefined }}
      >
        <span>{selected.label}</span>
        <ChevronDown className={`h-4 w-4 text-[#5b564e] transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>
      {open && anchorRect && createPortal(
        <div
          ref={menuRef}
          style={{
            position: 'fixed',
            top: anchorRect.bottom + 4,
            left: anchorRect.left,
            width: anchorRect.width,
            zIndex: 9999,
          }}
          className="rounded-[0.45rem] border border-black/[0.08] bg-[rgba(255,255,255,0.94)] py-1.5 shadow-[0_18px_40px_rgba(0,0,0,0.12)] backdrop-blur-xl"
        >
          {FILTER_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              onClick={() => { onChange(opt.value); setOpen(false) }}
              className={`flex w-full items-center gap-2.5 px-4 py-2 text-[13px] text-left transition-colors hover:bg-black/5 ${value === opt.value ? 'font-semibold text-[#ff5f8f]' : 'text-gray-700'}`}
            >
              {opt.label}
            </button>
          ))}
        </div>,
        document.body
      )}
    </>
  )
}

// Dropdown Menu — rendered via portal so it escapes card overflow/stacking
const DropdownMenu = ({
  agent,
  onDelete,
  onClose,
  anchorRect,
}: {
  agent: Agent
  onDelete: () => void
  onClose: () => void
  anchorRect: DOMRect
}) => {
  const router = useRouter()
  const menuRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        onClose()
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [onClose])

  const style: CSSProperties = {
    position: 'fixed',
    top: anchorRect.bottom + 4,
    right: window.innerWidth - anchorRect.right,
    width: 176,
    zIndex: 9999,
  }

  return createPortal(
    <div
      ref={menuRef}
      style={style}
      className="rounded-[0.45rem] border border-black/[0.08] bg-[rgba(255,255,255,0.84)] py-1.5 shadow-[0_18px_40px_rgba(0,0,0,0.12)] backdrop-blur-xl"
    >
      <button
        onClick={() => { router.push(`/agents/${agent.slug}/edit`); onClose() }}
        className="flex w-full items-center gap-2.5 px-4 py-2 text-sm text-gray-700 hover:bg-black/5"
      >
        <Settings size={15} className="text-gray-400" />
        Edit
      </button>
      <button
        onClick={() => { router.push(`/agents/${agent.slug}/landing-page`); onClose() }}
        className="flex w-full items-center gap-2.5 px-4 py-2 text-sm text-gray-700 hover:bg-black/5"
      >
        <Globe size={15} className="text-[#ff5f8f]" />
        Landing Page
      </button>
      <button
        onClick={() => { router.push(`/agents/${agent.slug}/sub-agents`); onClose() }}
        className="flex w-full items-center gap-2.5 px-4 py-2 text-sm text-gray-700 hover:bg-black/5"
      >
        <Users size={15} className="text-gray-400" />
        Sub-Agents
      </button>
      <button
        onClick={() => { router.push(`/agents/${agent.slug}/clone`); onClose() }}
        className="flex w-full items-center gap-2.5 px-4 py-2 text-sm text-gray-700 hover:bg-black/5"
      >
        <Copy size={15} className="text-gray-400" />
        Duplicate
      </button>
      <button
        onClick={() => { router.push(`/agents/${agent.slug}/lens`); onClose() }}
        className="flex w-full items-center gap-2.5 px-4 py-2 text-sm text-gray-700 hover:bg-black/5"
      >
        <Activity size={15} className="text-indigo-400" />
        Lens
      </button>
      <div className="my-1.5 h-px bg-black/[0.08]" />
      <button
        onClick={() => { onDelete(); onClose() }}
        className="flex w-full items-center gap-2.5 px-4 py-2 text-sm text-red-600 hover:bg-red-50"
      >
        <Trash2 size={15} />
        Delete
      </button>
    </div>,
    document.body
  )
}

// Agent Card
const AgentCard = ({
  agent,
  onDelete
}: {
  agent: Agent
  onDelete: (agent: { id: string; name: string }) => void
}) => {
  const router = useRouter()
  const [menuOpen, setMenuOpen] = useState(false)
  const [anchorRect, setAnchorRect] = useState<DOMRect | null>(null)
  const btnRef = useRef<HTMLButtonElement>(null)
  const hasAvatar = Boolean(agent.avatar)

  const handleMenuToggle = (e: ReactMouseEvent<HTMLButtonElement>) => {
    e.preventDefault()
    e.stopPropagation()
    if (!menuOpen && btnRef.current) {
      setAnchorRect(btnRef.current.getBoundingClientRect())
    }
    setMenuOpen(!menuOpen)
  }

  return (
    <div className="flex flex-col overflow-hidden rounded-[0.5rem] border border-black/10 bg-white/60 shadow-[0_18px_40px_rgba(0,0,0,0.05)] transition-all duration-300 hover:-translate-y-1 hover:shadow-[0_24px_56px_rgba(0,0,0,0.08)]">
      <div className="relative flex min-h-[16rem] items-center justify-center overflow-hidden border-b border-black/10 md:min-h-[18.5rem]">
        {hasAvatar ? (
          <>
            <img
              src={agent.avatar || undefined}
              alt={agent.agent_name}
              className="absolute inset-0 h-full w-full object-cover object-center"
            />
            <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_50%_24%,rgba(255,255,255,0.22),transparent_42%)]" />
            <div className="pointer-events-none absolute inset-0 bg-[linear-gradient(180deg,rgba(243,236,223,0.08),rgba(243,236,223,0.04)_45%,rgba(255,255,255,0.1))]" />
          </>
        ) : (
          <AgentIllustration name={agent.agent_name} />
        )}

        <div className="absolute right-5 top-5 z-20">
          <button
            ref={btnRef}
            onClick={handleMenuToggle}
            className="flex h-10 w-10 items-center justify-center rounded-[0.35rem] border border-black/10 bg-white/88 shadow-[0_8px_20px_rgba(0,0,0,0.08)] transition-colors hover:bg-white"
          >
            <MoreVertical className="h-4 w-4 text-gray-500" />
          </button>
          {menuOpen && anchorRect && (
            <DropdownMenu
              agent={agent}
              onDelete={() => onDelete({ id: agent.slug, name: agent.agent_name })}
              onClose={() => setMenuOpen(false)}
              anchorRect={anchorRect}
            />
          )}
        </div>
      </div>

      <div className="flex flex-1 flex-col p-6">
        <div className="mb-2 flex items-start justify-between gap-3">
          <h3 className="line-clamp-2 text-[1.35rem] font-semibold leading-tight tracking-[-0.04em] text-[#171717]">
            {agent.agent_name}
          </h3>
          <div className="flex shrink-0 items-center gap-1.5 text-[#7a736a]">
            {agent.is_public ? <Globe className="h-4 w-4 text-[#2d8b69]" /> : <Lock className="h-4 w-4" />}
            <span className="text-[11px] font-semibold uppercase tracking-[0.16em]">
              {agent.is_public ? 'Public' : 'Private'}
            </span>
          </div>
        </div>

        <p className="mb-3 text-sm uppercase tracking-[0.16em] text-[#7a736a]">
          {agent.category || agent.agent_type || 'AI Agent'}
        </p>

        <p className="mb-4 line-clamp-2 text-sm leading-relaxed text-[#575149]">
          {agent.description || 'No description provided'}
        </p>

        <p className="text-xs text-[#7a736a]">
          Created {formatDate(agent.created_at)}
        </p>

        <div className="my-4 border-t border-black/10" />

        <div className="mb-5 flex items-center gap-6">
          <div>
            <p className="mb-0.5 text-xs uppercase tracking-[0.16em] text-[#7a736a]">Uses</p>
            <p className="text-xl font-semibold text-[#171717]">{formatNumber(agent.execution_count || 0)}</p>
          </div>
          <div>
            <p className="mb-0.5 text-xs uppercase tracking-[0.16em] text-[#7a736a]">Success</p>
            <p className="text-xl font-semibold text-[#171717]">{(agent.success_rate || 0).toFixed(0)}%</p>
          </div>
          <div>
            <p className="mb-0.5 text-xs uppercase tracking-[0.16em] text-[#7a736a]">Team</p>
            <p className="text-xl font-semibold text-[#171717]">{agent.sub_agents_count || 0}</p>
          </div>
        </div>

        <div className="mt-auto flex items-center gap-3">
          <button
            onClick={() => router.push(`/agents/${agent.slug}/chat`)}
            className="flex-1 rounded-[0.35rem] border border-black/15 bg-white/70 px-5 py-2.5 text-center text-sm font-semibold uppercase tracking-[0.14em] text-[#171717] transition-colors hover:bg-white"
          >
            Start Chat
          </button>
          <button
            onClick={() => router.push(`/agents/${agent.slug}/view`)}
            className="px-4 py-2.5 text-sm font-medium text-[#7a736a] transition-colors hover:text-[#171717]"
          >
            View Details
          </button>
          <a
            href={`/a/${agent.public_slug || slugify(agent.agent_name)}`}
            target="_blank"
            rel="noopener noreferrer"
            className="flex h-10 w-10 items-center justify-center rounded-[0.35rem] border border-black/10 bg-white/70 text-[#7a736a] transition-colors hover:bg-white hover:text-[#171717]"
            title="View public page"
          >
            <Globe className="h-4 w-4" />
          </a>
        </div>
      </div>
    </div>
  )
}

export default function AgentsPage() {
  const router = useRouter()
  const [agents, setAgents] = useState<Agent[]>([])
  const [loading, setLoading] = useState(true)
  const [showDeleteModal, setShowDeleteModal] = useState(false)
  const [agentToDelete, setAgentToDelete] = useState<{ id: string; name: string } | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [filterType, setFilterType] = useState<FilterType>('all')

  const [currentPage, setCurrentPage] = useState(1)
  const [pageSize] = useState(9)
  const [totalPages, setTotalPages] = useState(1)
  // Separate flag for search-while-results-exist: dims the grid instead of replacing it
  const [isSearching, setIsSearching] = useState(false)

  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  // Track the active page+search combination to avoid stale responses overwriting newer ones
  const fetchIdRef = useRef(0)

  const fetchAgents = useCallback(async (search: string, page: number, isInitial = false) => {
    const id = ++fetchIdRef.current
    if (isInitial) {
      setLoading(true)
    } else {
      setIsSearching(true)
    }
    try {
      const response = await apiClient.getAgents(page, pageSize, search || undefined)
      if (id !== fetchIdRef.current) return // stale response — discard
      const agentsList = response.agents_list || []
      const pagination = response.pagination || {}
      setAgents(agentsList)
      setTotalPages(pagination.total_pages || 1)
    } catch (error) {
      if (id !== fetchIdRef.current) return
      console.error('Failed to fetch agents:', error)
      toast.error('Failed to load agents')
    } finally {
      if (id === fetchIdRef.current) {
        setLoading(false)
        setIsSearching(false)
      }
    }
  }, [pageSize])

  // Initial load
  useEffect(() => {
    fetchAgents(searchQuery, currentPage, true)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Page change (not triggered by search — search resets page via its own handler)
  useEffect(() => {
    if (loading) return // skip during initial load
    fetchAgents(searchQuery, currentPage, false)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentPage])

  const handleSearchChange = (value: string) => {
    setSearchQuery(value)
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      setCurrentPage(1)
      fetchAgents(value, 1, false)
    }, 300)
  }

  useEffect(() => {
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current) }
  }, [])

  const handleDeleteAgent = async () => {
    if (!agentToDelete) return
    try {
      await apiClient.deleteAgent(agentToDelete.id)
      toast.success('Agent deleted')
      setShowDeleteModal(false)
      setAgentToDelete(null)
      fetchAgents(searchQuery, currentPage, false)
    } catch (error) {
      console.error('Failed to delete agent:', error)
      toast.error('Failed to delete agent')
    }
  }

  // Filter is now server-side for search. Client-side filter only handles
  // sub-agent exclusion and the type dropdown (active/workflow/public).
  const filteredAgents = agents.filter((agent) => {
    if (agent.is_sub_agent) return false
    const matchesFilter =
      filterType === 'all' ? true :
      filterType === 'active' ? (agent.status === 'ACTIVE' || agent.status === 'idle') :
      filterType === 'workflow' ? agent.workflow_type !== null :
      filterType === 'public' ? agent.is_public : true
    return matchesFilter
  })

  // Only count parent/standalone agents (exclude sub-agents)
  const parentAgents = agents.filter(a => !a.is_sub_agent)
  const activeCount = parentAgents.filter(a => a.status === 'ACTIVE' || a.status === 'idle').length
  const workflowCount = parentAgents.filter(a => a.workflow_type).length
  const publicCount = parentAgents.filter(a => a.is_public).length
  const parentAgentCount = parentAgents.length

  return (
    <div className="min-h-full px-4 py-4 md:px-8 md:py-6 xl:px-10">
      <div className="mx-auto max-w-[90rem]">
        <div className="dashboard-surface mb-6 p-5 md:p-6 xl:p-7">
          <div className="flex flex-col gap-6 xl:flex-row xl:items-end xl:justify-between">
            <div>
              <div className="mb-3 inline-flex items-center gap-2 rounded-[0.35rem] border border-black/10 bg-white/70 px-3.5 py-1.5 text-[11px] font-semibold uppercase tracking-[0.18em] text-[#6e675d]">
                <Sparkles className="h-3 w-3 text-[#ff5f8f]" />
                Agent Library
              </div>
              <h1 className="text-[1.8rem] font-semibold tracking-[-0.05em] text-[#171717] md:text-[2.65rem]">
                <span className="editorial-highlight">Agents</span>
              </h1>
              <p className="mt-3 max-w-3xl text-[13px] leading-relaxed text-[#5b564e] md:text-[15px]">
                {parentAgentCount} agents, {activeCount} active, and {publicCount} public. Search, filter, and jump directly into the ones doing the work.
              </p>
            </div>
            <button
              onClick={() => router.push('/agents/create')}
              className="inline-flex flex-shrink-0 items-center gap-2 rounded-[0.35rem] bg-[#181818] px-5 py-3 text-[13px] font-medium text-[#f7f2e7] transition-transform hover:-translate-y-0.5 md:text-[14px]"
            >
              <Plus size={18} />
              <span className="hidden sm:inline">New Agent</span>
              <span className="sm:hidden">New</span>
            </button>
          </div>

          <div className="mt-5 flex flex-wrap gap-3">
            <div className="dashboard-chip px-4 py-2 text-[13px] font-medium">{parentAgentCount} total</div>
            <div className="dashboard-chip px-4 py-2 text-[13px] font-medium">{activeCount} active</div>
            <div className="dashboard-chip px-4 py-2 text-[13px] font-medium">{workflowCount} workflows</div>
            <div className="dashboard-chip px-4 py-2 text-[13px] font-medium">{publicCount} public</div>
          </div>

          <div className="mt-5 grid gap-3 md:grid-cols-[minmax(0,1fr)_220px]">
            <label className="relative block">
              <Search className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-[#8a8378]" />
              <input
                type="text"
                placeholder="Search agents..."
                value={searchQuery}
                onChange={(e) => handleSearchChange(e.target.value)}
                className="w-full rounded-[0.35rem] border border-black/10 bg-white/[0.72] py-3 pl-11 pr-4 text-[13px] text-[#171717] outline-none transition-all focus:border-[#ff5f8f] focus:ring-2 focus:ring-[#ff5f8f]/20 md:text-[14px]"
              />
            </label>

            <FilterDropdown value={filterType} onChange={setFilterType} />
          </div>
        </div>

        {/* Content */}
        {loading ? (
          <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3">
            {[...Array(6)].map((_, i) => (
              <div key={i} className="animate-pulse overflow-hidden rounded-[0.5rem] border border-black/10 bg-white/60 shadow-[0_18px_40px_rgba(0,0,0,0.05)]">
                <div className="flex items-center justify-center border-b border-black/10 bg-[#efe7d8] pt-10 pb-12">
                  <div className="h-24 w-24 rounded-[0.45rem] bg-white shadow-lg" />
                </div>
                <div className="p-6">
                  <div className="mb-2 h-5 w-40 rounded bg-black/10" />
                  <div className="mb-3 h-4 w-28 rounded bg-black/5" />
                  <div className="mb-2 h-4 w-full rounded bg-black/5" />
                  <div className="mb-4 h-4 w-3/4 rounded bg-black/5" />
                  <div className="mb-4 h-3 w-24 rounded bg-black/5" />
                  <div className="mb-5 border-t border-black/10 pt-4">
                    <div className="flex gap-6">
                      <div>
                        <div className="mb-1 h-3 w-10 rounded bg-black/5" />
                        <div className="h-6 w-8 rounded bg-black/10" />
                      </div>
                      <div>
                        <div className="mb-1 h-3 w-12 rounded bg-black/5" />
                        <div className="h-6 w-10 rounded bg-black/10" />
                      </div>
                      <div>
                        <div className="mb-1 h-3 w-12 rounded bg-black/5" />
                        <div className="h-6 w-8 rounded bg-black/10" />
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <div className="h-10 flex-1 rounded-[0.35rem] bg-black/5" />
                    <div className="h-10 w-24 rounded-[0.35rem] bg-black/5" />
                    <div className="h-10 w-10 rounded-[0.35rem] bg-black/5" />
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : filteredAgents.length === 0 ? (
          <div className="dashboard-surface py-20 text-center">
            <div className="mx-auto mb-4 flex h-20 w-20 items-center justify-center rounded-[0.45rem] bg-[#ffe1ea]">
              <Bot className="h-10 w-10 text-[#171717]" />
            </div>
            <h3 className="mb-2 text-[1.05rem] font-semibold text-[#171717] md:text-[1.35rem]">
              {searchQuery || filterType !== 'all' ? 'No matching agents' : 'No agents yet'}
            </h3>
            <p className="mb-6 text-[13px] text-[#6c655c] md:text-[14px]">
              {searchQuery || filterType !== 'all'
                ? 'Try adjusting your search or filter'
                : 'Create your first AI agent to get started'}
            </p>
            {!searchQuery && filterType === 'all' && (
              <button
                onClick={() => router.push('/agents/create')}
                className="inline-flex items-center gap-2 rounded-[0.35rem] bg-[#181818] px-6 py-3 text-[13px] font-medium text-[#f7f2e7] transition-transform hover:-translate-y-0.5 md:text-[14px]"
              >
                <Plus size={20} />
                Create Agent
              </button>
            )}
          </div>
        ) : (
          <>
            <div className={`grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3 transition-opacity duration-150 ${isSearching ? 'opacity-50 pointer-events-none' : 'opacity-100'}`}>
              {filteredAgents.map((agent) => (
                <AgentCard
                  key={agent.id}
                  agent={agent}
                  onDelete={(agentToRemove) => {
                    setAgentToDelete(agentToRemove)
                    setShowDeleteModal(true)
                  }}
                />
              ))}
            </div>

            {totalPages > 1 && (
              <div className="dashboard-surface mt-8 flex items-center justify-center gap-4 px-4 py-3">
                <button
                  onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                  disabled={currentPage === 1}
                  className="rounded-[0.35rem] px-4 py-2 text-[13px] font-medium text-[#5b564e] transition-colors hover:bg-black/5 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  Previous
                </button>
                <span className="text-[13px] text-[#6c655c]">
                  {currentPage} of {totalPages}
                </span>
                <button
                  onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                  disabled={currentPage === totalPages}
                  className="rounded-[0.35rem] px-4 py-2 text-[13px] font-medium text-[#5b564e] transition-colors hover:bg-black/5 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  Next
                </button>
              </div>
            )}
          </>
        )}
      </div>

      {/* Delete Modal */}
      {showDeleteModal && agentToDelete && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
          <div className="dashboard-surface w-full max-w-sm p-6">
            <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-[0.35rem] bg-[#ffe1ea]">
              <Trash2 className="w-6 h-6 text-red-600" />
            </div>
            <h3 className="mb-2 text-center text-[1rem] font-semibold text-[#171717] md:text-[1.1rem]">
              Delete Agent
            </h3>
            <p className="mb-6 text-center text-[13px] text-[#6c655c] md:text-[14px]">
              Delete <strong className="text-[#171717]">{agentToDelete.name}</strong>? This cannot be undone.
            </p>
            <div className="flex gap-3">
              <button
                onClick={() => { setShowDeleteModal(false); setAgentToDelete(null) }}
                className="flex-1 rounded-[0.35rem] bg-white/70 px-4 py-2 text-[13px] font-medium text-[#171717] transition-colors hover:bg-white"
              >
                Cancel
              </button>
              <button
                onClick={handleDeleteAgent}
                className="flex-1 rounded-[0.35rem] bg-[#181818] px-4 py-2 text-[13px] font-medium text-white transition-colors hover:bg-black"
              >
                Delete
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
