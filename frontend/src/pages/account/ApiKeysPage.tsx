import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Key, Plus, Copy, Trash2, Eye, EyeOff, AlertTriangle, Check, RefreshCw } from 'lucide-react';
import { userApi } from '../../services/api';
import type { ApiKey } from '../../types';
import { format, formatDistanceToNow } from 'date-fns';

export function ApiKeysPage() {
  const queryClient = useQueryClient();
  const [showCreate, setShowCreate] = useState(false);
  const [newKeyName, setNewKeyName] = useState('');
  const [newKeyExpiry, setNewKeyExpiry] = useState('90');
  const [newlyCreatedKey, setNewlyCreatedKey] = useState<string | null>(null);
  const [visibleKeys, setVisibleKeys] = useState<Set<string>>(new Set());
  const [copiedKey, setCopiedKey] = useState<string | null>(null);

  const { data: keysData, isLoading } = useQuery({
    queryKey: ['api-keys'],
    queryFn: () => userApi.getApiKeys(),
  });

  const apiKeys: ApiKey[] = keysData?.data?.keys || [];

  const createMutation = useMutation({
    mutationFn: (data: { name: string; expires_in_days: number }) => userApi.createApiKey(data),
    onSuccess: (response) => {
      queryClient.invalidateQueries({ queryKey: ['api-keys'] });
      setNewlyCreatedKey(response.data.key);
      setNewKeyName('');
      setNewKeyExpiry('90');
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (keyId: string) => userApi.deleteApiKey(keyId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['api-keys'] }),
  });

  const rotateMutation = useMutation({
    mutationFn: (keyId: string) => userApi.rotateApiKey(keyId),
    onSuccess: (response) => {
      queryClient.invalidateQueries({ queryKey: ['api-keys'] });
      setNewlyCreatedKey(response.data.key);
    },
  });

  const toggleKeyVisibility = (keyId: string) => {
    setVisibleKeys((prev) => {
      const next = new Set(prev);
      if (next.has(keyId)) {
        next.delete(keyId);
      } else {
        next.add(keyId);
      }
      return next;
    });
  };

  const copyToClipboard = async (text: string, keyId: string) => {
    await navigator.clipboard.writeText(text);
    setCopiedKey(keyId);
    setTimeout(() => setCopiedKey(null), 2000);
  };

  const maskKey = (key: string) => {
    return key.slice(0, 8) + '...' + key.slice(-4);
  };

  const getStatusBadge = (key: ApiKey) => {
    if (!key.is_active) {
      return <span className="px-2 py-0.5 rounded-full bg-gray-100 text-gray-600 text-xs">Inactive</span>;
    }
    if (key.expires_at && new Date(key.expires_at) < new Date()) {
      return <span className="px-2 py-0.5 rounded-full bg-red-100 text-red-700 text-xs">Expired</span>;
    }
    if (key.expires_at) {
      const daysUntilExpiry = Math.ceil((new Date(key.expires_at).getTime() - Date.now()) / (1000 * 60 * 60 * 24));
      if (daysUntilExpiry <= 7) {
        return <span className="px-2 py-0.5 rounded-full bg-yellow-100 text-yellow-700 text-xs">Expiring Soon</span>;
      }
    }
    return <span className="px-2 py-0.5 rounded-full bg-green-100 text-green-700 text-xs">Active</span>;
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">API Keys</h1>
          <p className="text-gray-500">Manage your API keys for programmatic access</p>
        </div>
        <button onClick={() => setShowCreate(true)} className="btn-primary flex items-center gap-2">
          <Plus className="h-4 w-4" />
          Create API Key
        </button>
      </div>

      {/* Security Notice */}
      <div className="card p-4 bg-yellow-50 border-yellow-200">
        <div className="flex items-start gap-3">
          <AlertTriangle className="h-5 w-5 text-yellow-600 mt-0.5" />
          <div>
            <h4 className="font-medium text-yellow-800">Keep Your Keys Secure</h4>
            <p className="text-sm text-yellow-700 mt-1">
              API keys provide full access to your account. Never share them publicly or commit them to version control.
              Use environment variables to store keys in your applications.
            </p>
          </div>
        </div>
      </div>

      {/* Newly Created Key Alert */}
      {newlyCreatedKey && (
        <div className="card p-4 bg-green-50 border-green-200">
          <div className="flex items-start justify-between">
            <div>
              <h4 className="font-medium text-green-800 mb-2">New API Key Created</h4>
              <p className="text-sm text-green-700 mb-3">
                Copy this key now. You won't be able to see it again!
              </p>
              <div className="flex items-center gap-2">
                <code className="px-3 py-2 bg-white rounded border border-green-300 font-mono text-sm">
                  {newlyCreatedKey}
                </code>
                <button
                  onClick={() => copyToClipboard(newlyCreatedKey, 'new')}
                  className="p-2 text-green-600 hover:bg-green-100 rounded"
                >
                  {copiedKey === 'new' ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
                </button>
              </div>
            </div>
            <button
              onClick={() => setNewlyCreatedKey(null)}
              className="text-green-600 hover:text-green-800"
            >
              Dismiss
            </button>
          </div>
        </div>
      )}

      {/* Create Modal */}
      {showCreate && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center">
          <div className="bg-white rounded-xl p-6 w-full max-w-md shadow-xl">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold">Create API Key</h2>
              <button onClick={() => setShowCreate(false)} className="text-gray-400 hover:text-gray-600">
                ×
              </button>
            </div>

            <div className="space-y-4">
              <div>
                <label className="label mb-1 block">Key Name</label>
                <input
                  value={newKeyName}
                  onChange={(e) => setNewKeyName(e.target.value)}
                  className="input w-full"
                  placeholder="e.g., Production Server"
                />
                <p className="text-xs text-gray-500 mt-1">A descriptive name to identify this key</p>
              </div>

              <div>
                <label className="label mb-1 block">Expiration</label>
                <select
                  value={newKeyExpiry}
                  onChange={(e) => setNewKeyExpiry(e.target.value)}
                  className="select w-full"
                >
                  <option value="30">30 days</option>
                  <option value="90">90 days</option>
                  <option value="180">180 days</option>
                  <option value="365">1 year</option>
                  <option value="0">Never (not recommended)</option>
                </select>
              </div>

              <div className="flex gap-3 pt-2">
                <button onClick={() => setShowCreate(false)} className="btn-outline flex-1">
                  Cancel
                </button>
                <button
                  onClick={() => {
                    createMutation.mutate({
                      name: newKeyName,
                      expires_in_days: parseInt(newKeyExpiry),
                    });
                    setShowCreate(false);
                  }}
                  disabled={!newKeyName || createMutation.isPending}
                  className="btn-primary flex-1"
                >
                  {createMutation.isPending ? 'Creating...' : 'Create Key'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* API Keys List */}
      {isLoading ? (
        <div className="flex items-center justify-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600" />
        </div>
      ) : apiKeys.length === 0 ? (
        <div className="card p-12 text-center">
          <Key className="h-12 w-12 text-gray-300 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-gray-900 mb-2">No API Keys</h3>
          <p className="text-gray-500 mb-4">Create an API key to start using the API programmatically</p>
          <button onClick={() => setShowCreate(true)} className="btn-primary">
            Create Your First Key
          </button>
        </div>
      ) : (
        <div className="card overflow-hidden">
          <table className="w-full">
            <thead className="bg-gray-50 border-b">
              <tr>
                <th className="px-4 py-3 text-left text-sm font-medium text-gray-700">Name</th>
                <th className="px-4 py-3 text-left text-sm font-medium text-gray-700">Key</th>
                <th className="px-4 py-3 text-left text-sm font-medium text-gray-700">Status</th>
                <th className="px-4 py-3 text-left text-sm font-medium text-gray-700">Created</th>
                <th className="px-4 py-3 text-left text-sm font-medium text-gray-700">Last Used</th>
                <th className="px-4 py-3 text-left text-sm font-medium text-gray-700">Expires</th>
                <th className="px-4 py-3 text-left text-sm font-medium text-gray-700">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {apiKeys.map((key) => (
                <tr key={key.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3">
                    <div className="font-medium text-gray-900">{key.name}</div>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <code className="text-sm font-mono text-gray-600">
                        {visibleKeys.has(key.id) ? key.key_prefix + '...' : maskKey(key.key_prefix + 'xxxxxxxx')}
                      </code>
                      <button
                        onClick={() => toggleKeyVisibility(key.id)}
                        className="p-1 text-gray-400 hover:text-gray-600"
                      >
                        {visibleKeys.has(key.id) ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                      </button>
                      <button
                        onClick={() => copyToClipboard(key.key_prefix, key.id)}
                        className="p-1 text-gray-400 hover:text-gray-600"
                      >
                        {copiedKey === key.id ? <Check className="h-4 w-4 text-green-500" /> : <Copy className="h-4 w-4" />}
                      </button>
                    </div>
                  </td>
                  <td className="px-4 py-3">{getStatusBadge(key)}</td>
                  <td className="px-4 py-3 text-sm text-gray-600">
                    {format(new Date(key.created_at), 'MMM d, yyyy')}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-600">
                    {key.last_used_at
                      ? formatDistanceToNow(new Date(key.last_used_at), { addSuffix: true })
                      : 'Never'}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-600">
                    {key.expires_at
                      ? format(new Date(key.expires_at), 'MMM d, yyyy')
                      : 'Never'}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex gap-1">
                      <button
                        onClick={() => {
                          if (confirm('Rotate this key? The old key will stop working immediately.')) {
                            rotateMutation.mutate(key.id);
                          }
                        }}
                        className="p-2 text-primary-600 hover:bg-primary-50 rounded"
                        title="Rotate Key"
                      >
                        <RefreshCw className="h-4 w-4" />
                      </button>
                      <button
                        onClick={() => {
                          if (confirm('Delete this API key? This action cannot be undone.')) {
                            deleteMutation.mutate(key.id);
                          }
                        }}
                        className="p-2 text-danger-600 hover:bg-danger-50 rounded"
                        title="Delete Key"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Usage Example */}
      <div className="card p-5">
        <h3 className="font-semibold text-gray-900 mb-4">Usage Example</h3>
        <div className="bg-gray-900 rounded-lg p-4 overflow-x-auto">
          <pre className="text-sm text-gray-100">
{`# Python
import requests

headers = {
    "Authorization": "Bearer YOUR_API_KEY",
    "Content-Type": "application/json"
}

response = requests.get(
    "https://api.altdata.example.com/v1/factors",
    headers=headers
)
print(response.json())

# cURL
curl -X GET "https://api.altdata.example.com/v1/factors" \\
  -H "Authorization: Bearer YOUR_API_KEY"`}
          </pre>
        </div>
      </div>
    </div>
  );
}
