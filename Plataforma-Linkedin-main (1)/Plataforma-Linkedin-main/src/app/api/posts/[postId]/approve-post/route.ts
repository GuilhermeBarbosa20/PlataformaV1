import { NextRequest, NextResponse } from 'next/server';
import { createClient } from '@/utils/supabase/server';
import { publishToLinkedIn, validateLinkedInAuth } from '@/lib/linkedin-api';

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

    // Check if text is approved
    if (!post.text_approved) {
      return NextResponse.json(
        { error: 'Aprove o texto primeiro' },
        { status: 400 }
      );
    }

    // Check if already published
    if (post.linkedin_post_urn) {
      return NextResponse.json(
        { error: 'Este post já foi publicado no LinkedIn' },
        { status: 400 }
      );
    }

    // Get LinkedIn auth credentials
    console.log('[approve-post] Looking up LinkedIn auth for user:', user.id);

    const { data: linkedinAuth, error: linkedinAuthError } = await supabase
      .from('user_linkedin_auth')
      .select('linkedin_access_token, linkedin_person_urn, token_expires_at')
      .eq('user_id', user.id)
      .single();

    console.log('[approve-post] LinkedIn auth lookup result:', {
      found: !!linkedinAuth,
      error: linkedinAuthError?.message || null,
      hasToken: !!linkedinAuth?.linkedin_access_token,
      hasPersonUrn: !!linkedinAuth?.linkedin_person_urn,
      expiresAt: linkedinAuth?.token_expires_at || null,
    });

    if (linkedinAuthError || !linkedinAuth) {
      console.error('[approve-post] LinkedIn auth not found:', linkedinAuthError);
      return NextResponse.json(
        { error: 'Credenciais do LinkedIn não encontradas. Faça login novamente com o LinkedIn.' },
        { status: 401 }
      );
    }

    // Check if token is expired
    if (linkedinAuth.token_expires_at) {
      const expiresAt = new Date(linkedinAuth.token_expires_at);
      const now = new Date();

      if (now >= expiresAt) {
        console.log('[approve-post] LinkedIn token expired at:', expiresAt);
        return NextResponse.json(
          { error: 'Seu token do LinkedIn expirou. Faça login novamente com o LinkedIn.' },
          { status: 401 }
        );
      }
    }

    // Validate LinkedIn auth
    const auth = {
      access_token: linkedinAuth.linkedin_access_token,
      person_urn: linkedinAuth.linkedin_person_urn,
    };

    if (!validateLinkedInAuth(auth)) {
      return NextResponse.json(
        { error: 'Token do LinkedIn inválido. Faça login novamente.' },
        { status: 401 }
      );
    }

    // Build the post text
    let postText = '';

    // Use caption if available (refined text), otherwise build from ai_content
    if (post.caption && post.caption !== 'Conteúdo em preparação') {
      postText = post.caption;
    } else if (post.ai_content) {
      const parts = [];
      if (post.ai_content.headline) parts.push(post.ai_content.headline);
      if (post.ai_content.hook) parts.push(post.ai_content.hook);
      if (post.ai_content.body) parts.push(post.ai_content.body);
      if (post.ai_content.cta) parts.push(post.ai_content.cta);

      postText = parts.filter(Boolean).join('\n\n');

      // Add hashtags
      if (post.ai_content.hashtags && post.ai_content.hashtags.length > 0) {
        const hashtags = post.ai_content.hashtags
          .map((tag: string) => tag.startsWith('#') ? tag : `#${tag}`)
          .join(' ');
        postText += '\n\n' + hashtags;
      }
    }

    if (!postText) {
      return NextResponse.json(
        { error: 'Nenhum texto disponível para publicar' },
        { status: 400 }
      );
    }

    console.log('[approve-post] Publishing to LinkedIn...');
    console.log('[approve-post] Post ID:', params.postId);
    console.log('[approve-post] Has image:', !!post.generated_image_url);

    // Publish to LinkedIn
    const publishResult = await publishToLinkedIn(auth, {
      text: postText,
      imageUrl: post.generated_image_url || post.custom_image_url,
      visibility: 'PUBLIC',
    });

    if (!publishResult.success) {
      console.error('[approve-post] LinkedIn publish failed:', publishResult.error);

      // Save the error
      await supabase
        .from('posts')
        .update({
          publish_error: publishResult.error,
          updated_at: new Date().toISOString(),
        })
        .eq('id', params.postId);

      return NextResponse.json(
        { error: publishResult.error || 'Falha ao publicar no LinkedIn' },
        { status: 500 }
      );
    }

    console.log('[approve-post] Successfully published! URN:', publishResult.linkedinPostUrn);

    const now = new Date().toISOString();

    // Update post as published
    const { data: updated, error: updateError } = await supabase
      .from('posts')
      .update({
        post_approved: true,
        post_approved_at: now,
        linkedin_post_urn: publishResult.linkedinPostUrn,
        published_at: now,
        status: 'published',
        publish_error: null,
        updated_at: now,
      })
      .eq('id', params.postId)
      .select()
      .single();

    if (updateError) {
      console.error('Approve post error:', updateError);
      return NextResponse.json({ error: 'Falha ao atualizar post' }, { status: 500 });
    }

    return NextResponse.json({
      success: true,
      post: updated,
      linkedinPostUrn: publishResult.linkedinPostUrn,
      message: '🎉 Post publicado no LinkedIn com sucesso!'
    });
  } catch (error: any) {
    console.error('Approve post route error:', error);
    return NextResponse.json(
      { error: error.message || 'Internal server error' },
      { status: 500 },
    );
  }
}
