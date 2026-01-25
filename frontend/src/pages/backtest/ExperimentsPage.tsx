import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Plus, Award, TrendingUp, X } from 'lucide-react';
import { factorsApi, backtestApi } from '../../services/api';
import type { Factor, Experiment } from '../../types';
import clsx from 'clsx';
import { format } from 'date-fns';

export function ExperimentsPage() {
  const queryClient = useQueryClient();
  const [showCreate, setShowCreate] = useState(false);
  const [name, setName] = useState('');
  const [controlFactor, setControlFactor] = useState('');
  const [treatmentFactor, setTreatmentFactor] = useState('');

  const { data: factorsData } = useQuery({
    queryKey: ['factors-list'],
    queryFn: () => factorsApi.getFactors(),
  });

  const { data: experimentsData, isLoading } = useQuery({
    queryKey: ['experiments'],
    queryFn: () => backtestApi.getExperiments(),
  });

  const factors: Factor[] = factorsData?.data?.factors || [];
  const experiments: Experiment[] = experimentsData?.data?.experiments || [];

  const createMutation = useMutation({
    mutationFn: () =>
      backtestApi.createExperiment({
        name,
        control_factor_id: controlFactor,
        treatment_factor_id: treatmentFactor,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['experiments'] });
      setShowCreate(false);
      setName('');
      setControlFactor('');
      setTreatmentFactor('');
    },
  });

  const getStatusBadge = (status: string) => {
    const colors: Record<string, string> = {
      running: 'bg-blue-100 text-blue-700',
      completed: 'bg-green-100 text-green-700',
      stopped: 'bg-gray-100 text-gray-700',
    };
    return (
      <span className={clsx('px-2 py-1 rounded-full text-xs font-medium capitalize', colors[status])}>
        {status}
      </span>
    );
  };

  const getWinnerBadge = (winner?: string) => {
    if (!winner || winner === 'inconclusive') return null;
    return (
      <span className={clsx(
        'px-2 py-1 rounded-full text-xs font-medium flex items-center gap-1',
        winner === 'treatment' ? 'bg-green-100 text-green-700' : 'bg-blue-100 text-blue-700'
      )}>
        <Award className="h-3 w-3" />
        {winner === 'treatment' ? 'Treatment Wins' : 'Control Wins'}
      </span>
    );
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">A/B Experiments</h1>
          <p className="text-gray-500">Test different factor formulations side-by-side</p>
        </div>
        <button onClick={() => setShowCreate(true)} className="btn-primary flex items-center gap-2">
          <Plus className="h-4 w-4" />
          New Experiment
        </button>
      </div>

      {/* Create Modal */}
      {showCreate && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center">
          <div className="bg-white rounded-xl p-6 w-full max-w-md shadow-xl">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold">Create Experiment</h2>
              <button onClick={() => setShowCreate(false)} className="text-gray-400 hover:text-gray-600">
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="space-y-4">
              <div>
                <label className="label mb-1 block">Experiment Name</label>
                <input
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="input w-full"
                  placeholder="e.g., TSA Momentum v2 Test"
                />
              </div>

              <div>
                <label className="label mb-1 block">Control Factor</label>
                <select
                  value={controlFactor}
                  onChange={(e) => setControlFactor(e.target.value)}
                  className="select w-full"
                >
                  <option value="">Select control...</option>
                  {factors.map((f) => (
                    <option key={f.id} value={f.id}>{f.name}</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="label mb-1 block">Treatment Factor</label>
                <select
                  value={treatmentFactor}
                  onChange={(e) => setTreatmentFactor(e.target.value)}
                  className="select w-full"
                >
                  <option value="">Select treatment...</option>
                  {factors.map((f) => (
                    <option key={f.id} value={f.id}>{f.name}</option>
                  ))}
                </select>
              </div>

              <div className="flex gap-3 pt-2">
                <button onClick={() => setShowCreate(false)} className="btn-outline flex-1">Cancel</button>
                <button
                  onClick={() => createMutation.mutate()}
                  disabled={!name || !controlFactor || !treatmentFactor || createMutation.isPending}
                  className="btn-primary flex-1"
                >
                  {createMutation.isPending ? 'Creating...' : 'Create'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Experiments List */}
      {isLoading ? (
        <div className="flex items-center justify-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600" />
        </div>
      ) : experiments.length === 0 ? (
        <div className="card p-12 text-center">
          <TrendingUp className="h-12 w-12 text-gray-300 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-gray-900 mb-2">No experiments yet</h3>
          <p className="text-gray-500 mb-4">Create your first A/B experiment to compare factors</p>
          <button onClick={() => setShowCreate(true)} className="btn-primary">
            Create Experiment
          </button>
        </div>
      ) : (
        <div className="space-y-4">
          {experiments.map((exp) => (
            <div key={exp.id} className="card p-5">
              <div className="flex items-start justify-between mb-4">
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <h3 className="font-semibold text-gray-900">{exp.name}</h3>
                    {getStatusBadge(exp.status)}
                    {getWinnerBadge(exp.winner)}
                  </div>
                  <p className="text-sm text-gray-500">
                    Started {format(new Date(exp.start_date), 'MMM d, yyyy')}
                  </p>
                </div>

                {exp.p_value !== undefined && (
                  <div className="text-right">
                    <div className="text-sm text-gray-500">P-Value</div>
                    <div className={clsx(
                      'text-lg font-semibold',
                      exp.p_value < 0.05 ? 'text-success-500' : 'text-gray-900'
                    )}>
                      {exp.p_value.toFixed(4)}
                    </div>
                  </div>
                )}
              </div>

              {/* Metrics Comparison */}
              {exp.control_metrics && exp.treatment_metrics && (
                <div className="grid grid-cols-2 gap-4">
                  <div className="p-4 bg-blue-50 rounded-lg">
                    <div className="text-sm text-blue-700 mb-2 font-medium">Control</div>
                    <div className="grid grid-cols-2 gap-2 text-sm">
                      <div>IC: {(exp.control_metrics.ic * 100).toFixed(2)}%</div>
                      <div>IR: {exp.control_metrics.ir.toFixed(2)}</div>
                      <div>T-Stat: {exp.control_metrics.t_stat.toFixed(2)}</div>
                      <div>Hit: {(exp.control_metrics.hit_rate * 100).toFixed(1)}%</div>
                    </div>
                  </div>
                  <div className="p-4 bg-green-50 rounded-lg">
                    <div className="text-sm text-green-700 mb-2 font-medium">Treatment</div>
                    <div className="grid grid-cols-2 gap-2 text-sm">
                      <div>IC: {(exp.treatment_metrics.ic * 100).toFixed(2)}%</div>
                      <div>IR: {exp.treatment_metrics.ir.toFixed(2)}</div>
                      <div>T-Stat: {exp.treatment_metrics.t_stat.toFixed(2)}</div>
                      <div>Hit: {(exp.treatment_metrics.hit_rate * 100).toFixed(1)}%</div>
                    </div>
                  </div>
                </div>
              )}

              {exp.status === 'completed' && exp.winner === 'treatment' && (
                <button className="btn-primary w-full mt-4">
                  Promote Treatment to Production
                </button>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
