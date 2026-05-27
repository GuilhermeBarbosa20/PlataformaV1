import { NextRequest, NextResponse } from 'next/server';
import { createClient } from '@/utils/supabase/server';
import {
  generatePostContent,
  composeCaption,
  GeneratedPostContent,
} from '@/lib/posts/postGeneration';
import { fetchUserContentContext, appendRevisionHistory } from '@/lib/posts/context';

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

    const context = await fetchUserContentContext(supabase, user.id);

    const aiContent = await generatePostContent({
      date: post.scheduled_for,
      themes: context.themes,
      objectives: context.objectives,
    });

    const caption = composeCaption({ content: aiContent as GeneratedPostContent });
    const history = appendRevisionHistory(post, null);
    const now = new Date().toISOString();

    const { data: updated, error: updateError } = await supabase
      .from('posts')
      .update({
        ai_content: aiContent,
        ai_context: context,
        caption,
        ai_revision_history: history,
        last_generated_at: now,
        approval_status: 'aguardar',
        needs_regeneration: false,
        updated_at: now,
      })
      .eq('id', params.postId)
      .select()
      .single();

    if (updateError) {
      console.error('Regenerate update error:', updateError);
      return NextResponse.json({ error: 'Falha ao guardar nova versão' }, { status: 500 });
    }

    return NextResponse.json({ success: true, post: updated });
  } catch (error: any) {
    console.error('Regenerate route error:', error);
    return NextResponse.json(
      { error: error.message || 'Internal server error' },
      { status: 500 },
    );
  }
}
