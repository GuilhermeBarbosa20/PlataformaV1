'use client';

import { useEffect } from 'react';

export function LinkedInCookieExtractor() {
  useEffect(() => {
    const extractAndStoreCookie = async () => {
      try {
        // Obtém todos os cookies do document
        const cookies = document.cookie.split('; ');
        
        // Procura pelo cookie li_at
        const liAtCookie = cookies.find(c => c.startsWith('li_at='));
        
        if (liAtCookie) {
          const cookieValue = liAtCookie.split('=')[1];
          
          // Envia para a API para salvar no banco
          const response = await fetch('/api/auth/store-linkedin-cookie', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
              liAtCookie: cookieValue,
            }),
          });

          if (response.ok) {
            console.log('✅ Cookie li_at capturado e armazenado!');
          } else {
            console.warn('⚠️ Falha ao armazenar cookie');
          }
        } else {
          console.log('⚠️ Cookie li_at não encontrado no browser');
        }
      } catch (error) {
        console.error('Erro ao extrair cookie:', error);
      }
    };

    // Aguarda um pouco para o cookie ser setado
    const timer = setTimeout(extractAndStoreCookie, 2000);
    
    return () => clearTimeout(timer);
  }, []);

  return null; // Component não renderiza nada
}
