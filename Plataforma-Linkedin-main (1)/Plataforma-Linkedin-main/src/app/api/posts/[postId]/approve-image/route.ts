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

    // Check if text is approved first
    if (!post.text_approved) {
      return NextResponse.json(
        { error: 'Aprove o texto primeiro antes de aprovar a imagem' },
        { status: 400 }
      );
    }

    // Check if there's an image to approve
    if (!post.generated_image_url && !post.custom_image_url) {
      return NextResponse.json(
        { error: 'Nenhuma imagem para aprovar. Gere ou envie uma imagem primeiro.' },
        { status: 400 }
      );
    }

    const now = new Date().toISOString();

    const { data: updated, error: updateError } = await supabase
      .from('posts')
      .update({
        image_approved: true,
        image_approved_at: now,
        updated_at: now,
      })
      .eq('id', params.postId)
      .select()
      .single();

    if (updateError) {
      console.error('Approve image error:', updateError);
      return NextResponse.json({ error: 'Falha ao aprovar imagem' }, { status: 500 });
    }

    return NextResponse.json({ success: true, post: updated });
  } catch (error: any) {
    console.error('Approve image route error:', error);
    return NextResponse.json(
      { error: error.message || 'Internal server error' },
      { status: 500 },
    );
  }
}
