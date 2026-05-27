import { NextRequest, NextResponse } from 'next/server';
import { createClient } from '@/utils/supabase/server';
import { fetchUserContentContext } from '@/lib/posts/context';

export const dynamic = 'force-dynamic';

const OPENAI_API_KEY = process.env.OPENAI_API_KEY;
const OPENAI_COMPLETIONS_URL = 'https://api.openai.com/v1/chat/completions';

interface NewsArticle {
    title: string;
    description: string;
    link: string;
    feedName: string;
}

interface GeneratedPost {
    headline: string;
    hook: string;
    body: string;
    cta: string;
    hashtags: string[];
    tone: string;
}

/**
 * POST /api/rss/generate-post
 * Generate a LinkedIn post from a news article
 * 
 * Body:
 * - article: { title, description, link, feedName }
 */
export async function POST(request: NextRequest) {
    try {
        if (!OPENAI_API_KEY) {
            return NextResponse.json(
                { error: 'OpenAI API key not configured' },
                { status: 503 }
            );
        }

        const supabase = await createClient();
        const { data: { user }, error: authError } = await supabase.auth.getUser();

        if (authError || !user) {
            return NextResponse.json(
                { error: 'Unauthorized' },
                { status: 401 }
            );
        }

        const body = await request.json();
        const article: NewsArticle = body.article;

        if (!article || !article.title) {
            return NextResponse.json(
                { error: 'Artigo é obrigatório' },
                { status: 400 }
            );
        }

        // Fetch user context (themes, objectives)
        const context = await fetchUserContentContext(supabase, user.id);

        // Fetch user's objectives with more detail
        const { data: objectives } = await supabase
            .from('user_objectives')
            .select('objective, priority')
            .eq('user_id', user.id)
            .eq('is_active', true)
            .order('priority', { ascending: false });

        // Build context strings
        const themesStr = context.themes.length > 0
            ? context.themes.map((t: any) => `${t.theme_name} (tom: ${t.communication_tone || 'profissional'})`).join(', ')
            : 'Tecnologia, Inovação, Negócios';

        const objectivesStr = context.objectives.length > 0
            ? context.objectives.join(', ')
            : 'Engajar audiência, Compartilhar conhecimento, Construir autoridade';

        // Generate post using OpenAI
        const systemPrompt = `Você é um especialista em criação de conteúdo para LinkedIn. 
Sua tarefa é transformar uma notícia em um post engajador para LinkedIn.

CONTEXTO DO USUÁRIO:
- Temas de interesse: ${themesStr}
- Objetivos: ${objectivesStr}

REGRAS:
1. NÃO copie a notícia - use-a como inspiração para criar conteúdo original
2. Conecte a notícia com a experiência/perspectiva do usuário
3. Mantenha o tom ${context.themes[0]?.communication_tone || 'profissional mas acessível'}
4. Crie um hook forte nas primeiras 2 linhas
5. Inclua uma reflexão ou insight pessoal
6. Termine com CTA que incentive discussão
7. Use 3-5 hashtags relevantes
8. Máximo 1500 caracteres
9. Mencione a fonte da notícia de forma sutil

Responda APENAS em JSON válido:
{
  "headline": "Título impactante (opcional, curto)",
  "hook": "Primeiras linhas que capturam atenção",
  "body": "Corpo do post com insight e análise",
  "cta": "Call-to-action final",
  "hashtags": ["hashtag1", "hashtag2", "hashtag3"],
  "tone": "Tom do post"
}`;

        const userPrompt = `Transforme esta notícia em um post LinkedIn envolvente:

NOTÍCIA:
Título: ${article.title}
Descrição: ${article.description || 'N/A'}
Fonte: ${article.feedName}
Link: ${article.link}

Crie um post que:
1. Conecte a notícia com os temas do usuário
2. Adicione perspectiva/valor único
3. Engaje a audiência para atingir os objetivos`;

        const response = await fetch(OPENAI_COMPLETIONS_URL, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${OPENAI_API_KEY}`,
            },
            body: JSON.stringify({
                model: 'gpt-4o-mini',
                temperature: 0.7,
                max_tokens: 1500,
                messages: [
                    { role: 'system', content: systemPrompt },
                    { role: 'user', content: userPrompt },
                ],
            }),
        });

        if (!response.ok) {
            const errorText = await response.text();
            console.error('[RSS Generate Post] OpenAI error:', errorText);
            return NextResponse.json(
                { error: 'Falha ao gerar post' },
                { status: 500 }
            );
        }

        const completion = await response.json();
        const rawContent = completion?.choices?.[0]?.message?.content;

        if (!rawContent) {
            return NextResponse.json(
                { error: 'OpenAI não retornou conteúdo' },
                { status: 500 }
            );
        }

        // Parse JSON response
        let generatedPost: GeneratedPost;
        try {
            // Clean the response (remove markdown if present)
            const cleanContent = rawContent
                .replace(/```json\s*/g, '')
                .replace(/```\s*/g, '')
                .trim();
            generatedPost = JSON.parse(cleanContent);
        } catch (parseError) {
            console.error('[RSS Generate Post] JSON parse error:', parseError);
            console.error('[RSS Generate Post] Raw content:', rawContent);
            return NextResponse.json(
                { error: 'Falha ao processar resposta da IA' },
                { status: 500 }
            );
        }

        // Compose full caption
        const parts = [
            generatedPost.headline,
            generatedPost.hook,
            generatedPost.body,
            generatedPost.cta,
        ].filter(Boolean);

        const hashtags = Array.isArray(generatedPost.hashtags)
            ? generatedPost.hashtags.map(tag => tag.startsWith('#') ? tag : `#${tag}`).join(' ')
            : '';

        const fullCaption = [...parts, hashtags].filter(Boolean).join('\n\n');

        return NextResponse.json({
            success: true,
            post: {
                ...generatedPost,
                caption: fullCaption,
            },
            source: {
                title: article.title,
                link: article.link,
                feedName: article.feedName,
            },
        });

    } catch (error) {
        console.error('[RSS Generate Post] Error:', error);
        return NextResponse.json(
            { error: 'Failed to generate post' },
            { status: 500 }
        );
    }
}
