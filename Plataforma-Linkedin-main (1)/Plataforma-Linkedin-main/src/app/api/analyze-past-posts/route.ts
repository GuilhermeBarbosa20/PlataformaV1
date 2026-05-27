import { NextRequest, NextResponse } from 'next/server';
import { createClient } from '@/utils/supabase/server';
import { AIService } from '@/lib/ai/AIService';

export const dynamic = 'force-dynamic';

// Types for scraped posts
interface ScrapedPost {
  text?: string;
  postUrl?: string;
  postedAt?: string;
  postedAtTimestamp?: number;
  reactionCount?: number;
  commentsCount?: number;
  repostsCount?: number;
  mediaType?: string;
  images?: string[];
}

// Types for AI analysis result
interface ThemeSuggestion {
  name: string;
  relevance: number;
  posts_count: number;
  example_posts: string[];
  recommended_tone: string;
}

interface PostAnalysisResult {
  themes: ThemeSuggestion[];
  summary: string;
  writing_style: {
    avg_length: string;
    tone: string;
    common_patterns: string[];
    hashtag_usage: string;
    emoji_usage: string;
  };
  best_performing_topics: string[];
  posting_frequency: string;
  recommendations: string[];
}

/**
 * POST /api/analyze-past-posts
 * Analyzes user's past posts (last 12 months) using AI and suggests themes
 * This should be called on first login to auto-populate suggested themes
 */
export async function POST(req: NextRequest) {
  console.log('\n========================================');
  console.log('[ANALYZE POSTS] POST request received');
  console.log('========================================');

  try {
    const supabase = await createClient();
    const { data: { user }, error: authError } = await supabase.auth.getUser();

    console.log('[ANALYZE POSTS] Auth check - User ID:', user?.id);
    console.log('[ANALYZE POSTS] Auth check - Error:', authError?.message || 'none');

    if (authError || !user) {
      console.log('[ANALYZE POSTS] ❌ Unauthorized');
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    }

    // Check if user has already been analyzed
    const { data: userAgent, error: agentError } = await supabase
      .from('user_agents')
      .select('has_been_analyzed, scraped_posts_data, themes_suggested_at, analysis_summary, scraped_posts_count')
      .eq('user_id', user.id)
      .single();

    console.log('[ANALYZE POSTS] User agent fetch error:', agentError?.message || 'none');
    console.log('[ANALYZE POSTS] Has been analyzed:', userAgent?.has_been_analyzed);
    console.log('[ANALYZE POSTS] Scraped posts count in DB:', userAgent?.scraped_posts_count);
    console.log('[ANALYZE POSTS] Scraped posts data exists:', !!userAgent?.scraped_posts_data);
    console.log('[ANALYZE POSTS] Scraped posts data type:', typeof userAgent?.scraped_posts_data);

    if (agentError && agentError.code !== 'PGRST116') {
      console.log('[ANALYZE POSTS] ⚠️ Error checking user agent:', agentError);
    }

    // If already analyzed and has themes, return early
    if (userAgent?.has_been_analyzed) {
      console.log('[ANALYZE POSTS] ⚠️ Already analyzed, returning early');
      return NextResponse.json({
        success: true,
        already_analyzed: true,
        message: '⚠️ Análise já foi realizada anteriormente',
        analysis_summary: userAgent.analysis_summary,
      });
    }

    // Get scraped posts from user_agents
    let scrapedPosts: ScrapedPost[] = [];
    
    if (Array.isArray(userAgent?.scraped_posts_data)) {
      scrapedPosts = userAgent.scraped_posts_data;
    } else if (userAgent?.scraped_posts_data && typeof userAgent.scraped_posts_data === 'object') {
      // Maybe it's wrapped in an object
      console.log('[ANALYZE POSTS] Posts data keys:', Object.keys(userAgent.scraped_posts_data));
    }

    console.log('[ANALYZE POSTS] Scraped posts array length:', scrapedPosts.length);

    if (!scrapedPosts || scrapedPosts.length === 0) {
      console.log('[ANALYZE POSTS] ❌ No scraped posts found');
      console.log('[ANALYZE POSTS] Raw scraped_posts_data:', JSON.stringify(userAgent?.scraped_posts_data)?.substring(0, 500));
      return NextResponse.json(
        { 
          error: 'No scraped posts found. Please run the scraper first.',
          debug: {
            has_user_agent: !!userAgent,
            scraped_posts_data_type: typeof userAgent?.scraped_posts_data,
            scraped_posts_count: userAgent?.scraped_posts_count,
          }
        },
        { status: 400 }
      );
    }

    console.log('[ANALYZE POSTS] First post sample:', JSON.stringify(scrapedPosts[0], null, 2));

    // Initialize AI service
    console.log('\n[ANALYZE POSTS] --- Initializing AI Service ---');
    console.log('[ANALYZE POSTS] GROQ_API_KEY exists:', !!process.env.GROQ_API_KEY);
    console.log('[ANALYZE POSTS] NANO_BANANA_URL exists:', !!process.env.NANO_BANANA_URL);
    console.log('[ANALYZE POSTS] AI_PROVIDER:', process.env.AI_PROVIDER || 'auto');
    
    const aiService = AIService.fromEnv();
    console.log('[ANALYZE POSTS] AI Service initialized');

    // Analyze posts with AI
    console.log('\n[ANALYZE POSTS] --- Calling AI Analysis ---');
    const analysisResult = await analyzePostsWithAI(aiService, scrapedPosts);
    console.log('[ANALYZE POSTS] Analysis result received');
    console.log('[ANALYZE POSTS] Themes found:', analysisResult.themes?.length || 0);
    console.log('[ANALYZE POSTS] Themes:', JSON.stringify(analysisResult.themes, null, 2));

    // Check if user already has themes
    console.log('\n[ANALYZE POSTS] --- Checking Existing Themes ---');
    const { data: existingThemes, error: checkError } = await supabase
      .from('user_themes')
      .select('id')
      .eq('user_id', user.id)
      .limit(1);

    console.log('[ANALYZE POSTS] Check themes error:', checkError?.message || 'none');
    console.log('[ANALYZE POSTS] Existing themes count:', existingThemes?.length || 0);

    if (checkError) {
      console.log('[ANALYZE POSTS] ❌ Failed to check existing themes');
      return NextResponse.json(
        { error: 'Failed to check existing themes' },
        { status: 500 }
      );
    }

    // If user has no themes, auto-insert suggested ones
    let insertedThemes: any[] = [];
    if (existingThemes && existingThemes.length === 0 && analysisResult.themes.length > 0) {
      console.log('\n[ANALYZE POSTS] --- Inserting Themes ---');
      const themesToInsert = analysisResult.themes.slice(0, 5).map((theme) => ({
        user_id: user.id,
        theme_name: theme.name,
        importance_weight: Math.round(theme.relevance * 100),
        communication_tone: theme.recommended_tone || 'Simples',
        is_suggested: true,
      }));

      console.log('[ANALYZE POSTS] Themes to insert:', JSON.stringify(themesToInsert, null, 2));

      const { data: inserted, error: insertError } = await supabase
        .from('user_themes')
        .insert(themesToInsert)
        .select();

      console.log('[ANALYZE POSTS] Insert error:', insertError?.message || 'none');
      console.log('[ANALYZE POSTS] Inserted themes:', inserted?.length || 0);

      if (insertError) {
        console.log('[ANALYZE POSTS] ❌ Failed to insert themes:', insertError);
        return NextResponse.json(
          { error: 'Failed to save suggested themes', details: insertError.message },
          { status: 500 }
        );
      }

      insertedThemes = inserted || [];
      console.log('[ANALYZE POSTS] ✅ Themes inserted successfully!');
    } else {
      console.log('[ANALYZE POSTS] ⚠️ Skipping theme insertion - existing themes or no AI themes');
    }

    // Update user_agents with analysis results
    console.log('\n[ANALYZE POSTS] --- Updating User Agent ---');
    const upsertData = {
      user_id: user.id,
      has_been_analyzed: true,
      themes_suggested_at: new Date().toISOString(),
      analysis_summary: analysisResult,
    };
    console.log('[ANALYZE POSTS] Upsert data:', JSON.stringify({ ...upsertData, analysis_summary: '[ANALYSIS DATA]' }));

    const { error: updateError } = await supabase
      .from('user_agents')
      .upsert(upsertData, { onConflict: 'user_id' });

    if (updateError) {
      console.log('[ANALYZE POSTS] ❌ Error updating user agent:', updateError);
    } else {
      console.log('[ANALYZE POSTS] ✅ User agent updated with has_been_analyzed = true');
    }

    const response = {
      success: true,
      suggested_themes: analysisResult.themes,
      inserted_count: insertedThemes.length,
      analysis: {
        summary: analysisResult.summary,
        writing_style: analysisResult.writing_style,
        best_topics: analysisResult.best_performing_topics,
        posting_frequency: analysisResult.posting_frequency,
        recommendations: analysisResult.recommendations,
      },
      posts_analyzed: scrapedPosts.length,
      message: insertedThemes.length > 0 
        ? `✅ ${insertedThemes.length} temas sugeridos adicionados com base em ${scrapedPosts.length} posts analisados!`
        : '⚠️ Você já tem temas configurados',
    };

    console.log('\n========================================');
    console.log('[ANALYZE POSTS] ✅ COMPLETE');
    console.log('[ANALYZE POSTS] Response:', JSON.stringify(response, null, 2));
    console.log('========================================\n');

    return NextResponse.json(response);

  } catch (error: any) {
    console.log('[ANALYZE POSTS] ❌ FATAL ERROR:', error);
    console.log('[ANALYZE POSTS] Error stack:', error.stack);
    return NextResponse.json(
      { error: error.message || 'Internal server error' },
      { status: 500 }
    );
  }
}

/**
 * Analyze posts with AI to extract themes and patterns
 */
async function analyzePostsWithAI(
  aiService: AIService, 
  posts: ScrapedPost[]
): Promise<PostAnalysisResult> {
  console.log('\n[AI ANALYSIS] Starting AI analysis');
  console.log('[AI ANALYSIS] Total posts received:', posts.length);

  // Prepare posts summary for AI (limit text to avoid token overflow)
  const postsForAnalysis = posts.slice(0, 50).map((post, index) => ({
    index: index + 1,
    text: (post.text || '').slice(0, 500),
    reactions: post.reactionCount || 0,
    comments: post.commentsCount || 0,
    reposts: post.repostsCount || 0,
    date: post.postedAt || '',
    hasMedia: post.mediaType || 'none',
  }));

  console.log('[AI ANALYSIS] Posts prepared for analysis:', postsForAnalysis.length);
  console.log('[AI ANALYSIS] Sample post for AI:', JSON.stringify(postsForAnalysis[0], null, 2));

  const systemPrompt = `
Você é um analista de conteúdo especializado em LinkedIn.
Analise os posts do usuário e retorne um JSON ESTRITO com a seguinte estrutura:

{
  "themes": [
    {
      "name": "string - nome do tema em português",
      "relevance": "number 0-1 - relevância baseada em frequência e engajamento",
      "posts_count": "number - quantos posts sobre este tema",
      "example_posts": ["string - resumo de 1-2 posts exemplo"],
      "recommended_tone": "string - Simples | Profissional | Inspirador | Técnico | Casual"
    }
  ],
  "summary": "string - resumo geral do perfil de conteúdo do usuário",
  "writing_style": {
    "avg_length": "string - curto/médio/longo",
    "tone": "string - tom predominante",
    "common_patterns": ["string - padrões de escrita identificados"],
    "hashtag_usage": "string - baixo/médio/alto",
    "emoji_usage": "string - baixo/médio/alto"
  },
  "best_performing_topics": ["string - tópicos com mais engajamento"],
  "posting_frequency": "string - frequência de postagem estimada",
  "recommendations": ["string - recomendações para melhorar conteúdo"]
}

REGRAS:
- Identifique de 3 a 6 temas principais
- Ordene temas por relevância (maior primeiro)
- Use português do Brasil
- Seja específico nos nomes dos temas (não use termos genéricos)
- Baseie relevância em frequência + engajamento médio
`;

  const userPrompt = {
    role: 'user' as const,
    content: `Analise os seguintes ${postsForAnalysis.length} posts do LinkedIn e retorne apenas o JSON:\n\n${JSON.stringify(postsForAnalysis, null, 2)}`,
  };

  console.log('[AI ANALYSIS] Calling AI model...');
  console.log('[AI ANALYSIS] User prompt length:', userPrompt.content.length, 'chars');

  try {
    // @ts-ignore - using internal method
    const raw = await aiService['callModel'](systemPrompt, [userPrompt]);
    
    console.log('[AI ANALYSIS] Raw AI response length:', raw?.length || 0, 'chars');
    console.log('[AI ANALYSIS] Raw AI response (first 500 chars):', raw?.substring(0, 500));
    
    // Parse and validate response
    const cleaned = raw
      .trim()
      .replace(/^```(json)?/i, '')
      .replace(/```$/, '')
      .trim();
    
    console.log('[AI ANALYSIS] Cleaned response length:', cleaned.length, 'chars');
    
    const result = JSON.parse(cleaned) as PostAnalysisResult;
    console.log('[AI ANALYSIS] ✅ JSON parsed successfully');
    console.log('[AI ANALYSIS] Themes in result:', result.themes?.length || 0);
    
    // Ensure required fields exist
    if (!result.themes || !Array.isArray(result.themes)) {
      console.log('[AI ANALYSIS] ⚠️ No themes array, creating empty');
      result.themes = [];
    }
    if (!result.summary) {
      result.summary = 'Análise realizada com sucesso';
    }
    if (!result.writing_style) {
      result.writing_style = {
        avg_length: 'médio',
        tone: 'profissional',
        common_patterns: [],
        hashtag_usage: 'médio',
        emoji_usage: 'baixo',
      };
    }
    if (!result.best_performing_topics) {
      result.best_performing_topics = result.themes.slice(0, 3).map(t => t.name);
    }
    if (!result.posting_frequency) {
      result.posting_frequency = 'variável';
    }
    if (!result.recommendations) {
      result.recommendations = [];
    }

    return result;
  } catch (error: any) {
    console.log('[AI ANALYSIS] ❌ AI analysis error:', error.message);
    console.log('[AI ANALYSIS] Error stack:', error.stack);
    console.log('[AI ANALYSIS] Falling back to word frequency analysis');
    
    // Fallback: Generate basic themes from post content
    return generateFallbackAnalysis(posts);
  }
}

/**
 * Fallback analysis if AI fails
 */
function generateFallbackAnalysis(posts: ScrapedPost[]): PostAnalysisResult {
  console.log('[FALLBACK ANALYSIS] Starting fallback word frequency analysis');
  console.log('[FALLBACK ANALYSIS] Posts count:', posts.length);

  // Simple word frequency analysis
  const wordCounts: Record<string, number> = {};
  const commonWords = new Set(['de', 'que', 'e', 'a', 'o', 'da', 'do', 'em', 'um', 'uma', 'para', 'com', 'não', 'é', 'os', 'as', 'se', 'na', 'no', 'por', 'mais', 'como', 'mas', 'ao', 'ou']);

  posts.forEach(post => {
    const words = (post.text || '')
      .toLowerCase()
      .replace(/[^\w\sáàâãéèêíïóôõöúüç]/g, '')
      .split(/\s+/)
      .filter(w => w.length > 3 && !commonWords.has(w));
    
    words.forEach(word => {
      wordCounts[word] = (wordCounts[word] || 0) + 1;
    });
  });

  console.log('[FALLBACK ANALYSIS] Unique words found:', Object.keys(wordCounts).length);

  // Get top themes from word frequency
  const topWords = Object.entries(wordCounts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5);

  console.log('[FALLBACK ANALYSIS] Top words:', topWords);

  const themes: ThemeSuggestion[] = topWords.map(([word, count], index) => ({
    name: word.charAt(0).toUpperCase() + word.slice(1),
    relevance: Math.max(0.3, 1 - (index * 0.15)),
    posts_count: count,
    example_posts: [],
    recommended_tone: 'Profissional',
  }));

  // Add default themes if none found
  if (themes.length === 0) {
    console.log('[FALLBACK ANALYSIS] ⚠️ No themes from word frequency, using defaults');
    themes.push(
      { name: 'Desenvolvimento Profissional', relevance: 0.8, posts_count: 0, example_posts: [], recommended_tone: 'Profissional' },
      { name: 'Tecnologia', relevance: 0.7, posts_count: 0, example_posts: [], recommended_tone: 'Técnico' },
      { name: 'Carreira', relevance: 0.6, posts_count: 0, example_posts: [], recommended_tone: 'Inspirador' },
    );
  }

  console.log('[FALLBACK ANALYSIS] Final themes:', themes.length);
  console.log('[FALLBACK ANALYSIS] Themes:', JSON.stringify(themes, null, 2));

  return {
    themes,
    summary: `Análise baseada em ${posts.length} posts. Recomendamos revisar os temas sugeridos.`,
    writing_style: {
      avg_length: 'médio',
      tone: 'profissional',
      common_patterns: [],
      hashtag_usage: 'médio',
      emoji_usage: 'baixo',
    },
    best_performing_topics: themes.slice(0, 3).map(t => t.name),
    posting_frequency: `Aproximadamente ${Math.round(posts.length / 12)} posts por mês`,
    recommendations: [
      'Mantenha consistência nos temas identificados',
      'Experimente variar o formato dos posts',
      'Engaje com comentários para aumentar alcance',
    ],
  };
}

/**
 * GET /api/analyze-past-posts
 * Returns the analysis status and results for the current user
 */
export async function GET(req: NextRequest) {
  try {
    const supabase = await createClient();
    const { data: { user }, error: authError } = await supabase.auth.getUser();

    if (authError || !user) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    }

    const { data: userAgent, error } = await supabase
      .from('user_agents')
      .select('has_been_analyzed, themes_suggested_at, analysis_summary, scraped_posts_count')
      .eq('user_id', user.id)
      .single();

    if (error && error.code !== 'PGRST116') {
      return NextResponse.json({ error: 'Failed to fetch analysis status' }, { status: 500 });
    }

    return NextResponse.json({
      has_been_analyzed: userAgent?.has_been_analyzed || false,
      themes_suggested_at: userAgent?.themes_suggested_at,
      posts_analyzed: userAgent?.scraped_posts_count || 0,
      analysis: userAgent?.analysis_summary || null,
    });

  } catch (error: any) {
    console.error('Error getting analysis status:', error);
    return NextResponse.json(
      { error: error.message || 'Internal server error' },
      { status: 500 }
    );
  }
}
