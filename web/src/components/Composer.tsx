import { useRef, useState } from 'react'
import { ArrowUp, Square } from 'lucide-react'

interface Props {
  onSend: (text: string) => void
  onStop?: () => void
  busy: boolean
  disabled?: boolean
}

export default function Composer({ onSend, onStop, busy, disabled }: Props) {
  const [text, setText] = useState('')
  const ref = useRef<HTMLTextAreaElement>(null)

  const resize = () => {
    const el = ref.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = Math.min(el.scrollHeight, 200) + 'px'
  }

  const submit = () => {
    const t = text.trim()
    if (!t || busy || disabled) return
    onSend(t)
    setText('')
    requestAnimationFrame(() => {
      if (ref.current) ref.current.style.height = 'auto'
    })
  }

  return (
    <div className="px-4 pb-5 pt-2 md:px-6">
      <div className="mx-auto max-w-[760px]">
        <div className="flex items-end gap-2 rounded-[var(--radius-xl)] border border-line bg-surface-raised p-2 shadow-[0_2px_14px_rgba(27,28,25,0.05)] transition focus-within:border-accent/45">
          <textarea
            ref={ref}
            value={text}
            rows={1}
            disabled={disabled}
            placeholder={disabled ? 'Konfigurera API-nyckel under Inställningar…' : 'Fråga om ett system, felkod, artikelnummer…'}
            onChange={(e) => {
              setText(e.target.value)
              resize()
            }}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                submit()
              }
            }}
            className="max-h-[200px] flex-1 resize-none bg-transparent px-2.5 py-2 text-[15px] leading-relaxed text-ink outline-none placeholder:text-ink-faint disabled:cursor-not-allowed"
          />
          {busy ? (
            <button
              onClick={onStop}
              className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-ink text-paper transition hover:opacity-90"
              aria-label="Avbryt"
            >
              <Square size={15} fill="currentColor" />
            </button>
          ) : (
            <button
              onClick={submit}
              disabled={!text.trim() || disabled}
              className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-accent text-white transition enabled:hover:bg-accent-hover disabled:cursor-not-allowed disabled:opacity-35"
              aria-label="Skicka"
            >
              <ArrowUp size={18} strokeWidth={2.4} />
            </button>
          )}
        </div>
        <p className="mt-2 text-center text-[11px] text-ink-faint">
          Grunden kan ha fel — kontrollera kritiska uppgifter mot manualen.
        </p>
      </div>
    </div>
  )
}
