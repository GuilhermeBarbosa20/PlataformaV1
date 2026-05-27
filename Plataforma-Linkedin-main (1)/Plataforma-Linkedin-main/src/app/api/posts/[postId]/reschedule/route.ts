import { NextRequest, NextResponse } from 'next/server';
import { createClient } from '@/utils/supabase/server';

export const dynamic = 'force-dynamic';

interface RouteParams {
    params: { postId: string };
}

/**
 * PATCH /api/posts/[postId]/reschedule
 * Update the scheduled date of a post (for drag-and-drop)
 * 
 * Body:
 * - scheduled_for: YYYY-MM-DD format
 */
export async function PATCH(request: NextRequest, { params }: RouteParams) {
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
        const { scheduled_for } = body;

        if (!scheduled_for) {
            return NextResponse.json(
                { error: 'scheduled_for é obrigatório' },
                { status: 400 }
            );
        }

        // Validate date format (YYYY-MM-DD)
        const dateRegex = /^\d{4}-\d{2}-\d{2}$/;
        if (!dateRegex.test(scheduled_for)) {
            return NextResponse.json(
                { error: 'Formato de data inválido. Use YYYY-MM-DD' },
                { status: 400 }
            );
        }

        // Verify post exists and belongs to user
        const { data: post, error: fetchError } = await supabase
            .from('posts')
            .select('id, scheduled_for, status')
            .eq('id', params.postId)
            .eq('user_id', user.id)
            .single();

        if (fetchError || !post) {
            return NextResponse.json(
                { error: 'Post não encontrado' },
                { status: 404 }
            );
        }

        // Don't allow rescheduling published posts
        if (post.status === 'published') {
            return NextResponse.json(
                { error: 'Não é possível reagendar posts já publicados' },
                { status: 400 }
            );
        }

        // Update the scheduled date
        const { data: updated, error: updateError } = await supabase
            .from('posts')
            .update({
                scheduled_for,
                updated_at: new Date().toISOString(),
            })
            .eq('id', params.postId)
            .select()
            .single();

        if (updateError) {
            console.error('[Reschedule] Error updating post:', updateError);
            return NextResponse.json(
                { error: 'Falha ao reagendar post' },
                { status: 500 }
            );
        }

        return NextResponse.json({
            success: true,
            post: updated,
            message: `Post reagendado para ${scheduled_for}`,
        });

    } catch (error) {
        console.error('[Reschedule] Error:', error);
        return NextResponse.json(
            { error: 'Failed to reschedule post' },
            { status: 500 }
        );
    }
}
