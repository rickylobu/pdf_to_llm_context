/**
 * Sidebar.jsx
 * Book navigation: chapter/page list with search.
 */

import { useState, useMemo } from 'react'

export default function Sidebar({ index, currentPage, onPageSelect, isOpen, onClose }) {
  const [search, setSearch] = useState('')

  const filtered = useMemo(() => {
    if (!search.trim()) return index.pages
    const q = search.toLowerCase()
    return index.pages.filter(
      p =>
        p.preview.toLowerCase().includes(q) ||
        String(p.page).includes(q)
    )
  }, [search, index.pages])

  return (
    <>
      {/* Overlay for mobile */}
      {isOpen && (
        <div className="sidebar-overlay" onClick={onClose} aria-hidden="true" />
      )}

      <aside className={`sidebar ${isOpen ? 'open' : ''}`} aria-label="Book navigation">
        {/* Header */}
        <div className="sidebar-header">
          <div className="sidebar-book-info">
            {index.cover && (
              <img src={index.cover} alt="Book cover" className="sidebar-cover" />
            )}
            <div>
              <h1 className="sidebar-title">{index.title}</h1>
              {index.author && <p className="sidebar-author">{index.author}</p>}
              {index.year && <p className="sidebar-meta">{index.year}</p>}
            </div>
          </div>

          {/* Search */}
          <div className="sidebar-search-wrap">
            <input
              type="search"
              placeholder="Search pages..."
              className="sidebar-search"
              value={search}
              onChange={e => setSearch(e.target.value)}
              aria-label="Search pages"
            />
          </div>
        </div>

        {/* Page list */}
        <nav className="sidebar-nav" aria-label="Pages">
          {filtered.length === 0 ? (
            <p className="sidebar-empty">No results for "{search}"</p>
          ) : (
            <ul className="sidebar-list">
              {filtered.map(p => (
                <li key={p.page}>
                  <button
                    className={`sidebar-item ${currentPage === p.page ? 'active' : ''}`}
                    onClick={() => { onPageSelect(p.page); onClose() }}
                    aria-current={currentPage === p.page ? 'page' : undefined}
                  >
                    <span className="sidebar-page-num">p.{p.page}</span>
                    <span className="sidebar-preview">{p.preview.slice(0, 80)}&hellip;</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </nav>

        {/* Footer */}
        <div className="sidebar-footer">
          <p>{index.total_pages} pages digitized</p>
          {index.original_url && (
            <a
              href={index.original_url}
              target="_blank"
              rel="noopener noreferrer"
              className="sidebar-source-link"
            >
              📎 Original source
            </a>
          )}
        </div>
      </aside>
    </>
  )
}
