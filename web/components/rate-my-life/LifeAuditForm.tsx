'use client'

import { useState } from 'react'
import type { DimensionAnswer } from '@/lib/api/rate-my-life'

const DIMENSIONS = [
  {
    key: 'Career & Growth',
    label: 'Career & Growth',
    question: 'How fulfilled are you with your career trajectory and professional growth?',
    low: 'Stuck / lost',
    high: 'Thriving',
  },
  {
    key: 'Financial Health',
    label: 'Financial Health',
    question: 'How secure and in control do you feel about your finances?',
    low: 'Stressed',
    high: 'Comfortable',
  },
  {
    key: 'Physical Health',
    label: 'Physical Health',
    question: 'How well are you taking care of your body, exercise, diet, sleep, energy?',
    low: 'Neglected',
    high: 'Peak form',
  },
  {
    key: 'Mental Wellbeing',
    label: 'Mental Wellbeing',
    question: 'How would you rate your stress levels, happiness, and emotional balance?',
    low: 'Struggling',
    high: 'At peace',
  },
  {
    key: 'Relationships',
    label: 'Relationships',
    question: 'How strong are your connections, partner, family, friendships, social life?',
    low: 'Isolated',
    high: 'Deep bonds',
  },
  {
    key: 'Personal Growth',
    label: 'Personal Growth',
    question: 'Are you learning, creating, and growing as a person?',
    low: 'Stagnant',
    high: 'Evolving',
  },
]

interface LifeAuditFormProps {
  onSubmit: (answers: DimensionAnswer[]) => void
  isLoading: boolean
}

export function LifeAuditForm({ onSubmit, isLoading }: LifeAuditFormProps) {
  const [answers, setAnswers] = useState<Record<string, { score: number; context: string }>>(
    Object.fromEntries(DIMENSIONS.map((d) => [d.key, { score: 5, context: '' }]))
  )
  const [step, setStep] = useState(0)

  const currentDim = DIMENSIONS[step]
  const isLast = step === DIMENSIONS.length - 1

  const updateAnswer = (field: 'score' | 'context', value: number | string) => {
    setAnswers((prev) => ({
      ...prev,
      [currentDim.key]: { ...prev[currentDim.key], [field]: value },
    }))
  }

  const handleNext = () => {
    if (isLast) {
      const result: DimensionAnswer[] = DIMENSIONS.map((d) => ({
        dimension: d.key,
        score: answers[d.key].score,
        context: answers[d.key].context,
      }))
      onSubmit(result)
    } else {
      setStep(step + 1)
    }
  }

  const handleBack = () => {
    if (step > 0) setStep(step - 1)
  }

  const current = answers[currentDim.key]

  return (
    <div className="w-full max-w-2xl mx-auto">
      {/* Progress */}
      <div className="flex items-center gap-1.5 mb-8">
        {DIMENSIONS.map((_, i) => (
          <div
            key={i}
            className={`h-1.5 flex-1 rounded-full transition-[color,background-color,border-color,box-shadow,opacity,transform] duration-300 ${
              i <= step ? 'bg-ink' : 'bg-line'
            }`}
          />
        ))}
      </div>

      {/* Step counter */}
      <div className="text-xs font-medium text-ash mb-2">
        {step + 1} of {DIMENSIONS.length}
      </div>

      {/* Question */}
      <h2 className="text-2xl font-bold text-ink mb-2">{currentDim.label}</h2>
      <p className="text-ink-soft mb-8">{currentDim.question}</p>

      {/* Slider */}
      <div className="mb-6">
        <div className="flex items-center justify-between mb-3">
          <span className="text-sm text-ink-mute">{currentDim.low}</span>
          <span className="text-4xl font-bold text-ink">{current.score}</span>
          <span className="text-sm text-ink-mute">{currentDim.high}</span>
        </div>
        <input
          type="range"
          min={1}
          max={10}
          value={current.score}
          onChange={(e) => updateAnswer('score', parseInt(e.target.value))}
          className="w-full h-2 bg-line rounded-lg appearance-none cursor-pointer accent-brand"
        />
        <div className="flex justify-between mt-1">
          {Array.from({ length: 10 }, (_, i) => (
            <span key={i} className="text-[10px] text-ash w-6 text-center">
              {i + 1}
            </span>
          ))}
        </div>
      </div>

      {/* Optional context */}
      <div className="mb-8">
        <label className="block text-sm font-medium text-ink-soft mb-2">
          Add context <span className="text-ash font-normal">(optional)</span>
        </label>
        <textarea
          value={current.context}
          onChange={(e) => updateAnswer('context', e.target.value)}
          placeholder="e.g., Just got promoted but working 60hr weeks…"
          rows={2}
          className="w-full px-4 py-3 text-sm border border-line rounded-lg focus:outline-none focus:ring-2 focus:ring-ink/20 focus:border-hotpink resize-none placeholder-ash"
        />
      </div>

      {/* Navigation */}
      <div className="flex items-center justify-between">
        <button
          onClick={handleBack}
          disabled={step === 0}
          className="px-5 py-2.5 text-sm font-medium text-ink-soft border border-line rounded-lg hover:bg-cream disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
        >
          Back
        </button>
        <button
          onClick={handleNext}
          disabled={isLoading}
          className="px-6 py-2.5 text-sm font-medium text-white bg-ink rounded-lg hover:from-danger hover:to-danger disabled:opacity-50 transition-[color,background-color,border-color,box-shadow,opacity,transform]"
        >
          {isLoading ? (
            <span className="flex items-center gap-2">
              <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full motion-safe:animate-spin" />
              Starting audit...
            </span>
          ) : isLast ? (
            'Start My Life Audit'
          ) : (
            'Next'
          )}
        </button>
      </div>
    </div>
  )
}
