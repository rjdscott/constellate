import * as Tooltip from '@radix-ui/react-tooltip'
import { motion } from 'motion/react'
import { useEffect, useState, type ReactNode } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router'

const THEME_KEY = 'constellate:theme' // also read by the pre-paint script in index.html
const RAIL_KEY = 'constellate:rail'

/** Durations live in tokens.css (and are zeroed under prefers-reduced-motion),
 *  so JS reads them instead of hardcoding milliseconds. */
function motionSeconds(token: string): number {
  const raw = getComputedStyle(document.documentElement).getPropertyValue(token)
  return parseFloat(raw) / 1000 || 0
}

const EASE_STANDARD = [0.2, 0, 0, 1] as const // --ease-standard

/** NavLink's own `className={({isActive}) => …}` cannot be used here: Radix's
 *  `Trigger asChild` merges props by string-concatenating className, which
 *  stringifies the function onto the element. Compute the state instead. */
const isActive = (pathname: string, to: string) =>
  to === '/' ? pathname === '/' : pathname.startsWith(to)

type Theme = 'dark' | 'light'

function useTheme(): [Theme, () => void] {
  const [theme, setTheme] = useState<Theme>(
    () => (document.documentElement.dataset.theme as Theme | undefined) ?? 'dark',
  )
  useEffect(() => {
    document.documentElement.dataset.theme = theme
    localStorage.setItem(THEME_KEY, theme)
  }, [theme])
  return [theme, () => setTheme((current) => (current === 'dark' ? 'light' : 'dark'))]
}

const NAV = [
  {
    to: '/',
    label: 'Overview',
    icon: (
      <>
        <path d="M3 12l5-8 5 5 4-6" />
        <circle cx="3" cy="12" r="1.6" />
        <circle cx="8" cy="4" r="1.6" />
        <circle cx="13" cy="9" r="1.6" />
        <circle cx="17" cy="3" r="1.6" />
      </>
    ),
  },
  {
    to: '/playground',
    label: 'Playground',
    icon: (
      <>
        <path d="M3 5l4 4-4 4" />
        <path d="M10 13h7" />
      </>
    ),
  },
  {
    to: '/bench',
    label: 'Bench',
    icon: (
      <>
        <path d="M3 16V9" />
        <path d="M8.5 16V4" />
        <path d="M14 16v-5" />
      </>
    ),
  },
]

function RailIcon({ children }: { children: ReactNode }) {
  return (
    <svg
      viewBox="0 0 20 20"
      aria-hidden
      className="size-5 shrink-0 stroke-current"
      fill="none"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      {children}
    </svg>
  )
}

function RailButton({
  label,
  collapsed,
  onClick,
  children,
}: {
  label: string
  collapsed: boolean
  onClick: () => void
  children: ReactNode
}) {
  return (
    <Hint label={label} show={collapsed}>
      <button
        type="button"
        onClick={onClick}
        aria-label={label}
        className="flex w-full items-center gap-3 rounded-sm px-3 py-2 text-text-dim transition-colors duration-[var(--motion-fast)] hover:bg-raised hover:text-text"
      >
        {children}
        {!collapsed && <span className="truncate text-sm">{label}</span>}
      </button>
    </Hint>
  )
}

/** Tooltip only earns its keep on the collapsed rail, where labels are gone. */
function Hint({ label, show, children }: { label: string; show: boolean; children: ReactNode }) {
  if (!show) return children
  return (
    <Tooltip.Root>
      <Tooltip.Trigger asChild>{children}</Tooltip.Trigger>
      <Tooltip.Portal>
        <Tooltip.Content
          side="right"
          sideOffset={8}
          className="rounded-sm border border-hairline bg-raised px-2 py-1 text-sm text-text shadow-[var(--shadow-2)]"
        >
          {label}
        </Tooltip.Content>
      </Tooltip.Portal>
    </Tooltip.Root>
  )
}

export default function Shell() {
  const location = useLocation()
  const [theme, toggleTheme] = useTheme()
  const [collapsed, setCollapsed] = useState(() => localStorage.getItem(RAIL_KEY) === 'collapsed')

  useEffect(() => {
    localStorage.setItem(RAIL_KEY, collapsed ? 'collapsed' : 'expanded')
  }, [collapsed])

  return (
    <Tooltip.Provider delayDuration={200}>
      <div className="flex min-h-screen">
        <nav
          aria-label="Sections"
          style={{ width: collapsed ? 64 : 220 }}
          className="flex shrink-0 flex-col border-r border-hairline bg-surface transition-[width] duration-[var(--motion-base)] ease-standard"
        >
          <div className="flex items-center gap-2.5 px-3.5 py-6">
            <span aria-hidden className="text-accent text-md leading-none">
              ✦
            </span>
            {!collapsed && (
              <span className="text-xs font-semibold tracking-[0.28em] uppercase">
                Constellate
              </span>
            )}
          </div>

          <ul className="flex flex-col gap-1 px-2">
            {NAV.map((item) => (
              <li key={item.to}>
                <Hint label={item.label} show={collapsed}>
                  <NavLink
                    to={item.to}
                    aria-label={item.label}
                    className={`relative flex items-center gap-3 rounded-sm px-3 py-2 transition-colors duration-[var(--motion-fast)] ${
                      isActive(location.pathname, item.to)
                        ? 'bg-raised text-accent before:absolute before:inset-y-1 before:left-0 before:w-0.5 before:rounded-full before:bg-accent before:content-[""]'
                        : 'text-text-dim hover:bg-raised hover:text-text'
                    }`}
                  >
                    <RailIcon>{item.icon}</RailIcon>
                    {!collapsed && <span className="truncate text-sm">{item.label}</span>}
                  </NavLink>
                </Hint>
              </li>
            ))}
          </ul>

          <div className="mt-auto flex flex-col gap-1 border-t border-hairline p-2">
            <RailButton
              label={theme === 'dark' ? 'Light theme' : 'Dark theme'}
              collapsed={collapsed}
              onClick={toggleTheme}
            >
              <RailIcon>
                {theme === 'dark' ? (
                  <path d="M14.5 12.5A6 6 0 0 1 7.5 5.5a6 6 0 1 0 7 7z" />
                ) : (
                  <>
                    <circle cx="10" cy="10" r="3.4" />
                    <path d="M10 2.5v2M10 15.5v2M2.5 10h2M15.5 10h2M4.7 4.7l1.4 1.4M13.9 13.9l1.4 1.4M15.3 4.7l-1.4 1.4M6.1 13.9l-1.4 1.4" />
                  </>
                )}
              </RailIcon>
            </RailButton>
            <RailButton
              label={collapsed ? 'Expand rail' : 'Collapse rail'}
              collapsed={collapsed}
              onClick={() => setCollapsed((value) => !value)}
            >
              <RailIcon>
                <path d={collapsed ? 'M8 5l4 5-4 5' : 'M12 5l-4 5 4 5'} />
              </RailIcon>
            </RailButton>
          </div>
        </nav>

        <motion.main
          key={location.pathname}
          initial={{ opacity: 0, y: 4 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: motionSeconds('--motion-view'), ease: EASE_STANDARD }}
          className="relative flex-1 overflow-y-auto"
        >
          <Outlet />
        </motion.main>
      </div>
    </Tooltip.Provider>
  )
}
