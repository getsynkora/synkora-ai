'use client';

import { TeamMember, UserRole} from '@/types/team';

interface TeamMembersListProps {
  members: TeamMember[];
  currentUserId: string;
  onRemoveMember: (accountId: string) => Promise<void>;
  onUpdateRole: (accountId: string, role: UserRole) => Promise<void>;
  canManageTeam: boolean;
}

export function TeamMembersList({
  members: rawMembers,
  currentUserId,
  onRemoveMember,
  onUpdateRole,
  canManageTeam,
}: TeamMembersListProps) {
  // Transform API response to match TypeScript interface
  const members = rawMembers.map((m: any) => ({
    ...m,
    name: m.account_name || m.name,
    email: m.account_email || m.email,
    avatar_url: m.account_avatar_url || m.avatar_url,
  }));

  const getRoleBadgeColor = (role: UserRole) => {
    const colorMap: Record<UserRole, string> = {
      owner: 'bg-blush-wash text-wine',
      admin: 'bg-sky-wash text-azure',
      editor: 'bg-leaf-wash text-forest',
      member: 'bg-sand text-ink',
    };
    return colorMap[role] || 'bg-sand text-ink';
  };

  const handleRoleChange = async (accountId: string, newRole: string) => {
    await onUpdateRole(accountId, newRole as UserRole);
  };

  const handleRemove = async (accountId: string, memberName: string) => {
    if (confirm(`Are you sure you want to remove ${memberName} from the team?`)) {
      await onRemoveMember(accountId);
    }
  };

  return (
    <div className="bg-white shadow rounded-lg overflow-hidden">
      <div className="px-6 py-4 border-b border-line">
        <h3 className="text-lg font-medium text-ink">Team Members</h3>
        <p className="mt-1 text-sm text-ink-mute">
          {members.length} {members.length === 1 ? 'member' : 'members'}
        </p>
      </div>

      <ul className="divide-y divide-line">
        {members.map((member) => {
          const isCurrentUser = member.account_id === currentUserId;
          const isOwner = member.role === 'owner';
          const canEdit = canManageTeam && !isOwner && !isCurrentUser;

          return (
            <li key={member.account_id} className="px-6 py-4 hover:bg-cream">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-4 flex-1">
                  {/* Avatar */}
                  <div className="flex-shrink-0">
                    {member.avatar_url ? (
                      <img
                        src={member.avatar_url}
                        alt={member.name}
                        className="h-10 w-10 rounded-full"
                      />
                    ) : (
                      <div className="h-10 w-10 rounded-full bg-line flex items-center justify-center">
                        <span className="text-ink-soft font-medium text-sm">
                          {member.name.charAt(0).toUpperCase()}
                        </span>
                      </div>
                    )}
                  </div>

                  {/* Member Info */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center space-x-2">
                      <p className="text-sm font-medium text-ink truncate">
                        {member.name}
                        {isCurrentUser && (
                          <span className="ml-2 text-xs text-ink-mute">(You)</span>
                        )}
                      </p>
                    </div>
                    <p className="text-sm text-ink-mute truncate">{member.email}</p>
                    {member.joined_at && (
                      <p className="text-xs text-ash mt-1">
                        Joined {new Date(member.joined_at).toLocaleDateString()}
                      </p>
                    )}
                  </div>

                  {/* Role Badge/Selector */}
                  <div className="flex items-center space-x-3">
                    {canEdit ? (
                      <select
                        value={member.role}
                        onChange={(e) => handleRoleChange(member.account_id, e.target.value)}
                        className="text-sm border border-taupe rounded-md px-3 py-1 focus:outline-none focus:ring-2 focus:ring-azure"
                      >
                        <option value="admin">Admin</option>
                        <option value="editor">Editor</option>
                        <option value="member">Member</option>
                      </select>
                    ) : (
                      <span
                        className={`inline-flex items-center px-3 py-1 rounded-full text-xs font-medium ${getRoleBadgeColor(
                          member.role
                        )}`}
                      >
                        {member.role}
                      </span>
                    )}

                    {/* Remove Button */}
                    {canEdit && (
                      <button
                        onClick={() => handleRemove(member.account_id, member.name)}
                        className="text-danger hover:text-wine text-sm font-medium"
                      >
                        Remove
                      </button>
                    )}
                  </div>
                </div>
              </div>

              {/* Custom Permissions */}
              {member.custom_permissions && member.custom_permissions.length > 0 && (
                <div className="mt-3 pl-14">
                  <p className="text-xs text-ink-mute mb-1">Custom Permissions:</p>
                  <div className="flex flex-wrap gap-1">
                    {member.custom_permissions.map((permission: string, index: number) => (
                      <span
                        key={index}
                        className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-sand-deep text-gold"
                      >
                        {permission}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </li>
          );
        })}
      </ul>

      {members.length === 0 && (
        <div className="px-6 py-12 text-center">
          <p className="text-ink-mute">No team members yet</p>
        </div>
      )}
    </div>
  );
}
