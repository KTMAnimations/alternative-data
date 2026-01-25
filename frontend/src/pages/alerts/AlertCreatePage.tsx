import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useMutation } from '@tanstack/react-query';
import { useForm } from 'react-hook-form';
import { ArrowLeft, Bell, Zap, MapPin, Clock, Mail, Globe } from 'lucide-react';
import { alertsApi, factorsApi } from '../../services/api';
import type { Factor } from '../../types';
import clsx from 'clsx';

type AlertType = 'threshold' | 'anomaly' | 'event';

interface AlertFormData {
  name: string;
  description: string;
  factor_id: string;
  ticker_list: string;
  // Threshold
  threshold_value: number;
  direction: 'above' | 'below' | 'crosses';
  // Anomaly
  sensitivity_std: number;
  baseline_period_days: number;
  use_ml: boolean;
  // Event
  event_type: string;
  magnitude_threshold: number;
  region: string;
  // Notification
  notification_channel: 'email' | 'webhook';
  webhook_url: string;
  // Fatigue management
  quiet_hours_enabled: boolean;
  quiet_hours_start: string;
  quiet_hours_end: string;
  cooldown_minutes: number;
  digest_enabled: boolean;
  digest_time: string;
}

const EVENT_TYPES = [
  { id: 'earthquake', label: 'Earthquake' },
  { id: 'contract_award', label: 'Government Contract' },
  { id: 'power_outage', label: 'Power Outage' },
  { id: 'cyber_attack', label: 'Cyber Attack' },
];

export function AlertCreatePage() {
  const navigate = useNavigate();
  const [alertType, setAlertType] = useState<AlertType>('threshold');

  const { register, handleSubmit, watch, formState: { errors } } = useForm<AlertFormData>({
    defaultValues: {
      direction: 'above',
      sensitivity_std: 2,
      baseline_period_days: 30,
      use_ml: false,
      notification_channel: 'email',
      cooldown_minutes: 60,
      quiet_hours_enabled: false,
      quiet_hours_start: '22:00',
      quiet_hours_end: '08:00',
      digest_enabled: false,
      digest_time: '09:00',
    },
  });

  const { data: factorsData } = useQuery({
    queryKey: ['factors-list'],
    queryFn: () => factorsApi.getFactors(),
  });

  const factors: Factor[] = factorsData?.data?.factors || [];

  const createMutation = useMutation({
    mutationFn: (data: AlertFormData) =>
      alertsApi.createAlert({
        name: data.name,
        description: data.description,
        factor_id: data.factor_id,
        ticker_list: data.ticker_list.split(',').map((t) => t.trim()),
        threshold_value: data.threshold_value,
        direction: data.direction,
        notification_channel: data.notification_channel,
        enabled: true,
      }),
    onSuccess: () => navigate('/alerts'),
  });

  const watchChannel = watch('notification_channel');
  const watchQuietHours = watch('quiet_hours_enabled');
  const watchDigest = watch('digest_enabled');

  const onSubmit = (data: AlertFormData) => {
    createMutation.mutate(data);
  };

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      {/* Header */}
      <div>
        <button
          onClick={() => navigate('/alerts')}
          className="flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700 mb-2"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to Alerts
        </button>
        <h1 className="text-2xl font-bold text-gray-900">Create Alert</h1>
        <p className="text-gray-500">Configure a new alert for factor monitoring</p>
      </div>

      {/* Alert Type Selection */}
      <div className="card p-5">
        <h2 className="font-semibold text-gray-900 mb-4">Alert Type</h2>
        <div className="grid grid-cols-3 gap-3">
          {[
            { id: 'threshold', label: 'Threshold', icon: Bell, desc: 'Trigger when value crosses threshold' },
            { id: 'anomaly', label: 'Anomaly', icon: Zap, desc: 'Detect unusual movements' },
            { id: 'event', label: 'Event', icon: MapPin, desc: 'Monitor specific events' },
          ].map((type) => (
            <button
              key={type.id}
              type="button"
              onClick={() => setAlertType(type.id as AlertType)}
              className={clsx(
                'p-4 rounded-lg border text-left transition-colors',
                alertType === type.id
                  ? 'border-primary-500 bg-primary-50'
                  : 'border-gray-200 hover:border-gray-300'
              )}
            >
              <type.icon className={clsx('h-5 w-5 mb-2', alertType === type.id ? 'text-primary-600' : 'text-gray-400')} />
              <div className="font-medium text-gray-900">{type.label}</div>
              <div className="text-xs text-gray-500 mt-1">{type.desc}</div>
            </button>
          ))}
        </div>
      </div>

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
        {/* Basic Info */}
        <div className="card p-5 space-y-4">
          <h2 className="font-semibold text-gray-900">Basic Information</h2>

          <div>
            <label className="label mb-1 block">Alert Name *</label>
            <input
              {...register('name', { required: 'Name is required' })}
              className="input w-full"
              placeholder="e.g., TSA Traffic Spike Alert"
            />
            {errors.name && <p className="text-danger-500 text-sm mt-1">{errors.name.message}</p>}
          </div>

          <div>
            <label className="label mb-1 block">Description</label>
            <textarea
              {...register('description')}
              className="input w-full"
              rows={2}
              placeholder="Optional description..."
            />
          </div>

          <div>
            <label className="label mb-1 block">Factor *</label>
            <select {...register('factor_id', { required: 'Factor is required' })} className="select w-full">
              <option value="">Select a factor...</option>
              {factors.map((factor) => (
                <option key={factor.id} value={factor.id}>
                  {factor.name}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="label mb-1 block">Tickers (comma-separated) *</label>
            <input
              {...register('ticker_list', { required: 'At least one ticker is required' })}
              className="input w-full"
              placeholder="e.g., DAL, UAL, AAL"
            />
          </div>
        </div>

        {/* Threshold Config */}
        {alertType === 'threshold' && (
          <div className="card p-5 space-y-4">
            <h2 className="font-semibold text-gray-900">Threshold Configuration</h2>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="label mb-1 block">Direction</label>
                <select {...register('direction')} className="select w-full">
                  <option value="above">Above</option>
                  <option value="below">Below</option>
                  <option value="crosses">Crosses</option>
                </select>
              </div>
              <div>
                <label className="label mb-1 block">Threshold Value</label>
                <input
                  type="number"
                  step="0.01"
                  {...register('threshold_value', { valueAsNumber: true })}
                  className="input w-full"
                  placeholder="e.g., 1.5"
                />
              </div>
            </div>
          </div>
        )}

        {/* Anomaly Config */}
        {alertType === 'anomaly' && (
          <div className="card p-5 space-y-4">
            <h2 className="font-semibold text-gray-900">Anomaly Detection Configuration</h2>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="label mb-1 block">Sensitivity (Std Devs)</label>
                <input
                  type="number"
                  step="0.5"
                  {...register('sensitivity_std', { valueAsNumber: true })}
                  className="input w-full"
                />
                <p className="text-xs text-gray-500 mt-1">Higher = fewer alerts</p>
              </div>
              <div>
                <label className="label mb-1 block">Baseline Period (Days)</label>
                <select {...register('baseline_period_days', { valueAsNumber: true })} className="select w-full">
                  <option value={7}>7 days</option>
                  <option value={30}>30 days</option>
                  <option value={90}>90 days</option>
                </select>
              </div>
            </div>

            <label className="flex items-center gap-2">
              <input type="checkbox" {...register('use_ml')} className="rounded border-gray-300" />
              <span className="text-sm text-gray-700">Use ML-based detection (more accurate, slower)</span>
            </label>
          </div>
        )}

        {/* Event Config */}
        {alertType === 'event' && (
          <div className="card p-5 space-y-4">
            <h2 className="font-semibold text-gray-900">Event Configuration</h2>

            <div>
              <label className="label mb-1 block">Event Type</label>
              <select {...register('event_type')} className="select w-full">
                {EVENT_TYPES.map((type) => (
                  <option key={type.id} value={type.id}>{type.label}</option>
                ))}
              </select>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="label mb-1 block">Magnitude Threshold</label>
                <input
                  type="number"
                  step="0.1"
                  {...register('magnitude_threshold', { valueAsNumber: true })}
                  className="input w-full"
                  placeholder="e.g., 6.0"
                />
              </div>
              <div>
                <label className="label mb-1 block">Region Filter</label>
                <select {...register('region')} className="select w-full">
                  <option value="">All regions</option>
                  <option value="california">California</option>
                  <option value="pacific_northwest">Pacific Northwest</option>
                  <option value="gulf_coast">Gulf Coast</option>
                </select>
              </div>
            </div>
          </div>
        )}

        {/* Notification */}
        <div className="card p-5 space-y-4">
          <h2 className="font-semibold text-gray-900">Notification Settings</h2>

          <div>
            <label className="label mb-2 block">Notification Channel</label>
            <div className="flex gap-3">
              <label className={clsx(
                'flex-1 flex items-center gap-2 p-3 rounded-lg border cursor-pointer',
                watchChannel === 'email' ? 'border-primary-500 bg-primary-50' : 'border-gray-200'
              )}>
                <input type="radio" value="email" {...register('notification_channel')} className="hidden" />
                <Mail className={clsx('h-5 w-5', watchChannel === 'email' ? 'text-primary-600' : 'text-gray-400')} />
                <span className="font-medium">Email</span>
              </label>
              <label className={clsx(
                'flex-1 flex items-center gap-2 p-3 rounded-lg border cursor-pointer',
                watchChannel === 'webhook' ? 'border-primary-500 bg-primary-50' : 'border-gray-200'
              )}>
                <input type="radio" value="webhook" {...register('notification_channel')} className="hidden" />
                <Globe className={clsx('h-5 w-5', watchChannel === 'webhook' ? 'text-primary-600' : 'text-gray-400')} />
                <span className="font-medium">Webhook</span>
              </label>
            </div>
          </div>

          {watchChannel === 'webhook' && (
            <div>
              <label className="label mb-1 block">Webhook URL</label>
              <input
                {...register('webhook_url')}
                className="input w-full"
                placeholder="https://your-endpoint.com/webhook"
              />
            </div>
          )}
        </div>

        {/* Alert Fatigue Management */}
        <div className="card p-5 space-y-4">
          <h2 className="font-semibold text-gray-900 flex items-center gap-2">
            <Clock className="h-5 w-5" />
            Alert Fatigue Management
          </h2>

          <div>
            <label className="label mb-1 block">Cooldown Period (minutes)</label>
            <input
              type="number"
              {...register('cooldown_minutes', { valueAsNumber: true })}
              className="input w-full"
            />
            <p className="text-xs text-gray-500 mt-1">Minimum time between repeated alerts</p>
          </div>

          <label className="flex items-center gap-2">
            <input type="checkbox" {...register('quiet_hours_enabled')} className="rounded border-gray-300" />
            <span className="text-sm text-gray-700">Enable quiet hours</span>
          </label>

          {watchQuietHours && (
            <div className="grid grid-cols-2 gap-4 ml-6">
              <div>
                <label className="label mb-1 block">Start Time</label>
                <input type="time" {...register('quiet_hours_start')} className="input w-full" />
              </div>
              <div>
                <label className="label mb-1 block">End Time</label>
                <input type="time" {...register('quiet_hours_end')} className="input w-full" />
              </div>
            </div>
          )}

          <label className="flex items-center gap-2">
            <input type="checkbox" {...register('digest_enabled')} className="rounded border-gray-300" />
            <span className="text-sm text-gray-700">Send as daily digest instead of real-time</span>
          </label>

          {watchDigest && (
            <div className="ml-6">
              <label className="label mb-1 block">Digest Time</label>
              <input type="time" {...register('digest_time')} className="input w-48" />
            </div>
          )}
        </div>

        {/* Submit */}
        <div className="flex gap-3">
          <button type="button" onClick={() => navigate('/alerts')} className="btn-outline flex-1">
            Cancel
          </button>
          <button
            type="submit"
            disabled={createMutation.isPending}
            className="btn-primary flex-1"
          >
            {createMutation.isPending ? 'Creating...' : 'Create Alert'}
          </button>
        </div>
      </form>
    </div>
  );
}
