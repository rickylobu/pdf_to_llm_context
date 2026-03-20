/**
 * Reader.jsx
 * Renders a Markdown page with full GFM support (tables, code, etc.)
 * Intercepts GeoGebra links and renders them as interactive iframes.
 */

import { useEffect, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeRaw from 'rehype-raw'

const BASE_PATH = import.meta.env.BASE_URL

function GeoGebraEmbed({ url }) {
  return (
    <div className="geogebra-embed">
      <iframe
        src={url}
        title="GeoGebra interactive graph"
        allowFullScreen
        loading="lazy"
        aria-label="Interactive mathematical visualization"
      />
      <p className="geogebra-label">📊 Interactive graph via GeoGebra</p>
    </div>
  )
}

// Custom link renderer — intercepts GeoGebra links
function CustomLink({ href, children, ...props }) {
  if (href && href.includes('geogebra.org')) {
    return <GeoGebraEmbed url={href} />
  }
  return (
    <a href={href} target="_blank" rel="noopener noreferrer" {...props}>
      {children}
    </a>
  )
}

const MD_COMPONENTS = {
  a: CustomLink,
  // Accessible table wrapper
  table: ({ node, ...props }) => (
    <div className="table-scroll" role="region" aria-label="Table" tabIndex={0}>
      <table {...props} />
    </div>
  ),
}

export default function Reader({ pageNumber, basePath, onTextReady }) {
  const [content, setContent] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (!pageNumber) return
    setLoading(true)
    setError(null)
    setContent('')

    const url = `${BASE_PATH}pages/page_${String(pageNumber).padStart(4, '0')}.md`

    fetch(url)
      .then(r => {
        if (!r.ok) throw new Error(`Page ${pageNumber} not found (${r.status})`)
        return r.text()
      })
      .then(text => {
        setContent(text)
        setLoading(false)
        onTextReady?.(text)
      })
      .catch(err => {
        setError(err.message)
        setLoading(false)
      })
  }, [pageNumber])

  if (loading) {
    return (
      <div className="reader-state" aria-live="polite" aria-busy="true">
        <div className="spinner" aria-hidden="true" />
        <p>Loading page {pageNumber}…</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="reader-state error" role="alert">
        <p>⚠️ {error}</p>
      </div>
    )
  }

  if (!content) {
    return (
      <div className="reader-state">
        <p>Select a page from the sidebar to start reading.</p>
      </div>
    )
  }

  // Strip YAML frontmatter before rendering
  const markdownBody = content.replace(/^---[\s\S]*?---\n/, '')

  return (
    <article className="reader-article" aria-label={`Page ${pageNumber}`}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeRaw]}
        components={MD_COMPONENTS}
      >
        {markdownBody}
      </ReactMarkdown>
    </article>
  )
}
