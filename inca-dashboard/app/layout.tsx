import type { Metadata } from 'next'
import { Syne, Inter } from 'next/font/google'
import './globals.css'

const syne = Syne({ subsets: ['latin'], weight: ['600', '700'], variable: '--font-syne' })
const inter = Inter({ subsets: ['latin'], weight: ['400', '500'], variable: '--font-inter' })

export const metadata: Metadata = {
  title: 'INCA Claims Dashboard',
  description: 'Insurance claims management',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" className={`${syne.variable} ${inter.variable}`}>
      <body style={{ margin: 0, background: '#F9F7F7' }} suppressHydrationWarning>
        {children}
      </body>
    </html>
  )
}
