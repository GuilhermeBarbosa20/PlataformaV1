import { NextRequest, NextResponse } from 'next/server';
import { createClient } from '@/utils/supabase/server';

export const dynamic = 'force-dynamic';

/**
 * GET /api/trends/posts
 * Get relevant posts for the trends page
 */
export async function GET(request: NextRequest) {
    try {
        const supabase = await createClient();
        const { data: { user }, error: authError } = await supabase.auth.getUser();

        if (authError || !user) {
            return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
        }

        const { searchParams } = new URL(request.url);
        const showAll = searchParams.get('all') === 'true';

        // Get posts - either all analyzed or only relevant ones
        let query = supabase
            .from('monitored_posts')
            .select('*, monitored_profiles(profile_name, profile_vanity_name, profile_avatar_url)')
            .eq('user_id', user.id)
            .eq('is_analyzed', true)
            .is('user_action', null) // Only show posts not yet acted upon
            .order('ai_relevance_score', { ascending: false })
            .order('posted_at', { ascending: false })
            .limit(50);

        if (!showAll) {
            query = query.eq('is_relevant', true);
        }

        const { data: posts, error: postsError } = await query;

        if (postsError) {
            console.error('[TRENDS POSTS] Error fetching posts:', postsError);
            return NextResponse.json({ error: 'Failed to fetch posts' }, { status: 500 });
        }

        // Get stats
        const { count: totalCount } = await supabase
            .from('monitored_posts')
            .select('*', { count: 'exact', head: true })
            .eq('user_id', user.id);

        const { count: relevantCount } = await supabase
            .from('monitored_posts')
            .select('*', { count: 'exact', head: true })
            .eq('user_id', user.id)
            .eq('is_relevant', true)
            .is('user_action', null);

        const { count: unanalyzedCount } = await supabase
            .from('monitored_posts')
            .select('*', { count: 'exact', head: true })
            .eq('user_id', user.id)
            .eq('is_analyzed', false);

        return NextResponse.json({
            success: true,
            posts: posts || [],
            stats: {
                total: totalCount || 0,
                relevant: relevantCount || 0,
                unanalyzed: unanalyzedCount || 0,
            },
        });

    } catch (error: any) {
        console.error('[TRENDS POSTS] Error:', error);
        return NextResponse.json({ error: error.message || 'Internal server error' }, { status: 500 });
    }
}

/**
 * POST /api/trends/posts
 * Mark a post with an action (like, comment, repost, dismiss)
 */
export async function POST(request: NextRequest) {
    try {
        const supabase = await createClient();
        const { data: { user }, error: authError } = await supabase.auth.getUser();

        if (authError || !user) {
            return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
        }

        const body = await request.json();
        const { post_id, action } = body;

        if (!post_id || !action) {
            return NextResponse.json({ error: 'post_id and action are required' }, { status: 400 });
        }

        const validActions = ['liked', 'commented', 'reposted', 'dismissed'];
        if (!validActions.includes(action)) {
            return NextResponse.json({ error: 'Invalid action' }, { status: 400 });
        }

        const { error: updateError } = await supabase
            .from('monitored_posts')
            .update({
                user_action: action,
                user_action_at: new Date().toISOString(),
                updated_at: new Date().toISOString(),
            })
            .eq('id', post_id)
            .eq('user_id', user.id);

        if (updateError) {
            console.error('[TRENDS POSTS] Error updating post:', updateError);
            return NextResponse.json({ error: 'Failed to update post' }, { status: 500 });
        }

        return NextResponse.json({
            success: true,
            message: `Post marcado como ${action}`,
        });

    } catch (error: any) {
        console.error('[TRENDS POSTS] Error:', error);
        return NextResponse.json({ error: error.message || 'Internal server error' }, { status: 500 });
    }
}
