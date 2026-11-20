'use client';

import React, { useEffect } from 'react';
import { Mic, Square, Pause, Play } from 'lucide-react';
import { useVoiceRecording } from '../hooks/useVoiceRecording';
import { useSpeechRecognition } from '../hooks/useSpeechRecognition';
import { Button } from '@/components/ui/Button';
import { cn } from '@/lib/utils';

interface VoiceInputProps {
  onTranscript: (text: string) => void;
  onRecordingComplete?: (audioBlob: Blob) => void;
  className?: string;
  mode?: 'speech-to-text' | 'audio-recording';
  language?: string;
}

/**
 * VoiceInput Component
 * Provides voice input functionality with visual feedback
 * Supports both speech-to-text and audio recording modes
 */
export function VoiceInput({
  onTranscript,
  onRecordingComplete,
  className,
  mode = 'speech-to-text',
  language = 'en-US',
}: VoiceInputProps) {
  const {
    isRecording: isAudioRecording,
    isPaused: isAudioPaused,
    duration: audioDuration,
    audioBlob,
    error: audioError,
    startRecording: startAudioRecording,
    stopRecording: stopAudioRecording,
    pauseRecording: pauseAudioRecording,
    resumeRecording: resumeAudioRecording,
    clearRecording: clearAudioRecording,
    isSupported: isAudioSupported,
  } = useVoiceRecording();

  const {
    isListening,
    transcript,
    interimTranscript,
    error: speechError,
    startListening,
    stopListening,
    resetTranscript,
    isSupported: isSpeechSupported,
  } = useSpeechRecognition(language, true);

  const isRecording = mode === 'audio-recording' ? isAudioRecording : isListening;
  const isPaused = mode === 'audio-recording' ? isAudioPaused : false;
  const error = mode === 'audio-recording' ? audioError : speechError;
  const isSupported = mode === 'audio-recording' ? isAudioSupported : isSpeechSupported;

  // Handle transcript updates
  useEffect(() => {
    if (mode === 'speech-to-text' && transcript) {
      onTranscript(transcript);
    }
  }, [transcript, mode, onTranscript]);

  // Handle audio recording completion
  useEffect(() => {
    if (mode === 'audio-recording' && audioBlob && onRecordingComplete) {
      onRecordingComplete(audioBlob);
      clearAudioRecording();
    }
  }, [audioBlob, mode, onRecordingComplete, clearAudioRecording]);

  const handleStartStop = () => {
    if (isRecording) {
      if (mode === 'audio-recording') {
        stopAudioRecording();
      } else {
        stopListening();
      }
    } else {
      if (mode === 'audio-recording') {
        startAudioRecording();
      } else {
        resetTranscript();
        startListening();
      }
    }
  };

  const handlePauseResume = () => {
    if (mode === 'audio-recording') {
      if (isPaused) {
        resumeAudioRecording();
      } else {
        pauseAudioRecording();
      }
    }
  };

  const formatDuration = (seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  if (!isSupported) {
    return (
      <div className={cn('text-sm text-muted-foreground', className)}>
        Voice input is not supported in this browser
      </div>
    );
  }

  return (
    <div className={cn('flex items-center gap-2', className)}>
      {/* Main record/stop button */}
      <Button
        type="button"
        variant={isRecording ? 'secondary' : 'outline'}
        size="sm"
        onClick={handleStartStop}
        className={cn(
          'relative transition-[color,background-color,border-color,box-shadow,opacity,transform] w-10 h-10 p-0',
          isRecording && 'motion-safe:animate-pulse bg-ink hover:bg-danger text-white'
        )}
        title={isRecording ? 'Stop recording' : 'Start recording'}
      >
        {isRecording ? (
          <Square className="h-4 w-4" />
        ) : (
          <Mic className="h-4 w-4" />
        )}
      </Button>

      {/* Pause/Resume button (audio recording only) */}
      {mode === 'audio-recording' && isRecording && (
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={handlePauseResume}
          className="w-10 h-10 p-0"
          title={isPaused ? 'Resume recording' : 'Pause recording'}
        >
          {isPaused ? (
            <Play className="h-4 w-4" />
          ) : (
            <Pause className="h-4 w-4" />
          )}
        </Button>
      )}

      {/* Recording indicator and duration */}
      {isRecording && (
        <div className="flex items-center gap-2 text-sm">
          <div className="flex items-center gap-1">
            <div className="h-2 w-2 rounded-full bg-ink motion-safe:animate-pulse" />
            <span className="text-muted-foreground">
              {isPaused ? 'Paused' : 'Recording'}
            </span>
          </div>
          {mode === 'audio-recording' && (
            <span className="font-mono text-muted-foreground">
              {formatDuration(audioDuration)}
            </span>
          )}
        </div>
      )}

      {/* Interim transcript (speech-to-text only) */}
      {mode === 'speech-to-text' && isListening && interimTranscript && (
        <div className="flex-1 text-sm text-muted-foreground italic truncate">
          {interimTranscript}
        </div>
      )}

      {/* Error message */}
      {error && (
        <div className="text-sm text-destructive truncate max-w-xs">
          {error}
        </div>
      )}
    </div>
  );
}
