import { Component } from 'react';
import type { ErrorInfo, ReactNode } from 'react';

export default class ErrorBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  componentDidCatch(error: Error, info: ErrorInfo) { console.error('Workspace error', error, info.componentStack); }
  render() {
    if (this.state.failed) return <div role="alert" className="mx-auto max-w-lg space-y-4 p-10 text-center text-slate-300"><h1 className="text-xl">The workspace could not load</h1><p>Reload the page to try again.</p><button className="research-button" onClick={() => window.location.reload()}>Reload workspace</button></div>;
    return this.props.children;
  }
}
