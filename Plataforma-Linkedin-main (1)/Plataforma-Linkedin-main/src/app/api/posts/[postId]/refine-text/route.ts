import { NextRequest, NextResponse } from 'next/server';
import { createClient } from '@/utils/supabase/server';
import { checkRateLimit, checkApiRateLimit } from '@/lib/rateLimit';

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

  // Check usage rate limit (plan limits)
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

  // Get post - FRESH from database
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
  const { instruction } = body;

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

  console.log('[refine-text] Starting text refinement');
  console.log('[refine-text] Post ID:', params.postId);
  console.log('[refine-text] User instruction:', instruction);

  try {
    // Get the CURRENT text of the post (most recent version)
    const currentCaption = post.caption || '';
    const currentBody = post.ai_content?.body || '';
    const currentHashtags = post.ai_content?.hashtags || [];
    
    // Use caption if it exists (it's the refined version), otherwise use ai_content.body
    const textToRefine = currentCaption || currentBody;
    
    if (!textToRefine) {
      console.error('[refine-text] No text to refine - both caption and body are empty');
      return NextResponse.json({ error: 'Não há texto para refinar' }, { status: 400 });
    }
    
    console.log('[refine-text] Text to refine length:', textToRefine.length);
    console.log('[refine-text] Text preview:', textToRefine.substring(0, 100));

    // ============================================
    // SIMPLE, DIRECT, OBEDIENT PROMPT
    // ============================================
    const systemPrompt = `Você é um editor de texto. Sua ÚNICA função é modificar o texto EXATAMENTE como o usuário pedir.

REGRAS ABSOLUTAS:
1. FAÇA EXATAMENTE o que o usuário pediu - NADA MAIS, NADA MENOS
2. Se pedir "encurtar" ou "mais curto" → REDUZA DRASTICAMENTE para 2-3 parágrafos no máximo
3. Se pedir "remover X" → remova COMPLETAMENTE X
4. Se pedir "mudar tom" → mude COMPLETAMENTE o tom
5. Se pedir "só X parágrafos" → retorne APENAS X parágrafos
6. Se pedir "objetivo" ou "direto" → vá DIRETO ao ponto, sem floreios
7. NUNCA adicione conteúdo que o usuário não pediu
8. NUNCA ignore instruções do usuário
9. NUNCA "melhore" além do que foi pedido
10. NUNCA retorne o texto original sem modificações

Responda APENAS com o texto modificado. Sem explicações. Sem comentários. Sem markdown.`;

    const userPrompt = `Aqui está o texto atual que você deve modificar:

"""
${textToRefine}
"""

INSTRUÇÃO DO USUÁRIO: ${instruction}

Agora retorne o texto MODIFICADO de acordo com a instrução acima. Aplique a instrução de forma COMPLETA e RADICAL.`;

    const response = await fetch(OPENAI_COMPLETIONS_URL, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${apiKey}`,
      },
      body: JSON.stringify({
        model: 'gpt-4o-mini',
        temperature: 0.3, // Very low for maximum obedience
        max_tokens: 2000,
        messages: [
          { role: 'system', content: systemPrompt },
          { role: 'user', content: userPrompt },
        ],
      }),
    });

    if (!response.ok) {
      const errorText = await response.text();
      console.error('[refine-text] OpenAI error:', errorText);
      throw new Error(`OpenAI request failed: ${response.status}`);
    }

    const completion = await response.json();
    const refinedText = completion?.choices?.[0]?.message?.content?.trim();

    if (!refinedText) {
      throw new Error('OpenAI response missing content');
    }

    console.log('[refine-text] Original length:', textToRefine.length);
    console.log('[refine-text] Refined length:', refinedText.length);
    console.log('[refine-text] Refined text generated successfully');

    // Save refinement history
    const refinementHistory = post.refinement_history || [];
    refinementHistory.push({
      type: 'text',
      instruction,
      previousContent: textToRefine,
      newContent: refinedText,
      timestamp: new Date().toISOString(),
    });

    // Update post with refined text
    const { data: updated, error: updateError } = await supabase
      .from('posts')
      .update({
        caption: refinedText,
        refinement_history: refinementHistory,
        last_refined_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      })
      .eq('id', params.postId)
      .select()
      .single();

    if (updateError) {
      console.error('[refine-text] Update error:', updateError);
      return NextResponse.json({ error: 'Falha ao salvar refinamento' }, { status: 500 });
    }

    return NextResponse.json({
      success: true,
      post: updated,
      refinedText,
      previousText: textToRefine,
      message: 'Texto refinado com sucesso!',
    });

  } catch (error: any) {
    console.error('[refine-text] Error:', error);
    return NextResponse.json(
      { error: error.message || 'Falha ao refinar texto' },
      { status: 500 }
    );
  }
}
