import { NextRequest, NextResponse } from 'next/server';
import { createClient } from '@supabase/supabase-js';
import { getPostSocialActions } from '@/lib/linkedin-api';

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL!;
const supabaseServiceKey = process.env.SUPABASE_SERVICE_ROLE_KEY!;

interface PostAnalytics {
    post_id: string;
    social_id: string;
    linkedin_post_urn: string;
    caption: string;
    published_at: string;
    reaction_counter: number;
    comment_counter: number;
    repost_counter: number;
    impressions_counter: number;
    analytics?: {
        impressions: number;
        engagements: number;
        engagement_rate: number;
        clicks: number;
        clickthrough_rate: number;
        followers_gained_from_this_post: number;
    };
}

interface AggregatedAnalytics {
    totalPosts: number;
    totalReactions: number;
    totalComments: number;
    totalReposts: number;
    totalImpressions: number;
    totalEngagements: number;
    totalClicks: number;
    avgEngagementRate: number;
    totalFollowersGained: number;
    posts: PostAnalytics[];
    topPerformingPost: PostAnalytics | null;
    lastUpdated: string | null;
}

/**
 * GET /api/analytics
 * 
 * Returns aggregated analytics for the user's published posts
 * Uses data stored in the database (updated via POST)
 */
export async function GET(request: NextRequest) {
    try {
        const authHeader = request.headers.get('authorization');
        if (!authHeader || !authHeader.startsWith('Bearer ')) {
            return NextResponse.json(
                { error: 'Missing or invalid authorization header' },
                { status: 401 }
            );
        }

        const token = authHeader.replace('Bearer ', '');
        const supabase = createClient(supabaseUrl, supabaseServiceKey);
        const { data: { user }, error: authError } = await supabase.auth.getUser(token);

        if (authError || !user) {
            return NextResponse.json(
                { error: 'Invalid or expired token' },
                { status: 401 }
            );
        }

        // Fetch published posts from database
        const { data: publishedPosts, error: postsError } = await supabase
            .from('posts')
            .select('id, linkedin_post_urn, caption, published_at, ai_content, analytics_data, analytics_updated_at')
            .eq('user_id', user.id)
            .not('linkedin_post_urn', 'is', null)
            // Sometimes published_at might be missing if we only have the URN
            .order('created_at', { ascending: false });

        if (postsError) {
            console.error('[Analytics] Error fetching posts:', postsError);
            return NextResponse.json(
                { error: 'Failed to fetch posts' },
                { status: 500 }
            );
        }

        console.log('[Analytics] Found', publishedPosts?.length || 0, 'published posts in database');

        if (!publishedPosts || publishedPosts.length === 0) {
            return NextResponse.json({
                success: true,
                analytics: {
                    totalPosts: 0,
                    totalReactions: 0,
                    totalComments: 0,
                    totalReposts: 0,
                    totalImpressions: 0,
                    totalEngagements: 0,
                    totalClicks: 0,
                    avgEngagementRate: 0,
                    totalFollowersGained: 0,
                    posts: [],
                    topPerformingPost: null,
                    lastUpdated: null,
                } as AggregatedAnalytics,
            });
        }

        // Aggregate analytics from stored data
        let totalReactions = 0;
        let totalComments = 0;
        let totalReposts = 0;
        let totalImpressions = 0;
        let totalEngagements = 0;
        let totalClicks = 0;
        let totalFollowersGained = 0;
        let engagementRateSum = 0;
        let postsWithAnalytics = 0;
        let lastUpdated: string | null = null;

        const postsWithData: PostAnalytics[] = publishedPosts.map((post) => {
            const analyticsData = post.analytics_data || {};

            totalReactions += analyticsData.reaction_counter || 0;
            totalComments += analyticsData.comment_counter || 0;
            totalReposts += analyticsData.repost_counter || 0;
            totalImpressions += analyticsData.impressions_counter || 0;

            if (analyticsData.analytics) {
                totalEngagements += analyticsData.analytics.engagements || 0;
                totalClicks += analyticsData.analytics.clicks || 0;
                totalFollowersGained += analyticsData.analytics.followers_gained_from_this_post || 0;
                if (analyticsData.analytics.engagement_rate) {
                    engagementRateSum += analyticsData.analytics.engagement_rate;
                    postsWithAnalytics++;
                }
            }

            if (post.analytics_updated_at) {
                if (!lastUpdated || new Date(post.analytics_updated_at) > new Date(lastUpdated)) {
                    lastUpdated = post.analytics_updated_at;
                }
            }

            return {
                post_id: post.id,
                social_id: post.linkedin_post_urn || '',
                linkedin_post_urn: post.linkedin_post_urn || '',
                caption: post.caption || post.ai_content?.body || '',
                published_at: post.published_at || '',
                reaction_counter: analyticsData.reaction_counter || 0,
                comment_counter: analyticsData.comment_counter || 0,
                repost_counter: analyticsData.repost_counter || 0,
                impressions_counter: analyticsData.impressions_counter || 0,
                analytics: analyticsData.analytics,
            };
        });

        // Find top performing post by engagement
        const topPerformingPost = postsWithData.reduce((top, post) => {
            const engagement = post.reaction_counter + post.comment_counter + post.repost_counter;
            const topEngagement = top ? (top.reaction_counter + top.comment_counter + top.repost_counter) : 0;
            return engagement > topEngagement ? post : top;
        }, null as PostAnalytics | null);

        const analytics: AggregatedAnalytics = {
            totalPosts: publishedPosts.length,
            totalReactions,
            totalComments,
            totalReposts,
            totalImpressions,
            totalEngagements,
            totalClicks,
            avgEngagementRate: postsWithAnalytics > 0 ? engagementRateSum / postsWithAnalytics : 0,
            totalFollowersGained,
            posts: postsWithData,
            topPerformingPost,
            lastUpdated,
        };

        return NextResponse.json({
            success: true,
            analytics,
        });

    } catch (error) {
        console.error('[Analytics] Error:', error);
        return NextResponse.json(
            { error: 'Failed to fetch analytics' },
            { status: 500 }
        );
    }
}

/**
 * POST /api/analytics
 * 
 * Refresh analytics data using LinkedIn Community Management API v202505
 * Updates likes/comments counts for all published posts
 */
export async function POST(request: NextRequest) {
    try {
        const authHeader = request.headers.get('authorization');
        if (!authHeader || !authHeader.startsWith('Bearer ')) {
            return NextResponse.json(
                { error: 'Missing or invalid authorization header' },
                { status: 401 }
            );
        }

        const token = authHeader.replace('Bearer ', '');
        const supabase = createClient(supabaseUrl, supabaseServiceKey);
        const { data: { user }, error: authError } = await supabase.auth.getUser(token);

        if (authError || !user) {
            return NextResponse.json(
                { error: 'Invalid or expired token' },
                { status: 401 }
            );
        }

        // Get LinkedIn Community tokens (has required scopes)
        const { data: communityData, error: communityError } = await supabase
            .from('linkedin_community_tokens')
            .select('access_token')
            .eq('user_id', user.id)
            .single();

        // Also try regular user_linkedin_auth as fallback (previously was linkedin_tokens)
        const { data: linkedinData, error: linkedinError } = await supabase
            .from('user_linkedin_auth')
            .select('linkedin_access_token')
            .eq('user_id', user.id)
            .single();

        let accessToken: string | null = null;

        if (!communityError && communityData?.access_token) {
            accessToken = communityData.access_token;
            console.log('[Analytics] Using community token for refresh');
        } else if (!linkedinError && linkedinData?.linkedin_access_token) {
            accessToken = linkedinData.linkedin_access_token;
            console.log('[Analytics] Using regular LinkedIn token for refresh');
        }

        if (!accessToken) {
            return NextResponse.json(
                { error: 'LinkedIn não conectado. Por favor, conecte sua conta.' },
                { status: 404 }
            );
        }

        // Fetch published posts from our database
        const { data: publishedPosts, error: postsError } = await supabase
            .from('posts')
            .select('id, linkedin_post_urn, analytics_data')
            .eq('user_id', user.id)
            .not('linkedin_post_urn', 'is', null);

        if (postsError) {
            console.error('[Analytics] Error fetching posts:', postsError);
            return NextResponse.json(
                { error: 'Failed to fetch posts' },
                { status: 500 }
            );
        }

        if (!publishedPosts || publishedPosts.length === 0) {
            return NextResponse.json({
                success: true,
                message: 'Nenhum post publicado encontrado',
                updatedCount: 0,
            });
        }

        console.log('[Analytics] Refreshing analytics for', publishedPosts.length, 'posts');

        let updatedCount = 0;

        // Import getSinglePostAnalytics at the top - Note: we need to also import it
        // For now, we'll create an inline implementation

        // Update analytics for each post using LinkedIn API
        for (const post of publishedPosts) {
            if (!post.linkedin_post_urn) continue;

            try {
                // Use the social actions API to get likes/comments count
                const socialActions = await getPostSocialActions(accessToken, post.linkedin_post_urn);

                // Also try to get impressions from memberCreatorPostAnalytics
                let impressionsData: { impressionCount?: number; uniqueImpressionsCount?: number } | null = null;
                try {
                    const { getSinglePostAnalytics } = await import('@/lib/linkedin-api');
                    impressionsData = await getSinglePostAnalytics(accessToken, post.linkedin_post_urn);
                    if (impressionsData) {
                        console.log('[Analytics] Got impressions for post:', post.id,
                            'impressions:', impressionsData.impressionCount,
                            'unique:', impressionsData.uniqueImpressionsCount);
                    }
                } catch (err) {
                    console.log('[Analytics] Could not get impressions for post:', post.id);
                }

                if (socialActions || impressionsData) {
                    const existingData = post.analytics_data || {};
                    const analyticsData = {
                        ...existingData,
                        reaction_counter: socialActions?.likes ?? existingData.reaction_counter ?? 0,
                        comment_counter: socialActions?.comments ?? existingData.comment_counter ?? 0,
                        repost_counter: existingData.repost_counter || 0,
                        // Use impressions from API if available, otherwise keep existing
                        impressions_counter: impressionsData?.impressionCount ??
                            impressionsData?.uniqueImpressionsCount ??
                            existingData.impressions_counter ?? 0,
                    };

                    const { error: updateError } = await supabase
                        .from('posts')
                        .update({
                            analytics_data: analyticsData,
                            analytics_updated_at: new Date().toISOString(),
                        })
                        .eq('id', post.id);

                    if (!updateError) {
                        updatedCount++;
                        console.log('[Analytics] Updated post:', post.id,
                            'likes:', analyticsData.reaction_counter,
                            'comments:', analyticsData.comment_counter,
                            'impressions:', analyticsData.impressions_counter);
                    }
                }
            } catch (err) {
                console.log('[Analytics] Failed to update post:', post.id, err);
                // Continue with other posts
            }
        }

        return NextResponse.json({
            success: true,
            message: `Analytics atualizados para ${updatedCount} posts`,
            updatedCount,
            totalPosts: publishedPosts.length,
        });

    } catch (error) {
        console.error('[Analytics] Refresh error:', error);
        return NextResponse.json(
            { error: 'Failed to refresh analytics' },
            { status: 500 }
        );
    }
}
