/**
 * TacticsMaster - Navigation Component
 */

import { cn } from '../lib/utils'

export type Page = 'home' | 'comps' | 'items' | 'augments' | 'stats' | 'settings'

interface NavigationProps {
  currentPage: Page
  onPageChange: (page: Page) => void
}

// Icons
const HomeIcon = () => (
  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
  </svg>
)

const CrownIcon = () => (
  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z" />
  </svg>
)

const ItemIcon = () => (
  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
  </svg>
)

const SparklesIcon = () => (
  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z" />
  </svg>
)

const ChartIcon = () => (
  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
  </svg>
)

const SettingsIcon = () => (
  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
  </svg>
)

function NavButton({ 
  icon, 
  active, 
  onClick, 
  title 
}: { 
  icon: React.ReactNode
  active: boolean
  onClick: () => void
  title: string
}) {
  return (
    <button
      onClick={onClick}
      title={title}
      className={cn("nav-btn", active && "active")}
    >
      {icon}
    </button>
  )
}

export function Navigation({ currentPage, onPageChange }: NavigationProps) {
  return (
    <aside className="w-16 border-r border-border flex flex-col items-center py-6 gap-8 bg-surface/30 backdrop-blur-sm z-40">
      {/* Logo */}
      <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-primary to-cyan-400 flex items-center justify-center shadow-lg shadow-primary/20">
        <span className="text-lg font-bold text-white">TM</span>
      </div>
      
      {/* Navigation */}
      <nav className="flex flex-col gap-4 w-full items-center">
        <NavButton 
          icon={<HomeIcon />} 
          active={currentPage === 'home'} 
          onClick={() => onPageChange('home')} 
          title="Home"
        />
        <NavButton 
          icon={<CrownIcon />} 
          active={currentPage === 'comps'} 
          onClick={() => onPageChange('comps')} 
          title="Compositions"
        />
        <NavButton 
          icon={<ItemIcon />} 
          active={currentPage === 'items'} 
          onClick={() => onPageChange('items')} 
          title="Items"
        />
        <NavButton 
          icon={<SparklesIcon />} 
          active={currentPage === 'augments'} 
          onClick={() => onPageChange('augments')} 
          title="Augments"
        />
        <NavButton 
          icon={<ChartIcon />} 
          active={currentPage === 'stats'} 
          onClick={() => onPageChange('stats')} 
          title="Statistics"
        />
      </nav>
      
      {/* Spacer */}
      <div className="flex-1" />
      
      {/* Settings */}
      <NavButton 
        icon={<SettingsIcon />} 
        active={currentPage === 'settings'} 
        onClick={() => onPageChange('settings')} 
        title="Settings"
      />
    </aside>
  )
}

export default Navigation
