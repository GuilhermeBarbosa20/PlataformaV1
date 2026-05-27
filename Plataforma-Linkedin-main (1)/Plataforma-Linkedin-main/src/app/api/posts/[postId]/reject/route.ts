import { NextRequest, NextResponse } from 'next/server';
import { createClient } from '@/utils/supabase/server';

export const dynamic = 'force-dynamic';

interface RouteParams {
  params: { postId: string };
}

export async function POST(request: NextRequest, { params }: RouteParams) {
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
      .select('id')
      .eq('id', params.postId)
      .eq('user_id', user.id)
      .single();

    if (fetchError || !post) {
      return NextResponse.json({ error: 'Post não encontrado' }, { status: 404 });
    }

    const body = await request.json().catch(() => ({}));
    const reason = body?.reason ?? null;

    const { data: updated, error: updateError } = await supabase
      .from('posts')
      .update({
        approval_status: 'revisar',
        approval_notes: reason,
        needs_regeneration: true,
        generated_image_url: null,
        generated_image_metadata: {},
        image_generation_status: 'idle',
        image_generated_at: null,
        // Reset approval stages
        text_approved: false,
        text_approved_at: null,
        image_approved: false,
        image_approved_at: null,
        post_approved: false,
        post_approved_at: null,
      })
      .eq('id', params.postId)
      .select()
      .single();

    if (updateError) {
      console.error('Reject update error:', updateError);
      return NextResponse.json({ error: 'Falha ao atualizar post' }, { status: 500 });
    }

    return NextResponse.json({ success: true, post: updated });
  } catch (error: any) {
    console.error('Reject route error:', error);
    return NextResponse.json(
      { error: error.message || 'Internal server error' },
      { status: 500 },
    );
  }
}
