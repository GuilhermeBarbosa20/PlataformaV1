/**
 * Rate Limiting System for LinkedIn Content Platform
 * 
 * Pricing tiers:
 * - Starter (free trial): 30 posts/month, 10 images/month, 5 refinements/day
 * - Pro (R$97/month): 60 posts/month, 30 images/month, 20 refinements/day
 * - Business (R$197/month): Unlimited posts, unlimited images, unlimited refinements
 */

import { createClient } from '@/utils/supabase/server';

export type PlanTier = 'starter' | 'pro' | 'business';

export interface PlanLimits {
  postsPerMonth: number;
  imagesPerMonth: number;
  refinementsPerDay: number;
  maxPhotos: number;
  aiAgentEnabled: boolean;
}

export interface UsageStats {
  postsThisMonth: number;
  imagesThisMonth: number;
  refinementsToday: number;
  photosCount: number;
}

export interface RateLimitResult {
  allowed: boolean;
  reason?: string;
  remaining?: number;
  resetAt?: string;
  usage?: UsageStats;
  limits?: PlanLimits;
}

// Plan limits configuration
const PLAN_LIMITS: Record<PlanTier, PlanLimits> = {
  starter: {
    postsPerMonth: 30,
    imagesPerMonth: 10,
    refinementsPerDay: 5,
    maxPhotos: 3,
    aiAgentEnabled: true,
  },
  pro: {
    postsPerMonth: 60,
    imagesPerMonth: 30,
    refinementsPerDay: 20,
    maxPhotos: 10,
    aiAgentEnabled: true,
  },
  business: {
    postsPerMonth: -1, // Unlimited
    imagesPerMonth: -1, // Unlimited
    refinementsPerDay: -1, // Unlimited
    maxPhotos: -1, // Unlimited
    aiAgentEnabled: true,
  },
};

/**
 * Get user's current plan tier
 * For now, all users are on 'starter' tier until subscriptions are implemented
 */
export async function getUserPlan(userId: string): Promise<PlanTier> {
  try {
    const supabase = await createClient();
    
    // Check if user has a subscription (for future implementation)
    const { data: subscription } = await supabase
      .from('user_subscriptions')
      .select('plan_tier, status, expires_at')
      .eq('user_id', userId)
      .eq('status', 'active')
      .maybeSingle();
    
    if (subscription?.plan_tier && subscription.status === 'active') {
      // Check if subscription is not expired
      if (subscription.expires_at && new Date(subscription.expires_at) > new Date()) {
        return subscription.plan_tier as PlanTier;
      }
    }
    
    // Default to starter (free tier)
    return 'starter';
  } catch (error) {
    // If table doesn't exist or error, default to starter
    console.warn('[rateLimit] Error getting user plan, defaulting to starter:', error);
    return 'starter';
  }
}

/**
 * Get plan limits for a specific tier
 */
export function getPlanLimits(tier: PlanTier): PlanLimits {
  return PLAN_LIMITS[tier];
}

/**
 * Get user's current usage statistics
 */
export async function getUserUsage(userId: string): Promise<UsageStats> {
  const supabase = await createClient();
  
  const now = new Date();
  const startOfMonth = new Date(now.getFullYear(), now.getMonth(), 1).toISOString();
  const startOfDay = new Date(now.getFullYear(), now.getMonth(), now.getDate()).toISOString();
  
  // Count posts this month
  const { count: postsCount } = await supabase
    .from('posts')
    .select('*', { count: 'exact', head: true })
    .eq('user_id', userId)
    .gte('created_at', startOfMonth);
  
  // Count images this month
  const { count: imagesCount } = await supabase
    .from('posts')
    .select('*', { count: 'exact', head: true })
    .eq('user_id', userId)
    .not('generated_image_url', 'is', null)
    .gte('image_generated_at', startOfMonth);
  
  // Count refinements today
  const { count: refinementsCount } = await supabase
    .from('posts')
    .select('*', { count: 'exact', head: true })
    .eq('user_id', userId)
    .gte('last_refined_at', startOfDay);
  
  // Count user photos
  const { count: photosCount } = await supabase
    .from('user_photos')
    .select('*', { count: 'exact', head: true })
    .eq('user_id', userId);
  
  return {
    postsThisMonth: postsCount || 0,
    imagesThisMonth: imagesCount || 0,
    refinementsToday: refinementsCount || 0,
    photosCount: photosCount || 0,
  };
}

/**
 * Check if user can perform a specific action
 */
export async function checkRateLimit(
  userId: string,
  action: 'post' | 'image' | 'refinement' | 'photo'
): Promise<RateLimitResult> {
  const plan = await getUserPlan(userId);
  const limits = getPlanLimits(plan);
  const usage = await getUserUsage(userId);
  
  const now = new Date();
  const endOfMonth = new Date(now.getFullYear(), now.getMonth() + 1, 0, 23, 59, 59);
  const endOfDay = new Date(now.getFullYear(), now.getMonth(), now.getDate(), 23, 59, 59);
  
  switch (action) {
    case 'post': {
      if (limits.postsPerMonth === -1) {
        return { allowed: true, usage, limits };
      }
      const remaining = limits.postsPerMonth - usage.postsThisMonth;
      if (remaining <= 0) {
        return {
          allowed: false,
          reason: `Limite de ${limits.postsPerMonth} posts/mês atingido. Faça upgrade para o plano Pro ou Business.`,
          remaining: 0,
          resetAt: endOfMonth.toISOString(),
          usage,
          limits,
        };
      }
      return { allowed: true, remaining, resetAt: endOfMonth.toISOString(), usage, limits };
    }
    
    case 'image': {
      if (limits.imagesPerMonth === -1) {
        return { allowed: true, usage, limits };
      }
      const remaining = limits.imagesPerMonth - usage.imagesThisMonth;
      if (remaining <= 0) {
        return {
          allowed: false,
          reason: `Limite de ${limits.imagesPerMonth} imagens/mês atingido. Faça upgrade para o plano Pro ou Business.`,
          remaining: 0,
          resetAt: endOfMonth.toISOString(),
          usage,
          limits,
        };
      }
      return { allowed: true, remaining, resetAt: endOfMonth.toISOString(), usage, limits };
    }
    
    case 'refinement': {
      if (limits.refinementsPerDay === -1) {
        return { allowed: true, usage, limits };
      }
      const remaining = limits.refinementsPerDay - usage.refinementsToday;
      if (remaining <= 0) {
        return {
          allowed: false,
          reason: `Limite de ${limits.refinementsPerDay} refinamentos/dia atingido. Tente novamente amanhã ou faça upgrade.`,
          remaining: 0,
          resetAt: endOfDay.toISOString(),
          usage,
          limits,
        };
      }
      return { allowed: true, remaining, resetAt: endOfDay.toISOString(), usage, limits };
    }
    
    case 'photo': {
      if (limits.maxPhotos === -1) {
        return { allowed: true, usage, limits };
      }
      const remaining = limits.maxPhotos - usage.photosCount;
      if (remaining <= 0) {
        return {
          allowed: false,
          reason: `Limite de ${limits.maxPhotos} fotos atingido. Remova fotos existentes ou faça upgrade.`,
          remaining: 0,
          usage,
          limits,
        };
      }
      return { allowed: true, remaining, usage, limits };
    }
    
    default:
      return { allowed: true, usage, limits };
  }
}

/**
 * Check if user can use a specific feature
 */
export async function checkFeatureAccess(
  userId: string,
  feature: 'aiAgent'
): Promise<{ allowed: boolean; reason?: string }> {
  const plan = await getUserPlan(userId);
  const limits = getPlanLimits(plan);
  
  switch (feature) {
    case 'aiAgent':
      if (!limits.aiAgentEnabled) {
        return {
          allowed: false,
          reason: 'AI Agent não disponível no seu plano. Faça upgrade para o plano Pro ou Business.',
        };
      }
      return { allowed: true };
    
    default:
      return { allowed: true };
  }
}

/**
 * Simple in-memory rate limiter for API abuse prevention
 * This is in addition to the usage limits
 */
const requestCounts = new Map<string, { count: number; resetAt: number }>();
const REQUEST_LIMIT_PER_MINUTE = 60;

export function checkApiRateLimit(userId: string): { allowed: boolean; retryAfter?: number } {
  const now = Date.now();
  const key = userId;
  const record = requestCounts.get(key);
  
  if (!record || now > record.resetAt) {
    requestCounts.set(key, { count: 1, resetAt: now + 60000 });
    return { allowed: true };
  }
  
  if (record.count >= REQUEST_LIMIT_PER_MINUTE) {
    const retryAfter = Math.ceil((record.resetAt - now) / 1000);
    return { allowed: false, retryAfter };
  }
  
  record.count++;
  return { allowed: true };
}

// Cleanup old records periodically (in production, use Redis instead)
setInterval(() => {
  const now = Date.now();
  for (const [key, record] of requestCounts.entries()) {
    if (now > record.resetAt) {
      requestCounts.delete(key);
    }
  }
}, 60000);
