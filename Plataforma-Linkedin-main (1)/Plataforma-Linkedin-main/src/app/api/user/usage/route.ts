import { NextResponse } from 'next/server';
import { createClient } from '@/utils/supabase/server';
import { getUserPlan, getPlanLimits, getUserUsage } from '@/lib/rateLimit';

// Force dynamic rendering - this route uses cookies
export const dynamic = 'force-dynamic';

/**
 * User Usage API
 * GET /api/user/usage
 * 
 * Returns the current user's usage statistics and plan limits
 */
export async function GET() {
  try {
    const supabase = await createClient();
    const { data: { user }, error: authError } = await supabase.auth.getUser();

    if (authError || !user) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    }

    const plan = await getUserPlan(user.id);
    const limits = getPlanLimits(plan);
    const usage = await getUserUsage(user.id);

    // Calculate remaining
    const remaining = {
      posts: limits.postsPerMonth === -1 ? -1 : Math.max(0, limits.postsPerMonth - usage.postsThisMonth),
      images: limits.imagesPerMonth === -1 ? -1 : Math.max(0, limits.imagesPerMonth - usage.imagesThisMonth),
      refinements: limits.refinementsPerDay === -1 ? -1 : Math.max(0, limits.refinementsPerDay - usage.refinementsToday),
      photos: limits.maxPhotos === -1 ? -1 : Math.max(0, limits.maxPhotos - usage.photosCount),
    };

    // Calculate reset times
    const now = new Date();
    const endOfMonth = new Date(now.getFullYear(), now.getMonth() + 1, 0, 23, 59, 59);
    const endOfDay = new Date(now.getFullYear(), now.getMonth(), now.getDate(), 23, 59, 59);

    return NextResponse.json({
      plan: {
        tier: plan,
        name: plan === 'starter' ? 'Starter (Gratuito)' : plan === 'pro' ? 'Pro' : 'Business',
      },
      limits: {
        postsPerMonth: limits.postsPerMonth === -1 ? 'Ilimitado' : limits.postsPerMonth,
        imagesPerMonth: limits.imagesPerMonth === -1 ? 'Ilimitado' : limits.imagesPerMonth,
        refinementsPerDay: limits.refinementsPerDay === -1 ? 'Ilimitado' : limits.refinementsPerDay,
        maxPhotos: limits.maxPhotos === -1 ? 'Ilimitado' : limits.maxPhotos,
        features: {
          aiAgent: limits.aiAgentEnabled,
        },
      },
      usage: {
        postsThisMonth: usage.postsThisMonth,
        imagesThisMonth: usage.imagesThisMonth,
        refinementsToday: usage.refinementsToday,
        photosCount: usage.photosCount,
      },
      remaining: {
        posts: remaining.posts === -1 ? 'Ilimitado' : remaining.posts,
        images: remaining.images === -1 ? 'Ilimitado' : remaining.images,
        refinements: remaining.refinements === -1 ? 'Ilimitado' : remaining.refinements,
        photos: remaining.photos === -1 ? 'Ilimitado' : remaining.photos,
      },
      resetTimes: {
        monthly: endOfMonth.toISOString(),
        daily: endOfDay.toISOString(),
      },
    });
  } catch (error: any) {
    console.error('[usage] Error:', error);
    return NextResponse.json(
      { error: error.message || 'Internal server error' },
      { status: 500 }
    );
  }
}
