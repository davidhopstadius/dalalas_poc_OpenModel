import { useEffect, useState } from 'react'
import { Check, Loader2 } from 'lucide-react'
import { api } from '../api'
import type { Provider, Settings } from '../types'

interface Props {
  settings: Settings | null
  onSaved: () => void
}

type Form = Settings & {
  api_key: string
  brave_api_key: string
  berget_api_key: string
  anthropic_api_key: string
}

const PROVIDERS: { id: Provider; label: string }[] = [
  { id: 'grunden', label: 'Grunden' },
  { id: 'berget', label: 'Berget' },
  { id: 'anthropic', label: 'Anthropic' },
]

export default function SettingsView({ settings, onSaved }: Props) {
  const [form, setForm] = useState<Form | null>(null)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    if (settings)
      setForm({
        ...settings,
        api_key: '',
        brave_api_key: '',
        berget_api_key: '',
        anthropic_api_key: '',
      })
  }, [settings])

  if (!form) {
    return (
      <div className="grid flex-1 place-items-center text-ink-faint">
        <Loader2 className="animate-spin" />
      </div>
    )
  }

  const set = <K extends keyof Form>(k: K, v: Form[K]) => {
    setForm({ ...form, [k]: v })
    setSaved(false)
  }

  const save = async () => {
    setSaving(true)
    try {
      const patch: Record<string, unknown> = {
        provider: form.provider,
        base_url: form.base_url,
        model: form.model,
        berget_base_url: form.berget_base_url,
        berget_model: form.berget_model,
        berget_price_in: form.berget_price_in,
        berget_price_out: form.berget_price_out,
        anthropic_model: form.anthropic_model,
        system_prompt: form.system_prompt,
        thinking: form.thinking,
        search: form.search,
        doc_search: form.doc_search,
        rerank: form.rerank,
        rerank_model: form.rerank_model,
        rerank_candidates: form.rerank_candidates,
        embed_model: form.embed_model,
        rag_top_k: form.rag_top_k,
        request_timeout: form.request_timeout,
      }
      if (form.api_key.trim()) patch.api_key = form.api_key.trim()
      if (form.brave_api_key.trim()) patch.brave_api_key = form.brave_api_key.trim()
      if (form.berget_api_key.trim()) patch.berget_api_key = form.berget_api_key.trim()
      if (form.anthropic_api_key.trim()) patch.anthropic_api_key = form.anthropic_api_key.trim()
      await api.updateSettings(patch)
      setSaved(true)
      onSaved()
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="min-h-0 flex-1 overflow-y-auto">
      <div className="mx-auto max-w-[720px] px-5 py-8 md:px-6">
        <h1 className="font-display text-[22px] font-semibold tracking-tight">Inställningar</h1>
        <p className="mt-1.5 text-[14px] text-ink-soft">
          Ändringar gäller direkt för nästa fråga.
        </p>

        {/* Leverantör */}
        <Section title="AI-leverantör" hint="Välj vilken leverantör som besvarar frågorna. Byt fritt — RAG-indexet (dokumentsökningen) påverkas inte.">
          <div className="grid grid-cols-3 gap-2">
            {PROVIDERS.map((p) => (
              <button
                key={p.id}
                onClick={() => set('provider', p.id)}
                className={`rounded-lg border px-3 py-2 text-[13.5px] font-medium transition
                  ${form.provider === p.id ? 'border-accent bg-accent-soft text-accent-hover' : 'border-line bg-surface-raised text-ink-soft hover:text-ink'}`}
              >
                {p.label}
              </button>
            ))}
          </div>

          {form.provider === 'grunden' && (
            <>
              <Field label="Base URL">
                <Input value={form.base_url} onChange={(v) => set('base_url', v)} mono />
              </Field>
              <Field label="Modell">
                <Input value={form.model} onChange={(v) => set('model', v)} mono />
              </Field>
              <Field label="API-nyckel" hint={form.has_api_key ? 'En nyckel är redan satt — lämna tomt för att behålla.' : 'Ingen nyckel satt.'}>
                <Input
                  value={form.api_key}
                  onChange={(v) => set('api_key', v)}
                  type="password"
                  placeholder={form.has_api_key ? '•••••••••••• (satt)' : 'sk-…'}
                  mono
                />
              </Field>
            </>
          )}

          {form.provider === 'berget' && (
            <>
              <Field label="Base URL">
                <Input value={form.berget_base_url} onChange={(v) => set('berget_base_url', v)} mono />
              </Field>
              <Field label="Modell" hint="Berget-modellens id (OpenAI-kompatibelt). Hämtas från din Berget-konsol.">
                <Input value={form.berget_model} onChange={(v) => set('berget_model', v)} mono />
              </Field>
              <Field label="API-nyckel" hint={form.has_berget_key ? 'En nyckel är redan satt — lämna tomt för att behålla.' : 'Ingen nyckel satt.'}>
                <Input
                  value={form.berget_api_key}
                  onChange={(v) => set('berget_api_key', v)}
                  type="password"
                  placeholder={form.has_berget_key ? '•••••••••••• (satt)' : 'sk-…'}
                  mono
                />
              </Field>
              <div className="grid grid-cols-2 gap-4">
                <Field label="Pris in (kr/1M)" hint="För kostnadsanalysen.">
                  <NumberInput value={form.berget_price_in} onChange={(v) => set('berget_price_in', v)} />
                </Field>
                <Field label="Pris ut (kr/1M)">
                  <NumberInput value={form.berget_price_out} onChange={(v) => set('berget_price_out', v)} />
                </Field>
              </div>
            </>
          )}

          {form.provider === 'anthropic' && (
            <>
              <Field label="Modell" hint="T.ex. claude-sonnet-4-6, claude-opus-4-8 eller claude-haiku-4-5.">
                <Input value={form.anthropic_model} onChange={(v) => set('anthropic_model', v)} mono />
              </Field>
              <Field label="API-nyckel" hint={form.has_anthropic_key ? 'En nyckel är redan satt — lämna tomt för att behålla.' : 'Ingen nyckel satt.'}>
                <Input
                  value={form.anthropic_api_key}
                  onChange={(v) => set('anthropic_api_key', v)}
                  type="password"
                  placeholder={form.has_anthropic_key ? '•••••••••••• (satt)' : 'sk-ant-…'}
                  mono
                />
              </Field>
            </>
          )}

          <Field label="Brave-nyckel (webbsök)" hint={form.has_brave_key ? 'Satt. Gäller alla leverantörer.' : 'Krävs för webbsökning.'}>
            <Input
              value={form.brave_api_key}
              onChange={(v) => set('brave_api_key', v)}
              type="password"
              placeholder={form.has_brave_key ? '•••••••••••• (satt)' : 'BSA…'}
              mono
            />
          </Field>
        </Section>

        {/* Beteende */}
        <Section title="Beteende">
          <Switch label="Reasoning (thinking)" desc="Låt modellen resonera innan svar." on={form.thinking} onChange={(v) => set('thinking', v)} />
          <Switch label="Reranking (Steg 2)" desc="BGE cross-encoder omsorterar träffarna." on={form.rerank} onChange={(v) => set('rerank', v)} />
          <Switch label="Dokumentsökning (RAG)" desc="Sök i indexerade manualer." on={form.doc_search} onChange={(v) => set('doc_search', v)} />
          <Switch label="Webbsökning" desc="Slå upp aktuell info via Brave." on={form.search} onChange={(v) => set('search', v)} />
        </Section>

        {/* Avancerat */}
        <Section title="Sökning & avancerat">
          <div className="grid grid-cols-2 gap-4">
            <Field label="Träffar (top-k)">
              <NumberInput value={form.rag_top_k} onChange={(v) => set('rag_top_k', v)} />
            </Field>
            <Field label="Rerank-kandidater">
              <NumberInput value={form.rerank_candidates} onChange={(v) => set('rerank_candidates', v)} />
            </Field>
            <Field label="Embeddingmodell">
              <Input value={form.embed_model} onChange={(v) => set('embed_model', v)} mono />
            </Field>
            <Field label="Rerank-modell">
              <Input value={form.rerank_model} onChange={(v) => set('rerank_model', v)} mono />
            </Field>
            <Field label="Timeout (sek)">
              <NumberInput value={form.request_timeout} onChange={(v) => set('request_timeout', v)} />
            </Field>
          </div>
          <Field label="Systemprompt" hint="Lämna tomt för standardprompt med dagens datum.">
            <textarea
              value={form.system_prompt}
              onChange={(e) => set('system_prompt', e.target.value)}
              rows={3}
              className="w-full resize-y rounded-lg border border-line bg-surface-raised px-3 py-2 text-[14px] text-ink outline-none transition focus:border-accent/50"
            />
          </Field>
        </Section>

        <div className="sticky bottom-0 mt-8 flex items-center gap-3 border-t border-line bg-paper/80 py-4 backdrop-blur">
          <button
            onClick={save}
            disabled={saving}
            className="inline-flex items-center gap-2 rounded-xl bg-accent px-5 py-2.5 text-[14px] font-medium text-white transition hover:bg-accent-hover disabled:opacity-60"
          >
            {saving ? <Loader2 size={16} className="animate-spin" /> : saved ? <Check size={16} /> : null}
            {saved ? 'Sparat' : 'Spara inställningar'}
          </button>
        </div>
      </div>
    </div>
  )
}

function Section({ title, hint, children }: { title: string; hint?: string; children: React.ReactNode }) {
  return (
    <section className="mt-8">
      <h2 className="font-display text-[15px] font-semibold">{title}</h2>
      {hint && <p className="mt-0.5 text-[12.5px] text-ink-faint">{hint}</p>}
      <div className="mt-3 space-y-4 rounded-2xl border border-line bg-surface p-5">{children}</div>
    </section>
  )
}

function Field({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <div className="mb-1.5 text-[13px] font-medium text-ink">{label}</div>
      {children}
      {hint && <div className="mt-1 text-[12px] text-ink-faint">{hint}</div>}
    </label>
  )
}

function Input({
  value,
  onChange,
  type = 'text',
  placeholder,
  mono,
}: {
  value: string
  onChange: (v: string) => void
  type?: string
  placeholder?: string
  mono?: boolean
}) {
  return (
    <input
      type={type}
      value={value}
      placeholder={placeholder}
      onChange={(e) => onChange(e.target.value)}
      className={`w-full rounded-lg border border-line bg-surface-raised px-3 py-2 text-[14px] text-ink outline-none transition focus:border-accent/50 placeholder:text-ink-faint ${mono ? 'mono' : ''}`}
    />
  )
}

function NumberInput({ value, onChange }: { value: number; onChange: (v: number) => void }) {
  return (
    <input
      type="number"
      value={value}
      onChange={(e) => onChange(Number(e.target.value))}
      className="mono w-full rounded-lg border border-line bg-surface-raised px-3 py-2 text-[14px] text-ink outline-none transition focus:border-accent/50"
    />
  )
}

function Switch({
  label,
  desc,
  on,
  onChange,
}: {
  label: string
  desc: string
  on: boolean
  onChange: (v: boolean) => void
}) {
  return (
    <div className="flex items-center justify-between gap-4">
      <div>
        <div className="text-[14px] font-medium text-ink">{label}</div>
        <div className="text-[12.5px] text-ink-faint">{desc}</div>
      </div>
      <button
        onClick={() => onChange(!on)}
        className={`relative h-6 w-11 shrink-0 rounded-full transition ${on ? 'bg-accent' : 'bg-line'}`}
        role="switch"
        aria-checked={on}
        aria-label={label}
      >
        <span
          className={`absolute top-0.5 h-5 w-5 rounded-full bg-white shadow-sm transition-all ${on ? 'left-[22px]' : 'left-0.5'}`}
        />
      </button>
    </div>
  )
}
