/**
 * TTSControls.jsx
 * Text-to-speech control panel using the Web Speech API.
 */

import { useState } from 'react'

export default function TTSControls({ tts, currentText }) {
  const [showSettings, setShowSettings] = useState(false)
  const { isPlaying, isPaused, isSupported, voices, selectedVoice,
          setSelectedVoice, rate, setRate, pitch, setPitch,
          speak, pause, resume, stop } = tts

  if (!isSupported) {
    return (
      <div className="tts-bar unsupported">
        <span>🔇 Text-to-speech not supported in this browser.</span>
      </div>
    )
  }

  const handlePlay = () => {
    if (isPaused) return resume()
    if (isPlaying) return pause()
    speak(currentText)
  }

  return (
    <div className="tts-bar">
      <div className="tts-controls-row">
        {/* Play / Pause */}
        <button
          className="tts-btn primary"
          onClick={handlePlay}
          title={isPlaying && !isPaused ? 'Pause' : 'Read aloud'}
        >
          {isPlaying && !isPaused ? '⏸' : isPaused ? '▶️' : '🔊'}
          <span>{isPlaying && !isPaused ? 'Pause' : isPaused ? 'Resume' : 'Read Aloud'}</span>
        </button>

        {/* Stop */}
        {(isPlaying || isPaused) && (
          <button className="tts-btn" onClick={stop} title="Stop">
            ⏹ Stop
          </button>
        )}

        {/* Settings toggle */}
        <button
          className="tts-btn"
          onClick={() => setShowSettings(s => !s)}
          title="Voice settings"
        >
          ⚙️
        </button>

        {isPlaying && !isPaused && (
          <span className="tts-indicator">◉ Reading...</span>
        )}
      </div>

      {/* Expandable settings panel */}
      {showSettings && (
        <div className="tts-settings">
          {/* Voice selector */}
          <label className="tts-label">
            Voice
            <select
              className="tts-select"
              value={selectedVoice?.name || ''}
              onChange={e =>
                setSelectedVoice(voices.find(v => v.name === e.target.value) || null)
              }
            >
              {voices.map(v => (
                <option key={v.name} value={v.name}>
                  {v.name} ({v.lang})
                </option>
              ))}
            </select>
          </label>

          {/* Speed */}
          <label className="tts-label">
            Speed: {rate.toFixed(2)}×
            <input
              type="range" min="0.5" max="2" step="0.05"
              value={rate}
              onChange={e => setRate(parseFloat(e.target.value))}
              className="tts-range"
            />
          </label>

          {/* Pitch */}
          <label className="tts-label">
            Pitch: {pitch.toFixed(2)}
            <input
              type="range" min="0.5" max="2" step="0.05"
              value={pitch}
              onChange={e => setPitch(parseFloat(e.target.value))}
              className="tts-range"
            />
          </label>
        </div>
      )}
    </div>
  )
}
