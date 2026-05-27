/**
 * Helper to get user's prompt (custom or default)
 */

import { DEFAULT_PROMPTS, replacePromptVariables } from './defaultPrompts';

/**
 * Get user's custom prompt or fallback to default
 */
export async function getUserPrompt(
    supabase: any,
    userId: string,
    promptType: string,
    variables?: Record<string, string>
): Promise<string> {
    // Try to get user's custom prompt
    const { data: customPrompt } = await supabase
        .from('user_custom_prompts')
        .select('prompt_content, is_active')
        .eq('user_id', userId)
        .eq('prompt_type', promptType)
        .single();

    let promptContent: string;

    if (customPrompt?.prompt_content && customPrompt.is_active) {
        console.log(`[PROMPTS] Using custom prompt for ${promptType}`);
        promptContent = customPrompt.prompt_content;
    } else {
        const defaultPrompt = DEFAULT_PROMPTS[promptType];
        if (!defaultPrompt) {
            console.warn(`[PROMPTS] No default prompt found for ${promptType}`);
            return '';
        }
        console.log(`[PROMPTS] Using default prompt for ${promptType}`);
        promptContent = defaultPrompt.content;
    }

    // Replace variables if provided
    if (variables) {
        promptContent = replacePromptVariables(promptContent, variables);
    }

    return promptContent;
}

/**
 * Check if user has prompts customization enabled
 */
export async function isPromptsCustomizationEnabled(
    supabase: any,
    userId: string
): Promise<boolean> {
    const { data } = await supabase
        .from('user_settings')
        .select('prompts_customization_enabled')
        .eq('user_id', userId)
        .single();

    return data?.prompts_customization_enabled || false;
}
