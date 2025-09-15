import React, { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card } from '@/components/ui/card';
import { Send, Loader2 } from 'lucide-react';
import { useToast } from '@/hooks/use-toast';
import ReactMarkdown from 'react-markdown';

const ChatInterface = () => {
  const [query, setQuery] = useState('');
  const [response, setResponse] = useState<string | null>(null);
  const [streamingResponse, setStreamingResponse] = useState<string>('');
  const [isLoading, setIsLoading] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const { toast } = useToast();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;

    setIsLoading(true);
    setIsStreaming(true);
    setResponse(null);
    setStreamingResponse('');

    try {
      const res = await fetch("http://localhost:8000/query/stream", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ query }),
});

const reader = res.body?.getReader();
if (!reader) throw new Error("No reader available");

setIsLoading(false);
setIsStreaming(true);

const decoder = new TextDecoder();

while (true) {
  const { done, value } = await reader.read();
  if (done) break;

  const chunk = decoder.decode(value, { stream: true }).trim();
  const lines = chunk.split("\n");

  for (const line of lines) {
    if (line.startsWith("data: ")) {
      const data = line.replace("data: ", "");

      if (data === "[DONE]") {
        setIsStreaming(false);
        setResponse(streamingResponse);
        
        return;
      }

      try {
        const parsed = JSON.parse(data);
        if (parsed.content) {
          setStreamingResponse((prev) => prev + parsed.content);
        }
      } catch {
        console.warn("Non-JSON SSE message:", data);
      }
    }
  }
}

    } catch (error) {
      console.error('Error querying API:', error);
      setIsStreaming(false);
      setIsLoading(false);
      toast({
        title: 'Error',
        description: 'Failed to get response. Please try again.',
        variant: 'destructive',
      });
    }
  };

  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-4 relative">
      {/* Background decoration */}
      <div className="absolute inset-0 bg-gradient-to-br from-background via-background to-muted/20 -z-10" />
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-primary/5 via-background to-background -z-10" />
      
      <div className="w-full max-w-4xl mx-auto relative z-10">
        {/* Header */}
        <div className="text-center mb-8 animate-in fade-in-50 slide-in-from-bottom-4 duration-1000">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-gradient-primary rounded-2xl mb-4 shadow-elegant">
            <svg className="w-8 h-8 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
            </svg>
          </div>
          <h1 className="text-4xl font-bold bg-gradient-primary bg-clip-text text-transparent mb-3">
            AI Knowledge Assistant
          </h1>
          <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
            Get instant, intelligent answers to your domain-specific questions with our advanced AI assistant
          </p>
        </div>

        {/* Chat Container */}
        <Card className="bg-card/50 backdrop-blur-xl border border-border/20 shadow-elegant hover:shadow-glow transition-all duration-300 animate-in fade-in-30 slide-in-from-bottom-6 duration-1000 delay-200">
          <div className="p-8">
            {/* Input Form */}
            <form onSubmit={handleSubmit} className="mb-6">
              <div className="flex gap-3">
                <Input
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Ask me anything about your domain..."
                  disabled={isLoading || isStreaming}
                  className="flex-1 bg-background/50 border-border/30 focus:border-primary transition-all duration-300 text-base py-3"
                />
                <Button 
                  type="submit" 
                  disabled={isLoading || isStreaming || !query.trim()}
                  className="bg-gradient-primary hover:bg-gradient-primary/90 text-white px-8 py-3 shadow-elegant hover:shadow-glow transition-all duration-300 hover:scale-105"
                >
                  {(isLoading || isStreaming) ? (
                    <Loader2 className="h-5 w-5 animate-spin" />
                  ) : (
                    <Send className="h-5 w-5" />
                  )}
                </Button>
              </div>
            </form>

            {/* Response Display */}
            {(response || streamingResponse) && (
              <div className="bg-background/30 backdrop-blur-sm border border-border/20 rounded-xl p-8 animate-in fade-in-50 slide-in-from-bottom-4 duration-500">
                {/* Show streaming response while streaming */}
                {isStreaming && streamingResponse && (
                  <div className="text-muted-foreground leading-relaxed whitespace-pre-wrap font-mono text-sm">
                    {streamingResponse}
                    <span className="animate-pulse">|</span>
                  </div>
                )}
                
                {/* Show formatted markdown response when streaming is complete */}
                {!isStreaming && response && (
                  <div className="prose prose-slate max-w-none dark:prose-invert prose-headings:text-foreground prose-p:text-muted-foreground prose-strong:text-foreground prose-a:text-primary">
                    <ReactMarkdown
                      components={{
                        h1: ({ children }) => (
                          <h1 className="text-3xl font-bold text-foreground mb-6 leading-tight">{children}</h1>
                        ),
                        h2: ({ children }) => (
                          <h2 className="text-2xl font-semibold text-foreground mb-4 mt-8 leading-tight">{children}</h2>
                        ),
                        h3: ({ children }) => (
                          <h3 className="text-xl font-semibold text-foreground mb-3 mt-6 leading-tight">{children}</h3>
                        ),
                        p: ({ children }) => (
                          <p className="text-muted-foreground mb-4 leading-relaxed text-base">{children}</p>
                        ),
                        ul: ({ children }) => (
                          <ul className="list-disc list-inside text-muted-foreground mb-6 space-y-2 pl-4">{children}</ul>
                        ),
                        ol: ({ children }) => (
                          <ol className="list-decimal list-inside text-muted-foreground mb-6 space-y-2 pl-4">{children}</ol>
                        ),
                        li: ({ children }) => (
                          <li className="text-muted-foreground leading-relaxed">{children}</li>
                        ),
                        strong: ({ children }) => (
                          <strong className="font-semibold text-foreground">{children}</strong>
                        ),
                        a: ({ href, children }) => (
                          <a 
                            href={href} 
                            className="text-primary hover:text-primary/80 underline underline-offset-2 transition-colors font-medium"
                            target="_blank"
                            rel="noopener noreferrer"
                          >
                            {children}
                          </a>
                        ),
                      }}
                    >
                      {response}
                    </ReactMarkdown>
                  </div>
                )}
              </div>
            )}

            {/* Loading State */}
            {isLoading && (
              <div className="flex items-center justify-center py-12 animate-in fade-in-50 duration-300">
                <div className="flex items-center gap-4 text-muted-foreground">
                  <div className="relative">
                    <Loader2 className="h-6 w-6 animate-spin text-primary" />
                    <div className="absolute inset-0 h-6 w-6 animate-ping rounded-full bg-primary/20"></div>
                  </div>
                  <span className="text-lg">Generating your answer...</span>
                </div>
              </div>
            )}

            {/* Empty State */}
            {!response && !streamingResponse && !isLoading && !isStreaming && (
              <div className="text-center py-16 animate-in fade-in-50 slide-in-from-bottom-4 duration-700 delay-400">
                <div className="w-20 h-20 bg-gradient-primary rounded-3xl flex items-center justify-center mx-auto mb-6 shadow-elegant">
                  <svg 
                    className="w-10 h-10 text-white" 
                    fill="none" 
                    stroke="currentColor" 
                    viewBox="0 0 24 24"
                  >
                    <path 
                      strokeLinecap="round" 
                      strokeLinejoin="round" 
                      strokeWidth={2} 
                      d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" 
                    />
                  </svg>
                </div>
                <p className="text-muted-foreground text-lg max-w-md mx-auto leading-relaxed">
                  Ready to help! Ask me anything about your business domain or specific knowledge base.
                </p>
              </div>
            )}
          </div>
        </Card>

        {/* Footer */}
        <div className="text-center mt-8 animate-in fade-in-50 slide-in-from-bottom-4 duration-1000 delay-600">
          <p className="text-sm text-muted-foreground/70">
            Powered by Advanced AI • Intelligent Knowledge Assistant
          </p>
        </div>
      </div>
    </div>
  );
};

export default ChatInterface;