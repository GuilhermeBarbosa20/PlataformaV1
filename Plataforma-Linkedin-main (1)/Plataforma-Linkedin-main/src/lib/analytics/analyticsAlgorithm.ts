/**
 * Analytics Algorithm Service
 * 
 * Analyzes post performance data to generate insights and recommendations
 * that can be used to improve future post generation based on user objectives.
 */

export interface PostAnalyticsData {
    post_id: string;
    caption: string;
    published_at: string;
    reaction_counter: number;
    comment_counter: number;
    repost_counter: number;
    impressions_counter: number;
    ai_content?: {
        headline?: string;
        body?: string;
        tone?: string;
    };
    themes?: string[];
    analytics?: {
        engagement_rate?: number;
        clicks?: number;
        followers_gained_from_this_post?: number;
    };
}

export interface UserObjective {
    objective: string;
    priority: number;
}

export interface AnalyticsInsights {
    // Performance summary
    avgEngagementRate: number;
    avgReactions: number;
    avgComments: number;
    totalFollowersGained: number;

    // Top performing content patterns
    topPerformingThemes: string[];
    bestContentLength: 'short' | 'medium' | 'long';
    bestPostingDays: string[];
    bestPostingHours: number[];

    // Recommendations for content generation
    recommendations: string[];

    // Objective progress tracking
    objectiveProgress: Record<string, {
        objective: string;
        progress: number; // 0-100
        trend: 'up' | 'down' | 'stable';
        insight: string;
    }>;

    // Content suggestions for next posts
    contentSuggestions: {
        suggestedThemes: string[];
        suggestedTone: string;
        suggestedLength: string;
        suggestedCta: string;
    };
}

/**
 * Analyze post performance and generate insights
 */
export function analyzePostPerformance(
    posts: PostAnalyticsData[],
    objectives: UserObjective[]
): AnalyticsInsights {
    if (posts.length === 0) {
        return getEmptyInsights();
    }

    // Calculate averages
    const avgEngagementRate = calculateAvgEngagementRate(posts);
    const avgReactions = calculateAvg(posts, 'reaction_counter');
    const avgComments = calculateAvg(posts, 'comment_counter');
    const totalFollowersGained = posts.reduce(
        (sum, p) => sum + (p.analytics?.followers_gained_from_this_post || 0),
        0
    );

    // Analyze content patterns
    const topPerformingPosts = getTopPerformingPosts(posts, 5);
    const topPerformingThemes = extractThemes(topPerformingPosts);
    const bestContentLength = analyzeBestContentLength(topPerformingPosts);
    const { bestDays, bestHours } = analyzeBestPostingTimes(topPerformingPosts);

    // Generate recommendations
    const recommendations = generateRecommendations(posts, objectives, topPerformingPosts);

    // Calculate objective progress
    const objectiveProgress = calculateObjectiveProgress(posts, objectives, avgEngagementRate);

    // Generate content suggestions
    const contentSuggestions = generateContentSuggestions(
        topPerformingThemes,
        bestContentLength,
        topPerformingPosts
    );

    return {
        avgEngagementRate,
        avgReactions,
        avgComments,
        totalFollowersGained,
        topPerformingThemes,
        bestContentLength,
        bestPostingDays: bestDays,
        bestPostingHours: bestHours,
        recommendations,
        objectiveProgress,
        contentSuggestions,
    };
}

function getEmptyInsights(): AnalyticsInsights {
    return {
        avgEngagementRate: 0,
        avgReactions: 0,
        avgComments: 0,
        totalFollowersGained: 0,
        topPerformingThemes: [],
        bestContentLength: 'medium',
        bestPostingDays: [],
        bestPostingHours: [],
        recommendations: ['Publique mais posts para gerar insights de performance'],
        objectiveProgress: {},
        contentSuggestions: {
            suggestedThemes: [],
            suggestedTone: 'profissional',
            suggestedLength: 'médio',
            suggestedCta: 'Comente sua opinião!',
        },
    };
}

function calculateAvgEngagementRate(posts: PostAnalyticsData[]): number {
    const validPosts = posts.filter(p => p.analytics?.engagement_rate);
    if (validPosts.length === 0) {
        // Calculate from reactions/impressions if no engagement_rate available
        const postsWithImpressions = posts.filter(p => p.impressions_counter > 0);
        if (postsWithImpressions.length === 0) return 0;

        const totalEngagement = postsWithImpressions.reduce(
            (sum, p) => sum + (p.reaction_counter + p.comment_counter + p.repost_counter),
            0
        );
        const totalImpressions = postsWithImpressions.reduce(
            (sum, p) => sum + p.impressions_counter,
            0
        );
        return totalImpressions > 0 ? (totalEngagement / totalImpressions) * 100 : 0;
    }

    return validPosts.reduce((sum, p) => sum + (p.analytics?.engagement_rate || 0), 0) / validPosts.length;
}

function calculateAvg(posts: PostAnalyticsData[], field: keyof PostAnalyticsData): number {
    if (posts.length === 0) return 0;
    return posts.reduce((sum, p) => sum + (Number(p[field]) || 0), 0) / posts.length;
}

function getTopPerformingPosts(posts: PostAnalyticsData[], count: number): PostAnalyticsData[] {
    return [...posts]
        .sort((a, b) => {
            const engagementA = a.reaction_counter + a.comment_counter * 2 + a.repost_counter * 3;
            const engagementB = b.reaction_counter + b.comment_counter * 2 + b.repost_counter * 3;
            return engagementB - engagementA;
        })
        .slice(0, count);
}

function extractThemes(posts: PostAnalyticsData[]): string[] {
    const themeCounts = new Map<string, number>();

    posts.forEach((post) => {
        if (post.themes) {
            post.themes.forEach((theme) => {
                themeCounts.set(theme, (themeCounts.get(theme) || 0) + 1);
            });
        }
    });

    return Array.from(themeCounts.entries())
        .sort((a, b) => b[1] - a[1])
        .slice(0, 3)
        .map(([theme]) => theme);
}

function analyzeBestContentLength(posts: PostAnalyticsData[]): 'short' | 'medium' | 'long' {
    const lengthScores = { short: 0, medium: 0, long: 0 };

    posts.forEach((post) => {
        const length = (post.caption || '').length;
        const engagement = post.reaction_counter + post.comment_counter * 2;

        if (length < 500) {
            lengthScores.short += engagement;
        } else if (length < 1500) {
            lengthScores.medium += engagement;
        } else {
            lengthScores.long += engagement;
        }
    });

    if (lengthScores.long >= lengthScores.medium && lengthScores.long >= lengthScores.short) {
        return 'long';
    }
    if (lengthScores.short >= lengthScores.medium) {
        return 'short';
    }
    return 'medium';
}

function analyzeBestPostingTimes(posts: PostAnalyticsData[]): { bestDays: string[]; bestHours: number[] } {
    const dayEngagement = new Map<string, number>();
    const hourEngagement = new Map<number, number>();
    const dayNames = ['Domingo', 'Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado'];

    posts.forEach((post) => {
        if (!post.published_at) return;

        const date = new Date(post.published_at);
        const day = dayNames[date.getDay()];
        const hour = date.getHours();
        const engagement = post.reaction_counter + post.comment_counter * 2;

        dayEngagement.set(day, (dayEngagement.get(day) || 0) + engagement);
        hourEngagement.set(hour, (hourEngagement.get(hour) || 0) + engagement);
    });

    const bestDays = Array.from(dayEngagement.entries())
        .sort((a, b) => b[1] - a[1])
        .slice(0, 2)
        .map(([day]) => day);

    const bestHours = Array.from(hourEngagement.entries())
        .sort((a, b) => b[1] - a[1])
        .slice(0, 3)
        .map(([hour]) => hour);

    return { bestDays, bestHours };
}

function generateRecommendations(
    posts: PostAnalyticsData[],
    objectives: UserObjective[],
    topPosts: PostAnalyticsData[]
): string[] {
    const recommendations: string[] = [];

    // Engagement recommendations
    const avgComments = calculateAvg(posts, 'comment_counter');
    if (avgComments < 3) {
        recommendations.push('Adicione mais CTAs (call-to-action) perguntando a opinião dos leitores');
    }

    // Content length recommendations
    const avgLength = posts.reduce((sum, p) => sum + (p.caption?.length || 0), 0) / posts.length;
    if (avgLength < 500) {
        recommendations.push('Experimente posts mais longos com histórias ou cases para aumentar engajamento');
    }

    // Objective-based recommendations
    objectives.forEach((obj) => {
        switch (obj.objective) {
            case 'Aumentar seguidores':
                recommendations.push('Inclua mais conteúdo educacional e dicas práticas para atrair seguidores');
                break;
            case 'Gerar leads':
                recommendations.push('Adicione CTAs específicos sobre seus serviços nos posts de melhor performance');
                break;
            case 'Construir comunidade':
                recommendations.push('Responda mais comentários e faça perguntas abertas aos leitores');
                break;
        }
    });

    return recommendations.slice(0, 5);
}

function calculateObjectiveProgress(
    posts: PostAnalyticsData[],
    objectives: UserObjective[],
    avgEngagementRate: number
): AnalyticsInsights['objectiveProgress'] {
    const progress: AnalyticsInsights['objectiveProgress'] = {};

    objectives.forEach((obj) => {
        let progressValue = 0;
        let trend: 'up' | 'down' | 'stable' = 'stable';
        let insight = '';

        switch (obj.objective) {
            case 'Aumentar seguidores':
                const followersGained = posts.reduce(
                    (sum, p) => sum + (p.analytics?.followers_gained_from_this_post || 0),
                    0
                );
                progressValue = Math.min(followersGained * 10, 100);
                insight = followersGained > 0
                    ? `Ganhou ${followersGained} seguidores dos posts`
                    : 'Nenhum seguidor ganho ainda';
                break;

            case 'Aumentar visualizações':
                const totalImpressions = posts.reduce((sum, p) => sum + p.impressions_counter, 0);
                progressValue = Math.min(totalImpressions / 100, 100);
                insight = `${totalImpressions} impressões totais`;
                break;

            case 'Gerar leads':
                const clicks = posts.reduce((sum, p) => sum + (p.analytics?.clicks || 0), 0);
                progressValue = Math.min(clicks * 5, 100);
                insight = `${clicks} cliques nos posts`;
                break;

            default:
                progressValue = Math.min(avgEngagementRate * 10, 100);
                insight = `Taxa de engajamento: ${avgEngagementRate.toFixed(2)}%`;
        }

        progress[obj.objective] = {
            objective: obj.objective,
            progress: progressValue,
            trend,
            insight,
        };
    });

    return progress;
}

function generateContentSuggestions(
    topThemes: string[],
    bestLength: 'short' | 'medium' | 'long',
    topPosts: PostAnalyticsData[]
): AnalyticsInsights['contentSuggestions'] {
    const lengthMap = {
        short: 'curto (até 500 caracteres)',
        medium: 'médio (500-1500 caracteres)',
        long: 'longo (1500+ caracteres)',
    };

    // Extract tone from top posts
    const tones = topPosts
        .map((p) => p.ai_content?.tone)
        .filter(Boolean);
    const suggestedTone = tones.length > 0 ? tones[0] as string : 'profissional e acessível';

    return {
        suggestedThemes: topThemes.length > 0 ? topThemes : ['produtividade', 'carreira', 'inovação'],
        suggestedTone,
        suggestedLength: lengthMap[bestLength],
        suggestedCta: 'O que você acha? Comente abaixo! 👇',
    };
}

/**
 * Generate a context string for the AI agent to use when generating posts
 */
export function generateAgentContext(insights: AnalyticsInsights): string {
    const lines: string[] = [
        '## Insights de Performance dos Posts Anteriores',
        '',
        `- Taxa média de engajamento: ${insights.avgEngagementRate.toFixed(2)}%`,
        `- Média de reações por post: ${insights.avgReactions.toFixed(1)}`,
        `- Média de comentários por post: ${insights.avgComments.toFixed(1)}`,
        '',
    ];

    if (insights.topPerformingThemes.length > 0) {
        lines.push(`**Temas que mais performam:** ${insights.topPerformingThemes.join(', ')}`);
    }

    if (insights.bestPostingDays.length > 0) {
        lines.push(`**Melhores dias para postar:** ${insights.bestPostingDays.join(', ')}`);
    }

    lines.push(`**Tamanho ideal de conteúdo:** ${insights.contentSuggestions.suggestedLength}`);
    lines.push(`**Tom recomendado:** ${insights.contentSuggestions.suggestedTone}`);
    lines.push('');
    lines.push('**Recomendações:**');
    insights.recommendations.forEach((rec) => {
        lines.push(`- ${rec}`);
    });

    return lines.join('\n');
}
