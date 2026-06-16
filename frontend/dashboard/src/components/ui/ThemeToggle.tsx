import { Moon, Sun } from 'lucide-react'
import { useTheme } from '../../theme/ThemeProvider'
import { IconButton } from './IconButton'

export function ThemeToggle() {
  const { theme, toggleTheme } = useTheme()
  const isDark = theme === 'dark'

  return (
    <IconButton
      label={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
      onClick={toggleTheme}
    >
      {isDark ? <Sun size={18} /> : <Moon size={18} />}
    </IconButton>
  )
}
