import { NextRequest, NextResponse } from 'next/server';
import { createClient } from '@/utils/supabase/server';
import { generateImage, getUserPhotos, UserPhotoData, fetchImageAsBase64, ReferenceImage } from '@/lib/posts/postGeneration';
import { checkRateLimit, checkApiRateLimit } from '@/lib/rateLimit';
import { uploadAndSaveImage, linkImageToPost } from '@/lib/storage/imageStorage';

export const dynamic = 'force-dynamic';

interface RouteParams {
  params: { postId: string };
}

const OPENAI_COMPLETIONS_URL = 'https://api.openai.com/v1/chat/completions';

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

  // Check usage rate limit for refinements
  const rateLimit = await checkRateLimit(user.id, 'refinement');
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

  // Also check image limit since we're generating a new image
  const imageLimit = await checkRateLimit(user.id, 'image');
  if (!imageLimit.allowed) {
    return NextResponse.json(
      {
        error: imageLimit.reason,
        usage: imageLimit.usage,
        limits: imageLimit.limits,
        resetAt: imageLimit.resetAt,
      },
      { status: 429 }
    );
  }

  // Get post
  const { data: post, error: fetchError } = await supabase
    .from('posts')
    .select('*')
    .eq('id', params.postId)
    .eq('user_id', user.id)
    .single();

  if (fetchError || !post) {
    return NextResponse.json({ error: 'Post não encontrado' }, { status: 404 });
  }

  // Get refinement instruction from user
  const body = await request.json();
  const { instruction, forceReanalyzePhotos = false } = body;

  if (!instruction || typeof instruction !== 'string') {
    return NextResponse.json(
      { error: 'Instrução de refinamento é obrigatória' },
      { status: 400 }
    );
  }

  const apiKey = process.env.OPENAI_API_KEY;
  if (!apiKey) {
    return NextResponse.json(
      { error: 'OpenAI API key não configurada' },
      { status: 500 }
    );
  }

  console.log('[refine-image] Starting image refinement');
  console.log('[refine-image] Instruction:', instruction);
  console.log('[refine-image] Force reanalyze photos:', forceReanalyzePhotos);

  try {
    // Get user's photos for personalization
    const userPhotos = await getUserPhotos(user.id);
    console.log('[refine-image] User photos found:', userPhotos.length);

    // Get user appearance description (with enhanced detail for refinement)
    let userDescription = '';

    if (userPhotos.length > 0) {
      const primaryPhoto = userPhotos.find(p => p.is_primary) || userPhotos[0];

      // Check if we should reanalyze or use cache
      if (forceReanalyzePhotos || !primaryPhoto.metadata?.appearance_description) {
        console.log('[refine-image] Analyzing user photos with enhanced detail...');
        userDescription = await getEnhancedUserDescription(userPhotos);

        // Cache the enhanced description
        if (userDescription && primaryPhoto.id) {
          await supabase
            .from('user_photos')
            .update({
              metadata: {
                ...primaryPhoto.metadata,
                appearance_description: userDescription,
                last_analyzed_at: new Date().toISOString(),
              }
            })
            .eq('id', primaryPhoto.id);
        }
      } else {
        userDescription = primaryPhoto.metadata.appearance_description;
      }
    }

    // Build refined image prompt - SIMPLE AND DIRECT
    const currentPrompt = post.generated_image_prompt ||
      post.ai_content?.suggestedImagePrompt ||
      '';

    console.log('[refine-image] Current prompt:', currentPrompt.substring(0, 100));
    console.log('[refine-image] User instruction:', instruction);

    const refinedPrompt = await buildRefinedImagePrompt(
      currentPrompt,
      instruction,
      userDescription,
      apiKey
    );

    console.log('[refine-image] Refined prompt generated');

    // Fetch the previous generated image to use as base for editing
    // IMPORTANT: Don't optimize base image - keep original quality for editing
    let baseImage: ReferenceImage | null = null;
    const previousImageUrl = post.generated_image_url || post.custom_image_url;

    if (previousImageUrl) {
      console.log('[refine-image] Fetching previous image for editing (no compression)...');
      baseImage = await fetchImageAsBase64(previousImageUrl, false); // Don't optimize - keep original quality
      if (baseImage) {
        console.log('[refine-image] ✅ Previous image loaded for editing (original quality)');
      } else {
        console.log('[refine-image] ⚠️ Could not load previous image, will generate new');
      }
    }

    // Update status to pending
    await supabase
      .from('posts')
      .update({ image_generation_status: 'pending' })
      .eq('id', params.postId);

    // Generate refined image - pass baseImage for editing if available
    const imageResult = await generateImage({
      prompt: refinedPrompt,
      userId: user.id,
      userPhotos: userPhotos.length > 0 ? userPhotos : undefined,
      baseImage: baseImage || undefined,
      isRefinement: !!baseImage, // Only true if we have a base image to edit
    });

    // Extract base64 data from the generated image
    const base64Match = imageResult.imageUrl.match(/^data:([^;]+);base64,(.+)$/);
    if (!base64Match) {
      throw new Error('Invalid image format returned from generator');
    }

    const base64Data = base64Match[2];

    // Upload to Supabase Storage and save metadata
    const savedImage = await uploadAndSaveImage(base64Data, {
      userId: user.id,
      postId: params.postId,
      prompt: refinedPrompt,
      modelUsed: 'vertex-gemini',
      isPersonalized: userPhotos.length > 0,
      generationParams: {
        ...imageResult.metadata,
        refinement_instruction: instruction,
        personalized: userPhotos.length > 0,
        photos_used: userPhotos.length,
        is_refinement: true,
      },
    });

    if (!savedImage.success || !savedImage.imageId || !savedImage.publicUrl) {
      throw new Error(savedImage.error || 'Failed to save refined image');
    }

    // Link image to the post
    await linkImageToPost(params.postId, savedImage.imageId, savedImage.publicUrl);

    // Save refinement history
    const refinementHistory = post.refinement_history || [];
    refinementHistory.push({
      type: 'image',
      instruction,
      previousPrompt: currentPrompt,
      newPrompt: refinedPrompt,
      imageId: savedImage.imageId,
      timestamp: new Date().toISOString(),
    });

    // Update post with new image
    const now = new Date().toISOString();
    const { data: updated, error: updateError } = await supabase
      .from('posts')
      .update({
        generated_image_url: savedImage.publicUrl,
        generated_image_prompt: refinedPrompt,
        generated_image_metadata: {
          ...imageResult.metadata,
          refinement_instruction: instruction,
          personalized: userPhotos.length > 0,
          photos_used: userPhotos.length,
          storage_path: savedImage.storagePath,
          image_id: savedImage.imageId,
        },
        refinement_history: refinementHistory,
        image_generation_status: 'ready',
        image_generated_at: now,
        last_refined_at: now,
        updated_at: now,
      })
      .eq('id', params.postId)
      .select()
      .single();

    if (updateError) {
      console.error('[refine-image] Update error:', updateError);
      return NextResponse.json({ error: 'Falha ao salvar imagem refinada' }, { status: 500 });
    }

    console.log('[refine-image] ✅ Image refined successfully');

    return NextResponse.json({
      success: true,
      post: updated,
      message: 'Imagem refinada com sucesso!',
      personalized: userPhotos.length > 0,
      imageUrl: savedImage.publicUrl,
    });

  } catch (error: any) {
    console.error('[refine-image] Error:', error);

    // Reset status on error
    await supabase
      .from('posts')
      .update({ image_generation_status: 'failed' })
      .eq('id', params.postId);

    return NextResponse.json(
      { error: error.message || 'Falha ao refinar imagem' },
      { status: 500 }
    );
  }
}

/**
 * Get enhanced user description from all photos
 */
async function getEnhancedUserDescription(userPhotos: UserPhotoData[]): Promise<string> {
  const apiKey = process.env.OPENAI_API_KEY;
  if (!apiKey || userPhotos.length === 0) return '';

  try {
    // Analyze up to 3 photos for better description
    const photosToAnalyze = userPhotos.slice(0, 3);

    const imageContent = photosToAnalyze.map(photo => ({
      type: 'image_url' as const,
      image_url: { url: photo.public_url, detail: 'high' as const }
    }));

    const response = await fetch(OPENAI_COMPLETIONS_URL, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${apiKey}`,
      },
      body: JSON.stringify({
        model: 'gpt-4o',
        max_tokens: 800,
        messages: [
          {
            role: 'system',
            content: `You are an expert at describing people's appearance for AI image generation.
Analyze ALL the photos provided and create a COMPREHENSIVE, DETAILED description of this person.
This description will be used to generate images where the person should look AS SIMILAR AS POSSIBLE to the photos.

Focus on CONSISTENT features across all photos:
- Gender and age range
- Face shape and structure
- Skin tone (be specific: light olive, medium brown, etc.)
- Hair: color, texture, style, length
- Eyes: shape, color, distinctive features
- Nose and mouth shape
- Facial hair (if any)
- Body type and build
- Any distinctive features (dimples, freckles, glasses, etc.)

Be EXTREMELY detailed and specific. This is crucial for generating accurate images.
Output ONLY the description, no explanations.`
          },
          {
            role: 'user',
            content: [
              ...imageContent,
              {
                type: 'text' as const,
                text: 'Analyze these photos and provide a comprehensive appearance description for AI image generation.'
              }
            ]
          }
        ],
      }),
    });

    if (!response.ok) {
      console.error('[getEnhancedUserDescription] API error:', response.status);
      return '';
    }

    const data = await response.json();
    return data.choices?.[0]?.message?.content || '';

  } catch (error) {
    console.error('[getEnhancedUserDescription] Error:', error);
    return '';
  }
}

/**
 * Build refined image prompt based on user instruction
 * SIMPLE AND ABSOLUTELY OBEDIENT
 */
async function buildRefinedImagePrompt(
  currentPrompt: string,
  instruction: string,
  userDescription: string,
  apiKey: string
): Promise<string> {
  try {
    const response = await fetch(OPENAI_COMPLETIONS_URL, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${apiKey}`,
      },
      body: JSON.stringify({
        model: 'gpt-4o-mini',
        temperature: 0.3, // Very low for maximum obedience
        max_tokens: 1500,
        messages: [
          {
            role: 'system',
            content: `You modify image prompts. Your ONLY job is to apply the user's instruction EXACTLY.

RULES:
1. DO EXACTLY what the user asks - nothing more, nothing less
2. If user says "change background" → change the ENTIRE background
3. If user says "remove X" → remove X COMPLETELY
4. If user says "add X" → add X EXACTLY as described
5. If user says "more X" → make it SIGNIFICANTLY more X
6. NEVER ignore user instructions
7. NEVER "improve" beyond what was asked

${userDescription ? `IMPORTANT: Keep this person description:\n${userDescription}` : ''}

Output ONLY the new prompt. No explanations.`
          },
          {
            role: 'user',
            content: `CURRENT PROMPT:
"""
${currentPrompt}
"""

INSTRUCTION: ${instruction}

New prompt:`
          }
        ],
      }),
    });

    if (!response.ok) {
      throw new Error(`OpenAI request failed: ${response.status}`);
    }

    const data = await response.json();
    let refinedPrompt = data.choices?.[0]?.message?.content?.trim() || currentPrompt;

    // Ensure person description is included
    if (userDescription && refinedPrompt.length > 0) {
      // Check if the prompt mentions a person
      const mentionsPerson = /person|man|woman|professional|individual/i.test(refinedPrompt);
      if (!mentionsPerson) {
        refinedPrompt = `${userDescription}\n\n${refinedPrompt}`;
      }
    }

    return refinedPrompt;

  } catch (error) {
    console.error('[buildRefinedImagePrompt] Error:', error);
    // Return modified current prompt as fallback
    return `${currentPrompt}\n\nMUST APPLY: ${instruction}`;
  }
}
