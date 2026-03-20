/**
 * useTTS.js
 * Encapsulates the Web Speech API for text-to-speech functionality.
 * Handles browser compatibility, voice selection, and playback state.
 */

import { useState, useEffect, useCallback, useRef } from 'react'

const DEFAULT_RATE = 0.95
const DEFAULT_PITCH = 1.0
const DEFAULT_VOLUME = 1.0

export function useTTS() {
  const [isPlaying, setIsPlaying] = useState(false)
  const [isPaused, setIsPaused] = useState(false)
  const [voices, setVoices] = useState([])
  const [selectedVoice, setSelectedVoice] = useState(null)
  const [rate, setRate] = useState(DEFAULT_RATE)
  const [pitch, setPitch] = useState(DEFAULT_PITCH)
  const [isSupported, setIsSupported] = useState(false)
  const utteranceRef = useRef(null)

  // Initialize voices
  useEffect(() => {
    if (!('speechSynthesis' in window)) {
      setIsSupported(false)
      return
    }
    setIsSupported(true)

    const loadVoices = () => {
      const available = window.speechSynthesis.getVoices()
      setVoices(available)
      // Prefer Spanish voices for accounting texts
      const spanish = available.find(
        v => v.lang.startsWith('es') && v.localService
      ) || available.find(v => v.lang.startsWith('es'))
      setSelectedVoice(spanish || available[0] || null)
    }

    loadVoices()
    window.speechSynthesis.addEventListener('voiceschanged', loadVoices)
    return () => {
      window.speechSynthesis.removeEventListener('voiceschanged', loadVoices)
    }
  }, [])

  // Strip Markdown for cleaner speech
  const stripMarkdown = (text) =>
    text
      .replace(/#{1,6}\s/g, '')          // headings
      .replace(/\*\*(.+?)\*\*/g, '$1')   // bold
      .replace(/\*(.+?)\*/g, '$1')       // italic
      .replace(/`(.+?)`/g, '$1')         // inline code
      .replace(/\|/g, ' ')               // table separators
      .replace(/[-─]+/g, '')             // table dividers
      .replace(/\[(.+?)\]\(.+?\)/g, '$1') // links
      .replace(/^\s*>\s*/gm, '')          // blockquotes
      .replace(/\n{2,}/g, '. ')          // paragraph breaks → pause
      .replace(/\n/g, ' ')
      .trim()

  const speak = useCallback((markdownText) => {
    if (!isSupported || !markdownText) return

    window.speechSynthesis.cancel()

    const clean = stripMarkdown(markdownText)
    const utterance = new SpeechSynthesisUtterance(clean)
    utterance.rate = rate
    utterance.pitch = pitch
    utterance.volume = DEFAULT_VOLUME

    if (selectedVoice) utterance.voice = selectedVoice

    utterance.onstart = () => { setIsPlaying(true); setIsPaused(false) }
    utterance.onend = () => { setIsPlaying(false); setIsPaused(false) }
    utterance.onerror = () => { setIsPlaying(false); setIsPaused(false) }
    utterance.onpause = () => setIsPaused(true)
    utterance.onresume = () => setIsPaused(false)

    utteranceRef.current = utterance
    window.speechSynthesis.speak(utterance)
  }, [isSupported, rate, pitch, selectedVoice])

  const pause = useCallback(() => {
    if (window.speechSynthesis.speaking) {
      window.speechSynthesis.pause()
    }
  }, [])

  const resume = useCallback(() => {
    if (window.speechSynthesis.paused) {
      window.speechSynthesis.resume()
    }
  }, [])

  const stop = useCallback(() => {
    window.speechSynthesis.cancel()
    setIsPlaying(false)
    setIsPaused(false)
  }, [])

  return {
    speak,
    pause,
    resume,
    stop,
    isPlaying,
    isPaused,
    isSupported,
    voices,
    selectedVoice,
    setSelectedVoice,
    rate,
    setRate,
    pitch,
    setPitch,
  }
}
