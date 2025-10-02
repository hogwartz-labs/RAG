import React, { useEffect, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card } from '@/components/ui/card';
import { Send, Loader2 } from 'lucide-react';
import { useToast } from '@/hooks/use-toast';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {fetchWithTimeout} from '@/services/services'
const ChatInterface = () => {
  const [companyId, setCompanyId] = useState(null);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const cid = params.get('companyId');

    if (!cid) {
      alert('Company ID is required in the URL as a query parameter, e.g., ?companyId=your_company_id');
      // donot render anything in this page.. just show the error api key is not present. contanct admin
      setCompanyId(null);
      return;
    } else {
      setCompanyId(cid);
    }
  }, []);

  const [query, setQuery] = useState('');
  const [currentResponse, setCurrentResponse] = useState<string>('');
  const [isLoading, setIsLoading] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const { toast } = useToast();

  const handleSubmit = async () => {
    if (!query.trim()) return;

    setIsLoading(true);
    setIsStreaming(false);
    setCurrentResponse(''); // Clear previous response

    try {
      const res = await fetchWithTimeout("https://hogwatrz-1.eastus.cloudapp.azure.com/query/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json",
          "x-api-key": companyId 
        },
        body: JSON.stringify({ query }),
      });
      if (!res.ok) {
        toast({
          title: 'Error',
          description: `Failed to get response: ${res.statusText} with error code ${res.status}`,
          variant: 'destructive',
        });
      }

      const reader = res.body?.getReader();
      if (!reader) throw new Error("No reader available");

      setIsLoading(false);
      setIsStreaming(true);

      const decoder = new TextDecoder();
      let accumulatedResponse = '';

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
              setQuery('')
              return;
            }

            try {
              const parsed = JSON.parse(data);
              if (parsed.content) {
                accumulatedResponse += parsed.content;
                setCurrentResponse(accumulatedResponse);
              }
            } catch {
              console.warn("Non-JSON SSE message:", data);
            }
          }
        }
      }

    } catch (error) {
      if (error.name === 'AbortError') {
        console.error('Request timed out');
        toast({
          title: 'Error',
          description: 'Request timed out. Please try again.',
          variant: 'destructive',
        });
      } else {
        console.error('Error querying API:', error);
      }
      setIsStreaming(false);
      setIsLoading(false);
      toast({
        title: 'Error',
        description: 'Failed to get response. Please try again.',
        variant: 'destructive',
      });
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-4 relative">
      {/* Background decoration */}
      {companyId ? (<>
      <div className="absolute inset-0 bg-gradient-to-br from-background via-background to-muted/20 -z-10" />
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-primary/5 via-background to-background -z-10" />
      
      <div className="w-full max-w-4xl mx-auto relative z-10">
        {/* Header */}
        <div className="text-center mb-8 animate-in fade-in-50 slide-in-from-bottom-4 duration-1000">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-gradient-to-r from-blue-600 to-purple-600 rounded-2xl mb-4 shadow-lg">
            <svg className="w-8 h-8 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
            </svg>
          </div>
          <h1 className="text-4xl font-bold bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent mb-3">
            Smart Doc
          </h1>
          <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
            Get instant answers to your domain-specific questions
          </p>
        </div>

        {/* Chat Container */}
        <Card className="bg-card/50 backdrop-blur-xl border border-border/20 shadow-xl hover:shadow-2xl transition-all duration-300 animate-in fade-in-30 slide-in-from-bottom-6 duration-1000 delay-200">
          <div className="p-8">
            {/* Input Area */}
            <div className="mb-6">
              <div className="flex gap-3">
                <Input
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  onKeyPress={handleKeyPress}
                  placeholder="Ask me anything about your domain..."
                  disabled={isLoading || isStreaming}
                  className="flex-1 bg-background/50 border-border/30 focus:border-primary transition-all duration-300 text-base py-3"
                />
                <Button 
                  onClick={handleSubmit}
                  disabled={isLoading || isStreaming || !query.trim()}
                  className="bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 text-white px-8 py-3 shadow-lg hover:shadow-xl transition-all duration-300 hover:scale-105"
                >
                  {(isLoading || isStreaming) ? (
                    <Loader2 className="h-5 w-5 animate-spin" />
                  ) : (
                    <Send className="h-5 w-5" />
                  )}
                </Button>
              </div>
            </div>

            {/* Response Display */}
            {currentResponse && (
              <div className="bg-background/30 backdrop-blur-sm border border-border/20 rounded-xl p-8 animate-in fade-in-50 slide-in-from-bottom-4 duration-500">
                <div className="prose prose-slate max-w-none dark:prose-invert">
                  <ReactMarkdown
                    remarkPlugins={[remarkGfm]}
                    components={{
                      h1: ({ children }) => (
                        <h1 className="text-2xl font-bold text-foreground mb-4 leading-tight border-b border-border/20 pb-3">{children}</h1>
                      ),
                      h2: ({ children }) => (
                        <h2 className="text-xl font-semibold text-foreground mb-3 mt-6 leading-tight border-b border-border/10 pb-2">{children}</h2>
                      ),
                      h3: ({ children }) => (
                        <h3 className="text-lg font-semibold text-foreground mb-2 mt-4 leading-tight">{children}</h3>
                      ),
                      h4: ({ children }) => (
                        <h4 className="text-base font-semibold text-foreground mb-1 mt-3">{children}</h4>
                      ),
                      p: ({ children }) => (
                        <p className="text-foreground mb-2 leading-relaxed text-base">{children}</p>
                      ),
                      ul: ({ children }) => (
                        <ul className="list-disc list-outside text-foreground mb-4 space-y-2 pl-6 marker:text-primary">{children}</ul>
                      ),
                      ol: ({ children }) => (
                        <ol className="list-decimal list-outside text-foreground mb-4 space-y-2 pl-6 marker:text-primary marker:font-semibold">{children}</ol>
                      ),
                      li: ({ children }) => (
                        <li className="text-foreground leading-relaxed pl-2">{children}</li>
                      ),
                      strong: ({ children }) => (
                        <strong className="font-semibold text-foreground bg-primary/10 px-1 rounded">{children}</strong>
                      ),
                      em: ({ children }) => (
                        <em className="italic text-foreground/90">{children}</em>
                      ),
                      code: ({ children, className }) => {
                        const isInline = !className;
                        return isInline ? (
                          <code className="bg-muted text-muted-foreground px-2 py-1 rounded text-sm font-mono border">{children}</code>
                        ) : (
                          <code className="block bg-muted text-muted-foreground p-4 rounded-lg text-sm font-mono border overflow-x-auto whitespace-pre">{children}</code>
                        );
                      },
                      pre: ({ children }) => (
                        <pre className="bg-muted text-muted-foreground p-4 rounded-lg text-sm font-mono border overflow-x-auto mb-6 whitespace-pre-wrap">{children}</pre>
                      ),
                      blockquote: ({ children }) => (
                        <blockquote className="border-l-4 border-primary bg-primary/5 pl-6 py-2 my-6 italic text-foreground/90">{children}</blockquote>
                      ),
                      a: ({ href, children }) => (
                        <a 
                          href={href} 
                          className="text-primary hover:text-primary/80 underline underline-offset-2 transition-colors font-medium hover:bg-primary/10 px-1 rounded"
                          target="_blank"
                          rel="noopener noreferrer"
                        >
                          {children}
                        </a>
                      ),
                      table: ({ children }) => (
                        <div className="overflow-x-auto my-6 rounded-lg border border-border/20 shadow-sm bg-card/30">
                          <table className="w-full border-collapse">{children}</table>
                        </div>
                      ),
                      thead: ({ children }) => (
                        <thead className="bg-muted/50">{children}</thead>
                      ),
                      tbody: ({ children }) => (
                        <tbody className="bg-card/30 divide-y divide-border/10">{children}</tbody>
                      ),
                      tr: ({ children }) => (
                        <tr className="hover:bg-muted/20 transition-colors">{children}</tr>
                      ),
                      th: ({ children }) => (
                        <th className="px-4 py-3 text-left text-sm font-bold text-foreground border border-border/20 bg-muted/50 whitespace-nowrap">
                          {children}
                        </th>
                      ),
                      td: ({ children }) => (
                        <td className="px-4 py-3 text-sm text-foreground border border-border/10 whitespace-normal align-top">
                          <div className="break-words">{children}</div>
                        </td>
                      ),
                      hr: () => (
                        <hr className="my-6 border-border/30" />
                      ),
                    }}
                  >
                    {currentResponse}
                  </ReactMarkdown>
                  
                  {/* Show cursor when streaming */}
                  {isStreaming && (
                    <span className="inline-block w-3 h-5 bg-primary animate-pulse ml-1 rounded-sm"></span>
                  )}
                </div>
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
            {!currentResponse && !isLoading && !isStreaming && (
              <div className="text-center py-16 animate-in fade-in-50 slide-in-from-bottom-4 duration-700 delay-400">
                <div className="w-20 h-20 bg-gradient-to-r from-blue-600 to-purple-600 rounded-3xl flex items-center justify-center mx-auto mb-6 shadow-lg">
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
            Built with ❤️ by &amp; <a href="https://hogwartz.vercel.app" target="_blank" rel="noopener noreferrer" className="underline hover:text-primary transition-colors">Hogwartz Labs</a>. <br />
            © Hogwarz Labs.
          </p>
        </div>
      </div></>) : (
        <div className="text-center text-red-600 font-semibold">
          Company ID is required in the URL as a query parameter, e.g., ?companyId=your_company_id
        </div>)}
    </div>
  );
};

export default ChatInterface;