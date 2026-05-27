/**
 * Image Optimization Utilities
 * Uses Sharp for efficient image processing
 */

import sharp from 'sharp';

// Configuration for different image types
export const IMAGE_CONFIG = {
    // User reference photos for AI identity preservation
    userPhoto: {
        maxWidth: 1024,
        maxHeight: 1024,
        quality: 85,
        format: 'webp' as const,
    },
    // Generated images for display
    generated: {
        maxWidth: 2048,
        maxHeight: 2048,
        quality: 90,
        format: 'webp' as const,
    },
    // Archived images after refinement
    archived: {
        maxWidth: 800,
        maxHeight: 800,
        quality: 75,
        format: 'webp' as const,
    },
    // Images prepared for AI API calls (reduce token usage)
    forAI: {
        maxWidth: 1024,
        maxHeight: 1024,
        quality: 80,
        format: 'jpeg' as const,
    },
};

export interface OptimizeOptions {
    maxWidth?: number;
    maxHeight?: number;
    quality?: number;
    format?: 'webp' | 'jpeg' | 'png';
}

export interface OptimizeResult {
    buffer: Buffer;
    mimeType: string;
    width: number;
    height: number;
    originalSize: number;
    optimizedSize: number;
    compressionRatio: number;
}

/**
 * Optimize an image buffer with the given options
 */
export async function optimizeImage(
    input: Buffer | ArrayBuffer,
    options: OptimizeOptions = {}
): Promise<OptimizeResult> {
    const {
        maxWidth = 1024,
        maxHeight = 1024,
        quality = 85,
        format = 'webp',
    } = options;

    const inputBuffer = input instanceof Buffer ? input : Buffer.from(new Uint8Array(input));
    const originalSize = inputBuffer.length;

    // Get original image metadata
    const metadata = await sharp(inputBuffer).metadata();

    // Calculate new dimensions while maintaining aspect ratio
    let width = metadata.width || maxWidth;
    let height = metadata.height || maxHeight;

    if (width > maxWidth || height > maxHeight) {
        const ratio = Math.min(maxWidth / width, maxHeight / height);
        width = Math.round(width * ratio);
        height = Math.round(height * ratio);
    }

    // Process the image
    let processor = sharp(inputBuffer)
        .resize(width, height, {
            fit: 'inside',
            withoutEnlargement: true,
        });

    // Apply format-specific compression
    let mimeType: string;
    switch (format) {
        case 'webp':
            processor = processor.webp({ quality });
            mimeType = 'image/webp';
            break;
        case 'jpeg':
            processor = processor.jpeg({ quality, mozjpeg: true });
            mimeType = 'image/jpeg';
            break;
        case 'png':
            processor = processor.png({ compressionLevel: 9 });
            mimeType = 'image/png';
            break;
        default:
            processor = processor.webp({ quality });
            mimeType = 'image/webp';
    }

    const outputBuffer = await processor.toBuffer();
    const optimizedSize = outputBuffer.length;

    console.log(
        `[optimizeImage] ${format.toUpperCase()} | ` +
        `${Math.round(originalSize / 1024)}KB → ${Math.round(optimizedSize / 1024)}KB | ` +
        `${width}x${height} | ` +
        `${Math.round((1 - optimizedSize / originalSize) * 100)}% reduction`
    );

    return {
        buffer: outputBuffer,
        mimeType,
        width,
        height,
        originalSize,
        optimizedSize,
        compressionRatio: originalSize / optimizedSize,
    };
}

/**
 * Optimize user reference photo for storage and AI usage
 */
export async function optimizeUserPhoto(input: Buffer | ArrayBuffer): Promise<OptimizeResult> {
    return optimizeImage(input, IMAGE_CONFIG.userPhoto);
}

/**
 * Optimize image for AI API calls (reduce tokens)
 */
export async function optimizeForAI(input: Buffer | ArrayBuffer): Promise<OptimizeResult> {
    return optimizeImage(input, IMAGE_CONFIG.forAI);
}

/**
 * Optimize image for archival (after refinement)
 */
export async function optimizeForArchive(input: Buffer | ArrayBuffer): Promise<OptimizeResult> {
    return optimizeImage(input, IMAGE_CONFIG.archived);
}

/**
 * Convert base64 image data to optimized buffer
 */
export async function optimizeBase64Image(
    base64Data: string,
    options: OptimizeOptions = IMAGE_CONFIG.forAI
): Promise<{ base64: string; mimeType: string; size: number }> {
    const buffer = Buffer.from(base64Data, 'base64');
    const result = await optimizeImage(buffer, options);

    return {
        base64: result.buffer.toString('base64'),
        mimeType: result.mimeType,
        size: result.optimizedSize,
    };
}

/**
 * Fetch image from URL and optimize it
 */
export async function fetchAndOptimize(
    imageUrl: string,
    options: OptimizeOptions = IMAGE_CONFIG.forAI
): Promise<{
    buffer: Buffer;
    base64: string;
    mimeType: string;
    originalSize: number;
    optimizedSize: number;
} | null> {
    try {
        console.log('[fetchAndOptimize] Fetching:', imageUrl.substring(0, 80) + '...');

        const response = await fetch(imageUrl);
        if (!response.ok) {
            console.error('[fetchAndOptimize] Failed to fetch:', response.status);
            return null;
        }

        const arrayBuffer = await response.arrayBuffer();
        const result = await optimizeImage(arrayBuffer, options);

        return {
            buffer: result.buffer,
            base64: result.buffer.toString('base64'),
            mimeType: result.mimeType,
            originalSize: result.originalSize,
            optimizedSize: result.optimizedSize,
        };
    } catch (error) {
        console.error('[fetchAndOptimize] Error:', error);
        return null;
    }
}
