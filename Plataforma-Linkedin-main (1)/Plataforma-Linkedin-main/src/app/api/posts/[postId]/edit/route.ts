import { NextRequest, NextResponse } from 'next/server';
import { createClient } from '@/utils/supabase/server';

export const dynamic = 'force-dynamic';

interface RouteParams {
    params: { postId: string };
}

/**
 * PATCH /api/posts/[postId]/edit
 * Simple endpoint to edit post caption directly
 */
export async function PATCH(request: NextRequest, { params }: RouteParams) {
    try {
        const supabase = await createClient();
        const {
            data: { user },
            error: authError,
        } = await supabase.auth.getUser();

        if (authError || !user) {
            return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
        }

        const { data: post, error: fetchError } = await supabase
            .from('posts')
            .select('*')
            .eq('id', params.postId)
            .eq('user_id', user.id)
            .single();

        if (fetchError || !post) {
            return NextResponse.json({ error: 'Post não encontrado' }, { status: 404 });
        }

        const body = await request.json();
        const { caption } = body;

        if (!caption || typeof caption !== 'string') {
            return NextResponse.json(
                { error: 'Caption é obrigatório' },
                { status: 400 },
            );
        }

        const now = new Date().toISOString();

        const { data: updated, error: updateError } = await supabase
            .from('posts')
            .update({
                caption: caption.trim(),
                updated_at: now,
                // Mark as needing re-approval if it was already approved
                approval_status: post.approval_status === 'aprovado' ? 'aguardar' : post.approval_status,
            })
            .eq('id', params.postId)
            .select()
            .single();

        if (updateError) {
            console.error('[edit-post] Update error:', updateError);
            return NextResponse.json({ error: 'Falha ao atualizar post' }, { status: 500 });
        }

        console.log('[edit-post] Post updated successfully:', params.postId);
        return NextResponse.json({ success: true, post: updated });

    } catch (error: any) {
        console.error('[edit-post] Error:', error);
        return NextResponse.json(
            { error: error.message || 'Internal server error' },
            { status: 500 },
        );
    }
}
