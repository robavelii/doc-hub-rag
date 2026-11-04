import type { ReactNode } from 'react'
import { ThemeToggle } from './ui'

interface AuthLayoutProps {
  aside: ReactNode
  children: ReactNode
}

// Sign-in and sign-up share one frame: a quiet side panel in the sidebar tone, the form on paper.
export default function AuthLayout({ aside, children }: AuthLayoutProps) {
  return (
    <div className="flex min-h-dvh bg-bg">
      <aside className="hidden w-[44%] max-w-[560px] flex-col justify-between bg-sidebar p-10 lg:flex xl:p-14">
        <span className="text-lg font-semibold tracking-tight text-text">Doc-Hub</span>
        <div className="max-w-sm">{aside}</div>
      </aside>

      <main className="relative flex flex-1 flex-col px-5 py-6 sm:px-10">
        <div className="flex items-center justify-between">
          <span className="text-lg font-semibold tracking-tight text-text lg:invisible">Doc-Hub</span>
          <ThemeToggle />
        </div>
        <div className="flex flex-1 items-center justify-center py-10">
          <div className="w-full max-w-sm">{children}</div>
        </div>
      </main>
    </div>
  )
}
