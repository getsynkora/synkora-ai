import { defineConfig } from 'wxt';

export default defineConfig({
  srcDir: 'src',
  extensionEntrypoints: {},
  manifest: {
    name: 'Synkora Agent',
    description: 'Access your Synkora AI agents on any webpage',
permissions: ['storage', 'sidePanel', 'alarms', 'contextMenus', 'activeTab', 'tabs', 'identity', 'scripting'],
    optional_host_permissions: ['*://*/*'],
    action: {},
    commands: {
      _execute_action: {
        suggested_key: {
          default: 'Ctrl+Shift+S',
          mac: 'Command+Shift+S',
        },
        description: 'Toggle Synkora Agent side panel',
      },
    },
    side_panel: {
      default_path: 'sidepanel.html',
    },
    content_security_policy: {
      extension_pages: "script-src 'self'; object-src 'self'",
    },
  },
});
