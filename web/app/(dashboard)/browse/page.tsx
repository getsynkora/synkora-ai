'use client'

import { useState, useEffect, useMemo, useRef } from 'react'
import { createPortal } from 'react-dom'
import { useRouter } from 'next/navigation'
import {
  Search,
  Sparkles,
  Zap,
  Brain,
  TrendingUp,
  MessageSquare,
  Eye,
  Star,
  ChevronLeft,
  ChevronRight,
  ChevronDown,
  LayoutGrid,
  List,
  SlidersHorizontal,
  CheckCircle,
  Award,
} from 'lucide-react'
import toast from 'react-hot-toast'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5001'

// Ink-style SVG illustrations — shared with agents page
const INK = '#1c1816'
const BG = '#f3ecdf'
const WASH = '#e5dac9'

function AgentIllustration({ name }: { name: string }) {
  let h = 0
  for (let i = 0; i < name.length; i++) h = name.charCodeAt(i) + ((h << 5) - h)
  const idx = Math.abs(h) % 8
  const shared = 'absolute inset-0 h-full w-full'

  if (idx === 0) return (
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
    </svg>
  )
  return (
    <svg viewBox="0 0 400 280" fill="none" xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="xMidYMid slice" className={shared} aria-hidden>
      <rect width="400" height="280" fill={BG}/>
      <ellipse cx="200" cy="150" rx="158" ry="92" fill={WASH} opacity="0.4"/>
      <rect x="88" y="188" width="228" height="44" rx="4" fill="#ede5d6" stroke={INK} strokeWidth="1.5" opacity="0.58"/>
      <line x1="103" y1="204" x2="198" y2="204" stroke={INK} strokeWidth="1" opacity="0.32"/>
      <line x1="103" y1="215" x2="173" y2="215" stroke={INK} strokeWidth="1" opacity="0.28"/>
      <line x1="103" y1="224" x2="188" y2="224" stroke={INK} strokeWidth="1" opacity="0.28"/>
      <rect x="76" y="142" width="228" height="44" rx="4" fill="#f0e8d9" stroke={INK} strokeWidth="1.5" opacity="0.73"/>
      <line x1="91" y1="158" x2="188" y2="158" stroke={INK} strokeWidth="1" opacity="0.38"/>
      <line x1="91" y1="169" x2="162" y2="169" stroke={INK} strokeWidth="1" opacity="0.35"/>
      <line x1="91" y1="179" x2="180" y2="179" stroke={INK} strokeWidth="1" opacity="0.35"/>
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
      <path d="M55 192 Q195 186 345 192" stroke={INK} strokeWidth="2.5" strokeLinecap="round" opacity="0.65"/>
      <path d="M148 132 Q148 120 168 118 Q188 120 188 132 L188 190 L148 190 Z" fill={INK} opacity="0.12" stroke={INK} strokeWidth="1.5" strokeLinejoin="round"/>
      <line x1="153" y1="190" x2="148" y2="248" stroke={INK} strokeWidth="2" strokeLinecap="round" opacity="0.4"/>
      <line x1="183" y1="190" x2="188" y2="248" stroke={INK} strokeWidth="2" strokeLinecap="round" opacity="0.4"/>
      <line x1="140" y1="230" x2="196" y2="230" stroke={INK} strokeWidth="1.5" strokeLinecap="round" opacity="0.3"/>
      <path d="M168 158 Q155 168 152 192 Q168 195 188 192 Q185 168 172 158 Z" fill={INK} opacity="0.78"/>
      <circle cx="170" cy="142" r="20" fill={INK} opacity="0.85"/>
      <path d="M178 172 Q200 178 222 184" stroke={INK} strokeWidth="4" strokeLinecap="round" opacity="0.6"/>
      <rect x="218" y="98" width="95" height="68" rx="4" fill="#f9f5ee" stroke={INK} strokeWidth="2" opacity="0.9"/>
      <line x1="229" y1="116" x2="302" y2="116" stroke={INK} strokeWidth="1.2" opacity="0.4"/>
      <line x1="229" y1="128" x2="285" y2="128" stroke={INK} strokeWidth="1" opacity="0.32"/>
      <line x1="229" y1="139" x2="296" y2="139" stroke={INK} strokeWidth="1" opacity="0.32"/>
      <line x1="229" y1="150" x2="272" y2="150" stroke={INK} strokeWidth="1" opacity="0.28"/>
      <line x1="265" y1="166" x2="265" y2="186" stroke={INK} strokeWidth="2" strokeLinecap="round" opacity="0.45"/>
      <line x1="252" y1="187" x2="278" y2="187" stroke={INK} strokeWidth="2" strokeLinecap="round" opacity="0.45"/>
      <rect x="200" y="186" width="70" height="10" rx="2" fill="none" stroke={INK} strokeWidth="1" opacity="0.35"/>
      <circle cx="62" cy="50" r="2.5" fill={INK} opacity="0.1"/>
      <circle cx="342" cy="54" r="1.5" fill={INK} opacity="0.08"/>
      <circle cx="58" cy="244" r="1.5" fill={INK} opacity="0.08"/>
      <circle cx="348" cy="240" r="2" fill={INK} opacity="0.08"/>
      <circle cx="100" cy="88" r="1.5" fill={INK} opacity="0.1"/>
    </svg>
  )

  // idx === 7: Prism — chaos meets order
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
      <ellipse cx="148" cy="148" rx="118" ry="95" fill="#e8622a" opacity="0.11"/>
      <ellipse cx="135" cy="155" rx="95" ry="75" fill="#c0392b" opacity="0.09"/>
      <ellipse cx="158" cy="138" rx="78" ry="62" fill="#e67e22" opacity="0.08"/>
      <path d="M162 145 Q200 92 238 122 Q262 145 240 175 Q214 208 172 200 Q128 190 115 156 Q105 112 138 84 Q172 58 212 70 Q258 84 270 128" fill="none" stroke="#c0392b" strokeWidth="3.5" opacity="0.68" strokeLinecap="round"/>
      <path d="M162 145 Q188 116 208 133 Q222 147 210 164 Q194 180 172 174 Q148 166 143 148 Q138 126 154 113 Q172 100 193 110" fill="none" stroke="#c0392b" strokeWidth="2" opacity="0.48" strokeLinecap="round"/>
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
      <polygon points="65,106 73,98 71,112" fill="#e74c3c" opacity="0.55"/>
      <polygon points="68,152 76,145 74,160" fill="#c0392b" opacity="0.5"/>
      <polygon points="78,190 86,183 84,198" fill="#d35400" opacity="0.52"/>
      <polygon points="248,182 255,173 258,186" fill="#e74c3c" opacity="0.5"/>
      <polygon points="255,135 262,126 265,140" fill="#c0392b" opacity="0.55"/>
      <polygon points="247,95 254,86 257,100" fill="#d35400" opacity="0.55"/>
      <polygon points="44,92 51,85 49,98" fill="#e74c3c" opacity="0.32"/>
      <polygon points="38,146 45,138 47,152" fill="#c0392b" opacity="0.28"/>
      <circle cx="212" cy="143" r="30" fill="url(#ag-burst)"/>
      <circle cx="213" cy="166" r="18" fill="url(#ag-burst)" opacity="0.65"/>
      <circle cx="212" cy="143" r="5" fill="#00e676" opacity="0.95"/>
      <circle cx="213" cy="166" r="3.5" fill="#00e676" opacity="0.85"/>
      <line x1="212" y1="143" x2="195" y2="127" stroke="#00e676" strokeWidth="1.5" opacity="0.68"/>
      <line x1="212" y1="143" x2="231" y2="129" stroke="#00e676" strokeWidth="1.5" opacity="0.62"/>
      <line x1="212" y1="143" x2="199" y2="161" stroke="#00e676" strokeWidth="1.5" opacity="0.6"/>
      <line x1="212" y1="143" x2="227" y2="157" stroke="#00e676" strokeWidth="1.5" opacity="0.58"/>
      <circle cx="308" cy="140" r="68" fill="#f5ede0" stroke="#2c3e50" strokeWidth="2.5" opacity="0.88"/>
      <circle cx="308" cy="140" r="50" fill="none" stroke="#2c3e50" strokeWidth="1" opacity="0.3"/>
      {([
        [308,72,5,0.82],[352,93,5,0.78],[372,138,5,0.82],[354,184,5,0.78],
        [308,205,5,0.82],[262,184,5,0.78],[242,138,5,0.82],[262,93,5,0.78],
        [330,80,3.5,0.68],[362,112,3.5,0.65],[368,165,3.5,0.68],[342,196,3.5,0.65],
        [280,198,3.5,0.68],[250,165,3.5,0.65],[248,112,3.5,0.68],[278,80,3.5,0.65],
      ] as [number,number,number,number][]).map(([cx,cy,r,op],i) => (
        <circle key={i} cx={cx} cy={cy} r={r} fill="#2c3e50" opacity={op}/>
      ))}
      {([
        [308,72,352,93,1.2,0.42],[352,93,372,138,1.2,0.42],[372,138,354,184,1.2,0.42],[354,184,308,205,1.2,0.42],
        [308,205,262,184,1.2,0.42],[262,184,242,138,1.2,0.42],[242,138,262,93,1.2,0.42],[262,93,308,72,1.2,0.42],
        [308,72,330,80,0.75,0.22],[330,80,352,93,0.75,0.22],[372,138,368,165,0.75,0.22],[354,184,342,196,0.75,0.22],
        [308,205,280,198,0.75,0.22],[262,184,250,165,0.75,0.22],[242,138,248,112,0.75,0.22],[262,93,278,80,0.75,0.22],
        [308,72,308,205,0.75,0.18],[352,93,262,184,0.75,0.18],[372,138,242,138,0.75,0.18],[354,184,262,93,0.75,0.18],
        [330,80,280,198,0.75,0.18],[368,165,248,112,0.75,0.18],[342,196,278,80,0.75,0.18],
      ] as [number,number,number,number,number,number][]).map(([x1,y1,x2,y2,w,op],i) => (
        <line key={i} x1={x1} y1={y1} x2={x2} y2={y2} stroke="#2c3e50" strokeWidth={w} opacity={op}/>
      ))}
      <circle cx="293" cy="140" r="18" fill="none" stroke="#2c3e50" strokeWidth="2.5" opacity="0.75"/>
      <circle cx="323" cy="140" r="18" fill="none" stroke="#2c3e50" strokeWidth="2.5" opacity="0.75"/>
      <ellipse cx="308" cy="140" rx="7" ry="14" fill="#f5ede0"/>
      <path d="M363 122 Q390 108 400 102" stroke="#1abc9c" strokeWidth="3.5" opacity="0.72" strokeLinecap="round"/>
      <path d="M371 136 Q398 132 400 130" stroke="#1abc9c" strokeWidth="5" opacity="0.82" strokeLinecap="round"/>
      <path d="M371 145 Q398 149 400 151" stroke="#1abc9c" strokeWidth="4" opacity="0.75" strokeLinecap="round"/>
      <path d="M363 158 Q390 170 400 176" stroke="#1abc9c" strokeWidth="3" opacity="0.65" strokeLinecap="round"/>
      <path d="M354 172 Q382 188 400 196" stroke="#1abc9c" strokeWidth="2" opacity="0.48" strokeLinecap="round"/>
    </svg>
  )
}

const SORT_OPTIONS = [
  { value: 'popular', label: 'Most Popular' },
  { value: 'recent', label: 'Recently Added' },
  { value: 'rating', label: 'Highest Rated' },
  { value: 'name', label: 'Name (A-Z)' },
] as const

type SortBy = 'popular' | 'recent' | 'rating' | 'name'

function SortDropdown({ value, onChange }: { value: SortBy; onChange: (v: SortBy) => void }) {
  const [open, setOpen] = useState(false)
  const [anchorRect, setAnchorRect] = useState<DOMRect | null>(null)
  const btnRef = useRef<HTMLButtonElement>(null)
  const menuRef = useRef<HTMLDivElement>(null)
  const selected = SORT_OPTIONS.find((o) => o.value === value)!

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
        aria-label="Sort by"
        className="flex w-full items-center justify-between rounded-[0.35rem] border border-black/10 bg-white/[0.78] px-4 py-3 text-[13px] text-[#171717] outline-none transition-all focus:border-[#ff5f8f] focus:ring-2 focus:ring-[#ff5f8f]/20 md:text-[14px]"
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
          {SORT_OPTIONS.map((opt) => (
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

interface AgentPricing {
  model: string
  is_free: boolean
  credits_per_use?: number | null
  session_credits?: number | null
  daily_credits?: number | null
  weekly_credits?: number | null
  monthly_credits?: number | null
  trial_messages: number
}

interface PublicAgent {
  id: string
  agent_name: string
  description: string
  avatar?: string
  category: string
  tags: string[]
  likes_count: number
  dislikes_count: number
  usage_count: number
  model_name: string
  created_at: string
  user_rating?: 'like' | 'dislike' | null
  system_prompt?: string
  tools?: any[]
  provider?: string
  pricing?: AgentPricing | null
}

interface Category {
  category: string
  count: number
}

// Get icon based on category
const getCategoryIcon = (category: string, size: number = 32) => {
  const icons: Record<string, any> = {
    Productivity: Zap,
    Research: Search,
    Development: Brain,
    Writing: Eye,
    'Data Analysis': TrendingUp,
    'Customer Support': MessageSquare,
    Education: Star,
    Entertainment: Sparkles,
    Other: Sparkles,
  }
  const Icon = icons[category] || Sparkles
  return <Icon size={size} />
}

// Get rating from likes/dislikes
const getRating = (agent: PublicAgent) => {
  const total = agent.likes_count + agent.dislikes_count
  if (total === 0) return 4.5
  const ratio = agent.likes_count / total
  return Math.round((3 + ratio * 2) * 10) / 10
}

// Get badge type based on agent properties
const getBadge = (agent: PublicAgent) => {
  const rating = getRating(agent)
  if (rating >= 4.9) return { type: 'top_rated', label: 'TOP RATED' }
  if (agent.usage_count > 100) return { type: 'verified', label: 'VERIFIED' }
  return null
}

// Format pricing for display
const formatPricing = (pricing?: AgentPricing | null): { label: string; sub: string } => {
  if (!pricing || pricing.is_free || pricing.model === 'FREE') {
    return { label: 'Free', sub: '' }
  }
  switch (pricing.model) {
    case 'PER_USE':
      return { label: `${pricing.credits_per_use ?? '?'} cr`, sub: '/use' }
    case 'SESSION':
      return { label: `${pricing.session_credits ?? '?'} cr`, sub: '/session' }
    case 'DAILY':
      return { label: `${pricing.daily_credits ?? '?'} cr`, sub: '/day' }
    case 'WEEKLY':
      return { label: `${pricing.weekly_credits ?? '?'} cr`, sub: '/week' }
    case 'SUBSCRIPTION':
    case 'MONTHLY':
      return { label: `${pricing.monthly_credits ?? '?'} cr`, sub: '/mo' }
    default:
      return { label: 'Free', sub: '' }
  }
}

// Main categories from agent creation
const mainCategories = [
  'Productivity',
  'Research',
  'Development',
  'Writing',
  'Data Analysis',
  'Customer Support',
  'Education',
  'Entertainment',
  'Other',
]

export default function BrowsePage() {
  const router = useRouter()
  const [agents, setAgents] = useState<PublicAgent[]>([])
  const [categories, setCategories] = useState<Category[]>([])
  const [loading, setLoading] = useState(true)
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedCategory, setSelectedCategory] = useState<string>('')
  const [sortBy, setSortBy] = useState<SortBy>('popular')
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid')
  const [selectedTags, setSelectedTags] = useState<string[]>([])
  const [currentPage, setCurrentPage] = useState(1)
  const itemsPerPage = 9

  useEffect(() => {
    const fetchCategories = async () => {
      try {
        const response = await fetch(`${API_URL}/api/v1/agents/categories`)
        const data = await response.json()
        if (data.success) {
          const normalized = (data.data.categories || []).map((c: any) => ({
            category: c.category || c.name,
            count: c.count ?? 0,
          }))
          setCategories(normalized)
        }
      } catch (error) {
        console.error('Failed to fetch categories:', error)
      }
    }

    const fetchAgents = async () => {
      setLoading(true)
      try {
        const params = new URLSearchParams()
        if (selectedCategory) params.append('category', selectedCategory)
        if (searchQuery) params.append('search', searchQuery)
        if (sortBy) params.append('sort_by', sortBy)
        params.append('limit', '50')

        const response = await fetch(`${API_URL}/api/v1/agents/public?${params}`)
        const data = await response.json()
        if (data.success) {
          setAgents(data.data.agents)
        }
      } catch (error) {
        console.error('Failed to fetch agents:', error)
        toast.error('Failed to load agents')
      } finally {
        setLoading(false)
      }
    }

    void fetchCategories()
    void fetchAgents()
  }, [selectedCategory, sortBy, searchQuery])

  useEffect(() => {
    setCurrentPage(1)
  }, [selectedCategory, sortBy, searchQuery, selectedTags])

  const clearAllFilters = () => {
    setSelectedCategory('')
    setSelectedTags([])
    setSearchQuery('')
    setCurrentPage(1)
  }

  const toggleTag = (tag: string) => {
    setSelectedTags((prev) =>
      prev.includes(tag) ? prev.filter((t) => t !== tag) : [...prev, tag]
    )
  }

  // Extract all unique tags from agents
  const availableTags = useMemo(() => {
    const tagSet = new Set<string>()
    agents.forEach((agent) => {
      agent.tags?.forEach((tag) => tagSet.add(tag))
    })
    return Array.from(tagSet).slice(0, 10) // Limit to 10 tags
  }, [agents])

  // Filtered and paginated agents
  const filteredAgents = useMemo(() => {
    let result = [...agents]
    if (selectedTags.length > 0) {
      result = result.filter((a) =>
        selectedTags.some((tag) => a.tags?.includes(tag))
      )
    }
    return result
  }, [agents, selectedTags])

  const totalPages = Math.ceil(filteredAgents.length / itemsPerPage)
  const paginatedAgents = useMemo(() => {
    const start = (currentPage - 1) * itemsPerPage
    return filteredAgents.slice(start, start + itemsPerPage)
  }, [filteredAgents, currentPage])

  // Use main categories for the sidebar
  const displayCategories = mainCategories
  const categoryCountMap = useMemo(
    () => new Map(categories.map((item) => [item.category, item.count])),
    [categories]
  )
  const hasActiveFilters = Boolean(searchQuery || selectedCategory || selectedTags.length)

  return (
    <div className="dashboard-app min-h-full px-4 py-4 md:px-8 md:py-6 xl:px-10">
      <div className="mx-auto max-w-[90rem]">
        <div className="dashboard-surface mb-4 px-5 py-3">
          <nav className="flex items-center gap-2 text-sm text-[#7a736a]">
            <button onClick={() => router.push('/')} className="transition-colors hover:text-[#171717]">
              Home
            </button>
            <ChevronRight size={14} className="text-[#9a9388]" />
            <button onClick={() => router.push('/browse')} className="transition-colors hover:text-[#171717]">
              Marketplace
            </button>
            {selectedCategory && (
              <>
                <ChevronRight size={14} className="text-[#9a9388]" />
                <span className="font-medium text-[#171717]">{selectedCategory}</span>
              </>
            )}
          </nav>
        </div>

        <div className="dashboard-surface mb-6 p-5 md:p-6 xl:p-7">
          <div className="flex flex-col gap-6 xl:flex-row xl:items-end xl:justify-between">
            <div>
              <div className="mb-3 inline-flex items-center gap-2 rounded-[0.35rem] border border-black/10 bg-white/70 px-3.5 py-1.5 text-[11px] font-semibold uppercase tracking-[0.18em] text-[#6e675d]">
                <Sparkles className="h-3 w-3 text-[#2d8b69]" />
                Marketplace Access
              </div>
              <h1 className="text-[1.8rem] font-semibold tracking-[-0.05em] text-[#171717] md:text-[2.65rem]">
                {selectedCategory ? (
                  <>
                    <span className="highlight-mint">{selectedCategory}</span> agents
                  </>
                ) : (
                  <>
                    Browse <span className="highlight-mint">AI agents</span>
                  </>
                )}
              </h1>
              <p className="mt-3 max-w-3xl text-[13px] leading-relaxed text-[#5b564e] md:text-[15px]">
                Discover marketplace agents with clearer pricing, stronger trust signals, and cleaner category navigation. Deploy the right specialist without digging through clutter.
              </p>
            </div>

            <button
              onClick={clearAllFilters}
              className="inline-flex flex-shrink-0 items-center gap-2 rounded-[0.35rem] border border-black/10 bg-white/[0.78] px-5 py-3 text-[13px] font-medium text-[#171717] transition-colors hover:bg-white md:text-[14px]"
            >
              <SlidersHorizontal size={16} />
              Clear Filters
            </button>
          </div>

          <div className="mt-5 flex flex-wrap gap-3">
            <div className="dashboard-chip px-4 py-2 text-[13px] font-medium">{filteredAgents.length} visible</div>
            <div className="dashboard-chip px-4 py-2 text-[13px] font-medium">{displayCategories.length} categories</div>
            <div className="dashboard-chip px-4 py-2 text-[13px] font-medium">{availableTags.length} tags</div>
            <div className="dashboard-chip px-4 py-2 text-[13px] font-medium">{viewMode === 'grid' ? 'Grid view' : 'List view'}</div>
          </div>

          <div className="mt-5 grid gap-3 md:grid-cols-[minmax(0,1fr)_220px_auto]">
            <label className="relative block">
              <Search className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-[#8a8378]" />
              <input
                type="text"
                placeholder="Search agents, tools, or use cases..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full rounded-[0.35rem] border border-black/10 bg-white/[0.78] py-3 pl-11 pr-4 text-[13px] text-[#171717] outline-none transition-all focus:border-[#ff5f8f] focus:ring-2 focus:ring-[#ff5f8f]/20 md:text-[14px]"
              />
            </label>

            <SortDropdown value={sortBy} onChange={setSortBy} />

            <div className="flex items-center rounded-[0.35rem] border border-black/10 bg-white/[0.78] p-1">
              <button
                onClick={() => setViewMode('grid')}
                className={`flex h-10 w-10 items-center justify-center rounded-[0.35rem] transition-colors ${
                  viewMode === 'grid' ? 'bg-[#181818] text-[#f7f2e7]' : 'text-[#6f685e] hover:bg-black/5'
                }`}
                aria-label="Grid view"
              >
                <LayoutGrid size={18} />
              </button>
              <button
                onClick={() => setViewMode('list')}
                className={`flex h-10 w-10 items-center justify-center rounded-[0.35rem] transition-colors ${
                  viewMode === 'list' ? 'bg-[#181818] text-[#f7f2e7]' : 'text-[#6f685e] hover:bg-black/5'
                }`}
                aria-label="List view"
              >
                <List size={18} />
              </button>
            </div>
          </div>
        </div>

        <div className="grid gap-6 xl:grid-cols-[248px_minmax(0,1fr)]">
          <aside className="dashboard-surface p-3 md:p-4 xl:sticky xl:top-24 xl:h-fit">
            <div className="mb-4">
              <p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.16em] text-[#8a8378]">Categories</p>
              <div className="space-y-1">
                {displayCategories.map((cat) => {
                  const isActive = selectedCategory === cat
                  return (
                    <button
                      key={cat}
                      onClick={() => setSelectedCategory(isActive ? '' : cat)}
                      className={`relative flex w-full items-center gap-2 overflow-hidden rounded-[0.35rem] px-2 py-2 text-left transition-all ${
                        isActive
                          ? 'border border-black/10 bg-white/[0.82] text-[#171717] shadow-sm'
                          : 'text-[#5b564e] hover:bg-white/[0.62] hover:text-[#171717]'
                      }`}
                    >
                      {isActive && (
                        <span className="absolute left-0 top-1/2 h-5 w-1 -translate-y-1/2 rounded-r-[0.35rem] bg-[#63dfbe]" aria-hidden="true" />
                      )}
                      <span className={`flex h-7 w-7 items-center justify-center rounded-[0.35rem] ${isActive ? 'bg-[#181818] text-[#f7f2e7]' : 'bg-white/80 text-[#8a8378]'}`}>
                        {getCategoryIcon(cat, 14)}
                      </span>
                      <span className="flex-1 text-[13px] font-medium leading-none">{cat}</span>
                      <span className="text-[10px] font-semibold uppercase tracking-[0.06em] text-[#8a8378]">
                        {categoryCountMap.get(cat) ?? 0}
                      </span>
                    </button>
                  )
                })}
              </div>
            </div>

            {availableTags.length > 0 && (
              <>
                <div className="mb-3 border-t border-black/[0.08]" />
                <div>
                  <p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.16em] text-[#8a8378]">Tags</p>
                  <div className="flex flex-wrap gap-1.5">
                    {availableTags.map((tag) => {
                      const isSelected = selectedTags.includes(tag)
                      return (
                        <button
                          key={tag}
                          onClick={() => toggleTag(tag)}
                          className={`rounded-[0.35rem] px-2.5 py-1.5 text-[11px] font-medium transition-colors ${
                            isSelected
                              ? 'bg-[#181818] text-[#f7f2e7]'
                              : 'border border-black/10 bg-white/70 text-[#5b564e] hover:bg-white'
                          }`}
                        >
                          {tag}
                        </button>
                      )
                    })}
                  </div>
                </div>
              </>
            )}
          </aside>

          <section className="min-w-0">
            <div className="mb-5 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
              <div>
                <p className="text-[13px] uppercase tracking-[0.18em] text-[#8a8378]">Results</p>
                <p className="mt-1 text-[15px] text-[#5b564e]">
                  Showing <span className="font-semibold text-[#171717]">{filteredAgents.length}</span> marketplace agents
                  {selectedCategory && <> in <span className="font-semibold text-[#171717]">{selectedCategory}</span></>}
                </p>
              </div>

              {hasActiveFilters && (
                <div className="flex flex-wrap gap-2">
                  {selectedCategory && (
                    <span className="rounded-[0.35rem] border border-black/10 bg-white/70 px-3 py-2 text-xs font-medium text-[#171717]">
                      {selectedCategory}
                    </span>
                  )}
                  {selectedTags.map((tag) => (
                    <span key={tag} className="rounded-[0.35rem] border border-black/10 bg-white/70 px-3 py-2 text-xs font-medium text-[#171717]">
                      {tag}
                    </span>
                  ))}
                  {searchQuery && (
                    <span className="rounded-[0.35rem] border border-black/10 bg-white/70 px-3 py-2 text-xs font-medium text-[#171717]">
                      {searchQuery}
                    </span>
                  )}
                </div>
              )}
            </div>

            {loading ? (
              <div className={viewMode === 'grid' ? 'grid grid-cols-1 gap-6 md:grid-cols-2 xl:grid-cols-3' : 'space-y-4'}>
                {Array.from({ length: 6 }).map((_, i) => (
                  <div key={i} className="dashboard-panel animate-pulse overflow-hidden">
                    <div className="border-b border-black/10 bg-[#efe7d8] pt-10 pb-12">
                      <div className="mx-auto h-24 w-24 rounded-[0.45rem] bg-white shadow-lg" />
                    </div>
                    <div className="p-5">
                      <div className="mb-2 h-5 w-40 rounded bg-black/10" />
                      <div className="mb-3 h-4 w-24 rounded bg-black/5" />
                      <div className="mb-2 h-4 w-full rounded bg-black/5" />
                      <div className="mb-4 h-4 w-3/4 rounded bg-black/5" />
                      <div className="mb-4 border-t border-black/10 pt-4">
                        <div className="flex gap-6">
                          <div className="h-8 w-12 rounded bg-black/10" />
                          <div className="h-8 w-12 rounded bg-black/10" />
                        </div>
                      </div>
                      <div className="h-10 w-32 rounded-[0.35rem] bg-black/5" />
                    </div>
                  </div>
                ))}
              </div>
            ) : paginatedAgents.length === 0 ? (
              <div className="dashboard-surface py-20 text-center">
                <div className="mx-auto mb-4 flex h-20 w-20 items-center justify-center rounded-[0.45rem] bg-[#f1eadc] text-[#171717]">
                  <Search className="h-8 w-8" />
                </div>
                <h3 className="mb-2 text-[1.05rem] font-semibold text-[#171717] md:text-[1.35rem]">No matching agents</h3>
                <p className="mb-6 text-[13px] text-[#6c655c] md:text-[14px]">
                  Try clearing filters or broadening your search terms.
                </p>
                <button
                  onClick={clearAllFilters}
                  className="inline-flex items-center gap-2 rounded-[0.35rem] bg-[#181818] px-6 py-3 text-[13px] font-medium text-[#f7f2e7] transition-transform hover:-translate-y-0.5 md:text-[14px]"
                >
                  Reset Filters
                </button>
              </div>
            ) : (
              <div className={viewMode === 'grid' ? 'grid grid-cols-1 gap-6 md:grid-cols-2 xl:grid-cols-3' : 'space-y-4'}>
                {paginatedAgents.map((agent) => {
                  const badge = getBadge(agent)
                  const rating = getRating(agent)
                  const price = formatPricing(agent.pricing)

                  if (viewMode === 'list') {
                    return (
                      <div
                        key={agent.id}
                        onClick={() => router.push(`/browse/${agent.id}`)}
                        className="dashboard-panel flex cursor-pointer flex-col gap-5 p-5 transition-all duration-300 hover:-translate-y-1 md:flex-row md:items-center"
                      >
                        <div className="relative flex h-40 items-center justify-center overflow-hidden rounded-[0.45rem] border border-black/10 bg-[linear-gradient(180deg,#efe7d8_0%,#f3ecdf_100%)] md:h-48 md:w-56">
                          {agent.avatar ? (
                            <>
                              <img
                                src={agent.avatar}
                                alt={agent.agent_name}
                                className="absolute inset-0 h-full w-full object-cover object-center"
                              />
                              <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_50%_24%,rgba(255,255,255,0.22),transparent_42%)]" />
                              <div className="pointer-events-none absolute inset-0 bg-[linear-gradient(180deg,rgba(243,236,223,0.08),rgba(243,236,223,0.04)_45%,rgba(255,255,255,0.1))]" />
                            </>
                          ) : (
                          <AgentIllustration name={agent.agent_name} />
                        )}
                        </div>

                        <div className="min-w-0 flex-1">
                          <div className="mb-2 flex flex-wrap items-center gap-2">
                            {badge && (
                              <span className={`inline-flex items-center gap-1 rounded-[0.35rem] px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.16em] ${
                                badge.type === 'top_rated'
                                  ? 'bg-[#fff0d9] text-[#171717]'
                                  : 'bg-[rgba(99,223,190,0.18)] text-[#171717]'
                              }`}>
                                {badge.type === 'verified' && <CheckCircle size={12} />}
                                {badge.type === 'top_rated' && <Award size={12} />}
                                {badge.label}
                              </span>
                            )}
                            <span className="rounded-[0.35rem] border border-black/10 bg-white/70 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-[#5b564e]">
                              {agent.category || 'General'}
                            </span>
                          </div>

                          <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                            <div className="min-w-0">
                              <h3 className="line-clamp-1 text-[1.35rem] font-semibold tracking-[-0.04em] text-[#171717]">
                                {agent.agent_name}
                              </h3>
                              <p className="mt-2 line-clamp-2 text-[14px] leading-relaxed text-[#5b564e]">
                                {agent.description || 'AI agent for your business needs.'}
                              </p>
                            </div>

                            <div className="flex items-center gap-5 lg:ml-6 lg:flex-col lg:items-end lg:text-right">
                              <div className="flex items-center gap-1 text-[#b7832f]">
                                <Star size={16} fill="currentColor" />
                                <span className="text-sm font-semibold text-[#171717]">{rating.toFixed(1)}</span>
                              </div>
                              <div>
                                <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[#8a8378]">
                                  {price.label === 'Free' ? 'Access' : 'Starting at'}
                                </p>
                                <p className="text-lg font-semibold text-[#171717]">
                                  {price.label}
                                  {price.sub && <span className="ml-1 text-sm font-medium text-[#7a736a]">{price.sub}</span>}
                                </p>
                              </div>
                            </div>
                          </div>

                          <div className="mt-5 flex items-center justify-between gap-4 border-t border-black/10 pt-4">
                            <div className="flex items-center gap-6">
                              <div>
                                <p className="text-xs uppercase tracking-[0.16em] text-[#8a8378]">Uses</p>
                                <p className="text-lg font-semibold text-[#171717]">{agent.usage_count}</p>
                              </div>
                              <div>
                                <p className="text-xs uppercase tracking-[0.16em] text-[#8a8378]">Likes</p>
                                <p className="text-lg font-semibold text-[#171717]">{agent.likes_count}</p>
                              </div>
                            </div>

                            <button className="rounded-[0.35rem] bg-[#181818] px-5 py-2.5 text-sm font-semibold uppercase tracking-[0.14em] text-[#f7f2e7] transition-transform hover:-translate-y-0.5">
                              View Details
                            </button>
                          </div>
                        </div>
                      </div>
                    )
                  }

                  return (
                    <div
                      key={agent.id}
                      onClick={() => router.push(`/browse/${agent.id}`)}
                      className="dashboard-panel group flex cursor-pointer flex-col overflow-hidden transition-all duration-300 hover:-translate-y-1"
                    >
                      <div className="relative flex min-h-[16rem] items-center justify-center overflow-hidden border-b border-black/10 bg-[linear-gradient(180deg,#efe7d8_0%,#f3ecdf_100%)] md:min-h-[18.5rem]">
                        {badge && (
                          <span className={`absolute left-4 top-4 inline-flex items-center gap-1 rounded-[0.35rem] px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.16em] ${
                            badge.type === 'top_rated'
                              ? 'bg-[#fff0d9] text-[#171717]'
                              : 'bg-[rgba(99,223,190,0.18)] text-[#171717]'
                          }`}>
                            {badge.type === 'verified' && <CheckCircle size={12} />}
                            {badge.type === 'top_rated' && <Award size={12} />}
                            {badge.label}
                          </span>
                        )}

                        <div className="absolute right-4 top-4 rounded-[0.35rem] border border-black/10 bg-white/78 px-3 py-1.5 text-[11px] font-semibold uppercase tracking-[0.16em] text-[#171717]">
                          {price.label}
                          {price.sub && <span className="ml-1 font-medium text-[#7a736a]">{price.sub}</span>}
                        </div>

                        {agent.avatar ? (
                          <>
                            <img
                              src={agent.avatar}
                              alt={agent.agent_name}
                              className="absolute inset-0 h-full w-full object-cover object-center"
                            />
                            <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_50%_24%,rgba(255,255,255,0.22),transparent_42%)]" />
                            <div className="pointer-events-none absolute inset-0 bg-[linear-gradient(180deg,rgba(243,236,223,0.08),rgba(243,236,223,0.04)_45%,rgba(255,255,255,0.1))]" />
                          </>
                        ) : (
                          <AgentIllustration name={agent.agent_name} />
                        )}
                      </div>

                      <div className="flex flex-1 flex-col p-5">
                        <div className="mb-2 flex items-start justify-between gap-3">
                          <div>
                            <h3 className="line-clamp-2 text-[1.3rem] font-semibold leading-tight tracking-[-0.04em] text-[#171717]">
                              {agent.agent_name}
                            </h3>
                            <p className="mt-2 text-[12px] uppercase tracking-[0.16em] text-[#7a736a]">
                              {agent.category || 'General'}
                            </p>
                          </div>

                          <div className="flex items-center gap-1 text-[#b7832f]">
                            <Star size={15} fill="currentColor" />
                            <span className="text-sm font-semibold text-[#171717]">{rating.toFixed(1)}</span>
                          </div>
                        </div>

                        <p className="mb-4 line-clamp-2 text-[14px] leading-relaxed text-[#5b564e]">
                          {agent.description || 'AI agent for your business needs.'}
                        </p>

                        {agent.tags?.length > 0 && (
                          <div className="mb-4 flex flex-wrap gap-2">
                            {agent.tags.slice(0, 2).map((tag) => (
                              <span key={tag} className="rounded-[0.35rem] border border-black/10 bg-white/70 px-3 py-1 text-[11px] font-medium text-[#5b564e]">
                                {tag}
                              </span>
                            ))}
                          </div>
                        )}

                        <div className="mb-5 border-t border-black/10 pt-4">
                          <div className="flex items-center gap-6">
                            <div>
                              <p className="mb-0.5 text-xs uppercase tracking-[0.16em] text-[#8a8378]">Uses</p>
                              <p className="text-xl font-semibold text-[#171717]">{agent.usage_count}</p>
                            </div>
                            <div>
                              <p className="mb-0.5 text-xs uppercase tracking-[0.16em] text-[#8a8378]">Likes</p>
                              <p className="text-xl font-semibold text-[#171717]">{agent.likes_count}</p>
                            </div>
                          </div>
                        </div>

                        <button className="mt-auto rounded-[0.35rem] border border-black/15 bg-white/70 px-5 py-2.5 text-center text-sm font-semibold uppercase tracking-[0.14em] text-[#171717] transition-colors hover:bg-white">
                          View Details
                        </button>
                      </div>
                    </div>
                  )
                })}
              </div>
            )}

            {totalPages > 1 && (
              <div className="dashboard-surface mt-8 flex items-center justify-center gap-3 px-4 py-3">
                <button
                  onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                  disabled={currentPage === 1}
                  className="flex h-10 w-10 items-center justify-center rounded-[0.35rem] text-[#5b564e] transition-colors hover:bg-black/5 disabled:cursor-not-allowed disabled:opacity-50"
                  aria-label="Previous page"
                >
                  <ChevronLeft size={18} />
                </button>

                {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                  let pageNum: number
                  if (totalPages <= 5) {
                    pageNum = i + 1
                  } else if (currentPage <= 3) {
                    pageNum = i + 1
                  } else if (currentPage >= totalPages - 2) {
                    pageNum = totalPages - 4 + i
                  } else {
                    pageNum = currentPage - 2 + i
                  }

                  return (
                    <button
                      key={pageNum}
                      onClick={() => setCurrentPage(pageNum)}
                      className={`flex h-10 w-10 items-center justify-center rounded-[0.35rem] text-sm font-semibold transition-colors ${
                        currentPage === pageNum
                          ? 'bg-[#181818] text-[#f7f2e7]'
                          : 'text-[#5b564e] hover:bg-black/5'
                      }`}
                    >
                      {pageNum}
                    </button>
                  )
                })}

                {totalPages > 5 && currentPage < totalPages - 2 && (
                  <>
                    <span className="text-[#8a8378]">...</span>
                    <button
                      onClick={() => setCurrentPage(totalPages)}
                      className="flex h-10 w-10 items-center justify-center rounded-[0.35rem] text-sm font-semibold text-[#5b564e] transition-colors hover:bg-black/5"
                    >
                      {totalPages}
                    </button>
                  </>
                )}

                <button
                  onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                  disabled={currentPage === totalPages}
                  className="flex h-10 w-10 items-center justify-center rounded-[0.35rem] text-[#5b564e] transition-colors hover:bg-black/5 disabled:cursor-not-allowed disabled:opacity-50"
                  aria-label="Next page"
                >
                  <ChevronRight size={18} />
                </button>
              </div>
            )}
          </section>
        </div>
      </div>
    </div>
  )
}
