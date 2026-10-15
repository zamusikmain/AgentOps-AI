import './globals.css';
export const metadata = {title: 'AgentOps AI', description: 'AI agent orchestration workspace'};
export default function Layout({children}: Readonly<{children: React.ReactNode}>) {
  return <html lang="ru" suppressHydrationWarning><body>{children}</body></html>;
}
