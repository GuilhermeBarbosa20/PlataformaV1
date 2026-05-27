import { ThemeInput } from './postGeneration';

export interface UserContentContext {
  themes: ThemeInput;
  objectives: string[];
}

export async function fetchUserContentContext(
  supabase: any,
  userId: string,
): Promise<UserContentContext> {
  const { data: themes } = await supabase
    .from('user_themes')
    .select('theme_name, importance_weight, communication_tone')
    .eq('user_id', userId)
    .order('importance_weight', { ascending: false });

  const { data: objectives } = await supabase
    .from('user_objectives')
    .select('objective, priority')
    .eq('user_id', userId)
    .eq('is_active', true)
    .order('priority', { ascending: false });

  return {
    themes: themes ?? [],
    objectives: (objectives ?? []).map((item: { objective: string; priority: number }) => item.objective),
  };
}

export function appendRevisionHistory(
  post: any,
  newEntry: any,
): any[] {
  const history = Array.isArray(post?.ai_revision_history)
    ? [...post.ai_revision_history]
    : [];

  if (post?.ai_content && Object.keys(post.ai_content || {}).length > 0) {
    history.push({
      saved_at: new Date().toISOString(),
      content: post.ai_content,
    });
  }

  if (newEntry) {
    history.push(newEntry);
  }

  return history;
}
