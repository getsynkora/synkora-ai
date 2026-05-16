import { apiClient } from './http';
import { secureStorage } from '../auth/secure-storage';

export interface ChatPageConfig {
  branding?: {
    logo_url?: string;
    company_name?: string;
    tagline?: string;
    favicon_url?: string;
  };
  colors?: {
    primary?: string;
    secondary?: string;
    background?: string;
    text_primary?: string;
    text_secondary?: string;
    border?: string;
    header_bg?: string;
    sidebar_bg?: string;
  };
  marketing?: {
    hero_title?: string;
    hero_description?: string;
    hero_image_url?: string;
    features?: Array<{
      icon?: string;
      title: string;
      description: string;
    }>;
    cta_text?: string;
    cta_url?: string;
    footer_text?: string;
    footer_links?: Array<{
      text: string;
      url: string;
    }>;
  };
  seo?: {
    title?: string;
    description?: string;
    keywords?: string[];
    og_image?: string;
  };
}

export interface ChatConfigResponse {
  agent_id: string;
  agent_name: string;
  agent_type: string;
  description: string;
  has_custom_config: boolean;
  chat_page_config: ChatPageConfig | null;
}

export async function getChatConfig(agentId: string): Promise<ChatConfigResponse> {
  const response = await apiClient.request('GET', `/api/v1/agents/${agentId}/chat-config`);
  return response;
}

export async function updateChatConfig(
  agentId: string,
  config: ChatPageConfig
): Promise<ChatConfigResponse> {
  const response = await apiClient.request('PUT', `/api/v1/agents/${agentId}/chat-config`, {
    chat_page_config: config
  });
  return response;
}

export interface ImageUploadResponse {
  message: string;
  url: string;
  s3_key: string;
  image_type: string;
}

export async function uploadChatImage(
  agentId: string,
  imageType: 'logo' | 'favicon',
  file: File
): Promise<ImageUploadResponse> {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('image_type', imageType);

  const token = secureStorage.getAccessToken()
  const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/v1/agents/${agentId}/chat-config/upload-image`, {
    method: 'POST',
    headers: {
      ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
    },
    credentials: 'include',
    body: formData,
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to upload image');
  }

  return response.json();
}

export async function deleteChatImage(
  agentId: string,
  s3Key: string
): Promise<{ message: string; s3_key: string }> {
  const response = await apiClient.request(
    'DELETE',
    `/api/v1/agents/${agentId}/chat-config/delete-image?s3_key=${encodeURIComponent(s3Key)}`
  );
  return response;
}