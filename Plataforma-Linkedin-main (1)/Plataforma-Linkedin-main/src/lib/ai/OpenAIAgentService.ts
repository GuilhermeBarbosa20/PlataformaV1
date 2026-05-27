/**
 * OpenAI Agent Service
 * Manages per-user AI Assistants with Vector Stores for personalized content analysis
 */

const OPENAI_BASE_URL = 'https://api.openai.com/v1';

export interface CreateAgentResult {
  assistantId: string;
  vectorStoreId: string;
  threadId: string;
}

export interface VectorStoreFile {
  fileId: string;
  filename: string;
}

export interface AgentAnalysisResult {
  themes: Array<{
    name: string;
    description: string;
    relevance: number;
    examples: string[];
  }>;
  writingStyle: {
    tone: string;
    averageLength: string;
    commonPatterns: string[];
  };
  recommendations: string[];
}

/**
 * Creates a new OpenAI Vector Store for a user
 * Vector stores do NOT expire by default
 */
export async function createVectorStore(
  userId: string,
  userName?: string
): Promise<string> {
  const apiKey = process.env.OPENAI_API_KEY;
  if (!apiKey) throw new Error('OPENAI_API_KEY not configured');

  console.log('[OPENAI] Creating vector store for user:', userId);

  const response = await fetch(`${OPENAI_BASE_URL}/vector_stores`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${apiKey}`,
      'Content-Type': 'application/json',
      'OpenAI-Beta': 'assistants=v2',
    },
    body: JSON.stringify({
      name: `LinkedIn Posts - ${userName || userId}`,
      // No expiration policy = never expires
    }),
  });

  if (!response.ok) {
    const error = await response.text();
    throw new Error(`Failed to create vector store: ${error}`);
  }

  const data = await response.json();
  console.log('[OPENAI] Vector store created:', data.id);
  return data.id;
}

/**
 * Uploads posts as files to the Vector Store
 */
export async function uploadPostsToVectorStore(
  vectorStoreId: string,
  posts: any[],
  userId: string
): Promise<VectorStoreFile[]> {
  const apiKey = process.env.OPENAI_API_KEY;
  if (!apiKey) throw new Error('OPENAI_API_KEY not configured');

  console.log('[OPENAI] Uploading', posts.length, 'posts to vector store');

  // Create a combined document with all posts
  const postsContent = posts.map((post, index) => {
    const date = post.postedAt || post.postedAtTimestamp 
      ? new Date(post.postedAtTimestamp || post.postedAt).toLocaleDateString('pt-BR')
      : 'Data desconhecida';
    
    return `
=== POST ${index + 1} ===
Data: ${date}
Texto: ${post.text || 'Sem texto'}
Reações: ${post.reactionCount || 0}
Comentários: ${post.commentsCount || 0}
Compartilhamentos: ${post.sharesCount || 0}
---
`;
  }).join('\n');

  // Create the file
  const formData = new FormData();
  const blob = new Blob([postsContent], { type: 'text/plain' });
  formData.append('file', blob, `linkedin_posts_${userId}.txt`);
  formData.append('purpose', 'assistants');

  const uploadResponse = await fetch(`${OPENAI_BASE_URL}/files`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${apiKey}`,
    },
    body: formData,
  });

  if (!uploadResponse.ok) {
    const error = await uploadResponse.text();
    throw new Error(`Failed to upload file: ${error}`);
  }

  const fileData = await uploadResponse.json();
  console.log('[OPENAI] File uploaded:', fileData.id);

  // Attach file to vector store
  const attachResponse = await fetch(`${OPENAI_BASE_URL}/vector_stores/${vectorStoreId}/files`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${apiKey}`,
      'Content-Type': 'application/json',
      'OpenAI-Beta': 'assistants=v2',
    },
    body: JSON.stringify({
      file_id: fileData.id,
    }),
  });

  if (!attachResponse.ok) {
    const error = await attachResponse.text();
    throw new Error(`Failed to attach file to vector store: ${error}`);
  }

  console.log('[OPENAI] File attached to vector store');

  return [{ fileId: fileData.id, filename: `linkedin_posts_${userId}.txt` }];
}

/**
 * Creates a new OpenAI Assistant with the user's Vector Store
 */
export async function createAssistant(
  userId: string,
  vectorStoreId: string,
  userName?: string
): Promise<string> {
  const apiKey = process.env.OPENAI_API_KEY;
  if (!apiKey) throw new Error('OPENAI_API_KEY not configured');

  console.log('[OPENAI] Creating assistant for user:', userId);

  const instructions = `Você é um assistente especializado em análise de conteúdo do LinkedIn para o usuário ${userName || 'profissional'}.

Seu papel é:
1. Analisar os posts históricos do usuário para identificar padrões, temas e estilo de escrita
2. Sugerir novos temas de conteúdo baseados no que funcionou bem
3. Ajudar a criar conteúdo que mantenha a voz autêntica do usuário
4. Fornecer insights sobre engajamento e performance

Você tem acesso aos posts anteriores do usuário através da sua base de conhecimento.
Sempre responda em Português do Brasil.
Seja direto, profissional e forneça insights acionáveis.`;

  const response = await fetch(`${OPENAI_BASE_URL}/assistants`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${apiKey}`,
      'Content-Type': 'application/json',
      'OpenAI-Beta': 'assistants=v2',
    },
    body: JSON.stringify({
      name: `LinkedIn Agent - ${userName || userId}`,
      instructions,
      model: 'gpt-4o-mini',
      tools: [{ type: 'file_search' }],
      tool_resources: {
        file_search: {
          vector_store_ids: [vectorStoreId],
        },
      },
    }),
  });

  if (!response.ok) {
    const error = await response.text();
    throw new Error(`Failed to create assistant: ${error}`);
  }

  const data = await response.json();
  console.log('[OPENAI] Assistant created:', data.id);
  return data.id;
}

/**
 * Creates a new conversation thread
 */
export async function createThread(): Promise<string> {
  const apiKey = process.env.OPENAI_API_KEY;
  if (!apiKey) throw new Error('OPENAI_API_KEY not configured');

  const response = await fetch(`${OPENAI_BASE_URL}/threads`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${apiKey}`,
      'Content-Type': 'application/json',
      'OpenAI-Beta': 'assistants=v2',
    },
    body: JSON.stringify({}),
  });

  if (!response.ok) {
    const error = await response.text();
    throw new Error(`Failed to create thread: ${error}`);
  }

  const data = await response.json();
  return data.id;
}

/**
 * Sends a message to the assistant and gets a response
 */
export async function sendMessage(
  threadId: string,
  assistantId: string,
  message: string
): Promise<string> {
  const apiKey = process.env.OPENAI_API_KEY;
  if (!apiKey) throw new Error('OPENAI_API_KEY not configured');

  // Add message to thread
  await fetch(`${OPENAI_BASE_URL}/threads/${threadId}/messages`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${apiKey}`,
      'Content-Type': 'application/json',
      'OpenAI-Beta': 'assistants=v2',
    },
    body: JSON.stringify({
      role: 'user',
      content: message,
    }),
  });

  // Run the assistant
  const runResponse = await fetch(`${OPENAI_BASE_URL}/threads/${threadId}/runs`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${apiKey}`,
      'Content-Type': 'application/json',
      'OpenAI-Beta': 'assistants=v2',
    },
    body: JSON.stringify({
      assistant_id: assistantId,
    }),
  });

  if (!runResponse.ok) {
    const error = await runResponse.text();
    throw new Error(`Failed to run assistant: ${error}`);
  }

  const run = await runResponse.json();

  // Poll for completion
  let status = run.status;
  let attempts = 0;
  const maxAttempts = 60;

  while (status !== 'completed' && status !== 'failed' && attempts < maxAttempts) {
    await new Promise(resolve => setTimeout(resolve, 1000));
    
    const statusResponse = await fetch(`${OPENAI_BASE_URL}/threads/${threadId}/runs/${run.id}`, {
      headers: {
        'Authorization': `Bearer ${apiKey}`,
        'OpenAI-Beta': 'assistants=v2',
      },
    });
    
    const statusData = await statusResponse.json();
    status = statusData.status;
    attempts++;
  }

  if (status !== 'completed') {
    throw new Error(`Assistant run failed with status: ${status}`);
  }

  // Get the latest message
  const messagesResponse = await fetch(`${OPENAI_BASE_URL}/threads/${threadId}/messages?limit=1`, {
    headers: {
      'Authorization': `Bearer ${apiKey}`,
      'OpenAI-Beta': 'assistants=v2',
    },
  });

  const messagesData = await messagesResponse.json();
  const assistantMessage = messagesData.data[0];

  if (assistantMessage?.content?.[0]?.type === 'text') {
    return assistantMessage.content[0].text.value;
  }

  return 'No response from assistant';
}

/**
 * Analyzes posts using the assistant to extract themes
 */
export async function analyzePostsWithAgent(
  assistantId: string,
  threadId: string
): Promise<AgentAnalysisResult> {
  const prompt = `Analise todos os posts do LinkedIn na sua base de conhecimento e me forneça:

1. **Temas Principais**: Liste os 5-7 principais temas/assuntos que aparecem nos posts, com:
   - Nome do tema
   - Breve descrição
   - Nível de relevância (0.0 a 1.0)
   - 2-3 exemplos de frases dos posts

2. **Estilo de Escrita**: Descreva:
   - Tom predominante (ex: profissional, casual, técnico)
   - Tamanho médio dos posts
   - Padrões comuns (ex: usa perguntas, conta histórias, usa dados)

3. **Recomendações**: Liste 3-5 sugestões de novos temas ou abordagens baseadas no que funcionou bem.

Responda APENAS em formato JSON válido seguindo esta estrutura:
{
  "themes": [
    {
      "name": "string",
      "description": "string",
      "relevance": number,
      "examples": ["string"]
    }
  ],
  "writingStyle": {
    "tone": "string",
    "averageLength": "string",
    "commonPatterns": ["string"]
  },
  "recommendations": ["string"]
}`;

  const response = await sendMessage(threadId, assistantId, prompt);

  // Parse JSON from response
  try {
    const jsonMatch = response.match(/\{[\s\S]*\}/);
    if (jsonMatch) {
      return JSON.parse(jsonMatch[0]) as AgentAnalysisResult;
    }
  } catch (e) {
    console.error('[OPENAI] Failed to parse analysis response:', e);
  }

  // Fallback response
  return {
    themes: [
      { name: 'Desenvolvimento Profissional', description: 'Crescimento na carreira', relevance: 0.8, examples: [] },
      { name: 'Tecnologia', description: 'Inovação e tendências tech', relevance: 0.7, examples: [] },
      { name: 'Liderança', description: 'Gestão e liderança', relevance: 0.6, examples: [] },
    ],
    writingStyle: {
      tone: 'Profissional',
      averageLength: 'Médio',
      commonPatterns: ['Posts diretos', 'Compartilha experiências'],
    },
    recommendations: [
      'Experimentar posts com perguntas para engajamento',
      'Incluir mais dados e estatísticas',
      'Contar mais histórias pessoais',
    ],
  };
}

/**
 * Complete flow to create a user's AI agent
 */
export async function createUserAgent(
  userId: string,
  userName: string | undefined,
  posts: any[]
): Promise<CreateAgentResult> {
  console.log('\n========================================');
  console.log('[AGENT] Creating AI Agent for user');
  console.log('========================================');
  console.log('[AGENT] User ID:', userId);
  console.log('[AGENT] Posts count:', posts.length);

  // 1. Create Vector Store
  const vectorStoreId = await createVectorStore(userId, userName);

  // 2. Upload posts to Vector Store
  if (posts.length > 0) {
    await uploadPostsToVectorStore(vectorStoreId, posts, userId);
  }

  // 3. Create Assistant
  const assistantId = await createAssistant(userId, vectorStoreId, userName);

  // 4. Create Thread
  const threadId = await createThread();

  console.log('[AGENT] ✅ Agent created successfully!');
  console.log('[AGENT] Assistant ID:', assistantId);
  console.log('[AGENT] Vector Store ID:', vectorStoreId);
  console.log('[AGENT] Thread ID:', threadId);

  return {
    assistantId,
    vectorStoreId,
    threadId,
  };
}

/**
 * Deletes a user's AI agent resources
 */
export async function deleteUserAgent(
  assistantId?: string,
  vectorStoreId?: string
): Promise<void> {
  const apiKey = process.env.OPENAI_API_KEY;
  if (!apiKey) return;

  if (assistantId) {
    try {
      await fetch(`${OPENAI_BASE_URL}/assistants/${assistantId}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${apiKey}`,
          'OpenAI-Beta': 'assistants=v2',
        },
      });
      console.log('[OPENAI] Deleted assistant:', assistantId);
    } catch (e) {
      console.error('[OPENAI] Failed to delete assistant:', e);
    }
  }

  if (vectorStoreId) {
    try {
      await fetch(`${OPENAI_BASE_URL}/vector_stores/${vectorStoreId}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${apiKey}`,
          'OpenAI-Beta': 'assistants=v2',
        },
      });
      console.log('[OPENAI] Deleted vector store:', vectorStoreId);
    } catch (e) {
      console.error('[OPENAI] Failed to delete vector store:', e);
    }
  }
}
