'use client';

import React from 'react';
import { OktaTenant } from '@/types/okta-sso';

interface OktaTenantCardProps {
  tenant: OktaTenant;
  onEdit: () => void;
  onDelete: () => void;
  onTest: () => void;
}

export const OktaTenantCard: React.FC<OktaTenantCardProps> = ({
  tenant,
  onEdit,
  onDelete,
  onTest,
}) => {
  return (
    <div className="bg-white dark:bg-ink rounded-lg border border-line dark:border-ink-soft p-6 hover:shadow-md transition-shadow">
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-2">
            <h3 className="text-lg font-semibold text-ink dark:text-white">
              {tenant.okta_domain}
            </h3>
            <span
              className={`px-2 py-1 text-xs font-medium rounded-full ${
                tenant.is_active
                  ? 'bg-leaf-wash text-forest dark:bg-forest dark:text-mint'
                  : 'bg-sand text-ink dark:bg-ink-soft dark:text-taupe'
              }`}
            >
              {tenant.is_active ? 'Active' : 'Inactive'}
            </span>
          </div>
          
          <div className="space-y-1 text-sm text-ink-soft dark:text-ash">
            <p>
              <span className="font-medium">Tenant ID:</span> {tenant.tenant_id}
            </p>
            <p>
              <span className="font-medium">Client ID:</span>{' '}
              {tenant.client_id.substring(0, 20)}...
            </p>
          </div>

          {tenant.updated_at && (
            <p className="text-xs text-ash dark:text-ink-mute mt-2">
              Last updated: {new Date(tenant.updated_at).toLocaleDateString()}
            </p>
          )}
        </div>

        <div className="flex items-center gap-2 ml-4">
          <button
            onClick={onTest}
            className="px-3 py-1.5 text-sm font-medium text-azure hover:text-azure dark:text-steel dark:hover:text-steel hover:bg-sky-wash dark:hover:bg-azure/20 rounded-md transition-colors"
          >
            Test
          </button>
          <button
            onClick={onEdit}
            className="px-3 py-1.5 text-sm font-medium text-ink-soft hover:text-ink dark:text-taupe dark:hover:text-white hover:bg-sand dark:hover:bg-ink-soft rounded-md transition-colors"
          >
            Edit
          </button>
          <button
            onClick={onDelete}
            className="px-3 py-1.5 text-sm font-medium text-danger hover:text-danger dark:text-hotpink dark:hover:text-blush hover:bg-blush-wash dark:hover:bg-wine/20 rounded-md transition-colors"
          >
            Delete
          </button>
        </div>
      </div>
    </div>
  );
};
