'use client';

import { useState } from 'react';
import { Profile } from '@/types/profile';

interface ProfileFormProps {
  profile: Profile | null;
  onSubmit: (data: Partial<Profile>) => Promise<void>;
  onCancel?: () => void;
}

export function ProfileForm({ profile, onSubmit, onCancel }: ProfileFormProps) {
  const [formData, setFormData] = useState({
    name: profile?.name || '',
    email: profile?.email || '',
    phone: profile?.phone || '',
    bio: profile?.bio || '',
    company: profile?.company || '',
    job_title: profile?.job_title || '',
    location: profile?.location || '',
    website: profile?.website || '',
  });
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);

    try {
      await onSubmit(formData);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update profile');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      {error && (
        <div className="bg-blush-wash border border-blush text-danger px-4 py-3 rounded">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Name */}
        <div>
          <label htmlFor="name" className="block text-sm font-medium text-ink-soft mb-2">
            Full Name *
          </label>
          <input
            type="text"
            id="name"
            name="name"
            value={formData.name}
            onChange={handleChange}
            required
            className="w-full px-3 py-2 border border-taupe rounded-md focus:outline-none focus:ring-2 focus:ring-azure"
          />
        </div>

        {/* Email */}
        <div>
          <label htmlFor="email" className="block text-sm font-medium text-ink-soft mb-2">
            Email *
          </label>
          <input
            type="email"
            id="email"
            name="email"
            value={formData.email}
            onChange={handleChange}
            required
            className="w-full px-3 py-2 border border-taupe rounded-md focus:outline-none focus:ring-2 focus:ring-azure"
          />
        </div>

        {/* Phone */}
        <div>
          <label htmlFor="phone" className="block text-sm font-medium text-ink-soft mb-2">
            Phone
          </label>
          <input
            type="tel"
            id="phone"
            name="phone"
            value={formData.phone}
            onChange={handleChange}
            className="w-full px-3 py-2 border border-taupe rounded-md focus:outline-none focus:ring-2 focus:ring-azure"
          />
        </div>

        {/* Company */}
        <div>
          <label htmlFor="company" className="block text-sm font-medium text-ink-soft mb-2">
            Company
          </label>
          <input
            type="text"
            id="company"
            name="company"
            value={formData.company}
            onChange={handleChange}
            className="w-full px-3 py-2 border border-taupe rounded-md focus:outline-none focus:ring-2 focus:ring-azure"
          />
        </div>

        {/* Job Title */}
        <div>
          <label htmlFor="job_title" className="block text-sm font-medium text-ink-soft mb-2">
            Job Title
          </label>
          <input
            type="text"
            id="job_title"
            name="job_title"
            value={formData.job_title}
            onChange={handleChange}
            className="w-full px-3 py-2 border border-taupe rounded-md focus:outline-none focus:ring-2 focus:ring-azure"
          />
        </div>

        {/* Location */}
        <div>
          <label htmlFor="location" className="block text-sm font-medium text-ink-soft mb-2">
            Location
          </label>
          <input
            type="text"
            id="location"
            name="location"
            value={formData.location}
            onChange={handleChange}
            placeholder="City, Country"
            className="w-full px-3 py-2 border border-taupe rounded-md focus:outline-none focus:ring-2 focus:ring-azure"
          />
        </div>

        {/* Website */}
        <div className="md:col-span-2">
          <label htmlFor="website" className="block text-sm font-medium text-ink-soft mb-2">
            Website
          </label>
          <input
            type="url"
            id="website"
            name="website"
            value={formData.website}
            onChange={handleChange}
            placeholder="https://example.com"
            className="w-full px-3 py-2 border border-taupe rounded-md focus:outline-none focus:ring-2 focus:ring-azure"
          />
        </div>

        {/* Bio */}
        <div className="md:col-span-2">
          <label htmlFor="bio" className="block text-sm font-medium text-ink-soft mb-2">
            Bio
          </label>
          <textarea
            id="bio"
            name="bio"
            value={formData.bio}
            onChange={handleChange}
            rows={4}
            placeholder="Tell us about yourself…"
            className="w-full px-3 py-2 border border-taupe rounded-md focus:outline-none focus:ring-2 focus:ring-azure"
          />
        </div>
      </div>

      {/* Actions */}
      <div className="flex justify-end space-x-3 pt-4 border-t">
        {onCancel && (
          <button
            type="button"
            onClick={onCancel}
            disabled={isSubmitting}
            className="px-4 py-2 border border-taupe rounded-md text-ink-soft hover:bg-cream disabled:opacity-50"
          >
            Cancel
          </button>
        )}
        <button
          type="submit"
          disabled={isSubmitting}
          className="px-4 py-2 bg-azure text-white rounded-md hover:bg-azure disabled:opacity-50"
        >
          {isSubmitting ? 'Saving…' : 'Save Changes'}
        </button>
      </div>
    </form>
  );
}
