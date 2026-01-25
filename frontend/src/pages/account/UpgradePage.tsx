import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Check, Zap, Building, Crown, ArrowRight } from 'lucide-react';
import { userApi } from '../../services/api';
import type { Tier, UserUsage } from '../../types';
import clsx from 'clsx';

export function UpgradePage() {
  const queryClient = useQueryClient();
  const [selectedTier, setSelectedTier] = useState<string | null>(null);
  const [billingCycle, setBillingCycle] = useState<'monthly' | 'annual'>('annual');

  const { data: tiersData } = useQuery({
    queryKey: ['tiers'],
    queryFn: () => userApi.getTiers(),
  });

  const { data: usageData } = useQuery({
    queryKey: ['user-usage'],
    queryFn: () => userApi.getUsage(),
  });

  const tiers: Tier[] = tiersData?.data?.tiers || [];
  const currentUsage: UserUsage | undefined = usageData?.data;
  const currentTierId = currentUsage?.tier_id;

  const upgradeMutation = useMutation({
    mutationFn: (tierId: string) => userApi.upgradeTier(tierId, billingCycle),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['user-usage'] });
      setSelectedTier(null);
    },
  });

  const getTierIcon = (tierName: string) => {
    switch (tierName.toLowerCase()) {
      case 'free':
        return <Zap className="h-6 w-6" />;
      case 'professional':
        return <Building className="h-6 w-6" />;
      case 'enterprise':
        return <Crown className="h-6 w-6" />;
      default:
        return <Zap className="h-6 w-6" />;
    }
  };

  const getTierColor = (tierName: string) => {
    switch (tierName.toLowerCase()) {
      case 'free':
        return 'border-gray-200 bg-white';
      case 'professional':
        return 'border-primary-200 bg-primary-50';
      case 'enterprise':
        return 'border-yellow-200 bg-yellow-50';
      default:
        return 'border-gray-200 bg-white';
    }
  };

  const formatPrice = (price: number) => {
    if (price === 0) return 'Free';
    return `$${price.toLocaleString()}`;
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="text-center max-w-2xl mx-auto">
        <h1 className="text-3xl font-bold text-gray-900 mb-3">Choose Your Plan</h1>
        <p className="text-gray-500">
          Scale your alternative data research with the right plan for your needs
        </p>
      </div>

      {/* Billing Toggle */}
      <div className="flex justify-center">
        <div className="inline-flex items-center p-1 bg-gray-100 rounded-lg">
          <button
            onClick={() => setBillingCycle('monthly')}
            className={clsx(
              'px-4 py-2 text-sm font-medium rounded-md transition',
              billingCycle === 'monthly'
                ? 'bg-white text-gray-900 shadow'
                : 'text-gray-600 hover:text-gray-900'
            )}
          >
            Monthly
          </button>
          <button
            onClick={() => setBillingCycle('annual')}
            className={clsx(
              'px-4 py-2 text-sm font-medium rounded-md transition',
              billingCycle === 'annual'
                ? 'bg-white text-gray-900 shadow'
                : 'text-gray-600 hover:text-gray-900'
            )}
          >
            Annual
            <span className="ml-2 text-xs text-success-600 font-semibold">Save 20%</span>
          </button>
        </div>
      </div>

      {/* Pricing Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 max-w-5xl mx-auto">
        {tiers.map((tier) => {
          const isCurrent = tier.id === currentTierId;
          const price = billingCycle === 'annual' ? Math.floor(tier.price_monthly * 0.8) : tier.price_monthly;

          return (
            <div
              key={tier.id}
              className={clsx(
                'card p-6 border-2 transition-all',
                getTierColor(tier.name),
                isCurrent && 'ring-2 ring-primary-500'
              )}
            >
              {/* Tier Header */}
              <div className="flex items-center gap-3 mb-4">
                <div className={clsx(
                  'w-12 h-12 rounded-lg flex items-center justify-center',
                  tier.name.toLowerCase() === 'free' && 'bg-gray-100 text-gray-600',
                  tier.name.toLowerCase() === 'professional' && 'bg-primary-100 text-primary-600',
                  tier.name.toLowerCase() === 'enterprise' && 'bg-yellow-100 text-yellow-600'
                )}>
                  {getTierIcon(tier.name)}
                </div>
                <div>
                  <h3 className="font-semibold text-gray-900">{tier.name}</h3>
                  {isCurrent && (
                    <span className="text-xs text-primary-600 font-medium">Current Plan</span>
                  )}
                </div>
              </div>

              {/* Price */}
              <div className="mb-6">
                <div className="flex items-baseline gap-1">
                  <span className="text-4xl font-bold text-gray-900">{formatPrice(price)}</span>
                  {tier.price_monthly > 0 && (
                    <span className="text-gray-500">/month</span>
                  )}
                </div>
                {billingCycle === 'annual' && tier.price_monthly > 0 && (
                  <p className="text-sm text-gray-500 mt-1">
                    Billed annually at ${(price * 12).toLocaleString()}/year
                  </p>
                )}
              </div>

              {/* Features */}
              <ul className="space-y-3 mb-6">
                <li className="flex items-center gap-2 text-sm">
                  <Check className="h-4 w-4 text-success-500 flex-shrink-0" />
                  <span>{tier.api_calls_limit.toLocaleString()} API calls/month</span>
                </li>
                <li className="flex items-center gap-2 text-sm">
                  <Check className="h-4 w-4 text-success-500 flex-shrink-0" />
                  <span>{tier.data_limit_mb >= 1000 ? `${tier.data_limit_mb / 1000} GB` : `${tier.data_limit_mb} MB`} data download/month</span>
                </li>
                {tier.features?.map((feature, idx) => (
                  <li key={idx} className="flex items-center gap-2 text-sm">
                    <Check className="h-4 w-4 text-success-500 flex-shrink-0" />
                    <span>{feature}</span>
                  </li>
                ))}
              </ul>

              {/* CTA Button */}
              {isCurrent ? (
                <button disabled className="btn-outline w-full opacity-50 cursor-not-allowed">
                  Current Plan
                </button>
              ) : tier.price_monthly === 0 ? (
                <button
                  onClick={() => upgradeMutation.mutate(tier.id)}
                  className="btn-outline w-full"
                >
                  Downgrade to Free
                </button>
              ) : (
                <button
                  onClick={() => setSelectedTier(tier.id)}
                  className={clsx(
                    'w-full flex items-center justify-center gap-2',
                    tier.name.toLowerCase() === 'professional' ? 'btn-primary' : 'btn-outline'
                  )}
                >
                  {currentTierId && tiers.findIndex(t => t.id === currentTierId) > tiers.findIndex(t => t.id === tier.id)
                    ? 'Downgrade'
                    : 'Upgrade'}
                  <ArrowRight className="h-4 w-4" />
                </button>
              )}
            </div>
          );
        })}
      </div>

      {/* Upgrade Confirmation Modal */}
      {selectedTier && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center">
          <div className="bg-white rounded-xl p-6 w-full max-w-md shadow-xl">
            <h2 className="text-lg font-semibold mb-4">Confirm Plan Change</h2>

            {(() => {
              const tier = tiers.find(t => t.id === selectedTier);
              const price = billingCycle === 'annual' ? Math.floor((tier?.price_monthly || 0) * 0.8) : (tier?.price_monthly || 0);

              return (
                <div className="space-y-4">
                  <div className="p-4 bg-gray-50 rounded-lg">
                    <div className="flex justify-between mb-2">
                      <span className="text-gray-600">New Plan</span>
                      <span className="font-medium">{tier?.name}</span>
                    </div>
                    <div className="flex justify-between mb-2">
                      <span className="text-gray-600">Billing Cycle</span>
                      <span className="font-medium capitalize">{billingCycle}</span>
                    </div>
                    <div className="flex justify-between border-t pt-2 mt-2">
                      <span className="text-gray-900 font-medium">Total</span>
                      <span className="font-semibold text-lg">
                        {billingCycle === 'annual'
                          ? `$${(price * 12).toLocaleString()}/year`
                          : `$${price.toLocaleString()}/month`
                        }
                      </span>
                    </div>
                  </div>

                  <p className="text-sm text-gray-500">
                    Your plan will change immediately. You'll be charged a prorated amount for the remaining billing period.
                  </p>

                  <div className="flex gap-3">
                    <button
                      onClick={() => setSelectedTier(null)}
                      className="btn-outline flex-1"
                    >
                      Cancel
                    </button>
                    <button
                      onClick={() => upgradeMutation.mutate(selectedTier)}
                      disabled={upgradeMutation.isPending}
                      className="btn-primary flex-1"
                    >
                      {upgradeMutation.isPending ? 'Processing...' : 'Confirm Upgrade'}
                    </button>
                  </div>
                </div>
              );
            })()}
          </div>
        </div>
      )}

      {/* FAQ Section */}
      <div className="max-w-3xl mx-auto mt-12">
        <h2 className="text-xl font-semibold text-gray-900 text-center mb-6">Frequently Asked Questions</h2>
        <div className="space-y-4">
          <div className="card p-4">
            <h4 className="font-medium text-gray-900 mb-2">Can I change plans at any time?</h4>
            <p className="text-sm text-gray-600">
              Yes, you can upgrade or downgrade your plan at any time. Changes take effect immediately,
              and you'll be charged or credited a prorated amount.
            </p>
          </div>
          <div className="card p-4">
            <h4 className="font-medium text-gray-900 mb-2">What happens if I exceed my limits?</h4>
            <p className="text-sm text-gray-600">
              You'll receive notifications as you approach your limits. If you exceed them, additional
              usage is billed at overage rates or requests may be rate-limited depending on your plan.
            </p>
          </div>
          <div className="card p-4">
            <h4 className="font-medium text-gray-900 mb-2">Do you offer custom Enterprise plans?</h4>
            <p className="text-sm text-gray-600">
              Yes! For organizations with specific requirements, dedicated support needs, or high-volume
              usage, contact our sales team for a custom quote.
            </p>
          </div>
          <div className="card p-4">
            <h4 className="font-medium text-gray-900 mb-2">Is there a free trial?</h4>
            <p className="text-sm text-gray-600">
              The Free tier lets you explore the platform with no time limit. When you're ready for
              more capacity, upgrade to a paid plan.
            </p>
          </div>
        </div>
      </div>

      {/* Contact Sales */}
      <div className="card p-6 text-center max-w-2xl mx-auto bg-gradient-to-r from-primary-50 to-blue-50 border-primary-200">
        <h3 className="font-semibold text-gray-900 mb-2">Need a Custom Solution?</h3>
        <p className="text-gray-600 mb-4">
          Our enterprise team can help you build a plan that fits your specific research needs.
        </p>
        <button className="btn-primary">
          Contact Sales
        </button>
      </div>
    </div>
  );
}
