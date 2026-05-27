import { NextRequest, NextResponse } from 'next/server';
import { createClient } from '@/utils/supabase/server';

export const dynamic = 'force-dynamic';

/**
 * POST /api/posts/create-from-news
 * Create a new post from a generated news article
 * 
 * Body:
 * - caption: Full post text
 * - ai_content: Generated post structure
 * - source: { type, title, link, feedName }
 * - scheduled_for: Date string (YYYY-MM-DD)
 */
export async function POST(request: NextRequest) {
    try {
        const supabase = await createClient();
        const { data: { user }, error: authError } = await supabase.auth.getUser();

        if (authError || !user) {
            return NextResponse.json(
                { error: 'Unauthorized' },
                { status: 401 }
            );
        }

        const body = await request.json();
        const { caption, ai_content, source, scheduled_for } = body;

        if (!caption) {
            return NextResponse.json(
                { error: 'Caption é obrigatório' },
                { status: 400 }
            );
        }

        // Find the last scheduled post to determine the next available date
        const { data: lastPost } = await supabase
            .from('posts')
            .select('scheduled_for')
            .eq('user_id', user.id)
            .order('scheduled_for', { ascending: false })
            .limit(1)
            .single();

        // Calculate next available date (last scheduled date + 1 day, or today if no posts)
        let nextDate: string;
        if (lastPost?.scheduled_for) {
            const lastDate = new Date(lastPost.scheduled_for);
            lastDate.setDate(lastDate.getDate() + 1);
            nextDate = lastDate.toISOString().split('T')[0];
        } else {
            // No existing posts, start from today
            nextDate = new Date().toISOString().split('T')[0];
        }

        // Create the post with smart scheduling
        const now = new Date().toISOString();
        const { data: post, error } = await supabase
            .from('posts')
            .insert({
                user_id: user.id,
                caption,
                ai_content: ai_content || {},
                ai_context: {
                    source: source || {},
                    generated_from: 'rss_news',
                },
                scheduled_for: nextDate,
                approval_status: 'aguardar',
                needs_regeneration: false,
                created_at: now,
                updated_at: now,
            })
            .select()
            .single();

        if (error) {
            console.error('[Create Post from News] Error:', error);
            return NextResponse.json(
                { error: 'Falha ao criar post' },
                { status: 500 }
            );
        }

        return NextResponse.json({
            success: true,
            post,
            message: 'Post criado com sucesso!',
        });

    } catch (error) {
        console.error('[Create Post from News] Error:', error);
        return NextResponse.json(
            { error: 'Failed to create post' },
            { status: 500 }
        );
    }
}
