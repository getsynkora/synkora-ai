'use client';

import { useState, useRef, useEffect } from 'react';
import Image from 'next/image';
import { Camera } from 'lucide-react';

interface AvatarUploadProps {
  currentAvatar?: string;
  onUpload: (file: File) => Promise<string>;
  onRemove?: () => Promise<void>;
}

export function AvatarUpload({ currentAvatar, onUpload}: AvatarUploadProps) {
  const [preview, setPreview] = useState<string | null>(currentAvatar || null);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Sync preview with currentAvatar prop changes
  useEffect(() => {
    if (currentAvatar) {
      setPreview(currentAvatar);
    }
  }, [currentAvatar]);

  // Check if URL is external (HTTP/HTTPS) - use regular img tag for external URLs
  const isExternalUrl = (url: string) => {
    return url.startsWith('http://') || url.startsWith('https://');
  };

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // Validate file type
    if (!file.type.startsWith('image/')) {
      setError('Please select an image file');
      return;
    }

    // Validate file size (max 5MB)
    if (file.size > 5 * 1024 * 1024) {
      setError('Image size must be less than 5MB');
      return;
    }

    setError(null);
    setIsUploading(true);

    try {
      // Create preview
      const reader = new FileReader();
      reader.onloadend = () => {
        setPreview(reader.result as string);
      };
      reader.readAsDataURL(file);

      // Upload file
      await onUpload(file);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to upload avatar');
      setPreview(currentAvatar || null);
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <div className="relative inline-block">
      {/* Avatar Preview */}
      <div className="relative group">
        <div className="w-24 h-24 rounded-full overflow-hidden bg-line flex items-center justify-center ring-4 ring-white shadow-lg">
          {preview ? (
            isExternalUrl(preview) ? (
              // Use regular img tag for external URLs (presigned URLs with query parameters)
              <img
                src={preview}
                alt="Avatar"
                width={96}
                height={96}
                className="w-full h-full object-cover"
              />
            ) : (
              // Use Next.js Image for relative/local URLs
              <Image
                src={preview}
                alt="Avatar"
                width={96}
                height={96}
                className="object-cover"
              />
            )
          ) : (
            <svg aria-hidden="true"
              className="w-12 h-12 text-ash"
              fill="currentColor"
              viewBox="0 0 20 20"
            >
              <path
                fillRule="evenodd"
                d="M10 9a3 3 0 100-6 3 3 0 000 6zm-7 9a7 7 0 1114 0H3z"
                clipRule="evenodd"
              />
            </svg>
          )}
        </div>
        
        {/* Upload Button Overlay */}
        <button
          type="button"
          onClick={() => fileInputRef.current?.click()}
          disabled={isUploading}
          className="absolute bottom-0 right-0 p-2 bg-leaf text-white rounded-full hover:bg-forest disabled:opacity-50 shadow-lg transition-[color,background-color,border-color,box-shadow,opacity,transform] duration-200 hover:scale-110"
          title="Change avatar"
        >
          <Camera className="w-4 h-4" />
        </button>

        {isUploading && (
          <div className="absolute inset-0 bg-black bg-opacity-50 rounded-full flex items-center justify-center">
            <div className="motion-safe:animate-spin rounded-full h-8 w-8 border-b-2 border-white"></div>
          </div>
        )}
      </div>

      {/* Hidden File Input */}
      <input
        ref={fileInputRef}
        type="file"
        accept="image/*"
        onChange={handleFileSelect}
        className="hidden"
        disabled={isUploading}
      />

      {/* Error Message */}
      {error && (
        <p className="mt-2 text-xs text-danger text-center">{error}</p>
      )}
    </div>
  );
}
