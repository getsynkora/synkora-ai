'use client';

import { useState, useEffect, useCallback } from 'react';
import { useProfile } from '@/hooks/useProfile';
import { AvatarUpload } from '@/components/profile/AvatarUpload';
import { toast } from 'react-hot-toast';
import { User, Mail, Phone, MapPin, Briefcase, Building2, Globe, FileText, Shield, Clock, Monitor, Smartphone, Laptop, AlertTriangle } from 'lucide-react';
import { apiClient } from '@/lib/api/client';

// ── Types ────────────────────────────────────────────────────────────────────

interface Session {
  session_id: string;
  created_at: string;
  ip_address: string | null;
  user_agent: string | null;
  is_current: boolean;
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function parseUserAgent(ua: string | null): { device: string; browser: string; os: string } {
  if (!ua) return { device: 'Unknown device', browser: 'Unknown browser', os: '' };

  let browser = 'Unknown browser';
  let os = '';

  // Browser detection (order matters — Edge/Opera include "Chrome" in their UA)
  if (/Edg\//.test(ua)) browser = 'Edge';
  else if (/OPR\/|Opera\//.test(ua)) browser = 'Opera';
  else if (/Firefox\//.test(ua)) browser = 'Firefox';
  else if (/Chrome\//.test(ua)) browser = 'Chrome';
  else if (/Safari\//.test(ua) && /Version\//.test(ua)) browser = 'Safari';
  else if (/MSIE|Trident/.test(ua)) browser = 'Internet Explorer';

  // OS detection
  if (/iPhone|iPad|iPod/.test(ua)) os = 'iOS';
  else if (/Android/.test(ua)) os = 'Android';
  else if (/Macintosh|Mac OS X/.test(ua)) os = 'macOS';
  else if (/Windows/.test(ua)) os = 'Windows';
  else if (/Linux/.test(ua)) os = 'Linux';

  const device = os ? `${browser} on ${os}` : browser;
  return { device, browser, os };
}

function DeviceIcon({ ua }: { ua: string | null }) {
  if (!ua) return <Monitor className="w-4 h-4 text-ash" />;
  if (/iPhone|iPod/.test(ua) || /Android.*Mobile/.test(ua)) {
    return <Smartphone className="w-4 h-4 text-ash" />;
  }
  if (/iPad|Android(?!.*Mobile)/.test(ua)) {
    return <Laptop className="w-4 h-4 text-ash" />;
  }
  return <Monitor className="w-4 h-4 text-ash" />;
}

function formatSessionDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export default function ProfilePage() {
  const { profile, loading, updateProfile, uploadAvatar } = useProfile();
  const [isEditing, setIsEditing] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [formData, setFormData] = useState({
    name: '',
    email: '',
    phone: '',
    location: '',
    company: '',
    job_title: '',
    website: '',
    bio: '',
  });

  // ── Active Sessions state ─────────────────────────────────────────────────
  const [sessions, setSessions] = useState<Session[]>([]);
  const [sessionsLoading, setSessionsLoading] = useState(true);
  const [revokingId, setRevokingId] = useState<string | null>(null);
  const [revokingAll, setRevokingAll] = useState(false);

  const fetchSessions = useCallback(async () => {
    setSessionsLoading(true);
    try {
      const res = await apiClient.request('GET', '/console/api/me/sessions');
      const data = (res as any)?.data ?? res;
      setSessions(data?.sessions ?? []);
    } catch {
      toast.error('Failed to load sessions');
    } finally {
      setSessionsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchSessions();
  }, [fetchSessions]);

  const handleRevokeSession = async (sessionId: string) => {
    // Optimistic removal
    setSessions(prev => prev.filter(s => s.session_id !== sessionId));
    setRevokingId(sessionId);
    try {
      await apiClient.request('DELETE', `/console/api/me/sessions/${sessionId}`);
      toast.success('Session revoked');
    } catch {
      toast.error('Failed to revoke session');
      // Restore on failure
      fetchSessions();
    } finally {
      setRevokingId(null);
    }
  };

  const handleRevokeAllSessions = async () => {
    setRevokingAll(true);
    // Optimistic: keep only current session
    setSessions(prev => prev.filter(s => s.is_current));
    try {
      await apiClient.request('DELETE', '/console/api/me/sessions');
      toast.success('All other sessions revoked');
    } catch {
      toast.error('Failed to revoke sessions');
      fetchSessions();
    } finally {
      setRevokingAll(false);
    }
  };

  useEffect(() => {
    if (profile) {
      setFormData({
        name: profile.name || '',
        email: profile.email || '',
        phone: profile.phone || '',
        location: profile.location || '',
        company: profile.company || '',
        job_title: profile.job_title || '',
        website: profile.website || '',
        bio: profile.bio || '',
      });
    }
  }, [profile]);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  const handleSave = async () => {
    setIsSaving(true);
    try {
      await updateProfile(formData);
      setIsEditing(false);
      toast.success('Profile updated successfully');
    } catch {
      toast.error('Failed to update profile');
    } finally {
      setIsSaving(false);
    }
  };

  const handleCancel = () => {
    if (profile) {
      setFormData({
        name: profile.name || '',
        email: profile.email || '',
        phone: profile.phone || '',
        location: profile.location || '',
        company: profile.company || '',
        job_title: profile.job_title || '',
        website: profile.website || '',
        bio: profile.bio || '',
      });
    }
    setIsEditing(false);
  };

  const handleAvatarUpload = async (file: File) => {
    try {
      const avatarUrl = await uploadAvatar(file);
      toast.success('Avatar uploaded successfully');
      return avatarUrl;
    } catch (error) {
      toast.error('Failed to upload avatar');
      throw error;
    }
  };

  if (loading) {
    return (
      <div className="dashboard-settings-page flex min-h-screen items-center justify-center">
        <div className="motion-safe:animate-spin rounded-full h-12 w-12 border-b-2 border-danger"></div>
      </div>
    );
  }

  return (
    <div className="dashboard-settings-page min-h-screen">
      <div className="max-w-5xl mx-auto px-4 md:px-6 py-4 md:py-6">
        {/* Header */}
        <div className="mb-6">
          <h1 className="text-2xl md:text-3xl font-extrabold text-ink tracking-tight">Profile Settings</h1>
          <p className="mt-1 text-sm text-ink-soft">Manage your personal information and preferences</p>
        </div>

        {/* Main Content */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
          {/* Left Sidebar - Profile Card */}
          <div className="lg:col-span-1">
            <div className="bg-white rounded-lg shadow-sm border border-line overflow-hidden">
              <div className="h-20 bg-sand-deep"></div>
              <div className="px-5 pb-5">
                <div className="flex flex-col items-center -mt-10">
                  <AvatarUpload
                    currentAvatar={profile?.avatar_url}
                    onUpload={handleAvatarUpload}
                  />
                  <h2 className="mt-3 text-lg font-semibold text-ink">{profile?.name || 'User'}</h2>
                  <p className="text-xs text-ink-mute">{profile?.email}</p>
                  {profile?.job_title && (
                    <p className="mt-2 text-xs text-ink-soft">{profile.job_title}</p>
                  )}
                  {profile?.company && (
                    <p className="text-xs text-ink-mute">{profile.company}</p>
                  )}
                </div>

                {/* Quick Stats */}
                <div className="mt-5 pt-5 border-t border-line space-y-2.5">
                  <div className="flex items-center text-xs">
                    <Shield className="w-3.5 h-3.5 text-leaf mr-2" />
                    <span className="text-ink-soft">
                      2FA: <span className="font-medium text-ink">
                        {profile?.two_factor_enabled ? 'Enabled' : 'Disabled'}
                      </span>
                    </span>
                  </div>
                  {profile?.last_login_at && (
                    <div className="flex items-center text-xs">
                      <Clock className="w-3.5 h-3.5 text-leaf mr-2" />
                      <span className="text-ink-soft">
                        Last login: <span className="font-medium text-ink">
                          {new Date(profile.last_login_at).toLocaleDateString()}
                        </span>
                      </span>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>

          {/* Right Content - Form */}
          <div className="lg:col-span-2">
            <div className="bg-white rounded-lg shadow-sm border border-line">
              {/* Form Header */}
              <div className="px-5 py-3.5 border-b border-line flex items-center justify-between">
                <h3 className="text-base font-semibold text-ink">Personal Information</h3>
                {!isEditing ? (
                  <button
                    onClick={() => setIsEditing(true)}
                    className="px-3 py-1.5 bg-ink text-white rounded-lg hover:from-danger hover:to-danger transition-[color,background-color,border-color,box-shadow,opacity,transform] text-xs font-medium shadow-sm"
                  >
                    Edit Profile
                  </button>
                ) : (
                  <div className="flex gap-2">
                    <button
                      onClick={handleCancel}
                      className="px-3 py-1.5 border border-taupe text-ink-soft rounded-lg hover:bg-cream transition-colors text-xs font-medium"
                    >
                      Cancel
                    </button>
                    <button
                      onClick={handleSave}
                      disabled={isSaving}
                      className="px-3 py-1.5 bg-ink text-white rounded-lg hover:from-danger hover:to-danger transition-[color,background-color,border-color,box-shadow,opacity,transform] text-xs font-medium shadow-sm disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      {isSaving ? 'Saving…' : 'Save Changes'}
                    </button>
                  </div>
                )}
              </div>

              {/* Form Content */}
              <div className="p-5">
                <form className="space-y-5">
                  {/* Basic Information */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <label className="block text-xs font-medium text-ink-soft mb-1.5">
                        Full Name <span className="text-leaf">*</span>
                      </label>
                      <div className="relative">
                        <User className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-ash" />
                        <input
                          type="text"
                          name="name"
                          value={formData.name}
                          onChange={handleInputChange}
                          disabled={!isEditing}
                          required
                          className="w-full pl-10 pr-3 py-2 text-sm border border-taupe rounded-lg focus:ring-2 focus:ring-ink focus:border-ink disabled:bg-cream disabled:text-ink-mute transition-colors"
                          placeholder="Enter your full name"
                        />
                      </div>
                    </div>

                    <div>
                      <label className="block text-xs font-medium text-ink-soft mb-1.5">
                        Email Address <span className="text-leaf">*</span>
                      </label>
                      <div className="relative">
                        <Mail className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-ash" />
                        <input
                          type="email"
                          name="email"
                          value={formData.email}
                          onChange={handleInputChange}
                          disabled={!isEditing}
                          required
                          className="w-full pl-10 pr-3 py-2 text-sm border border-taupe rounded-lg focus:ring-2 focus:ring-ink focus:border-ink disabled:bg-cream disabled:text-ink-mute transition-colors"
                          placeholder="your.email@example.com"
                        />
                      </div>
                    </div>

                    <div>
                      <label className="block text-xs font-medium text-ink-soft mb-1.5">Phone Number</label>
                      <div className="relative">
                        <Phone className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-ash" />
                        <input
                          type="tel"
                          name="phone"
                          value={formData.phone}
                          onChange={handleInputChange}
                          disabled={!isEditing}
                          className="w-full pl-10 pr-3 py-2 text-sm border border-taupe rounded-lg focus:ring-2 focus:ring-ink focus:border-ink disabled:bg-cream disabled:text-ink-mute transition-colors"
                          placeholder="+1 (555) 000-0000"
                        />
                      </div>
                    </div>

                    <div>
                      <label className="block text-xs font-medium text-ink-soft mb-1.5">Location</label>
                      <div className="relative">
                        <MapPin className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-ash" />
                        <input
                          type="text"
                          name="location"
                          value={formData.location}
                          onChange={handleInputChange}
                          disabled={!isEditing}
                          className="w-full pl-10 pr-3 py-2 text-sm border border-taupe rounded-lg focus:ring-2 focus:ring-ink focus:border-ink disabled:bg-cream disabled:text-ink-mute transition-colors"
                          placeholder="City, Country"
                        />
                      </div>
                    </div>
                  </div>

                  {/* Professional Information */}
                  <div className="pt-5 border-t border-line">
                    <h4 className="text-sm font-semibold text-ink mb-3.5">Professional Details</h4>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div>
                        <label className="block text-xs font-medium text-ink-soft mb-1.5">Company</label>
                        <div className="relative">
                          <Building2 className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-ash" />
                          <input
                            type="text"
                            name="company"
                            value={formData.company}
                            onChange={handleInputChange}
                            disabled={!isEditing}
                            className="w-full pl-10 pr-3 py-2 text-sm border border-taupe rounded-lg focus:ring-2 focus:ring-ink focus:border-ink disabled:bg-cream disabled:text-ink-mute transition-colors"
                            placeholder="Your company name"
                          />
                        </div>
                      </div>

                      <div>
                        <label className="block text-xs font-medium text-ink-soft mb-1.5">Job Title</label>
                        <div className="relative">
                          <Briefcase className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-ash" />
                          <input
                            type="text"
                            name="job_title"
                            value={formData.job_title}
                            onChange={handleInputChange}
                            disabled={!isEditing}
                            className="w-full pl-10 pr-3 py-2 text-sm border border-taupe rounded-lg focus:ring-2 focus:ring-ink focus:border-ink disabled:bg-cream disabled:text-ink-mute transition-colors"
                            placeholder="Your role"
                          />
                        </div>
                      </div>

                      <div className="md:col-span-2">
                        <label className="block text-xs font-medium text-ink-soft mb-1.5">Website</label>
                        <div className="relative">
                          <Globe className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-ash" />
                          <input
                            type="url"
                            name="website"
                            value={formData.website}
                            onChange={handleInputChange}
                            disabled={!isEditing}
                            className="w-full pl-10 pr-3 py-2 text-sm border border-taupe rounded-lg focus:ring-2 focus:ring-ink focus:border-ink disabled:bg-cream disabled:text-ink-mute transition-colors"
                            placeholder="https://yourwebsite.com"
                          />
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Bio Section */}
                  <div className="pt-5 border-t border-line">
                    <h4 className="text-sm font-semibold text-ink mb-3.5">About You</h4>
                    <div>
                      <label className="block text-xs font-medium text-ink-soft mb-1.5">Bio</label>
                      <div className="relative">
                        <FileText className="absolute left-3 top-3 w-4 h-4 text-ash" />
                        <textarea
                          name="bio"
                          value={formData.bio}
                          onChange={handleInputChange}
                          disabled={!isEditing}
                          rows={4}
                          className="w-full pl-10 pr-3 py-2 text-sm border border-taupe rounded-lg focus:ring-2 focus:ring-ink focus:border-ink disabled:bg-cream disabled:text-ink-mute transition-colors resize-none"
                          placeholder="Tell us about yourself…"
                        />
                      </div>
                    </div>
                  </div>
                </form>
              </div>
            </div>
          </div>
        </div>

        {/* Active Sessions — full-width below the two-column grid */}
        <div className="mt-5">
          <div className="bg-white rounded-lg shadow-sm border border-line">
            {/* Card header */}
            <div className="px-5 py-3.5 border-b border-line">
              <h3 className="text-base font-semibold text-ink">Active Sessions</h3>
              <p className="text-xs text-ink-mute mt-0.5">Manage devices and sessions signed into your account</p>
            </div>

            {/* Card body */}
            <div className="p-5">
              {sessionsLoading ? (
                <div className="flex items-center justify-center py-8">
                  <div className="motion-safe:animate-spin rounded-full h-6 w-6 border-b-2 border-danger" />
                </div>
              ) : sessions.length === 0 ? (
                <p className="text-sm text-ink-mute text-center py-6">No active sessions found.</p>
              ) : (
                <>
                  <ul className="divide-y divide-sand">
                    {sessions.map(session => {
                      const { device } = parseUserAgent(session.user_agent);
                      const isRevoking = revokingId === session.session_id;
                      return (
                        <li key={session.session_id} className="py-3 flex items-start justify-between gap-3">
                          <div className="flex items-start gap-3 min-w-0">
                            <div className="mt-0.5 flex-shrink-0">
                              <DeviceIcon ua={session.user_agent} />
                            </div>
                            <div className="min-w-0">
                              <div className="flex items-center gap-2 flex-wrap">
                                <span className="text-sm font-medium text-ink truncate">{device}</span>
                                {session.is_current && (
                                  <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-leaf-wash text-forest border border-mint">
                                    Current session
                                  </span>
                                )}
                              </div>
                              <div className="mt-0.5 flex flex-wrap gap-x-3 gap-y-0.5">
                                <span className="text-xs text-ink-mute">
                                  {session.ip_address ?? 'Unknown location'}
                                </span>
                                <span className="text-xs text-ash">
                                  Signed in {formatSessionDate(session.created_at)}
                                </span>
                              </div>
                            </div>
                          </div>

                          {!session.is_current && (
                            <button
                              onClick={() => handleRevokeSession(session.session_id)}
                              disabled={isRevoking || revokingAll}
                              className="flex-shrink-0 inline-flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-medium text-danger border border-blush rounded-lg hover:bg-blush-wash transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                            >
                              {isRevoking ? (
                                <>
                                  <div className="motion-safe:animate-spin rounded-full h-3 w-3 border-b border-danger" />
                                  Revoking...
                                </>
                              ) : (
                                <>
                                  <AlertTriangle className="w-3 h-3" />
                                  Revoke
                                </>
                              )}
                            </button>
                          )}
                        </li>
                      );
                    })}
                  </ul>

                  {/* Footer: revoke all other sessions */}
                  {sessions.filter(s => !s.is_current).length > 0 && (
                    <div className="mt-4 pt-4 border-t border-sand flex justify-end">
                      <button
                        onClick={handleRevokeAllSessions}
                        disabled={revokingAll}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-danger bg-blush-wash border border-blush rounded-lg hover:bg-blush-wash transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        {revokingAll ? (
                          <>
                            <div className="motion-safe:animate-spin rounded-full h-3 w-3 border-b border-danger" />
                            Revoking all...
                          </>
                        ) : (
                          <>
                            <AlertTriangle className="w-3 h-3" />
                            Revoke all other sessions
                          </>
                        )}
                      </button>
                    </div>
                  )}

                  {/* Empty other-sessions state */}
                  {sessions.filter(s => !s.is_current).length === 0 && !sessionsLoading && (
                    <p className="mt-3 text-xs text-ash text-center">No other active sessions.</p>
                  )}
                </>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
