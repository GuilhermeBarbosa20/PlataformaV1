/**
 * Google Cloud Authentication Helper
 * 
 * Supports two modes:
 * 1. JSON file path via GOOGLE_APPLICATION_CREDENTIALS (development)
 * 2. Base64 encoded JSON via GOOGLE_CREDENTIALS_BASE64 (production/cloud)
 * 
 * For production:
 * - Convert your service account JSON to base64: base64 -w 0 service-account.json
 * - Set the GOOGLE_CREDENTIALS_BASE64 environment variable with the result
 */

import { GoogleAuth, GoogleAuthOptions } from 'google-auth-library';
import * as fs from 'fs';
import * as path from 'path';

const VERTEX_SCOPE = 'https://www.googleapis.com/auth/cloud-platform';

interface ServiceAccountCredentials {
  type: string;
  project_id: string;
  private_key_id: string;
  private_key: string;
  client_email: string;
  client_id: string;
  auth_uri: string;
  token_uri: string;
  auth_provider_x509_cert_url: string;
  client_x509_cert_url: string;
  universe_domain?: string;
}

let cachedCredentials: ServiceAccountCredentials | null = null;
let cachedAuth: GoogleAuth | null = null;

/**
 * Get service account credentials from environment
 */
export function getServiceAccountCredentials(): ServiceAccountCredentials {
  if (cachedCredentials) {
    return cachedCredentials;
  }

  // Priority 1: Base64 encoded credentials (recommended for production)
  const base64Creds = process.env.GOOGLE_CREDENTIALS_BASE64;
  if (base64Creds) {
    try {
      const decoded = Buffer.from(base64Creds, 'base64').toString('utf-8');
      cachedCredentials = JSON.parse(decoded) as ServiceAccountCredentials;
      console.log('[GoogleAuth] Using credentials from GOOGLE_CREDENTIALS_BASE64');
      return cachedCredentials;
    } catch (error) {
      console.error('[GoogleAuth] Failed to parse GOOGLE_CREDENTIALS_BASE64:', error);
      throw new Error('Invalid GOOGLE_CREDENTIALS_BASE64 format');
    }
  }

  // Priority 2: Individual environment variables
  const privateKey = process.env.GOOGLE_PRIVATE_KEY;
  const clientEmail = process.env.GOOGLE_CLIENT_EMAIL;
  const projectId = process.env.VERTEX_PROJECT_ID || process.env.GOOGLE_PROJECT_ID;
  
  if (privateKey && clientEmail && projectId) {
    cachedCredentials = {
      type: 'service_account',
      project_id: projectId,
      private_key_id: process.env.GOOGLE_PRIVATE_KEY_ID || '',
      private_key: privateKey.replace(/\\n/g, '\n'), // Handle escaped newlines
      client_email: clientEmail,
      client_id: process.env.GOOGLE_CLIENT_ID || '',
      auth_uri: 'https://accounts.google.com/o/oauth2/auth',
      token_uri: 'https://oauth2.googleapis.com/token',
      auth_provider_x509_cert_url: 'https://www.googleapis.com/oauth2/v1/certs',
      client_x509_cert_url: `https://www.googleapis.com/robot/v1/metadata/x509/${encodeURIComponent(clientEmail)}`,
    };
    console.log('[GoogleAuth] Using credentials from individual env vars');
    return cachedCredentials;
  }

  // Priority 3: JSON file path (development only)
  const credentialsPath = process.env.GOOGLE_APPLICATION_CREDENTIALS;
  if (credentialsPath) {
    try {
      const absolutePath = path.isAbsolute(credentialsPath) 
        ? credentialsPath 
        : path.join(process.cwd(), credentialsPath);
      
      if (fs.existsSync(absolutePath)) {
        const fileContent = fs.readFileSync(absolutePath, 'utf-8');
        cachedCredentials = JSON.parse(fileContent) as ServiceAccountCredentials;
        console.log('[GoogleAuth] Using credentials from GOOGLE_APPLICATION_CREDENTIALS file');
        return cachedCredentials;
      }
    } catch (error) {
      console.error('[GoogleAuth] Failed to read credentials file:', error);
    }
  }

  throw new Error(
    'Google Cloud credentials not configured. Set one of:\n' +
    '1. GOOGLE_CREDENTIALS_BASE64 (recommended for production)\n' +
    '2. GOOGLE_PRIVATE_KEY + GOOGLE_CLIENT_EMAIL + VERTEX_PROJECT_ID\n' +
    '3. GOOGLE_APPLICATION_CREDENTIALS (path to JSON file, development only)'
  );
}

/**
 * Get a configured GoogleAuth instance
 */
export function getGoogleAuth(): GoogleAuth {
  if (cachedAuth) {
    return cachedAuth;
  }

  const credentials = getServiceAccountCredentials();
  
  const authOptions: GoogleAuthOptions = {
    scopes: [VERTEX_SCOPE],
    credentials: {
      client_email: credentials.client_email,
      private_key: credentials.private_key,
    },
    projectId: credentials.project_id,
  };

  cachedAuth = new GoogleAuth(authOptions);
  return cachedAuth;
}

/**
 * Get the project ID from credentials
 */
export function getProjectId(): string {
  const envProjectId = process.env.VERTEX_PROJECT_ID || process.env.GOOGLE_PROJECT_ID;
  if (envProjectId) {
    return envProjectId;
  }
  
  try {
    const credentials = getServiceAccountCredentials();
    return credentials.project_id;
  } catch {
    throw new Error('Google Cloud project ID not configured');
  }
}

/**
 * Helper to convert JSON credentials file to base64
 * Usage: node -e "console.log(require('./src/lib/google-auth').convertToBase64('./service-account.json'))"
 */
export function convertToBase64(filePath: string): string {
  const absolutePath = path.isAbsolute(filePath) 
    ? filePath 
    : path.join(process.cwd(), filePath);
  
  const fileContent = fs.readFileSync(absolutePath, 'utf-8');
  // Validate it's valid JSON first
  JSON.parse(fileContent);
  return Buffer.from(fileContent).toString('base64');
}

/**
 * Validate that Google Cloud credentials are properly configured
 */
export async function validateGoogleCredentials(): Promise<{
  valid: boolean;
  projectId?: string;
  clientEmail?: string;
  error?: string;
}> {
  try {
    const credentials = getServiceAccountCredentials();
    const auth = getGoogleAuth();
    
    // Try to get an access token to validate credentials
    const client = await auth.getClient();
    await client.getAccessToken();
    
    return {
      valid: true,
      projectId: credentials.project_id,
      clientEmail: credentials.client_email,
    };
  } catch (error: any) {
    return {
      valid: false,
      error: error.message || 'Unknown error validating credentials',
    };
  }
}
