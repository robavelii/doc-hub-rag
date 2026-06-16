import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { FileText, MessageSquare, Puzzle, X } from 'lucide-react'
import { Button } from './ui'

const STEPS = [
  { icon: FileText, title: 'Upload documents', desc: 'Add PDFs, DOCX, or URLs to build your knowledge base.', path: '/documents' },
  { icon: MessageSquare, title: 'Ask questions', desc: 'Chat with cited answers powered by your documents.', path: '/chat' },
  { icon: Puzzle, title: 'Embed the widget', desc: 'Copy the embed code and add AI chat to your website.', path: '/widget' },
]

const STORAGE_KEY = 'doc-hub-onboarding-done'

export function isOnboardingDone(): boolean {
  return localStorage.getItem(STORAGE_KEY) === 'true'
}

export function markOnboardingDone(): void {
  localStorage.setItem(STORAGE_KEY, 'true')
}

export default function Onboarding() {
  const [step, setStep] = useState(0)
  const [visible, setVisible] = useState(!isOnboardingDone())
  const navigate = useNavigate()

  if (!visible) return null

  const current = STEPS[step]
  if (!current) return null
  const Icon = current.icon

  const finish = () => {
    markOnboardingDone()
    setVisible(false)
  }

  return (
    <div className="fixed inset-0 z-[200] flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
      <div className="glass max-w-md w-full rounded-2xl p-6 animate-scale-in relative">
        <button
          onClick={finish}
          className="absolute top-4 right-4 p-1 rounded-md text-muted hover:text-text"
          aria-label="Dismiss"
        >
          <X size={18} />
        </button>
        <div className="flex items-center gap-3 mb-4">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary-muted">
            <Icon size={20} className="text-primary" />
          </div>
          <div>
            <p className="text-xs text-muted">Step {step + 1} of {STEPS.length}</p>
            <h3 className="font-semibold text-text">{current.title}</h3>
          </div>
        </div>
        <p className="text-sm text-muted mb-6">{current.desc}</p>
        <div className="flex gap-2 mb-4">
          {STEPS.map((_, i) => (
            <div key={i} className={`h-1 flex-1 rounded-full ${i <= step ? 'bg-primary' : 'bg-border'}`} />
          ))}
        </div>
        <div className="flex gap-2">
          {step < STEPS.length - 1 ? (
            <>
              <Button variant="ghost" onClick={finish} className="flex-1">Skip tour</Button>
              <Button
                onClick={() => {
                  navigate(current.path)
                  setStep(step + 1)
                }}
                className="flex-1"
              >
                Next
              </Button>
            </>
          ) : (
            <Button onClick={() => { navigate(current.path); finish() }} className="w-full">
              Get started
            </Button>
          )}
        </div>
      </div>
    </div>
  )
}
