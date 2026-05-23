'use client'

import { useEffect, useMemo, useState } from 'react'
import { CheckCircle2, Loader2, Paperclip, Upload } from 'lucide-react'
import { cn } from '@/lib/utils'
import { useFileUpload } from '../hooks/useFileUpload'
import { Attachment, FormDefinition, FormField } from '../types'

interface InteractiveFormCardProps {
  form: FormDefinition
  conversationId?: string
  onSubmit?: (form: FormDefinition, answers: Record<string, unknown>, attachments?: Attachment[]) => Promise<void> | void
  disabled?: boolean
  primaryColor?: string
}

type UploadMap = Record<string, Attachment[]>

function buildInitialValues(form: FormDefinition): Record<string, unknown> {
  return form.fields.reduce<Record<string, unknown>>((acc, field) => {
    if (field.default_value !== undefined) {
      acc[field.id] = field.default_value
    } else if (field.type === 'checkbox_group') {
      acc[field.id] = []
    } else if (field.type === 'boolean') {
      acc[field.id] = null
    } else {
      acc[field.id] = ''
    }
    return acc
  }, {})
}

function normalizeUploadAnswer(attachments: Attachment[]): Array<Record<string, unknown>> {
  return attachments.map((attachment) => ({
    file_id: attachment.file_id,
    file_name: attachment.file_name,
    file_type: attachment.file_type,
    file_url: attachment.file_url,
  }))
}

function validateField(field: FormField, value: unknown, uploadedFiles?: Attachment[]): string | null {
  if (!field.required) return null

  if (field.type === 'checkbox_group') {
    return Array.isArray(value) && value.length > 0 ? null : 'Select at least one option.'
  }

  if (field.type === 'image_upload' || field.type === 'file_upload') {
    return uploadedFiles && uploadedFiles.length > 0 ? null : 'Upload at least one file.'
  }

  if (field.type === 'boolean') {
    return typeof value === 'boolean' ? null : 'Choose Yes or No.'
  }

  return String(value ?? '').trim() ? null : 'This field is required.'
}

function formatFieldLabel(field: FormField): string {
  return field.required ? `${field.label} *` : field.label
}

export function InteractiveFormCard({
  form,
  conversationId,
  onSubmit,
  disabled = false,
  primaryColor = '#0d9488',
}: InteractiveFormCardProps) {
  const initialValues = useMemo(() => buildInitialValues(form), [form])
  const [values, setValues] = useState<Record<string, unknown>>(initialValues)
  const [uploadedFiles, setUploadedFiles] = useState<UploadMap>({})
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [submitError, setSubmitError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [hasSubmitted, setHasSubmitted] = useState(form.status === 'submitted')
  const { uploadFiles, uploadProgress, isUploading, clearProgress } = useFileUpload()

  useEffect(() => {
    setValues(initialValues)
    setUploadedFiles({})
    setErrors({})
    setSubmitError(null)
    setHasSubmitted(form.status === 'submitted')
    clearProgress()
  }, [form.form_id, form.status, initialValues]) // eslint-disable-line react-hooks/exhaustive-deps

  const isDisabled = disabled || hasSubmitted || isSubmitting || isUploading

  const handleValueChange = (fieldId: string, value: unknown) => {
    setValues((prev) => ({ ...prev, [fieldId]: value }))
    setErrors((prev) => {
      if (!prev[fieldId]) return prev
      const next = { ...prev }
      delete next[fieldId]
      return next
    })
  }

  const handleCheckboxGroupChange = (fieldId: string, optionValue: string, checked: boolean) => {
    const currentValue = Array.isArray(values[fieldId]) ? (values[fieldId] as string[]) : []
    const nextValue = checked
      ? [...currentValue, optionValue]
      : currentValue.filter((item) => item !== optionValue)
    handleValueChange(fieldId, nextValue)
  }

  const handleUpload = async (field: FormField, files: FileList | null) => {
    if (!files || files.length === 0) return
    if (!conversationId) {
      setSubmitError('Uploads are available after the conversation starts.')
      return
    }

    const selectedFiles = Array.from(files)
    const maxFiles = field.max_files || 1
    const currentFiles = uploadedFiles[field.id] || []
    if (currentFiles.length + selectedFiles.length > maxFiles) {
      setSubmitError(`"${field.label}" allows up to ${maxFiles} file${maxFiles === 1 ? '' : 's'}.`)
      return
    }

    try {
      setSubmitError(null)
      const attachments = await uploadFiles(selectedFiles, conversationId)
      setUploadedFiles((prev) => ({
        ...prev,
        [field.id]: [...(prev[field.id] || []), ...attachments],
      }))
      setErrors((prev) => {
        if (!prev[field.id]) return prev
        const next = { ...prev }
        delete next[field.id]
        return next
      })
    } catch (error) {
      setSubmitError(error instanceof Error ? error.message : 'Failed to upload files.')
    }
  }

  const removeUploadedFile = (fieldId: string, index: number) => {
    setUploadedFiles((prev) => ({
      ...prev,
      [fieldId]: (prev[fieldId] || []).filter((_, itemIndex) => itemIndex !== index),
    }))
  }

  const handleSubmit = async () => {
    if (!onSubmit || isDisabled) return

    const nextErrors: Record<string, string> = {}
    const answers: Record<string, unknown> = {}
    const attachments: Attachment[] = []

    for (const field of form.fields) {
      const uploaded = uploadedFiles[field.id]
      let value: unknown
      if (field.type === 'image_upload' || field.type === 'file_upload') {
        value = normalizeUploadAnswer(uploaded || [])
      } else if ((field.type === 'number' || field.type === 'scale') && values[field.id] !== '') {
        value = Number(values[field.id])
      } else {
        value = values[field.id]
      }

      const validationError = validateField(field, value, uploaded)
      if (validationError) {
        nextErrors[field.id] = validationError
      }

      answers[field.id] = value
      if (uploaded?.length) {
        attachments.push(...uploaded)
      }
    }

    if (Object.keys(nextErrors).length > 0) {
      setErrors(nextErrors)
      return
    }

    setIsSubmitting(true)
    setSubmitError(null)
    try {
      await onSubmit(form, answers, attachments.length > 0 ? attachments : undefined)
      setHasSubmitted(true)
    } catch (error) {
      setSubmitError(error instanceof Error ? error.message : 'Failed to submit form.')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="mt-4 rounded-[1.35rem] border border-slate-200/80 bg-[linear-gradient(180deg,rgba(255,255,255,0.98),rgba(247,248,250,0.96))] p-4 shadow-[0_20px_50px_-34px_rgba(15,23,42,0.3)]">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="inline-flex items-center rounded-full border border-slate-200 bg-white px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">
            Interactive Input
          </div>
          <h3 className="mt-3 text-base font-semibold tracking-[-0.03em] text-slate-900">{form.title}</h3>
          {form.description && (
            <p className="mt-1 text-sm leading-6 text-slate-600">{form.description}</p>
          )}
        </div>
        {hasSubmitted && (
          <div className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 px-2.5 py-1 text-xs font-medium text-emerald-700">
            <CheckCircle2 size={14} />
            Submitted
          </div>
        )}
      </div>

      <div className="mt-4 space-y-4">
        {form.fields.map((field) => {
          const fieldError = errors[field.id]
          const uploaded = uploadedFiles[field.id] || []

          return (
            <div key={field.id} className="rounded-2xl border border-slate-200/80 bg-white/90 p-3.5">
              <label className="block text-sm font-semibold text-slate-800">{formatFieldLabel(field)}</label>
              {field.description && (
                <p className="mt-1 text-xs leading-5 text-slate-500">{field.description}</p>
              )}

              <div className="mt-3">
                <FormFieldInput
                  field={field}
                  value={values[field.id]}
                  uploadedFiles={uploaded}
                  disabled={isDisabled}
                  primaryColor={primaryColor}
                  onChange={handleValueChange}
                  onCheckboxGroupChange={handleCheckboxGroupChange}
                  onUpload={handleUpload}
                  onRemoveUploadedFile={removeUploadedFile}
                />
              </div>

              {field.help_text && (
                <p className="mt-2 text-xs text-slate-500">{field.help_text}</p>
              )}
              {fieldError && (
                <p className="mt-2 text-xs font-medium text-rose-600">{fieldError}</p>
              )}
            </div>
          )
        })}
      </div>

      {uploadProgress.length > 0 && (
        <div className="mt-4 rounded-2xl border border-slate-200 bg-white px-3.5 py-3">
          <div className="space-y-2">
            {uploadProgress.map((item) => (
              <div key={item.fileId} className="flex items-center gap-3 text-xs text-slate-600">
                <span className="min-w-0 flex-1 truncate">{item.fileName}</span>
                <div className="h-1.5 w-24 overflow-hidden rounded-full bg-slate-200">
                  <div
                    className="h-full rounded-full transition-all"
                    style={{ width: `${item.progress}%`, backgroundColor: primaryColor }}
                  />
                </div>
                <span className="w-10 text-right">{item.progress}%</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {submitError && (
        <div className="mt-4 rounded-2xl border border-rose-200 bg-rose-50 px-3.5 py-3 text-sm text-rose-700">
          {submitError}
        </div>
      )}

      <div className="mt-4 flex items-center justify-between gap-3">
        <p className="text-xs text-slate-500">
          Responses are sent back to the agent as structured data.
        </p>
        <button
          type="button"
          onClick={handleSubmit}
          disabled={!onSubmit || isDisabled}
          className={cn(
            'inline-flex items-center gap-2 rounded-full px-4 py-2 text-sm font-semibold text-white transition-all disabled:cursor-not-allowed disabled:opacity-60',
            !isDisabled && 'shadow-[0_12px_28px_-18px_rgba(15,23,42,0.5)]'
          )}
          style={{ backgroundColor: primaryColor }}
        >
          {isSubmitting ? <Loader2 size={16} className="animate-spin" /> : null}
          {form.submit_label || 'Continue'}
        </button>
      </div>
    </div>
  )
}

interface FormFieldInputProps {
  field: FormField
  value: unknown
  uploadedFiles: Attachment[]
  disabled: boolean
  primaryColor: string
  onChange: (fieldId: string, value: unknown) => void
  onCheckboxGroupChange: (fieldId: string, optionValue: string, checked: boolean) => void
  onUpload: (field: FormField, files: FileList | null) => Promise<void>
  onRemoveUploadedFile: (fieldId: string, index: number) => void
}

function FormFieldInput({
  field,
  value,
  uploadedFiles,
  disabled,
  primaryColor,
  onChange,
  onCheckboxGroupChange,
  onUpload,
  onRemoveUploadedFile,
}: FormFieldInputProps) {
  const sharedInputClassName =
    'w-full rounded-2xl border border-slate-200 bg-slate-50 px-3 py-2.5 text-sm text-slate-800 outline-none transition focus:border-slate-300 focus:bg-white'

  if (field.type === 'boolean') {
    const selectedValue = typeof value === 'boolean' ? value : null
    return (
      <div className="grid grid-cols-2 gap-2">
        {[
          { label: 'Yes', value: true },
          { label: 'No', value: false },
        ].map((option) => {
          const isActive = selectedValue === option.value
          return (
            <button
              key={option.label}
              type="button"
              disabled={disabled}
              onClick={() => onChange(field.id, option.value)}
              className={cn(
                'rounded-2xl border px-3 py-2.5 text-sm font-medium transition',
                isActive ? 'text-white shadow-sm' : 'border-slate-200 bg-slate-50 text-slate-700 hover:bg-slate-100'
              )}
              style={isActive ? { backgroundColor: primaryColor, borderColor: primaryColor } : undefined}
            >
              {option.label}
            </button>
          )
        })}
      </div>
    )
  }

  if (field.type === 'radio') {
    return (
      <div className="space-y-2">
        {(field.options || []).map((option) => {
          const checked = value === option.value
          return (
            <label
              key={option.value}
              className={cn(
                'flex cursor-pointer items-center gap-3 rounded-2xl border px-3 py-2.5 text-sm transition',
                checked ? 'border-transparent bg-slate-900 text-white' : 'border-slate-200 bg-slate-50 text-slate-700 hover:bg-slate-100'
              )}
            >
              <input
                type="radio"
                name={field.id}
                value={option.value}
                checked={checked}
                disabled={disabled}
                onChange={() => onChange(field.id, option.value)}
                className="h-4 w-4"
              />
              <span>{option.label}</span>
            </label>
          )
        })}
      </div>
    )
  }

  if (field.type === 'checkbox_group') {
    const selectedValues = Array.isArray(value) ? (value as string[]) : []
    return (
      <div className="space-y-2">
        {(field.options || []).map((option) => {
          const checked = selectedValues.includes(option.value)
          return (
            <label
              key={option.value}
              className="flex cursor-pointer items-center gap-3 rounded-2xl border border-slate-200 bg-slate-50 px-3 py-2.5 text-sm text-slate-700 transition hover:bg-slate-100"
            >
              <input
                type="checkbox"
                value={option.value}
                checked={checked}
                disabled={disabled}
                onChange={(event) => onCheckboxGroupChange(field.id, option.value, event.target.checked)}
                className="h-4 w-4 rounded border-slate-300"
              />
              <span>{option.label}</span>
            </label>
          )
        })}
      </div>
    )
  }

  if (field.type === 'select') {
    return (
      <select
        value={String(value || '')}
        disabled={disabled}
        onChange={(event) => onChange(field.id, event.target.value)}
        className={sharedInputClassName}
      >
        <option value="">Select an option</option>
        {(field.options || []).map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    )
  }

  if (field.type === 'textarea') {
    return (
      <textarea
        value={String(value || '')}
        disabled={disabled}
        placeholder={field.placeholder}
        maxLength={field.max_length}
        onChange={(event) => onChange(field.id, event.target.value)}
        rows={4}
        className={sharedInputClassName}
      />
    )
  }

  if (field.type === 'number') {
    return (
      <input
        type="number"
        value={String(value || '')}
        disabled={disabled}
        placeholder={field.placeholder}
        min={field.min}
        max={field.max}
        step={field.step}
        onChange={(event) => onChange(field.id, event.target.value)}
        className={sharedInputClassName}
      />
    )
  }

  if (field.type === 'scale') {
    const min = field.min ?? 1
    const max = field.max ?? 5
    const step = field.step ?? 1
    const steps: number[] = []
    for (let current = min; current <= max; current += step) {
      steps.push(current)
    }

    return (
      <div>
        <div className="flex flex-wrap gap-2">
          {steps.map((optionValue) => {
            const checked = String(value) === String(optionValue)
            return (
              <button
                key={optionValue}
                type="button"
                disabled={disabled}
                onClick={() => onChange(field.id, String(optionValue))}
                className={cn(
                  'min-w-11 rounded-2xl border px-3 py-2 text-sm font-semibold transition',
                  checked ? 'text-white shadow-sm' : 'border-slate-200 bg-slate-50 text-slate-700 hover:bg-slate-100'
                )}
                style={checked ? { backgroundColor: primaryColor, borderColor: primaryColor } : undefined}
              >
                {optionValue}
              </button>
            )
          })}
        </div>
        {(field.min_label || field.max_label) && (
          <div className="mt-2 flex items-center justify-between text-[11px] text-slate-500">
            <span>{field.min_label || ''}</span>
            <span>{field.max_label || ''}</span>
          </div>
        )}
      </div>
    )
  }

  if (field.type === 'image_upload' || field.type === 'file_upload') {
    const accept = field.type === 'image_upload' ? 'image/*' : (field.accept || []).join(',')
    const label = field.type === 'image_upload' ? 'Upload image' : 'Upload file'

    return (
      <div className="space-y-3">
        <label className="flex cursor-pointer items-center justify-center gap-2 rounded-2xl border border-dashed border-slate-300 bg-slate-50 px-4 py-4 text-sm font-medium text-slate-700 transition hover:bg-slate-100">
          {field.type === 'image_upload' ? <Upload size={16} /> : <Paperclip size={16} />}
          {label}
          <input
            type="file"
            accept={accept || undefined}
            multiple={(field.max_files || 1) > 1}
            disabled={disabled}
            onChange={(event) => {
              void onUpload(field, event.target.files)
              event.target.value = ''
            }}
            className="hidden"
          />
        </label>

        {uploadedFiles.length > 0 && (
          <div className="space-y-2">
            {uploadedFiles.map((attachment, index) => (
              <div
                key={`${attachment.file_id || attachment.file_name || 'upload'}-${index}`}
                className="flex items-center justify-between gap-3 rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700"
              >
                <div className="min-w-0">
                  <div className="truncate font-medium">{attachment.file_name || 'Uploaded file'}</div>
                  {attachment.file_type && (
                    <div className="text-xs text-slate-500">{attachment.file_type}</div>
                  )}
                </div>
                <button
                  type="button"
                  disabled={disabled}
                  onClick={() => onRemoveUploadedFile(field.id, index)}
                  className="text-xs font-medium text-slate-500 transition hover:text-slate-800"
                >
                  Remove
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    )
  }

  return (
    <input
      type="text"
      value={String(value || '')}
      disabled={disabled}
      placeholder={field.placeholder}
      maxLength={field.max_length}
      onChange={(event) => onChange(field.id, event.target.value)}
      className={sharedInputClassName}
    />
  )
}
