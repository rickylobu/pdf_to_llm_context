/**
 * App.jsx
 * Root component. Loads index.json, applies dynamic theme from book cover,
 * and orchestrates Sidebar + Reader + TTS.
 */

import { useState, useEffect, useCallback } from 'react'
import Sidebar from './components/Sidebar'
import Reader from './components/Reader'
import TTSControls from './components/TTSControls'
import { useTTS } from './hooks/useTTS'

const BASE_PATH = import.meta.env.BASE_URL

function applyTheme(theme) {
  if (!theme) return
  const root = document.documentElement
  const map = {
    primary_color: '--color-primary',
    secondary_color: '--color-secondary',
    accent_color: '--color-accent',
    background_color: '--color-bg',
    text_color: '--color-text',
  }
  Object.entries(map).forEach(([key, cssVar]) => {
    if (theme[key]) root.style.setProperty(cssVar, theme[key])
  })
}

export default function App() {
  const [index, setIndex] = useState(null)
  const [currentPage, setCurrentPage] = useState(null)
  const [currentText, setCurrentText] = useState('')
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [loadError, setLoadError] = useState(null)
  const tts = useTTS()

  // Load index.json on mount
  useEffect(() => {
    fetch(`${BASE_PATH}index.json`)
      .then(r => {
        if (!r.ok) throw new Error('index.json not found. Run the extractor first.')
        return r.json()
      })
      .then(data => {
        setIndex(data)
        applyTheme(data.theme)
        document.title = data.title ? `${data.title} — Reader` : 'Book Reader'
        if (data.pages?.length > 0) {
          setCurrentPage(data.pages[0].page)
        }
      })
      .catch(err => setLoadError(err.message))
  }, [])

  const handlePageSelect = useCallback((pageNum) => {
    tts.stop()
    setCurrentPage(pageNum)
  }, [tts])

  const handleTextReady = useCallback((text) => {
    setCurrentText(text)
  }, [])

  // Keyboard navigation
  useEffect(() => {
    const onKey = (e) => {
      if (!index) return
      const pages = index.pages.map(p => p.page)
      const idx = pages.indexOf(currentPage)
      if (e.key === 'ArrowRight' && idx < pages.length - 1) {
        handlePageSelect(pages[idx + 1])
      } else if (e.key === 'ArrowLeft' && idx > 0) {
        handlePageSelect(pages[idx - 1])
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [index, currentPage, handlePageSelect])

  if (loadError) {
    return (
      <div className="app-error">
        <h1>⚠️ Setup Required</h1>
        <p>{loadError}</p>
        <a
          href="https://github.com/YOUR_USERNAME/pdf-to-llm-context#quick-start"
          className="btn-primary"
        >
          View Setup Instructions →
        </a>
      </div>
    )
  }

  if (!index) {
    return (
      <div className="app-loading">
        <div className="spinner large" aria-hidden="true" />
        <p>Loading book…</p>
      </div>
    )
  }

  const pages = index.pages.map(p => p.page)
  const currentIdx = pages.indexOf(currentPage)
  const hasPrev = currentIdx > 0
  const hasNext = currentIdx < pages.length - 1

  return (
    <div className="app-layout">
      {/* Skip link for accessibility */}
      <a href="#reader-main" className="skip-link">Skip to content</a>

      {/* Mobile header */}
      <header className="mobile-header">
        <button
          className="menu-btn"
          onClick={() => setSidebarOpen(true)}
          aria-label="Open navigation"
        >
          ☰
        </button>
        <span className="mobile-title">{index.title}</span>
        <span className="mobile-page">p.{currentPage}</span>
      </header>

      {/* Sidebar */}
      <Sidebar
        index={index}
        currentPage={currentPage}
        onPageSelect={handlePageSelect}
        isOpen={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
      />

      {/* Main content */}
      <main className="main-content" id="reader-main">
        {/* TTS bar */}
        <TTSControls tts={tts} currentText={currentText} />

        {/* Reader */}
        <div className="reader-wrap">
          <Reader
            pageNumber={currentPage}
            onTextReady={handleTextReady}
          />
        </div>

        {/* Pagination */}
        <nav className="pagination" aria-label="Page navigation">
          <button
            className="btn-nav"
            disabled={!hasPrev}
            onClick={() => handlePageSelect(pages[currentIdx - 1])}
            aria-label="Previous page"
          >
            ← Prev
          </button>
          <span className="pagination-info" aria-live="polite">
            Page {currentPage} of {index.total_pages}
          </span>
          <button
            className="btn-nav"
            disabled={!hasNext}
            onClick={() => handlePageSelect(pages[currentIdx + 1])}
            aria-label="Next page"
          >
            Next →
          </button>
        </nav>
      </main>
    </div>
  )
}
