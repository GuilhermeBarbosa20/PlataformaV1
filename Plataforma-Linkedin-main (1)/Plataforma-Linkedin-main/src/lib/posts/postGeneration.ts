import { createClient } from '@/utils/supabase/server';
import { getGoogleAuth, getProjectId } from '@/lib/google-auth';

export type ThemeInput = Array<{
  theme_name: string;
  importance_weight: number;
  communication_tone: string;
}>;

export type ObjectiveInput = string[];

export interface GeneratedPostContent {
  headline: string;
  hook: string;
  body: string;
  cta: string;
  hashtags: string[];
  tone: string;
  suggestedImagePrompt: string;
}

export interface UserPhotoData {
  id: string;
  public_url: string;
  is_primary: boolean;
  metadata: {
    appearance_description?: string;
    gender?: string;
    age_range?: string;
    hair?: string;
    skin_tone?: string;
    style?: string;
  };
}

interface GeneratePostArgs {
  date: string;
  themes: ThemeInput;
  objectives: ObjectiveInput;
}

interface ComposeCaptionOptions {
  content: Partial<GeneratedPostContent> | null;
}

export interface GenerateImageResult {
  imageUrl: string;
  metadata: Record<string, any>;
  isPersonalized?: boolean;
}

// Reference image for multimodal identity-preserving generation
export interface ReferenceImage {
  base64Data: string;
  mimeType: 'image/jpeg' | 'image/png' | 'image/webp';
}

const OPENAI_COMPLETIONS_URL = 'https://api.openai.com/v1/chat/completions';
// Use Gemini 2.5 Flash for native image generation with identity preservation
const DEFAULT_VERTEX_IMAGE_MODEL = 'gemini-2.5-flash-preview-05-20';
const DEFAULT_VERTEX_LOCATION = 'us-central1';

// Use the new auth system
const getVertexAuth = () => getGoogleAuth();

// ============================================
// POST CONTENT GENERATION
// ============================================

export async function generatePostContent({
  date,
  themes,
  objectives,
}: GeneratePostArgs): Promise<GeneratedPostContent> {
  const apiKey = process.env.OPENAI_API_KEY;
  if (!apiKey) {
    throw new Error('OPENAI_API_KEY is not configured');
  }

  // Get day of week for variety
  const dayOfWeek = new Date(date).getDay();
  const dayNames = ['Domingo', 'Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado'];

  // Different content formats for variety
  const contentFormats = [
    'história pessoal com lição aprendida',
    'lista numerada com dicas práticas (3-5 itens)',
    'pergunta provocadora seguida de reflexão',
    'caso de sucesso ou fracasso com análise',
    'comparação entre duas abordagens (antes vs depois)',
    'previsão ou tendência do mercado',
    'mito vs realidade sobre o tema',
  ];

  // Pick format based on day to ensure variety
  const selectedFormat = contentFormats[dayOfWeek % contentFormats.length];

  // Different opening styles
  const openingStyles = [
    'Comece com uma estatística surpreendente',
    'Comece com uma pergunta retórica',
    'Comece com uma afirmação controversa',
    'Comece com uma história curta em primeira pessoa',
    'Comece descrevendo um problema comum',
    'Comece com uma citação adaptada',
    'Comece com "Ontem aconteceu algo que..." ou similar',
  ];

  const selectedOpening = openingStyles[dayOfWeek % openingStyles.length];

  const systemPrompt = `És um redator especializado em LinkedIn para o mercado português.
Geras conteúdos VARIADOS e ÚNICOS em Português de Portugal, com um tom profissional porém humano e autêntico.

REGRA CRÍTICA DE DIVERSIDADE:
- CADA post deve ter uma estrutura COMPLETAMENTE DIFERENTE dos outros
- NUNCA use a mesma abertura ou formato duas vezes na semana
- VARIE entre: histórias pessoais, listas, perguntas, análises, comparações, previsões
- Use diferentes comprimentos: alguns posts curtos (3 parágrafos), outros médios (5-6 parágrafos)
- ALTERNE entre tons: inspirador, educativo, provocador, reflexivo, prático

Para ESTE post específico, use:
📌 FORMATO: ${selectedFormat}
📌 ABERTURA: ${selectedOpening}
📌 DIA: ${dayNames[dayOfWeek]}

Responde SEMPRE em JSON puro com a seguinte estrutura:
{
  "headline": string,
  "hook": string,
  "body": string,
  "cta": string,
  "hashtags": string[],
  "tone": string,
  "suggestedImagePrompt": string
}

Regras:
- O hook deve ter até 2 frases curtas e impactantes.
- O corpo deve ter parágrafos curtos separados por linhas em branco.
- VARIE o tamanho do corpo: de 2 a 6 parágrafos dependendo do formato.
- CTA claro e variado no final (não use sempre "Comente abaixo").
- Máximo 4 hashtags muito específicas e relevantes.
- A imagem sugerida deve descrever uma cena fotográfica realista, orientada para LinkedIn.
- NÃO use clichês como "neste mundo em constante mudança" ou "a chave para o sucesso".
- Seja AUTÊNTICO e evite linguagem corporativa genérica.`;

  const userPrompt = `Data alvo: ${date} (${dayNames[dayOfWeek]})
Temas prioritários (com peso): ${themes
      .map(
        (t) => `${t.theme_name} (${t.importance_weight}/100, tom ${t.communication_tone})`,
      )
      .join(', ') || 'Não definidos'}
Objectivos ativos: ${objectives.join(', ') || 'Sem objetivos definidos'}

IMPORTANTE: Este é um post para ${dayNames[dayOfWeek]}. 
Use o formato "${selectedFormat}" e comece de forma única.
Evita clichês e mantém autenticidade. Cria algo que REALMENTE se destaque.`;

  const response = await fetch(OPENAI_COMPLETIONS_URL, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${apiKey}`,
    },
    body: JSON.stringify({
      model: 'gpt-4o-mini',
      temperature: 0.85, // Higher temperature for more creativity and variety
      response_format: { type: 'json_object' },
      messages: [
        { role: 'system', content: systemPrompt },
        { role: 'user', content: userPrompt },
      ],
    }),
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`OpenAI request failed: ${response.status} ${errorText}`);
  }

  const completion = await response.json();
  const rawContent = completion?.choices?.[0]?.message?.content;
  if (!rawContent) {
    throw new Error('OpenAI response missing content');
  }

  try {
    const parsed = JSON.parse(rawContent) as GeneratedPostContent;
    return parsed;
  } catch (error) {
    throw new Error(`Failed to parse OpenAI JSON response: ${String(error)} | Raw: ${rawContent}`);
  }
}

export function composeCaption({ content }: ComposeCaptionOptions): string {
  if (!content) {
    return 'Conteúdo em preparação';
  }

  const sections = [content.hook, content.body, content.cta]
    .filter(Boolean)
    .map((section) => section?.trim());

  const hashtags = Array.isArray(content.hashtags)
    ? content.hashtags.filter(Boolean).map((tag) => (tag.startsWith('#') ? tag : `#${tag}`))
    : [];

  return [
    content.headline?.trim(),
    ...sections,
    hashtags.length ? hashtags.join(' ') : null,
  ]
    .filter(Boolean)
    .join('\n\n');
}

// ============================================
// USER PHOTOS HANDLING
// ============================================

/**
 * Fetch user photos from database
 */
export async function getUserPhotos(userId: string): Promise<UserPhotoData[]> {
  try {
    const supabase = await createClient();

    const { data: photos, error } = await supabase
      .from('user_photos')
      .select('id, public_url, is_primary, metadata')
      .eq('user_id', userId)
      .order('is_primary', { ascending: false });

    if (error) {
      console.error('[getUserPhotos] Error fetching photos:', error.message);
      return [];
    }

    return (photos || []) as UserPhotoData[];
  } catch (err) {
    console.error('[getUserPhotos] Exception:', err);
    return [];
  }
}

/**
 * Check if an appearance description describes multiple people
 * Returns true if the description is valid (single person), false if it describes multiple people
 */
function isValidSinglePersonDescription(description: string): boolean {
  if (!description) return false;

  const lowerDesc = description.toLowerCase();

  // Patterns that indicate multiple people
  const multiplePersonPatterns = [
    /\b(group of|team of|four|three|two|several|multiple)\s+(people|professionals|persons|individuals|men|women)/i,
    /\bfour professionals\b/i,
    /\bthree professionals\b/i,
    /\btwo professionals\b/i,
    /\bgroup photo\b/i,
    /\bmultiple people\b/i,
    /\bseveral people\b/i,
    /\bteam photo\b/i,
    /\bfirst person[\s,:].*second person/i,
    /\bperson 1[\s,:].*person 2/i,
    /\b(one|1)[\s.,:]+.*\b(two|2)[\s.,:]+/i,
  ];

  for (const pattern of multiplePersonPatterns) {
    if (pattern.test(description)) {
      console.log('[isValidSinglePersonDescription] Description describes multiple people, pattern matched:', pattern);
      return false;
    }
  }

  return true;
}

/**
 * Analyze a user photo to extract appearance description using OpenAI Vision
 */
export async function analyzeUserPhoto(photoUrl: string): Promise<string> {
  const apiKey = process.env.OPENAI_API_KEY;
  if (!apiKey) {
    console.error('[analyzeUserPhoto] OPENAI_API_KEY not configured');
    return '';
  }

  try {
    const response = await fetch(OPENAI_COMPLETIONS_URL, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${apiKey}`,
      },
      body: JSON.stringify({
        model: 'gpt-4o-mini',
        max_tokens: 500,
        messages: [
          {
            role: 'system',
            content: `You are an expert at describing people's physical appearance for AI image generation.
Analyze the photo and provide a DETAILED description of ONLY ONE PERSON - the main subject or protagonist in the photo.
If the photo contains multiple people, focus ONLY on the most prominent/central person and describe them as a single individual.
NEVER describe multiple people. ALWAYS describe exactly one person.
Focus on: gender, approximate age range, ethnicity/skin tone, hair (color, style, length), facial features, body type, and typical style/clothing preferences.
Be specific and objective. Output ONLY the description of ONE person, no extra text.
Example: "Professional man in his 30s, light skin, short dark brown hair styled back, clean-shaven, warm brown eyes, medium build, wearing business casual attire"`
          },
          {
            role: 'user',
            content: [
              {
                type: 'image_url',
                image_url: { url: photoUrl, detail: 'high' }
              },
              {
                type: 'text',
                text: 'Describe the MAIN PERSON (only one person) in this photo in detail for AI image generation purposes. Focus on single individual only.'
              }
            ]
          }
        ],
      }),
    });

    if (!response.ok) {
      console.error('[analyzeUserPhoto] API error:', response.status);
      return '';
    }

    const data = await response.json();
    const description = data.choices?.[0]?.message?.content || '';
    console.log('[analyzeUserPhoto] Generated description:', description.substring(0, 100) + '...');

    // Validate that the description is for a single person
    if (!isValidSinglePersonDescription(description)) {
      console.warn('[analyzeUserPhoto] Generated description describes multiple people, rejecting');
      return '';
    }

    return description;
  } catch (error) {
    console.error('[analyzeUserPhoto] Error:', error);
    return '';
  }
}

/**
 * Cache the appearance description in the database
 */
async function cacheAppearanceDescription(
  photoId: string,
  currentMetadata: any,
  description: string
): Promise<void> {
  try {
    const supabase = await createClient();
    await supabase
      .from('user_photos')
      .update({
        metadata: {
          ...currentMetadata,
          appearance_description: description
        }
      })
      .eq('id', photoId);
    console.log('[cacheAppearanceDescription] Cached successfully');
  } catch (err) {
    console.error('[cacheAppearanceDescription] Error:', err);
  }
}

// ============================================
// REFERENCE IMAGE HANDLING (Gemini 2.5 Flash Identity Preservation)
// ============================================

// Try to import image optimization - fallback if not available
let fetchAndOptimize: ((url: string, options?: any) => Promise<any>) | null = null;
try {
  // Dynamic import to avoid build issues if sharp is not installed
  const optimization = require('@/lib/imageOptimization');
  fetchAndOptimize = optimization.fetchAndOptimize;
} catch (e) {
  console.log('[postGeneration] Image optimization not available, using raw images');
}

/**
 * Fetch an image from URL and convert to base64 for Gemini multimodal input
 * @param optimize - If true, resize and compress the image to reduce tokens
 */
export async function fetchImageAsBase64(imageUrl: string, optimize = true): Promise<ReferenceImage | null> {
  try {
    console.log('[fetchImageAsBase64] Fetching image from:', imageUrl.substring(0, 80) + '...');

    // Try optimized fetch if available and requested
    if (optimize && fetchAndOptimize) {
      const optimized = await fetchAndOptimize(imageUrl, {
        maxWidth: 1024,
        maxHeight: 1024,
        quality: 80,
        format: 'jpeg',
      });

      if (optimized) {
        console.log('[fetchImageAsBase64] Optimized:', Math.round(optimized.originalSize / 1024), 'KB →', Math.round(optimized.optimizedSize / 1024), 'KB');
        return {
          base64Data: optimized.base64,
          mimeType: optimized.mimeType as 'image/jpeg' | 'image/png' | 'image/webp',
        };
      }
    }

    // Fallback to raw fetch
    const response = await fetch(imageUrl);
    if (!response.ok) {
      console.error('[fetchImageAsBase64] Failed to fetch image:', response.status);
      return null;
    }

    const contentType = response.headers.get('content-type') || 'image/jpeg';
    const arrayBuffer = await response.arrayBuffer();
    const base64Data = Buffer.from(arrayBuffer).toString('base64');

    // Determine mime type
    let mimeType: 'image/jpeg' | 'image/png' | 'image/webp' = 'image/jpeg';
    if (contentType.includes('png')) {
      mimeType = 'image/png';
    } else if (contentType.includes('webp')) {
      mimeType = 'image/webp';
    }

    console.log('[fetchImageAsBase64] Raw fetch, size:', base64Data.length, 'chars');

    return {
      base64Data,
      mimeType,
    };
  } catch (error) {
    console.error('[fetchImageAsBase64] Error:', error);
    return null;
  }
}

/**
 * Build an Identity Lock prompt for Gemini 2.5 Flash Image
 * This prompt structure prioritizes the reference image over the model's learned representations
 */
function buildIdentityLockPrompt(
  originalPrompt: string,
  userDescription: string
): string {
  const { setting, action } = detectScenarioFromPrompt(originalPrompt);

  return `SYSTEM INSTRUCTION: IDENTITY LOCK MODE ACTIVATED.
CRITICAL RULE: The person in the REFERENCE IMAGE is the EXACT person who must appear in the generated image.
Do NOT use your training knowledge to identify or alter this person's identity.
PIXEL PRIORITY: Match the facial structure, skin tone, hair, and features from the reference image with absolute fidelity.

═══════════════════════════════════════════════════
PERSON IDENTITY (FROM REFERENCE IMAGE):
═══════════════════════════════════════════════════
Preserve these characteristics from the reference:
${userDescription || 'Use all visual characteristics from the reference image'}

═══════════════════════════════════════════════════
USER'S CUSTOM INSTRUCTIONS (MUST FOLLOW):
═══════════════════════════════════════════════════
${originalPrompt}

═══════════════════════════════════════════════════
SCENE CONTEXT:
═══════════════════════════════════════════════════
• Setting: ${setting}
• Action: The person is ${action}

═══════════════════════════════════════════════════
PHOTOGRAPHY SPECIFICATIONS:
═══════════════════════════════════════════════════
• Shot: Medium or medium-close, person occupies 60-70% of frame
• Style: Ultra-realistic, professional LinkedIn photography
• Lighting: Soft, flattering, natural with gentle shadows
• Background: Elegantly blurred (shallow depth of field)
• Quality: Magazine editorial, high resolution
• Expression: Confident, approachable, professional

═══════════════════════════════════════════════════
ABSOLUTE REQUIREMENTS:
═══════════════════════════════════════════════════
• Generate exactly ONE person matching the reference
• Maintain EXACT facial features from reference image
• FOLLOW ALL CLOTHING/STYLE INSTRUCTIONS from user's custom instructions above
• Do NOT replace with any known public figure
• Do NOT alter ethnicity, skin tone, or distinctive features
• Natural pose appropriate for the setting`;
}

// ============================================
// IMAGE PROMPT BUILDING
// ============================================

/**
 * Detect scenario/setting from the original prompt
 */
function detectScenarioFromPrompt(prompt: string): { setting: string; action: string } {
  const scenario = prompt.toLowerCase();

  // Meeting / Team scenarios
  if (scenario.includes('reunião') || scenario.includes('meeting') || scenario.includes('equipe') || scenario.includes('team')) {
    return {
      setting: 'modern meeting room with glass walls and city skyline visible',
      action: 'leading a meeting, gesturing while explaining a concept'
    };
  }

  // Presentation / Stage scenarios
  if (scenario.includes('apresentação') || scenario.includes('presentation') || scenario.includes('palco') || scenario.includes('stage') || scenario.includes('palestra')) {
    return {
      setting: 'professional conference stage with soft spotlight',
      action: 'giving an inspiring presentation, confident posture, one hand gesturing'
    };
  }

  // Technology / Coding scenarios
  if (scenario.includes('tecnologia') || scenario.includes('tech') || scenario.includes('computador') || scenario.includes('code') || scenario.includes('programm') || scenario.includes('software')) {
    return {
      setting: 'modern tech workspace with multiple monitors showing code',
      action: 'focused on work, looking engaged and productive, slight smile'
    };
  }

  // Leadership / Executive scenarios
  if (scenario.includes('liderança') || scenario.includes('leadership') || scenario.includes('gestão') || scenario.includes('ceo') || scenario.includes('executive')) {
    return {
      setting: 'executive corner office with floor-to-ceiling windows and city view',
      action: 'standing confidently by the window, looking determined and thoughtful'
    };
  }

  // Networking / Coffee scenarios
  if (scenario.includes('café') || scenario.includes('coffee') || scenario.includes('networking') || scenario.includes('conexão') || scenario.includes('connect')) {
    return {
      setting: 'upscale coffee shop with warm ambient lighting',
      action: 'having an engaging conversation, warm genuine smile, relaxed posture'
    };
  }

  // Success / Achievement scenarios
  if (scenario.includes('sucesso') || scenario.includes('success') || scenario.includes('conquista') || scenario.includes('achievement') || scenario.includes('vitória')) {
    return {
      setting: 'modern office space with natural lighting and celebration atmosphere',
      action: 'celebrating a win with a genuine smile of satisfaction, arms slightly raised'
    };
  }

  // Innovation / Creativity scenarios
  if (scenario.includes('inovação') || scenario.includes('innovation') || scenario.includes('criativ') || scenario.includes('ideia') || scenario.includes('idea')) {
    return {
      setting: 'creative workspace with whiteboards full of ideas and post-its',
      action: 'brainstorming, looking inspired, pointing at ideas on whiteboard'
    };
  }

  // Mentoring / Teaching scenarios
  if (scenario.includes('mentor') || scenario.includes('coach') || scenario.includes('ensina') || scenario.includes('teach') || scenario.includes('orientação')) {
    return {
      setting: 'comfortable meeting space with warm lighting',
      action: 'mentoring, attentive and supportive expression, leaning in slightly'
    };
  }

  // Startup / Entrepreneurship scenarios
  if (scenario.includes('startup') || scenario.includes('empreend') || scenario.includes('entrepreneur') || scenario.includes('negócio')) {
    return {
      setting: 'dynamic startup office with open floor plan and modern furniture',
      action: 'working energetically, passionate expression, sleeves rolled up'
    };
  }

  // Default professional scenario
  return {
    setting: 'modern professional office environment with clean minimalist design',
    action: 'working confidently, approachable expression, professional demeanor'
  };
}

/**
 * Build an enhanced prompt that focuses on the user as the protagonist
 */
function buildPersonalizedImagePrompt(
  originalPrompt: string,
  userDescription: string
): string {
  const { setting, action } = detectScenarioFromPrompt(originalPrompt);

  return `CRITICAL INSTRUCTION: Generate an image with EXACTLY ONE PERSON as the clear protagonist. This person must match the description below.

═══════════════════════════════════════════════════
THE PERSON (MAIN SUBJECT - CENTER OF FRAME):
═══════════════════════════════════════════════════
${userDescription}

═══════════════════════════════════════════════════
SCENE COMPOSITION:
═══════════════════════════════════════════════════
• Setting: ${setting}
• Action: The person is ${action}
• Framing: Medium shot or medium-close shot
• Person occupies 60-70% of the frame
• Camera angle: Slightly below eye level (empowering perspective)
• Expression: Confident, approachable, genuine, professional

═══════════════════════════════════════════════════
PHOTOGRAPHY STYLE:
═══════════════════════════════════════════════════
• Ultra-realistic, high-end professional photography
• LinkedIn-appropriate, corporate but warm and human
• Soft, flattering lighting with gentle shadows
• Shallow depth of field, background elegantly blurred
• Color palette: warm, inviting, professional tones
• Magazine-quality editorial style
• Natural skin textures, no over-smoothing

═══════════════════════════════════════════════════
ABSOLUTELY MUST AVOID:
═══════════════════════════════════════════════════
• Multiple people in the image (ONLY ONE PERSON)
• Generic stock photo appearance
• Artificial or forced expressions
• Cluttered or distracting backgrounds
• Cartoon-like or low-quality rendering
• Overly dramatic lighting
• Visible logos or brand names

Original context: ${originalPrompt}`;
}

/**
 * Build a generic professional prompt when no user photos available
 * Generates contextual images related to the post content (not person photos)
 */
function buildGenericImagePrompt(originalPrompt: string): string {
  const { setting, action } = detectScenarioFromPrompt(originalPrompt);

  return `Generate a professional, visually striking image for a LinkedIn post.

CONTEXT: ${originalPrompt}

IMAGE REQUIREMENTS:
• Create a conceptual, abstract or symbolic representation of the theme
• Use modern, clean design aesthetics suitable for professional social media
• Include subtle visual metaphors related to: ${setting}
• Color palette: Professional blues, teals, or warm corporate colors
• Style: Modern corporate, tech-forward, inspirational
• NO text or words in the image
• NO human faces or people (use abstract shapes, objects, or landscapes instead)
• High resolution, magazine-quality visual
• Suitable for LinkedIn professional audience

VISUAL ELEMENTS TO CONSIDER:
• Abstract geometric shapes representing growth/success
• Modern workspace elements (without people)
• Technology and innovation symbols
• Nature metaphors (paths, mountains, horizons) for growth/journey themes
• Light and shadow for depth and professionalism

Create an inspiring, scroll-stopping image that complements professional content.`;
}

// ============================================
// IMAGE GENERATION
// ============================================

interface GenerateImageArgs {
  prompt: string;
  aspectRatio?: '1:1' | '4:5' | '16:9';
  userId?: string;
  userPhotos?: UserPhotoData[];
  referenceImages?: ReferenceImage[]; // For multimodal identity preservation
  useIdentityLock?: boolean; // Enable identity lock prompting
  baseImage?: ReferenceImage; // Previous generated image for editing/refinement
  isRefinement?: boolean; // If true, use baseImage as source for editing
}

export async function generateImage({
  prompt,
  aspectRatio = '4:5',
  userId,
  userPhotos,
  referenceImages,
  useIdentityLock = true, // Enable by default for identity preservation
  baseImage, // Previous image for editing
  isRefinement = false, // Whether this is a refinement/edit operation
}: GenerateImageArgs): Promise<GenerateImageResult> {
  console.log('[generateImage] Starting image generation...');
  console.log('[generateImage] Original prompt:', prompt.substring(0, 100) + '...');
  console.log('[generateImage] Is refinement:', isRefinement, '| Has base image:', !!baseImage);

  // Get user appearance description if we have photos
  let userDescription = '';
  let isPersonalized = false;
  let referenceImage: ReferenceImage | null = null;

  // Fetch photos if userId provided but photos not
  if (userId && !userPhotos) {
    console.log('[generateImage] Fetching user photos...');
    userPhotos = await getUserPhotos(userId);
    console.log('[generateImage] Found', userPhotos.length, 'photos');
  }

  // Process user photos to get appearance description AND reference image for identity lock
  if (userPhotos && userPhotos.length > 0) {
    const primaryPhoto = userPhotos.find(p => p.is_primary) || userPhotos[0];

    // Check for cached description first
    if (primaryPhoto.metadata?.appearance_description) {
      const cachedDescription = primaryPhoto.metadata.appearance_description;

      // Validate the cached description - it must describe a single person
      if (isValidSinglePersonDescription(cachedDescription)) {
        userDescription = cachedDescription;
        console.log('[generateImage] Using cached appearance description');
      } else {
        console.warn('[generateImage] Cached description is invalid (multiple people), re-analyzing photo...');
        // Clear invalid cache and re-analyze
        if (primaryPhoto.public_url) {
          userDescription = await analyzeUserPhoto(primaryPhoto.public_url);
          if (userDescription && primaryPhoto.id) {
            await cacheAppearanceDescription(primaryPhoto.id, primaryPhoto.metadata, userDescription);
            console.log('[generateImage] Updated cache with valid single-person description');
          }
        }
      }
    } else if (primaryPhoto.public_url) {
      // Analyze the photo to get appearance description
      console.log('[generateImage] Analyzing user photo...');
      userDescription = await analyzeUserPhoto(primaryPhoto.public_url);

      // Cache the description for future use
      if (userDescription && primaryPhoto.id) {
        await cacheAppearanceDescription(primaryPhoto.id, primaryPhoto.metadata, userDescription);
      }
    }

    // NEW: Fetch the actual photo as base64 for Gemini multimodal generation (Identity Lock)
    if (useIdentityLock && primaryPhoto.public_url) {
      console.log('[generateImage] Fetching reference image for identity lock...');
      referenceImage = await fetchImageAsBase64(primaryPhoto.public_url);
      if (referenceImage) {
        console.log('[generateImage] ✅ Reference image ready for identity lock');
      }
    }

    // Use provided reference images if available (override fetched one)
    if (referenceImages && referenceImages.length > 0) {
      referenceImage = referenceImages[0];
      console.log('[generateImage] Using provided reference image');
    }

    if (userDescription || referenceImage) {
      isPersonalized = true;
    }
  }

  // Build the final prompt - use identity lock prompt if we have a reference image
  let finalPrompt: string;

  if (referenceImage && userDescription) {
    // Best case: we have both reference image AND description
    finalPrompt = buildIdentityLockPrompt(prompt, userDescription);
    console.log('[generateImage] Using IDENTITY LOCK prompt with reference image');
  } else if (userDescription) {
    // Fallback: only text description (no reference image)
    finalPrompt = buildPersonalizedImagePrompt(prompt, userDescription);
    console.log('[generateImage] Using PERSONALIZED prompt with user description (no reference image)');
  } else {
    // No user photos - use generic prompt
    finalPrompt = buildGenericImagePrompt(prompt);
    console.log('[generateImage] Using GENERIC prompt (no user photos)');
  }

  // Call Vertex AI
  const location = process.env.VERTEX_LOCATION || DEFAULT_VERTEX_LOCATION;
  const modelName = process.env.VERTEX_IMAGE_MODEL || DEFAULT_VERTEX_IMAGE_MODEL;
  const projectId = getProjectId();

  console.log('[generateImage] Model:', modelName);
  console.log('[generateImage] Location:', location);
  console.log('[generateImage] Project:', projectId);
  console.log('[generateImage] Using reference image:', !!referenceImage);

  const vertexAuth = getVertexAuth();
  const client = await vertexAuth.getClient();
  const headers = await client.getRequestHeaders();

  let imageUrl: string;
  let responseData: any;

  // Check if using Gemini model (uses generateContent API) or Imagen (uses predict API)
  const isGeminiModel = modelName.includes('gemini');

  if (isGeminiModel) {
    // Use Gemini generateContent API with multimodal support
    const modelPath = `projects/${projectId}/locations/${location}/publishers/google/models/${modelName}`;

    // Build content parts - include reference image if available for identity lock
    const contentParts: any[] = [];

    // Add text prompt first
    contentParts.push({ text: finalPrompt });

    // Add base image if this is a refinement/edit operation
    if (isRefinement && baseImage) {
      contentParts.push({
        inlineData: {
          mimeType: baseImage.mimeType,
          data: baseImage.base64Data,
        },
      });
      contentParts.push({
        text: 'This is the CURRENT image. Apply the modifications described above to THIS image. Keep everything else the same, only change what was explicitly requested.'
      });
      console.log('[generateImage] Added base image for editing');
    }

    // Add reference image if available (for identity preservation) - but NOT in refinement mode
    // In refinement mode, the baseImage already contains the person
    if (referenceImage && !isRefinement) {
      contentParts.push({
        inlineData: {
          mimeType: referenceImage.mimeType,
          data: referenceImage.base64Data,
        },
      });
      // Add instruction to use the reference
      contentParts.push({
        text: 'Generate an image placing this EXACT person from the reference photo into the described scene. Maintain absolute facial fidelity.'
      });
    }

    const body = {
      contents: [
        {
          role: 'user',
          parts: contentParts,
        },
      ],
      generationConfig: {
        responseModalities: ['IMAGE', 'TEXT'],
        temperature: referenceImage ? 0.7 : 1, // Lower temperature for more faithful reproduction
        topP: 0.95,
        topK: 40,
      },
      safetySettings: [
        { category: 'HARM_CATEGORY_HARASSMENT', threshold: 'BLOCK_MEDIUM_AND_ABOVE' },
        { category: 'HARM_CATEGORY_HATE_SPEECH', threshold: 'BLOCK_MEDIUM_AND_ABOVE' },
        { category: 'HARM_CATEGORY_SEXUALLY_EXPLICIT', threshold: 'BLOCK_MEDIUM_AND_ABOVE' },
        { category: 'HARM_CATEGORY_DANGEROUS_CONTENT', threshold: 'BLOCK_MEDIUM_AND_ABOVE' },
      ],
    };

    console.log('[generateImage] Using Gemini generateContent API');

    // Retry logic for 429 errors
    const MAX_RETRIES = 2;
    const RETRY_DELAY_MS = 30000; // 30 seconds

    let lastError: Error | null = null;
    let response: Response | null = null;

    for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
      if (attempt > 0) {
        console.log(`[generateImage] Retry attempt ${attempt}/${MAX_RETRIES} after 429 error, waiting ${RETRY_DELAY_MS / 1000}s...`);
        await new Promise(resolve => setTimeout(resolve, RETRY_DELAY_MS));
      }

      response = await fetch(
        `https://${location}-aiplatform.googleapis.com/v1/${modelPath}:generateContent`,
        {
          method: 'POST',
          headers: {
            ...headers,
            'Content-Type': 'application/json',
            'x-goog-user-project': projectId,
          },
          body: JSON.stringify(body),
        },
      );

      if (response.ok) {
        break; // Success!
      }

      // Check if it's a 429 rate limit error
      if (response.status === 429 && attempt < MAX_RETRIES) {
        console.log(`[generateImage] Got 429 rate limit, will retry...`);
        lastError = new Error(`Rate limited (attempt ${attempt + 1})`);
        continue; // Retry
      }

      // For other errors or final 429, throw
      const errorText = await response.text();
      console.error('[generateImage] Gemini API error:', errorText);
      throw new Error(`Gemini image request failed: ${response.status} ${errorText}`);
    }

    if (!response || !response.ok) {
      throw lastError || new Error('Failed after all retries');
    }

    responseData = await response.json();

    // Extract image from Gemini response
    const candidate = responseData?.candidates?.[0];
    const parts = candidate?.content?.parts || [];
    const imagePart = parts.find((p: any) => p.inlineData?.data);

    if (!imagePart?.inlineData?.data) {
      console.error('[generateImage] Gemini response:', JSON.stringify(responseData, null, 2));
      throw new Error('Gemini response missing image data');
    }

    const mimeType = imagePart.inlineData.mimeType || 'image/png';
    imageUrl = `data:${mimeType};base64,${imagePart.inlineData.data}`;

  } else {
    // Use Imagen predict API
    const modelPath = `projects/${projectId}/locations/${location}/publishers/google/models/${modelName}`;

    const body = {
      instances: [
        {
          prompt: finalPrompt,
        },
      ],
      parameters: {
        sampleCount: 1,
        aspectRatio: aspectRatio,
        safetyFilterLevel: 'block_some',
        personGeneration: 'allow_adult',
      },
    };

    console.log('[generateImage] Using Imagen predict API');

    const response = await fetch(
      `https://${location}-aiplatform.googleapis.com/v1/${modelPath}:predict`,
      {
        method: 'POST',
        headers: {
          ...headers,
          'Content-Type': 'application/json',
          'x-goog-user-project': projectId,
        },
        body: JSON.stringify(body),
      },
    );

    if (!response.ok) {
      const errorText = await response.text();
      console.error('[generateImage] Imagen API error:', errorText);
      throw new Error(`Imagen request failed: ${response.status} ${errorText}`);
    }

    responseData = await response.json();

    // Extract image from Imagen response
    const predictions = responseData?.predictions;
    if (!predictions || predictions.length === 0) {
      throw new Error('Imagen response missing predictions');
    }

    const imageBytes = predictions[0]?.bytesBase64Encoded;
    if (!imageBytes) {
      throw new Error('Imagen response missing image data');
    }

    imageUrl = `data:image/png;base64,${imageBytes}`;
  }

  console.log('[generateImage] ✅ Image generated successfully');
  console.log('[generateImage] Personalized:', isPersonalized);

  return {
    imageUrl,
    metadata: {
      ...responseData,
      isPersonalized,
      modelUsed: modelName,
      promptUsed: finalPrompt.substring(0, 500) + '...',
    },
    isPersonalized,
  };
}
