'use client';

import { useState, useRef, useCallback } from 'react';

interface ImageUploadModalProps {
    open: boolean;
    postId: string | null;
    onClose: () => void;
    onUpload: (postId: string, file: File) => Promise<void>;
    uploading: boolean;
}

const MAX_FILE_SIZE = 5 * 1024 * 1024; // 5MB in bytes

export default function ImageUploadModal({
    open,
    postId,
    onClose,
    onUpload,
    uploading,
}: ImageUploadModalProps) {
    const [dragOver, setDragOver] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [selectedFile, setSelectedFile] = useState<{ file: File; preview: string } | null>(null);
    const fileInputRef = useRef<HTMLInputElement>(null);

    const validateFile = (file: File): string | null => {
        // Check file type
        if (!file.type.startsWith('image/')) {
            return 'Apenas arquivos de imagem são permitidos';
        }

        // Check file size
        if (file.size > MAX_FILE_SIZE) {
            return `Tamanho máximo permitido: 5MB. Seu arquivo tem ${(file.size / (1024 * 1024)).toFixed(2)}MB`;
        }

        return null;
    };

    const handleFile = useCallback((file: File) => {
        setError(null);

        const validationError = validateFile(file);
        if (validationError) {
            setError(validationError);
            return;
        }

        // Create preview
        const reader = new FileReader();
        reader.onload = (e) => {
            setSelectedFile({
                file,
                preview: e.target?.result as string,
            });
        };
        reader.readAsDataURL(file);
    }, []);

    const handleDrop = useCallback((e: React.DragEvent) => {
        e.preventDefault();
        setDragOver(false);

        const files = e.dataTransfer.files;
        if (files && files.length > 0) {
            handleFile(files[0]);
        }
    }, [handleFile]);

    const handleDragOver = useCallback((e: React.DragEvent) => {
        e.preventDefault();
        setDragOver(true);
    }, []);

    const handleDragLeave = useCallback((e: React.DragEvent) => {
        e.preventDefault();
        setDragOver(false);
    }, []);

    const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const files = e.target.files;
        if (files && files.length > 0) {
            handleFile(files[0]);
        }
    };

    const handleUploadClick = async () => {
        if (!selectedFile || !postId) return;

        try {
            await onUpload(postId, selectedFile.file);
            handleClose();
        } catch (error) {
            // Error is handled by the parent
        }
    };

    const handleClose = () => {
        setSelectedFile(null);
        setError(null);
        setDragOver(false);
        if (fileInputRef.current) {
            fileInputRef.current.value = '';
        }
        onClose();
    };

    if (!open) return null;

    return (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
            <div className="bg-white rounded-2xl w-full max-w-lg overflow-hidden animate-fadeIn">
                {/* Header */}
                <div className="px-6 py-4 border-b border-neutral-100 flex justify-between items-center">
                    <div>
                        <h2 className="text-lg font-semibold text-neutral-900">Enviar Imagem</h2>
                        <p className="text-xs text-neutral-500 mt-0.5">
                            Arraste uma imagem ou clique para selecionar
                        </p>
                    </div>
                    <button
                        onClick={handleClose}
                        disabled={uploading}
                        className="w-8 h-8 rounded-full bg-neutral-100 hover:bg-neutral-200 flex items-center justify-center text-neutral-500 hover:text-neutral-700 transition-colors disabled:opacity-50"
                    >
                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                        </svg>
                    </button>
                </div>

                {/* Body */}
                <div className="p-6">
                    {/* Drag and Drop Zone */}
                    <div
                        onDrop={handleDrop}
                        onDragOver={handleDragOver}
                        onDragLeave={handleDragLeave}
                        onClick={() => !uploading && fileInputRef.current?.click()}
                        className={`
              relative border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-all
              ${dragOver ? 'border-violet-400 bg-violet-50' : 'border-neutral-300 hover:border-neutral-400 hover:bg-neutral-50'}
              ${uploading ? 'opacity-50 cursor-not-allowed' : ''}
            `}
                    >
                        <input
                            ref={fileInputRef}
                            type="file"
                            accept="image/*"
                            onChange={handleInputChange}
                            className="hidden"
                            disabled={uploading}
                        />

                        {selectedFile ? (
                            <div className="space-y-4">
                                <div className="relative w-40 h-40 mx-auto rounded-lg overflow-hidden shadow-md">
                                    <img
                                        src={selectedFile.preview}
                                        alt="Preview"
                                        className="w-full h-full object-cover"
                                    />
                                </div>
                                <div className="text-sm text-neutral-600">
                                    <p className="font-medium truncate">{selectedFile.file.name}</p>
                                    <p className="text-xs text-neutral-400">
                                        {(selectedFile.file.size / (1024 * 1024)).toFixed(2)} MB
                                    </p>
                                </div>
                                <button
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        setSelectedFile(null);
                                        if (fileInputRef.current) fileInputRef.current.value = '';
                                    }}
                                    className="text-xs text-rose-600 hover:text-rose-700"
                                >
                                    Remover e selecionar outra
                                </button>
                            </div>
                        ) : (
                            <>
                                <div className="w-16 h-16 bg-neutral-100 rounded-2xl flex items-center justify-center mx-auto mb-4">
                                    <svg className="w-8 h-8 text-neutral-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                                    </svg>
                                </div>
                                <p className="text-sm text-neutral-600 mb-2">
                                    <span className="font-medium text-violet-600">Clique aqui</span> ou arraste uma imagem
                                </p>
                                <p className="text-xs text-neutral-400">
                                    PNG, JPG ou WEBP • Máximo <span className="font-medium text-amber-600">5 MB</span>
                                </p>
                            </>
                        )}
                    </div>

                    {/* Error Message */}
                    {error && (
                        <div className="mt-4 p-3 rounded-lg bg-rose-50 border border-rose-200 flex items-start gap-2">
                            <svg className="w-5 h-5 text-rose-500 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                            </svg>
                            <p className="text-sm text-rose-700">{error}</p>
                        </div>
                    )}

                    {/* Info Message */}
                    <div className="mt-4 p-3 rounded-lg bg-amber-50 border border-amber-200 flex items-start gap-2">
                        <svg className="w-5 h-5 text-amber-500 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                        </svg>
                        <p className="text-xs text-amber-700">
                            Esta imagem substituirá a imagem gerada pela IA para este post.
                        </p>
                    </div>
                </div>

                {/* Footer */}
                <div className="px-6 py-4 border-t border-neutral-100 flex justify-end gap-3">
                    <button
                        onClick={handleClose}
                        disabled={uploading}
                        className="px-4 py-2 rounded-lg bg-neutral-100 hover:bg-neutral-200 text-neutral-700 text-sm font-medium transition-colors disabled:opacity-50"
                    >
                        Cancelar
                    </button>
                    <button
                        onClick={handleUploadClick}
                        disabled={!selectedFile || uploading}
                        className="px-5 py-2 rounded-lg bg-violet-600 hover:bg-violet-700 disabled:bg-neutral-300 text-white text-sm font-medium transition-colors flex items-center gap-2"
                    >
                        {uploading ? (
                            <>
                                <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
                                Enviando...
                            </>
                        ) : (
                            <>
                                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
                                </svg>
                                Enviar Imagem
                            </>
                        )}
                    </button>
                </div>
            </div>
        </div>
    );
}
