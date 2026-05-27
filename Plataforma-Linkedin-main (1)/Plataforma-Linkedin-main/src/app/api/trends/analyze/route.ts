import { NextRequest, NextResponse } from 'next/server';
import { createClient } from '@/utils/supabase/server';
import { getUserPrompt } from '@/lib/prompts/getPrompt';

export const dynamic = 'force-dynamic';

const OPENAI_API_KEY = process.env.OPENAI_API_KEY;

/**
 * POST /api/trends/analyze
 * Analyze unanalyzed posts using AI to determine relevance
 */
export async function POST(request: NextRequest) {
    console.log('[TRENDS ANALYZE] Starting AI analysis of posts');

    try {
        const supabase = await createClient();
        const { data: { user }, error: authError } = await supabase.auth.getUser();

        if (authError || !user) {
            return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
        }

        if (!OPENAI_API_KEY) {
            return NextResponse.json({ error: 'OpenAI não configurado' }, { status: 500 });
        }

        // Get user's themes from user_themes table
        const { data: userThemes } = await supabase
            .from('user_themes')
            .select('theme_name, importance_weight, communication_tone')
            .eq('user_id', user.id)
            .order('importance_weight', { ascending: false });

        // Get user's objectives from user_objectives table
        const { data: userObjectives } = await supabase
            .from('user_objectives')
            .select('objective, priority')
            .eq('user_id', user.id)
            .eq('is_active', true)
            .order('priority', { ascending: false });

        // Get user's persona/tone from user_agents
        const { data: userAgent } = await supabase
            .from('user_agents')
            .select('agent_persona')
            .eq('user_id', user.id)
            .single();

        const themes = userThemes?.map(t => t.theme_name) || [];
        const objectives = userObjectives?.map(o => o.objective) || [];

        if (themes.length === 0 && objectives.length === 0) {
            return NextResponse.json({
                error: 'Configure seus temas e objetivos primeiro'
            }, { status: 400 });
        }

        // Get unanalyzed posts (max 20 at a time to control costs)
        const { data: posts, error: postsError } = await supabase
            .from('monitored_posts')
            .select('*, monitored_profiles(profile_name)')
            .eq('user_id', user.id)
            .eq('is_analyzed', false)
            .order('posted_at', { ascending: false })
            .limit(20);

        if (postsError) {
            console.error('[TRENDS ANALYZE] Error fetching posts:', postsError);
            return NextResponse.json({ error: 'Failed to fetch posts' }, { status: 500 });
        }

        if (!posts || posts.length === 0) {
            return NextResponse.json({
                success: true,
                message: 'Nenhum post para analisar',
                analyzed_count: 0,
            });
        }

        console.log(`[TRENDS ANALYZE] Analyzing ${posts.length} posts`);
        console.log(`[TRENDS ANALYZE] User themes: ${themes.join(', ')}`);
        console.log(`[TRENDS ANALYZE] User objectives: ${objectives.join(', ')}`);

        // Get base prompt template (custom or default)
        const basePromptTemplate = await getUserPrompt(supabase, user.id, 'trend_analysis');

        let analyzedCount = 0;
        let relevantCount = 0;

        // Analyze each post
        for (const post of posts) {
            try {
                const postContent = post.post_content?.substring(0, 1000) || '';
                if (!postContent.trim()) {
                    // Mark empty posts as analyzed but not relevant
                    await supabase
                        .from('monitored_posts')
                        .update({
                            is_analyzed: true,
                            is_relevant: false,
                            ai_reason: 'Post sem conteúdo',
                            updated_at: new Date().toISOString(),
                        })
                        .eq('id', post.id);
                    continue;
                }

                // Replace variables in prompt
                const prompt = basePromptTemplate
                    .replace(/{{themes}}/g, themes.join(', ') || 'Não definido')
                    .replace(/{{objectives}}/g, objectives.join(', ') || 'Não definido')
                    .replace(/{{persona}}/g, userAgent?.agent_persona || 'profissional')
                    .replace(/{{author_name}}/g, post.author_name || 'Desconhecido')
                    .replace(/{{post_content}}/g, postContent);

                const response = await fetch('https://api.openai.com/v1/chat/completions', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${OPENAI_API_KEY}`,
                    },
                    body: JSON.stringify({
                        model: 'gpt-4o-mini',
                        messages: [{ role: 'user', content: prompt }],
                        max_tokens: 400,
                        temperature: 0.7,
                    }),
                });

                if (!response.ok) {
                    console.error('[TRENDS ANALYZE] OpenAI error for post:', post.id);
                    continue;
                }

                const data = await response.json();
                const content = data.choices?.[0]?.message?.content || '';

                // Parse JSON response
                let analysis = { is_relevant: false, score: 0, reason: 'Análise indisponível', suggested_comment: '' };
                try {
                    const jsonMatch = content.match(/\{[\s\S]*\}/);
                    if (jsonMatch) {
                        analysis = JSON.parse(jsonMatch[0]);
                    }
                } catch {
                    console.warn('[TRENDS ANALYZE] Failed to parse AI response');
                }

                // Update post with analysis
                const isRelevant = analysis.is_relevant && analysis.score >= 60;

                await supabase
                    .from('monitored_posts')
                    .update({
                        is_analyzed: true,
                        is_relevant: isRelevant,
                        ai_relevance_score: analysis.score || 0,
                        ai_reason: analysis.reason || '',
                        suggested_comment: isRelevant ? (analysis.suggested_comment || '') : null,
                        updated_at: new Date().toISOString(),
                    })
                    .eq('id', post.id);

                analyzedCount++;
                if (isRelevant) relevantCount++;

            } catch (err) {
                console.error('[TRENDS ANALYZE] Error analyzing post:', post.id, err);
            }
        }

        console.log(`[TRENDS ANALYZE] ✅ Analyzed: ${analyzedCount}, Relevant: ${relevantCount}`);

        return NextResponse.json({
            success: true,
            message: `${analyzedCount} posts analisados, ${relevantCount} relevantes`,
            analyzed_count: analyzedCount,
            relevant_count: relevantCount,
        });

    } catch (error: any) {
        console.error('[TRENDS ANALYZE] Error:', error);
        return NextResponse.json({ error: error.message || 'Internal server error' }, { status: 500 });
    }
}
