import { NextRequest, NextResponse } from 'next/server';
import { createClient } from '@/utils/supabase/server';
import { 
  createUserAgent, 
  analyzePostsWithAgent,
  AgentAnalysisResult 
} from '@/lib/ai/OpenAIAgentService';

export const dynamic = 'force-dynamic';
export const maxDuration = 300; // 5 minutes max for Vercel

export async function POST(req: NextRequest) {
  console.log('\n========================================');
  console.log('[ONBOARDING ANALYZE] Starting');
  console.log('========================================');

  try {
    const supabase = await createClient();
    const { data: { user }, error: authError } = await supabase.auth.getUser();

    if (authError || !user) {
      console.log('[ONBOARDING] ❌ Unauthorized');
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    }

    console.log('[ONBOARDING] User ID:', user.id);
    const userName = user.user_metadata?.name || user.email?.split('@')[0];

    const body = await req.json();
    const { profileUrl, createAgent: shouldCreateAgent = true } = body;

    if (!profileUrl) {
      return NextResponse.json({ error: 'Profile URL is required' }, { status: 400 });
    }

    console.log('[ONBOARDING] Profile URL:', profileUrl);
    console.log('[ONBOARDING] Create Agent:', shouldCreateAgent);

    // Check if already analyzed
    const { data: existingAgent } = await supabase
      .from('user_agents')
      .select('has_been_analyzed')
      .eq('user_id', user.id)
      .maybeSingle();

    if (existingAgent?.has_been_analyzed) {
      console.log('[ONBOARDING] Already analyzed, skipping');
      return NextResponse.json({ success: true, message: 'Already analyzed' });
    }

    // ============================================
    // STEP 1: Start Apify Scraping
    // ============================================
    console.log('\n[STEP 1] Starting Apify scraping...');

    const apifyToken = process.env.APIFY_API_TOKEN || process.env.APIFY_TOKEN;
    if (!apifyToken) {
      console.log('[STEP 1] ❌ APIFY_TOKEN not configured');
      return NextResponse.json({ error: 'Apify token not configured' }, { status: 500 });
    }

    const actorId = 'LQQIXN9Othf8f7R5n';
    const apifyInput = {
      username: profileUrl,
      limit: 100,
      page_number: 1,
    };

    console.log('[STEP 1] Actor ID:', actorId);
    console.log('[STEP 1] Input:', JSON.stringify(apifyInput, null, 2));

    // Start actor run
    const startUrl = `https://api.apify.com/v2/acts/${actorId}/runs?token=${apifyToken}`;
    console.log('[STEP 1] Starting actor...');

    const startResponse = await fetch(startUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(apifyInput),
    });

    console.log('[STEP 1] Start response status:', startResponse.status);
    const startData = await startResponse.json();

    if (!startResponse.ok) {
      console.log('[STEP 1] ❌ Failed to start Apify:', startData);
      return NextResponse.json({ 
        error: `Failed to start scraping: ${startData.error?.message || 'Unknown error'}` 
      }, { status: 500 });
    }

    const runId = startData.data?.id;
    console.log('[STEP 1] ✅ Run started! ID:', runId);

    // ============================================
    // STEP 2: Poll for completion
    // ============================================
    console.log('\n[STEP 2] Polling for completion...');

    let attempts = 0;
    const maxAttempts = 60; // 5 minutes max
    let runStatus = 'RUNNING';
    let datasetId: string | null = null;

    while (attempts < maxAttempts && (runStatus === 'RUNNING' || runStatus === 'READY')) {
      await new Promise(resolve => setTimeout(resolve, 5000));
      attempts++;

      const statusUrl = `https://api.apify.com/v2/actor-runs/${runId}?token=${apifyToken}`;
      
      try {
        const statusResponse = await fetch(statusUrl);
        const statusData = await statusResponse.json();
        
        runStatus = statusData.data?.status || 'UNKNOWN';
        datasetId = statusData.data?.defaultDatasetId;
        
        console.log(`[STEP 2] Poll ${attempts}/${maxAttempts}: Status=${runStatus}, Dataset=${datasetId || 'pending'}`);
      } catch (e: any) {
        console.log(`[STEP 2] Poll error:`, e.message);
      }
    }

    if (runStatus !== 'SUCCEEDED') {
      console.log('[STEP 2] ❌ Run did not succeed. Status:', runStatus);
      return NextResponse.json({ 
        error: `Scraping failed with status: ${runStatus}` 
      }, { status: 500 });
    }

    // ============================================
    // STEP 3: Fetch results
    // ============================================
    console.log('\n[STEP 3] Fetching results...');

    const datasetUrl = `https://api.apify.com/v2/datasets/${datasetId}/items?token=${apifyToken}`;

    const datasetResponse = await fetch(datasetUrl);
    const posts = await datasetResponse.json();

    console.log('[STEP 3] Posts fetched:', Array.isArray(posts) ? posts.length : 'not an array');

    if (!Array.isArray(posts)) {
      console.log('[STEP 3] ❌ Invalid posts data');
      return NextResponse.json({ error: 'Invalid posts data from scraper' }, { status: 500 });
    }

    // Filter to last 12 months
    const twelveMonthsAgo = new Date();
    twelveMonthsAgo.setMonth(twelveMonthsAgo.getMonth() - 12);

    const recentPosts = posts.filter((post: any) => {
      if (!post.postedAtTimestamp) return true;
      return post.postedAtTimestamp >= twelveMonthsAgo.getTime();
    });

    console.log('[STEP 3] Recent posts (12 months):', recentPosts.length);

    // Store posts in database
    const vanityName = profileUrl.split('/in/')[1]?.replace(/\/$/, '') || null;

    const { error: storeError } = await supabase
      .from('user_agents')
      .upsert({
        user_id: user.id,
        linkedin_profile_url: profileUrl,
        linkedin_vanity_name: vanityName,
        scraped_posts_data: recentPosts,
        scraped_posts_count: recentPosts.length,
        last_scraped_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      }, { onConflict: 'user_id' });

    if (storeError) {
      console.log('[STEP 3] ❌ Error storing posts:', storeError.message);
    } else {
      console.log('[STEP 3] ✅ Posts stored in database');
    }

    // ============================================
    // STEP 4: Create AI Agent with Vector Store
    // ============================================
    let agentResult = null;
    let agentAnalysis: AgentAnalysisResult | null = null;
    
    if (shouldCreateAgent && process.env.OPENAI_API_KEY) {
      console.log('\n[STEP 4] Creating AI Agent...');
      
      try {
        // Create the agent with vector store
        agentResult = await createUserAgent(user.id, userName, recentPosts);
        
        // Save agent info to database
        await supabase.from('user_agents').upsert({
          user_id: user.id,
          openai_assistant_id: agentResult.assistantId,
          openai_vector_store_id: agentResult.vectorStoreId,
          openai_thread_id: agentResult.threadId,
          assistant_created_at: new Date().toISOString(),
          vector_store_created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        }, { onConflict: 'user_id' });
        
        console.log('[STEP 4] ✅ Agent created and saved');
        
        // Use agent to analyze posts
        if (recentPosts.length > 0) {
          console.log('[STEP 4] Analyzing posts with AI agent...');
          agentAnalysis = await analyzePostsWithAgent(
            agentResult.assistantId, 
            agentResult.threadId
          );
          console.log('[STEP 4] ✅ AI analysis complete');
        }
      } catch (agentError: any) {
        console.log('[STEP 4] ⚠️ Agent creation failed:', agentError.message);
        console.log('[STEP 4] Falling back to basic theme extraction');
      }
    }

    // ============================================
    // STEP 5: Extract themes (from AI or fallback)
    // ============================================
    console.log('\n[STEP 5] Processing themes...');

    let themes: any[] = [];

    if (agentAnalysis?.themes?.length) {
      // Use AI-generated themes
      themes = agentAnalysis.themes.map(t => ({
        name: t.name,
        description: t.description,
        relevance: t.relevance,
        examples: t.examples,
      }));
      console.log('[STEP 5] Using AI-generated themes:', themes.length);
    } else if (recentPosts.length === 0) {
      console.log('[STEP 5] No posts to analyze, using defaults');
      themes = getDefaultThemes();
    } else {
      // Fallback to word frequency
      themes = extractThemesFromPosts(recentPosts);
      console.log('[STEP 5] Using word-frequency themes');
    }

    console.log('[STEP 5] Themes to save:', themes.length);
    themes.forEach((t: any, i: number) => {
      console.log(`  ${i + 1}. ${t.name}`);
    });

    // ============================================
    // STEP 6: Save themes to database
    // ============================================
    console.log('\n[STEP 6] Saving themes to database...');

    let insertedCount = 0;
    for (const theme of themes) {
      const { error: themeError } = await supabase
        .from('user_themes')
        .insert({
          user_id: user.id,
          theme_name: theme.name,
          importance_weight: Math.round(theme.relevance * 100),
          communication_tone: 'Profissional',
          description: theme.description || `Tema identificado automaticamente`,
          is_suggested: true,
        });

      if (themeError) {
        // Might be duplicate, try upsert approach
        if (themeError.code === '23505') {
          console.log(`[STEP 6] Theme "${theme.name}" already exists, skipping`);
        } else {
          console.log(`[STEP 6] Error inserting "${theme.name}":`, themeError.message);
        }
      } else {
        console.log(`[STEP 6] ✅ Inserted: ${theme.name}`);
        insertedCount++;
      }
    }

    // Mark as analyzed and complete onboarding
    const { error: updateError } = await supabase
      .from('user_agents')
      .upsert({
        user_id: user.id,
        has_been_analyzed: true,
        onboarding_completed: true,
        onboarding_step: 'complete',
        themes_suggested_at: new Date().toISOString(),
        analysis_summary: {
          posts_analyzed: recentPosts.length,
          themes_suggested: themes.length,
          analyzed_at: new Date().toISOString(),
          ai_agent_created: !!agentResult,
        },
        updated_at: new Date().toISOString(),
      }, { onConflict: 'user_id' });

    if (updateError) {
      console.log('[STEP 6] Error updating user_agents:', updateError.message);
    }

    console.log('\n========================================');
    console.log('[ONBOARDING] ✅ COMPLETE!');
    console.log('========================================');
    console.log('[ONBOARDING] Posts analyzed:', recentPosts.length);
    console.log('[ONBOARDING] Themes inserted:', insertedCount);

    return NextResponse.json({
      success: true,
      posts_analyzed: recentPosts.length,
      themes_suggested: insertedCount,
    });

  } catch (error: any) {
    console.log('\n[ONBOARDING] ❌ FATAL ERROR');
    console.log('[ONBOARDING] Error:', error.message);
    console.log('[ONBOARDING] Stack:', error.stack);
    return NextResponse.json({ error: error.message }, { status: 500 });
  }
}

/**
 * Extract themes from posts using word frequency
 */
function extractThemesFromPosts(posts: any[]): any[] {
  console.log('[THEMES] Extracting from', posts.length, 'posts...');

  const wordFreq: { [key: string]: number } = {};
  const stopWords = new Set([
    'de', 'a', 'o', 'que', 'e', 'do', 'da', 'em', 'um', 'para', 'é', 'com', 
    'não', 'uma', 'os', 'no', 'se', 'na', 'por', 'mais', 'as', 'dos', 'como', 
    'mas', 'foi', 'ao', 'ele', 'das', 'tem', 'à', 'seu', 'sua', 'ou', 'ser',
    'quando', 'muito', 'há', 'nos', 'já', 'está', 'eu', 'também', 'só', 'pelo',
    'pela', 'até', 'isso', 'ela', 'entre', 'era', 'depois', 'sem', 'mesmo',
    'aos', 'ter', 'seus', 'quem', 'nas', 'me', 'esse', 'eles', 'você', 'essa',
    'num', 'nem', 'suas', 'meu', 'minha', 'têm', 'numa', 'isso', 'aqui', 'ali',
    'sobre', 'esse', 'essa', 'este', 'esta', 'isso', 'aquilo', 'cada', 'outro',
    'outra', 'outros', 'outras', 'todo', 'toda', 'todos', 'todas', 'algum',
    'alguma', 'alguns', 'algumas', 'nenhum', 'nenhuma', 'muito', 'muita',
    'muitos', 'muitas', 'pouco', 'pouca', 'poucos', 'poucas', 'tanto', 'tanta',
    'tantos', 'tantas', 'quanto', 'quanta', 'quantos', 'quantas', 'qual',
    'quais', 'cujo', 'cuja', 'cujos', 'cujas', 'onde', 'aonde', 'donde',
    'the', 'and', 'to', 'of', 'in', 'is', 'it', 'for', 'on', 'with', 'as',
    'this', 'that', 'are', 'was', 'be', 'have', 'has', 'had', 'do', 'does',
    'will', 'would', 'could', 'should', 'may', 'might', 'must', 'can',
    'been', 'being', 'from', 'they', 'their', 'them', 'these', 'those',
    'which', 'who', 'whom', 'whose', 'what', 'when', 'where', 'why', 'how',
    'all', 'each', 'every', 'both', 'few', 'more', 'most', 'other', 'some',
    'such', 'than', 'too', 'very', 'just', 'only', 'own', 'same', 'so',
    'then', 'now', 'here', 'there', 'before', 'after', 'above', 'below',
    'between', 'into', 'through', 'during', 'under', 'again', 'further',
    'once', 'always', 'never', 'sometimes', 'often', 'still', 'also',
    'back', 'well', 'way', 'even', 'new', 'want', 'because', 'any', 'give',
    'day', 'most', 'us', 'linkedin', 'post', 'share', 'like', 'comment',
  ]);

  posts.forEach((post: any) => {
    const text = (post.text || '').toLowerCase();
    const words = text.split(/\s+/);

    words.forEach((word: string) => {
      const clean = word.replace(/[^a-záàâãéèêíïóôõöúçA-Z]/gi, '');
      if (clean.length > 4 && !stopWords.has(clean)) {
        wordFreq[clean] = (wordFreq[clean] || 0) + 1;
      }
    });
  });

  const sorted = Object.entries(wordFreq)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5);

  console.log('[THEMES] Top words:', sorted);

  const themes = sorted.map(([word, count], index) => ({
    name: word.charAt(0).toUpperCase() + word.slice(1),
    description: `Tema identificado em ${count} posts`,
    relevance: Math.max(0.5, 1 - index * 0.1),
    posts_count: count,
  }));

  // If not enough themes, add defaults
  if (themes.length < 3) {
    const defaults = getDefaultThemes();
    for (const def of defaults) {
      if (themes.length >= 5) break;
      if (!themes.some(t => t.name.toLowerCase() === def.name.toLowerCase())) {
        themes.push(def);
      }
    }
  }

  return themes;
}

/**
 * Default themes if no posts found
 */
function getDefaultThemes(): any[] {
  return [
    { name: 'Liderança', description: 'Gestão e liderança de equipes', relevance: 0.8 },
    { name: 'Inovação', description: 'Tendências e novidades do mercado', relevance: 0.7 },
    { name: 'Carreira', description: 'Desenvolvimento profissional', relevance: 0.7 },
    { name: 'Tecnologia', description: 'Transformação digital e tech', relevance: 0.6 },
    { name: 'Produtividade', description: 'Eficiência e gestão de tempo', relevance: 0.5 },
  ];
}
