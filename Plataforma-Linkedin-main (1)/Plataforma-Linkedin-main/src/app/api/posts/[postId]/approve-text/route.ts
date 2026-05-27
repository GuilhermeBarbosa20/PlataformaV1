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
      .select('*')
      .eq('id', params.postId)
      .eq('user_id', user.id)
      .single();

    if (fetchError || !post) {
      return NextResponse.json({ error: 'Post não encontrado' }, { status: 404 });
    }

    const now = new Date().toISOString();

    const { data: updated, error: updateError } = await supabase
      .from('posts')
      .update({
        text_approved: true,
        text_approved_at: now,
        approval_status: 'aprovado', // Mark as approved (text approved)
        approved_at: now,
        needs_regeneration: false,
        updated_at: now,
      })
      .eq('id', params.postId)
      .select()
      .single();

    if (updateError) {
      console.error('Approve text error:', updateError);
      return NextResponse.json({ error: 'Falha ao aprovar texto' }, { status: 500 });
    }

    return NextResponse.json({ success: true, post: updated });
  } catch (error: any) {
    console.error('Approve text route error:', error);
    return NextResponse.json(
      { error: error.message || 'Internal server error' },
      { status: 500 },
    );
  }
}
