import { NextRequest, NextResponse } from 'next/server';
import { createClient } from '@supabase/supabase-js';

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL!;
const supabaseServiceKey = process.env.SUPABASE_SERVICE_ROLE_KEY!;
const OPENAI_API_KEY = process.env.OPENAI_API_KEY;

type ResponseType = 'agradecer' | 'agregar_valor' | 'resposta_simples' | 'perguntar';

const RESPONSE_PROMPTS: Record<ResponseType, string> = {
    agradecer: `Gere uma resposta de AGRADECIMENTO calorosa e genuína. 
A resposta deve:
- Agradecer pelo comentário/contribuição
- Mostrar que você valoriza a interação
- Ser breve mas sincera (1-2 frases)
- Usar emoji apropriado (como 🙏 ou 💪)`,

    agregar_valor: `Gere uma resposta que AGREGA VALOR ao que foi dito.
A resposta deve:
- Complementar a ideia do comentário
- Trazer um insight adicional ou perspectiva
- Ser construtiva e enriquecedora
- Ter 2-3 frases no máximo`,

    resposta_simples: `Gere uma RESPOSTA SIMPLES e cordial.
A resposta deve:
- Ser breve e direta
- Concordar ou reconhecer o ponto do comentário
- Ser amigável mas profissional
- Ter apenas 1 frase curta`,

    perguntar: `Gere uma resposta que faz uma PERGUNTA sobre o assunto.
A resposta deve:
- Demonstrar interesse genuíno no ponto de vista do autor
- Fazer uma pergunta relevante sobre o tema
- Estimular mais diálogo
- Ter 1-2 frases no máximo`,
};

/**
 * POST /api/generate-comment-reply
 * 
 * Generates an AI-powered reply to a LinkedIn comment
 * 
 * Body:
 * - post_text: The original post text
 * - comment_text: The comment to respond to
 * - comment_author: The comment author name
 * - response_type: The type of response (agradecer, agregar_valor, resposta_simples, perguntar)
 */
export async function POST(request: NextRequest) {
    try {
        if (!OPENAI_API_KEY) {
            return NextResponse.json(
                { error: 'OpenAI API key not configured' },
                { status: 503 }
            );
        }

        const authHeader = request.headers.get('authorization');
        if (!authHeader || !authHeader.startsWith('Bearer ')) {
            return NextResponse.json(
                { error: 'Missing or invalid authorization header' },
                { status: 401 }
            );
        }

        const token = authHeader.replace('Bearer ', '');
        const supabase = createClient(supabaseUrl, supabaseServiceKey);
        const { data: { user }, error: authError } = await supabase.auth.getUser(token);

        if (authError || !user) {
            return NextResponse.json(
                { error: 'Invalid or expired token' },
                { status: 401 }
            );
        }

        const body = await request.json();
        const { post_text, comment_text, comment_author, response_type } = body;

        if (!comment_text || !response_type) {
            return NextResponse.json(
                { error: 'comment_text and response_type are required' },
                { status: 400 }
            );
        }

        const responseInstruction = RESPONSE_PROMPTS[response_type as ResponseType];
        if (!responseInstruction) {
            return NextResponse.json(
                { error: 'Invalid response_type' },
                { status: 400 }
            );
        }

        // Build the prompt
        const systemPrompt = `Você é um especialista em LinkedIn que ajuda profissionais a responder comentários de forma estratégica.
Suas respostas devem ser:
- Naturais e autênticas
- Profissionais mas não formais demais
- Adequadas para público brasileiro do LinkedIn
- Em português brasileiro

NUNCA inclua:
- Saudações como "Olá" ou "Oi"
- Assinaturas ou nome no final
- Frases genéricas ou robóticas
- Mais de 280 caracteres (limite do LinkedIn)`;

        const userPrompt = `${responseInstruction}

**CONTEXTO DO POST:**
${post_text ? `"${post_text.substring(0, 500)}${post_text.length > 500 ? '...' : ''}"` : '(Post não disponível)'}

**COMENTÁRIO de ${comment_author || 'um usuário'}:**
"${comment_text}"

Gere APENAS a resposta, sem explicações ou formatação adicional.`;

        const response = await fetch('https://api.openai.com/v1/chat/completions', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${OPENAI_API_KEY}`,
            },
            body: JSON.stringify({
                model: 'gpt-4o-mini',
                temperature: 0.7,
                max_tokens: 200,
                messages: [
                    { role: 'system', content: systemPrompt },
                    { role: 'user', content: userPrompt },
                ],
            }),
        });

        if (!response.ok) {
            const errorText = await response.text();
            console.error('[generate-comment-reply] OpenAI error:', errorText);
            return NextResponse.json(
                { error: 'Failed to generate response' },
                { status: 500 }
            );
        }

        const completion = await response.json();
        const generatedReply = completion?.choices?.[0]?.message?.content?.trim();

        if (!generatedReply) {
            return NextResponse.json(
                { error: 'No response generated' },
                { status: 500 }
            );
        }

        return NextResponse.json({
            success: true,
            reply: generatedReply,
        });

    } catch (error) {
        console.error('[generate-comment-reply] Error:', error);
        return NextResponse.json(
            { error: 'Failed to generate reply' },
            { status: 500 }
        );
    }
}
