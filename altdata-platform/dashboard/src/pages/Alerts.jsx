import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '../api/client'

function Alerts() {
  const queryClient = useQueryClient()
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [selectedRule, setSelectedRule] = useState(null)

  // Fetch alert rules
  const { data: rulesData, isLoading: rulesLoading } = useQuery({
    queryKey: ['alertRules'],
    queryFn: () => api.get('/api/v1/alerts/rules').then(res => res.data)
  })

  // Fetch notifications
  const { data: notificationsData, isLoading: notificationsLoading } = useQuery({
    queryKey: ['alertNotifications'],
    queryFn: () => api.get('/api/v1/alerts/notifications?page_size=20').then(res => res.data)
  })

  // Delete rule mutation
  const deleteMutation = useMutation({
    mutationFn: (ruleId) => api.delete(`/api/v1/alerts/rules/${ruleId}`),
    onSuccess: () => {
      queryClient.invalidateQueries(['alertRules'])
    }
  })

  // Toggle active mutation
  const toggleMutation = useMutation({
    mutationFn: ({ ruleId, isActive }) =>
      api.put(`/api/v1/alerts/rules/${ruleId}`, { is_active: isActive }),
    onSuccess: () => {
      queryClient.invalidateQueries(['alertRules'])
    }
  })

  // Trigger check mutation
  const triggerCheckMutation = useMutation({
    mutationFn: () => api.post('/api/v1/alerts/check'),
    onSuccess: () => {
      queryClient.invalidateQueries(['alertNotifications'])
    }
  })

  const conditionLabels = {
    gt: 'Greater than',
    lt: 'Less than',
    eq: 'Equal to',
    zscore_gt: 'Z-score >',
    zscore_lt: 'Z-score <',
    pct_change_gt: '% Change >',
    pct_change_lt: '% Change <',
  }

  const statusColors = {
    pending: 'bg-yellow-100 text-yellow-800',
    sent: 'bg-green-100 text-green-800',
    failed: 'bg-red-100 text-red-800',
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Alerts</h1>
          <p className="mt-1 text-sm text-gray-500">
            Manage alert rules and view triggered notifications
          </p>
        </div>
        <div className="flex space-x-3">
          <button
            onClick={() => triggerCheckMutation.mutate()}
            disabled={triggerCheckMutation.isPending}
            className="px-4 py-2 text-sm font-medium text-indigo-600 bg-white border border-indigo-600 rounded-md hover:bg-indigo-50"
          >
            {triggerCheckMutation.isPending ? 'Checking...' : 'Run Check Now'}
          </button>
          <button
            onClick={() => setShowCreateModal(true)}
            className="px-4 py-2 text-sm font-medium text-white bg-indigo-600 rounded-md hover:bg-indigo-700"
          >
            Create Rule
          </button>
        </div>
      </div>

      {/* Alert Rules */}
      <div className="bg-white shadow rounded-lg">
        <div className="px-4 py-5 sm:px-6 border-b">
          <h2 className="text-lg font-medium text-gray-900">Alert Rules</h2>
        </div>
        <div className="overflow-x-auto">
          {rulesLoading ? (
            <div className="p-8 text-center text-gray-500">Loading rules...</div>
          ) : rulesData?.rules?.length === 0 ? (
            <div className="p-8 text-center text-gray-500">
              No alert rules configured. Create one to get started.
            </div>
          ) : (
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Name</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Factor</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Entity</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Condition</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Channel</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Actions</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {rulesData?.rules?.map((rule) => (
                  <tr key={rule.id}>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm font-medium text-gray-900">{rule.name}</div>
                      {rule.description && (
                        <div className="text-xs text-gray-500">{rule.description}</div>
                      )}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {rule.factor_name}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {rule.entity_id || 'All'}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {conditionLabels[rule.condition]} {rule.threshold}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 capitalize">
                      {rule.notification_channel}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <button
                        onClick={() => toggleMutation.mutate({ ruleId: rule.id, isActive: !rule.is_active })}
                        className={`px-2 py-1 text-xs font-medium rounded ${
                          rule.is_active
                            ? 'bg-green-100 text-green-800'
                            : 'bg-gray-100 text-gray-800'
                        }`}
                      >
                        {rule.is_active ? 'Active' : 'Inactive'}
                      </button>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm">
                      <button
                        onClick={() => deleteMutation.mutate(rule.id)}
                        className="text-red-600 hover:text-red-900"
                      >
                        Delete
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {/* Recent Notifications */}
      <div className="bg-white shadow rounded-lg">
        <div className="px-4 py-5 sm:px-6 border-b">
          <h2 className="text-lg font-medium text-gray-900">Recent Notifications</h2>
        </div>
        <div className="overflow-x-auto">
          {notificationsLoading ? (
            <div className="p-8 text-center text-gray-500">Loading notifications...</div>
          ) : notificationsData?.notifications?.length === 0 ? (
            <div className="p-8 text-center text-gray-500">
              No notifications yet. Alerts will appear here when triggered.
            </div>
          ) : (
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Rule</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Entity</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Value</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Threshold</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Triggered</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {notificationsData?.notifications?.map((notification) => (
                  <tr key={notification.id}>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      Rule #{notification.rule_id}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {notification.entity_id}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {notification.factor_value?.toFixed(4)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {notification.threshold}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {new Date(notification.triggered_at).toLocaleString()}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className={`px-2 py-1 text-xs font-medium rounded ${statusColors[notification.notification_status]}`}>
                        {notification.notification_status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {/* Create Rule Modal */}
      {showCreateModal && (
        <CreateRuleModal
          onClose={() => setShowCreateModal(false)}
          onSuccess={() => {
            setShowCreateModal(false)
            queryClient.invalidateQueries(['alertRules'])
          }}
        />
      )}
    </div>
  )
}

function CreateRuleModal({ onClose, onSuccess }) {
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    factor_name: '',
    entity_id: '',
    condition: 'gt',
    threshold: '',
    lookback_days: 30,
    notification_channel: 'slack',
    notification_config: '',
    cooldown_minutes: 60,
  })

  const createMutation = useMutation({
    mutationFn: (data) => api.post('/api/v1/alerts/rules', data),
    onSuccess: onSuccess
  })

  const handleSubmit = (e) => {
    e.preventDefault()
    const payload = {
      ...formData,
      threshold: parseFloat(formData.threshold),
      entity_id: formData.entity_id || null,
      notification_config: formData.notification_config || null,
    }
    createMutation.mutate(payload)
  }

  return (
    <div className="fixed inset-0 bg-gray-500 bg-opacity-75 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl max-w-lg w-full mx-4">
        <div className="px-4 py-5 sm:px-6 border-b">
          <h3 className="text-lg font-medium text-gray-900">Create Alert Rule</h3>
        </div>
        <form onSubmit={handleSubmit} className="px-4 py-5 sm:p-6 space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700">Name</label>
            <input
              type="text"
              required
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700">Factor Name</label>
            <input
              type="text"
              required
              placeholder="e.g., insider_transaction_momentum"
              value={formData.factor_name}
              onChange={(e) => setFormData({ ...formData, factor_name: e.target.value })}
              className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700">Entity ID (optional)</label>
            <input
              type="text"
              placeholder="e.g., AAPL (leave empty for all)"
              value={formData.entity_id}
              onChange={(e) => setFormData({ ...formData, entity_id: e.target.value })}
              className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700">Condition</label>
              <select
                value={formData.condition}
                onChange={(e) => setFormData({ ...formData, condition: e.target.value })}
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
              >
                <option value="gt">Greater than</option>
                <option value="lt">Less than</option>
                <option value="eq">Equal to</option>
                <option value="zscore_gt">Z-score greater than</option>
                <option value="zscore_lt">Z-score less than</option>
                <option value="pct_change_gt">% Change greater than</option>
                <option value="pct_change_lt">% Change less than</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700">Threshold</label>
              <input
                type="number"
                step="any"
                required
                value={formData.threshold}
                onChange={(e) => setFormData({ ...formData, threshold: e.target.value })}
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
              />
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700">Notification Channel</label>
            <select
              value={formData.notification_channel}
              onChange={(e) => setFormData({ ...formData, notification_channel: e.target.value })}
              className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
            >
              <option value="slack">Slack</option>
              <option value="email">Email</option>
              <option value="webhook">Webhook</option>
            </select>
          </div>
          <div className="flex justify-end space-x-3 pt-4">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={createMutation.isPending}
              className="px-4 py-2 text-sm font-medium text-white bg-indigo-600 rounded-md hover:bg-indigo-700 disabled:opacity-50"
            >
              {createMutation.isPending ? 'Creating...' : 'Create Rule'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

export default Alerts
