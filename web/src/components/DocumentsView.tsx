import { useEffect, useRef, useState } from 'react'
import { FileText, Loader2, Trash2, Upload } from 'lucide-react'
import { api } from '../api'
import type { DocumentSummary } from '../types'

export default function DocumentsView() {
  const [docs, setDocs] = useState<DocumentSummary[]>([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [dragOver, setDragOver] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  const refresh = () => api.listDocuments().then((d) => setDocs(d.documents)).catch(() => {})

  useEffect(() => {
    refresh()
  }, [])

  const upload = async (file: File) => {
    setError(null)
    setBusy(true)
    try {
      await api.uploadDocument(file)
      await refresh()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const remove = async (name: string) => {
    await api.deleteDocument(name)
    refresh()
  }

  return (
    <div className="min-h-0 flex-1 overflow-y-auto">
      <div className="mx-auto max-w-[760px] px-5 py-8 md:px-6">
        <h1 className="font-display text-[22px] font-semibold tracking-tight">Dokument</h1>
        <p className="mt-1.5 text-[14px] text-ink-soft">
          Ladda upp tekniska manualer (PDF). De indexeras lokalt så assistenten kan söka i dem och
          svara med sidhänvisning.
        </p>

        {/* Dropzone */}
        <div
          onDragOver={(e) => {
            e.preventDefault()
            setDragOver(true)
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={(e) => {
            e.preventDefault()
            setDragOver(false)
            const f = e.dataTransfer.files?.[0]
            if (f) upload(f)
          }}
          onClick={() => !busy && inputRef.current?.click()}
          className={`mt-6 cursor-pointer rounded-2xl border-2 border-dashed px-6 py-10 text-center transition
            ${dragOver ? 'border-accent bg-accent-soft' : 'border-line bg-surface hover:border-accent/40'}`}
        >
          <input
            ref={inputRef}
            type="file"
            accept="application/pdf"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0]
              if (f) upload(f)
              e.target.value = ''
            }}
          />
          <div className="grid place-items-center gap-2 text-ink-soft">
            {busy ? (
              <>
                <Loader2 size={22} className="animate-spin text-accent" />
                <span className="text-[14px]">Indexerar… det kan ta en stund</span>
              </>
            ) : (
              <>
                <Upload size={22} className="text-accent" />
                <span className="text-[14px] font-medium text-ink">
                  Släpp en PDF här eller klicka för att välja
                </span>
                <span className="text-[12px] text-ink-faint">Endast PDF</span>
              </>
            )}
          </div>
        </div>

        {error && (
          <div className="mt-4 rounded-xl border border-danger/25 bg-danger/5 px-4 py-3 text-[13.5px] text-danger">
            {error}
          </div>
        )}

        {/* Lista */}
        <div className="mt-8">
          <div className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-ink-faint">
            Indexerade dokument ({docs.length})
          </div>
          {docs.length === 0 ? (
            <p className="text-[14px] text-ink-faint">Inga dokument indexerade än.</p>
          ) : (
            <ul className="divide-y divide-line overflow-hidden rounded-xl border border-line bg-surface">
              {docs.map((d) => (
                <li key={d.doc} className="flex items-center gap-3 px-4 py-3">
                  <FileText size={18} className="shrink-0 text-accent" />
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-[14px] text-ink">{d.doc.replace(/\.pdf$/i, '')}</div>
                    <div className="mono text-[11.5px] text-ink-faint">
                      {d.pages} sidor · {d.chunks} segment
                    </div>
                  </div>
                  <button
                    onClick={() => remove(d.doc)}
                    className="grid h-8 w-8 place-items-center rounded-lg text-ink-faint transition hover:bg-line-soft hover:text-danger"
                    aria-label="Radera dokument"
                  >
                    <Trash2 size={16} />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  )
}
