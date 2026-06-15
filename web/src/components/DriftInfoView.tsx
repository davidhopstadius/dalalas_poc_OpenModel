import { useEffect, useState } from 'react'
import { ArrowDownLeft, ArrowUpRight, Coins, Loader2, RotateCw, Sigma } from 'lucide-react'
import { api } from '../api'
import type { UsageBlock, UsageSummary } from '../types'

const nf = new Intl.NumberFormat('sv-SE')

function tokens(n: number): string {
  return nf.format(n)
}

function kr(amount: number): string {
  // Sma belopp: visa fler decimaler sa det inte avrundas till 0.
  const decimals = amount > 0 && amount < 1 ? 4 : 2
  return (
    amount.toLocaleString('sv-SE', {
      minimumFractionDigits: 2,
      maximumFractionDigits: decimals,
    }) + ' kr'
  )
}

export default function DriftInfoView() {
  const [usage, setUsage] = useState<UsageSummary | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  const refresh = async () => {
    try {
      setUsage(await api.getUsage())
      setError(null)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    refresh()
    // Uppdatera diskret medan vyn ar oppen, sa siffrorna ar frascha.
    const id = setInterval(refresh, 5000)
    return () => clearInterval(id)
  }, [])

  return (
    <div className="min-h-0 flex-1 overflow-y-auto">
      <div className="mx-auto max-w-[760px] px-5 py-8 md:px-6">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="font-display text-[22px] font-semibold tracking-tight">Driftinfo</h1>
            <p className="mt-1.5 text-[14px] text-ink-soft">
              Tokenförbrukning och beräknad kostnad hos nuvarande AI-leverantör.
            </p>
          </div>
          <button
            onClick={refresh}
            className="mt-1 grid h-9 w-9 shrink-0 place-items-center rounded-lg border border-line bg-surface text-ink-soft transition hover:text-accent"
            aria-label="Uppdatera"
          >
            <RotateCw size={16} />
          </button>
        </div>

        {/* Leverantör / pris */}
        {usage && (
          <div className="mt-6 rounded-2xl border border-line bg-surface px-5 py-4">
            <div className="text-[11px] font-semibold uppercase tracking-wider text-ink-faint">
              Leverantör &amp; pris
            </div>
            <div className="mt-2 flex flex-wrap items-baseline gap-x-6 gap-y-1">
              <div className="text-[15px] font-medium text-ink">
                Grunden.ai · <span className="mono">{usage.model}</span>
              </div>
              <div className="mono text-[13px] text-ink-soft">
                {tokens(usage.rates.input_per_mtok)} kr / 1M in
              </div>
              <div className="mono text-[13px] text-ink-soft">
                {tokens(usage.rates.output_per_mtok)} kr / 1M ut
              </div>
            </div>
          </div>
        )}

        {loading && !usage && (
          <div className="mt-8 flex items-center gap-2 text-[14px] text-ink-soft">
            <Loader2 size={18} className="animate-spin text-accent" /> Hämtar driftinfo…
          </div>
        )}

        {error && (
          <div className="mt-6 rounded-xl border border-danger/25 bg-danger/5 px-4 py-3 text-[13.5px] text-danger">
            {error}
          </div>
        )}

        {usage && (
          <div className="mt-6 grid gap-4 sm:grid-cols-2">
            <UsageCard
              title="Senaste fråga"
              subtitle="Den senast ställda frågan"
              block={usage.last_message}
              currency={usage.currency}
            />
            <UsageCard
              title="Senaste tråd"
              subtitle={usage.last_conversation.conversation_title || 'Inget aktivt samtal'}
              block={usage.last_conversation}
              currency={usage.currency}
            />
            <UsageCard
              title="Idag"
              subtitle="Sedan midnatt"
              block={usage.today}
              currency={usage.currency}
            />
            <UsageCard
              title="Totalt"
              subtitle="Sedan start"
              block={usage.total}
              currency={usage.currency}
              accent
            />
          </div>
        )}

        {usage && (
          <p className="mt-6 text-[12px] leading-relaxed text-ink-faint">
            Kostnaden är beräknad utifrån Grunden.ai:s listpris (standardtakt) och avser endast
            chattmodellen. Embeddings och reranker debiteras inte. Siffrorna räknas från och med att
            den här funktionen togs i bruk.
          </p>
        )}
      </div>
    </div>
  )
}

function UsageCard({
  title,
  subtitle,
  block,
  currency,
  accent,
}: {
  title: string
  subtitle: string
  block: UsageBlock
  currency: string
  accent?: boolean
}) {
  return (
    <div
      className={`rounded-2xl border bg-surface p-5 ${
        accent ? 'border-accent/30 bg-accent-soft/40' : 'border-line'
      }`}
    >
      <div className="flex items-baseline justify-between">
        <h2 className="font-display text-[15px] font-semibold tracking-tight">{title}</h2>
        <span className="mono text-[11px] text-ink-faint">{block.requests} anrop</span>
      </div>
      <p className="mt-0.5 truncate text-[12px] text-ink-faint" title={subtitle}>
        {subtitle}
      </p>

      <div className="mt-4 space-y-2">
        <Row icon={<ArrowDownLeft size={14} />} label="Tokens in" value={tokens(block.prompt_tokens)} />
        <Row icon={<ArrowUpRight size={14} />} label="Tokens ut" value={tokens(block.completion_tokens)} />
        <Row icon={<Sigma size={14} />} label="Totalt" value={tokens(block.total_tokens)} />
      </div>

      <div className="mt-4 flex items-center justify-between border-t border-line pt-3">
        <span className="flex items-center gap-1.5 text-[12px] font-medium text-ink-soft">
          <Coins size={14} className="text-accent" /> Kostnad
        </span>
        <span className="mono text-[15px] font-semibold text-ink">
          {kr(block.cost)}
          {currency !== 'SEK' && <span className="ml-1 text-[11px] text-ink-faint">{currency}</span>}
        </span>
      </div>
    </div>
  )
}

function Row({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <div className="flex items-center justify-between text-[13px]">
      <span className="flex items-center gap-1.5 text-ink-soft">
        <span className="text-ink-faint">{icon}</span>
        {label}
      </span>
      <span className="mono text-ink">{value}</span>
    </div>
  )
}
