import type { ReactNode } from 'react';
import './globals.css';
import Navbar from '@/components/Navbar';

export const metadata = {
  title: 'LinkedIn Agent',
  description:
    'An AI agent that plans, analyzes, and self-heals LinkedIn content strategy.',
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet" />
      </head>
      <body className="min-h-screen bg-neutral-50 text-neutral-900 antialiased">
        <Navbar />
        <main className="animate-fadeIn">
          {children}
        </main>
      </body>
    </html>
  );
}


