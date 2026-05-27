import { NextRequest, NextResponse } from 'next/server';
import { createClient } from '@/utils/supabase/server';
import {
  generatePostContent,
  composeCaption,
  GeneratedPostContent,
  ThemeInput,
} from '@/lib/posts/postGeneration';
import { appendRevisionHistory } from '@/lib/posts/context';
import { checkRateLimit, checkApiRateLimit } from '@/lib/rateLimit';

export const dynamic = 'force-dynamic';

const formatDate = (date: Date) => date.toISOString().split('T')[0];

const getNextSevenDays = () => {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return Array.from({ length: 7 }, (_, idx) => {
    const clone = new Date(today);
    clone.setDate(clone.getDate() + idx);
    return formatDate(clone);
  });
};

export async function GET() {
  try {
    const supabase = await createClient();
    const {
      data: { user },
      error: authError,
    } = await supabase.auth.getUser();

    if (authError || !user) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    }

    const days = getNextSevenDays();
    const startDate = days[0];
    const endDate = days[days.length - 1];

    const { data: posts, error } = await supabase
      .from('posts')
      .select('*')
      .eq('user_id', user.id)
      .gte('scheduled_for', startDate)
      .lte('scheduled_for', endDate)
      .order('scheduled_for', { ascending: true });

    if (error) {
      console.error('Error fetching posts:', error);
      return NextResponse.json({ error: 'Failed to fetch posts' }, { status: 500 });
    }

    return NextResponse.json({ posts: posts ?? [], days });
  } catch (error: any) {
    console.error('week GET error:', error);
    return NextResponse.json(
      { error: error.message || 'Internal server error' },
      { status: 500 },
    );
  }
}

export async function POST(req: NextRequest) {
  try {
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
    const rateLimit = await checkRateLimit(user.id, 'post');
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

    const days = getNextSevenDays();
    const startDate = days[0];
    const endDate = days[days.length - 1];

    // Fetch existing posts in the range
    const { data: existingPosts, error: fetchError } = await supabase
      .from('posts')
      .select('*')
      .eq('user_id', user.id)
      .gte('scheduled_for', startDate)
      .lte('scheduled_for', endDate)
      .order('scheduled_for', { ascending: true });

    if (fetchError) {
      console.error('Error fetching existing posts:', fetchError);
      return NextResponse.json({ error: 'Failed to fetch posts' }, { status: 500 });
    }

    const postsByDate = new Map<string, any>();
    (existingPosts || []).forEach((post) => {
      postsByDate.set(post.scheduled_for, post);
    });

    const missingDates = days.filter((day) => !postsByDate.has(day));

    if (missingDates.length > 0) {
      const inserts = missingDates.map((scheduled_for) => ({
        user_id: user.id,
        scheduled_for,
        caption: 'Conteúdo em preparação',
      }));

      const { error: insertError } = await supabase.from('posts').insert(inserts);
      if (insertError) {
        console.error('Error inserting missing posts:', insertError);
        return NextResponse.json(
          { error: 'Failed to prepare weekly posts' },
          { status: 500 },
        );
      }
    }

    // Re-fetch to include newly inserted posts
    const { data: postsAfterInsert, error: refetchError } = await supabase
      .from('posts')
      .select('*')
      .eq('user_id', user.id)
      .gte('scheduled_for', startDate)
      .lte('scheduled_for', endDate)
      .order('scheduled_for', { ascending: true });

    if (refetchError) {
      console.error('Error refetching posts:', refetchError);
      return NextResponse.json({ error: 'Failed to fetch posts' }, { status: 500 });
    }

    const posts = postsAfterInsert ?? [];

    // Load context (themes & objectives)
    const { data: themes } = await supabase
      .from('user_themes')
      .select('theme_name, importance_weight, communication_tone')
      .eq('user_id', user.id)
      .order('importance_weight', { ascending: false });

    const { data: objectives } = await supabase
      .from('user_objectives')
      .select('objective, priority')
      .eq('user_id', user.id)
      .eq('is_active', true)
      .order('priority', { ascending: false });

    const themeContext = themes ?? [];
    const activeObjectives = (objectives ?? []).map((item) => item.objective);

    const postsNeedingGeneration = posts.filter((post) => {
      const hasContent = post?.ai_content && Object.keys(post.ai_content || {}).length > 0;
      return !hasContent || post.needs_regeneration;
    });

    for (const post of postsNeedingGeneration) {
      await generateAndPersistPost({
        post,
        supabase,
        themes: themeContext,
        objectives: activeObjectives,
      });
    }

    const { data: finalPosts } = await supabase
      .from('posts')
      .select('*')
      .eq('user_id', user.id)
      .gte('scheduled_for', startDate)
      .lte('scheduled_for', endDate)
      .order('scheduled_for', { ascending: true });

    return NextResponse.json({
      success: true,
      posts: finalPosts ?? [],
    });
  } catch (error: any) {
    console.error('week POST error:', error);
    return NextResponse.json(
      { error: error.message || 'Internal server error' },
      { status: 500 },
    );
  }
}

interface GenerateAndPersistArgs {
  post: any;
  supabase: Awaited<ReturnType<typeof createClient>>;
  themes: ThemeInput;
  objectives: string[];
}

async function generateAndPersistPost({
  post,
  supabase,
  themes,
  objectives,
}: GenerateAndPersistArgs) {
  const aiContent = await generatePostContent({
    date: post.scheduled_for,
    themes,
    objectives,
  });

  const caption = composeCaption({ content: aiContent });
  const now = new Date().toISOString();

  const history = appendRevisionHistory(post, null);

  const updates = {
    ai_context: {
      themes: themes.map((theme) => ({
        name: theme.theme_name,
        weight: theme.importance_weight,
        tone: theme.communication_tone,
      })),
      objectives,
    },
    ai_content: aiContent as GeneratedPostContent,
    ai_revision_history: history,
    caption,
    last_generated_at: now,
    approval_status: 'aguardar',
    needs_regeneration: false,
    updated_at: now,
  };

  const { error } = await supabase
    .from('posts')
    .update(updates)
    .eq('id', post.id);

  if (error) {
    console.error('Error updating post with AI content:', error);
    throw new Error('Failed to store AI content');
  }
}
