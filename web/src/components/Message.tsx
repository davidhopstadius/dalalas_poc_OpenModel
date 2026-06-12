import Markdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { FileText } from 'lucide-react'
import type { Citation } from '../types'

interface Props {
  role: 'user' | 'assistant'
  content: string
  citations?: Citation[]
}

export default function Message({ role, content, citations }: Props) {
  if (role === 'user') {
    return (
      <div className="rise flex justify-end">
        <div className="max-w-[85%] whitespace-pre-wrap rounded-2xl rounded-br-md bg-ink px-4 py-2.5 text-[14.5px] leading-relaxed text-paper">
          {content}
        </div>
      </div>
    )
  }

  return (
    <div className="rise">
      <div className="prose-grunden max-w-none text-[15px] text-ink">
        <Markdown remarkPlugins={[remarkGfm]}>{content}</Markdown>
      </div>
      {citations && citations.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {citations.map((c, i) => (
            <span
              key={`${c.doc}-${c.page}-${i}`}
              className="inline-flex items-center gap-1.5 rounded-full border border-line bg-surface px-2.5 py-1 text-[12px] text-ink-soft"
            >
              <FileText size={12.5} className="text-accent" />
              <span className="max-w-[200px] truncate">{c.doc.replace(/\.pdf$/i, '')}</span>
              <span className="mono text-ink-faint">· s.&nbsp;{c.page}</span>
            </span>
          ))}
        </div>
      )}
    </div>
  )
}
