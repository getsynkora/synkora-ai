'use client';

import React, { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { Mic, Square, X, Check, Loader2 } from 'lucide-react';
import { useSpeechRecognition } from '../hooks/useSpeechRecognition';
import { Button } from '@/components/ui/Button';
import { cn } from '@/lib/utils';

interface VoiceInputModalProps {
  isOpen: boolean;
  onClose: () => void;
  onTranscript: (text: string) => void;
  language?: string;
}

/**
 * VoiceInputModal Component
 * ChatGPT-style voice input modal with Cancel/Done buttons
 * Keeps recording until user explicitly stops
 */
export function VoiceInputModal({
  isOpen,
  onClose,
  onTranscript,
  language = 'en-US',
}: VoiceInputModalProps) {
  const [localTranscript, setLocalTranscript] = useState('');
  const [isRecording, setIsRecording] = useState(false);

  const {
    isListening,
    transcript,
    interimTranscript,
    error,
    startListening,
    stopListening,
    resetTranscript,
    isSupported,
  } = useSpeechRecognition(language, true);

  // Auto-start recording when modal opens
  useEffect(() => {
    if (isOpen && isSupported && !isRecording) {
      resetTranscript();
      setLocalTranscript('');
      startListening();
      setIsRecording(true);
    }
  }, [isOpen, isSupported]);

  // Update local transcript as user speaks
  useEffect(() => {
    if (transcript) {
      setLocalTranscript(transcript);
    }
  }, [transcript]);

  const handleCancel = () => {
    if (isListening) {
      stopListening();
    }
    setIsRecording(false);
    setLocalTranscript('');
    resetTranscript();
    onClose();
  };

  const handleDone = () => {
    if (isListening) {
      stopListening();
    }
    setIsRecording(false);
    
    // Send the transcript to parent
    if (localTranscript.trim()) {
      onTranscript(localTranscript.trim());
    }
    
    setLocalTranscript('');
    resetTranscript();
    onClose();
  };

  const handleToggleRecording = () => {
    if (isListening) {
      stopListening();
      setIsRecording(false);
    } else {
      startListening();
      setIsRecording(true);
    }
  };

  if (!isOpen) return null;

  if (!isSupported) {
    return createPortal(
      <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4">
        <div className="bg-white rounded-2xl shadow-2xl p-8 max-w-md w-full mx-4">
          <div className="text-center">
            <div className="mx-auto w-16 h-16 bg-sand-deep rounded-full flex items-center justify-center mb-4">
              <X className="h-8 w-8 text-leaf" />
            </div>
            <h3 className="text-lg font-semibold text-ink mb-2">
              Voice Input Not Supported
            </h3>
            <p className="text-sm text-ink-soft mb-6">
              Your browser doesn't support voice input. Please try using Chrome, Edge, or Safari.
            </p>
            <Button onClick={onClose} className="w-full">
              Close
            </Button>
          </div>
        </div>
      </div>,
      document.body
    );
  }

  return createPortal(
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4 animate-in fade-in duration-200">
      <div className="bg-white rounded-2xl shadow-2xl p-8 max-w-lg w-full mx-4 animate-in zoom-in-95 duration-200">
        {/* Header */}
        <div className="text-center mb-8">
          <h3 className="text-2xl font-semibold text-ink mb-2">
            {isRecording ? 'Listening…' : 'Voice Input Paused'}
          </h3>
          <p className="text-sm text-ink-mute">
            {isRecording 
              ? 'Speak now, I\'m listening' 
              : 'Click the microphone to resume'}
          </p>
        </div>

        {/* Visual Feedback */}
        <div className="mb-8">
          {/* Microphone Button */}
          <div className="flex justify-center mb-6">
            <button
              onClick={handleToggleRecording}
              className={cn(
                'relative w-24 h-24 rounded-full transition-[color,background-color,border-color,box-shadow,opacity,transform] duration-300 shadow-lg',
                isRecording
                  ? 'bg-ink hover:bg-ink/85 motion-safe:animate-pulse'
                  : 'bg-leaf'
              )}
            >
              {isRecording ? (
                <Square className="h-10 w-10 text-white absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2" />
              ) : (
                <Mic className="h-10 w-10 text-white absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2" />
              )}
              
              {/* Pulsing rings when recording */}
              {isRecording && (
                <>
                  <span className="absolute inset-0 rounded-full bg-hotpink motion-safe:animate-ping opacity-75" />
                  <span className="absolute inset-0 rounded-full bg-hotpink motion-safe:animate-pulse opacity-50" />
                </>
              )}
            </button>
          </div>

          {/* Transcript Display */}
          <div className="min-h-[120px] max-h-[200px] overflow-y-auto bg-cream rounded-xl p-4 border-2 border-line">
            {localTranscript || interimTranscript ? (
              <div className="space-y-2">
                {localTranscript && (
                  <p className="text-ink leading-relaxed">
                    {localTranscript}
                  </p>
                )}
                {interimTranscript && (
                  <p className="text-ash italic leading-relaxed">
                    {interimTranscript}
                  </p>
                )}
              </div>
            ) : (
              <div className="flex items-center justify-center h-full text-ash">
                <div className="text-center">
                  {isRecording ? (
                    <>
                      <Loader2 className="h-8 w-8 motion-safe:animate-spin mx-auto mb-2" />
                      <p className="text-sm">Waiting for speech…</p>
                    </>
                  ) : (
                    <p className="text-sm">Click the microphone to start</p>
                  )}
                </div>
              </div>
            )}
          </div>

          {/* Error Message */}
          {error && (
            <div className="mt-4 p-3 bg-blush-wash border border-blush rounded-lg">
              <p className="text-sm text-danger">{error}</p>
            </div>
          )}
        </div>

        {/* Action Buttons */}
        <div className="flex gap-3">
          <Button
            onClick={handleCancel}
            variant="outline"
            className="flex-1 h-12 text-base font-medium"
          >
            <X className="h-5 w-5 mr-2" />
            Cancel
          </Button>
          <Button
            onClick={handleDone}
            disabled={!localTranscript.trim()}
            className={cn(
              'flex-1 h-12 text-base font-medium',
              localTranscript.trim()
                ? 'bg-leaf'
                : 'bg-taupe cursor-not-allowed'
            )}
          >
            <Check className="h-5 w-5 mr-2" />
            Done
          </Button>
        </div>

        {/* Helper Text */}
        <p className="text-xs text-ash text-center mt-4">
          {isRecording ? 'Recording will continue until you click Done or Cancel' : 'Paused - Click microphone to resume'}
        </p>
      </div>
    </div>,
    document.body
  );
}
