import { NextRequest, NextResponse } from 'next/server';
import { createClient } from '@/utils/supabase/server';
import { generateImage, getUserPhotos } from '@/lib/posts/postGeneration';
import { checkRateLimit, checkApiRateLimit } from '@/lib/rateLimit';
import { uploadAndSaveImage, linkImageToPost } from '@/lib/storage/imageStorage';
import { getUserPrompt } from '@/lib/prompts/getPrompt';

export const dynamic = 'force-dynamic';

interface RouteParams {
  params: { postId: string };
}

export async function POST(request: NextRequest, { params }: RouteParams) {
  const supabase = await createClient();
  const {
    data: { user },
    error: authError,
  } = await supabase.auth.getUser();

  if (authError || !user) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  // Check API rate limit (abuse prevention)
  const apiLimit = checkApiRateLimit(user.id);
  if (!apiLimit.allowed) {
    return NextResponse.json(
      { error: `Too many requests. Retry after ${apiLimit.retryAfter} seconds.` },
      { status: 429 }
    );
  }

  // Check usage rate limit (plan limits)
  const rateLimit = await checkRateLimit(user.id, 'image');
  if (!rateLimit.allowed) {
    return NextResponse.json(
      {
        error: rateLimit.reason,
        usage: rateLimit.usage,
        limits: rateLimit.limits,
        resetAt: rateLimit.resetAt,
      },
      { status: 429 }
    );
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

  if (post.approval_status !== 'aprovado') {
    return NextResponse.json(
      { error: 'Só é possível gerar imagem após aprovação do texto' },
      { status: 400 },
    );
  }

  const body = await request.json().catch(() => ({}));

  // Try to get user's custom image prompt and generate based on post content
  let prompt = body?.prompt || post.generated_image_prompt || post.ai_content?.suggestedImagePrompt;

  // If no existing prompt, generate one using user's custom image_prompt template
  if (!prompt && post.caption) {
    console.log('[generate-image] Generating image prompt using custom template...');

    // Fetch user agent for themes
    const { data: userAgent } = await supabase
      .from('user_agents')
      .select('themes')
      .eq('user_id', user.id)
      .single();

    // Get custom image_prompt or use default
    const imagePromptTemplate = await getUserPrompt(
      supabase,
      user.id,
      'image_prompt',
      {
        post_content: post.caption.slice(0, 500),
        themes: userAgent?.themes || 'tecnologia, inovação',
      }
    );

    if (imagePromptTemplate) {
      // Use OpenAI to generate image prompt based on template
      const apiKey = process.env.OPENAI_API_KEY;
      if (apiKey) {
        try {
          const response = await fetch('https://api.openai.com/v1/chat/completions', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'Authorization': `Bearer ${apiKey}`,
            },
            body: JSON.stringify({
              model: 'gpt-4o-mini',
              max_tokens: 300,
              messages: [
                {
                  role: 'system',
                  content: imagePromptTemplate,
                },
                {
                  role: 'user',
                  content: `Gera um prompt em inglês para criar uma imagem profissional para este post do LinkedIn:\n\n${post.caption.slice(0, 500)}`,
                },
              ],
            }),
          });

          if (response.ok) {
            const data = await response.json();
            prompt = data.choices?.[0]?.message?.content || '';
            console.log('[generate-image] Generated custom prompt:', prompt.substring(0, 100) + '...');
          }
        } catch (error) {
          console.error('[generate-image] Error generating custom prompt:', error);
        }
      }
    }

    // Fallback to generic prompt
    if (!prompt) {
      prompt = `Foto profissional relacionada a: ${post.caption.slice(0, 200)}`;
    }
  }

  if (!prompt) {
    return NextResponse.json(
      { error: 'Não existe um prompt válido para gerar a imagem' },
      { status: 400 },
    );
  }

  // Fetch user's photos for personalized image generation
  console.log('[generate-image] Fetching user photos for personalization...');
  const userPhotos = await getUserPhotos(user.id);
  console.log('[generate-image] User photos found:', userPhotos.length);

  // Check if user has reference images enabled in settings
  const { data: userSettings } = await supabase
    .from('user_settings')
    .select('reference_images_enabled')
    .eq('user_id', user.id)
    .single();

  const useIdentityLock = userSettings?.reference_images_enabled !== false; // Default to true
  console.log('[generate-image] Identity Lock enabled:', useIdentityLock);

  await supabase
    .from('posts')
    .update({ image_generation_status: 'pending' })
    .eq('id', params.postId);

  try {
    // Pass userId and photos for personalized generation
    const imageResult = await generateImage({
      prompt,
      userId: user.id,
      userPhotos: userPhotos.length > 0 ? userPhotos : undefined,
      useIdentityLock, // Respect user's preference
    });

    // Extract base64 data from the generated image
    // imageUrl format: data:image/png;base64,<base64data>
    const base64Match = imageResult.imageUrl.match(/^data:([^;]+);base64,(.+)$/);
    if (!base64Match) {
      throw new Error('Invalid image format returned from generator');
    }

    const base64Data = base64Match[2];

    // Upload to Supabase Storage and save metadata
    const savedImage = await uploadAndSaveImage(base64Data, {
      userId: user.id,
      postId: params.postId,
      prompt,
      modelUsed: 'vertex-gemini',
      isPersonalized: userPhotos.length > 0,
      generationParams: {
        ...imageResult.metadata,
        personalized: userPhotos.length > 0,
        photos_used: userPhotos.length,
      },
    });

    if (!savedImage.success || !savedImage.imageId || !savedImage.publicUrl) {
      throw new Error(savedImage.error || 'Failed to save image');
    }

    // Link image to the post
    await linkImageToPost(params.postId, savedImage.imageId, savedImage.publicUrl);

    const now = new Date().toISOString();

    const { data: updated, error: updateError } = await supabase
      .from('posts')
      .update({
        generated_image_url: savedImage.publicUrl,
        generated_image_prompt: prompt,
        generated_image_metadata: {
          ...imageResult.metadata,
          personalized: userPhotos.length > 0,
          photos_used: userPhotos.length,
          storage_path: savedImage.storagePath,
          image_id: savedImage.imageId,
        },
        image_provider: 'vertex-gemini',
        image_generation_status: 'ready',
        image_generated_at: now,
        updated_at: now,
      })
      .eq('id', params.postId)
      .select()
      .single();

    if (updateError) {
      console.error('Image update error:', updateError);
      return NextResponse.json({ error: 'Falha ao guardar imagem' }, { status: 500 });
    }

    return NextResponse.json({
      success: true,
      post: updated,
      personalized: userPhotos.length > 0,
      imageUrl: savedImage.publicUrl,
    });
  } catch (error: any) {
    console.error('Image generation error:', error);
    await supabase
      .from('posts')
      .update({ image_generation_status: 'failed' })
      .eq('id', params.postId);

    return NextResponse.json(
      { error: error.message || 'Falha ao gerar imagem' },
      { status: 500 },
    );
  }
}
