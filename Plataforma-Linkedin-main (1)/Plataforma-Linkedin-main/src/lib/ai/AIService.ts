// Core AI service for the LinkedIn Autonomous Agent Platform.
// This class abstracts the "Nano Banana" custom endpoint and Groq fallback.
// It exposes three high-level methods used by the agent loop:
//  - analyze_performance
//  - refine_strategy
//  - draft_post

export type Provider = 'nano-banana' | 'groq';

export interface AIServiceConfig {
  provider: Provider;
  nanoBananaUrl?: string;
  nanoBananaApiKey?: string;
  groqApiKey?: string;
  model?: string;
}

export interface PerformanceSample {
  postId: string;
  scheduledFor: string; // ISO date
  caption: string;
  expectedMetrics: Record<string, any>;
  actualMetrics: Record<string, any>;
}

export interface PerformanceInsights {
  summary: string;
  perPost: Array<{
    postId: string;
    outcome: 'above_expectation' | 'on_par' | 'below_expectation';
    keyDrivers: string[];
    recommendedAdjustments: string[];
  }>;
  globalPatterns: {
    topicsWorking: string[];
    topicsToAvoid: string[];
    styleNotes: string[];
    postingTimeHints: string[];
  };
}

export interface StrategyGuidelines {
  version: number;
  goals: string[];
  contentPillars: string[];
  postingCadence: string;
  toneAndStyle: string;
  doMoreOf: string[];
  doLessOf: string[];
}

export interface DraftPostInput {
  date: string; // ISO date
  topic: string;
  guidelines: StrategyGuidelines;
  userPersonaPrompt: string;
  userStyleEmbeddingId?: string; // reference to user_style row / vector
  availableImages: Array<{
    id: string; // cloudinary public_id
    url: string;
    tags?: string[];
    caption?: string;
  }>;
}

export interface DraftPostResult {
  caption: string;
  imageId: string | null;
  reasoning: string;
  expectedMetrics: Record<string, any>;
}

export class AIService {
  private config: AIServiceConfig;

  constructor(config: AIServiceConfig) {
    this.config = config;
  }

  static fromEnv(): AIService {
    const provider =
      (process.env.AI_PROVIDER as Provider) ||
      (process.env.NANO_BANANA_URL ? 'nano-banana' : 'groq');

    return new AIService({
      provider,
      nanoBananaUrl: process.env.NANO_BANANA_URL,
      nanoBananaApiKey: process.env.NANO_BANANA_API_KEY,
      groqApiKey: process.env.GROQ_API_KEY,
      model:
        process.env.AI_MODEL ||
        (provider === 'groq' ? 'llama-3.1-70b-versatile' : 'nano-banana-latest'),
    });
  }

  async analyze_performance(
    pastData: PerformanceSample[],
  ): Promise<PerformanceInsights> {
    const systemPrompt = `
You are an analytics strategist for LinkedIn content.
You receive a list of posts with their expected vs actual performance.
Your job is to detect patterns and output a STRICT JSON object matching this TypeScript type:

{
  "summary": string;
  "perPost": {
    "postId": string;
    "outcome": "above_expectation" | "on_par" | "below_expectation";
    "keyDrivers": string[];
    "recommendedAdjustments": string[];
  }[];
  "globalPatterns": {
    "topicsWorking": string[];
    "topicsToAvoid": string[];
    "styleNotes": string[];
    "postingTimeHints": string[];
  };
}
`;

    const userPrompt: { role: 'user' | 'assistant' | 'system'; content: string } = {
      role: 'user',
      content: `Analyze the following posts and return JSON only.\n\n${JSON.stringify(
        pastData,
      )}`,
    };

    const raw = await this.callModel(systemPrompt, [userPrompt]);
    return this.safeParseJSON<PerformanceInsights>(raw, 'analyze_performance');
  }

  async refine_strategy(
    insights: PerformanceInsights,
    currentGoals: string[],
    previousVersion: number,
  ): Promise<StrategyGuidelines> {
    const systemPrompt = `
You are an AI content strategist improving a LinkedIn posting strategy.
Return STRICT JSON matching this TypeScript type:
{
  "version": number;
  "goals": string[];
  "contentPillars": string[];
  "postingCadence": string;
  "toneAndStyle": string;
  "doMoreOf": string[];
  "doLessOf": string[];
}
`;

    const userPrompt: { role: 'user' | 'assistant' | 'system'; content: string } = {
      role: 'user',
      content: `Current goals: ${JSON.stringify(
        currentGoals,
      )}\n\nInsights from performance:\n${JSON.stringify(
        insights,
      )}\n\nBase the next version on version ${previousVersion} and increment the version number.`,
    };

    const raw = await this.callModel(systemPrompt, [userPrompt]);
    const parsed = this.safeParseJSON<StrategyGuidelines>(
      raw,
      'refine_strategy',
    );
    if (!parsed.version || parsed.version <= previousVersion) {
      parsed.version = previousVersion + 1;
    }
    return parsed;
  }

  async draft_post(input: DraftPostInput): Promise<DraftPostResult> {
    const systemPrompt = `
You are a LinkedIn ghostwriter agent.
You must perfectly mimic the user's style, given their persona prompt, and follow the provided strategy guidelines.
You MUST return STRICT JSON only, no explanations, matching:
{
  "caption": string;
  "imageId": string | null;
  "reasoning": string;
  "expectedMetrics": Record<string, any>;
}

Rules:
- Keep captions concise, high-signal, and formatted for LinkedIn (short paragraphs, occasional emojis allowed, but not mandatory).
- Include a clear hook in the first 2 lines.
- Avoid hashtags overload (0-5 highly targeted hashtags).
`;

    const userPrompt: { role: 'user' | 'assistant' | 'system'; content: string } = {
      role: 'user',
      content: `Draft a LinkedIn post.\n\nInput:\n${JSON.stringify(
        input,
      )}\n\nChoose the best imageId from availableImages (or null if text-only).`,
    };

    const raw = await this.callModel(systemPrompt, [userPrompt]);
    return this.safeParseJSON<DraftPostResult>(raw, 'draft_post');
  }

  // --- Low-level model call wrapper ---

  private async callModel(
    systemPrompt: string,
    messages: Array<{ role: 'user' | 'assistant' | 'system'; content: string }>,
  ): Promise<string> {
    if (this.config.provider === 'nano-banana') {
      return this.callNanoBanana(systemPrompt, messages);
    }
    return this.callGroq(systemPrompt, messages);
  }

  private async callNanoBanana(
    systemPrompt: string,
    messages: Array<{ role: string; content: string }>,
  ): Promise<string> {
    if (!this.config.nanoBananaUrl) {
      throw new Error('NANO_BANANA_URL is not configured');
    }

    const res = await fetch(this.config.nanoBananaUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(this.config.nanoBananaApiKey
          ? { Authorization: `Bearer ${this.config.nanoBananaApiKey}` }
          : {}),
      },
      body: JSON.stringify({
        model: this.config.model,
        messages: [
          { role: 'system', content: systemPrompt },
          ...messages,
        ],
        response_format: { type: 'json_object' },
      }),
    });

    if (!res.ok) {
      const text = await res.text();
      throw new Error(
        `Nano Banana request failed: ${res.status} ${res.statusText} - ${text}`,
      );
    }

    const data = await res.json();
    // assuming OpenAI-style payload
    return (
      data.choices?.[0]?.message?.content ??
      JSON.stringify(data)
    ) as string;
  }

  private async callGroq(
    systemPrompt: string,
    messages: Array<{ role: string; content: string }>,
  ): Promise<string> {
    if (!this.config.groqApiKey) {
      throw new Error('GROQ_API_KEY is not configured');
    }

    const res = await fetch('https://api.groq.com/openai/v1/chat/completions', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${this.config.groqApiKey}`,
      },
      body: JSON.stringify({
        model: this.config.model,
        messages: [
          { role: 'system', content: systemPrompt },
          ...messages,
        ],
        response_format: { type: 'json_object' },
      }),
    });

    if (!res.ok) {
      const text = await res.text();
      throw new Error(
        `Groq request failed: ${res.status} ${res.statusText} - ${text}`,
      );
    }

    const data = await res.json();
    return (
      data.choices?.[0]?.message?.content ??
      JSON.stringify(data)
    ) as string;
  }

  private safeParseJSON<T>(raw: string, context: string): T {
    try {
      // Some models may wrap JSON in markdown fences; strip them.
      const cleaned = raw
        .trim()
        .replace(/^```(json)?/i, '')
        .replace(/```$/, '')
        .trim();
      return JSON.parse(cleaned) as T;
    } catch (err) {
      throw new Error(
        `Failed to parse JSON response from model in ${context}: ${String(
          err,
        )}. Raw: ${raw}`,
      );
    }
  }
}


