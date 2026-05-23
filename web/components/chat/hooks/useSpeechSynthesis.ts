'use client';

import { useState, useRef, useCallback, useEffect } from 'react';

export interface Voice {
  name: string;
  lang: string;
  default: boolean;
  localService: boolean;
  voiceURI: string;
}

export interface UseSpeechSynthesisReturn {
  speak: (text: string) => void;
  cancel: () => void;
  pause: () => void;
  resume: () => void;
  isSpeaking: boolean;
  isPaused: boolean;
  voices: Voice[];
  selectedVoice: Voice | null;
  setSelectedVoice: (voice: Voice | null) => void;
  rate: number;
  setRate: (rate: number) => void;
  pitch: number;
  setPitch: (pitch: number) => void;
  volume: number;
  setVolume: (volume: number) => void;
  isSupported: boolean;
}

/**
 * Hook for text-to-speech using the Web Speech API
 * Provides natural voice synthesis for text content
 */
export function useSpeechSynthesis(): UseSpeechSynthesisReturn {
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [isPaused, setIsPaused] = useState(false);
  const [voices, setVoices] = useState<Voice[]>([]);
  const [selectedVoice, setSelectedVoice] = useState<Voice | null>(null);
  const [rate, setRate] = useState(1);
  const [pitch, setPitch] = useState(1);
  const [volume, setVolume] = useState(1);

  const utteranceRef = useRef<SpeechSynthesisUtterance | null>(null);
  // Guard: set default voice only once to prevent selectedVoice → effect → setSelectedVoice loop
  const hasInitializedVoiceRef = useRef(false);

  // Check if Web Speech API is supported
  const isSupported =
    typeof window !== 'undefined' && 'speechSynthesis' in window;

  // Load available voices.
  // selectedVoice is intentionally NOT in the dependency array — including it
  // caused an infinite loop: setSelectedVoice → re-run effect → setSelectedVoice → …
  useEffect(() => {
    if (!isSupported) return;

    const loadVoices = () => {
      const availableVoices = window.speechSynthesis.getVoices();
      const voiceList: Voice[] = availableVoices.map((voice) => ({
        name: voice.name,
        lang: voice.lang,
        default: voice.default,
        localService: voice.localService,
        voiceURI: voice.voiceURI,
      }));

      setVoices(voiceList);

      // Set default voice only on the first successful load
      if (!hasInitializedVoiceRef.current && voiceList.length > 0) {
        hasInitializedVoiceRef.current = true;
        const englishVoice = voiceList.find((v) => v.lang.startsWith('en'));
        setSelectedVoice(englishVoice || voiceList[0]);
      }
    };

    loadVoices();

    // Some browsers load voices asynchronously
    if (window.speechSynthesis.onvoiceschanged !== undefined) {
      window.speechSynthesis.onvoiceschanged = loadVoices;
    }

    return () => {
      if (window.speechSynthesis.onvoiceschanged !== undefined) {
        window.speechSynthesis.onvoiceschanged = null;
      }
    };
   
  }, [isSupported]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (isSupported) {
        window.speechSynthesis.cancel();
      }
    };
  }, [isSupported]);

  const speak = useCallback(
    (text: string) => {
      if (!isSupported) {
        console.error('Speech synthesis is not supported');
        return;
      }

      // Cancel any ongoing speech
      window.speechSynthesis.cancel();

      const utterance = new SpeechSynthesisUtterance(text);
      
      // Set voice if selected
      if (selectedVoice) {
        const voice = window.speechSynthesis
          .getVoices()
          .find((v) => v.voiceURI === selectedVoice.voiceURI);
        if (voice) {
          utterance.voice = voice;
        }
      }

      // Set speech parameters
      utterance.rate = rate;
      utterance.pitch = pitch;
      utterance.volume = volume;

      // Event handlers
      utterance.onstart = () => {
        setIsSpeaking(true);
        setIsPaused(false);
      };

      utterance.onend = () => {
        setIsSpeaking(false);
        setIsPaused(false);
        utteranceRef.current = null;
      };

      utterance.onerror = (event) => {
        console.error('Speech synthesis error:', event);
        setIsSpeaking(false);
        setIsPaused(false);
        utteranceRef.current = null;
      };

      utterance.onpause = () => {
        setIsPaused(true);
      };

      utterance.onresume = () => {
        setIsPaused(false);
      };

      utteranceRef.current = utterance;
      window.speechSynthesis.speak(utterance);
    },
    [isSupported, selectedVoice, rate, pitch, volume]
  );

  const cancel = useCallback(() => {
    if (isSupported) {
      window.speechSynthesis.cancel();
      setIsSpeaking(false);
      setIsPaused(false);
      utteranceRef.current = null;
    }
  }, [isSupported]);

  const pause = useCallback(() => {
    if (isSupported && isSpeaking && !isPaused) {
      window.speechSynthesis.pause();
      setIsPaused(true);
    }
  }, [isSupported, isSpeaking, isPaused]);

  const resume = useCallback(() => {
    if (isSupported && isSpeaking && isPaused) {
      window.speechSynthesis.resume();
      setIsPaused(false);
    }
  }, [isSupported, isSpeaking, isPaused]);

  return {
    speak,
    cancel,
    pause,
    resume,
    isSpeaking,
    isPaused,
    voices,
    selectedVoice,
    setSelectedVoice,
    rate,
    setRate,
    pitch,
    setPitch,
    volume,
    setVolume,
    isSupported,
  };
}
