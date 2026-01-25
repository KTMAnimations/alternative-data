import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Plus, Check, X, MessageSquare, ChevronDown, ChevronUp } from 'lucide-react';
import { adminApi } from '../../services/api';
import type { DataSourceRequest } from '../../types';
import clsx from 'clsx';
import { format } from 'date-fns';

export function DataRequestsPage() {
  const queryClient = useQueryClient();
  const [showCreate, setShowCreate] = useState(false);
  const [expandedRequest, setExpandedRequest] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [newRequest, setNewRequest] = useState({
    source_name: '',
    source_type: 'api',
    description: '',
    use_case: '',
    priority: 'medium',
  });

  const { data: requestsData, isLoading } = useQuery({
    queryKey: ['data-requests', statusFilter],
    queryFn: () => adminApi.getDataRequests({ status: statusFilter === 'all' ? undefined : statusFilter }),
  });

  const requests: DataSourceRequest[] = requestsData?.data?.requests || [];

  const createMutation = useMutation({
    mutationFn: (data: typeof newRequest) => adminApi.createDataRequest(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['data-requests'] });
      setShowCreate(false);
      setNewRequest({ source_name: '', source_type: 'api', description: '', use_case: '', priority: 'medium' });
    },
  });

  const updateStatusMutation = useMutation({
    mutationFn: ({ id, status, notes }: { id: string; status: string; notes?: string }) =>
      adminApi.updateDataRequestStatus(id, status, notes),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['data-requests'] }),
  });

  const getStatusBadge = (status: string) => {
    const colors: Record<string, string> = {
      pending: 'bg-yellow-100 text-yellow-700',
      in_review: 'bg-blue-100 text-blue-700',
      approved: 'bg-green-100 text-green-700',
      rejected: 'bg-red-100 text-red-700',
      in_progress: 'bg-purple-100 text-purple-700',
      completed: 'bg-gray-100 text-gray-700',
    };
    return (
      <span className={clsx('px-2 py-1 rounded-full text-xs font-medium capitalize', colors[status])}>
        {status.replace('_', ' ')}
      </span>
    );
  };

  const getPriorityBadge = (priority: string) => {
    const colors: Record<string, string> = {
      low: 'text-gray-500',
      medium: 'text-yellow-600',
      high: 'text-orange-600',
      critical: 'text-red-600',
    };
    return <span className={clsx('text-xs font-medium capitalize', colors[priority])}>{priority}</span>;
  };

  const pendingCount = requests.filter(r => r.status === 'pending').length;
  const inProgressCount = requests.filter(r => ['in_review', 'in_progress'].includes(r.status)).length;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Data Source Requests</h1>
          <p className="text-gray-500">Manage requests for new data sources</p>
        </div>
        <button onClick={() => setShowCreate(true)} className="btn-primary flex items-center gap-2">
          <Plus className="h-4 w-4" />
          New Request
        </button>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-4 gap-4">
        <div className="card p-4">
          <div className="text-2xl font-bold text-gray-900">{requests.length}</div>
          <div className="text-sm text-gray-500">Total Requests</div>
        </div>
        <div className="card p-4">
          <div className="text-2xl font-bold text-yellow-600">{pendingCount}</div>
          <div className="text-sm text-gray-500">Pending Review</div>
        </div>
        <div className="card p-4">
          <div className="text-2xl font-bold text-blue-600">{inProgressCount}</div>
          <div className="text-sm text-gray-500">In Progress</div>
        </div>
        <div className="card p-4">
          <div className="text-2xl font-bold text-green-600">
            {requests.filter(r => r.status === 'completed').length}
          </div>
          <div className="text-sm text-gray-500">Completed</div>
        </div>
      </div>

      {/* Filters */}
      <div className="flex gap-2">
        {['all', 'pending', 'in_review', 'approved', 'in_progress', 'completed', 'rejected'].map((status) => (
          <button
            key={status}
            onClick={() => setStatusFilter(status)}
            className={clsx(
              'px-4 py-2 rounded-lg text-sm font-medium capitalize',
              statusFilter === status
                ? 'bg-primary-100 text-primary-700'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            )}
          >
            {status.replace('_', ' ')}
          </button>
        ))}
      </div>

      {/* Create Modal */}
      {showCreate && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center">
          <div className="bg-white rounded-xl p-6 w-full max-w-lg shadow-xl">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold">Request New Data Source</h2>
              <button onClick={() => setShowCreate(false)} className="text-gray-400 hover:text-gray-600">
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="space-y-4">
              <div>
                <label className="label mb-1 block">Source Name</label>
                <input
                  value={newRequest.source_name}
                  onChange={(e) => setNewRequest({ ...newRequest, source_name: e.target.value })}
                  className="input w-full"
                  placeholder="e.g., Bloomberg Terminal Data"
                />
              </div>

              <div>
                <label className="label mb-1 block">Source Type</label>
                <select
                  value={newRequest.source_type}
                  onChange={(e) => setNewRequest({ ...newRequest, source_type: e.target.value })}
                  className="select w-full"
                >
                  <option value="api">API</option>
                  <option value="file">File Upload</option>
                  <option value="scraping">Web Scraping</option>
                  <option value="partnership">Data Partnership</option>
                  <option value="other">Other</option>
                </select>
              </div>

              <div>
                <label className="label mb-1 block">Description</label>
                <textarea
                  value={newRequest.description}
                  onChange={(e) => setNewRequest({ ...newRequest, description: e.target.value })}
                  className="input w-full h-24 resize-none"
                  placeholder="Describe the data source and what data it provides..."
                />
              </div>

              <div>
                <label className="label mb-1 block">Use Case</label>
                <textarea
                  value={newRequest.use_case}
                  onChange={(e) => setNewRequest({ ...newRequest, use_case: e.target.value })}
                  className="input w-full h-20 resize-none"
                  placeholder="How will this data be used in research/factors?"
                />
              </div>

              <div>
                <label className="label mb-1 block">Priority</label>
                <select
                  value={newRequest.priority}
                  onChange={(e) => setNewRequest({ ...newRequest, priority: e.target.value })}
                  className="select w-full"
                >
                  <option value="low">Low</option>
                  <option value="medium">Medium</option>
                  <option value="high">High</option>
                  <option value="critical">Critical</option>
                </select>
              </div>

              <div className="flex gap-3 pt-2">
                <button onClick={() => setShowCreate(false)} className="btn-outline flex-1">
                  Cancel
                </button>
                <button
                  onClick={() => createMutation.mutate(newRequest)}
                  disabled={!newRequest.source_name || !newRequest.description || createMutation.isPending}
                  className="btn-primary flex-1"
                >
                  {createMutation.isPending ? 'Submitting...' : 'Submit Request'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Requests List */}
      {isLoading ? (
        <div className="flex items-center justify-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600" />
        </div>
      ) : requests.length === 0 ? (
        <div className="card p-12 text-center">
          <MessageSquare className="h-12 w-12 text-gray-300 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-gray-900 mb-2">No requests found</h3>
          <p className="text-gray-500">Submit a request to add a new data source</p>
        </div>
      ) : (
        <div className="space-y-3">
          {requests.map((request) => (
            <div key={request.id} className="card">
              <div
                className="p-4 cursor-pointer"
                onClick={() => setExpandedRequest(expandedRequest === request.id ? null : request.id)}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-4">
                    <div>
                      <div className="flex items-center gap-2 mb-1">
                        <h3 className="font-semibold text-gray-900">{request.source_name}</h3>
                        {getStatusBadge(request.status)}
                        {getPriorityBadge(request.priority)}
                      </div>
                      <p className="text-sm text-gray-500">{request.source_type} • Requested {format(new Date(request.created_at), 'MMM d, yyyy')}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    {request.status === 'pending' && (
                      <>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            updateStatusMutation.mutate({ id: request.id, status: 'approved' });
                          }}
                          className="p-2 text-success-600 hover:bg-success-50 rounded"
                          title="Approve"
                        >
                          <Check className="h-4 w-4" />
                        </button>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            const reason = prompt('Rejection reason:');
                            if (reason) {
                              updateStatusMutation.mutate({ id: request.id, status: 'rejected', notes: reason });
                            }
                          }}
                          className="p-2 text-danger-600 hover:bg-danger-50 rounded"
                          title="Reject"
                        >
                          <X className="h-4 w-4" />
                        </button>
                      </>
                    )}
                    {expandedRequest === request.id ? (
                      <ChevronUp className="h-5 w-5 text-gray-400" />
                    ) : (
                      <ChevronDown className="h-5 w-5 text-gray-400" />
                    )}
                  </div>
                </div>
              </div>

              {expandedRequest === request.id && (
                <div className="px-4 pb-4 border-t pt-4">
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <h4 className="text-sm font-medium text-gray-700 mb-1">Description</h4>
                      <p className="text-sm text-gray-600">{request.description}</p>
                    </div>
                    <div>
                      <h4 className="text-sm font-medium text-gray-700 mb-1">Use Case</h4>
                      <p className="text-sm text-gray-600">{request.use_case}</p>
                    </div>
                  </div>
                  {request.admin_notes && (
                    <div className="mt-4 p-3 bg-gray-50 rounded-lg">
                      <h4 className="text-sm font-medium text-gray-700 mb-1">Admin Notes</h4>
                      <p className="text-sm text-gray-600">{request.admin_notes}</p>
                    </div>
                  )}
                  {request.status === 'approved' && (
                    <div className="mt-4 flex gap-2">
                      <button
                        onClick={() => updateStatusMutation.mutate({ id: request.id, status: 'in_progress' })}
                        className="btn-primary text-sm"
                      >
                        Start Implementation
                      </button>
                    </div>
                  )}
                  {request.status === 'in_progress' && (
                    <div className="mt-4 flex gap-2">
                      <button
                        onClick={() => updateStatusMutation.mutate({ id: request.id, status: 'completed' })}
                        className="btn-primary text-sm"
                      >
                        Mark Complete
                      </button>
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
