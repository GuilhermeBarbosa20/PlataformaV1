import { NextRequest, NextResponse } from 'next/server';
import { createClient } from '@/utils/supabase/server';
import { composeCaption } from '@/lib/posts/postGeneration';
import { appendRevisionHistory } from '@/lib/posts/context';

export const dynamic = 'force-dynamic';

interface RouteParams {
  params: { postId: string };
}

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

    const body = await request.json().catch(() => ({}));
    const newContent = body?.aiContent ?? null;
    const manualCaption = body?.caption ?? null;
    const notes = body?.approvalNotes ?? undefined;

    if (!newContent && !manualCaption && typeof notes === 'undefined') {
      return NextResponse.json(
        { error: 'Nenhuma alteração recebida' },
        { status: 400 },
      );
    }

    const now = new Date().toISOString();
    const updates: Record<string, any> = {
      updated_at: now,
    };

    if (typeof notes !== 'undefined') {
      updates.approval_notes = notes;
    }

    if (manualCaption) {
      updates.caption = manualCaption;
    }

    if (newContent) {
      const history = appendRevisionHistory(post, null);
      updates.ai_content = newContent;
      updates.caption = manualCaption ?? composeCaption({ content: newContent });
      updates.ai_revision_history = history;
      updates.approval_status = 'aguardar';
      updates.needs_regeneration = false;
    }

    const { data: updated, error: updateError } = await supabase
      .from('posts')
      .update(updates)
      .eq('id', params.postId)
      .select()
      .single();

    if (updateError) {
      console.error('Update post error:', updateError);
      return NextResponse.json({ error: 'Falha ao atualizar post' }, { status: 500 });
    }

    return NextResponse.json({ success: true, post: updated });
  } catch (error: any) {
    console.error('Update route error:', error);
    return NextResponse.json(
      { error: error.message || 'Internal server error' },
      { status: 500 },
    );
  }
}
