'use client';

import React, { useEffect } from 'react';
import { Volume2, VolumeX, Pause, Play, Square } from 'lucide-react';
import { useSpeechSynthesis } from '../hooks/useSpeechSynthesis';
import { Button } from '@/components/ui/Button';
import { cn } from '@/lib/utils';

interface VoicePlayerProps {
  text: string;
  autoPlay?: boolean;
  className?: string;
  onPlaybackComplete?: () => void;
  compact?: boolean;
}

/**
 * VoicePlayer Component
 * Provides text-to-speech playback with controls
 * Uses Web Speech API for voice synthesis
 */
export function VoicePlayer({
  text,
  autoPlay = false,
  className,
  onPlaybackComplete,
  compact = false,
}: VoicePlayerProps) {
  const {
    speak,
    cancel,
    pause,
    resume,
    isSpeaking,
    isPaused,
    isSupported,
  } = useSpeechSynthesis();

  // Auto-play if enabled
  useEffect(() => {
    if (autoPlay && text && isSupported) {
      speak(text);
    }
  }, [autoPlay, text, isSupported, speak]);

  // Handle playback completion
  useEffect(() => {
    if (!isSpeaking && !isPaused && onPlaybackComplete) {
      onPlaybackComplete();
    }
  }, [isSpeaking, isPaused, onPlaybackComplete]);

  const handlePlayPause = () => {
    if (isSpeaking) {
      if (isPaused) {
        resume();
      } else {
        pause();
      }
    } else {
      speak(text);
    }
  };

  const handleStop = () => {
    cancel();
  };

  if (!isSupported) {
    if (compact) return null;
    return (
      <div className={cn('text-sm text-muted-foreground', className)}>
        <VolumeX className="h-4 w-4 inline mr-1" />
        Voice playback not supported
      </div>
    );
  }

  // Compact mode - single icon button
  if (compact) {
    return (
      <button
        type="button"
        onClick={handlePlayPause}
        className={cn(
          'p-1.5 rounded transition-colors',
          isSpeaking && !isPaused
            ? 'text-primary bg-primary/10'
            : 'text-ash hover:text-ink-soft hover:bg-sand',
          className
        )}
        title={isSpeaking ? (isPaused ? 'Resume' : 'Pause') : 'Listen'}
      >
        {isSpeaking && !isPaused ? (
          <Pause className="h-3.5 w-3.5" />
        ) : (
          <Volume2 className="h-3.5 w-3.5" />
        )}
      </button>
    );
  }

  return (
    <div className={cn('flex items-center gap-2', className)}>
      {/* Play/Pause button */}
      <Button
        type="button"
        variant="ghost"
        size="sm"
        onClick={handlePlayPause}
        className="h-8 w-8 p-0"
        title={isSpeaking ? (isPaused ? 'Resume' : 'Pause') : 'Play'}
      >
        {isSpeaking && !isPaused ? (
          <Pause className="h-4 w-4" />
        ) : (
          <Play className="h-4 w-4" />
        )}
      </Button>

      {/* Stop button (only show when playing) */}
      {isSpeaking && (
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={handleStop}
          className="h-8 w-8 p-0"
          title="Stop"
        >
          <Square className="h-4 w-4" />
        </Button>
      )}

      {/* Speaking indicator */}
      {isSpeaking && !isPaused && (
        <div className="flex items-center gap-1 text-sm text-muted-foreground">
          <Volume2 className="h-4 w-4 motion-safe:animate-pulse" />
          <span>Speaking…</span>
        </div>
      )}

      {/* Paused indicator */}
      {isPaused && (
        <div className="flex items-center gap-1 text-sm text-muted-foreground">
          <Volume2 className="h-4 w-4" />
          <span>Paused</span>
        </div>
      )}
    </div>
  );
}
